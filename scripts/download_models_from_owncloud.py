#!/usr/bin/env python3
"""
Téléchargement des modèles depuis OwnCloud avec rclone
Utilisé au démarrage des conteneurs RunPod
"""

import os
import sys
import subprocess
from pathlib import Path
from typing import Optional, Tuple

# Ajouter le répertoire parent au path
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.logger import get_logger, setup_logger

# Configuration du logger
setup_logger(level="INFO")
logger = get_logger(__name__)


def setup_rclone_config() -> bool:
    """Configure rclone pour OwnCloud"""
    server_url = os.getenv("OWNCLOUD_SERVER_URL", "").rstrip("/")
    username = os.getenv("OWNCLOUD_USERNAME", "")
    password = os.getenv("OWNCLOUD_PASSWORD", "")

    if not all([server_url, username, password]):
        logger.error("❌ Variables d'environnement OwnCloud manquantes")
        return False

    # Créer le fichier de configuration rclone
    rclone_config_dir = Path.home() / ".config" / "rclone"
    rclone_config_dir.mkdir(parents=True, exist_ok=True)

    rclone_config = rclone_config_dir / "rclone.conf"

    # Obscurcir le mot de passe avec rclone
    try:
        result = subprocess.run(
            ["rclone", "obscure", password], capture_output=True, text=True, check=True
        )
        obscured_password = result.stdout.strip()
    except Exception as e:
        logger.warning(f"⚠️ Mot de passe non obscurci: {e}")
        obscured_password = password

    # Configuration WebDAV pour OwnCloud
    config_content = f"""[owncloud]
type = webdav
url = {server_url}/remote.php/webdav/
vendor = owncloud
user = {username}
pass = {obscured_password}
"""

    # Écrire la configuration
    with open(rclone_config, "w") as f:
        f.write(config_content)

    logger.info("✅ Configuration rclone créée")
    return True


def download_model_from_owncloud(
    model_name: str = "wan2.2-i2v-a14b",
    target_dir: Path = Path("/workspace/comfyui/ComfyUI/models/diffusion_models"),
) -> Tuple[bool, Optional[str]]:
    """
    Télécharge un modèle depuis OwnCloud avec rclone

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
        # Configurer rclone
        if not setup_rclone_config():
            return False, "Configuration rclone échouée"

        # Chemin distant
        model_folder = os.getenv("OWNCLOUD_MODEL_FOLDER", "/GEGM_ComfyUI/Models")
        remote_path = f"owncloud:{model_folder}/{model_name}/"

        logger.info(f"📂 Source: {remote_path}")
        logger.info(f"📂 Destination: {model_target}")

        # Commande rclone copy
        cmd = [
            "rclone",
            "copy",
            remote_path,
            str(model_target),
            "--progress",
            "--transfers",
            "4",
            "--retries",
            "10",
            "--low-level-retries",
            "10",
            "--timeout",
            "1h",
            "--contimeout",
            "60s",
            "--stats",
            "30s",
            "-v",
        ]

        logger.info("🚀 Lancement du téléchargement...")

        # Exécuter rclone
        process = subprocess.Popen(
            cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, bufsize=1
        )

        # Afficher la sortie en temps réel
        for line in process.stdout:
            line = line.strip()
            if line:
                # Filtrer les lignes importantes
                if any(
                    keyword in line
                    for keyword in ["Transferred:", "Errors:", "Checks:", "ETA"]
                ):
                    print(f"   {line}")
                elif "ERROR" in line:
                    logger.error(f"   {line}")

        process.wait()

        if process.returncode == 0:
            logger.info(f"✅ Modèle {model_name} téléchargé !")

            # Vérifier la taille
            total_size = sum(
                f.stat().st_size for f in model_target.rglob("*") if f.is_file()
            )
            logger.info(f"📊 Taille totale: {total_size / 1024**3:.2f} GB")

            return True, None
        else:
            return False, f"rclone failed with code {process.returncode}"

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
