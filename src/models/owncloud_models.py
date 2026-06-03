"""
Modèles de données pour OwnCloud
Extrait de owncloud_uploader.py pour éviter les imports circulaires
"""

from dataclasses import dataclass, asdict
from datetime import datetime, timedelta
from typing import Any


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

    def validate(self) -> list[str]:
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
    duration: float | None = None
    width: int | None = None
    height: int | None = None
    fps: float | None = None
    format: str | None = None
    codec: str | None = None
    created_at: datetime | None = None
    workflow_id: str | None = None
    prompt: str | None = None
    model_used: str | None = None
    generation_params: dict[str, Any | None] = None

    def to_dict(self) -> dict[str, Any]:
        """Convertit en dictionnaire sérialisable"""
        data = asdict(self)
        if self.created_at:
            data["created_at"] = self.created_at.isoformat()
        return data

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "VideoMetadata":
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
    upload_duration: timedelta | None = None
    share_link: str | None = None
    metadata: VideoMetadata | None = None
    error_message: str | None = None
    owncloud_url: str | None = None

    @property
    def upload_speed_mbps(self) -> float | None:
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
        status_code: int | None = None,
        details: dict | None = None,
    ):
        super().__init__(message)
        self.status_code = status_code
        self.details = details or {}
