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
        self.metadata = template_data.get("metadata", {})

        logger.debug(f"Template chargé: {self.name} v{self.version}")

    def _detect_available_model(self) -> tuple[str, str]:
        """
        Détecte automatiquement quel modèle WAN 2.2 est disponible

        Returns:
            tuple: (model_name, model_type) où model_type = "5b" ou "14b"
        """
        import os

        # WanVideoModelLoader cherche dans diffusion_models
        comfyui_models_dir = Path("/workspace/comfyui/ComfyUI/models/diffusion_models")

        # Fallback si diffusion_models n'existe pas
        if not comfyui_models_dir.exists():
            comfyui_models_dir = Path("/workspace/comfyui/ComfyUI/models/checkpoints")

        # Priorité : 14B > 5B
        model_priority = [
            ("wan2.2-i2v-a14b", "14b"),
            ("wan2.2-ti2v-5b", "5b"),
        ]

        for model_name, model_type in model_priority:
            model_path = comfyui_models_dir / model_name
            if model_path.exists() and any(model_path.glob("*.safetensors")):
                logger.info(f"✅ Modèle détecté: {model_name} (type: {model_type})")
                return model_name, model_type

        # Fallback: Variable d'environnement
        env_model = os.getenv("OWNCLOUD_MODEL_NAME", "wan2.2-ti2v-5b")
        model_type = (
            "14b" if "14b" in env_model.lower() or "a14b" in env_model.lower() else "5b"
        )
        logger.warning(
            f"⚠️ Aucun modèle trouvé, utilisation variable env: {env_model} (type: {model_type})"
        )
        return env_model, model_type

    def _get_model_checkpoint_path(self, model_name: str) -> str:
        """
        Retourne le chemin du checkpoint selon le type de modèle

        Args:
            model_name: Nom du dossier (wan2.2-ti2v-5b ou wan2.2-i2v-a14b)

        Returns:
            str: Chemin du fichier checkpoint principal
        """

        # Chemins possibles des modèles
        comfyui_models_dir = Path("comfyui/ComfyUI/models/checkpoints")

        # Variante 1: Environnement RunPod
        if not comfyui_models_dir.exists():
            comfyui_models_dir = Path("/workspace/comfyui/ComfyUI/models/checkpoints")

        # Variante 2: Local
        if not comfyui_models_dir.exists():
            comfyui_models_dir = Path("../comfyui/ComfyUI/models/checkpoints")

        # DEBUG: Lister TOUS les dossiers dans checkpoints/
        if comfyui_models_dir.exists():
            all_dirs = [d for d in comfyui_models_dir.iterdir() if d.is_dir()]
            logger.warning(f"🔍 DEBUG - Dossiers dans {comfyui_models_dir}:")
            for d in all_dirs:
                logger.warning(f"   - {d.name}/")
        else:
            logger.error(f"❌ Le dossier {comfyui_models_dir} n'existe pas!")

        model_path = comfyui_models_dir / model_name

        # Détection automatique selon la structure des fichiers (ComfyUI Native)
        if "5b" in model_name.lower():
            # Modèle 5B : chercher le fichier ComfyUI Native (Comfy-Org)
            comfyui_native_checkpoint = model_path / "wan2.2_ti2v_5B_fp16.safetensors"
            if comfyui_native_checkpoint.exists():
                logger.info(
                    f"✅ Modèle 5B ComfyUI Native détecté : {comfyui_native_checkpoint.name}"
                )
                return f"{model_name}/{comfyui_native_checkpoint.name}"

            # Fallback : ancien format fusionné (v3.1.8)
            merged_checkpoint = model_path / "diffusion_pytorch_model.safetensors"
            if merged_checkpoint.exists():
                logger.warning(
                    f"⚠️  Ancien format fusionné détecté : {merged_checkpoint.name}"
                )
                logger.warning(
                    "   Recommandation : re-télécharger depuis Comfy-Org avec setup_wan22_native.sh"
                )
                return f"{model_name}/{merged_checkpoint.name}"

            # Fallback : si fichiers sharded encore présents (très ancienne version)
            checkpoint_files = list(
                model_path.glob("diffusion_pytorch_model-*.safetensors")
            )
            if checkpoint_files:
                first_checkpoint = sorted(checkpoint_files)[0]
                logger.warning(
                    f"⚠️  Fichiers sharded détectés (obsolète) : {first_checkpoint.name}"
                )
                logger.warning(
                    "   Recommandation : re-télécharger depuis Comfy-Org avec setup_wan22_native.sh"
                )
                return f"{model_name}/{first_checkpoint.name}"

        elif "14b" in model_name.lower() or "a14b" in model_name.lower():
            # Modèle 14B : chercher les fichiers ComfyUI Native FP16 (Comfy-Org)
            comfyui_native_high = (
                model_path / "wan2.2_i2v_high_noise_14B_fp16.safetensors"
            )

            # DEBUG: Lister TOUS les fichiers dans le dossier du modèle
            if model_path.exists():
                all_files = list(model_path.glob("*.safetensors"))
                logger.warning(f"🔍 DEBUG - Fichiers dans {model_path}:")
                for f in all_files:
                    logger.warning(
                        f"   - {f.name} ({f.stat().st_size / 1024**3:.2f} GB)"
                    )
            else:
                logger.error(f"❌ Le dossier {model_path} n'existe pas!")

            if comfyui_native_high.exists():
                checkpoint_path = f"{model_name}/{comfyui_native_high.name}"
                logger.info(
                    f"✅ Modèle 14B ComfyUI Native FP16 détecté : {comfyui_native_high.name}"
                )
                logger.warning(
                    f"🔍 DEBUG - Checkpoint path retourné: {checkpoint_path}"
                )
                logger.warning(
                    f"🔍 DEBUG - Chemin absolu: {comfyui_native_high.absolute()}"
                )
                return checkpoint_path

            # Fallback : ancien format fusionné (v3.1.8)
            merged_checkpoint = model_path / "diffusion_pytorch_model.safetensors"
            if merged_checkpoint.exists():
                logger.warning(
                    f"⚠️  Ancien format fusionné détecté : {merged_checkpoint.name}"
                )
                logger.warning(
                    "   Recommandation : re-télécharger depuis Comfy-Org avec setup_wan22_native.sh"
                )
                return f"{model_name}/{merged_checkpoint.name}"

            # Fallback : très ancienne architecture MoE
            checkpoint_file = model_path / "high_noise_model.safetensors"
            if checkpoint_file.exists():
                logger.warning("⚠️ Ancienne architecture MoE détectée")
                logger.warning(
                    "   Recommandation : re-télécharger depuis Comfy-Org avec setup_wan22_native.sh"
                )
                return f"{model_name}/high_noise_model.safetensors"

        # Fallback : retourner le premier safetensors trouvé
        all_checkpoints = list(model_path.glob("*.safetensors"))
        if all_checkpoints:
            fallback_checkpoint = sorted(all_checkpoints)[0]
            logger.warning(
                f"⚠️ Utilisation du fallback checkpoint: {fallback_checkpoint.name}"
            )
            return f"{model_name}/{fallback_checkpoint.name}"

        # Dernier fallback
        logger.error("❌ Aucun checkpoint trouvé !")
        return f"{model_name}/model.safetensors"

    def _generate_random_seed(self) -> int:
        """Génère un seed aléatoire valide (>= 0)"""
        import random

        return random.randint(0, 2**31 - 1)

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

        # Détecter et injecter le modèle automatiquement
        if "model_name" not in validated_params:
            detected_model, model_type = self._detect_available_model()
            validated_params["model_name"] = detected_model
            validated_params["model_type"] = model_type
            logger.info(
                f"🤖 Modèle auto-détecté: {detected_model} (type: {model_type})"
            )

        # Injecter le bon nom de VAE selon le modèle
        if validated_params.get("model_type") == "14b":
            validated_params["vae_name"] = "wan_2.1_vae.safetensors"
            logger.info("📦 VAE 14B: wan_2.1_vae.safetensors (254 MB - VAE 2.1)")
        else:
            validated_params["vae_name"] = "wan2.2_vae.safetensors"
            logger.info("📦 VAE 5B: wan2.2_vae.safetensors (1.41 GB - VAE 2.2)")

        # Construire le chemin de checkpoint adapté au modèle
        checkpoint_path = self._get_model_checkpoint_path(detected_model)
        validated_params["checkpoint_path"] = checkpoint_path
        logger.info(f"📁 Chemin checkpoint: {checkpoint_path}")

        # Remplacer seed=-1 par un seed aléatoire
        if "seed" in validated_params and validated_params["seed"] == -1:
            validated_params["seed"] = self._generate_random_seed()
            logger.info(f"🎲 Seed aléatoire généré: {validated_params['seed']}")

        # Cloner le workflow pour éviter les modifications
        workflow = copy.deepcopy(self.workflow)

        # Remplacer les placeholders EN GARDANT LES TYPES
        workflow = self._substitute_params_recursive(workflow, validated_params)

        # Remplacements spéciaux
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        workflow = self._substitute_params_recursive(workflow, {"timestamp": timestamp})

        logger.info(
            f"Workflow {self.name} préparé avec {len(validated_params)} paramètres"
        )
        return workflow

    def _substitute_params_recursive(self, obj: Any, params: Dict[str, Any]) -> Any:
        """
        Substitue les paramètres de manière récursive EN GARDANT LES TYPES
        Args:
            obj: Objet à traiter
            params: Paramètres de substitution
        Returns:
            Objet avec paramètres substitués
        """
        if isinstance(obj, dict):
            return {
                k: self._substitute_params_recursive(v, params) for k, v in obj.items()
            }
        elif isinstance(obj, list):
            return [self._substitute_params_recursive(item, params) for item in obj]
        elif isinstance(obj, str):
            # Si c'est EXACTEMENT un placeholder complet, retourner avec le type original
            for param_name, param_value in params.items():
                placeholder = f"{{{param_name}}}"
                if obj == placeholder:
                    # Retourner le type original (int, float, etc.)
                    return param_value

            # Sinon, c'est une substitution partielle dans une string
            result = obj
            for param_name, param_value in params.items():
                placeholder = f"{{{param_name}}}"
                if placeholder in result:
                    # Vérifier si c'est la SEULE valeur
                    if result == placeholder:
                        return param_value
                    # Sinon remplacer dans la string
                    result = result.replace(placeholder, str(param_value))
            return result
        else:
            return obj

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

    def validate_workflow(self, workflow_id: str) -> Dict[str, Any]:
        """
        Valide un workflow et retourne un rapport

        Args:
            workflow_id: ID du workflow à valider

        Returns:
            Dict: Rapport de validation
        """
        template = self.get_template(workflow_id)

        if not template:
            return {"valid": False, "errors": [f"Template {workflow_id} non trouvé"]}

        report = {
            "valid": True,
            "warnings": [],
            "errors": [],
            "info": {
                "name": template.name,
                "version": template.version,
                "node_count": len(template.workflow),
                "parameter_count": len(template.parameters),
            },
        }

        # Vérifier les nœuds
        for node_id, node in template.workflow.items():
            if "class_type" not in node:
                report["errors"].append(f"Nœud {node_id}: class_type manquant")
                report["valid"] = False

            if "inputs" not in node:
                report["warnings"].append(f"Nœud {node_id}: aucun input défini")

        # Vérifier les paramètres
        for param_name, param_config in template.parameters.items():
            if "type" not in param_config:
                report["errors"].append(f"Paramètre {param_name}: type manquant")
                report["valid"] = False

        return report

    def get_workflow_info(self, workflow_id: str) -> Optional[Dict[str, Any]]:
        """
        Retourne les informations détaillées d'un workflow

        Args:
            workflow_id: ID du workflow

        Returns:
            Dict: Informations du workflow
        """
        template = self.get_template(workflow_id)

        if not template:
            return None

        return {
            "id": workflow_id,
            "name": template.name,
            "description": template.description,
            "version": template.version,
            "parameters": {
                name: {
                    "type": config.get("type"),
                    "default": config.get("default"),
                    "required": config.get("required", False),
                    "description": config.get("description", ""),
                    "min": config.get("min"),
                    "max": config.get("max"),
                    "enum": config.get("enum"),
                }
                for name, config in template.parameters.items()
            },
            "metadata": template.metadata,
            "node_count": len(template.workflow),
            "tags": template.metadata.get("tags", []),
        }

    def list_workflows_by_tag(self, tag: str) -> List[Dict[str, str]]:
        """
        Liste les workflows par tag

        Args:
            tag: Tag à filtrer

        Returns:
            List: Workflows correspondants
        """
        workflows = []

        for workflow_id, template in self.templates.items():
            tags = template.metadata.get("tags", [])
            if tag in tags:
                workflows.append(
                    {
                        "id": workflow_id,
                        "name": template.name,
                        "description": template.description,
                    }
                )

        return workflows

    def get_parameter_schema(self, workflow_id: str) -> Optional[Dict[str, Any]]:
        """
        Retourne le schéma JSON des paramètres d'un workflow

        Args:
            workflow_id: ID du workflow

        Returns:
            Dict: Schéma JSON des paramètres
        """
        template = self.get_template(workflow_id)

        if not template:
            return None

        schema = {"type": "object", "properties": {}, "required": []}

        for param_name, param_config in template.parameters.items():
            param_type = param_config.get("type", "string")

            # Mapper types Python vers JSON Schema
            type_mapping = {
                "string": "string",
                "integer": "integer",
                "float": "number",
                "boolean": "boolean",
            }

            json_type = type_mapping.get(param_type, "string")

            param_schema = {
                "type": json_type,
                "description": param_config.get("description", ""),
            }

            # Ajouter contraintes
            if "min" in param_config:
                param_schema["minimum"] = param_config["min"]
            if "max" in param_config:
                param_schema["maximum"] = param_config["max"]
            if "enum" in param_config:
                param_schema["enum"] = param_config["enum"]
            if "default" in param_config:
                param_schema["default"] = param_config["default"]

            schema["properties"][param_name] = param_schema

            # Ajouter aux required si nécessaire
            if param_config.get("required", False):
                schema["required"].append(param_name)

        return schema


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
