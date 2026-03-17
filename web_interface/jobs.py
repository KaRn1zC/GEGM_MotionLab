"""
Gestionnaire de jobs asynchrones pour la génération de cinemagraphs
"""

import uuid
import threading
from datetime import datetime
from typing import Any
from dataclasses import dataclass, asdict
from enum import Enum


from src.logger import get_logger

logger = get_logger("job_manager")


class JobStatus(str, Enum):
    """Statuts possibles d'un job"""

    PENDING = "pending"
    UPLOADING = "uploading"
    PROCESSING = "processing"
    UPLOADING_RESULT = "uploading_result"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


@dataclass
class Job:
    """Représente un job de génération de cinemagraph"""

    job_id: str
    status: JobStatus
    input_image: str
    prompt: str
    parameters: dict[str, Any]
    created_at: datetime
    started_at: datetime | None = None
    completed_at: datetime | None = None
    progress: float = 0.0
    current_step: str | None = None
    workflow_id: str | None = None
    output_video: str | None = None
    owncloud_link: str | None = None
    error_message: str | None = None

    def to_dict(self) -> dict[str, Any]:
        """Convertit le job en dictionnaire"""
        data = asdict(self)
        data["status"] = self.status.value
        data["created_at"] = self.created_at.isoformat()
        if self.started_at:
            data["started_at"] = self.started_at.isoformat()
        if self.completed_at:
            data["completed_at"] = self.completed_at.isoformat()
        return data


class JobManager:
    """Gestionnaire central des jobs de génération"""

    def __init__(self):
        self.jobs: dict[str, Job] = {}
        self.active_jobs: dict[str, Job] = {}
        self.completed_jobs: dict[str, Job] = {}
        self.failed_jobs: dict[str, Job] = {}
        self._lock = threading.Lock()

        logger.info("JobManager initialisé")

    def create_job(
        self, input_image: str, prompt: str, parameters: dict[str, Any]
    ) -> Job:
        """
        Crée un nouveau job

        Args:
            input_image: Chemin de l'image d'entrée
            prompt: Prompt de génération
            parameters: Paramètres de génération

        Returns:
            Job: Job créé
        """
        job_id = str(uuid.uuid4())

        job = Job(
            job_id=job_id,
            status=JobStatus.PENDING,
            input_image=input_image,
            prompt=prompt,
            parameters=parameters,
            created_at=datetime.now(),
        )

        with self._lock:
            self.jobs[job_id] = job
            self.active_jobs[job_id] = job

        logger.info(f"Job créé: {job_id}")
        return job

    def get_job(self, job_id: str) -> Job | None:
        """Récupère un job par son ID"""
        with self._lock:
            return self.jobs.get(job_id)

    def update_job(
        self,
        job_id: str,
        status: JobStatus | None = None,
        progress: float | None = None,
        current_step: str | None = None,
        workflow_id: str | None = None,
        output_video: str | None = None,
        owncloud_link: str | None = None,
        error_message: str | None = None,
    ):
        """Met à jour un job"""
        with self._lock:
            job = self.jobs.get(job_id)
            if not job:
                logger.error(f"Job non trouvé: {job_id}")
                return

            if status:
                old_status = job.status
                job.status = status

                # Gérer les transitions de statut
                if status == JobStatus.PROCESSING and not job.started_at:
                    job.started_at = datetime.now()

                if status in [
                    JobStatus.COMPLETED,
                    JobStatus.FAILED,
                    JobStatus.CANCELLED,
                ]:
                    job.completed_at = datetime.now()

                    # Déplacer vers le bon dictionnaire
                    if job_id in self.active_jobs:
                        del self.active_jobs[job_id]

                    if status == JobStatus.COMPLETED:
                        self.completed_jobs[job_id] = job
                    elif status == JobStatus.FAILED:
                        self.failed_jobs[job_id] = job

                logger.info(f"Job {job_id}: {old_status.value} → {status.value}")

            if progress is not None:
                job.progress = progress

            if current_step:
                job.current_step = current_step

            if workflow_id:
                job.workflow_id = workflow_id

            if output_video:
                job.output_video = output_video

            if owncloud_link:
                job.owncloud_link = owncloud_link

            if error_message:
                job.error_message = error_message

    def list_jobs(
        self, status: JobStatus | None = None, limit: int = 50
    ) -> list[Job]:
        """
        Liste les jobs avec filtres optionnels

        Args:
            status: Filtrer par statut
            limit: Nombre maximum de jobs à retourner

        Returns:
            list[Job]: Liste des jobs
        """
        with self._lock:
            jobs = list(self.jobs.values())

        # Filtrer par statut si demandé
        if status:
            jobs = [j for j in jobs if j.status == status]

        # Trier par date de création (plus récent en premier)
        jobs.sort(key=lambda j: j.created_at, reverse=True)

        # Limiter le nombre de résultats
        return jobs[:limit]

    def delete_job(self, job_id: str) -> bool:
        """
        Supprime un job

        Args:
            job_id: ID du job à supprimer

        Returns:
            bool: True si supprimé
        """
        with self._lock:
            if job_id in self.jobs:
                job = self.jobs[job_id]

                # Ne supprimer que les jobs terminés
                if job.status in [
                    JobStatus.COMPLETED,
                    JobStatus.FAILED,
                    JobStatus.CANCELLED,
                ]:
                    del self.jobs[job_id]

                    if job_id in self.active_jobs:
                        del self.active_jobs[job_id]
                    if job_id in self.completed_jobs:
                        del self.completed_jobs[job_id]
                    if job_id in self.failed_jobs:
                        del self.failed_jobs[job_id]

                    logger.info(f"Job supprimé: {job_id}")
                    return True
                else:
                    logger.warning(f"Impossible de supprimer job actif: {job_id}")
                    return False

        return False

    def get_statistics(self) -> dict[str, Any]:
        """Retourne des statistiques sur les jobs"""
        with self._lock:
            return {
                "total": len(self.jobs),
                "active": len(self.active_jobs),
                "completed": len(self.completed_jobs),
                "failed": len(self.failed_jobs),
                "by_status": {
                    status.value: sum(
                        1 for j in self.jobs.values() if j.status == status
                    )
                    for status in JobStatus
                },
            }
