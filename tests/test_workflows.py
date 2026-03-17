"""
Tests unitaires pour les workflows
"""

import pytest


from workflows.workflow_manager import workflow_manager


class TestWorkflowValidation:
    """Tests de validation des workflows"""

    def test_wan22_5b_validation(self):
        """Test validation workflow WAN 2.2 5B"""
        validation = workflow_manager.validate_workflow("wan22_5b_i2v")
        assert validation["valid"] is True
        assert len(validation["errors"]) == 0

    def test_wan22_14b_validation(self):
        """Test validation workflow WAN 2.2 14B MoE"""
        validation = workflow_manager.validate_workflow("wan22_14b_i2v")
        assert validation["valid"] is True
        assert len(validation["errors"]) == 0

    def test_wan22_5b_upscale_validation(self):
        """Test validation workflow 5B + upscale"""
        validation = workflow_manager.validate_workflow("wan22_5b_with_upscale")
        assert validation["valid"] is True
        assert len(validation["errors"]) == 0

    def test_wan22_14b_upscale_validation(self):
        """Test validation workflow 14B + upscale"""
        validation = workflow_manager.validate_workflow("wan22_14b_with_upscale")
        assert validation["valid"] is True
        assert len(validation["errors"]) == 0


class TestWorkflowCreation:
    """Tests de création de workflows"""

    def test_create_wan22_5b_default(self):
        """Test création WAN 2.2 5B avec paramètres par défaut"""
        workflow = workflow_manager.create_workflow(
            "wan22_5b_i2v", {"input_image": "test.jpg"}
        )
        assert workflow is not None
        assert len(workflow) > 0

    def test_create_wan22_5b_custom(self):
        """Test création WAN 2.2 5B avec paramètres personnalisés"""
        workflow = workflow_manager.create_workflow(
            "wan22_5b_i2v",
            {
                "input_image": "test.jpg",
                "prompt": "test animation",
                "steps": 30,
                "cfg_scale": 9.0,
                # color_preservation=50 neutralise le modifier cfg (+0.0)
                "color_preservation": 50,
            },
        )
        assert workflow is not None
        # Node 8 = WanVideoSampler dans le template 5B
        assert workflow["8"]["inputs"]["steps"] == 30
        assert workflow["8"]["inputs"]["cfg"] == 9.0
        assert isinstance(workflow["8"]["inputs"]["steps"], int)
        assert isinstance(workflow["8"]["inputs"]["cfg"], float)

    def test_create_wan22_14b_default(self):
        """Test création WAN 2.2 14B MoE avec paramètres par défaut"""
        workflow = workflow_manager.create_workflow(
            "wan22_14b_i2v", {"input_image": "test.jpg"}
        )
        assert workflow is not None
        assert len(workflow) > 0


class TestWorkflowInfo:
    """Tests d'information sur les workflows"""

    def test_get_workflow_info_5b(self):
        """Test récupération infos workflow 5B"""
        info = workflow_manager.get_workflow_info("wan22_5b_i2v")
        assert info is not None
        assert info["name"] == "WAN 2.2 Image-to-Video"
        assert "parameters" in info
        assert "node_count" in info

    def test_get_workflow_info_14b(self):
        """Test récupération infos workflow 14B"""
        info = workflow_manager.get_workflow_info("wan22_14b_i2v")
        assert info is not None
        assert info["name"] == "WAN 2.2 14B Image-to-Video (MoE)"
        assert "parameters" in info
        assert "node_count" in info

    def test_get_parameter_schema(self):
        """Test récupération schéma paramètres"""
        schema = workflow_manager.get_parameter_schema("wan22_5b_i2v")
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
        assert any(wf["id"] == "wan22_5b_i2v" for wf in workflows)

    def test_list_by_tag_moe(self):
        """Test filtrage par tag 'moe'"""
        workflows = workflow_manager.list_workflows_by_tag("moe")
        assert len(workflows) > 0
        assert any(wf["id"] == "wan22_14b_i2v" for wf in workflows)


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
