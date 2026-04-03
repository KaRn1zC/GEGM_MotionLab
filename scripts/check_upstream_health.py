#!/usr/bin/env python3
"""
Vérifie la disponibilité et la version des fichiers upstream sur HuggingFace.

Utilise le registre central (config/model_registry.yaml) comme source de vérité.
Détecte les nouvelles versions en comparant les tailles de fichiers via HEAD requests.
"""

import sys
import argparse

import requests

from src.logger import get_logger
from src.model_registry import get_registry, ModelConfig

logger = get_logger("upstream_health")

# Tolérance de taille (±1% pour variations mineures)
SIZE_TOLERANCE = 0.01


def check_file_availability(
    url: str, expected_size: int, filename: str
) -> tuple[bool, int]:
    """
    Vérifie la disponibilité et la taille d'un fichier via HEAD request.

    Args:
        url: URL directe du fichier.
        expected_size: Taille attendue en bytes (0 = vérification accessibilité seule).
        filename: Nom du fichier pour les logs.

    Returns:
        (is_valid, actual_size) — True si accessible et taille cohérente.
    """
    try:
        response = requests.head(url, allow_redirects=True, timeout=15)

        if response.status_code != 200:
            logger.error(f"   ❌ {filename}: HTTP {response.status_code}")
            return False, 0

        actual_size = int(response.headers.get("Content-Length", 0))

        # Pas de taille attendue → simple vérification d'accessibilité
        if expected_size == 0:
            logger.success(f"   ✅ {filename}: accessible")
            return True, actual_size

        if actual_size == 0:
            logger.warning(f"   ⚠️  {filename}: taille non disponible dans headers")
            return False, 0

        min_size = expected_size * (1 - SIZE_TOLERANCE)
        max_size = expected_size * (1 + SIZE_TOLERANCE)

        if min_size <= actual_size <= max_size:
            size_mb = actual_size / (1024**2)
            expected_mb = expected_size / (1024**2)
            logger.success(
                f"   ✅ {filename}: {size_mb:.0f} MB (attendu: {expected_mb:.0f} MB)"
            )
            return True, actual_size

        size_mb = actual_size / (1024**2)
        expected_mb = expected_size / (1024**2)
        diff_pct = ((actual_size - expected_size) / expected_size) * 100
        logger.warning(
            f"   ⚠️  {filename}: {size_mb:.0f} MB "
            f"(attendu: {expected_mb:.0f} MB, diff: {diff_pct:+.1f}%)"
        )
        logger.warning("   → Nouvelle version détectée ou fichier modifié")
        return False, actual_size

    except requests.exceptions.RequestException as e:
        logger.error(f"   ❌ {filename}: erreur réseau — {e}")
        return False, 0


def check_hf_file(
    repo: str, hf_path: str, expected_size: int, filename: str
) -> tuple[bool, int]:
    """Vérifie un fichier sur HuggingFace via son repo et chemin."""
    url = f"https://huggingface.co/{repo}/resolve/main/{hf_path}"
    return check_file_availability(url, expected_size, filename)


def check_model_health(model: ModelConfig) -> bool:
    """
    Vérifie l'accessibilité et la cohérence de tous les fichiers upstream d'un modèle.

    Args:
        model: Configuration du modèle depuis le registre.

    Returns:
        True si tous les fichiers critiques sont disponibles et cohérents.
    """
    registry = get_registry()
    logger.info(f"🔍 Vérification upstream pour {model.name}...")
    all_valid = True

    # 1. Fichiers de diffusion (critiques)
    logger.info("📦 Fichiers de diffusion...")
    for df in model.diffusion_files:
        ok, _ = check_hf_file(model.hf_repo, df.hf_path, df.size_bytes, df.filename)
        if not ok:
            all_valid = False

    # 2. VAE (critique si séparé)
    if model.vae.filename != "integrated":
        logger.info("📦 VAE...")
        # Pas de size_bytes dans VaeConfig → vérification d'accessibilité
        ok, _ = check_hf_file(model.hf_repo, model.vae.hf_path, 0, model.vae.filename)
        if not ok:
            all_valid = False
    else:
        logger.info("   ℹ️  VAE intégré dans le checkpoint")

    # 3. Text encoder (critique)
    if model.text_encoder:
        # Text encoder propre au modèle (Gemma pour LTX)
        te = model.text_encoder
        logger.info(f"📦 Text encoder ({te.filename})...")
        ok, _ = check_hf_file(te.hf_repo, te.hf_path, te.size_bytes, te.filename)
        if not ok:
            all_valid = False
    else:
        # T5 partagé (WAN)
        shared_te = registry.get_shared_components().text_encoder
        logger.info(f"📦 Text encoder partagé ({shared_te.filename})...")
        ok, _ = check_hf_file(
            shared_te.hf_repo, shared_te.hf_path, shared_te.size_bytes,
            shared_te.filename,
        )
        if not ok:
            all_valid = False

    # 4. Composants partagés (non bloquants)
    shared = registry.get_shared_components()
    logger.info("🔧 Composants partagés (upscalers)...")
    for up in shared.upscalers:
        ok, _ = check_file_availability(up.url, 0, up.filename)
        if not ok and not up.optional:
            all_valid = False
        elif not ok:
            logger.warning(
                f"   ⚠️  {up.filename} indisponible (optionnel)"
            )

    return all_valid


def main() -> None:
    """Point d'entrée CLI — vérifie la santé upstream d'un modèle du registre."""
    parser = argparse.ArgumentParser(
        description="Vérifie la disponibilité des fichiers upstream via le registre"
    )
    parser.add_argument("model_name", help="Nom du modèle (ex: ltx-2.3-i2v-dev)")
    parser.add_argument("--verbose", "-v", action="store_true", help="Logs détaillés")
    args = parser.parse_args()

    registry = get_registry()
    model = registry.get_model(args.model_name)

    if not model:
        logger.error(f"❌ Modèle inconnu du registre: {args.model_name}")
        available = ", ".join(registry.list_models())
        logger.error(f"   Modèles disponibles: {available}")
        sys.exit(1)

    logger.info(f"📋 Registre chargé — {model.display_name} ({model.architecture})")

    is_healthy = check_model_health(model)

    if is_healthy:
        logger.success("")
        logger.success("=" * 70)
        logger.success("✅ UPSTREAM DISPONIBLE ET À JOUR")
        logger.success(f"   Modèle: {args.model_name} ({model.display_name})")
        logger.success("   Tous les fichiers correspondent aux versions attendues")
        logger.success("   Téléchargement upstream recommandé")
        logger.success("=" * 70)
        logger.success("")
        sys.exit(0)
    else:
        logger.warning("")
        logger.warning("=" * 70)
        logger.warning("⚠️  UPSTREAM NON DISPONIBLE OU VERSION DIFFÉRENTE")
        logger.warning(f"   Modèle: {args.model_name} ({model.display_name})")
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
