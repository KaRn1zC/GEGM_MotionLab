#!/usr/bin/env python3
"""
Vérifie la disponibilité et la version des fichiers upstream
Détecte les nouvelles versions en comparant les tailles de fichiers
"""

import sys
import json
import argparse
import requests
from pathlib import Path
from typing import Dict, Tuple

# Ajouter le répertoire parent au path
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.logger import get_logger

logger = get_logger("upstream_health")

# Tolérance de taille (±1% pour variations mineures)
SIZE_TOLERANCE = 0.01


def load_metadata() -> Dict:
    """Charge le fichier models_metadata.json"""
    metadata_path = Path(__file__).parent.parent / "models_metadata.json"

    if not metadata_path.exists():
        logger.error(f"❌ Fichier metadata non trouvé: {metadata_path}")
        sys.exit(1)

    with open(metadata_path, "r") as f:
        return json.load(f)


def check_file_size(url: str, expected_size: int, filename: str) -> Tuple[bool, int]:
    """
    Vérifie la taille d'un fichier via HEAD request

    Args:
        url: URL du fichier
        expected_size: Taille attendue en bytes
        filename: Nom du fichier (pour logs)

    Returns:
        (is_valid, actual_size): True si taille OK, False sinon + taille réelle
    """
    try:
        # HEAD request pour obtenir la taille sans télécharger
        response = requests.head(url, allow_redirects=True, timeout=10)

        if response.status_code != 200:
            logger.error(f"   ❌ {filename}: HTTP {response.status_code}")
            return False, 0

        # Récupérer la taille
        actual_size = int(response.headers.get("Content-Length", 0))

        if actual_size == 0:
            logger.warning(f"   ⚠️  {filename}: Taille non disponible dans headers")
            return False, 0

        # Calculer la tolérance
        min_size = expected_size * (1 - SIZE_TOLERANCE)
        max_size = expected_size * (1 + SIZE_TOLERANCE)

        if min_size <= actual_size <= max_size:
            size_mb = actual_size / (1024**2)
            expected_mb = expected_size / (1024**2)
            logger.success(
                f"   ✅ {filename}: {size_mb:.0f} MB (attendu: {expected_mb:.0f} MB)"
            )
            return True, actual_size
        else:
            size_mb = actual_size / (1024**2)
            expected_mb = expected_size / (1024**2)
            diff_percent = ((actual_size - expected_size) / expected_size) * 100
            logger.warning(
                f"   ⚠️  {filename}: {size_mb:.0f} MB (attendu: {expected_mb:.0f} MB, différence: {diff_percent:+.1f}%)"
            )
            logger.warning("   → Nouvelle version détectée ou fichier modifié")
            return False, actual_size

    except requests.exceptions.RequestException as e:
        logger.error(f"   ❌ {filename}: Erreur réseau - {e}")
        return False, 0
    except Exception as e:
        logger.error(f"   ❌ {filename}: Erreur - {e}")
        return False, 0


def check_huggingface_repo_file(
    repo: str, path: str, expected_size: int, filename: str
) -> Tuple[bool, int]:
    """Vérifie un fichier sur HuggingFace"""
    url = f"https://huggingface.co/{repo}/resolve/main/{path}"
    return check_file_size(url, expected_size, filename)


def check_model_health(model_name: str, metadata: Dict) -> bool:
    """
    Vérifie la santé d'un modèle upstream

    Args:
        model_name: Nom du modèle (wan2.2-ti2v-5b ou wan2.2-i2v-a14b)
        metadata: Données models_metadata.json

    Returns:
        True si tous les fichiers CRITIQUES OK, False sinon
        (Les composants optionnels n'affectent pas le résultat)
    """
    logger.info(f"🔍 Vérification upstream pour {model_name}...")

    if model_name not in metadata["models"]:
        logger.error(f"❌ Modèle inconnu: {model_name}")
        return False

    model_data = metadata["models"][model_name]
    all_critical_valid = True
    optional_failed = []

    # Vérifier les fichiers du modèle (TOUS critiques)
    logger.info("📦 Vérification des fichiers du modèle...")
    for filename, file_data in model_data["files"].items():
        repo = file_data["repo"]
        path = file_data["path"]
        expected_size = file_data["size"]

        is_valid, _ = check_huggingface_repo_file(repo, path, expected_size, filename)
        if not is_valid:
            all_critical_valid = False

    # Vérifier les composants partagés (CLIP, upscalers)
    logger.info("🔧 Vérification des composants partagés...")
    for filename, file_data in metadata["shared_components"].items():
        # Vérifier si ce composant est requis pour ce modèle
        if model_name in file_data["required_for"]:
            url = file_data["url"]
            expected_size = file_data["size"]
            is_optional = file_data.get("optional", False)

            is_valid, _ = check_file_size(url, expected_size, filename)
            if not is_valid:
                if is_optional:
                    # Composant optionnel : logger mais ne pas bloquer
                    optional_failed.append(filename)
                    logger.warning(
                        f"   ⚠️  {filename} indisponible (optionnel, sera téléchargé plus tard)"
                    )
                else:
                    # Composant critique : bloquer
                    all_critical_valid = False

    # Logger les composants optionnels échoués
    if optional_failed:
        logger.info(
            f"ℹ️  Composants optionnels indisponibles: {', '.join(optional_failed)}"
        )
        logger.info("   → Seront téléchargés pendant le setup si disponibles")

    return all_critical_valid


def main():
    parser = argparse.ArgumentParser(
        description="Vérifie la disponibilité et la version des fichiers upstream"
    )
    parser.add_argument(
        "model_name",
        help="Nom du modèle (wan2.2-ti2v-5b ou wan2.2-i2v-a14b)",
    )
    parser.add_argument(
        "--verbose",
        "-v",
        action="store_true",
        help="Affichage détaillé",
    )
    args = parser.parse_args()

    # Charger les métadonnées
    metadata = load_metadata()
    logger.info(f"📋 Métadonnées chargées (version {metadata['version']})")

    # Vérifier le modèle
    is_healthy = check_model_health(args.model_name, metadata)

    if is_healthy:
        logger.success("")
        logger.success("=" * 70)
        logger.success("✅ UPSTREAM DISPONIBLE ET À JOUR")
        logger.success(f"   Modèle: {args.model_name}")
        logger.success("   Tous les fichiers correspondent aux versions attendues")
        logger.success("   Téléchargement upstream recommandé")
        logger.success("=" * 70)
        logger.success("")
        sys.exit(0)
    else:
        logger.warning("")
        logger.warning("=" * 70)
        logger.warning("⚠️  UPSTREAM NON DISPONIBLE OU VERSION DIFFÉRENTE")
        logger.warning(f"   Modèle: {args.model_name}")
        logger.warning("   Raisons possibles:")
        logger.warning("   - Nouvelle version upstream disponible")
        logger.warning("   - Fichiers temporairement indisponibles")
        logger.warning("   - Erreur réseau")
        logger.warning("")
        logger.warning("   → FALLBACK SUR OWNCLOUD RECOMMANDÉ")
        logger.warning("   → Version stable et testée disponible sur OwnCloud")
        logger.warning("=" * 70)
        logger.warning("")
        sys.exit(1)


if __name__ == "__main__":
    main()
