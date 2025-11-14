#!/usr/bin/env python3
"""
Fusionne les fichiers safetensors sharded en un seul fichier
Usage: python scripts/merge_safetensors.py wan2.2-ti2v-5b
"""

import sys
import argparse
from pathlib import Path
from safetensors.torch import save_file, safe_open

# Ajouter le répertoire parent au path
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.logger import get_logger

logger = get_logger("merge_safetensors")


def merge_safetensors(model_name: str, base_dir: str = "models") -> bool:
    """
    Fusionne les fichiers safetensors sharded en un seul fichier

    Args:
        model_name: Nom du modèle (wan2.2-ti2v-5b ou wan2.2-i2v-a14b)
        base_dir: Répertoire de base contenant les modèles (défaut: "models")

    Returns:
        True si la fusion a réussi, False sinon
    """
    model_dir = Path(base_dir) / model_name

    logger.info(f"🔧 Fusion des fichiers safetensors pour {model_name}...")
    logger.info(f"📂 Dossier: {model_dir}")

    # 1. Détecter les fichiers safetensors sharded
    sharded_files = sorted(
        model_dir.glob("diffusion_pytorch_model-*-of-*.safetensors")
    )

    if not sharded_files:
        logger.warning(f"⚠️  Aucun fichier sharded trouvé dans {model_dir}")
        logger.info(
            "   Vérification si le fichier fusionné existe déjà..."
        )
        merged_file = model_dir / "diffusion_pytorch_model.safetensors"
        if merged_file.exists():
            file_size_gb = merged_file.stat().st_size / (1024**3)
            logger.success(f"✅ Fichier fusionné existe déjà: {file_size_gb:.2f} GB")
            return True
        else:
            logger.error("❌ Aucun fichier safetensors trouvé (ni sharded ni fusionné)")
            return False

    logger.info(f"📦 {len(sharded_files)} fichiers sharded détectés:")
    total_size = 0
    for f in sharded_files:
        size_gb = f.stat().st_size / (1024**3)
        total_size += f.stat().st_size
        logger.info(f"   - {f.name}: {size_gb:.2f} GB")

    logger.info(f"📊 Taille totale: {total_size / (1024**3):.2f} GB")

    # 2. Fusionner tous les tenseurs
    logger.info("")
    logger.info("🔄 Fusion des tenseurs en cours...")

    merged_state_dict = {}
    total_keys = 0

    for i, shard_file in enumerate(sharded_files, 1):
        logger.info(f"   Lecture {i}/{len(sharded_files)}: {shard_file.name}...")

        try:
            with safe_open(shard_file, framework="pt", device="cpu") as f:
                keys = list(f.keys())
                logger.info(f"      {len(keys)} clés trouvées")

                for key in keys:
                    if key in merged_state_dict:
                        logger.warning(f"      ⚠️  Clé dupliquée ignorée: {key}")
                        continue

                    tensor = f.get_tensor(key)
                    merged_state_dict[key] = tensor
                    total_keys += 1

        except Exception as e:
            logger.error(f"❌ Erreur lecture {shard_file.name}: {e}")
            return False

    logger.success(f"✅ {total_keys} tenseurs fusionnés")

    # 3. Vérifier les clés critiques
    logger.info("")
    logger.info("🔍 Vérification des clés critiques...")

    # Clés critiques pour WAN 2.2
    critical_keys = [
        "blocks.0.ffn.0.weight",
        "blocks.14.ffn.0.weight",  # Celle qui causait l'erreur !
        "blocks.23.ffn.0.weight",
    ]

    missing_keys = []
    for key in critical_keys:
        if key not in merged_state_dict:
            missing_keys.append(key)
            logger.error(f"   ❌ Clé manquante: {key}")
        else:
            tensor = merged_state_dict[key]
            logger.info(
                f"   ✅ {key}: shape={tuple(tensor.shape)}, dtype={tensor.dtype}"
            )

    if missing_keys:
        logger.error(
            f"❌ {len(missing_keys)} clé(s) critique(s) manquante(s) après fusion"
        )
        return False

    logger.success("✅ Toutes les clés critiques présentes")

    # 4. Sauvegarder le fichier fusionné
    merged_file = model_dir / "diffusion_pytorch_model.safetensors"

    logger.info("")
    logger.info(f"💾 Sauvegarde du fichier fusionné: {merged_file.name}...")

    try:
        save_file(merged_state_dict, str(merged_file))
        file_size_gb = merged_file.stat().st_size / (1024**3)
        logger.success(f"✅ Fichier fusionné sauvegardé: {file_size_gb:.2f} GB")
    except Exception as e:
        logger.error(f"❌ Erreur sauvegarde: {e}")
        return False

    # 5. Résumé
    logger.info("")
    logger.success("=" * 70)
    logger.success("✅ FUSION SAFETENSORS RÉUSSIE")
    logger.success(f"   Fichier: {merged_file.name}")
    logger.success(f"   Taille: {file_size_gb:.2f} GB")
    logger.success(f"   Clés: {total_keys}")
    logger.success("   Fichiers sharded originaux peuvent être supprimés")
    logger.success("=" * 70)
    logger.info("")

    return True


def main():
    parser = argparse.ArgumentParser(
        description="Fusionne les fichiers safetensors sharded en un seul"
    )
    parser.add_argument(
        "model_name",
        help="Nom du modèle (wan2.2-ti2v-5b ou wan2.2-i2v-a14b)",
    )
    parser.add_argument(
        "--base-dir",
        default="models",
        help="Répertoire de base contenant les modèles (défaut: models)",
    )
    args = parser.parse_args()

    success = merge_safetensors(args.model_name, args.base_dir)

    if not success:
        logger.error("")
        logger.error("❌ ÉCHEC DE LA FUSION SAFETENSORS")
        logger.error("   Le workflow est ARRÊTÉ")
        logger.error("")
        sys.exit(1)

    sys.exit(0)


if __name__ == "__main__":
    main()
