"""
Script de test et validation des workflows ComfyUI
"""

import sys


from src.logger import get_logger, setup_logger
from workflows.workflow_manager import workflow_manager

setup_logger(level="INFO")
logger = get_logger("test_workflows")


def test_all_workflows():
    """Teste tous les workflows disponibles"""
    logger.info("🧪 Test de tous les workflows")
    logger.info("=" * 60)

    workflows = workflow_manager.list_templates()

    if not workflows:
        logger.error("❌ Aucun workflow trouvé")
        return False

    logger.info(f"📋 {len(workflows)} workflow(s) trouvé(s)")

    all_valid = True

    for workflow_info in workflows:
        workflow_id = workflow_info["id"]
        logger.info(f"\n🔍 Test du workflow: {workflow_id}")
        logger.info(f"   Nom: {workflow_info['name']}")
        logger.info(f"   Version: {workflow_info['version']}")

        # Valider le workflow
        validation = workflow_manager.validate_workflow(workflow_id)

        if validation["valid"]:
            logger.success("   ✅ Validation OK")
            logger.info(f"   Nœuds: {validation['info']['node_count']}")
            logger.info(f"   Paramètres: {validation['info']['parameter_count']}")

            if validation["warnings"]:
                for warning in validation["warnings"]:
                    logger.warning(f"   ⚠️  {warning}")
        else:
            logger.error("   ❌ Validation échouée")
            for error in validation["errors"]:
                logger.error(f"      - {error}")
            all_valid = False

        # Tester la création avec paramètres requis
        try:
            # Récupérer le template
            template = workflow_manager.get_template(workflow_id)

            # Vérifier que le template existe (fix Pylance warning)
            if not template:
                logger.error(f"   ❌ Template {workflow_id} non trouvé")
                all_valid = False
                continue

            # Construire les paramètres requis
            required_params = {}

            for param_name, param_config in template.parameters.items():
                if param_config.get("required", False):
                    # Fournir une valeur de test pour les paramètres requis
                    param_type = param_config.get("type", "string")
                    if param_type == "string":
                        required_params[param_name] = f"test_{param_name}.jpg"
                    elif param_type == "integer":
                        required_params[param_name] = 10
                    elif param_type == "float":
                        required_params[param_name] = 1.0

            workflow = workflow_manager.create_workflow(workflow_id, required_params)
            logger.success(f"   ✅ Création avec défauts OK ({len(workflow)} nœuds)")
        except Exception as e:
            logger.error(f"   ❌ Erreur création: {e}")
            all_valid = False

    return all_valid


def test_workflow_details():
    """Affiche les détails de chaque workflow"""
    logger.info("\n📊 Détails des workflows")
    logger.info("=" * 60)

    workflows = workflow_manager.list_templates()

    for workflow_info in workflows:
        workflow_id = workflow_info["id"]
        details = workflow_manager.get_workflow_info(workflow_id)

        if not details:
            logger.warning(f"⚠️  Impossible de récupérer les détails de {workflow_id}")
            continue

        logger.info(f"\n📄 {details['name']} (v{details['version']})")
        logger.info(f"   ID: {workflow_id}")
        logger.info(f"   Description: {details['description']}")
        logger.info(f"   Nœuds: {details['node_count']}")

        if details.get("tags"):
            logger.info(f"   Tags: {', '.join(details['tags'])}")

        logger.info("   Paramètres:")
        for param_name, param_info in details["parameters"].items():
            required = "requis" if param_info["required"] else "optionnel"
            default = (
                f"défaut={param_info['default']}"
                if param_info.get("default") is not None
                else ""
            )
            logger.info(
                f"      - {param_name} ({param_info['type']}, {required}) {default}"
            )
            if param_info.get("description"):
                logger.info(f"        {param_info['description']}")


def test_workflow_creation():
    """Teste la création de workflows avec différents paramètres"""
    logger.info("\n🔧 Test de création de workflows")
    logger.info("=" * 60)

    # Test WAN 2.2
    logger.info("\n📹 Test WAN 2.2 I2V")
    try:
        workflow = workflow_manager.create_workflow(
            "wan22_i2v",
            {
                "input_image": "test.jpg",
                "prompt": "gentle water movement",
                "steps": 25,
                "cfg_scale": 8.0,
                "frames": 20,
                "fps": 10,
            },
        )
        logger.success(f"   ✅ Workflow créé: {len(workflow)} nœuds")
    except Exception as e:
        logger.error(f"   ❌ Erreur: {e}")

    # Test Combined
    logger.info("\n🔗 Test WAN 2.2 + Upscale")
    try:
        workflow = workflow_manager.create_workflow(
            "wan22_with_upscale",
            {
                "input_image": "test.jpg",
                "prompt": "cinematic animation",
                "scale_factor": 2.0,
            },
        )
        logger.success(f"   ✅ Workflow créé: {len(workflow)} nœuds")
    except Exception as e:
        logger.error(f"   ❌ Erreur: {e}")


def test_tags():
    """Teste le filtrage par tags"""
    logger.info("\n🏷️  Test filtrage par tags")
    logger.info("=" * 60)

    tags = ["cinemagraph", "upscale", "pipeline"]

    for tag in tags:
        workflows = workflow_manager.list_workflows_by_tag(tag)
        logger.info(f"\n   Tag '{tag}': {len(workflows)} workflow(s)")
        for wf in workflows:
            logger.info(f"      - {wf['id']}: {wf['name']}")


def main():
    """Fonction principale"""
    logger.info("🎬 Test des workflows ComfyUI - Comfy_Img_to_Loop")

    # Tests
    all_valid = test_all_workflows()
    test_workflow_details()
    test_workflow_creation()
    test_tags()

    # Résumé
    logger.info("\n" + "=" * 60)
    if all_valid:
        logger.success("✅ Tous les tests sont passés")
        return 0
    else:
        logger.error("❌ Certains tests ont échoué")
        return 1


if __name__ == "__main__":
    sys.exit(main())
