#!/usr/bin/env python3
"""
Vérifie l'intégrité du T5 Encoder après téléchargement
Usage: python scripts/verify_t5_integrity.py wan2.2-ti2v-5b
"""

import sys
import argparse
from pathlib import Path

# Ajouter le répertoire parent au path
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.logger import get_logger

logger = get_logger("t5_verification")


def verify_t5_encoder(model_name: str, base_dir: str = "models") -> bool:
    """
    Vérifie l'intégrité du T5 Encoder

    Args:
        model_name: Nom du modèle (wan2.2-ti2v-5b ou wan2.2-i2v-a14b)
        base_dir: Répertoire de base contenant les modèles (défaut: "models")

    Returns:
        True si le T5 est valide, False sinon
    """
    model_dir = Path(base_dir) / model_name
    t5_file = model_dir / "models_t5_umt5-xxl-enc-bf16.pth"

    print(f"🔍 Vérification de l'intégrité du T5 Encoder pour {model_name}...")
    logger.info(f"🔍 Vérification de l'intégrité du T5 Encoder pour {model_name}...")
    logger.info(f"📂 Fichier: {t5_file}")

    # 1. Vérifier que le fichier existe
    if not t5_file.exists():
        print(f"❌ Fichier T5 introuvable: {t5_file}")
        logger.error(f"❌ Fichier T5 introuvable: {t5_file}")
        return False

    print(f"✅ Fichier T5 trouvé")
    logger.success(f"✅ Fichier T5 trouvé")

    # 2. Vérifier la taille du fichier (devrait être ~9.5GB)
    file_size_bytes = t5_file.stat().st_size
    file_size_gb = file_size_bytes / (1024**3)

    print(f"📊 Taille du fichier: {file_size_gb:.2f} GB")
    logger.info(f"📊 Taille du fichier: {file_size_gb:.2f} GB")

    # Le T5 UMT5-XXL devrait faire entre 9GB et 11GB
    if file_size_gb < 9.0:
        logger.error(
            f"❌ Fichier T5 trop petit: {file_size_gb:.2f} GB (attendu: ~9.5-11 GB)"
        )
        logger.error(
            "   Le téléchargement est probablement incomplet ou le fichier est corrompu"
        )
        return False

    if file_size_gb > 12.0:
        logger.warning(
            f"⚠️  Fichier T5 plus gros que prévu: {file_size_gb:.2f} GB (attendu: ~9.5-11 GB)"
        )

    logger.success(f"✅ Taille du fichier valide")

    # 3. Essayer de charger le fichier avec PyTorch
    print("🔄 Chargement du fichier T5 avec PyTorch...")
    logger.info("🔄 Chargement du fichier T5 avec PyTorch...")

    try:
        import torch

        # Charger uniquement les clés (pas les poids complets pour économiser RAM)
        state_dict = torch.load(t5_file, map_location="cpu", weights_only=True)

        if not isinstance(state_dict, dict):
            print(f"❌ Format incorrect: attendu un dict, obtenu {type(state_dict)}")
            logger.error(
                f"❌ Format incorrect: attendu un dict, obtenu {type(state_dict)}"
            )
            return False

        print(f"✅ Fichier T5 chargé avec succès ({len(state_dict)} clés)")
        logger.success(f"✅ Fichier T5 chargé avec succès")
        logger.info(f"📊 Nombre de clés: {len(state_dict)}")

    except Exception as e:
        print(f"❌ Erreur lors du chargement du fichier T5: {e}")
        print("   Le fichier est probablement corrompu")
        logger.error(f"❌ Erreur lors du chargement du fichier T5: {e}")
        logger.error("   Le fichier est probablement corrompu")
        return False

    # 4. Vérifier les clés critiques
    print("🔍 Vérification des clés critiques...")
    logger.info("🔍 Vérification des clés critiques du modèle...")

    # Clés critiques qui doivent être présentes dans le T5 WAN 2.2
    # WAN 2.2 utilise un T5 modifié avec une structure de clés spécifique
    # Le modèle a 24 layers (blocks.0 à blocks.23)
    critical_keys = [
        "token_embedding.weight",  # Embeddings principaux
        "blocks.0.ffn.0.weight",  # Premier bloc FFN (format WAN 2.2)
        "blocks.14.ffn.0.weight",  # Bloc milieu (celui qui causait l'erreur)
        "blocks.23.ffn.0.weight",  # Dernier bloc FFN
        "final_norm.weight",  # Layer norm final
    ]

    missing_keys = []
    for key in critical_keys:
        if key not in state_dict:
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
        logger.error(
            "      1. Supprimer le dossier models/{model_name} complètement"
        )
        logger.error(
            f"         rm -rf models/{model_name}"
        )
        logger.error(
            "      2. Re-télécharger le modèle complet depuis Hugging Face"
        )
        logger.error(
            f"         ./scripts/setup_wan22_native.sh {model_name}"
        )
        return False

    print(f"✅ Toutes les clés critiques sont présentes")
    logger.success(f"✅ Toutes les clés critiques sont présentes")

    # 5. Vérifier quelques dimensions de tenseurs
    logger.info("🔍 Vérification des dimensions des tenseurs...")

    expected_dims = {
        "token_embedding.weight": 2,  # (vocab_size, hidden_dim)
        "blocks.14.ffn.0.weight": 2,  # (ffn_dim, hidden_dim) - format WAN 2.2
        "final_norm.weight": 1,  # (hidden_dim,)
    }

    for key, expected_ndim in expected_dims.items():
        if key in state_dict:
            tensor = state_dict[key]
            if tensor.ndim != expected_ndim:
                logger.error(
                    f"❌ Dimension incorrecte pour {key}: {tensor.ndim} (attendu: {expected_ndim})"
                )
                return False
            logger.info(
                f"   ✅ {key}: shape={tuple(tensor.shape)} ({'x'.join(map(str, tensor.shape))})"
            )

    logger.success("✅ Dimensions des tenseurs valides")

    # 6. Vérification finale
    print("")
    print("=" * 70)
    print("✅ VÉRIFICATION T5 ENCODER RÉUSSIE")
    print(f"   Fichier: {t5_file.name}")
    print(f"   Taille: {file_size_gb:.2f} GB")
    print(f"   Clés: {len(state_dict)}")
    print("   Le T5 Encoder est COMPLET et VALIDE")
    print("=" * 70)
    print("")

    logger.info("")
    logger.success("=" * 70)
    logger.success("✅ VÉRIFICATION T5 ENCODER RÉUSSIE")
    logger.success(f"   Fichier: {t5_file.name}")
    logger.success(f"   Taille: {file_size_gb:.2f} GB")
    logger.success(f"   Clés: {len(state_dict)}")
    logger.success("   Le T5 Encoder est COMPLET et VALIDE")
    logger.success("=" * 70)
    logger.info("")

    return True


def main():
    parser = argparse.ArgumentParser(
        description="Vérifie l'intégrité du T5 Encoder"
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
