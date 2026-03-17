"""
Application Flask principale pour Comfy_Img_to_Loop
Interface web pour la génération de cinemagraphs avec WAN 2.2
"""

import os
import sys
from pathlib import Path
from flask import Flask, render_template, jsonify, request
from flask_cors import CORS
from werkzeug.middleware.proxy_fix import ProxyFix

# Ajouter le projet au path

from src.logger import get_logger, setup_logger
from src.comfyui_client import ComfyUIConfig
from src.owncloud_config import get_owncloud_config, check_owncloud_setup
from web_interface.jobs import JobManager

# Configuration du logger
setup_logger(level=os.getenv("LOG_LEVEL", "INFO"))
logger = get_logger("flask_app")


def create_app(config_name="default"):
    """
    Factory pour créer l'application Flask

    Args:
        config_name: Nom de la configuration (default, development, production)

    Returns:
        Flask: Application Flask configurée
    """
    app = Flask(__name__, template_folder="templates", static_folder="static")

    # Configuration de base
    # Chemin absolu pour uploads (éviter les doublons de chemin)
    # Si lancé depuis /workspace, cwd = /workspace
    upload_folder = os.path.join(os.getcwd(), "web_interface", "uploads")

    app.config.update(
        SECRET_KEY=os.getenv("SECRET_KEY", "dev-secret-key-change-in-production"),
        MAX_CONTENT_LENGTH=100 * 1024 * 1024,  # 100MB max upload
        UPLOAD_FOLDER=upload_folder,
        ALLOWED_EXTENSIONS={"png", "jpg", "jpeg", "webp"},
        JSON_SORT_KEYS=False,
        JSONIFY_PRETTYPRINT_REGULAR=True,
    )

    # Configuration selon l'environnement
    if config_name == "production":
        app.config.update(DEBUG=False, TESTING=False)
    elif config_name == "development":
        app.config.update(DEBUG=True, TESTING=False)
    else:  # default
        app.config.update(
            DEBUG=os.getenv("FLASK_DEBUG", "False").lower() == "true", TESTING=False
        )

    # CORS
    CORS(
        app,
        resources={
            r"/api/*": {
                "origins": "*",
                "methods": ["GET", "POST", "PUT", "DELETE"],
                "allow_headers": ["Content-Type", "Authorization"],
            }
        },
    )

    # Proxy fix pour déploiement derrière reverse proxy
    app.wsgi_app = ProxyFix(app.wsgi_app, x_for=1, x_proto=1, x_host=1)

    # Créer le dossier d'upload si nécessaire
    os.makedirs(app.config["UPLOAD_FOLDER"], exist_ok=True)

    # Initialiser le gestionnaire de jobs
    app.job_manager = JobManager()

    # Configuration ComfyUI
    try:
        comfyui_host = os.getenv("COMFYUI_HOST", "127.0.0.1")
        comfyui_port = int(os.getenv("COMFYUI_PORT", "8188"))
        app.comfyui_config = ComfyUIConfig(host=comfyui_host, port=comfyui_port)
        logger.info(f"ComfyUI configuré: {comfyui_host}:{comfyui_port}")
    except Exception as e:
        logger.error(f"Erreur configuration ComfyUI: {e}")
        app.comfyui_config = None

    # Configuration OwnCloud
    try:
        owncloud_profile = os.getenv("OWNCLOUD_PROFILE", "default")
        if check_owncloud_setup():
            app.owncloud_config = get_owncloud_config(owncloud_profile)
            logger.info(f"OwnCloud configuré: {app.owncloud_config.server_url}")
        else:
            logger.warning("OwnCloud non configuré - upload désactivé")
            app.owncloud_config = None
    except Exception as e:
        logger.error(f"Erreur configuration OwnCloud: {e}")
        app.owncloud_config = None

    # Enregistrer les blueprints
    from web_interface.routes import api_bp, main_bp

    app.register_blueprint(api_bp, url_prefix="/api")
    app.register_blueprint(main_bp)

    # Gestionnaires d'erreurs
    @app.errorhandler(404)
    def not_found(error):
        if request.path.startswith("/api/"):
            return jsonify({"error": "Endpoint non trouvé"}), 404
        return render_template("404.html"), 404

    @app.errorhandler(500)
    def internal_error(error):
        logger.error(f"Erreur serveur: {error}")
        if request.path.startswith("/api/"):
            return jsonify({"error": "Erreur serveur interne"}), 500
        return render_template("500.html"), 500

    @app.errorhandler(413)
    def too_large(error):
        return jsonify({"error": "Fichier trop volumineux (max 100MB)"}), 413

    # Route de santé
    @app.route("/health")
    def health():
        """Endpoint de santé pour monitoring"""
        status = {
            "status": "healthy",
            "version": "1.0.0",
            "services": {
                "flask": "ok",
                "comfyui": "ok" if app.comfyui_config else "not_configured",
                "owncloud": "ok" if app.owncloud_config else "not_configured",
            },
            "jobs": {
                "active": len(app.job_manager.active_jobs),
                "completed": len(app.job_manager.completed_jobs),
                "failed": len(app.job_manager.failed_jobs),
            },
        }
        return jsonify(status)

    logger.info("✅ Application Flask créée avec succès")
    return app


# Instance globale pour développement
app = create_app()

if __name__ == "__main__":
    logger.info("🚀 Démarrage de Comfy_Img_to_Loop Web Interface")

    # Configuration depuis variables d'environnement
    host = os.getenv("FLASK_HOST", "0.0.0.0")
    port = int(os.getenv("FLASK_PORT", "5000"))
    debug = os.getenv("FLASK_DEBUG", "False").lower() == "true"

    logger.info(f"Serveur: http://{host}:{port}")
    logger.info(f"Mode debug: {debug}")

    app.run(host=host, port=port, debug=debug, threaded=True)
