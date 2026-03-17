"""
Gestionnaire de configuration OwnCloud
Charge .env (identifiants) + YAML (paramètres techniques)
"""

import os
import yaml
import sys
from pathlib import Path
from typing import Any
from dotenv import load_dotenv


from src.logger import get_logger
from src.models.owncloud_models import OwnCloudConfig

logger = get_logger("owncloud_config")


class OwnCloudConfigManager:
    """Gestionnaire centralisé OwnCloud"""

    def __init__(
        self, config_file: str = "config/owncloud.yaml", env_file: str = ".env"
    ):
        self.config_file = Path(config_file)
        self.env_file = Path(env_file)
        self.configs: dict[str, Any] = {}

        # 1. Charger .env
        self._load_env()

        # 2. Charger YAML
        self._load_yaml()

    def _load_env(self):
        """Charge les variables d'environnement depuis .env"""
        if self.env_file.exists():
            load_dotenv(self.env_file)
            logger.info(f"✅ Variables d'environnement chargées: {self.env_file}")
        else:
            logger.warning(f"⚠️  Fichier .env non trouvé: {self.env_file}")

    def _load_yaml(self):
        """Charge la configuration YAML (paramètres techniques)"""
        if self.config_file.exists():
            try:
                with open(self.config_file, "r", encoding="utf-8") as f:
                    self.configs = yaml.safe_load(f) or {}
                logger.info(f"✅ Configuration YAML chargée: {self.config_file}")
            except Exception as e:
                logger.error(f"❌ Erreur chargement YAML: {e}")
                self.configs = {}
        else:
            logger.warning(f"⚠️  Fichier YAML non trouvé: {self.config_file}")
            self.configs = {}

    def get_owncloud_config(self, profile: str = "default") -> OwnCloudConfig:
        """
        Crée une configuration OwnCloud complète

        Args:
            profile: Profil YAML (default, development, production, runpod)

        Returns:
            OwnCloudConfig: Configuration complète
        """
        # 1. Récupérer identifiants depuis .env (PRIORITAIRE)
        server_url = os.getenv("OWNCLOUD_SERVER_URL", "").rstrip("/")
        username = os.getenv("OWNCLOUD_USERNAME", "")
        password = os.getenv("OWNCLOUD_PASSWORD", "")
        upload_folder = os.getenv("OWNCLOUD_MODEL_FOLDER", "/Cinemagraphs")

        # 2. Récupérer paramètres techniques depuis YAML
        owncloud_configs = self.configs.get("owncloud", {})
        base_params = owncloud_configs.get("default", {})
        profile_params = owncloud_configs.get(profile, {})

        # 3. Merger (profile override base)
        technical_params = {**base_params, **profile_params}

        # 4. Construire la config finale
        final_config = {
            "server_url": server_url,
            "username": username,
            "password": password,
            "upload_folder": upload_folder,
            "chunk_size": technical_params.get("chunk_size", 8192),
            "timeout": technical_params.get("timeout", 300),
            "max_retries": technical_params.get("max_retries", 3),
            "retry_delay": technical_params.get("retry_delay", 1.0),
        }

        # 5. Créer et valider
        try:
            config = OwnCloudConfig(**final_config)
            errors = config.validate()

            if errors:
                raise ValueError(f"Configuration invalide: {', '.join(errors)}")

            logger.info(f"✅ Config OwnCloud créée (profil: {profile})")
            return config

        except Exception as e:
            logger.error(f"❌ Erreur création config: {e}")
            raise ValueError(f"Configuration OwnCloud invalide: {e}")

    def get_sharing_config(self) -> dict[str, Any]:
        """Retourne la config de partage depuis YAML"""
        return self.configs.get(
            "sharing",
            {
                "default_expire_days": 365,
                "default_permissions": 1,
                "password_protection": False,
            },
        )

    def get_metadata_config(self) -> dict[str, Any]:
        """Retourne la config des métadonnées depuis YAML"""
        return self.configs.get(
            "metadata",
            {
                "include_generation_params": True,
                "include_model_info": True,
                "include_prompt": True,
                "save_separate_json": True,
            },
        )

    def check_configuration(self) -> dict[str, Any]:
        """Vérifie que tout est bien configuré"""
        report = {
            "env_file_exists": self.env_file.exists(),
            "yaml_file_exists": self.config_file.exists(),
            "credentials": {},
            "issues": [],
        }

        # Vérifier les credentials depuis .env
        credentials = {
            "OWNCLOUD_SERVER_URL": os.getenv("OWNCLOUD_SERVER_URL"),
            "OWNCLOUD_USERNAME": os.getenv("OWNCLOUD_USERNAME"),
            "OWNCLOUD_PASSWORD": os.getenv("OWNCLOUD_PASSWORD"),
            "OWNCLOUD_MODEL_FOLDER": os.getenv("OWNCLOUD_MODEL_FOLDER"),
        }

        for key, value in credentials.items():
            if value:
                # Masquer le mot de passe
                display = "***" if "PASSWORD" in key else value
                report["credentials"][key] = f"✅ {display}"
            else:
                report["credentials"][key] = "❌ Manquant"
                report["issues"].append(f"Variable manquante: {key}")

        return report


# Instance globale
_config_manager = None


def get_config_manager() -> OwnCloudConfigManager:
    """Retourne l'instance globale du config manager"""
    global _config_manager
    if _config_manager is None:
        _config_manager = OwnCloudConfigManager()
    return _config_manager


def get_owncloud_config(profile: str = "default") -> OwnCloudConfig:
    """
    Fonction helper pour obtenir une config OwnCloud

    Args:
        profile: Profil à utiliser (default, development, production, runpod)

    Returns:
        OwnCloudConfig: Configuration prête
    """
    return get_config_manager().get_owncloud_config(profile)


def check_owncloud_setup() -> bool:
    """
    Vérifie que OwnCloud est bien configuré

    Returns:
        bool: True si config complète
    """
    manager = get_config_manager()
    report = manager.check_configuration()

    logger.info("🔍 Vérification configuration OwnCloud:")
    logger.info(f"   Fichier .env: {'✅' if report['env_file_exists'] else '❌'}")
    logger.info(f"   Fichier YAML: {'✅' if report['yaml_file_exists'] else '❌'}")
    logger.info("   Identifiants:")

    for key, status in report["credentials"].items():
        logger.info(f"      {key}: {status}")

    if report["issues"]:
        logger.warning(f"   ⚠️  {len(report['issues'])} problème(s):")
        for issue in report["issues"]:
            logger.warning(f"      - {issue}")
        return False

    logger.success("   ✅ Configuration complète et valide")
    return True


if __name__ == "__main__":
    from src.logger import setup_logger

    setup_logger(level="INFO")
    logger.info("🧪 Test configuration OwnCloud")

    # Vérifier la configuration
    is_valid = check_owncloud_setup()

    if is_valid:
        try:
            # Tester les profils
            for profile in ["default", "development", "production"]:
                logger.info(f"\n📋 Test profil: {profile}")
                config = get_owncloud_config(profile)
                logger.info(f"   Server: {config.server_url}")
                logger.info(f"   Upload folder: {config.upload_folder}")
                logger.info(f"   Timeout: {config.timeout}s")
                logger.info(f"   Chunk size: {config.chunk_size} bytes")
        except Exception as e:
            logger.error(f"❌ Erreur: {e}")

    logger.info("\n✅ Test terminé")
