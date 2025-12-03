"""
Routes API pour l'interface Flask
"""

import os
import asyncio
from datetime import datetime
from pathlib import Path
from flask import Blueprint, request, jsonify, current_app, send_file, render_template
from werkzeug.utils import secure_filename
import sys

sys.path.append(str(Path(__file__).parent.parent))

from src.logger import get_logger
from src.comfyui_client import ComfyUISession, test_comfyui_connection
from src.owncloud_uploader import OwnCloudUploader, upload_cinemagraph
from workflows.workflow_manager import workflow_manager
from web_interface.jobs import JobStatus

from PIL import Image
import uuid


def resize_image_with_ultrasharp(
    input_image_path: Path,
    target_width: int,
    target_height: int,
    comfyui_client: "ComfyUISession",
) -> Path:
    """
    Redimensionne une image avec UltraSharp 4x + downscale Lanczos.

    Processus :
    1. Upscale 4x avec UltraSharp (IA)
    2. Downscale/Upscale avec Lanczos vers target exacte

    Args:
        input_image_path: Chemin de l'image source
        target_width: Largeur cible
        target_height: Hauteur cible
        comfyui_client: Client ComfyUI connecté

    Returns:
        Path vers l'image redimensionnée
    """
    logger = get_logger("resize_ultrasharp")

    # Créer mini-workflow pour upscale + resize
    workflow_id = str(uuid.uuid4())[:8]

    workflow = {
        "1": {"class_type": "LoadImage", "inputs": {"image": input_image_path.name}},
        "2": {
            "class_type": "UpscaleModelLoader",
            "inputs": {"model_name": "4x-UltraSharp.pth"},
        },
        "3": {
            "class_type": "ImageUpscaleWithModel",
            "inputs": {"upscale_model": ["2", 0], "image": ["1", 0]},
        },
        "4": {
            "class_type": "ImageScale",
            "inputs": {
                "image": ["3", 0],
                "width": target_width,
                "height": target_height,
                "upscale_method": "lanczos",
                "crop": "disabled",
            },
        },
        "5": {
            "class_type": "SaveImage",
            "inputs": {"images": ["4", 0], "filename_prefix": f"resized_{workflow_id}"},
        },
    }

    logger.info(
        f"🔧 Redimensionnement UltraSharp: {input_image_path.name} → {target_width}x{target_height}"
    )

    # Exécuter le workflow synchrone
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)

    try:
        # Soumettre workflow
        prompt_id = loop.run_until_complete(comfyui_client.queue_workflow(workflow))

        # Attendre completion (timeout 60s suffisant pour resize)
        loop.run_until_complete(comfyui_client.wait_for_workflow(prompt_id, timeout=60))

        # Récupérer l'image résultante
        outputs = loop.run_until_complete(comfyui_client.get_output_images(prompt_id))

        if not outputs:
            raise RuntimeError("Aucune image générée par le workflow de resize")

        # L'image est dans le dossier output de ComfyUI
        output_dir = (
            Path("/workspace/comfyui/ComfyUI/output")
            if Path("/workspace").exists()
            else Path("output")
        )
        resized_image = output_dir / outputs[0]["filename"]

        if not resized_image.exists():
            raise RuntimeError(f"Image redimensionnée non trouvée: {resized_image}")

        logger.success(f"✅ Image redimensionnée: {resized_image.name}")
        return resized_image

    finally:
        loop.close()


def calculate_optimal_resolution(
    source_width: int, source_height: int, target_width: int, target_height: int
) -> tuple:
    """
    Calcule la résolution optimale en conservant le ratio

    Args:
        source_width, source_height: Résolution source
        target_width, target_height: Résolution demandée

    Returns:
        (final_width, final_height): Résolution ajustée (multiple de 32)
    """
    # Ratio de l'image source
    source_ratio = source_width / source_height

    # Arrondir à un multiple de 32 (requis par le VAE WAN 2.2 avec spatial_compress_level=1)
    def round_to_multiple(value, multiple=32):
        return int(round(value / multiple) * multiple)

    # Calculer selon le ratio source
    if target_width / target_height > source_ratio:
        # Limité par la hauteur
        final_height = round_to_multiple(target_height)
        final_width = round_to_multiple(final_height * source_ratio)
    else:
        # Limité par la largeur
        final_width = round_to_multiple(target_width)
        final_height = round_to_multiple(final_width / source_ratio)

    return final_width, final_height


