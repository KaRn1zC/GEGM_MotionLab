#!/usr/bin/env python3
"""
Nettoie les fichiers partiellement téléchargés en cas d'échec.

Utilise le registre central (config/model_registry.yaml) pour identifier
les fichiers attendus et vérifier leur intégrité par la taille.
"""

import sys
import shutil
import argparse
from pathlib import Path

from src.logger import get_logger
from src.model_registry import get_registry

logger = get_logger("cleanup")


def check_file_integrity(file_path: Path, expected_size: int) -> bool:
    """
    Vérifie l'intégrité d'un fichier via sa taille (tolérance ±1%).

    Args:
        file_path: Chemin du fichier à vérifier.
        expected_size: Taille attendue en bytes.

    Returns:
        True si le fichier existe et a la bonne taille.
    """
    if not file_path.exists():
        return False

    actual_size = file_path.stat().st_size
    min_size = expected_size * 0.99
    max_size = expected_size * 1.01

    return min_size <= actual_size <= max_size


def cleanup_model_files(model_name: str) -> int:
    """
    Nettoie les fichiers partiels d'un modèle.

    Args:
        model_name: Nom du modèle dans le registre.

    Returns:
        Nombre de fichiers/dossiers supprimés.
    """
    registry = get_registry()
    model = registry.get_model(model_name)
    models_dir = Path("models")
    model_dir = models_dir / model_name
    deleted_count = 0

    logger.info(f"🧹 Nettoyage des fichiers partiels pour {model_name}...")

    if not model_dir.exists():
        logger.info("   Aucun dossier à nettoyer")
        return 0

    # Vérifier les fichiers de diffusion via le registre
    if model:
        for df in model.diffusion_files:
            file_path = model_dir / df.filename
            if file_path.exists() and not check_file_integrity(file_path, df.size_bytes):
                logger.warning(f"   ❌ Fichier incomplet détecté: {df.filename}")
                file_path.unlink()
                logger.info(f"   🗑️  Supprimé: {df.filename}")
                deleted_count += 1
            elif file_path.exists():
                logger.success(f"   ✅ Fichier intègre conservé: {df.filename}")

        # Text encoder model-spécifique
        if model.text_encoder:
            te_path = model_dir / model.text_encoder.filename
            if te_path.exists() and not check_file_integrity(
                te_path, model.text_encoder.size_bytes
            ):
                logger.warning(f"   ❌ Text encoder incomplet: {model.text_encoder.filename}")
                te_path.unlink()
                logger.info(f"   🗑️  Supprimé: {model.text_encoder.filename}")
                deleted_count += 1
    else:
        logger.warning(f"   ⚠️  Modèle {model_name} inconnu du registre, nettoyage basique")

    # Nettoyer les dossiers temporaires
    for temp_dir in [models_dir / ".temp_download", model_dir / "chunks"]:
        if temp_dir.exists():
            logger.info(f"   🗑️  Suppression dossier temporaire: {temp_dir.name}")
            shutil.rmtree(temp_dir)
            deleted_count += 1

    return deleted_count


def cleanup_shared_components() -> int:
    """
    Nettoie les composants partagés partiels (upscalers).

    Returns:
        Nombre de fichiers supprimés.
    """
    registry = get_registry()
    shared = registry.get_shared_components()
    deleted_count = 0

    logger.info("🧹 Vérification des composants partagés...")

    # Text encoder partagé (T5)
    te = shared.text_encoder
    for base in [Path("models/text_encoders"), Path("models")]:
        te_path = base / te.filename
        if te_path.exists() and not check_file_integrity(te_path, te.size_bytes):
            logger.warning(f"   ❌ Text encoder incomplet: {te.filename}")
            te_path.unlink()
            logger.info(f"   🗑️  Supprimé: {te.filename}")
            deleted_count += 1

    # CLIP Vision
    cv = shared.clip_vision
    cv_path = Path(f"models/{cv.comfyui_subdir}") / cv.filename
    if cv_path.exists() and not check_file_integrity(cv_path, cv.size_bytes):
        logger.warning(f"   ❌ CLIP incomplet: {cv.filename}")
        cv_path.unlink()
        logger.info(f"   🗑️  Supprimé: {cv.filename}")
        deleted_count += 1

    return deleted_count


def main() -> None:
    """Point d'entrée CLI — nettoie les fichiers partiellement téléchargés."""
    parser = argparse.ArgumentParser(
        description="Nettoie les fichiers partiellement téléchargés"
    )
    parser.add_argument("--model", help="Nom du modèle à nettoyer")
    parser.add_argument("--all", action="store_true", help="Nettoyer tous les modèles")
    parser.add_argument(
        "--shared-only", action="store_true", help="Nettoyer uniquement les composants partagés"
    )
    args = parser.parse_args()

    total_deleted = 0

    # Composants partagés
    if args.shared_only or not args.model:
        total_deleted += cleanup_shared_components()

    # Modèles
    if not args.shared_only:
        if args.all:
            registry = get_registry()
            for name in registry.list_models():
                total_deleted += cleanup_model_files(name)
        elif args.model:
            total_deleted += cleanup_model_files(args.model)
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
