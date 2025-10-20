#!/usr/bin/env python3
"""
Téléchargement des modèles depuis OwnCloud
Utilisé au démarrage des conteneurs RunPod
Utilise webdavclient3 pour la simplicité
"""

import os
import sys
import time
from pathlib import Path
from typing import Optional, Tuple

# Ajouter le répertoire parent au path
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.logger import get_logger, setup_logger
from webdav3.client import Client

# Configuration du logger
setup_logger(level="INFO")
logger = get_logger("download_models")


def download_model_from_owncloud(
    model_name: str = "wan2.2-i2v-a14b",
    target_dir: Path = Path("/workspace/comfyui/ComfyUI/models/diffusion_models"),
) -> Tuple[bool, Optional[str]]:
    """
    Télécharge un modèle depuis OwnCloud

    Args:
        model_name: Nom du modèle
        target_dir: Répertoire de destination

    Returns:
        (success, error_message)
    """
    logger.info(f"📥 Début du téléchargement: {model_name}")

    # Créer le dossier de destination
    model_target = target_dir / model_name
    model_target.mkdir(parents=True, exist_ok=True)

    try:
        # Configuration WebDAV
        options = {
            "webdav_hostname": os.getenv("OWNCLOUD_SERVER_URL"),
            "webdav_login": os.getenv("OWNCLOUD_USERNAME"),
            "webdav_password": os.getenv("OWNCLOUD_PASSWORD"),
            "webdav_timeout": int(os.getenv("OWNCLOUD_TIMEOUT", "300")),
        }

        client = Client(options)

        # Obtenir le chemin distant
        model_folder = os.getenv("OWNCLOUD_MODEL_FOLDER", "/GEGM_ComfyUI/Models")
        remote_path = f"{model_folder}/{model_name}/"

        logger.info(f"📂 Chemin distant: {remote_path}")
        logger.info(f"📂 Chemin local: {model_target}")

        # Lister les fichiers distants
        logger.info("🔍 Listage des fichiers distants...")
        files_list = client.list(remote_path, get_info=True)

        # Filtrer seulement les fichiers
        files = [f for f in files_list if not f["isdir"]]
        total_files = len(files)

        logger.info(f"📦 {total_files} fichiers à télécharger")

        # Télécharger chaque fichier
        downloaded = 0
        failed = []

        start_time = time.time()

        for idx, file_info in enumerate(files, 1):
            remote_file = f"{remote_path}{file_info['name']}"
            local_file = model_target / file_info["name"]

            # Créer les sous-dossiers si nécessaire
            local_file.parent.mkdir(parents=True, exist_ok=True)

            # Skip si déjà téléchargé et même taille
            if local_file.exists() and local_file.stat().st_size == file_info["size"]:
                logger.debug(
                    f"⏭️  [{idx}/{total_files}] Déjà téléchargé: {file_info['name']}"
                )
                downloaded += 1
                continue

            logger.info(f"📥 [{idx}/{total_files}] {file_info['name']}")

            try:
                client.download_file(remote_file, str(local_file))
                downloaded += 1
                logger.success("   ✅ Téléchargé")
            except Exception as e:
                failed.append(file_info["name"])
                logger.error(f"   ❌ Échec: {e}")

        elapsed = time.time() - start_time

        # Résumé
        logger.info("=" * 60)
        logger.info("📊 Résumé:")
        logger.info(f"   Réussis: {downloaded}/{total_files}")
        logger.info(f"   Échecs: {len(failed)}")
        logger.info(f"   Durée: {elapsed:.1f}s")

        if len(failed) == 0:
            logger.success(f"✅ Modèle {model_name} téléchargé !")
            return True, None
        else:
            return False, f"{len(failed)} fichiers échoués"

    except Exception as e:
        logger.error(f"❌ Erreur: {e}")
        return False, str(e)


def main():
    import argparse

    parser = argparse.ArgumentParser()
    parser.add_argument("--model", default="wan2.2-i2v-a14b")
    parser.add_argument(
        "--target-dir", default="/workspace/comfyui/ComfyUI/models/diffusion_models"
    )

    args = parser.parse_args()

    success, error = download_model_from_owncloud(
        model_name=args.model, target_dir=Path(args.target_dir)
    )

    sys.exit(0 if success else 1)


if __name__ == "__main__":
    main()