def calculate_optimal_generation_strategy(
    source_width: int,
    source_height: int,
    target_width: int,
    target_height: int,
) -> dict:
    """
    Calcule la stratégie de génération optimale pour minimiser les artefacts d'upscale.

    Specs officielles WAN 2.2 (5B et 14B) :
    - Résolution max native : 1280x720 (720p)
    - Sweet spot upscale : 2-4x
    - Limite acceptable : 8x
    - Au-delà de 8x : artefacts possibles (mais génération autorisée)

    Args:
        source_width, source_height: Dimensions image source
        target_width, target_height: Dimensions cible finales

    Returns:
        dict: {
            'generation_width': int,      # Résolution pour WAN 2.2
            'generation_height': int,
            'upscale_ratio': float,       # Ratio upscale final
            'total_ratio': float,         # Ratio source→cible
            'quality_warning': str|None,  # Warning si ratio extrême
            'strategy': str              # Description stratégie
        }
    """
    # Constantes officielles
    WAN22_MAX_WIDTH = 1280
    WAN22_MAX_HEIGHT = 720
    WAN22_MAX_PIXELS = WAN22_MAX_WIDTH * WAN22_MAX_HEIGHT

    UPSCALE_OPTIMAL_RATIO = 2.5  # Sweet spot (qualité optimale)
    UPSCALE_MAX_RATIO = 4.0  # Limite qualité acceptable
    UPSCALE_WARNING_RATIO = 8.0  # Au-delà : avertissement

    # Fonction utilitaire
    def adjust_to_32(value):
        return int(round(value / 32) * 32)

    # Calculer ratios
    source_pixels = source_width * source_height
    target_pixels = target_width * target_height
    total_ratio = target_pixels / source_pixels
    aspect_ratio = source_width / source_height

    # Cas 1 : Pas besoin d'upscale ou upscale modéré (≤4x)
    if total_ratio <= UPSCALE_MAX_RATIO:
        gen_w = adjust_to_32(source_width)
        gen_h = adjust_to_32(source_height)
        upscale_ratio = (target_width * target_height) / (gen_w * gen_h)

        return {
            "generation_width": gen_w,
            "generation_height": gen_h,
            "upscale_ratio": upscale_ratio,
            "total_ratio": total_ratio,
            "quality_warning": None,
            "strategy": f"Génération à résolution source ({gen_w}x{gen_h}), upscale modéré {upscale_ratio:.1f}x",
        }

    # Cas 2 : Upscale agressif (>4x)
    # Calculer résolution intermédiaire optimale
    optimal_gen_pixels = target_pixels / (UPSCALE_OPTIMAL_RATIO**2)

    # Respecter limite 720p
    if optimal_gen_pixels > WAN22_MAX_PIXELS:
        optimal_gen_pixels = WAN22_MAX_PIXELS

    # Calculer dimensions en préservant aspect ratio
    gen_h = int((optimal_gen_pixels / aspect_ratio) ** 0.5)
    gen_w = int(gen_h * aspect_ratio)

    # Ajuster aux multiples de 32
    gen_w = adjust_to_32(gen_w)
    gen_h = adjust_to_32(gen_h)

    # Double-check : ne pas dépasser 1280x720
    if gen_w > WAN22_MAX_WIDTH:
        gen_w = WAN22_MAX_WIDTH
        gen_h = adjust_to_32(int(WAN22_MAX_WIDTH / aspect_ratio))

    if gen_h > WAN22_MAX_HEIGHT:
        gen_h = WAN22_MAX_HEIGHT
        gen_w = adjust_to_32(int(WAN22_MAX_HEIGHT * aspect_ratio))

    # Recalculer ratio upscale final
    upscale_ratio = (target_width * target_height) / (gen_w * gen_h)

    # Générer warning si ratio extrême
    quality_warning = None
    if upscale_ratio > UPSCALE_WARNING_RATIO:
        quality_warning = f"⚠️ Ratio upscale très élevé ({upscale_ratio:.1f}x). Des artefacts peuvent apparaître. Considérez réduire la résolution cible."

    return {
        "generation_width": gen_w,
        "generation_height": gen_h,
        "upscale_ratio": upscale_ratio,
        "total_ratio": total_ratio,
        "quality_warning": quality_warning,
        "strategy": f"Génération optimisée à {gen_w}x{gen_h} (proche max 720p), upscale {upscale_ratio:.1f}x vers résolution cible",
    }


