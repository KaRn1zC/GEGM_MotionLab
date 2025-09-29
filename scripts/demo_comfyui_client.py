#!/usr/bin/env python3
"""
Script de démonstration du client ComfyUI
Montre comment utiliser le client pour générer des cinemagraphs
"""

import sys
import asyncio
from pathlib import Path

# Ajouter le projet au path
sys.path.append(str(Path(__file__).parent.parent))

from src.logger import get_logger, setup_logger
from src.comfyui_client import ComfyUISession, ComfyUIConfig, test_comfyui_connection
from workflows.workflow_manager import workflow_manager

# Configuration du logger
setup_logger(level="INFO")
logger = get_logger("demo_comfyui")


async def demo_connection_test():
    """Démo du test de connexion"""
    logger.info("🔍 Test de connexion à ComfyUI...")

    config = ComfyUIConfig()
    is_connected = await test_comfyui_connection(config)

    if is_connected:
        logger.success("✅ ComfyUI accessible et opérationnel")
        return True
    else:
        logger.error("❌ ComfyUI non accessible")
        logger.info("💡 Assurez-vous que ComfyUI est démarré:")
        logger.info("   cd comfyui && python main.py --listen 0.0.0.0 --port 8188")
        return False


async def demo_workflow_creation():
    """Démo de création de workflow"""
    logger.info("🎬 Démonstration création de workflow...")

    # Lister les templates disponibles
    templates = workflow_manager.list_templates()
    logger.info(f"Templates disponibles: {len(templates)}")

    for template in templates:
        logger.info(f"  📋 {template['id']}: {template['name']}")

    # Utiliser le template WAN 2.2 si disponible
    if any(t["id"] == "wan22_i2v" for t in templates):
        logger.info("🎨 Création d'un workflow WAN 2.2 d'exemple...")

        # Paramètres d'exemple
        params = {
            "input_image": "example_input.jpg",
            "prompt": "gentle water ripples, subtle animation",
            "steps": 20,
            "cfg_scale": 7.5,
            "frames": 16,
            "fps": 8,
            "noise_level": "high",
        }

        try:
            workflow = workflow_manager.create_workflow("wan22_i2v", params)
            logger.success(f"✅ Workflow créé avec {len(workflow)} nœuds")

            # Afficher quelques détails du workflow
            for node_id, node in list(workflow.items())[:3]:
                logger.info(f"   Nœud {node_id}: {node['class_type']}")

            return workflow

        except Exception as e:
            logger.error(f"❌ Erreur création workflow: {e}")
            return None
    else:
        logger.warning("Template wan22_i2v non trouvé")
        return None


async def demo_full_workflow(workflow):
    """Démo d'exécution complète d'un workflow (simulation)"""
    if not workflow:
        logger.warning("Pas de workflow à exécuter")
        return

    logger.info("🚀 Simulation d'exécution de workflow...")

    try:
        # Configuration ComfyUI
        config = ComfyUIConfig()

        async with ComfyUISession(config) as client:
            logger.info("📡 Connexion établie avec ComfyUI")

            # Obtenir le statut de la file d'attente
            queue_status = await client.get_queue_status()
            pending = len(queue_status.get("queue_pending", []))
            running = len(queue_status.get("queue_running", []))

            logger.info(f"File d'attente: {running} en cours, {pending} en attente")

            # NOTE: Ici on ne lance pas vraiment le workflow car on n'a pas d'image d'entrée
            # Dans un vrai cas d'usage, on ferait :
            # workflow_id = await client.queue_prompt(workflow)
            # result = await client.wait_for_completion(workflow_id)
            # images = await client.get_output_images(workflow_id)

            logger.success("✅ Démonstration terminée")
            logger.info("💡 Pour une exécution réelle:")
            logger.info("   1. Placez une image dans comfyui/input/")
            logger.info("   2. Modifiez le paramètre input_image")
            logger.info("   3. Lancez client.queue_prompt(workflow)")

    except Exception as e:
        logger.error(f"❌ Erreur lors de la démonstration: {e}")


async def main():
    """Fonction principale de démonstration"""
    logger.info("🎬 Démonstration du Client ComfyUI - Comfy_Img_to_Loop")
    logger.info("=" * 60)

    # 1. Test de connexion
    if not await demo_connection_test():
        logger.error("Impossible de continuer sans ComfyUI")
        return

    logger.info("")

    # 2. Création de workflow
    workflow = await demo_workflow_creation()

    logger.info("")

    # 3. Simulation d'exécution
    await demo_full_workflow(workflow)

    logger.info("")
    logger.success("🎉 Démonstration terminée avec succès")
    logger.info("📚 Le client ComfyUI est prêt pour l'intégration")


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.warning("Démonstration interrompue par l'utilisateur")
    except Exception as e:
        logger.error(f"Erreur inattendue: {e}")
