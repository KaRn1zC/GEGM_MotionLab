"""
Configuration du logger pour GEGM MotionLab
Utilise loguru pour un logging avancé avec rotation et niveaux configurables
"""

import sys
import os
from pathlib import Path
from loguru import logger
from typing import Any


class ComfyLogger:
    """
    Gestionnaire de logging centralisé pour GEGM MotionLab
    Basé sur loguru avec configuration flexible
    """

    def __init__(self, base_dir: str = "."):
        self.base_dir = Path(base_dir)
        self.logs_dir = self.base_dir / "logs"
        self.logs_dir.mkdir(exist_ok=True)

        # Supprimer le handler par défaut de loguru
        logger.remove()

        # Configuration par défaut
        self.default_config = {
            "console": {
                "enabled": True,
                "level": "INFO",
                "format": "<green>{time:HH:mm:ss}</green> | <level>{level: <8}</level> | <cyan>{name}</cyan> | <level>{message}</level>",
                "colorize": True,
            },
            "file": {
                "enabled": True,
                "level": "DEBUG",
                "format": "{time:YYYY-MM-DD HH:mm:ss} | {level: <8} | {name} | {function} | {line} | {message}",
                "rotation": "10 MB",
                "retention": "7 days",
                "compression": "zip",
            },
            "error_file": {
                "enabled": True,
                "level": "ERROR",
                "format": "{time:YYYY-MM-DD HH:mm:ss} | {level: <8} | {name} | {function} | {line} | {message} | {exception}",
                "rotation": "5 MB",
                "retention": "30 days",
            },
        }

        self._configure_default()

    def _configure_default(self):
        """Configure les handlers par défaut"""

        # Handler console
        if self.default_config["console"]["enabled"]:
            logger.add(
                sys.stdout,
                level=self.default_config["console"]["level"],
                format=self.default_config["console"]["format"],
                colorize=self.default_config["console"]["colorize"],
                enqueue=True,
            )

        # Handler fichier principal
        if self.default_config["file"]["enabled"]:
            logger.add(
                self.logs_dir / "gegm-motionlab.log",
                level=self.default_config["file"]["level"],
                format=self.default_config["file"]["format"],
                rotation=self.default_config["file"]["rotation"],
                retention=self.default_config["file"]["retention"],
                compression=self.default_config["file"]["compression"],
                enqueue=True,
            )

        # Handler fichier erreurs
        if self.default_config["error_file"]["enabled"]:
            logger.add(
                self.logs_dir / "errors.log",
                level=self.default_config["error_file"]["level"],
                format=self.default_config["error_file"]["format"],
                rotation=self.default_config["error_file"]["rotation"],
                retention=self.default_config["error_file"]["retention"],
                enqueue=True,
            )

    def configure_module_logger(
        self, module_name: str, log_file: str | None = None, level: str = "INFO"
    ):
        """
        Configure un logger spécifique pour un module

        Args:
            module_name: Nom du module (ex: "download_models", "web_interface")
            log_file: Nom du fichier de log spécifique (optionnel)
            level: Niveau de log pour ce module
        """

        if log_file:
            log_path = self.logs_dir / f"{log_file}.log"
            logger.add(
                log_path,
                level=level,
                format="{time:YYYY-MM-DD HH:mm:ss} | {level: <8} | {module} | {function} | {message}",
                rotation="5 MB",
                retention="7 days",
                filter=lambda record: record["extra"].get("module") == module_name,
                enqueue=True,
            )

        # Logger contextualisé
        return logger.bind(module=module_name)

    def get_logger(self, name: str = "comfy") -> Any:
        """Retourne un logger contextualisé avec le nom du module"""
        return logger.bind(name=name)

    def set_level(self, level: str):
        """Change le niveau de log global (DEBUG, INFO, WARNING, ERROR)"""
        # Reconfigurer tous les handlers avec le nouveau niveau
        logger.remove()
        self.default_config["console"]["level"] = level
        self.default_config["file"]["level"] = level
        self._configure_default()

        logger.info(f"Niveau de log changé vers: {level}")