logger = get_logger("flask_routes")

# Blueprints
api_bp = Blueprint("api", __name__)
main_bp = Blueprint("main", __name__)


# Helper functions
def allowed_file(filename):
    """Vérifie si l'extension du fichier est autorisée"""
    return (
        "." in filename
        and filename.rsplit(".", 1)[1].lower()
        in current_app.config["ALLOWED_EXTENSIONS"]
    )


def get_file_path(filename):
    """Retourne le chemin complet d'un fichier uploadé"""
    return os.path.join(current_app.config["UPLOAD_FOLDER"], filename)


async def process_cinemagraph_generation(job_id: str):
    """
    Traite la génération d'un cinemagraph de manière asynchrone

    Args:
        job_id: ID du job à traiter
    """
    # Récupérer depuis le contexte Flask
    from flask import current_app as app

    try:
        job_manager = app.job_manager
        comfyui_config = app.comfyui_config
    except RuntimeError:
        # Contexte Flask non disponible - ne devrait jamais arriver après correction #2
        logger.error(f"Contexte Flask non disponible pour job {job_id}")
        return

    job = job_manager.get_job(job_id)

    if not job:
        logger.error(f"Job non trouvé: {job_id}")
        return

    try:
        # 1. Préparer le workflow
        job_manager.update_job(
            job_id,
            status=JobStatus.PROCESSING,
            current_step="Préparation du workflow",
            progress=0.1,
        )

        # Sélection automatique du workflow selon résolution
        img_path = Path(job.input_image)
        with Image.open(job.input_image) as img:
            source_width, source_height = img.size

        # Résolution demandée dans les paramètres
        target_width = job.parameters.get("width", source_width)
        target_height = job.parameters.get("height", source_height)

        # Ajuster les dimensions pour compatibilité WAN 2.2 (multiples de 32)
        # Note: Avec spatial_compress_level=1, le VAE nécessite des multiples de 32
        def adjust_dimension(value):
            """Ajuste une dimension pour qu'elle soit un multiple de 32"""
            return int(round(value / 32) * 32)

        # Ajuster dimensions source
        adjusted_source_width = adjust_dimension(source_width)
        adjusted_source_height = adjust_dimension(source_height)

        # Ajuster dimensions cibles
        adjusted_target_width = adjust_dimension(target_width)
        adjusted_target_height = adjust_dimension(target_height)

        # Calculer la stratégie de génération optimale
        strategy = calculate_optimal_generation_strategy(
            adjusted_source_width,
            adjusted_source_height,
            adjusted_target_width,
            adjusted_target_height,
        )

        generation_width = strategy["generation_width"]
        generation_height = strategy["generation_height"]
        upscale_ratio = strategy["upscale_ratio"]

        # Déterminer si on doit redimensionner l'image AVANT génération
        # Cas 1: Ajustement aux multiples de 32 (source → adjusted_source)
        # Cas 2: Upscale pour génération optimale (adjusted_source → generation)
        needs_resize_to_adjusted = (
            adjusted_source_width != source_width
            or adjusted_source_height != source_height
        )
        needs_upscale_for_generation = (
            generation_width > adjusted_source_width
            or generation_height > adjusted_source_height
        )

        image_to_upload = job.input_image
        upload_filename = img_path.name

        # Étape 1: Ajustement multiples de 32 si nécessaire (LANCZOS rapide)
        if needs_resize_to_adjusted:
            logger.info(
                f"📐 Ajustement multiples de 32: "
                f"{source_width}x{source_height} → {adjusted_source_width}x{adjusted_source_height}"
            )

            with Image.open(job.input_image) as img:
                resized_img = img.resize(
                    (adjusted_source_width, adjusted_source_height),
                    Image.Resampling.LANCZOS,
                )

                adjusted_path = (
                    img_path.parent / f"{img_path.stem}_adjusted{img_path.suffix}"
                )

                resized_img.save(adjusted_path, quality=95)
                logger.info(f"   ✅ Image ajustée: {adjusted_path.name}")

            image_to_upload = adjusted_path
            upload_filename = adjusted_path.name

        # Étape 2: Upscale pour génération optimale (UltraSharp + Lanczos)
        if needs_upscale_for_generation:
            logger.info(
                f"🎨 Upscale pré-génération (UltraSharp 4x + Lanczos): "
                f"{adjusted_source_width}x{adjusted_source_height} → {generation_width}x{generation_height}"
            )

            # Créer client ComfyUI temporaire pour le resize
            comfyui_client = ComfyUISession(config=current_app.config["comfyui_config"])

            try:
                # Connecter au serveur ComfyUI
                loop = asyncio.new_event_loop()
                asyncio.set_event_loop(loop)
                loop.run_until_complete(comfyui_client.connect())

                # Upscaler avec UltraSharp
                upscaled_path = resize_image_with_ultrasharp(
                    input_image_path=image_to_upload,
                    target_width=generation_width,
                    target_height=generation_height,
                    comfyui_client=comfyui_client,
                )

                image_to_upload = upscaled_path
                upload_filename = upscaled_path.name

                logger.success(
                    f"✅ Image upscalée pour génération optimale: {upload_filename}"
                )

            finally:
                loop.run_until_complete(comfyui_client.disconnect())
                loop.close()

        # Logger la stratégie choisie
        logger.info("📐 Stratégie de génération complète:")
        logger.info(f"   Image source originale: {source_width}x{source_height}")
        logger.info(
            f"   Image ajustée (×32): {adjusted_source_width}x{adjusted_source_height}"
        )
        logger.info(f"   Génération WAN 2.2: {generation_width}x{generation_height}")
        logger.info(
            f"   Résolution finale: {adjusted_target_width}x{adjusted_target_height}"
        )

        # Messages sur l'upscale post-génération
        if upscale_ratio > 1.5:
            logger.info(
                f"   Upscale post-génération: {generation_width}x{generation_height} → "
                f"{adjusted_target_width}x{adjusted_target_height} ({upscale_ratio:.2f}x)"
            )

            if upscale_ratio <= 4.0:
                logger.success(
                    f"   ✅ Upscale optimal ({upscale_ratio:.2f}x ≤ 4x) - 4x-UltraSharp + affinage Lanczos"
                )
            else:
                logger.warning(
                    f"   ⚠️  Upscale élevé ({upscale_ratio:.2f}x > 4x) - 4x UltraSharp + {upscale_ratio / 4:.2f}x Lanczos supplémentaire"
                )
                logger.warning(
                    "   Des artefacts peuvent apparaître au-delà de 4x. Qualité optimale garantie jusqu'à 4x."
                )

        # Calculer si VAE tiling doit être activé (pour résolutions >1080p ou upscale >4x)
        target_pixels = adjusted_target_width * adjusted_target_height
        enable_vae_tiling = target_pixels > (1920 * 1080) or upscale_ratio > 4.0

        # Sélectionner le workflow
        if upscale_ratio > 1.5:  # Besoin d'upscale intelligent
            selected_workflow = "wan22_with_upscale"
            logger.info(
                f"🔍 Workflow upscale sélectionné (ratio: {upscale_ratio:.2f}x)"
            )

            # Pour le workflow upscale, utiliser la résolution de génération optimale calculée
            # L'upscaling sera fait par 4x-UltraSharp (node 11) + resize Lanczos (node 11b)
            workflow_params = {
                "input_image": upload_filename,
                "prompt": job.prompt,
                "negative_prompt": job.parameters.get("negative_prompt", ""),
                **job.parameters,
                "width": generation_width,  # Résolution génération WAN 2.2
                "height": generation_height,
                "target_width": adjusted_target_width,  # Résolution finale après upscale
                "target_height": adjusted_target_height,
                "enable_vae_tiling": enable_vae_tiling,
            }

            if enable_vae_tiling:
                logger.info(
                    f"🔧 VAE tiling activé (résolution finale: {adjusted_target_width}x{adjusted_target_height}, upscale: {upscale_ratio:.2f}x)"
                )
        else:
            selected_workflow = "wan22_i2v"
            logger.info(f"✅ Workflow standard (ratio: {upscale_ratio:.2f}x)")

            # Pour génération standard, utiliser les dimensions optimales
            workflow_params = {
                "input_image": upload_filename,
                "prompt": job.prompt,
                "negative_prompt": job.parameters.get("negative_prompt", ""),
                **job.parameters,
                "width": generation_width,
                "height": generation_height,
                "enable_vae_tiling": enable_vae_tiling,
            }

            if enable_vae_tiling:
                logger.info(
                    f"🔧 VAE tiling activé (résolution: {generation_width}x{generation_height})"
                )

        workflow = workflow_manager.create_workflow(selected_workflow, workflow_params)

        # 2. Générer le cinemagraph
        job_manager.update_job(
            job_id, current_step="Génération du cinemagraph", progress=0.3
        )

        async with ComfyUISession(comfyui_config) as client:
            # Upload de l'image (originale ou redimensionnée)
            with open(image_to_upload, "rb") as f:
                image_data = f.read()

            # Lancer le workflow
            comfyui_workflow_id = await client.queue_prompt(
                workflow, images={upload_filename: image_data}
            )

            job_manager.update_job(job_id, workflow_id=comfyui_workflow_id)

            # Attendre la completion
            job_manager.update_job(
                job_id, current_step="Génération en cours...", progress=0.5
            )

            workflow_result = await client.wait_for_completion(comfyui_workflow_id)
            logger.info(
                f"Workflow terminé: {workflow_result.status if hasattr(workflow_result, 'status') else 'completed'}"
            )

            # Récupérer les images de sortie
            job_manager.update_job(
                job_id, current_step="Récupération du résultat", progress=0.8
            )

            output_images = await client.get_output_images(comfyui_workflow_id)

            if not output_images:
                raise Exception("Aucune vidéo générée")

            # Sauvegarder la vidéo
            output_path = os.path.join(
                app.config["UPLOAD_FOLDER"], f"output_{job_id}.mp4"
            )
            with open(output_path, "wb") as f:
                f.write(output_images[0]["data"])

            job_manager.update_job(job_id, output_video=output_path)

        # 3. Terminer (upload OwnCloud manuel via l'interface)
        job_manager.update_job(
            job_id, status=JobStatus.COMPLETED, progress=1.0, current_step="Terminé"
        )

        logger.success(f"Job {job_id} terminé avec succès")

    except Exception as e:
        logger.error(f"Erreur job {job_id}: {e}")
        import traceback

        logger.error(traceback.format_exc())
        job_manager.update_job(job_id, status=JobStatus.FAILED, error_message=str(e))

    finally:
        # Nettoyer les images redimensionnées temporaires si elles existent
        if (
            needs_resize_to_adjusted or needs_upscale_for_generation
        ) and image_to_upload.exists():
            try:
                image_to_upload.unlink()
                logger.debug(f"   🗑️ Image temporaire supprimée: {image_to_upload.name}")
            except Exception as cleanup_error:
                logger.warning(
                    f"   ⚠️ Impossible de supprimer {image_to_upload}: {cleanup_error}"
                )


