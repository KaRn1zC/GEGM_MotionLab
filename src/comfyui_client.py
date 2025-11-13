"""
Client ComfyUI pour Comfy_Img_to_Loop
Interface WebSocket pour la communication avec ComfyUI et gestion des workflows
"""

import json
import uuid
import asyncio
import websockets
import aiohttp
import io
import base64
from pathlib import Path
from typing import Dict, Any, Optional, List, Callable, Union
from dataclasses import dataclass
from datetime import datetime, timedelta

# Import du système de logging centralisé
from src.logger import get_logger

# Configuration du logger pour ce module
logger = get_logger("comfyui_client")


@dataclass
class ComfyUIConfig:
    """Configuration du client ComfyUI"""

    host: str = "127.0.0.1"
    port: int = 8188
    timeout: int = 300  # 5 minutes par défaut
    max_retries: int = 3
    retry_delay: float = 1.0
    websocket_timeout: int = 600  # 10 minutes pour les gros workflows

    @property
    def base_url(self) -> str:
        return f"http://{self.host}:{self.port}"

    @property
    def websocket_url(self) -> str:
        return f"ws://{self.host}:{self.port}/ws"


@dataclass
class WorkflowProgress:
    """État de progression d'un workflow"""

    workflow_id: str
    status: str = "pending"  # pending, running, completed, error
    progress: float = 0.0
    current_node: Optional[str] = None
    total_nodes: int = 0
    completed_nodes: int = 0
    start_time: Optional[datetime] = None
    end_time: Optional[datetime] = None
    error_message: Optional[str] = None

    @property
    def duration(self) -> Optional[timedelta]:
        if self.start_time and self.end_time:
            return self.end_time - self.start_time
        elif self.start_time:
            return datetime.now() - self.start_time
        return None


class ComfyUIError(Exception):
    """Exception personnalisée pour les erreurs ComfyUI"""

    def __init__(
        self, message: str, code: Optional[str] = None, details: Optional[Dict] = None
    ):
        super().__init__(message)
        self.code = code
        self.details = details or {}


