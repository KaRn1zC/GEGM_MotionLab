"""
Gestionnaire de workflows pour ComfyUI
Charge et applique les templates de workflows avec paramètres
"""

import json
import sys
from pathlib import Path
from typing import Dict, Any, Optional, List
from datetime import datetime
import copy

# Ajouter le projet au path
sys.path.append(str(Path(__file__).parent.parent))

# Import du système de logging centralisé
from src.logger import get_logger

logger = get_logger("workflow_manager")


class WorkflowTemplate:
    """Représente un template de workflow avec ses paramètres"""

    def __init__(self, template_data: Dict[str, Any]):
        self.name = template_data.get("name", "Unknown")
        self.description = template_data.get("description", "")
        self.version = template_data.get("version", "1.0.0")
        self.parameters = template_data.get("parameters", {})
        self.workflow = template_data.get("workflow", {})

        logger.debug(f"Template chargé: {self.name} v{self.version}")

    def apply_parameters(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """
        Applique les paramètres au template et retourne le workflow final

        Args:
            params: Paramètres à appliquer

        Returns:
            Dict: Workflow ComfyUI prêt à l'emploi
        """
        # Valider les paramètres
        validated_params = self._validate_parameters(params)

        # Cloner le workflow pour éviter les modifications
        workflow = copy.deepcopy(self.workflow)

        # Remplacer les placeholders
        workflow_str = json.dumps(workflow)

        for param_name, param_value in validated_params.items():
            placeholder = f"{{{param_name}}}"
            if placeholder in workflow_str:
                workflow_str = workflow_str.replace(placeholder, str(param_value))

        # Remplacements spéciaux
        workflow_str = workflow_str.replace(
            "{timestamp}", datetime.now().strftime("%Y%m%d_%H%M%S")
        )

        final_workflow = json.loads(workflow_str)

        logger.info(
            f"Workflow {self.name} préparé avec {len(validated_params)} paramètres"
        )
        return final_workflow

    def _validate_parameters(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """Valide et normalise les paramètres selon les règles du template"""
        validated = {}

        for param_name, param_config in self.parameters.items():
            # Obtenir la valeur (fournie ou par défaut)
            if param_name in params:
                value = params[param_name]
            elif param_config.get("default") is not None:
                value = param_config["default"]
            elif param_config.get("required", False):
                raise ValueError(f"Paramètre requis manquant: {param_name}")
            else:
                continue

            # Validation selon le type
            param_type = param_config.get("type", "string")

            if param_type == "integer":
                value = int(value)
                min_val = param_config.get("min")
                max_val = param_config.get("max")
                if min_val is not None and value < min_val:
                    value = min_val
                if max_val is not None and value > max_val:
                    value = max_val

            elif param_type == "float":
                value = float(value)
                min_val = param_config.get("min")
                max_val = param_config.get("max")
                if min_val is not None and value < min_val:
                    value = min_val
                if max_val is not None and value > max_val:
                    value = max_val

            elif param_type == "string":
                value = str(value)
                enum_values = param_config.get("enum")
                if enum_values and value not in enum_values:
                    raise ValueError(
                        f"Valeur invalide pour {param_name}: {value}. Valeurs acceptées: {enum_values}"
                    )

            validated[param_name] = value

        logger.debug(f"Paramètres validés: {list(validated.keys())}")
        return validated


class WorkflowManager:
    """Gestionnaire central des templates et workflows"""

    def __init__(self, templates_dir: str = "workflows/templates"):
        self.templates_dir = Path(templates_dir)
        self.templates: Dict[str, WorkflowTemplate] = {}

        # Charger tous les templates au démarrage
        self.load_templates()

    def load_templates(self):
        """Charge tous les templates depuis le dossier templates"""
        if not self.templates_dir.exists():
            logger.warning(f"Dossier templates inexistant: {self.templates_dir}")
            return

        loaded_count = 0
        for template_file in self.templates_dir.glob("*.json"):
            try:
                with open(template_file, "r", encoding="utf-8") as f:
                    template_data = json.load(f)

                template = WorkflowTemplate(template_data)
                template_id = template_file.stem
                self.templates[template_id] = template
                loaded_count += 1

                logger.info(f"Template chargé: {template_id} - {template.name}")

            except Exception as e:
                logger.error(f"Erreur chargement template {template_file}: {e}")

        logger.info(f"✅ {loaded_count} templates chargés")

    def get_template(self, template_id: str) -> Optional[WorkflowTemplate]:
        """Récupère un template par son ID"""
        return self.templates.get(template_id)

    def list_templates(self) -> List[Dict[str, str]]:
        """Liste tous les templates disponibles"""
        return [
            {
                "id": template_id,
                "name": template.name,
                "description": template.description,
                "version": template.version,
            }
            for template_id, template in self.templates.items()
        ]

    def create_workflow(
        self, template_id: str, parameters: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Crée un workflow en appliquant les paramètres à un template

        Args:
            template_id: ID du template à utiliser
            parameters: Paramètres à appliquer

        Returns:
            Dict: Workflow ComfyUI prêt
        """
        template = self.get_template(template_id)
        if not template:
            raise ValueError(f"Template non trouvé: {template_id}")

        workflow = template.apply_parameters(parameters)
        logger.success(f"✅ Workflow créé depuis template {template_id}")

        return workflow

    def validate_template_parameters(
        self, template_id: str, parameters: Dict[str, Any]
    ) -> Dict[str, str]:
        """
        Valide les paramètres d'un template sans créer le workflow

        Returns:
            Dict: Rapport de validation {param_name: status}
        """
        template = self.get_template(template_id)
        if not template:
            raise ValueError(f"Template non trouvé: {template_id}")

        validation_report = {}

        for param_name, param_config in template.parameters.items():
            if param_name in parameters:
                try:
                    # Essayer la validation
                    template._validate_parameters({param_name: parameters[param_name]})
                    validation_report[param_name] = "valid"
                except Exception as e:
                    validation_report[param_name] = f"error: {str(e)}"
            elif param_config.get("required", False):
                validation_report[param_name] = "missing_required"
            else:
                validation_report[param_name] = "using_default"

        return validation_report


# Instance globale du gestionnaire
workflow_manager = WorkflowManager()

if __name__ == "__main__":
    # Test du gestionnaire de workflows
    from src.logger import setup_logger

    # Configurer le logger pour voir les outputs
    setup_logger(level="INFO")

    logger.info("🧪 Test du gestionnaire de workflows")

    # Lister les templates
    templates = workflow_manager.list_templates()
    logger.info(f"Templates disponibles: {len(templates)}")

    for template_info in templates:
        logger.info(f"  - {template_info['id']}: {template_info['name']}")

    # Test de création de workflow
    if templates:
        template_id = templates[0]["id"]
        test_params = {
            "input_image": "test.jpg",
            "prompt": "gentle water movement",
            "steps": 25,
        }

        try:
            workflow = workflow_manager.create_workflow(template_id, test_params)
            logger.success(f"✅ Workflow test créé avec {len(workflow)} nœuds")
        except Exception as e:
            logger.error(f"❌ Erreur création workflow: {e}")

    logger.info("Test terminé")
