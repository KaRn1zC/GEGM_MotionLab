#!/usr/bin/env python3
"""
Upload des modèles WAN 2.2 vers OwnCloud et nettoyage local
Permet de fixer les versions des modèles WAN 2.2 et de libérer de l'espace disque
"""

import os
import sys
import asyncio
import hashlib
from pathlib import Path
from typing import Optional, Tuple

# Ajouter le répertoire parent au path
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.logger import get_logger, setup_logger
from src.owncloud_uploader import OwnCloudUploader, OwnCloudConfig

from dotenv import load_dotenv

load_dotenv()  # Charge les variables depuis .env

# Configuration du logger
setup_logger(level="INFO")
logger = get_logger("upload_models")


def calculate_checksum(file_path: Path) -> str:
    """Calcule le SHA256 d'un fichier"""
    sha256_hash = hashlib.sha256()
    with open(file_path, "rb") as f:
        for byte_block in iter(lambda: f.read(4096), b""):
            sha256_hash.update(byte_block)
    return sha256_hash.hexdigest()


def get_model_files(model_dir: Path) -> list:
    """Récupère tous les fichiers du modèle"""
    files = []
    for root, dirs, filenames in os.walk(model_dir):
        for filename in filenames:
            file_path = Path(root) / filename
            files.append(file_path)
    return files


async def upload_model_to_owncloud(
    model_name: str = "wan2.2-i2v-a14b", clean_local: bool = False
) -> Tuple[bool, Optional[str]]:
    """
    Upload un modèle vers OwnCloud (version async)

    Args:
        model_name: Nom du modèle
        clean_local: Supprimer les fichiers locaux après upload

    Returns:
        (success, error_message)
    """
    logger.info(f"🚀 Début de l'upload du modèle {model_name}")

    # Vérifier que le modèle existe
    model_dir = Path("models") / model_name
    if not model_dir.exists():
        error = f"Modèle non trouvé: {model_dir}"
        logger.error(error)
        return False, error

    # Obtenir la liste des fichiers
    files = get_model_files(model_dir)
    total_files = len(files)
    total_size = sum(f.stat().st_size for f in files)

    logger.info(f"📦 Modèle: {model_name}")
    logger.info(f"   Fichiers: {total_files}")
    logger.info(f"   Taille totale: {total_size / (1024**3):.2f} GB")

    # Initialiser l'uploader OwnCloud
    try:
        # Créer la config depuis les variables d'env
        config = OwnCloudConfig(
            server_url=os.getenv("OWNCLOUD_SERVER_URL"),
            username=os.getenv("OWNCLOUD_USERNAME"),
            password=os.getenv("OWNCLOUD_PASSWORD"),
            upload_folder=os.getenv("OWNCLOUD_OUTPUT_FOLDER", "/GEGM_ComfyUI/Outputs"),
            chunk_size=int(os.getenv("OWNCLOUD_CHUNK_SIZE", "8192")),
            timeout=int(os.getenv("OWNCLOUD_TIMEOUT", "300")),
        )

        uploader = OwnCloudUploader(config)
        await uploader.connect()
        logger.info("✅ Connexion OwnCloud établie")
    except Exception as e:
        error = f"Erreur connexion OwnCloud: {e}"
        logger.error(error)
        return False, error

    # Upload de chaque fichier
    uploaded_files = []
    failed_files = []

    try:
        for idx, file_path in enumerate(files, 1):
            relative_path = file_path.relative_to("models")

            remote_path = str(relative_path)

            logger.info(f"📤 [{idx}/{total_files}] Upload: {relative_path}")
            logger.info(f"   Taille: {file_path.stat().st_size / (1024**2):.2f} MB")

            try:
                # Upload vers OwnCloud (dossier MODEL)
                result = await uploader.upload_to_folder(
                    file_data=file_path,
                    remote_path=remote_path,
                    folder_type="model",  # Utilise OWNCLOUD_MODEL_FOLDER
                    create_share=False,
                )

                if result.success:
                    uploaded_files.append(file_path)
                    logger.success("   ✅ Upload réussi")
                else:
                    failed_files.append(file_path)
                    logger.error(f"   ❌ Échec: {result.error_message}")

            except Exception as e:
                failed_files.append(file_path)
                logger.error(f"   ❌ Exception: {e}")

        # Résumé
        logger.info("=" * 60)
        logger.info("📊 Résumé de l'upload:")
        logger.info(f"   Réussis: {len(uploaded_files)}/{total_files}")
        logger.info(f"   Échecs: {len(failed_files)}/{total_files}")

        # Si tout est uploadé et clean_local demandé
        if len(failed_files) == 0:
            logger.success("✅ Tous les fichiers uploadés avec succès !")

            if clean_local:
                logger.info("🗑️  Nettoyage des fichiers locaux...")
                try:
                    import shutil

                    shutil.rmtree(model_dir)
                    logger.success(f"✅ Modèle local supprimé: {model_dir}")
                    logger.info(f"💾 Espace libéré: {total_size / (1024**3):.2f} GB")
                except Exception as e:
                    logger.error(f"❌ Erreur suppression: {e}")
                    return True, None

            return True, None
        else:
            error = f"{len(failed_files)} fichiers non uploadés"
            logger.error(f"❌ {error}")
            return False, error

    finally:
        await uploader.disconnect()


def main():
    """Fonction principale"""
    import argparse

    parser = argparse.ArgumentParser(
        description="Upload des modèles WAN 2.2 vers OwnCloud"
    )
    parser.add_argument(
        "--model",
        choices=["wan2.2-i2v-a14b", "wan2.2-ti2v-5b"],
        default="wan2.2-i2v-a14b",
        help="Modèle à uploader",
    )
    parser.add_argument(
        "--clean",
        action="store_true",
        help="Supprimer les fichiers locaux après upload",
    )
    parser.add_argument(
        "--confirm-clean",
        action="store_true",
        help="Confirmation pour suppression (requis avec --clean)",
    )

    args = parser.parse_args()

    # Vérifier la confirmation si clean demandé
    if args.clean and not args.confirm_clean:
        logger.error("❌ --clean requiert --confirm-clean pour confirmation")
        sys.exit(1)

    # Upload (async)
    success, error = asyncio.run(
        upload_model_to_owncloud(model_name=args.model, clean_local=args.clean)
    )

    if success:
        logger.success("🎉 Upload terminé avec succès !")
        sys.exit(0)
    else:
        logger.error(f"❌ Échec de l'upload: {error}")
        sys.exit(1)


if __name__ == "__main__":
    main()