# === ROUTES PRINCIPALES ===


@main_bp.route("/")
def index():
    """Page d'accueil"""
    return render_template("index.html")


# === ROUTES API ===


@api_bp.route("/analyze-image", methods=["POST"])
def analyze_image():
    """
    Analyse une image uploadée et retourne ses dimensions

    Body:
        - image: Fichier image

    Returns:
        JSON avec dimensions source
    """
    if "image" not in request.files:
        return jsonify({"error": "Aucune image fournie"}), 400

    file = request.files["image"]

    if not allowed_file(file.filename):
        return jsonify({"error": "Type de fichier non autorisé"}), 400

    try:
        # Ouvrir l'image avec PIL
        img = Image.open(file.stream)
        width, height = img.size

        return jsonify(
            {
                "width": width,
                "height": height,
                "ratio": round(width / height, 2),
                "format": img.format,
                "mode": img.mode,
            }
        )
    except Exception as e:
        logger.error(f"Erreur analyse image: {e}")
        return jsonify({"error": f"Erreur analyse image: {str(e)}"}), 400


@api_bp.route("/calculate-resolution", methods=["POST"])
def calc_resolution():
    """
    Calcule la résolution optimale

    Body JSON:
        - source_width, source_height: Dimensions source
        - target_width, target_height: Dimensions demandées

    Returns:
        JSON avec résolution finale
    """
    data = request.get_json()

    try:
        # Validation des données avec valeurs par défaut
        source_w = int(data.get("source_width") or 1920)
        source_h = int(data.get("source_height") or 1080)
        target_w = int(data.get("target_width") or source_w)
        target_h = int(data.get("target_height") or source_h)

        # Vérifier que les valeurs sont positives
        if source_w <= 0 or source_h <= 0 or target_w <= 0 or target_h <= 0:
            return jsonify({"error": "Les dimensions doivent être positives"}), 400

        final_w, final_h = calculate_optimal_resolution(
            source_w, source_h, target_w, target_h
        )

        # Protection contre division par zéro
        ratio = round(final_w / final_h, 2) if final_h > 0 else 0

        return jsonify(
            {
                "final_width": final_w,
                "final_height": final_h,
                "ratio": ratio,
                "adjusted": (final_w != target_w or final_h != target_h),
            }
        )
    except (KeyError, ValueError) as e:
        return jsonify({"error": f"Paramètres invalides: {str(e)}"}), 400


