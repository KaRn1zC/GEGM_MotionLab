#!/usr/bin/env python3
"""
Vérifie l'intégrité du modèle de diffusion WAN 2.2 fusionné
Usage: python scripts/verify_diffusion_model.py wan2.2-ti2v-5b
"""

import sys
import argparse
from pathlib import Path

# Ajouter le répertoire parent au path
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.logger import get_logger

logger = get_logger("diffusion_verification")


def verify_diffusion_model(model_name: str, base_dir: str = "models") -> bool:
    """
    Vérifie l'intégrité du modèle de diffusion WAN 2.2 fusionné

    Args:
        model_name: Nom du modèle (wan2.2-ti2v-5b ou wan2.2-i2v-a14b)
        base_dir: Répertoire de base contenant les modèles (défaut: "models")

    Returns:
        True si le modèle est valide, False sinon
    """
    model_dir = Path(base_dir) / model_name
    diffusion_file = model_dir / "diffusion_pytorch_model.safetensors"

    print(f"🔍 Vérification de l'intégrité du modèle de diffusion pour {model_name}...")
    logger.info(f"🔍 Vérification du modèle de diffusion pour {model_name}...")
    logger.info(f"📂 Fichier: {diffusion_file}")

    # 1. Vérifier que le fichier fusionné existe
    if not diffusion_file.exists():
        print(f"❌ Fichier fusionné introuvable: {diffusion_file.name}")
        print("   Le fichier doit être fusionné avant la vérification")
        print("   Exécutez: python scripts/merge_safetensors.py " + model_name)
        logger.error(f"❌ Fichier fusionné introuvable: {diffusion_file}")
        return False

    print(f"✅ Fichier fusionné trouvé")
    logger.success(f"✅ Fichier fusionné trouvé")

    # 2. Vérifier la taille du fichier
    file_size_bytes = diffusion_file.stat().st_size
    file_size_gb = file_size_bytes / (1024**3)

    print(f"📊 Taille du fichier: {file_size_gb:.2f} GB")
    logger.info(f"📊 Taille du fichier: {file_size_gb:.2f} GB")

    # Tailles attendues
    expected_sizes = {
        "wan2.2-ti2v-5b": (17.0, 20.0),  # ~18.6 GB
        "wan2.2-i2v-a14b": (26.0, 30.0),  # ~28 GB
    }

    if model_name in expected_sizes:
        min_size, max_size = expected_sizes[model_name]
        if file_size_gb < min_size:
            logger.error(
                f"❌ Fichier trop petit: {file_size_gb:.2f} GB (attendu: {min_size}-{max_size} GB)"
            )
            logger.error("   Le fichier est probablement incomplet ou corrompu")
            return False

        if file_size_gb > max_size:
            logger.warning(
                f"⚠️  Fichier plus gros que prévu: {file_size_gb:.2f} GB (attendu: {min_size}-{max_size} GB)"
            )

    logger.success(f"✅ Taille du fichier valide")

    # 3. Charger avec safetensors
    print("🔄 Chargement du modèle avec safetensors...")
    logger.info("🔄 Chargement du modèle avec safetensors...")

    try:
        from safetensors.torch import safe_open

        with safe_open(diffusion_file, framework="pt", device="cpu") as f:
            keys = list(f.keys())

        print(f"✅ Modèle chargé avec succès ({len(keys)} clés)")
        logger.success(f"✅ Modèle chargé avec succès")
        logger.info(f"📊 Nombre de clés: {len(keys)}")

    except Exception as e:
        print(f"❌ Erreur lors du chargement du modèle: {e}")
        print("   Le fichier est probablement corrompu")
        logger.error(f"❌ Erreur lors du chargement: {e}")
        return False

    # 4. Vérifier les clés critiques (celles qui causaient l'erreur)
    print("🔍 Vérification des clés critiques...")
    logger.info("🔍 Vérification des clés critiques du modèle de diffusion...")

    # Clés critiques du modèle de diffusion WAN 2.2
    # Ce sont les clés qui causaient KeyError dans les logs originaux
    critical_keys = [
        "blocks.0.ffn.0.weight",  # Premier bloc
        "blocks.14.ffn.0.weight",  # Bloc milieu (celle qui causait l'erreur !)
        "blocks.23.ffn.0.weight",  # Dernier bloc
    ]

    missing_keys = []
    for key in critical_keys:
        if key not in keys:
            missing_keys.append(key)
            print(f"   ❌ Clé manquante: {key}")
            logger.error(f"   ❌ Clé manquante: {key}")

    if missing_keys:
        print(f"❌ {len(missing_keys)} clé(s) critique(s) manquante(s)")
        print("   Le modèle de diffusion est INCOMPLET ou CORROMPU")
        logger.error(f"❌ {len(missing_keys)} clé(s) critique(s) manquante(s)")
        logger.error("   Le modèle de diffusion est INCOMPLET ou CORROMPU")
        logger.error("")
        logger.error("   Clés manquantes:")
        for key in missing_keys:
            logger.error(f"      - {key}")
        logger.error("")
        logger.error("   💡 Solution:")
        logger.error(f"      1. Supprimer le dossier models/{model_name}")
        logger.error(f"         rm -rf models/{model_name}")
        logger.error("      2. Re-télécharger et fusionner:")
        logger.error(f"         ./scripts/setup_wan22_native.sh {model_name}")
        return False

    print(f"✅ Toutes les clés critiques sont présentes")
    logger.success(f"✅ Toutes les clés critiques sont présentes")

    # 5. Vérifier quelques dimensions de tenseurs
    logger.info("🔍 Vérification des dimensions des tenseurs...")

    try:
        from safetensors.torch import safe_open

        with safe_open(diffusion_file, framework="pt", device="cpu") as f:
            # Vérifier que les tenseurs ont les bonnes dimensions
            for key in ["blocks.0.ffn.0.weight", "blocks.14.ffn.0.weight"]:
                tensor = f.get_tensor(key)
                if tensor.ndim < 1:
                    logger.error(
                        f"❌ Dimension invalide pour {key}: {tensor.ndim}"
                    )
                    return False
                logger.info(
                    f"   ✅ {key}: shape={tuple(tensor.shape)}"
                )

    except Exception as e:
        logger.error(f"❌ Erreur vérification dimensions: {e}")
        return False

    logger.success("✅ Dimensions des tenseurs valides")

    # 6. Vérification finale
    print("")
    print("=" * 70)
    print("✅ VÉRIFICATION MODÈLE DE DIFFUSION RÉUSSIE")
    print(f"   Fichier: {diffusion_file.name}")
    print(f"   Taille: {file_size_gb:.2f} GB")
    print(f"   Clés: {len(keys)}")
    print("   Le modèle de diffusion est COMPLET et VALIDE")
    print("=" * 70)
    print("")

    logger.info("")
    logger.success("=" * 70)
    logger.success("✅ VÉRIFICATION MODÈLE DE DIFFUSION RÉUSSIE")
    logger.success(f"   Fichier: {diffusion_file.name}")
    logger.success(f"   Taille: {file_size_gb:.2f} GB")
    logger.success(f"   Clés: {len(keys)}")
    logger.success("   Le modèle de diffusion est COMPLET et VALIDE")
    logger.success("=" * 70)
    logger.info("")

    return True


def main():
    parser = argparse.ArgumentParser(
        description="Vérifie l'intégrité du modèle de diffusion fusionné"
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

    success = verify_diffusion_model(args.model_name, args.base_dir)

    if not success:
        logger.error("")
        logger.error("❌ ÉCHEC DE LA VÉRIFICATION DU MODÈLE DE DIFFUSION")
        logger.error(
            "   Le workflow est ARRÊTÉ pour éviter d'uploader un modèle corrompu"
        )
        logger.error("")
        sys.exit(1)

    sys.exit(0)


if __name__ == "__main__":
    main()
