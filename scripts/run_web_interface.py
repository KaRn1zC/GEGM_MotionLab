"""
Script de démarrage de l'interface web Flask
"""

import sys
from pathlib import Path

sys.path.append(str(Path(__file__).parent.parent))

from web_interface.app import app
from src.logger import setup_logger, get_logger

# Configuration du logger
setup_logger(level="INFO")
logger = get_logger("web_start")

if __name__ == "__main__":
    logger.info("🚀 Démarrage de Comfy_Img_to_Loop Web Interface")
    logger.info("=" * 60)

    # Afficher les configurations
    logger.info(f"📡 Flask: http://{app.config.get('HOST', '0.0.0.0')}:5000")
    logger.info(
        f"🎨 ComfyUI: {app.comfyui_config.base_url if app.comfyui_config else 'Non configuré'}"
    )
    logger.info(
        f"☁️  OwnCloud: {app.owncloud_config.server_url if app.owncloud_config else 'Non configuré'}"
    )
    logger.info("=" * 60)

    app.run(host="0.0.0.0", port=5000, debug=True, threaded=True)