@api_bp.route("/generate", methods=["POST"])
def generate_cinemagraph():
    """
    Crée un job de génération de cinemagraph

    Body:
        - image: Fichier image
        - prompt: Prompt de génération
        - negative_prompt: Negative prompt (optionnel)
        - target_width, target_height: Résolution demandée
        - duration: Durée en secondes
        - fps: Images par seconde
        - parameters: Autres paramètres JSON
    """
    # Vérifier que ComfyUI est accessible AVANT de créer le job
    try:
        comfyui_accessible = asyncio.run(
            test_comfyui_connection(current_app.comfyui_config)
        )
        if not comfyui_accessible:
            logger.error("ComfyUI inaccessible lors de la requête de génération")
            return (
                jsonify(
                    {
                        "error": "ComfyUI n'est pas accessible. Veuillez réessayer dans quelques instants.",
                        "details": "Le service de génération n'est pas prêt. Cela peut arriver au démarrage.",
                    }
                ),
                503,
            )
    except Exception as e:
        logger.error(f"Erreur lors de la vérification de ComfyUI: {e}")
        return (
            jsonify(
                {
                    "error": "Impossible de vérifier l'état de ComfyUI",
                    "details": str(e),
                }
            ),
            503,
        )

    # Vérifier l'image
    if "image" not in request.files:
        return jsonify({"error": "Aucune image fournie"}), 400

    file = request.files["image"]
    if file.filename == "" or not allowed_file(file.filename):
        return jsonify({"error": "Fichier invalide"}), 400

    # Sauvegarder l'image
    filename = secure_filename(file.filename)
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    filename = f"{timestamp}_{filename}"
    filepath = get_file_path(filename)
    file.save(filepath)

    # Analyser l'image pour obtenir les dimensions source
    try:
        with Image.open(filepath) as img:
            source_width, source_height = img.size
    except Exception as e:
        return jsonify({"error": f"Erreur lecture image: {e}"}), 400

    # Récupérer les paramètres
    prompt = request.form.get("prompt", "")
    negative_prompt = request.form.get("negative_prompt", "")

    # Résolution
    target_width = int(request.form.get("target_width", source_width))
    target_height = int(request.form.get("target_height", source_height))

    final_width, final_height = calculate_optimal_resolution(
        source_width, source_height, target_width, target_height
    )

    # Paramètres temporels
    duration = float(request.form.get("duration", 5.0))  # secondes
    fps = int(request.form.get("fps", 24))
    frames = int(duration * fps)

    # Autres paramètres
    try:
        import json

        parameters = json.loads(request.form.get("parameters", "{}"))
    except (json.JSONDecodeError, TypeError, ValueError):
        parameters = {}

    # Paramètres par défaut
    parameters.setdefault("steps", 20)
    parameters.setdefault("cfg_scale", 7.5)
    parameters.setdefault("noise_level", "high")

    # Ajouter les nouveaux paramètres
    parameters.update(
        {
            "width": final_width,
            "height": final_height,
            "frames": frames,
            "fps": fps,
            "duration": duration,
            "negative_prompt": negative_prompt,
        }
    )

    # Créer le job
    job = current_app.job_manager.create_job(
        input_image=filepath, prompt=prompt, parameters=parameters
    )

    # ============================================================
    # CORRECTION: Génération avec contexte Flask
    # ============================================================
    import threading

    # Récupérer l'app Flask et les configs AVANT le thread
    app = current_app._get_current_object()
    job_manager = current_app.job_manager
    comfyui_cfg = current_app.comfyui_config

    def run_async(job_id: str):
        """Exécute la génération async avec contexte Flask"""
        # Créer une nouvelle event loop
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)

        try:
            # Exécuter avec le contexte Flask
            with app.app_context():
                # Restaurer les configs dans le contexte
                current_app.job_manager = job_manager
                current_app.comfyui_config = comfyui_cfg

                loop.run_until_complete(process_cinemagraph_generation(job_id))
        except Exception as e:
            logger.error(f"Erreur dans run_async pour job {job_id}: {e}")
            import traceback

            logger.error(traceback.format_exc())
        finally:
            loop.close()

    thread = threading.Thread(target=run_async, args=(job.job_id,), daemon=True)
    thread.start()
    # ============================================================

    logger.info(f"Génération lancée pour job: {job.job_id}")
    logger.info(
        f"   Résolution: {final_width}x{final_height} ({frames} frames @ {fps}fps)"
    )
    # Log du workflow qui sera utilisé
    scale_ratio = (final_width * final_height) / (source_width * source_height)
    expected_workflow = "wan22_with_upscale" if scale_ratio > 1.5 else "wan22_i2v"
    logger.info(f"   Workflow: {expected_workflow} (ratio: {scale_ratio:.2f}x)")

    return jsonify(
        {
            "job_id": job.job_id,
            "status": job.status.value,
            "message": "Génération lancée",
            "resolution": {
                "source": f"{source_width}x{source_height}",
                "final": f"{final_width}x{final_height}",
                "frames": frames,
                "fps": fps,
                "duration": duration,
            },
        }
    ), 202


