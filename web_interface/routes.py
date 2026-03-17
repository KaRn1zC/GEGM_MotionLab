"""
Routes API pour l'interface Flask
"""

import os
import asyncio
from datetime import datetime
from pathlib import Path
from flask import Blueprint, request, jsonify, current_app, send_file, render_template
from werkzeug.utils import secure_filename
import subprocess
import sys


from src.logger import get_logger
from src.comfyui_client import ComfyUISession, test_comfyui_connection
from src.model_registry import get_registry
from src.owncloud_uploader import OwnCloudUploader, upload_cinemagraph
from workflows.workflow_manager import workflow_manager
from web_interface.jobs import JobStatus

from PIL import Image


def find_best_generation_dims(
    width: int, height: int, multiple: int = 32
) -> tuple[int, int]:
    """
    Trouve les dimensions multiples de `multiple` les plus proches du ratio original.

    Teste les 4 combinaisons (floor/ceil) x (width/height) et retourne celle
    qui préserve le mieux le ratio d'aspect, évitant le drift systématique du floor.

    Args:
        width: Largeur à ajuster
        height: Hauteur à ajuster
        multiple: Multiple cible (défaut: 32)

    Returns:
        (width, height) ajustés aux multiples de `multiple` avec ratio optimal
    """
    original_ratio = width / height

    w_floor = (width // multiple) * multiple
    w_ceil = w_floor + (multiple if w_floor != width else 0)
    h_floor = (height // multiple) * multiple
    h_ceil = h_floor + (multiple if h_floor != height else 0)

    candidates = [
        (w_floor, h_floor),
        (w_floor, h_ceil),
        (w_ceil, h_floor),
        (w_ceil, h_ceil),
    ]
    # Filtrer les candidats à 0
    candidates = [(w, h) for w, h in candidates if w > 0 and h > 0]

    return min(candidates, key=lambda c: abs(c[0] / c[1] - original_ratio))


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

    # Calculer selon le ratio source
    if target_width / target_height > source_ratio:
        # Limité par la hauteur
        raw_height = target_height
        raw_width = int(raw_height * source_ratio)
    else:
        # Limité par la largeur
        raw_width = target_width
        raw_height = int(raw_width / source_ratio)

    # Arrondi intelligent : teste les 4 combinaisons floor/ceil pour le meilleur ratio
    # Requis par le VAE WAN 2.2 (multiples de 32)
    return find_best_generation_dims(raw_width, raw_height)


def calculate_optimal_generation_strategy(
    source_width: int,
    source_height: int,
    target_width: int,
    target_height: int,
    model_name: str | None = None,
) -> dict:
    """
    Calcule la stratégie de génération optimale, adaptée au modèle actif.

    Interroge le registre pour obtenir les capacités de résolution du modèle,
    avec fallback sur les valeurs WAN 2.2 si le modèle est inconnu ou absent.

    Principe :
    1. Si source < résolution native → upscale Lanczos pré-génération
    2. Si source > résolution native → downscale Lanczos pré-génération
    3. Si source ≈ résolution native → ajuster multiples du stride uniquement
    4. Génération à résolution native du modèle
    5. Post-génération : upscale vers target si nécessaire

    Args:
        source_width, source_height: Dimensions image source (déjà ajustées au stride)
        target_width, target_height: Dimensions cible finales
        model_name: Nom du modèle dans le registre (fallback WAN 2.2 si None)

    Returns:
        dict avec generation_width, generation_height, needs_pregen_resize,
        resize_type, upscale_ratio, total_ratio, use_supersampling,
        dimension_stride, strategy
    """
    from src.model_registry import ResolutionConfig

    # Lookup registre avec fallback WAN 2.2 legacy
    res: ResolutionConfig | None = None
    try:
        registry = get_registry()
        res = registry.get_resolution_config(model_name) if model_name else None
    except Exception:
        pass

    if not res:
        res = ResolutionConfig(
            max_width=1280, max_height=720, dimension_stride=32,
            upscale_trigger_ratio=1.5, supersampling_max_ratio=4.0,
            vae_tiling_pixel_threshold=2073600, vae_tiling_upscale_threshold=4.0,
        )

    max_w = res.max_width
    max_h = res.max_height
    max_pixels = res.max_pixels
    stride = res.dimension_stride

    # Calculer ratios et dimensions
    source_pixels = source_width * source_height
    target_pixels = target_width * target_height
    total_ratio = target_pixels / source_pixels
    aspect_ratio = source_width / source_height

    # Si target ≤ source, générer à résolution source (pas d'upscale inutile)
    if target_width <= source_width and target_height <= source_height:
        gen_w = source_width
        gen_h = source_height
    else:
        # Dimensions max possibles en conservant ratio
        if aspect_ratio >= (max_w / max_h):
            gen_w = max_w
            gen_h = int(max_w / aspect_ratio)
        else:
            gen_h = max_h
            gen_w = int(max_h * aspect_ratio)

        # Ajuster aux multiples du stride (arrondi ratio-aware)
        gen_w, gen_h = find_best_generation_dims(gen_w, gen_h, multiple=stride)

        # Vérifier si on dépasse la résolution native après ajustement
        if gen_w * gen_h > max_pixels:
            if aspect_ratio >= (max_w / max_h):
                raw_w = max_w - stride
                raw_h = int(raw_w / aspect_ratio)
            else:
                raw_h = max_h - stride
                raw_w = int(raw_h * aspect_ratio)
            gen_w, gen_h = find_best_generation_dims(raw_w, raw_h, multiple=stride)

    # Déterminer si redimensionnement pré-génération nécessaire
    needs_pregen_resize = gen_w != source_width or gen_h != source_height

    # Déterminer type de redimensionnement pré-génération
    if source_pixels < gen_w * gen_h:
        resize_type = "upscale"
        strategy_desc = f"Upscale Lanczos pré-génération: {source_width}x{source_height} → {gen_w}x{gen_h}"
    elif source_pixels > gen_w * gen_h:
        resize_type = "downscale"
        strategy_desc = f"Downscale Lanczos pré-génération: {source_width}x{source_height} → {gen_w}x{gen_h}"
    else:
        resize_type = "none"
        strategy_desc = f"Génération directe à résolution source: {gen_w}x{gen_h}"

    # Calculer ratio upscale post-génération
    upscale_ratio = (target_width * target_height) / (gen_w * gen_h)
    use_supersampling = upscale_ratio <= res.supersampling_max_ratio

    return {
        "generation_width": gen_w,
        "generation_height": gen_h,
        "needs_pregen_resize": needs_pregen_resize,
        "resize_type": resize_type,
        "upscale_ratio": upscale_ratio,
        "total_ratio": total_ratio,
        "use_supersampling": use_supersampling,
        "dimension_stride": stride,
        "strategy": strategy_desc,
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

        # Résolution demandée dans les paramètres (déjà ajustée multiples 32 par generate_cinemagraph)
        target_width = job.parameters.get("width", source_width)
        target_height = job.parameters.get("height", source_height)

        # Dimensions exactes demandées par l'utilisateur (avant ajustement multiples de 32)
        user_target_width = job.parameters.get("user_target_width", target_width)
        user_target_height = job.parameters.get("user_target_height", target_height)

        # Détecter le modèle disponible AVANT le calcul de stratégie
        from workflows.workflow_manager import WorkflowTemplate

        temp_template = WorkflowTemplate({"parameters": {}, "workflow": {}})
        detected_model, model_type = temp_template._detect_available_model()
        logger.info(f"🤖 Modèle détecté: {detected_model} (type: {model_type})")

        # Obtenir la config du modèle depuis le registre (pour stride, seuils, etc.)
        model_cfg = None
        try:
            _registry = get_registry()
            model_cfg = _registry.get_model(detected_model)
        except Exception:
            pass

        # Stride d'alignement depuis le registre (fallback 32)
        stride = 32
        if model_cfg and model_cfg.resolution:
            stride = model_cfg.resolution.dimension_stride

        # Ajuster dimensions source et cible au stride du modèle
        adjusted_source_width, adjusted_source_height = find_best_generation_dims(
            source_width, source_height, multiple=stride
        )
        adjusted_target_width, adjusted_target_height = find_best_generation_dims(
            target_width, target_height, multiple=stride
        )

        # Calculer la stratégie de génération optimale selon le modèle
        strategy = calculate_optimal_generation_strategy(
            adjusted_source_width,
            adjusted_source_height,
            adjusted_target_width,
            adjusted_target_height,
            model_name=detected_model,
        )

        generation_width = strategy["generation_width"]
        generation_height = strategy["generation_height"]
        needs_pregen_resize = strategy["needs_pregen_resize"]
        resize_type = strategy["resize_type"]
        upscale_ratio = strategy["upscale_ratio"]
        use_supersampling = strategy["use_supersampling"]

        image_to_upload = job.input_image
        upload_filename = img_path.name

        # Étape 1: Ajustement multiples de 32 (si nécessaire)
        needs_resize_to_adjusted = (
            adjusted_source_width != source_width
            or adjusted_source_height != source_height
        )

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

        # Étape 2: Redimensionnement vers ~720p pour génération optimale (Lanczos)
        if needs_pregen_resize and (
            generation_width != adjusted_source_width
            or generation_height != adjusted_source_height
        ):
            if resize_type == "upscale":
                logger.info(
                    f"🔼 Upscale Lanczos pré-génération: "
                    f"{adjusted_source_width}x{adjusted_source_height} → {generation_width}x{generation_height}"
                )
            elif resize_type == "downscale":
                logger.info(
                    f"🔽 Downscale Lanczos pré-génération: "
                    f"{adjusted_source_width}x{adjusted_source_height} → {generation_width}x{generation_height}"
                )

            with Image.open(image_to_upload) as img:
                resized_img = img.resize(
                    (generation_width, generation_height),
                    Image.Resampling.LANCZOS,
                )

                pregen_path = (
                    img_path.parent / f"{img_path.stem}_pregen{img_path.suffix}"
                )

                resized_img.save(pregen_path, quality=95)
                logger.success(
                    f"   ✅ Image préparée pour génération: {pregen_path.name}"
                )

            image_to_upload = pregen_path
            upload_filename = pregen_path.name

        # Logger la stratégie choisie
        logger.info("📐 Stratégie de génération complète:")
        logger.info(f"   Image source originale: {source_width}x{source_height}")
        logger.info(
            f"   Image ajustée (×32): {adjusted_source_width}x{adjusted_source_height}"
        )
        logger.info(f"   Génération WAN 2.2: {generation_width}x{generation_height}")
        logger.info(
            f"   Résolution génération cible: {adjusted_target_width}x{adjusted_target_height}"
        )
        if (
            user_target_width != adjusted_target_width
            or user_target_height != adjusted_target_height
        ):
            logger.info(
                f"   Résolution finale (post-ffmpeg): {user_target_width}x{user_target_height}"
            )

        # Messages sur l'upscale post-génération
        if upscale_ratio > 1.5:
            logger.info(
                f"   Upscale post-génération: {generation_width}x{generation_height} → "
                f"{adjusted_target_width}x{adjusted_target_height} ({upscale_ratio:.2f}x)"
            )

            if use_supersampling:
                logger.success(
                    f"   ✅ Upscale optimal ({upscale_ratio:.2f}x ≤ 4x) - 4x-UltraSharp + supersampling Lanczos"
                )
            else:
                logger.warning(
                    f"   ⚠️  Upscale élevé ({upscale_ratio:.2f}x > 4x) - 4x UltraSharp + {upscale_ratio / 4:.2f}x Lanczos supplémentaire"
                )
                logger.warning(
                    "   Des artefacts peuvent apparaître au-delà de 4x. Qualité optimale garantie jusqu'à 4x."
                )

        # VAE tiling — piloté par le registre
        target_pixels = adjusted_target_width * adjusted_target_height
        if model_cfg and model_cfg.resolution:
            _res = model_cfg.resolution
            enable_vae_tiling = (
                target_pixels > _res.vae_tiling_pixel_threshold
                or upscale_ratio > _res.vae_tiling_upscale_threshold
            )
        else:
            enable_vae_tiling = target_pixels > 2073600 or upscale_ratio > 4.0

        # Sélection workflow — piloté par le registre
        if model_cfg and model_cfg.resolution:
            trigger = model_cfg.resolution.upscale_trigger_ratio
            base_wf = model_cfg.workflow_template
            upscale_wf = model_cfg.workflow_template_upscale or base_wf
        else:
            trigger = 1.5
            base_wf = f"wan22_{model_type}_i2v"
            upscale_wf = f"wan22_{model_type}_with_upscale"

        if upscale_ratio > trigger:
            selected_workflow = upscale_wf

            logger.info(
                f"🔍 Workflow {model_type.upper()} avec upscale sélectionné (ratio: {upscale_ratio:.2f}x)"
            )

            base_params = {
                k: v for k, v in job.parameters.items() if k not in ["width", "height"]
            }
            workflow_params = {
                "input_image": upload_filename,
                "prompt": job.prompt,
                "negative_prompt": job.parameters.get("negative_prompt", ""),
                **base_params,
                "width": generation_width,
                "height": generation_height,
                "target_width": adjusted_target_width,
                "target_height": adjusted_target_height,
                "enable_vae_tiling": enable_vae_tiling,
            }

            expected_output_width = adjusted_target_width
            expected_output_height = adjusted_target_height

            if enable_vae_tiling:
                logger.info(
                    f"🔧 VAE tiling activé (résolution finale: {adjusted_target_width}x{adjusted_target_height}, upscale: {upscale_ratio:.2f}x)"
                )
        else:
            selected_workflow = base_wf

            logger.info(
                f"✅ Workflow {model_type.upper()} standard (ratio: {upscale_ratio:.2f}x)"
            )

            # Pour génération standard, utiliser les dimensions optimales
            # IMPORTANT: Exclure width/height de job.parameters pour éviter conflit
            base_params = {
                k: v for k, v in job.parameters.items() if k not in ["width", "height"]
            }
            workflow_params = {
                "input_image": upload_filename,
                "prompt": job.prompt,
                "negative_prompt": job.parameters.get("negative_prompt", ""),
                **base_params,  # Tous les params sauf width/height
                "width": generation_width,
                "height": generation_height,
                "enable_vae_tiling": enable_vae_tiling,
            }

            # Sortie attendue du workflow standard : résolution de génération
            expected_output_width = generation_width
            expected_output_height = generation_height

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

            # Timeout adapté par modèle — registre d'abord, fallback hardcodé
            try:
                _reg = get_registry()
                workflow_timeout = _reg.get_timeout(detected_model) or (10800 if model_type == "14b" else 5400)
            except Exception:
                workflow_timeout = 10800 if model_type == "14b" else 5400
            logger.info(
                f"⏱️  Timeout workflow {model_type.upper()}: {workflow_timeout}s ({workflow_timeout // 60} min)"
            )

            workflow_result = await client.wait_for_completion(
                comfyui_workflow_id, timeout=workflow_timeout
            )
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

            # Post-processing : redimensionner vers les dimensions exactes demandées
            # Le VAE WAN 2.2 impose des multiples de 32, ffmpeg ajuste la sortie finale
            output_needs_resize = (
                user_target_width != expected_output_width
                or user_target_height != expected_output_height
            )

            if output_needs_resize:
                logger.info(
                    f"📐 Post-processing ffmpeg: {expected_output_width}x{expected_output_height} → "
                    f"{user_target_width}x{user_target_height}"
                )
                job_manager.update_job(
                    job_id, current_step="Ajustement dimensions finales", progress=0.85
                )

                temp_output = output_path + ".tmp.mp4"
                os.rename(output_path, temp_output)

                try:
                    subprocess.run(
                        [
                            "ffmpeg",
                            "-y",
                            "-i",
                            temp_output,
                            "-vf",
                            f"scale={user_target_width}:{user_target_height}:flags=lanczos",
                            "-c:v",
                            "libx264",
                            "-preset",
                            "ultrafast",
                            "-crf",
                            "1",
                            "-pix_fmt",
                            "yuv420p",
                            "-c:a",
                            "copy",
                            output_path,
                        ],
                        check=True,
                        capture_output=True,
                        text=True,
                    )
                    logger.success(
                        f"   ✅ Dimensions finales: {user_target_width}x{user_target_height}"
                    )
                except subprocess.CalledProcessError as e:
                    logger.error(f"   ❌ Erreur ffmpeg: {e.stderr}")
                    # Restaurer le fichier original en cas d'erreur
                    os.rename(temp_output, output_path)
                    logger.warning("   ⚠️ Sortie conservée aux dimensions de génération")
                finally:
                    # Nettoyer le fichier temporaire s'il existe encore
                    if os.path.exists(temp_output):
                        os.remove(temp_output)

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
            needs_resize_to_adjusted or needs_pregen_resize
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
    Calcule la résolution optimale et les infos d'upscale

    Body JSON:
        - source_width, source_height: Dimensions source
        - target_width, target_height: Dimensions demandées

    Returns:
        JSON avec résolution finale et infos upscale
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

        # Calculer résolution finale
        final_w, final_h = calculate_optimal_resolution(
            source_w, source_h, target_w, target_h
        )

        # Ajuster source aux multiples de 32 (arrondi ratio-aware)
        adjusted_source_w, adjusted_source_h = find_best_generation_dims(
            source_w, source_h
        )

        # Détecter le modèle disponible pour calcul stratégie
        from workflows.workflow_manager import WorkflowTemplate

        temp_template = WorkflowTemplate({"parameters": {}, "workflow": {}})
        detected_model, _model_type = temp_template._detect_available_model()

        # Calculer la stratégie de génération complète selon le modèle
        strategy = calculate_optimal_generation_strategy(
            adjusted_source_w,
            adjusted_source_h,
            final_w,
            final_h,
            model_name=detected_model,
        )

        upscale_ratio = strategy["upscale_ratio"]
        use_supersampling = strategy["use_supersampling"]

        # Déterminer le type et la description de l'upscale
        if upscale_ratio <= 1.5:
            upscale_type = "none"
            upscale_description = "Pas d'upscale nécessaire"
        elif use_supersampling:
            upscale_type = "optimal"
            upscale_description = f"Upscale optimal ({upscale_ratio:.2f}x ≤ 4x) - 4x-UltraSharp + supersampling Lanczos"
        else:
            upscale_type = "elevated"
            upscale_description = f"⚠️ Upscale élevé ({upscale_ratio:.2f}x > 4x) - 4x UltraSharp + {upscale_ratio / 4:.2f}x Lanczos. Artefacts possibles."

        # Protection contre division par zéro
        ratio = round(final_w / final_h, 2) if final_h > 0 else 0

        return jsonify(
            {
                "final_width": final_w,
                "final_height": final_h,
                "ratio": ratio,
                "adjusted": (final_w != target_w or final_h != target_h),
                "upscale_ratio": round(upscale_ratio, 2),
                "upscale_type": upscale_type,
                "upscale_description": upscale_description,
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
            "user_target_width": target_width,
            "user_target_height": target_height,
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
    from workflows.workflow_manager import WorkflowTemplate

    temp_template = WorkflowTemplate({"parameters": {}, "workflow": {}})
    detected_model_name, log_model_type = temp_template._detect_available_model()
    try:
        _reg = get_registry()
        _cfg = _reg.get_model(detected_model_name)
        if _cfg and _cfg.resolution:
            expected_workflow = (
                _cfg.workflow_template_upscale or _cfg.workflow_template
                if scale_ratio > _cfg.resolution.upscale_trigger_ratio
                else _cfg.workflow_template
            )
        else:
            expected_workflow = f"wan22_{log_model_type}_with_upscale" if scale_ratio > 1.5 else f"wan22_{log_model_type}_i2v"
    except Exception:
        expected_workflow = f"wan22_{log_model_type}_with_upscale" if scale_ratio > 1.5 else f"wan22_{log_model_type}_i2v"
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


@api_bp.route("/model-info", methods=["GET"])
def get_model_info():
    """
    Retourne les informations sur le modèle WAN 2.2 déployé

    Returns:
        JSON avec:
        - model_type: "5b" ou "14b"
        - model_name: Nom complet du modèle
        - display_name: Nom d'affichage pour l'UI
        - estimated_time: Temps estimé pour preset "Naturel" (30 steps)
    """
    import os
    from pathlib import Path

    try:
        # Détection directe du modèle disponible (sans dépendre d'un template)
        # Priorité : 14B > 5B (14B est le modèle plus puissant)
        comfyui_models_dir = Path("/workspace/comfyui/ComfyUI/models/diffusion_models")

        # Fallback si diffusion_models n'existe pas
        if not comfyui_models_dir.exists():
            comfyui_models_dir = Path("/workspace/comfyui/ComfyUI/models/checkpoints")

        # Recherche des modèles disponibles — registre d'abord, fallback hardcodé
        try:
            _reg = get_registry()
            model_priority = _reg.get_detection_priority()
        except Exception:
            model_priority = [
                ("wan2.2-i2v-a14b", "14b"),
                ("wan2.2-ti2v-5b", "5b"),
            ]

        detected_model = None
        model_type = None

        for model_name, m_type in model_priority:
            model_path = comfyui_models_dir / model_name
            if model_path.exists() and any(model_path.glob("*.safetensors")):
                detected_model = model_name
                model_type = m_type
                logger.info(
                    f"✅ API model-info: Modèle détecté: {model_name} (type: {m_type})"
                )
                break

        # Si aucun modèle trouvé dans les dossiers, utiliser variable d'environnement
        if not detected_model:
            env_model = os.getenv("OWNCLOUD_MODEL_NAME", "wan2.2-ti2v-5b")
            detected_model = env_model
            model_type = (
                "14b"
                if "14b" in env_model.lower() or "a14b" in env_model.lower()
                else "5b"
            )
            logger.warning(
                f"⚠️ API model-info: Utilisation env var: {env_model} (type: {model_type})"
            )

        # Informations enrichies depuis le registre
        try:
            _reg = get_registry()
            model_cfg = _reg.get_model(detected_model)
        except Exception:
            model_cfg = None

        if model_cfg:
            return jsonify(
                {
                    "model_type": model_type,
                    "model_name": detected_model,
                    "display_name": model_cfg.display_name,
                    "estimated_time": model_cfg.estimated_time,
                    "gpu_recommendation": model_cfg.vram_requirement,
                }
            )

        # Fallback legacy
        estimated_times = {"5b": "~8 min", "14b": "~15 min"}
        return jsonify(
            {
                "model_type": model_type,
                "model_name": detected_model,
                "display_name": f"WAN 2.2 {model_type.upper()}",
                "estimated_time": estimated_times.get(model_type, "~10 min"),
                "gpu_recommendation": "48GB+ VRAM"
                if model_type == "5b"
                else "80GB+ VRAM",
            }
        )

    except Exception as e:
        logger.warning(f"Impossible de détecter le modèle: {e}")
        # Fallback par défaut - utiliser variable d'environnement
        env_model = os.getenv("OWNCLOUD_MODEL_NAME", "wan2.2-ti2v-5b")
        model_type = (
            "14b" if "14b" in env_model.lower() or "a14b" in env_model.lower() else "5b"
        )
        return jsonify(
            {
                "model_type": model_type,
                "model_name": env_model,
                "display_name": f"WAN 2.2 {model_type.upper()}",
                "estimated_time": "~15 min" if model_type == "14b" else "~8 min",
                "gpu_recommendation": "80GB+ VRAM"
                if model_type == "14b"
                else "48GB+ VRAM",
            }
        )


@api_bp.route("/jobs/<job_id>/thumbnail", methods=["GET"])
def get_thumbnail(job_id):
    """Retourne une miniature du résultat (placeholder pour l'instant)"""
    # TODO: Extraire la première frame de la vidéo avec ffmpeg ou PIL
    logger.warning(f"Thumbnail placeholder retourné pour job {job_id} - extraction première frame non implémentée")
    import io

    # Placeholder image
    img = Image.new("RGB", (400, 300), color="#667eea")
    img_io = io.BytesIO()
    img.save(img_io, "JPEG")
    img_io.seek(0)

    return send_file(img_io, mimetype="image/jpeg")
