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
    job_manager = current_app.job_manager
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

        workflow = workflow_manager.create_workflow(
            "wan22_i2v",
            {
                "input_image": Path(job.input_image).name,
                "prompt": job.prompt,
                **job.parameters,
            },
        )

        # 2. Générer le cinemagraph
        job_manager.update_job(
            job_id, current_step="Génération du cinemagraph", progress=0.3
        )

        async with ComfyUISession(current_app.comfyui_config) as client:
            # Upload de l'image
            with open(job.input_image, "rb") as f:
                image_data = f.read()

            # Lancer le workflow
            workflow_id = await client.queue_prompt(
                workflow, images={Path(job.input_image).name: image_data}
            )

            job_manager.update_job(job_id, workflow_id=workflow_id)

            # Attendre la completion
            job_manager.update_job(
                job_id, current_step="Génération en cours...", progress=0.5
            )

            workflow_result = await client.wait_for_completion(workflow_id)
            logger.info(
                f"Workflow terminé: {workflow_result.status if hasattr(workflow_result, 'status') else 'completed'}"
            )

            # Récupérer les images de sortie
            job_manager.update_job(
                job_id, current_step="Récupération du résultat", progress=0.8
            )

            output_images = await client.get_output_images(workflow_id)

            if not output_images:
                raise Exception("Aucune vidéo générée")

            # Sauvegarder la vidéo
            output_path = get_file_path(f"output_{job_id}.mp4")
            with open(output_path, "wb") as f:
                f.write(output_images[0]["data"])

            job_manager.update_job(job_id, output_video=output_path)

            # 3. Upload sur OwnCloud si configuré
            if current_app.owncloud_config:
                job_manager.update_job(
                    job_id,
                    status=JobStatus.UPLOADING_RESULT,
                    current_step="Upload sur OwnCloud",
                    progress=0.9,
                )

                async with OwnCloudUploader(current_app.owncloud_config) as uploader:
                    upload_result = await upload_cinemagraph(
                        uploader=uploader,
                        video_file=Path(output_path),
                        workflow_id=workflow_id,
                        prompt=job.prompt,
                        generation_params=job.parameters,
                        create_share=True,
                    )

                    if upload_result.success and upload_result.share_link:
                        job_manager.update_job(
                            job_id, owncloud_link=upload_result.share_link
                        )

        # 4. Terminer
        job_manager.update_job(
            job_id, status=JobStatus.COMPLETED, progress=1.0, current_step="Terminé"
        )

        logger.success(f"Job {job_id} terminé avec succès")

    except Exception as e:
        logger.error(f"Erreur job {job_id}: {e}")
        job_manager.update_job(job_id, status=JobStatus.FAILED, error_message=str(e))


# === ROUTES PRINCIPALES ===


@main_bp.route("/")
def index():
    """Page d'accueil"""
    return render_template("index.html")


# === ROUTES API ===


@api_bp.route("/generate", methods=["POST"])
def generate_cinemagraph():
    """
    Crée un job de génération de cinemagraph

    Body:
        - image: Fichier image (multipart/form-data)
        - prompt: Prompt de génération
        - parameters: Paramètres JSON (steps, cfg_scale, etc.)

    Returns:
        JSON avec job_id
    """
    # Vérifier l'image
    if "image" not in request.files:
        return jsonify({"error": "Aucune image fournie"}), 400

    file = request.files["image"]

    if file.filename == "":
        return jsonify({"error": "Nom de fichier vide"}), 400

    if not allowed_file(file.filename):
        return jsonify({"error": "Type de fichier non autorisé"}), 400

    # Sauvegarder l'image
    filename = secure_filename(file.filename)
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    filename = f"{timestamp}_{filename}"
    filepath = get_file_path(filename)
    file.save(filepath)

    # Récupérer les paramètres
    prompt = request.form.get("prompt", "")

    try:
        import json

        parameters = json.loads(request.form.get("parameters", "{}"))
    except (json.JSONDecodeError, TypeError, ValueError) as e:
        logger.warning(f"Paramètres JSON invalides: {e}")
        parameters = {}

    # Paramètres par défaut
    parameters.setdefault("steps", 20)
    parameters.setdefault("cfg_scale", 7.5)
    parameters.setdefault("frames", 16)
    parameters.setdefault("fps", 8)
    parameters.setdefault("noise_level", "high")

    # Créer le job
    job = current_app.job_manager.create_job(
        input_image=filepath, prompt=prompt, parameters=parameters
    )

    # Lancer la génération en arrière-plan
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)

    def run_async():
        loop.run_until_complete(process_cinemagraph_generation(job.job_id))

    import threading

    thread = threading.Thread(target=run_async, daemon=True)
    thread.start()

    logger.info(f"Génération lancée pour job: {job.job_id}")

    return jsonify(
        {
            "job_id": job.job_id,
            "status": job.status.value,
            "message": "Génération lancée",
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
