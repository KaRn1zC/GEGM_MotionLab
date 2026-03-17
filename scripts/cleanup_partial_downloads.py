#!/usr/bin/env python3
"""
Nettoie les fichiers partiellement téléchargés en cas d'échec
Supprime les fichiers corrompus ou incomplets
"""

import sys
import json
import argparse
import shutil
from pathlib import Path

# Ajouter le répertoire parent au path

from src.logger import get_logger

logger = get_logger("cleanup")


def load_metadata() -> dict:
    """Charge le fichier models_metadata.json"""
    metadata_path = Path(__file__).parent.parent / "models_metadata.json"

    if not metadata_path.exists():
        logger.warning(f"⚠️  Fichier metadata non trouvé: {metadata_path}")
        return {}

    with open(metadata_path, "r") as f:
        return json.load(f)


def check_file_integrity(file_path: Path, expected_size: int) -> bool:
    """
    Vérifie l'intégrité d'un fichier basé sur la taille

    Args:
        file_path: Chemin du fichier
        expected_size: Taille attendue en bytes

    Returns:
        True si intègre, False sinon
    """
    if not file_path.exists():
        return False

    actual_size = file_path.stat().st_size

    # Tolérance de ±1%
    min_size = expected_size * 0.99
    max_size = expected_size * 1.01

    return min_size <= actual_size <= max_size


def cleanup_model_files(model_name: str, metadata: dict) -> int:
    """
    Nettoie les fichiers partiels d'un modèle

    Args:
        model_name: Nom du modèle
        metadata: Données models_metadata.json

    Returns:
        Nombre de fichiers supprimés
    """
    models_dir = Path("models")
    model_dir = models_dir / model_name
    deleted_count = 0

    logger.info(f"🧹 Nettoyage des fichiers partiels pour {model_name}...")

    if not model_dir.exists():
        logger.info("   Aucun dossier à nettoyer")
        return 0

    # Vérifier les fichiers du modèle
    if model_name in metadata.get("models", {}):
        model_data = metadata["models"][model_name]

        for filename, file_data in model_data["files"].items():
            file_path = model_dir / filename
            expected_size = file_data["size"]

            if file_path.exists():
                if not check_file_integrity(file_path, expected_size):
                    logger.warning(f"   ❌ Fichier incomplet détecté: {filename}")
                    file_path.unlink()
                    logger.info(f"   🗑️  Supprimé: {filename}")
                    deleted_count += 1
                else:
                    logger.success(f"   ✅ Fichier intègre conservé: {filename}")

    # Nettoyer les dossiers temporaires
    temp_dirs = [
        models_dir / ".temp_download",
        model_dir / "chunks",
    ]

    for temp_dir in temp_dirs:
        if temp_dir.exists():
            logger.info(f"   🗑️  Suppression dossier temporaire: {temp_dir.name}")
            shutil.rmtree(temp_dir)
            deleted_count += 1

    return deleted_count


def cleanup_shared_components(metadata: dict) -> int:
    """
    Nettoie les composants partagés partiels (CLIP, upscalers)

    Args:
        metadata: Données models_metadata.json

    Returns:
        Nombre de fichiers supprimés
    """
    deleted_count = 0

    logger.info("🧹 Vérification des composants partagés...")

    # Chemins possibles
    base_dirs = [
        Path("models"),
        Path("models/clip_vision"),
        Path("models/upscale_models"),
    ]

    for component_name, component_data in metadata.get("shared_components", {}).items():
        expected_size = component_data["size"]

        # Chercher le fichier dans les différents dossiers
        for base_dir in base_dirs:
            if not base_dir.exists():
                continue

            file_path = base_dir / component_name

            if file_path.exists():
                if not check_file_integrity(file_path, expected_size):
                    logger.warning(f"   ❌ Fichier incomplet détecté: {component_name}")
                    file_path.unlink()
                    logger.info(f"   🗑️  Supprimé: {component_name}")
                    deleted_count += 1
                else:
                    logger.success(f"   ✅ Fichier intègre conservé: {component_name}")

    return deleted_count


def main():
    parser = argparse.ArgumentParser(
        description="Nettoie les fichiers partiellement téléchargés"
    )
    parser.add_argument(
        "--model",
        help="Nom du modèle à nettoyer (wan2.2-ti2v-5b ou wan2.2-i2v-a14b)",
    )
    parser.add_argument(
        "--all",
        action="store_true",
        help="Nettoyer tous les modèles",
    )
    parser.add_argument(
        "--shared-only",
        action="store_true",
        help="Nettoyer uniquement les composants partagés",
    )
    args = parser.parse_args()

    # Charger les métadonnées
    metadata = load_metadata()

    if not metadata:
        logger.warning("⚠️  Nettoyage sans métadonnées (mode basique)")

    total_deleted = 0

    # Nettoyer les composants partagés
    if args.shared_only or not args.model:
        total_deleted += cleanup_shared_components(metadata)

    # Nettoyer les modèles
    if not args.shared_only:
        if args.all:
            for model_name in ["wan2.2-ti2v-5b", "wan2.2-i2v-a14b"]:
                total_deleted += cleanup_model_files(model_name, metadata)
        elif args.model:
            total_deleted += cleanup_model_files(args.model, metadata)
        else:
            logger.error("❌ Spécifiez --model, --all ou --shared-only")
            sys.exit(1)

    # Résumé
    logger.info("")
    logger.info("=" * 70)
    if total_deleted > 0:
        logger.success("✅ NETTOYAGE TERMINÉ")
        logger.success(f"   Fichiers supprimés: {total_deleted}")
    else:
        logger.success("✅ AUCUN FICHIER PARTIEL DÉTECTÉ")
        logger.success("   Tous les fichiers sont intègres")
    logger.info("=" * 70)
    logger.info("")


if __name__ == "__main__":
    main()
