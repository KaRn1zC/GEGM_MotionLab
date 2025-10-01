"""
Démonstration du module OwnCloud
"""

import sys
import asyncio
from pathlib import Path

sys.path.append(str(Path(__file__).parent.parent))

from src.logger import get_logger, setup_logger
from src.owncloud_config import get_owncloud_config, check_owncloud_setup
from src.owncloud_uploader import VideoMetadata

setup_logger(level="INFO")
logger = get_logger("demo")


async def demo_config():
    """Démo de la configuration"""
    logger.info("📋 Démonstration configuration")

    # Vérifier
    is_valid = check_owncloud_setup()

    if not is_valid:
        logger.warning("Configuration incomplète - démo limitée")
        return

    # Tester les profils
    for profile in ["default", "development", "production"]:
        try:
            config = get_owncloud_config(profile)
            logger.info(
                f"✅ Profil {profile}: {config.timeout}s timeout, {config.chunk_size}B chunks"
            )
        except Exception as e:
            logger.error(f"❌ Profil {profile}: {e}")


async def demo_metadata():
    """Démo des métadonnées"""
    logger.info("\n🎬 Démonstration métadonnées")

    metadata = VideoMetadata(
        filename="cinemagraph_example.mp4",
        original_name="photo.jpg",
        file_size=15_000_000,
        duration=3.0,
        width=1920,
        height=1080,
        fps=24.0,
        workflow_id="wan22-abc123",
        prompt="gentle water ripples",
        model_used="WAN 2.2 I2V 14B",
    )

    logger.info(f"Fichier: {metadata.filename}")
    logger.info(f"Taille: {metadata.file_size / 1_000_000:.1f} MB")
    logger.info(f"Durée: {metadata.duration}s @ {metadata.fps}fps")
    logger.info(f"Résolution: {metadata.width}x{metadata.height}")


async def main():
    logger.info("🎬 Démonstration OwnCloud - Comfy_Img_to_Loop")
    logger.info("=" * 60)

    await demo_config()
    await demo_metadata()

    logger.success("\n✅ Démonstration terminée")
    logger.info("💡 Configurez .env pour un test complet")


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.warning("Interrompu")