@api_bp.route("/jobs/<job_id>", methods=["GET"])
def get_job_status(job_id):
    """
    Récupère le statut d'un job

    Args:
        job_id: ID du job

    Returns:
        JSON avec les détails du job
    """
    job = current_app.job_manager.get_job(job_id)

    if not job:
        return jsonify({"error": "Job non trouvé"}), 404

    return jsonify(job.to_dict())


@api_bp.route("/jobs", methods=["GET"])
def list_jobs():
    """
    Liste tous les jobs

    Query params:
        - status: Filtrer par statut (optionnel)
        - limit: Nombre max de résultats (défaut: 50)

    Returns:
        JSON avec liste des jobs
    """
    status_filter = request.args.get("status")
    limit = int(request.args.get("limit", 50))

    # Convertir le statut si fourni
    status_enum = None
    if status_filter:
        try:
            status_enum = JobStatus(status_filter)
        except ValueError:
            return jsonify({"error": f"Statut invalide: {status_filter}"}), 400

    jobs = current_app.job_manager.list_jobs(status=status_enum, limit=limit)

    return jsonify({"jobs": [job.to_dict() for job in jobs], "count": len(jobs)})


@api_bp.route("/jobs/<job_id>", methods=["DELETE"])
def delete_job(job_id):
    """
    Supprime un job terminé

    Args:
        job_id: ID du job

    Returns:
        JSON avec résultat
    """
    success = current_app.job_manager.delete_job(job_id)

    if success:
        return jsonify({"message": "Job supprimé"}), 200
    else:
        return jsonify(
            {"error": "Impossible de supprimer le job (actif ou inexistant)"}
        ), 400


