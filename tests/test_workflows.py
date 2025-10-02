"""
Tests unitaires pour les workflows
"""

import sys
import pytest
from pathlib import Path

sys.path.append(str(Path(__file__).parent.parent))

from workflows.workflow_manager import workflow_manager


class TestWorkflowValidation:
    """Tests de validation des workflows"""

    def test_wan22_validation(self):
        """Test validation workflow WAN 2.2"""
        validation = workflow_manager.validate_workflow("wan22_i2v")
        assert validation["valid"] is True
        assert len(validation["errors"]) == 0

    def test_pyramid_validation(self):
        """Test validation workflow Pyramid"""
        validation = workflow_manager.validate_workflow("pyramid_upscale")
        assert validation["valid"] is True
        assert len(validation["errors"]) == 0

    def test_combined_validation(self):
        """Test validation workflow combiné"""
        validation = workflow_manager.validate_workflow("wan22_with_upscale")
        assert validation["valid"] is True
        assert len(validation["errors"]) == 0


class TestWorkflowCreation:
    """Tests de création de workflows"""

    def test_create_wan22_default(self):
        """Test création WAN 2.2 avec paramètres par défaut"""
        workflow = workflow_manager.create_workflow(
            "wan22_i2v", {"input_image": "test.jpg"}
        )
        assert workflow is not None
        assert len(workflow) > 0

    def test_create_wan22_custom(self):
        """Test création WAN 2.2 avec paramètres personnalisés"""
        workflow = workflow_manager.create_workflow(
            "wan22_i2v",
            {
                "input_image": "test.jpg",
                "prompt": "test animation",
                "steps": 30,
                "cfg_scale": 9.0,
            },
        )
        assert workflow is not None
        # Les valeurs doivent être des nombres, pas des strings
        assert workflow["6"]["inputs"]["steps"] == 30
        assert workflow["6"]["inputs"]["cfg"] == 9.0
        assert isinstance(workflow["6"]["inputs"]["steps"], int)
        assert isinstance(workflow["6"]["inputs"]["cfg"], float)

    def test_create_pyramid(self):
        """Test création Pyramid Upscale"""
        workflow = workflow_manager.create_workflow(
            "pyramid_upscale", {"input_video": "video.mp4", "scale_factor": 3.0}
        )
        assert workflow is not None
        assert len(workflow) > 0


class TestWorkflowInfo:
    """Tests d'information sur les workflows"""

    def test_get_workflow_info(self):
        """Test récupération infos workflow"""
        info = workflow_manager.get_workflow_info("wan22_i2v")
        assert info is not None
        assert info["name"] == "WAN 2.2 Image-to-Video"
        assert "parameters" in info
        assert "node_count" in info

    def test_get_parameter_schema(self):
        """Test récupération schéma paramètres"""
        schema = workflow_manager.get_parameter_schema("wan22_i2v")
        assert schema is not None
        assert schema["type"] == "object"
        assert "properties" in schema
        assert "input_image" in schema["properties"]


class TestWorkflowTags:
    """Tests de filtrage par tags"""

    def test_list_by_tag_cinemagraph(self):
        """Test filtrage par tag 'cinemagraph'"""
        workflows = workflow_manager.list_workflows_by_tag("cinemagraph")
        assert len(workflows) > 0
        assert any(wf["id"] == "wan22_i2v" for wf in workflows)

    def test_list_by_tag_upscale(self):
        """Test filtrage par tag 'upscale'"""
        workflows = workflow_manager.list_workflows_by_tag("upscale")
        assert len(workflows) > 0
        assert any(wf["id"] == "pyramid_upscale" for wf in workflows)


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
