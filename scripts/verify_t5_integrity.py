#!/usr/bin/env python3
"""
Vérifie l'intégrité du T5 Encoder (ComfyUI Native - FP16)
Usage: python scripts/verify_t5_integrity.py wan2.2-ti2v-5b
"""

import sys
import argparse
from pathlib import Path

from src.logger import get_logger
from src.model_registry import get_registry

logger = get_logger("t5_verification")


def verify_t5_encoder(model_name: str, base_dir: str = "models") -> bool:
    """
    Vérifie l'intégrité du T5 Encoder (ComfyUI Native - FP16)

    Args:
        model_name: Nom du modèle (wan2.2-ti2v-5b ou wan2.2-i2v-a14b)
        base_dir: Répertoire de base contenant les modèles (défaut: "models")

    Returns:
        True si le T5 est valide, False sinon
    """
    model_dir = Path(base_dir) / model_name

    # Filename T5 depuis le registre (fallback hardcodé)
    try:
        registry = get_registry()
        shared = registry.get_shared_components()
        t5_filename = shared.text_encoder.filename
    except Exception:
        t5_filename = "umt5_xxl_fp16.safetensors"

    t5_file = model_dir / t5_filename

    print(f"🔍 Vérification de l'intégrité du T5 Encoder pour {model_name}...")
    logger.info(
        "🔍 Vérification de l'intégrité du T5 Encoder (ComfyUI Native - FP16)..."
    )
    logger.info(f"📂 Fichier: {t5_file}")

    # 1. Vérifier que le fichier existe
    if not t5_file.exists():
        print(f"❌ Fichier T5 introuvable: {t5_file.name}")
        print("   Le modèle doit être téléchargé depuis HuggingFace")
        print("   Exécutez: ./scripts/setup_wan22_native.sh " + model_name)
        logger.error(f"❌ Fichier T5 introuvable: {t5_file}")
        return False

    print(f"✅ Fichier T5 trouvé: {t5_file.name}")
    logger.success("✅ Fichier T5 trouvé")

    # 2. Vérifier la taille du fichier (FP16: ~11.4 GB)
    file_size_bytes = t5_file.stat().st_size
    file_size_gb = file_size_bytes / (1024**3)

    print(f"📊 Taille du fichier: {file_size_gb:.2f} GB")
    logger.info(f"📊 Taille du fichier: {file_size_gb:.2f} GB")

    # Le T5 UMT5-XXL FP16 devrait faire entre 10GB et 12GB (~11.4 GB)
    if file_size_gb < 10.0:
        logger.error(
            f"❌ Fichier T5 trop petit: {file_size_gb:.2f} GB (attendu: ~10-12 GB pour FP16)"
        )
        logger.error(
            "   Le téléchargement est probablement incomplet ou le fichier est corrompu"
        )
        return False

    if file_size_gb > 13.0:
        logger.warning(
            f"⚠️  Fichier T5 plus gros que prévu: {file_size_gb:.2f} GB (attendu: ~10-12 GB pour FP16)"
        )

    logger.success("✅ Taille du fichier valide (FP16)")

    # 3. Essayer de charger le fichier avec safetensors
    print("🔄 Chargement du fichier T5 avec safetensors...")
    logger.info("🔄 Chargement du fichier T5 avec safetensors...")

    try:
        from safetensors.torch import safe_open

        with safe_open(t5_file, framework="pt", device="cpu") as f:
            keys = list(f.keys())

        print(f"✅ Fichier T5 chargé avec succès ({len(keys)} clés)")
        logger.success("✅ Fichier T5 chargé avec succès")
        logger.info(f"📊 Nombre de clés: {len(keys)}")

    except Exception as e:
        print(f"❌ Erreur lors du chargement du fichier T5: {e}")
        print("   Le fichier est probablement corrompu")
        logger.error(f"❌ Erreur lors du chargement du fichier T5: {e}")
        logger.error("   Le fichier est probablement corrompu")
        return False

    # 4. Vérifier les clés critiques
    print("🔍 Vérification des clés critiques...")
    logger.info("🔍 Vérification des clés critiques du T5 Encoder...")

    # Clés critiques depuis le registre (fallback hardcodé)
    try:
        critical_keys = shared.text_encoder.critical_keys
    except Exception:
        critical_keys = [
            "shared.weight",
            "encoder.block.0.layer.0.SelfAttention.q.weight",
            "encoder.block.0.layer.1.DenseReluDense.wi_0.weight",
            "encoder.block.0.layer.1.DenseReluDense.wi_1.weight",
            "encoder.block.0.layer.1.DenseReluDense.wo.weight",
            "encoder.block.11.layer.1.DenseReluDense.wi_0.weight",
            "encoder.block.23.layer.0.SelfAttention.q.weight",
            "encoder.block.23.layer.1.DenseReluDense.wo.weight",
            "encoder.final_layer_norm.weight",
        ]

    logger.info("Format attendu: HuggingFace/Comfy-Org (sera converti par ComfyUI)")

    missing_keys = []
    for key in critical_keys:
        if key not in keys:
            missing_keys.append(key)
            print(f"   ❌ Clé manquante: {key}")
            logger.error(f"   ❌ Clé manquante: {key}")

    if missing_keys:
        print(f"❌ {len(missing_keys)} clé(s) critique(s) manquante(s)")
        print("   Le fichier T5 est INCOMPLET ou CORROMPU")
        logger.error(f"❌ {len(missing_keys)} clé(s) critique(s) manquante(s)")
        logger.error("   Le fichier T5 est INCOMPLET ou CORROMPU")
        logger.error("")
        logger.error("   Clés manquantes:")
        for key in missing_keys:
            logger.error(f"      - {key}")
        logger.error("")
        logger.error("   💡 Solution:")
        logger.error(f"      1. Supprimer le dossier models/{model_name}")
        logger.error(f"         rm -rf models/{model_name}")
        logger.error("      2. Re-télécharger depuis HuggingFace:")
        logger.error(f"         ./scripts/setup_wan22_native.sh {model_name}")
        return False

    print("✅ Toutes les clés critiques sont présentes")
    logger.success("✅ Toutes les clés critiques sont présentes")

    # 5. Vérifier quelques dimensions de tenseurs
    logger.info("🔍 Vérification des dimensions des tenseurs...")

    # Clés au format HuggingFace (qui seront dans le fichier)
    expected_dims = {
        "shared.weight": 2,  # (vocab_size, hidden_dim)
        "encoder.block.11.layer.1.DenseReluDense.wi_1.weight": 2,  # (ffn_dim, hidden_dim)
        "encoder.final_layer_norm.weight": 1,  # (hidden_dim,)
    }

    try:
        from safetensors.torch import safe_open

        with safe_open(t5_file, framework="pt", device="cpu") as f:
            for key, expected_ndim in expected_dims.items():
                if key in keys:
                    tensor = f.get_tensor(key)
                    if tensor.ndim != expected_ndim:
                        logger.error(
                            f"❌ Dimension incorrecte pour {key}: {tensor.ndim} (attendu: {expected_ndim})"
                        )
                        return False
                    logger.info(
                        f"   ✅ {key}: shape={tuple(tensor.shape)} ({'x'.join(map(str, tensor.shape))})"
                    )

    except Exception as e:
        logger.error(f"❌ Erreur vérification dimensions: {e}")
        return False

    logger.success("✅ Dimensions des tenseurs valides")

    # 6. Vérification finale
    print("")
    print("=" * 70)
    print("✅ VÉRIFICATION T5 ENCODER RÉUSSIE")
    print(f"   Fichier: {t5_file.name}")
    print("   Format: SafeTensors FP16 (ComfyUI Native)")
    print(f"   Taille: {file_size_gb:.2f} GB")
    print(f"   Clés: {len(keys)}")
    print("   Le T5 Encoder est COMPLET et VALIDE")
    print("=" * 70)
    print("")

    logger.info("")
    logger.success("=" * 70)
    logger.success("✅ VÉRIFICATION T5 ENCODER RÉUSSIE")
    logger.success(f"   Fichier: {t5_file.name}")
    logger.success("   Format: SafeTensors FP16 (ComfyUI Native)")
    logger.success(f"   Taille: {file_size_gb:.2f} GB")
    logger.success(f"   Clés: {len(keys)}")
    logger.success("   Le T5 Encoder est COMPLET et VALIDE")
    logger.success("=" * 70)
    logger.info("")

    return True


def main():
    parser = argparse.ArgumentParser(description="Vérifie l'intégrité du T5 Encoder")
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

    success = verify_t5_encoder(args.model_name, args.base_dir)

    if not success:
        logger.error("")
        logger.error("❌ ÉCHEC DE LA VÉRIFICATION T5 ENCODER")
        logger.error(
            "   Le workflow est ARRÊTÉ pour éviter d'uploader un fichier corrompu"
        )
        logger.error("")
        sys.exit(1)

    sys.exit(0)


if __name__ == "__main__":
    main()
