"""
Tests pour l'application Flask
"""

import sys
import pytest
from pathlib import Path

sys.path.append(str(Path(__file__).parent.parent))

from web_interface.app import create_app
from web_interface.jobs import JobManager, JobStatus


@pytest.fixture
def app():
    """Fixture pour l'application Flask"""
    app = create_app("testing")
    app.config.update({"TESTING": True, "DEBUG": False})
    return app


@pytest.fixture
def client(app):
    """Fixture pour le client de test"""
    return app.test_client()


class TestFlaskApp:
    """Tests pour l'application Flask"""

    def test_health_endpoint(self, client):
        """Test de l'endpoint de santé"""
        response = client.get("/health")
        assert response.status_code == 200

        data = response.get_json()
        assert data["status"] == "healthy"
        assert "services" in data
        assert "jobs" in data

    def test_index_page(self, client):
        """Test de la page d'accueil"""
        response = client.get("/")
        assert response.status_code == 200

    def test_list_jobs_empty(self, client):
        """Test liste de jobs vide"""
        response = client.get("/api/jobs")
        assert response.status_code == 200

        data = response.get_json()
        assert "jobs" in data
        assert isinstance(data["jobs"], list)

    def test_get_nonexistent_job(self, client):
        """Test récupération job inexistant"""
        response = client.get("/api/jobs/nonexistent-id")
        assert response.status_code == 404

    def test_list_templates(self, client):
        """Test liste des templates"""
        response = client.get("/api/templates")
        assert response.status_code == 200

        data = response.get_json()
        assert "templates" in data

    def test_statistics(self, client):
        """Test endpoint statistiques"""
        response = client.get("/api/statistics")
        assert response.status_code == 200

        data = response.get_json()
        assert "total" in data
        assert "active" in data


class TestJobManager:
    """Tests pour le JobManager"""

    def test_create_job(self):
        """Test création de job"""
        manager = JobManager()

        job = manager.create_job(
            input_image="/path/to/image.jpg",
            prompt="test prompt",
            parameters={"steps": 20},
        )

        assert job.job_id is not None
        assert job.status == JobStatus.PENDING
        assert job.prompt == "test prompt"

    def test_get_job(self):
        """Test récupération de job"""
        manager = JobManager()

        job = manager.create_job(
            input_image="/path/to/image.jpg", prompt="test", parameters={}
        )

        retrieved = manager.get_job(job.job_id)
        assert retrieved is not None
        assert retrieved.job_id == job.job_id

    def test_update_job_status(self):
        """Test mise à jour statut job"""
        manager = JobManager()

        job = manager.create_job(
            input_image="/path/to/image.jpg", prompt="test", parameters={}
        )

        manager.update_job(job.job_id, status=JobStatus.PROCESSING, progress=0.5)

        updated = manager.get_job(job.job_id)
        assert updated.status == JobStatus.PROCESSING
        assert updated.progress == 0.5

    def test_list_jobs(self):
        """Test liste de jobs"""
        manager = JobManager()

        # Créer plusieurs jobs
        for i in range(5):
            manager.create_job(
                input_image=f"/path/to/image{i}.jpg", prompt=f"test {i}", parameters={}
            )

        jobs = manager.list_jobs()
        assert len(jobs) == 5

    def test_delete_completed_job(self):
        """Test suppression job terminé"""
        manager = JobManager()

        job = manager.create_job(
            input_image="/path/to/image.jpg", prompt="test", parameters={}
        )

        # Marquer comme terminé
        manager.update_job(job.job_id, status=JobStatus.COMPLETED)

        # Supprimer
        success = manager.delete_job(job.job_id)
        assert success is True

        # Vérifier qu'il n'existe plus
        retrieved = manager.get_job(job.job_id)
        assert retrieved is None


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
