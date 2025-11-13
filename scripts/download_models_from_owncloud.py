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


# Vérification d'intégrité des fichiers du modèle
def verify_model_files(model_target: Path) -> bool:
    """Vérifie que tous les fichiers du modèle sont présents et corrects"""
    logger.info("🔍 Vérification des fichiers téléchargés...")

    # Tailles minimales acceptables pour chaque fichier
    required_files = {
        "diffusion_pytorch_model-00001-of-00003.safetensors": 8
        * 1024**3,  # 8 GB minimum
        "diffusion_pytorch_model-00002-of-00003.safetensors": 8
        * 1024**3,  # 8 GB minimum
        "diffusion_pytorch_model-00003-of-00003.safetensors": 100
        * 1024**2,  # 100 MB minimum
    }

    all_ok = True
    for filename, min_size in required_files.items():
        filepath = model_target / filename

        if not filepath.exists():
            logger.error(f"❌ Fichier manquant: {filename}")
            all_ok = False
            continue

        actual_size = filepath.stat().st_size

        if actual_size < min_size:
            logger.error(
                f"❌ {filename} incomplet ou corrompu:"
                f"\n   Taille: {actual_size / 1024**3:.2f} GB"
                f"\n   Minimum requis: {min_size / 1024**3:.2f} GB"
            )
            all_ok = False
        else:
            logger.info(f"✅ {filename}: {actual_size / 1024**3:.2f} GB")

    if all_ok:
        logger.success("✅ Tous les fichiers sont complets")
    else:
        logger.error("❌ Vérification échouée - fichiers incomplets")

    return all_ok


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

            # Vérifier la taille totale
            total_size = sum(
                f.stat().st_size for f in model_target.rglob("*") if f.is_file()
            )
            logger.info(f"📊 Taille totale: {total_size / 1024**3:.2f} GB")

            # 🔧 RECONSTITUTION DES CHUNKS SI PRÉSENTS
            chunks_dir = model_target / "chunks"
            if chunks_dir.exists() and (chunks_dir / "mapping.txt").exists():
                logger.info("")
                logger.info("🔧 Reconstitution des fichiers découpés...")

                # Appeler le script de reconstitution
                reassemble_script = Path(__file__).parent / "reassemble_models.sh"

                if reassemble_script.exists():
                    result = subprocess.run(
                        ["bash", str(reassemble_script), str(model_target)],
                        capture_output=True,
                        text=True
                    )

                    if result.returncode == 0:
                        logger.success("✅ Fichiers reconstitués avec succès")
                        # Afficher la sortie
                        for line in result.stdout.split('\n'):
                            if line.strip():
                                logger.info(f"   {line}")
                    else:
                        logger.error(f"❌ Échec de la reconstitution:")
                        logger.error(result.stderr)
                        return False, "Échec reconstitution des chunks"
                else:
                    logger.error(f"❌ Script reassemble_models.sh non trouvé: {reassemble_script}")
                    return False, "Script de reconstitution manquant"
            else:
                logger.info("   Pas de chunks à reconstituer")

            # 🔍 Vérification d'intégrité des fichiers (APRÈS reconstitution)
            logger.info("")
            if not verify_model_files(model_target):
                logger.error("⚠️  Les fichiers téléchargés sont incomplets!")
                logger.error("    Action requise: Supprimer les fichiers incomplets")
                logger.error("    et relancer le téléchargement")
                return False, "Fichiers incomplets après téléchargement"

            # 🔍 Vérification d'intégrité du T5 Encoder (CRITIQUE)
            logger.info("")
            logger.info("🔍 Vérification de l'intégrité du T5 Encoder...")

            verify_script = Path(__file__).parent / "verify_t5_integrity.py"
            if verify_script.exists():
                result = subprocess.run(
                    [
                        "python3",
                        str(verify_script),
                        model_name,
                        "--base-dir",
                        str(target_dir)
                    ],
                    capture_output=True,
                    text=True
                )

                # Afficher la sortie
                for line in result.stdout.split('\n'):
                    if line.strip():
                        print(f"   {line}")

                if result.returncode != 0:
                    logger.error("")
                    logger.error("❌ ÉCHEC DE LA VÉRIFICATION T5 ENCODER")
                    logger.error("   Le workflow est ARRÊTÉ pour éviter d'utiliser un modèle corrompu")
                    logger.error("")
                    if result.stderr:
                        for line in result.stderr.split('\n'):
                            if line.strip():
                                logger.error(f"   {line}")
                    return False, "T5 Encoder corrompu ou incomplet"

                logger.success("✅ T5 Encoder validé avec succès")
            else:
                logger.warning(f"⚠️  Script de vérification T5 non trouvé: {verify_script}")
                logger.warning("   Impossible de vérifier l'intégrité du T5 Encoder")

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
