"""
Script de validation adapté pour la stratégie native ComfyUI + huggingface-cli
Version pure logger - tout passe par le système de logging
"""

import sys
import requests
import yaml
import subprocess
from pathlib import Path


# Import du système de logging centralisé
from src.logger import get_logger, setup_logger

# Configuration du logger pour ce script avec output console
setup_logger(level="INFO")
logger = get_logger("url_validation")


def load_model_config(config_path: str = "config/model_versions.yaml") -> dict:
    """Charge la configuration des modèles"""
    try:
        with open(config_path, "r") as f:
            config = yaml.safe_load(f)
        logger.info(
            f"Configuration chargée: {len(config.get('models', {}))} modèles trouvés"
        )
        return config
    except FileNotFoundError:
        logger.error(f"Fichier de configuration non trouvé: {config_path}")
        return {}
    except yaml.YAMLError as e:
        logger.error(f"Erreur de parsing YAML: {e}")
        return {}
    except Exception as e:
        logger.error(f"Erreur lors du chargement de la configuration: {e}")
        return {}


def validate_repository_url(repo_url: str) -> tuple[bool, str]:
    """Valide un repository Git"""
    try:
        if repo_url.endswith(".git"):
            web_url = repo_url[:-4]
        else:
            web_url = repo_url

        logger.debug(f"Validation de l'URL: {web_url}")
        response = requests.get(web_url, timeout=10)

        if response.status_code == 200:
            logger.debug(f"Repository valide: {web_url}")
            return True, "Repository valide"
        else:
            logger.warning(
                f"Repository inaccessible: {web_url} (HTTP {response.status_code})"
            )
            return False, f"HTTP {response.status_code}"

    except requests.exceptions.Timeout:
        logger.error(f"Timeout lors de la validation: {repo_url}")
        return False, "Timeout"
    except requests.exceptions.ConnectionError:
        logger.error(f"Erreur de connexion: {repo_url}")
        return False, "Erreur de connexion"
    except Exception as e:
        logger.error(f"Erreur lors de la validation de {repo_url}: {e}")
        return False, str(e)


def validate_huggingface_repo(repo_id: str) -> tuple[bool, str]:
    """Valide un repository HuggingFace"""
    try:
        url = f"https://huggingface.co/{repo_id}"
        logger.debug(f"Validation du repository HF: {url}")

        response = requests.get(url, timeout=10)

        if response.status_code == 200:
            logger.debug(f"Repository HF accessible: {repo_id}")
            return True, "Repository HF accessible"
        else:
            logger.warning(
                f"Repository HF inaccessible: {repo_id} (HTTP {response.status_code})"
            )
            return False, f"HTTP {response.status_code}"

    except requests.exceptions.Timeout:
        logger.error(f"Timeout lors de la validation HF: {repo_id}")
        return False, "Timeout"
    except requests.exceptions.ConnectionError:
        logger.error(f"Erreur de connexion HF: {repo_id}")
        return False, "Erreur de connexion"
    except Exception as e:
        logger.error(f"Erreur lors de la validation HF {repo_id}: {e}")
        return False, str(e)


def check_huggingface_cli() -> tuple[bool, str]:
    """Vérifie que huggingface-cli est installé"""
    try:
        logger.debug("Vérification de huggingface-cli...")
        result = subprocess.run(
            ["huggingface-cli", "--help"], capture_output=True, text=True, timeout=10
        )

        if result.returncode == 0:
            logger.info("HuggingFace CLI détecté et fonctionnel")
            return True, "CLI installé"
        else:
            logger.warning("HuggingFace CLI installé mais non fonctionnel")
            return False, "CLI non fonctionnel"

    except FileNotFoundError:
        logger.error("HuggingFace CLI non trouvé")
        return False, "CLI non installé"
    except subprocess.TimeoutExpired:
        logger.error("Timeout lors de la vérification de HuggingFace CLI")
        return False, "Timeout CLI"
    except Exception as e:
        logger.error(f"Erreur lors de la vérification CLI: {e}")
        return False, str(e)