class ComfyUIClient:
    """
    Client pour interfacer avec ComfyUI via WebSocket et HTTP
    Gère les workflows, le monitoring et la communication bidirectionnelle
    """

    def __init__(self, config: Optional[ComfyUIConfig] = None):
        self.config = config or ComfyUIConfig()
        self.websocket: Optional[websockets.WebSocketServerProtocol] = None
        self.session: Optional[aiohttp.ClientSession] = None
        self.client_id = str(uuid.uuid4())
        self.active_workflows: Dict[str, WorkflowProgress] = {}
        self.message_handlers: Dict[str, Callable] = {}
        self.is_connected = False
        self._monitoring_task: Optional[asyncio.Task] = None

        logger.info(f"Client ComfyUI initialisé - ID: {self.client_id}")
        logger.info(f"Configuration: {self.config.base_url}")

        # Gestionnaires de messages par défaut
        self._setup_default_handlers()

    def _setup_default_handlers(self):
        """Configure les gestionnaires de messages par défaut"""
        self.message_handlers.update(
            {
                "status": self._handle_status_message,
                "progress": self._handle_progress_message,
                "executing": self._handle_executing_message,
                "executed": self._handle_executed_message,
                "execution_error": self._handle_error_message,
                "execution_cached": self._handle_cached_message,
            }
        )

    async def connect(self) -> bool:
        """
        Établit la connexion WebSocket avec ComfyUI avec retry automatique

        Returns:
            bool: True si la connexion est établie avec succès
        """
        for attempt in range(1, self.config.max_retries + 1):
            try:
                logger.info(
                    f"Connexion à ComfyUI (tentative {attempt}/{self.config.max_retries}): {self.config.websocket_url}"
                )

                # Créer la session HTTP
                if not self.session:
                    self.session = aiohttp.ClientSession()

                # Test de connectivité HTTP d'abord
                await self._test_http_connection()

                # Connexion WebSocket avec timeout correct
                try:
                    self.websocket = await asyncio.wait_for(
                        websockets.connect(
                            f"{self.config.websocket_url}?clientId={self.client_id}",
                            open_timeout=30,  # Timeout d'ouverture de connexion
                            ping_timeout=20,  # Timeout pour les pings
                            close_timeout=10,  # Timeout pour la fermeture
                        ),
                        timeout=self.config.timeout,
                    )
                except asyncio.TimeoutError:
                    logger.error(
                        f"Timeout lors de la connexion WebSocket ({self.config.timeout}s)"
                    )
                    raise ComfyUIError(
                        f"Timeout de connexion après {self.config.timeout}s"
                    )

                self.is_connected = True
                logger.success(
                    f"✅ Connexion WebSocket établie avec ComfyUI (tentative {attempt})"
                )

                # Démarrer le monitoring des messages
                self._monitoring_task = asyncio.create_task(self._monitor_messages())

                return True

            except websockets.ConnectionClosed as e:
                logger.error(f"Connexion WebSocket fermée: {e}")
                self.is_connected = False
            except asyncio.TimeoutError:
                logger.error("Timeout lors de la connexion à ComfyUI")
            except ComfyUIError as e:
                logger.error(f"Erreur ComfyUI: {e}")
            except Exception as e:
                logger.error(f"Erreur lors de la connexion à ComfyUI: {e}")
                import traceback

                logger.error(traceback.format_exc())

            # Si ce n'est pas la dernière tentative, attendre avant de réessayer
            if attempt < self.config.max_retries:
                wait_time = self.config.retry_delay * attempt
                logger.info(f"Nouvelle tentative dans {wait_time}s...")
                await asyncio.sleep(wait_time)
            else:
                logger.error(
                    f"❌ Échec de connexion après {self.config.max_retries} tentatives"
                )

        return False

    async def _test_http_connection(self):
        """Test la connexion HTTP avec ComfyUI"""
        try:
            url = f"{self.config.base_url}/system_stats"
            async with self.session.get(url, timeout=5) as response:
                if response.status == 200:
                    stats = await response.json()
                    logger.info(
                        f"ComfyUI répond - RAM: {stats.get('system', {}).get('ram_used', 'N/A')}GB"
                    )
                else:
                    raise ComfyUIError(f"ComfyUI inaccessible (HTTP {response.status})")
        except asyncio.TimeoutError:
            raise ComfyUIError("Timeout de connexion à ComfyUI")
        except Exception as e:
            raise ComfyUIError(f"ComfyUI inaccessible: {e}")

    async def disconnect(self):
        """Ferme la connexion WebSocket et nettoie les ressources"""
        logger.info("Fermeture de la connexion ComfyUI")

        self.is_connected = False

        # Arrêter le monitoring
        if self._monitoring_task:
            self._monitoring_task.cancel()
            try:
                await self._monitoring_task
            except asyncio.CancelledError:
                pass

        # Fermer la WebSocket
        if self.websocket:
            await self.websocket.close()
            self.websocket = None

        # Fermer la session HTTP
        if self.session:
            await self.session.close()
            self.session = None

        logger.info("Connexion ComfyUI fermée")

    async def _monitor_messages(self):
        """Surveille les messages WebSocket en continu"""
        logger.info("Démarrage du monitoring des messages WebSocket")

        try:
            async for message in self.websocket:
                try:
                    data = json.loads(message)
                    message_type = data.get("type", "unknown")

                    logger.debug(f"Message reçu: {message_type}")

                    # Appeler le gestionnaire approprié
                    if message_type in self.message_handlers:
                        await self.message_handlers[message_type](data)
                    else:
                        logger.debug(f"Type de message non géré: {message_type}")

                except json.JSONDecodeError as e:
                    logger.error(f"Erreur de décodage JSON: {e}")
                except Exception as e:
                    logger.error(f"Erreur lors du traitement du message: {e}")

        except websockets.ConnectionClosed:
            logger.warning("Connexion WebSocket fermée côté serveur")
            self.is_connected = False
        except Exception as e:
            logger.error(f"Erreur dans le monitoring des messages: {e}")
            self.is_connected = False

    async def _handle_status_message(self, data: Dict[str, Any]):
        """Gère les messages de statut"""
        status_data = data.get("data", {})
        logger.debug(f"Statut ComfyUI: {status_data}")

    async def _handle_progress_message(self, data: Dict[str, Any]):
        """Gère les messages de progression"""
        progress_data = data.get("data", {})
        workflow_id = progress_data.get("prompt_id")

        if workflow_id and workflow_id in self.active_workflows:
            workflow = self.active_workflows[workflow_id]
            workflow.progress = progress_data.get("value", 0.0)
            workflow.current_node = progress_data.get("node")

            logger.info(
                f"Progression workflow {workflow_id[:8]}: {workflow.progress:.1%}"
            )

    async def _handle_executing_message(self, data: Dict[str, Any]):
        """Gère les messages d'exécution de nœud"""
        exec_data = data.get("data", {})
        workflow_id = exec_data.get("prompt_id")
        node_id = exec_data.get("node")

        if workflow_id and workflow_id in self.active_workflows:
            workflow = self.active_workflows[workflow_id]
            workflow.current_node = node_id
            workflow.status = "running"

            if not workflow.start_time:
                workflow.start_time = datetime.now()

            logger.info(f"Exécution nœud {node_id} pour workflow {workflow_id[:8]}")

    async def _handle_executed_message(self, data: Dict[str, Any]):
        """Gère les messages de nœud exécuté"""
        exec_data = data.get("data", {})
        workflow_id = exec_data.get("prompt_id")

        if workflow_id and workflow_id in self.active_workflows:
            workflow = self.active_workflows[workflow_id]
            workflow.completed_nodes += 1

            # Calculer la progression basée sur les nœuds
            if workflow.total_nodes > 0:
                workflow.progress = workflow.completed_nodes / workflow.total_nodes

            logger.debug(
                f"Nœud terminé pour workflow {workflow_id[:8]} ({workflow.completed_nodes}/{workflow.total_nodes})"
            )

    async def _handle_error_message(self, data: Dict[str, Any]):
        """Gère les messages d'erreur"""
        error_data = data.get("data", {})
        workflow_id = error_data.get("prompt_id")
        error_message = error_data.get("exception_message", "Erreur inconnue")
        exception_type = error_data.get("exception_type", "Unknown")
        traceback_str = error_data.get("traceback", "")

        logger.error(
            f"❌ Erreur workflow {workflow_id[:8] if workflow_id else 'inconnu'}: {exception_type}"
        )
        logger.error(f"   Message: {error_message}")
        if traceback_str:
            logger.error(f"   Traceback: {traceback_str[:500]}")

        if workflow_id and workflow_id in self.active_workflows:
            workflow = self.active_workflows[workflow_id]
            workflow.status = "error"
            workflow.error_message = error_message
            workflow.end_time = datetime.now()

    async def _handle_cached_message(self, data: Dict[str, Any]):
        """Gère les messages de cache"""
        cache_data = data.get("data", {})
        workflow_id = cache_data.get("prompt_id")

        if workflow_id:
            logger.info(f"Nœuds en cache utilisés pour workflow {workflow_id[:8]}")

    async def queue_prompt(
        self, workflow: Dict[str, Any], images: Optional[Dict[str, Any]] = None
    ) -> str:
        """
        Met en file d'attente un workflow pour exécution

        Args:
            workflow: Définition du workflow ComfyUI
            images: Images à uploader (optionnel)

        Returns:
            str: ID du workflow mis en queue
        """
        if not self.is_connected:
            raise ComfyUIError("Client non connecté à ComfyUI")

        try:
            # Uploader les images si nécessaire
            if images:
                for name, image_data in images.items():
                    await self._upload_image(name, image_data)

            # Préparer la requête
            prompt_data = {"client_id": self.client_id, "prompt": workflow}

            # Envoyer la requête
            url = f"{self.config.base_url}/prompt"
            async with self.session.post(url, json=prompt_data) as response:
                if response.status == 200:
                    result = await response.json()
                    workflow_id = result.get("prompt_id")

                    # Enregistrer le workflow
                    self.active_workflows[workflow_id] = WorkflowProgress(
                        workflow_id=workflow_id,
                        status="pending",
                        total_nodes=len(workflow),
                    )

                    logger.success(f"✅ Workflow {workflow_id[:8]} mis en queue")
                    return workflow_id
                else:
                    error_text = await response.text()
                    raise ComfyUIError(
                        f"Erreur lors de la mise en queue (HTTP {response.status}): {error_text}"
                    )

        except Exception as e:
            logger.error(f"Erreur lors de la mise en queue du workflow: {e}")
            raise ComfyUIError(f"Échec de la mise en queue: {e}")

    async def _upload_image(self, name: str, image_data: Union[bytes, str, Path]):
        """Upload une image vers ComfyUI"""
        try:
            if isinstance(image_data, Path):
                with open(image_data, "rb") as f:
                    image_bytes = f.read()
            elif isinstance(image_data, str):
                # Assume base64 encoded
                image_bytes = base64.b64decode(image_data)
            else:
                image_bytes = image_data

            # Préparer les données multipart
            data = aiohttp.FormData()
            data.add_field("image", io.BytesIO(image_bytes), filename=name)

            url = f"{self.config.base_url}/upload/image"
            async with self.session.post(url, data=data) as response:
                if response.status == 200:
                    result = await response.json()
                    logger.info(f"Image {name} uploadée: {result.get('name')}")
                else:
                    raise ComfyUIError(
                        f"Erreur upload image {name} (HTTP {response.status})"
                    )

        except Exception as e:
            logger.error(f"Erreur lors de l'upload de l'image {name}: {e}")
            raise

    async def wait_for_completion(
        self, workflow_id: str, timeout: Optional[int] = None
    ) -> WorkflowProgress:
        """
        Attend la completion d'un workflow

        Args:
            workflow_id: ID du workflow à surveiller
            timeout: Timeout en secondes (optionnel)

        Returns:
            WorkflowProgress: État final du workflow
        """
        if workflow_id not in self.active_workflows:
            raise ComfyUIError(f"Workflow {workflow_id} non trouvé")

        timeout = timeout or self.config.websocket_timeout
        start_time = datetime.now()

        logger.info(
            f"Attente de completion pour workflow {workflow_id[:8]} (timeout: {timeout}s)"
        )

        while True:
            workflow = self.active_workflows[workflow_id]

            # Vérifier les conditions de fin
            if workflow.status in ["completed", "error"]:
                logger.info(
                    f"Workflow {workflow_id[:8]} terminé avec statut: {workflow.status}"
                )
                return workflow

            # Vérifier le timeout
            elapsed = (datetime.now() - start_time).total_seconds()
            if elapsed > timeout:
                workflow.status = "timeout"
                workflow.error_message = f"Timeout après {timeout}s"
                logger.error(f"Timeout pour workflow {workflow_id[:8]}")
                raise ComfyUIError(f"Timeout workflow {workflow_id}")

            # Attendre un peu avant de revérifier
            await asyncio.sleep(1.0)

    async def get_output_images(self, workflow_id: str) -> List[Dict[str, Any]]:
        """
        Récupère les images de sortie d'un workflow terminé

        Args:
            workflow_id: ID du workflow

        Returns:
            List[Dict]: Liste des images de sortie
        """
        try:
            url = f"{self.config.base_url}/history/{workflow_id}"
            async with self.session.get(url) as response:
                if response.status == 200:
                    history = await response.json()

                    workflow_history = history.get(workflow_id, {})
                    outputs = workflow_history.get("outputs", {})

                    images = []
                    for node_id, node_outputs in outputs.items():
                        if "images" in node_outputs:
                            for image_info in node_outputs["images"]:
                                # Télécharger l'image
                                image_data = await self._download_image(
                                    image_info["filename"], image_info["subfolder"]
                                )

                                images.append(
                                    {
                                        "node_id": node_id,
                                        "filename": image_info["filename"],
                                        "data": image_data,
                                        "type": image_info.get("type", "output"),
                                    }
                                )

                    logger.info(
                        f"Récupéré {len(images)} images pour workflow {workflow_id[:8]}"
                    )
                    return images
                else:
                    raise ComfyUIError(
                        f"Erreur récupération historique (HTTP {response.status})"
                    )

        except Exception as e:
            logger.error(f"Erreur lors de la récupération des images: {e}")
            raise

    async def _download_image(self, filename: str, subfolder: str = "") -> bytes:
        """Télécharge une image depuis ComfyUI"""
        try:
            params = {"filename": filename, "subfolder": subfolder, "type": "output"}

            url = f"{self.config.base_url}/view"
            async with self.session.get(url, params=params) as response:
                if response.status == 200:
                    return await response.read()
                else:
                    raise ComfyUIError(
                        f"Erreur téléchargement image {filename} (HTTP {response.status})"
                    )

        except Exception as e:
            logger.error(f"Erreur téléchargement image {filename}: {e}")
            raise

    async def get_queue_status(self) -> Dict[str, Any]:
        """Récupère le statut de la file d'attente"""
        try:
            url = f"{self.config.base_url}/queue"
            async with self.session.get(url) as response:
                if response.status == 200:
                    queue_data = await response.json()
                    logger.debug(
                        f"File d'attente: {len(queue_data.get('queue_running', []))} en cours, {len(queue_data.get('queue_pending', []))} en attente"
                    )
                    return queue_data
                else:
                    raise ComfyUIError(
                        f"Erreur récupération file d'attente (HTTP {response.status})"
                    )
        except Exception as e:
            logger.error(f"Erreur récupération file d'attente: {e}")
            raise

    async def interrupt_execution(self) -> bool:
        """Interrompt l'exécution en cours"""
        try:
            url = f"{self.config.base_url}/interrupt"
            async with self.session.post(url) as response:
                if response.status == 200:
                    logger.warning("Exécution interrompue")
                    return True
                else:
                    logger.error(f"Erreur interruption (HTTP {response.status})")
                    return False
        except Exception as e:
            logger.error(f"Erreur lors de l'interruption: {e}")
            return False

    def get_workflow_progress(self, workflow_id: str) -> Optional[WorkflowProgress]:
        """Récupère l'état de progression d'un workflow"""
        return self.active_workflows.get(workflow_id)

    def list_active_workflows(self) -> List[WorkflowProgress]:
        """Liste tous les workflows actifs"""
        return list(self.active_workflows.values())


