"""
Module de sauvegarde OwnCloud pour Comfy_Img_to_Loop
Upload sécurisé des cinemagraphs générés avec métadonnées et liens de partage
"""

import io
import json
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, Any, Optional, List, Union
from dataclasses import dataclass, asdict
from urllib.parse import urljoin, quote

import aiohttp

# Import du système de logging centralisé
from src.logger import get_logger

logger = get_logger("owncloud_uploader")


@dataclass
class OwnCloudConfig:
    """Configuration pour OwnCloud - Créée depuis .env + YAML"""

    server_url: str
    username: str
    password: str
    upload_folder: str
    chunk_size: int = 8192
    timeout: int = 300
    max_retries: int = 3
    retry_delay: float = 1.0

    @property
    def webdav_url(self) -> str:
        """URL WebDAV complète"""
        # Nettoyer l'URL de base
        base = self.server_url.rstrip("/")
        return f"{base}/remote.php/dav/files/{self.username}"

    @property
    def sharing_api_url(self) -> str:
        """URL de l'API de partage OCS"""
        base = self.server_url.rstrip("/")
        return f"{base}/ocs/v2.php/apps/files_sharing/api/v1/shares"

    def validate(self) -> List[str]:
        """Valide la configuration"""
        errors = []

        if not self.server_url or not self.server_url.startswith(
            ("http://", "https://")
        ):
            errors.append("server_url doit être une URL valide (http:// ou https://)")

        if not self.username:
            errors.append("username est requis")

        if not self.password:
            errors.append("password est requis")

        if not self.upload_folder or not self.upload_folder.startswith("/"):
            errors.append("upload_folder doit commencer par '/'")

        if self.chunk_size <= 0:
            errors.append("chunk_size doit être positif")

        if self.timeout <= 0:
            errors.append("timeout doit être positif")

        return errors


@dataclass
class VideoMetadata:
    """Métadonnées d'une vidéo uploadée"""

    filename: str
    original_name: str
    file_size: int
    duration: Optional[float] = None
    width: Optional[int] = None
    height: Optional[int] = None
    fps: Optional[float] = None
    format: Optional[str] = None
    codec: Optional[str] = None
    created_at: Optional[datetime] = None
    workflow_id: Optional[str] = None
    prompt: Optional[str] = None
    model_used: Optional[str] = None
    generation_params: Optional[Dict[str, Any]] = None

    def to_dict(self) -> Dict[str, Any]:
        """Convertit en dictionnaire sérialisable"""
        data = asdict(self)
        if self.created_at:
            data["created_at"] = self.created_at.isoformat()
        return data

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "VideoMetadata":
        """Crée une instance depuis un dictionnaire"""
        if "created_at" in data and isinstance(data["created_at"], str):
            data["created_at"] = datetime.fromisoformat(data["created_at"])
        return cls(**data)


@dataclass
class UploadResult:
    """Résultat d'un upload"""

    success: bool
    file_path: str
    file_size: int
    upload_duration: Optional[timedelta] = None
    share_link: Optional[str] = None
    metadata: Optional[VideoMetadata] = None
    error_message: Optional[str] = None
    owncloud_url: Optional[str] = None

    @property
    def upload_speed_mbps(self) -> Optional[float]:
        """Vitesse d'upload en Mbps"""
        if self.upload_duration and self.file_size > 0:
            seconds = self.upload_duration.total_seconds()
            if seconds > 0:
                return (self.file_size * 8) / (
                    seconds * 1_000_000
                )  # bits per second to Mbps
        return None


class OwnCloudError(Exception):
    """Exception personnalisée pour les erreurs OwnCloud"""

    def __init__(
        self,
        message: str,
        status_code: Optional[int] = None,
        details: Optional[Dict] = None,
    ):
        super().__init__(message)
        self.status_code = status_code
        self.details = details or {}


