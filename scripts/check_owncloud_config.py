"""
Vérification rapide de la configuration OwnCloud
"""

import sys
from pathlib import Path

sys.path.append(str(Path(__file__).parent.parent))

from src.logger import get_logger, setup_logger
from src.owncloud_config import check_owncloud_setup, get_owncloud_config

setup_logger(level="INFO")
logger = get_logger("check_config")


def main():
    logger.info("🔍 Vérification configuration OwnCloud")
    logger.info("=" * 60)

    # Vérifier
    is_valid = check_owncloud_setup()

    if not is_valid:
        logger.error("\n❌ Configuration incomplète")
        logger.info("\n💡 Actions requises:")
        logger.info("   1. Créez le fichier .env à la racine")
        logger.info("   2. Ajoutez vos identifiants OwnCloud:")
        logger.info("      OWNCLOUD_SERVER_URL=https://www.cloud-gegm.com")
        logger.info("      OWNCLOUD_USERNAME=arnaud.boy@gegmgroup.com")
        logger.info("      OWNCLOUD_PASSWORD=votre_mot_de_passe")
        logger.info("      OWNCLOUD_MODEL_FOLDER=/GEGM_ComfyUI/Models")
        return 1

    # Tester la création de config
    try:
        config = get_owncloud_config("default")
        logger.success("\n✅ Configuration OwnCloud valide")
        logger.info("\n📊 Configuration active:")
        logger.info(f"   Serveur: {config.server_url}")
        logger.info(f"   Utilisateur: {config.username}")
        logger.info(f"   Dossier: {config.upload_folder}")
        logger.info(f"   Timeout: {config.timeout}s")
        return 0
    except Exception as e:
        logger.error(f"\n❌ Erreur: {e}")
        return 1


if __name__ == "__main__":
    sys.exit(main())
