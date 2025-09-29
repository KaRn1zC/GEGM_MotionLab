#!/usr/bin/env python3
"""
Tests unitaires pour le système de logging
"""

import sys
from pathlib import Path

# Ajouter le projet au path
sys.path.append(str(Path(__file__).parent.parent))

from src.logger import (
    get_logger,
    setup_logger,
    configure_for_development,
    log_model_download,
    log_cinemagraph_generation,
    log_api_request,
)


class TestComfyLogger:
    """Tests pour le système de logging"""

    def test_basic_logging(self):
        """Test des fonctionnalités de base"""
        logger = get_logger("test_basic")

        # Test que les méthodes ne lèvent pas d'erreur
        logger.debug("Message de debug")
        logger.info("Message d'information")
        logger.success("Message de succès")
        logger.warning("Avertissement")
        logger.error("Erreur")

    def test_specialized_logging(self):
        """Test des logs spécialisés"""
        # Test téléchargement de modèles
        log_model_download("test_model", "start")
        log_model_download("test_model", "progress", "50%")
        log_model_download("test_model", "success", "Terminé")
        log_model_download("test_model", "error", "Échec")

        # Test génération cinemagraph
        log_cinemagraph_generation("test.jpg", "start")
        log_cinemagraph_generation("test.jpg", "success", "output.mp4")

        # Test API
        log_api_request("/test", "GET", 200, 0.123)
        log_api_request("/error", "POST", 500, 1.234)

    def test_multiple_modules(self):
        """Test avec plusieurs modules"""
        logger_web = get_logger("web_interface")
        logger_api = get_logger("api")
        logger_models = get_logger("models")

        logger_web.info("Test web")
        logger_api.info("Test API")
        logger_models.info("Test modèles")

    def test_log_files_creation(self):
        """Test que les fichiers de log sont créés"""
        # Configurer le logger
        setup_logger(level="DEBUG")

        # Générer quelques logs
        logger = get_logger("test_files")
        logger.info("Test de création de fichier")

        # Vérifier que le dossier logs existe
        logs_dir = Path("logs")
        assert logs_dir.exists(), "Le dossier logs n'a pas été créé"

        # Vérifier que le fichier principal existe
        main_log = logs_dir / "comfy_img_to_loop.log"
        assert main_log.exists(), "Le fichier de log principal n'a pas été créé"


def test_logger_integration():
    """Test d'intégration simple du logger"""
    configure_for_development()
    logger = get_logger("integration_test")

    logger.info("🧪 Test d'intégration du logger")
    logger.success("✅ Logger fonctionnel")


if __name__ == "__main__":
    # Exécution directe des tests pour validation rapide
    print("🧪 Exécution des tests du logger...")

    test_logger_integration()

    test_instance = TestComfyLogger()
    test_instance.test_basic_logging()
    test_instance.test_specialized_logging()
    test_instance.test_multiple_modules()
    test_instance.test_log_files_creation()

    print("✅ Tous les tests passés")
    print("📂 Vérifiez les logs dans: logs/")