@api_bp.route("/jobs/<job_id>/download", methods=["GET"])
def download_result(job_id):
    """
    Télécharge le résultat d'un job

    Args:
        job_id: ID du job

    Returns:
        Fichier vidéo
    """
    job = current_app.job_manager.get_job(job_id)

    if not job:
        return jsonify({"error": "Job non trouvé"}), 404

    if job.status != JobStatus.COMPLETED:
        return jsonify({"error": "Job non terminé"}), 400

    if not job.output_video or not os.path.exists(job.output_video):
        return jsonify({"error": "Fichier de sortie introuvable"}), 404

    return send_file(
        job.output_video,
        mimetype="video/mp4",
        as_attachment=True,
        download_name=f"cinemagraph_{job_id}.mp4",
    )


@api_bp.route("/jobs/<job_id>/upload-owncloud", methods=["POST"])
def manual_upload_to_owncloud(job_id):
    """
    Upload manuel d'un cinemagraph vers OwnCloud

    Args:
        job_id: ID du job

    Returns:
        JSON avec résultat de l'upload
    """
    job = current_app.job_manager.get_job(job_id)

    if not job:
        return jsonify({"error": "Job non trouvé"}), 404

    if job.status != JobStatus.COMPLETED:
        return jsonify({"error": "Job non terminé"}), 400

    if not job.output_video or not os.path.exists(job.output_video):
        return jsonify({"error": "Fichier de sortie introuvable"}), 404

    if not current_app.owncloud_config:
        return jsonify({"error": "OwnCloud non configuré"}), 503

    # Si déjà uploadé
    if job.owncloud_link:
        return jsonify(
            {
                "success": True,
                "message": "Déjà uploadé",
                "share_link": job.owncloud_link,
            }
        )

    try:
        # Upload synchrone
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)

        async def do_upload():
            async with OwnCloudUploader(current_app.owncloud_config) as uploader:
                result = await upload_cinemagraph(
                    uploader=uploader,
                    video_file=Path(job.output_video),
                    workflow_id=job.workflow_id or job.job_id,
                    prompt=job.prompt,
                    generation_params=job.parameters,
                    create_share=True,
                )
                return result

        upload_result = loop.run_until_complete(do_upload())

        if upload_result.success:
            # Mettre à jour le job
            current_app.job_manager.update_job(
                job_id, owncloud_link=upload_result.share_link
            )

            return jsonify(
                {
                    "success": True,
                    "message": "Upload réussi",
                    "share_link": upload_result.share_link,
                }
            )
        else:
            return jsonify(
                {"success": False, "error": upload_result.error or "Upload échoué"}
            ), 500

    except Exception as e:
        logger.error(f"Erreur upload manuel OwnCloud: {e}")
        return jsonify({"success": False, "error": str(e)}), 500


