#!/usr/bin/env python3
"""
Vérifie l'intégrité du VAE WAN 2.2 (ComfyUI Native - WanVideoVAE38 48 canaux)
Usage: python scripts/verify_vae.py wan2.2-ti2v-5b
"""

import sys
import argparse
from pathlib import Path

from src.logger import get_logger
from src.model_registry import get_registry

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

    # Déterminer la config VAE via le registre (extensible)
    try:
        registry = get_registry()
        vae_config = registry.get_vae_config(model_name)
    except Exception:
        vae_config = None

    if vae_config:
        # VAE intégré dans le checkpoint (ex: LTX 2.3) → rien à vérifier
        if vae_config.filename == "integrated":
            print(f"✅ VAE intégré dans le checkpoint pour {model_name} (rien à vérifier)")
            logger.info(f"✅ VAE intégré dans le checkpoint pour {model_name}")
            return True

        vae_file = model_dir / vae_config.filename
        expected_size_min = vae_config.min_size_gb
        expected_size_max = vae_config.max_size_gb
        expected_channels = vae_config.expected_channels
        vae_version = vae_config.version
    else:
        logger.error(f"❌ Modèle inconnu: {model_name}")
        return False

    print(f"🔍 Vérification de l'intégrité du VAE pour {model_name}...")
    logger.info(
        f"🔍 Vérification de l'intégrité du VAE {vae_version} ({expected_channels} canaux)..."
    )
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

    # Clés critiques depuis le registre
    ver_config = registry.get_verification_config(model_name) if vae_config else None
    if ver_config:
        critical_keys = ver_config.vae_keys
    else:
        critical_keys = [
            "conv1.bias",
            "conv2.bias",
            "conv2.weight",
            "decoder.conv1.bias",
            "decoder.conv1.weight",
            "encoder.conv1.bias",
            "encoder.conv1.weight",
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
    print(f"🔍 VÉRIFICATION CRITIQUE: Nombre de canaux (VAE {vae_version})...")
    logger.info(f"🔍 VÉRIFICATION CRITIQUE: Nombre de canaux du VAE {vae_version}...")
    logger.info(f"   VAE {vae_version} attend {expected_channels} canaux")
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

            if decoder_in_channels != expected_channels:
                print(
                    f"   ❌ ERREUR: decoder.conv1.weight a {decoder_in_channels} canaux d'entrée (attendu: {expected_channels})"
                )
                logger.error(
                    f"   ❌ ERREUR: decoder.conv1.weight a {decoder_in_channels} canaux d'entrée (attendu: {expected_channels})"
                )
                logger.error("")
                logger.error(
                    f"   Ce VAE n'est PAS compatible avec le modèle {model_name}!"
                )
                logger.error(
                    f"   Architecture attendue: VAE {vae_version} ({expected_channels} canaux)"
                )
                logger.error("")
                logger.error("   💡 Solution:")
                logger.error("      1. Supprimer ce fichier VAE incompatible")
                logger.error(f"         rm {vae_file}")
                logger.error("      2. Re-télécharger le bon VAE depuis HuggingFace:")
                logger.error(f"         ./scripts/setup_wan22_native.sh {model_name}")
                return False

            print(
                f"   ✅ decoder.conv1.weight: {decoder_in_channels} canaux d'entrée (correct pour VAE {vae_version})"
            )
            logger.success(
                f"   ✅ decoder.conv1.weight: {decoder_in_channels} canaux d'entrée (correct pour VAE {vae_version})"
            )

            # Vérifier conv2.weight: shape [out_channels, in_channels, ...]
            # Le nombre de canaux de sortie doit correspondre à l'architecture du VAE
            conv2_weight = f.get_tensor("conv2.weight")
            conv2_out_channels = conv2_weight.shape[0]  # dimension [0]

            print(f"   conv2.weight: shape={tuple(conv2_weight.shape)}")
            logger.info(f"   conv2.weight: shape={tuple(conv2_weight.shape)}")

            if conv2_out_channels != expected_channels:
                print(
                    f"   ❌ ERREUR: conv2.weight a {conv2_out_channels} canaux de sortie (attendu: {expected_channels})"
                )
                logger.error(
                    f"   ❌ ERREUR: conv2.weight a {conv2_out_channels} canaux de sortie (attendu: {expected_channels})"
                )
                logger.error("")
                logger.error(
                    f"   Ce VAE n'est PAS compatible avec le modèle {model_name}!"
                )
                return False

            print(
                f"   ✅ conv2.weight: {conv2_out_channels} canaux de sortie (correct pour VAE {vae_version})"
            )
            logger.success(
                f"   ✅ conv2.weight: {conv2_out_channels} canaux de sortie (correct pour VAE {vae_version})"
            )

    except Exception as e:
        logger.error(f"❌ Erreur vérification canaux: {e}")
        return False

    print("")
    print(f"✅ LE VAE {vae_version} EST COMPATIBLE ({expected_channels} CANAUX)")
    logger.success(
        f"✅ LE VAE {vae_version} EST COMPATIBLE ({expected_channels} CANAUX)"
    )

    # 6. Vérification finale
    print("")
    print("=" * 70)
    print("✅ VÉRIFICATION VAE RÉUSSIE")
    print(f"   Fichier: {vae_file.name}")
    print(f"   Format: SafeTensors VAE {vae_version} (ComfyUI Native)")
    print(f"   Taille: {file_size_gb:.2f} GB")
    print(f"   Clés: {len(keys)}")
    print(f"   Canaux: {expected_channels} (compatible {model_name})")
    print("   Le VAE est COMPLET et VALIDE")
    print("=" * 70)
    print("")

    logger.info("")
    logger.success("=" * 70)
    logger.success("✅ VÉRIFICATION VAE RÉUSSIE")
    logger.success(f"   Fichier: {vae_file.name}")
    logger.success(f"   Format: SafeTensors VAE {vae_version} (ComfyUI Native)")
    logger.success(f"   Taille: {file_size_gb:.2f} GB")
    logger.success(f"   Clés: {len(keys)}")
    logger.success(f"   Canaux: {expected_channels} (compatible {model_name})")
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