# Gestionnaire de contexte pour faciliter l'utilisation
class ComfyUISession:
    """Gestionnaire de contexte pour les sessions ComfyUI"""

    def __init__(self, config: Optional[ComfyUIConfig] = None):
        self.client = ComfyUIClient(config)

    async def __aenter__(self):
        connected = await self.client.connect()
        if not connected:
            raise ComfyUIError(
                "Impossible de se connecter à ComfyUI. "
                "Vérifiez que ComfyUI est démarré et accessible sur "
                f"{self.client.config.base_url}"
            )
        return self.client

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        await self.client.disconnect()


# Fonctions utilitaires
async def test_comfyui_connection(config: Optional[ComfyUIConfig] = None) -> bool:
    """
    Test rapide de connexion à ComfyUI

    Args:
        config: Configuration ComfyUI

    Returns:
        bool: True si ComfyUI est accessible
    """
    try:
        async with ComfyUISession(config) as client:
            queue_status = await client.get_queue_status()
            logger.success(
                f"✅ ComfyUI accessible - Queue: {len(queue_status.get('queue_pending', []))} en attente"
            )
            return True
    except Exception as e:
        logger.error(f"❌ ComfyUI inaccessible: {e}")
        return False


# Fonction pour créer un workflow WAN 2.2 de base
def create_wan22_workflow(
    input_image: str,
    prompt: str = "",
    steps: int = 20,
    cfg_scale: float = 7.5,
    seed: Optional[int] = None,
) -> Dict[str, Any]:
    """
    Crée un workflow WAN 2.2 pour la génération image-to-video

    Args:
        input_image: Nom du fichier image d'entrée
        prompt: Prompt textuel (optionnel)
        steps: Nombre de steps de dénoising
        cfg_scale: Échelle de guidance
        seed: Seed pour la génération (aléatoire si None)

    Returns:
        Dict: Workflow ComfyUI pour WAN 2.2
    """
    if seed is None:
        import random

        seed = random.randint(0, 2**32 - 1)

    workflow = {
        "1": {"class_type": "LoadImage", "inputs": {"image": input_image}},
        "2": {
            "class_type": "WAN22_DiffusionModelLoader",
            "inputs": {
                "model_path": "models/wan2.2-i2v-a14b/high_noise_model/diffusion_pytorch_model-00001-of-00006.safetensors"
            },
        },
        "3": {
            "class_type": "WAN22_VAELoader",
            "inputs": {"vae_path": "models/wan2.2-i2v-a14b/Wan2.1_VAE.pth"},
        },
        "4": {
            "class_type": "WAN22_TextEncoder",
            "inputs": {
                "text_encoder_path": "models/wan2.2-i2v-a14b/models_t5_umt5-xxl-enc-bf16.pth",
                "prompt": prompt,
            },
        },
        "5": {
            "class_type": "WAN22_I2V_Sampler",
            "inputs": {
                "model": ["2", 0],
                "vae": ["3", 0],
                "text_encoder": ["4", 0],
                "image": ["1", 0],
                "steps": steps,
                "cfg_scale": cfg_scale,
                "seed": seed,
                "frames": 16,
                "fps": 8,
            },
        },
        "6": {
            "class_type": "SaveVideo",
            "inputs": {"video": ["5", 0], "filename_prefix": "wan22_cinemagraph"},
        },
    }

    logger.info(
        f"Workflow WAN 2.2 créé - Image: {input_image}, Steps: {steps}, Seed: {seed}"
    )
    return workflow


if __name__ == "__main__":
    # Test du client ComfyUI
    import asyncio

    async def test_client():
        """Test de base du client ComfyUI"""
        logger.info("🧪 Test du client ComfyUI")

        # Test de connexion
        is_accessible = await test_comfyui_connection()

        if is_accessible:
            logger.success("✅ Client ComfyUI opérationnel")
        else:
            logger.error("❌ ComfyUI non accessible")
            logger.info(
                "💡 Assurez-vous que ComfyUI est démarré avec: cd comfyui && python main.py"
            )

    asyncio.run(test_client())