# Instance globale du logger
_comfy_logger = None


def get_logger(name: str = "comfy") -> Any:
    """
    Fonction globale pour obtenir un logger configuré

    Args:
        name: Nom du module/composant

    Returns:
        Logger loguru configuré

    Usage:
        from src.logger import get_logger
        logger = get_logger("web_interface")
        logger.info("Message de log")
    """
    global _comfy_logger

    if _comfy_logger is None:
        _comfy_logger = ComfyLogger()

    return _comfy_logger.get_logger(name)


def setup_logger(
    config: dict[str, Any | None] = None, level: str = "INFO"
) -> ComfyLogger:
    """
    Configure le système de logging pour l'application

    Args:
        config: Configuration personnalisée (optionnel)
        level: Niveau de log par défaut

    Returns:
        Instance du ComfyLogger configuré
    """
    global _comfy_logger

    _comfy_logger = ComfyLogger()

    if config:
        # Appliquer la configuration personnalisée
        _comfy_logger.default_config.update(config)
        logger.remove()
        _comfy_logger._configure_default()

    _comfy_logger.set_level(level)

    logger.info("🎬 GEGM MotionLab - Système de logging initialisé")
    logger.info(f"📂 Logs sauvegardés dans: {_comfy_logger.logs_dir}")

    return _comfy_logger


def configure_for_development():
    """Configuration optimisée pour le développement"""
    dev_config = {
        "console": {
            "enabled": True,
            "level": "DEBUG",
            "format": "<green>{time:HH:mm:ss}</green> | <level>{level: <8}</level> | <blue>{name}</blue> | <level>{message}</level>",
            "colorize": True,
        }
    }

    return setup_logger(dev_config, level="DEBUG")


def configure_for_production():
    """Configuration optimisée pour la production"""
    prod_config = {
        "console": {
            "enabled": False,  # Pas de logs console en production
            "level": "INFO",
            "format": "<green>{time:HH:mm:ss}</green> | <level>{level: <8}</level> | <cyan>{name}</cyan> | <level>{message}</level>",
            "colorize": True,
        },
        "file": {
            "enabled": True,
            "level": "INFO",  # Moins verbeux qu'en dev
            "format": "{time:YYYY-MM-DD HH:mm:ss} | {level: <8} | {name} | {function} | {line} | {message}",
            "rotation": "50 MB",
            "retention": "30 days",
            "compression": "zip",
        },
        "error_file": {
            "enabled": True,
            "level": "ERROR",
            "format": "{time:YYYY-MM-DD HH:mm:ss} | {level: <8} | {name} | {function} | {line} | {message} | {exception}",
            "rotation": "5 MB",
            "retention": "30 days",
        },
    }

    return setup_logger(prod_config, level="INFO")


def configure_for_runpod():
    """Configuration optimisée pour l'environnement RunPod"""
    runpod_config = {
        "console": {
            "enabled": True,
            "level": "INFO",
            "format": "<green>{time:HH:mm:ss}</green> | <level>{level: <8}</level> | <cyan>{name}</cyan> | <level>{message}</level>",
            "colorize": True,
        },
        "file": {
            "enabled": True,
            "level": "DEBUG",
            "format": "{time:YYYY-MM-DD HH:mm:ss} | {level: <8} | {name} | {function} | {line} | {message}",
            "rotation": "20 MB",  # Rotation plus fréquente sur RunPod
            "retention": "3 days",  # Moins de rétention pour économiser l'espace
            "compression": "zip",
        },
        "error_file": {
            "enabled": True,  # AJOUT MANQUANT
            "level": "ERROR",  # AJOUT MANQUANT
            "format": "{time:YYYY-MM-DD HH:mm:ss} | {level: <8} | {name} | {function} | {line} | {message} | {exception}",
            "rotation": "5 MB",  # AJOUT MANQUANT
            "retention": "30 days",  # AJOUT MANQUANT
        },
    }

    return setup_logger(runpod_config, level="INFO")


# Fonctions utilitaires pour les logs spécialisés