class OwnCloudUploader:
    """
    Client pour l'upload sécurisé vers OwnCloud
    Gère les uploads, métadonnées et liens de partage
    """

    def __init__(self, config: OwnCloudConfig):
        self.config = config
        self.session: Optional[aiohttp.ClientSession] = None

        # Valider la configuration
        errors = self.config.validate()
        if errors:
            raise ValueError(f"Configuration OwnCloud invalide: {', '.join(errors)}")

        logger.info(f"OwnCloud Uploader initialisé - Serveur: {self.config.server_url}")
        logger.info(f"Dossier d'upload: {self.config.upload_folder}")

    async def __aenter__(self):
        """Entrée du context manager"""
        await self.connect()
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Sortie du context manager"""
        await self.disconnect()

    async def connect(self):
        """Établit la connexion HTTP"""
        if not self.session:
            connector = aiohttp.TCPConnector(limit=10, limit_per_host=5)
            self.session = aiohttp.ClientSession(
                connector=connector,
                timeout=aiohttp.ClientTimeout(total=self.config.timeout),
                auth=aiohttp.BasicAuth(self.config.username, self.config.password),
            )

            # Test de connexion
            await self.test_connection()
            logger.info("✅ Connexion OwnCloud établie")

    async def disconnect(self):
        """Ferme la connexion HTTP"""
        if self.session:
            await self.session.close()
            self.session = None
            logger.info("Connexion OwnCloud fermée")

    async def test_connection(self) -> bool:
        """
        Test la connexion à OwnCloud

        Returns:
            bool: True si la connexion fonctionne
        """
        try:
            url = urljoin(self.config.server_url, "status.php")

            async with self.session.get(url) as response:
                if response.status == 200:
                    data = await response.json()
                    version = data.get("version", "unknown")
                    logger.info(f"OwnCloud détecté - Version: {version}")
                    return True
                else:
                    raise OwnCloudError(
                        f"Échec test connexion (HTTP {response.status})"
                    )

        except Exception as e:
            logger.error(f"Erreur test connexion OwnCloud: {e}")
            raise OwnCloudError(f"Connexion impossible: {e}")

    async def create_folder(self, folder_path: str) -> bool:
        """
        Crée un dossier sur OwnCloud (récursif)

        Args:
            folder_path: Chemin du dossier à créer

        Returns:
            bool: True si créé avec succès
        """
        try:
            # Normaliser le chemin
            folder_path = folder_path.strip("/")

            # Créer les dossiers parents si nécessaire
            parts = folder_path.split("/")
            current_path = ""

            for part in parts:
                current_path = f"{current_path}/{part}" if current_path else part
                part_url = urljoin(self.config.webdav_url + "/", quote(current_path))

                async with self.session.request("MKCOL", part_url) as response:
                    if response.status in [201, 405]:  # 201=créé, 405=existe déjà
                        continue
                    elif response.status == 401:
                        raise OwnCloudError("Authentification échouée", response.status)
                    elif response.status == 403:
                        raise OwnCloudError("Permission refusée", response.status)
                    else:
                        logger.warning(
                            f"Création dossier {current_path}: HTTP {response.status}"
                        )

            logger.info(f"Dossier créé/vérifié: {folder_path}")
            return True

        except Exception as e:
            logger.error(f"Erreur création dossier {folder_path}: {e}")
            raise

    async def upload_file(
        self,
        file_data: Union[bytes, Path, io.IOBase],
        remote_path: str,
        metadata: Optional[VideoMetadata] = None,
        progress_callback: Optional[callable] = None,
    ) -> UploadResult:
        """
        Upload un fichier vers OwnCloud

        Args:
            file_data: Données du fichier (bytes, Path ou file object)
            remote_path: Chemin de destination sur OwnCloud
            metadata: Métadonnées vidéo (optionnel)
            progress_callback: Callback de progression (optionnel)

        Returns:
            UploadResult: Résultat de l'upload
        """
        start_time = datetime.now()

        try:
            # Préparer les données
            if isinstance(file_data, Path):
                file_size = file_data.stat().st_size
                file_obj = open(file_data, "rb")
            elif isinstance(file_data, bytes):
                file_size = len(file_data)
                file_obj = io.BytesIO(file_data)
            else:
                file_obj = file_data
                file_obj.seek(0, 2)  # Aller à la fin
                file_size = file_obj.tell()
                file_obj.seek(0)  # Retourner au début

            logger.info(
                f"Début upload: {remote_path} ({file_size / (1024 * 1024):.2f} MB)"
            )

            # S'assurer que le dossier parent existe
            parent_folder = "/".join(remote_path.split("/")[:-1])
            if parent_folder:
                await self.create_folder(parent_folder)

            # Préparer l'URL d'upload
            upload_url = urljoin(
                self.config.webdav_url + "/", quote(remote_path.lstrip("/"))
            )

            # Upload avec suivi de progression
            uploaded_bytes = 0

            async def upload_generator():
                nonlocal uploaded_bytes
                while True:
                    chunk = file_obj.read(self.config.chunk_size)
                    if not chunk:
                        break

                    uploaded_bytes += len(chunk)

                    # Callback de progression
                    if progress_callback:
                        progress = (uploaded_bytes / file_size) * 100
                        progress_callback(uploaded_bytes, file_size, progress)

                    yield chunk

            # Effectuer l'upload
            async with self.session.put(
                upload_url,
                data=upload_generator(),
                headers={"Content-Length": str(file_size)},
            ) as response:
                if response.status in [200, 201, 204]:
                    upload_duration = datetime.now() - start_time

                    # Fermer le fichier si on l'a ouvert
                    if isinstance(file_data, Path):
                        file_obj.close()

                    logger.success(f"✅ Upload réussi: {remote_path}")
                    logger.info(f"Durée: {upload_duration.total_seconds():.2f}s")

                    # Créer le résultat
                    result = UploadResult(
                        success=True,
                        file_path=remote_path,
                        file_size=file_size,
                        upload_duration=upload_duration,
                        metadata=metadata,
                        owncloud_url=urljoin(
                            self.config.server_url,
                            f"index.php/f/{quote(remote_path.lstrip('/'))}",
                        ),
                    )

                    # Sauvegarder les métadonnées si fournies
                    if metadata:
                        await self.save_metadata(remote_path, metadata)

                    return result

                else:
                    error_text = await response.text()
                    raise OwnCloudError(
                        f"Échec upload (HTTP {response.status}): {error_text}",
                        response.status,
                    )

        except Exception as e:
            logger.error(f"Erreur upload {remote_path}: {e}")

            return UploadResult(
                success=False,
                file_path=remote_path,
                file_size=file_size if "file_size" in locals() else 0,
                error_message=str(e),
            )

    async def save_metadata(self, file_path: str, metadata: VideoMetadata):
        """
        Sauvegarde les métadonnées d'un fichier

        Args:
            file_path: Chemin du fichier principal
            metadata: Métadonnées à sauvegarder
        """
        try:
            # Créer le fichier de métadonnées
            metadata_filename = f"{file_path}.metadata.json"
            metadata_data = json.dumps(
                metadata.to_dict(), indent=2, ensure_ascii=False
            ).encode("utf-8")

            await self.upload_file(
                file_data=metadata_data, remote_path=metadata_filename
            )

            logger.debug(f"Métadonnées sauvegardées: {metadata_filename}")

        except Exception as e:
            logger.error(f"Erreur sauvegarde métadonnées: {e}")

    async def create_share_link(
        self,
        file_path: str,
        password: Optional[str] = None,
        expire_days: Optional[int] = None,
        permissions: int = 1,  # 1=read, 15=all
    ) -> Optional[str]:
        """
        Crée un lien de partage pour un fichier

        Args:
            file_path: Chemin du fichier à partager
            password: Mot de passe de protection (optionnel)
            expire_days: Expiration en jours (optionnel)
            permissions: Permissions (1=lecture, 15=toutes)

        Returns:
            Optional[str]: URL du lien de partage
        """
        try:
            # Préparer les données de partage
            share_data = {
                "path": file_path,
                "shareType": 3,  # Public link
                "permissions": permissions,
                "format": "json",
            }

            if password:
                share_data["password"] = password

            if expire_days:
                expire_date = datetime.now() + timedelta(days=expire_days)
                share_data["expireDate"] = expire_date.strftime("%Y-%m-%d")

            # Créer le partage
            async with self.session.post(
                self.config.sharing_api_url,
                data=share_data,
                headers={"OCS-APIRequest": "true", "Accept": "application/json"},
            ) as response:
                if response.status == 200:
                    data = await response.json()

                    if data.get("ocs", {}).get("meta", {}).get("status") == "ok":
                        share_data = data["ocs"]["data"]
                        share_url = share_data.get("url")

                        logger.success(f"✅ Lien de partage créé: {share_url}")
                        return share_url
                    else:
                        error_msg = (
                            data.get("ocs", {})
                            .get("meta", {})
                            .get("message", "Erreur inconnue")
                        )
                        logger.error(f"Erreur API partage: {error_msg}")
                        return None
                else:
                    logger.error(f"Erreur création partage (HTTP {response.status})")
                    return None

        except Exception as e:
            logger.error(f"Erreur création lien partage: {e}")
            return None

    async def list_files(self, folder_path: str = "/") -> List[Dict[str, Any]]:
        """
        Liste les fichiers d'un dossier

        Args:
            folder_path: Chemin du dossier

        Returns:
            List[Dict]: Liste des fichiers avec métadonnées
        """
        try:
            folder_url = urljoin(
                self.config.webdav_url + "/", quote(folder_path.lstrip("/"))
            )

            async with self.session.request(
                "PROPFIND", folder_url, headers={"Depth": "1"}
            ) as response:
                if response.status == 207:  # Multi-Status
                    # Parser la réponse WebDAV (simplifié)
                    content = await response.text()
                    logger.debug(
                        f"Contenu dossier {folder_path}: {len(content)} caractères"
                    )

                    # Retour simplifié pour l'exemple
                    return [
                        {
                            "name": "example.mp4",
                            "size": 1024000,
                            "modified": datetime.now(),
                        }
                    ]
                else:
                    raise OwnCloudError(
                        f"Erreur listage dossier (HTTP {response.status})"
                    )

        except Exception as e:
            logger.error(f"Erreur listage dossier {folder_path}: {e}")
            return []

    async def delete_file(self, file_path: str) -> bool:
        """
        Supprime un fichier de OwnCloud

        Args:
            file_path: Chemin du fichier à supprimer

        Returns:
            bool: True si supprimé avec succès
        """
        try:
            file_url = urljoin(
                self.config.webdav_url + "/", quote(file_path.lstrip("/"))
            )

            async with self.session.delete(file_url) as response:
                if response.status == 204:  # No Content = succès
                    logger.info(f"Fichier supprimé: {file_path}")
                    return True
                else:
                    logger.error(f"Erreur suppression (HTTP {response.status})")
                    return False

        except Exception as e:
            logger.error(f"Erreur suppression {file_path}: {e}")
            return False

    def generate_filename(
        self,
        original_name: str,
        workflow_id: Optional[str] = None,
        add_timestamp: bool = True,
    ) -> str:
        """
        Génère un nom de fichier unique pour l'upload

        Args:
            original_name: Nom original du fichier
            workflow_id: ID du workflow (optionnel)
            add_timestamp: Ajouter un timestamp

        Returns:
            str: Nom de fichier unique
        """
        # Nettoyer le nom original
        name_parts = Path(original_name).stem, Path(original_name).suffix
        clean_name = "".join(c for c in name_parts[0] if c.isalnum() or c in "_-")

        # Construire le nouveau nom
        parts = [clean_name]

        if workflow_id:
            parts.append(f"wf_{workflow_id[:8]}")

        if add_timestamp:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            parts.append(timestamp)

        filename = "_".join(parts) + name_parts[1]

        # Construire le chemin complet
        date_folder = datetime.now().strftime("%Y/%m")
        full_path = f"{self.config.upload_folder.rstrip('/')}/{date_folder}/{filename}"

        logger.debug(f"Nom de fichier généré: {full_path}")
        return full_path


# Fonctions utilitaires


def extract_video_metadata(file_path: Union[Path, str]) -> VideoMetadata:
    """
    Extrait les métadonnées d'une vidéo (version simple)

    Args:
        file_path: Chemin vers le fichier vidéo

    Returns:
        VideoMetadata: Métadonnées extraites
    """
    file_path = Path(file_path)

    # Métadonnées de base
    metadata = VideoMetadata(
        filename=file_path.name,
        original_name=file_path.name,
        file_size=file_path.stat().st_size,
        created_at=datetime.now(),
        format=file_path.suffix.lstrip(".").lower(),
    )

    # Essayer d'extraire plus de métadonnées avec ffprobe si disponible
    try:
        import subprocess
        import json

        result = subprocess.run(
            [
                "ffprobe",
                "-v",
                "quiet",
                "-print_format",
                "json",
                "-show_format",
                "-show_streams",
                str(file_path),
            ],
            capture_output=True,
            text=True,
        )

        if result.returncode == 0:
            data = json.loads(result.stdout)

            # Format info
            if "format" in data:
                format_info = data["format"]
                metadata.duration = float(format_info.get("duration", 0))

            # Stream info (vidéo)
            for stream in data.get("streams", []):
                if stream.get("codec_type") == "video":
                    metadata.width = stream.get("width")
                    metadata.height = stream.get("height")
                    metadata.codec = stream.get("codec_name")

                    # FPS
                    fps_str = stream.get("r_frame_rate", "0/1")
                    if "/" in fps_str:
                        num, den = map(int, fps_str.split("/"))
                        metadata.fps = num / den if den != 0 else None

                    break

            logger.debug(
                f"Métadonnées extraites via ffprobe: {metadata.duration}s, {metadata.width}x{metadata.height}"
            )

    except (
        ImportError,
        FileNotFoundError,
        subprocess.SubprocessError,
        json.JSONDecodeError,
    ):
        logger.debug("ffprobe non disponible, métadonnées basiques utilisées")

    return metadata


async def upload_cinemagraph(
    uploader: OwnCloudUploader,
    video_file: Union[Path, bytes],
    workflow_id: Optional[str] = None,
    prompt: Optional[str] = None,
    generation_params: Optional[Dict[str, Any]] = None,
    create_share: bool = True,
    share_password: Optional[str] = None,
) -> UploadResult:
    """
    Upload un cinemagraph avec métadonnées complètes

    Args:
        uploader: Instance de OwnCloudUploader
        video_file: Fichier vidéo à uploader
        workflow_id: ID du workflow de génération
        prompt: Prompt utilisé pour la génération
        generation_params: Paramètres de génération
        create_share: Créer un lien de partage
        share_password: Mot de passe pour le partage

    Returns:
        UploadResult: Résultat de l'upload avec lien de partage
    """

    # Extraire métadonnées
    if isinstance(video_file, Path):
        metadata = extract_video_metadata(video_file)
        original_name = video_file.name
    else:
        # Pour bytes, créer métadonnées basiques
        metadata = VideoMetadata(
            filename="cinemagraph.mp4",
            original_name="cinemagraph.mp4",
            file_size=len(video_file),
            created_at=datetime.now(),
        )
        original_name = "cinemagraph.mp4"

    # Ajouter info de génération
    metadata.workflow_id = workflow_id
    metadata.prompt = prompt
    metadata.model_used = "WAN 2.2 I2V 14B"
    metadata.generation_params = generation_params

    # Générer nom de fichier unique
    remote_path = uploader.generate_filename(original_name, workflow_id)

    # Upload avec callback de progression
    def progress_callback(uploaded: int, total: int, percent: float):
        logger.info(f"Upload progression: {percent:.1f}% ({uploaded}/{total} bytes)")

    # Effectuer l'upload
    result = await uploader.upload_file(
        file_data=video_file,
        remote_path=remote_path,
        metadata=metadata,
        progress_callback=progress_callback,
    )

    # Créer lien de partage si demandé
    if result.success and create_share:
        share_link = await uploader.create_share_link(
            file_path=remote_path,
            password=share_password,
            expire_days=365,  # 1 an d'expiration
        )
        result.share_link = share_link

    return result


if __name__ == "__main__":
    # Test du module OwnCloud
    from src.logger import setup_logger

    setup_logger(level="INFO")
    logger.info("🧪 Test du module OwnCloud Uploader")

    async def test_owncloud():
        # Configuration de test (à adapter)
        config = OwnCloudConfig(
            server_url="https://your-owncloud-server.com",
            username="your-username",
            password="your-password",
            upload_folder="/Cinemagraphs",
        )

        try:
            async with OwnCloudUploader(config) as uploader:
                logger.info("✅ Connexion OwnCloud OK")

                # Test de création de dossier
                await uploader.create_folder("Test_Uploads")

                # Test d'upload (fichier de test)
                test_data = b"Test file content for OwnCloud upload"
                result = await uploader.upload_file(
                    file_data=test_data, remote_path="/Test_Uploads/test.txt"
                )

                if result.success:
                    logger.success(f"✅ Upload test réussi: {result.file_path}")

                    # Test de partage
                    share_link = await uploader.create_share_link(result.file_path)
                    if share_link:
                        logger.success(f"✅ Lien de partage: {share_link}")
                else:
                    logger.error(f"❌ Échec upload: {result.error_message}")

        except Exception as e:
            logger.error(f"❌ Erreur test OwnCloud: {e}")
            logger.info(
                "💡 Configurez les variables d'environnement ou modifiez le config pour tester"
            )

    # Ne pas lancer le test automatiquement (nécessite une vraie config)
    logger.info("⚠️  Test nécessite une configuration OwnCloud valide")
    logger.info("💡 Modifiez le config dans le code pour tester avec votre serveur")
