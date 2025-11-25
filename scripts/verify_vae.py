#!/usr/bin/env python3
"""
Vérifie l'intégrité du VAE WAN 2.2 (ComfyUI Native - WanVideoVAE38 48 canaux)
Usage: python scripts/verify_vae.py wan2.2-ti2v-5b
"""

import sys
import argparse
from pathlib import Path

# Ajouter le répertoire parent au path
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.logger import get_logger

logger = get_logger("vae_verification")


def verify_vae(model_name: str, base_dir: str = "models") -> bool:
    """
    Vérifie l'intégrité du VAE WAN 2.2 (ComfyUI Native - WanVideoVAE38 48 canaux)

    Args:
        model_name: Nom du modèle (wan2.2-ti2v-5b ou wan2.2-i2v-a14b)
        base_dir: Répertoire de base contenant les modèles (défaut: "models")

    Returns:
        True si le VAE est valide, False sinon
    """
    model_dir = Path(base_dir) / model_name

    # Déterminer le nom du fichier VAE selon le modèle
    if model_name == "wan2.2-ti2v-5b":
        vae_file = model_dir / "wan2.2_vae.safetensors"
        expected_size_min = 0.5  # ~600 MB
        expected_size_max = 1.5
    elif model_name == "wan2.2-i2v-a14b":
        vae_file = model_dir / "wan_2.1_vae.safetensors"
        expected_size_min = 0.5  # ~600 MB
        expected_size_max = 1.5
    else:
        logger.error(f"❌ Modèle inconnu: {model_name}")
        return False

    print(f"🔍 Vérification de l'intégrité du VAE pour {model_name}...")
    logger.info("🔍 Vérification de l'intégrité du VAE (WanVideoVAE38 - 48 canaux)...")
    logger.info(f"📂 Fichier: {vae_file}")

    # 1. Vérifier que le fichier existe
    if not vae_file.exists():
        print(f"❌ Fichier VAE introuvable: {vae_file.name}")
        print("   Le modèle doit être téléchargé depuis HuggingFace")
        print("   Exécutez: ./scripts/setup_wan22_native.sh " + model_name)
        logger.error(f"❌ Fichier VAE introuvable: {vae_file}")
        return False

    print(f"✅ Fichier VAE trouvé: {vae_file.name}")
    logger.success("✅ Fichier VAE trouvé")

    # 2. Vérifier la taille du fichier (~600 MB pour WanVideoVAE38)
    file_size_bytes = vae_file.stat().st_size
    file_size_gb = file_size_bytes / (1024**3)

    print(f"📊 Taille du fichier: {file_size_gb:.2f} GB")
    logger.info(f"📊 Taille du fichier: {file_size_gb:.2f} GB")

    if file_size_gb < expected_size_min:
        logger.error(
            f"❌ Fichier VAE trop petit: {file_size_gb:.2f} GB (attendu: ~{expected_size_min}-{expected_size_max} GB)"
        )
        logger.error(
            "   Le téléchargement est probablement incomplet ou le fichier est corrompu"
        )
        return False

    if file_size_gb > expected_size_max:
        logger.warning(
            f"⚠️  Fichier VAE plus gros que prévu: {file_size_gb:.2f} GB (attendu: ~{expected_size_min}-{expected_size_max} GB)"
        )

    logger.success("✅ Taille du fichier valide")

    # 3. Essayer de charger le fichier avec safetensors
    print("🔄 Chargement du fichier VAE avec safetensors...")
    logger.info("🔄 Chargement du fichier VAE avec safetensors...")

    try:
        from safetensors.torch import safe_open

        with safe_open(vae_file, framework="pt", device="cpu") as f:
            keys = list(f.keys())

        print(f"✅ Fichier VAE chargé avec succès ({len(keys)} clés)")
        logger.success("✅ Fichier VAE chargé avec succès")
        logger.info(f"📊 Nombre de clés: {len(keys)}")

    except Exception as e:
        print(f"❌ Erreur lors du chargement du fichier VAE: {e}")
        print("   Le fichier est probablement corrompu")
        logger.error(f"❌ Erreur lors du chargement du fichier VAE: {e}")
        logger.error("   Le fichier est probablement corrompu")
        return False

    # 4. Vérifier les clés critiques
    print("🔍 Vérification des clés critiques...")
    logger.info("🔍 Vérification des clés critiques du VAE...")

    # Clés critiques pour WanVideoVAE38 (ComfyUI Native)
    # Structure réelle du fichier wan2.2_vae.safetensors
    critical_keys = [
        "conv1.bias",  # (96,) - Entrée VAE global
        "conv2.bias",  # (48,) - Sortie VAE global
        "conv2.weight",  # (48, 48, 1, 1, 1) - Critique pour vérif canaux
        "decoder.conv1.bias",  # (1024,) - Entrée décodeur
        "decoder.conv1.weight",  # (1024, 48, 3, 3, 3) - Critique pour vérif canaux
        "encoder.conv1.bias",  # Entrée encodeur
        "encoder.conv1.weight",  # Entrée encodeur
    ]

    logger.info("Format attendu: WanVideoVAE38 (ComfyUI Native, 48 canaux)")

    missing_keys = []
    for key in critical_keys:
        if key not in keys:
            missing_keys.append(key)
            print(f"   ❌ Clé manquante: {key}")
            logger.error(f"   ❌ Clé manquante: {key}")

    if missing_keys:
        print(f"❌ {len(missing_keys)} clé(s) critique(s) manquante(s)")
        print("   Le fichier VAE est INCOMPLET ou CORROMPU")
        logger.error(f"❌ {len(missing_keys)} clé(s) critique(s) manquante(s)")
        logger.error("   Le fichier VAE est INCOMPLET ou CORROMPU")
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

    # 5. VÉRIFICATION CRITIQUE: Nombre de canaux (48 pour WanVideoVAE38)
    # Source: https://github.com/kijai/ComfyUI-WanVideoWrapper/blob/main/nodes_model_loading.py
    # WanVideoVAELoader.loadmodel() vérifie que le VAE a 48 canaux (pas 96!)

    print("")
    print("🔍 VÉRIFICATION CRITIQUE: Nombre de canaux...")
    logger.info("🔍 VÉRIFICATION CRITIQUE: Nombre de canaux du VAE...")
    logger.info("   WanVideoVAE38 attend 48 canaux (pas 96!)")
    logger.info("   Source: ComfyUI-WanVideoWrapper/nodes_model_loading.py")

    try:
        from safetensors.torch import safe_open

        with safe_open(vae_file, framework="pt", device="cpu") as f:
            # Vérifier decoder.conv1.weight: shape [out_channels, in_channels, ...]
            # Pour WanVideoVAE38, in_channels (dimension [1]) doit être 48
            decoder_conv1_weight = f.get_tensor("decoder.conv1.weight")
            decoder_in_channels = decoder_conv1_weight.shape[1]  # dimension [1]

            print(f"   decoder.conv1.weight: shape={tuple(decoder_conv1_weight.shape)}")
            logger.info(
                f"   decoder.conv1.weight: shape={tuple(decoder_conv1_weight.shape)}"
            )

            if decoder_in_channels != 48:
                print(
                    f"   ❌ ERREUR: decoder.conv1.weight a {decoder_in_channels} canaux d'entrée (attendu: 48)"
                )
                logger.error(
                    f"   ❌ ERREUR: decoder.conv1.weight a {decoder_in_channels} canaux d'entrée (attendu: 48)"
                )
                logger.error("")
                logger.error(
                    "   Ce VAE n'est PAS compatible avec ComfyUI WanVideoVAE38!"
                )
                logger.error(
                    "   Il s'agit probablement d'un VAE 96 canaux (ancien format)"
                )
                logger.error("")
                logger.error("   💡 Solution:")
                logger.error("      1. Supprimer ce fichier VAE incompatible")
                logger.error(f"         rm {vae_file}")
                logger.error("      2. Re-télécharger le bon VAE depuis HuggingFace:")
                logger.error(f"         ./scripts/setup_wan22_native.sh {model_name}")
                return False

            print(
                f"   ✅ decoder.conv1.weight: {decoder_in_channels} canaux d'entrée (correct)"
            )
            logger.success(
                f"   ✅ decoder.conv1.weight: {decoder_in_channels} canaux d'entrée (correct)"
            )

            # Vérifier conv2.weight: shape [out_channels, in_channels, ...]
            # Pour WanVideoVAE38, out_channels (dimension [0]) doit être 48
            conv2_weight = f.get_tensor("conv2.weight")
            conv2_out_channels = conv2_weight.shape[0]  # dimension [0]

            print(f"   conv2.weight: shape={tuple(conv2_weight.shape)}")
            logger.info(f"   conv2.weight: shape={tuple(conv2_weight.shape)}")

            if conv2_out_channels != 48:
                print(
                    f"   ❌ ERREUR: conv2.weight a {conv2_out_channels} canaux de sortie (attendu: 48)"
                )
                logger.error(
                    f"   ❌ ERREUR: conv2.weight a {conv2_out_channels} canaux de sortie (attendu: 48)"
                )
                logger.error("")
                logger.error(
                    "   Ce VAE n'est PAS compatible avec ComfyUI WanVideoVAE38!"
                )
                return False

            print(
                f"   ✅ conv2.weight: {conv2_out_channels} canaux de sortie (correct)"
            )
            logger.success(
                f"   ✅ conv2.weight: {conv2_out_channels} canaux de sortie (correct)"
            )

    except Exception as e:
        logger.error(f"❌ Erreur vérification canaux: {e}")
        return False

    print("")
    print("✅ LE VAE EST COMPATIBLE AVEC COMFYUI WANVIDEOVAE38 (48 CANAUX)")
    logger.success("✅ LE VAE EST COMPATIBLE AVEC COMFYUI WANVIDEOVAE38 (48 CANAUX)")

    # 6. Vérification finale
    print("")
    print("=" * 70)
    print("✅ VÉRIFICATION VAE RÉUSSIE")
    print(f"   Fichier: {vae_file.name}")
    print("   Format: SafeTensors WanVideoVAE38 (ComfyUI Native)")
    print(f"   Taille: {file_size_gb:.2f} GB")
    print(f"   Clés: {len(keys)}")
    print("   Canaux: 48 (compatible ComfyUI)")
    print("   Le VAE est COMPLET et VALIDE")
    print("=" * 70)
    print("")

    logger.info("")
    logger.success("=" * 70)
    logger.success("✅ VÉRIFICATION VAE RÉUSSIE")
    logger.success(f"   Fichier: {vae_file.name}")
    logger.success("   Format: SafeTensors WanVideoVAE38 (ComfyUI Native)")
    logger.success(f"   Taille: {file_size_gb:.2f} GB")
    logger.success(f"   Clés: {len(keys)}")
    logger.success("   Canaux: 48 (compatible ComfyUI)")
    logger.success("   Le VAE est COMPLET et VALIDE")
    logger.success("=" * 70)
    logger.info("")

    return True


def main():
    parser = argparse.ArgumentParser(description="Vérifie l'intégrité du VAE WAN 2.2")
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

    success = verify_vae(args.model_name, args.base_dir)

    if not success:
        logger.error("")
        logger.error("❌ ÉCHEC DE LA VÉRIFICATION VAE")
        logger.error(
            "   Le workflow est ARRÊTÉ pour éviter d'uploader un fichier corrompu"
        )
        logger.error("")
        sys.exit(1)

    sys.exit(0)


if __name__ == "__main__":
    main()