def log_model_download(model_name: str, status: str, details: str = ""):
    """Log spécialisé pour les téléchargements de modèles"""
    logger = get_logger("model_download")

    if status == "start":
        logger.info(f"🔽 Début téléchargement: {model_name}")
    elif status == "success":
        logger.success(f"✅ Téléchargement réussi: {model_name} | {details}")
    elif status == "error":
        logger.error(f"❌ Erreur téléchargement: {model_name} | {details}")
    elif status == "progress":
        logger.debug(f"📊 Progression: {model_name} | {details}")


def log_cinemagraph_generation(input_image: str, status: str, details: str = ""):
    """Log spécialisé pour la génération de cinemagraphs"""
    logger = get_logger("cinemagraph")

    if status == "start":
        logger.info(f"🎬 Début génération: {input_image}")
    elif status == "success":
        logger.success(f"✅ Cinemagraph généré: {input_image} | {details}")
    elif status == "error":
        logger.error(f"❌ Erreur génération: {input_image} | {details}")
    elif status == "progress":
        logger.debug(f"📊 Progression: {input_image} | {details}")


def log_api_request(
    endpoint: str, method: str, status_code: int, response_time: float = 0.0
):
    """Log spécialisé pour les requêtes API"""
    logger = get_logger("api")

    if status_code >= 200 and status_code < 300:
        logger.info(f"🌐 {method} {endpoint} | {status_code} | {response_time:.3f}s")
    elif status_code >= 400:
        logger.warning(f"⚠️  {method} {endpoint} | {status_code} | {response_time:.3f}s")


def log_system_info():
    """Log des informations système au démarrage"""
    import platform
    import psutil

    logger = get_logger("system")

    logger.info("🖥️  Informations système:")
    logger.info(f"   OS: {platform.system()} {platform.release()}")
    logger.info(f"   Python: {platform.python_version()}")
    logger.info(f"   CPU: {psutil.cpu_count()} cores")
    logger.info(f"   RAM: {psutil.virtual_memory().total / (1024**3):.1f}GB")

    # Information GPU si disponible
    try:
        import torch

        if torch.cuda.is_available():
            gpu_name = torch.cuda.get_device_name(0)
            gpu_memory = torch.cuda.get_device_properties(0).total_memory / (1024**3)
            logger.info(f"   GPU: {gpu_name} ({gpu_memory:.1f}GB)")
        else:
            logger.info("   GPU: Non disponible")
    except ImportError:
        logger.debug("   GPU: PyTorch non installé, impossible de détecter")


# Configuration automatique selon l'environnement
def auto_configure():
    """Configuration automatique selon l'environnement détecté"""

    # Détecter l'environnement
    if os.getenv("RUNPOD_POD_ID"):
        logger_instance = configure_for_runpod()
        get_logger("system").info("🚀 Environnement RunPod détecté")
    elif os.getenv("FLASK_ENV") == "development":
        logger_instance = configure_for_development()
        get_logger("system").info("🛠️  Environnement de développement détecté")
    else:
        logger_instance = configure_for_production()
        get_logger("system").info("🏭 Environnement de production détecté")

    log_system_info()
    return logger_instance


if __name__ == "__main__":
    # Test du système de logging
    print("🧪 Test du système de logging GEGM MotionLab")

    # Configuration pour test
    test_logger = setup_logger(level="DEBUG")

    # Tests des différents niveaux
    logger = get_logger("test")

    logger.debug("Message de debug")
    logger.info("Message d'information")
    logger.success("Message de succès")
    logger.warning("Message d'avertissement")
    logger.error("Message d'erreur")

    # Test des logs spécialisés
    log_model_download("wan_2_2_i2v_14b", "start")
    log_model_download("wan_2_2_i2v_14b", "success", "28.5GB téléchargés")

    log_cinemagraph_generation("test_image.jpg", "start")
    log_cinemagraph_generation("test_image.jpg", "success", "output.mp4 généré")

    log_api_request("/generate", "POST", 200, 1.234)

    print("✅ Test terminé - Vérifiez le dossier logs/")
