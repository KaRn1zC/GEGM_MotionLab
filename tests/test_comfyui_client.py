"""
Tests pour le client ComfyUI
"""

import pytest


from src.comfyui_client import (
    ComfyUIClient,
    ComfyUIConfig,
    WorkflowProgress,
)
from workflows.workflow_manager import WorkflowManager, WorkflowTemplate


class TestComfyUIConfig:
    """Tests pour la configuration ComfyUI"""

    def test_default_config(self):
        """Test de la configuration par défaut"""
        config = ComfyUIConfig()

        assert config.host == "127.0.0.1"
        assert config.port == 8188
        assert config.timeout == 300
        assert config.base_url == "http://127.0.0.1:8188"
        assert config.websocket_url == "ws://127.0.0.1:8188/ws"

    def test_custom_config(self):
        """Test d'une configuration personnalisée"""
        config = ComfyUIConfig(host="192.168.1.100", port=8080, timeout=600)

        assert config.host == "192.168.1.100"
        assert config.port == 8080
        assert config.timeout == 600
        assert config.base_url == "http://192.168.1.100:8080"


class TestWorkflowProgress:
    """Tests pour le suivi de progression"""

    def test_workflow_progress_creation(self):
        """Test de création d'un WorkflowProgress"""
        progress = WorkflowProgress(workflow_id="test-123")

        assert progress.workflow_id == "test-123"
        assert progress.status == "pending"
        assert progress.progress == 0.0
        assert progress.duration is None

    def test_workflow_progress_duration(self):
        """Test du calcul de durée"""
        from datetime import datetime, timedelta

        progress = WorkflowProgress(workflow_id="test-123")
        progress.start_time = datetime.now() - timedelta(seconds=30)
        progress.end_time = datetime.now()

        duration = progress.duration
        assert duration is not None
        assert 25 <= duration.total_seconds() <= 35


class TestComfyUIClient:
    """Tests pour le client ComfyUI"""

    def test_client_initialization(self):
        """Test d'initialisation du client"""
        client = ComfyUIClient()

        assert client.config.host == "127.0.0.1"
        assert client.config.port == 8188
        assert not client.is_connected
        assert client.websocket is None
        assert len(client.client_id) > 0

    @pytest.mark.asyncio
    async def test_connection_failure(self):
        """Test de gestion des erreurs de connexion"""
        # Configuration avec un port inaccessible
        config = ComfyUIConfig(port=9999)
        client = ComfyUIClient(config)

        # La connexion devrait échouer
        result = await client.connect()
        assert result is False
        assert not client.is_connected

        # Nettoyer la session pour éviter le warning
        if client.session:
            await client.session.close()


class TestWorkflowManager:
    """Tests pour le gestionnaire de workflows"""

    def test_workflow_template_creation(self):
        """Test de création d'un template"""
        template_data = {
            "name": "Test Template",
            "description": "Template de test",
            "version": "1.0.0",
            "parameters": {
                "test_param": {"type": "string", "default": "default_value"}
            },
            "workflow": {
                "1": {"class_type": "TestNode", "inputs": {"value": "{test_param}"}}
            },
        }

        template = WorkflowTemplate(template_data)

        assert template.name == "Test Template"
        assert template.version == "1.0.0"
        assert "test_param" in template.parameters

    def test_template_parameter_application(self):
        """Test d'application des paramètres à un template"""
        template_data = {
            "name": "Test Template",
            "parameters": {
                "input_value": {"type": "string", "required": True},
                "optional_value": {"type": "integer", "default": 42},
            },
            "workflow": {
                "1": {
                    "class_type": "TestNode",
                    "inputs": {
                        "input": "{input_value}",
                        "optional": "{optional_value}",
                    },
                }
            },
        }

        template = WorkflowTemplate(template_data)

        # Test avec paramètres fournis
        params = {"input_value": "test_input", "optional_value": 100}
        workflow = template.apply_parameters(params)

        assert workflow["1"]["inputs"]["input"] == "test_input"
        assert workflow["1"]["inputs"]["optional"] == 100
        assert isinstance(workflow["1"]["inputs"]["optional"], int)

        # Test avec valeur par défaut
        params_minimal = {"input_value": "test_input"}
        workflow_minimal = template.apply_parameters(params_minimal)

        assert workflow_minimal["1"]["inputs"]["optional"] == 42
        assert isinstance(workflow_minimal["1"]["inputs"]["optional"], int)


def test_workflow_templates_loading():
    """Test de chargement des templates"""
    manager = WorkflowManager()

    templates = manager.list_templates()
    template_ids = [t["id"] for t in templates]

    # Les 4 templates doivent être chargés
    assert "wan22_5b_i2v" in template_ids
    assert "wan22_14b_i2v" in template_ids

    template = manager.get_template("wan22_5b_i2v")
    assert template is not None
    assert template.name == "WAN 2.2 Image-to-Video"


if __name__ == "__main__":
    print("🧪 Exécution des tests ComfyUI Client...")

    test_config = TestComfyUIConfig()
    test_config.test_default_config()
    test_config.test_custom_config()
    print("✅ Tests de configuration passés")

    test_progress = TestWorkflowProgress()
    test_progress.test_workflow_progress_creation()
    print("✅ Tests de progression passés")

    test_client = TestComfyUIClient()
    test_client.test_client_initialization()
    print("✅ Tests de client passés")

    test_workflow_templates_loading()
    print("✅ Tests de templates passés")

    print("🎉 Tous les tests sont passés !")