@api_bp.route("/statistics", methods=["GET"])
def get_statistics():
    """
    Retourne les statistiques des jobs

    Returns:
        JSON avec statistiques
    """
    stats = current_app.job_manager.get_statistics()
    return jsonify(stats)


@api_bp.route("/templates", methods=["GET"])
def list_templates():
    """
    Liste les templates de workflows disponibles

    Returns:
        JSON avec liste des templates
    """
    templates = workflow_manager.list_templates()
    return jsonify({"templates": templates, "count": len(templates)})


@api_bp.route("/config/comfyui", methods=["GET"])
def check_comfyui():
    """
    Vérifie la connexion à ComfyUI

    Returns:
        JSON avec statut ComfyUI
    """
    if not current_app.comfyui_config:
        return jsonify({"error": "ComfyUI non configuré"}), 503

    loop = asyncio.new_event_loop()
    is_connected = loop.run_until_complete(
        test_comfyui_connection(current_app.comfyui_config)
    )

    return jsonify(
        {
            "connected": is_connected,
            "host": current_app.comfyui_config.host,
            "port": current_app.comfyui_config.port,
        }
    )


@api_bp.route("/config/owncloud", methods=["GET"])
def check_owncloud():
    """
    Vérifie la configuration OwnCloud

    Returns:
        JSON avec statut OwnCloud
    """
    if not current_app.owncloud_config:
        return jsonify({"configured": False, "message": "OwnCloud non configuré"})

    return jsonify(
        {
            "configured": True,
            "server": current_app.owncloud_config.server_url,
            "upload_folder": current_app.owncloud_config.upload_folder,
        }
    )


@api_bp.route("/jobs/<job_id>/thumbnail", methods=["GET"])
def get_thumbnail(job_id):
    """Retourne une miniature du résultat (placeholder pour l'instant)"""
    # TODO: Générer vraie miniature avec PIL
    from flask import send_file
    import io
    from PIL import Image

    # Placeholder image
    img = Image.new("RGB", (400, 300), color="#667eea")
    img_io = io.BytesIO()
    img.save(img_io, "JPEG")
    img_io.seek(0)

    return send_file(img_io, mimetype="image/jpeg")