def main():
    """Fonction principale de validation adaptée"""
    logger.info("🔍 Validation ComfyUI Native + HuggingFace - Comfy_Img_to_Loop")
    logger.info("=" * 65)

    config = load_model_config()
    if not config:
        logger.error("Impossible de charger la configuration, arrêt du script")
        return 1

    # 1. Vérifier huggingface-cli
    logger.info("🤗 Validation HuggingFace CLI...")
    hf_ok, hf_msg = check_huggingface_cli()
    hf_icon = "✅" if hf_ok else "❌"
    logger.info(f"{hf_icon} HuggingFace CLI: {hf_msg}")

    if not hf_ok:
        logger.warning("HuggingFace CLI non disponible")
        logger.info("💡 Installation: pip install 'huggingface_hub[cli]'")

    # 2. Valider les repositories HuggingFace
    models = config.get("models", {})
    hf_results = []

    if models:
        logger.info(f"🤖 Validation de {len(models)} repositories HuggingFace...")

        for model_name, model_info in models.items():
            repo = model_info.get("repository", "")
            if repo:
                logger.info(f"🔍 {model_name}: {repo}")
                is_valid, info = validate_huggingface_repo(repo)
                hf_results.append((model_name, is_valid, info))
            else:
                logger.warning(f"Pas de repository défini pour le modèle: {model_name}")

    # 3. Valider les custom nodes
    custom_nodes = config.get("custom_nodes", {})
    logger.info(f"🔌 Validation de {len(custom_nodes)} custom nodes...")

    node_results = []
    for node_name, node_info in custom_nodes.items():
        repo_url = node_info.get("repository", "")
        if repo_url:
            logger.info(f"🔍 {node_name}: {repo_url}")
            is_valid, info = validate_repository_url(repo_url)
            node_results.append((node_name, is_valid, info))
        else:
            logger.warning(f"Pas de repository défini pour le custom node: {node_name}")

    # Résumé
    logger.info("=" * 65)
    logger.info("📊 RÉSUMÉ DE LA VALIDATION")
    logger.info("=" * 65)

    # CLI HuggingFace
    logger.info("🤗 HUGGINGFACE CLI:")
    logger.info(f"{hf_icon} {hf_msg}")

    # Repositories HF
    valid_hf = 0
    if models and hf_results:
        logger.info("🤖 REPOSITORIES HUGGINGFACE:")
        for name, is_valid, info in hf_results:
            icon = "✅" if is_valid else "❌"
            logger.info(f"{icon} {name:25} | {info}")
            if is_valid:
                valid_hf += 1

        logger.info(f"   📈 Score HF: {valid_hf}/{len(hf_results)}")

    # Custom nodes
    logger.info("🔌 CUSTOM NODES:")
    valid_nodes = 0
    for name, is_valid, info in node_results:
        icon = "✅" if is_valid else "❌"
        logger.info(f"{icon} {name:25} | {info}")
        if is_valid:
            valid_nodes += 1

    logger.info(f"   📈 Score nodes: {valid_nodes}/{len(node_results)}")

    # Score global et recommandations
    total_valid = (1 if hf_ok else 0) + valid_nodes + valid_hf
    total_items = 1 + len(node_results) + len(hf_results)

    logger.info(f"🎯 SCORE GLOBAL: {total_valid}/{total_items}")

    # Recommandations
    logger.info("💡 PROCHAINES ÉTAPES:")
    if not hf_ok:
        logger.warning(
            "1. ❌ Installer huggingface-cli: pip install 'huggingface_hub[cli]'"
        )
    else:
        logger.info("1. ✅ HuggingFace CLI prêt")

    if valid_nodes >= len(node_results) - 1:  # Au moins 2/3 nodes OK
        logger.info("2. ✅ Custom nodes accessibles")
    else:
        logger.warning("2. ⚠️  Vérifier les custom nodes manquants")

    if total_valid >= total_items - 1:
        logger.success("3. 🚀 PRÊT ! Exécuter: ./scripts/setup_wan22_native.sh")
        logger.success("✅ Validation terminée avec succès - Système prêt")
        return 0
    else:
        logger.error("3. ⚠️  Corriger les problèmes avant setup")
        logger.error("❌ Validation échouée - Corrections nécessaires")
        return 1


if __name__ == "__main__":
    import sys

    try:
        exit_code = main()
        logger.info(f"Script de validation terminé avec le code: {exit_code}")
        sys.exit(exit_code)
    except KeyboardInterrupt:
        logger.warning("Script interrompu par l'utilisateur")
        sys.exit(1)
    except Exception as e:
        logger.error(f"Erreur inattendue dans le script: {e}")
        sys.exit(1)
