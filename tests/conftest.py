"""
Configuration des tests pour Comfy_Img_to_Loop
"""

import pytest
import sys
from pathlib import Path

# Ajouter le projet au path pour tous les tests
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))


@pytest.fixture(scope="session", autouse=True)
def setup_test_environment():
    """Configuration globale pour tous les tests"""
    # Créer le dossier logs pour les tests si nécessaire
    logs_dir = project_root / "logs"
    logs_dir.mkdir(exist_ok=True)

    yield

    # Nettoyage après les tests si nécessaire
    # (optionnel - on peut garder les logs de test)
