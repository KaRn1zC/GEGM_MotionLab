"""
Tests pour le module OwnCloud Uploader
Tests unitaires avec mocks (pas de dépendance au .env)
"""

import sys
import os
import pytest
from pathlib import Path
from datetime import datetime, timedelta
from unittest.mock import Mock, AsyncMock, patch

# Ajouter le projet au path
sys.path.append(str(Path(__file__).parent.parent))

from src.owncloud_uploader import (
    OwnCloudConfig,
    OwnCloudUploader,
    VideoMetadata,
    UploadResult,
    OwnCloudError,
    extract_video_metadata,
    upload_cinemagraph,
)
from src.owncloud_config import OwnCloudConfigManager


class TestOwnCloudConfig:
    """Tests pour la classe OwnCloudConfig"""

    def test_config_creation_direct(self):
        """Test de création directe d'une configuration"""
        config = OwnCloudConfig(
            server_url="https://cloud.example.com",
            username="testuser",
            password="testpass",
            upload_folder="/Test",
        )

        assert config.server_url == "https://cloud.example.com"
        assert config.username == "testuser"
        assert config.password == "testpass"
        assert config.upload_folder == "/Test"
        assert (
            config.webdav_url
            == "https://cloud.example.com/remote.php/dav/files/testuser"
        )
        assert config.sharing_api_url.endswith(
            "/ocs/v2.php/apps/files_sharing/api/v1/shares"
        )

    def test_config_validation_invalid(self):
        """Test de validation avec configuration invalide"""
        # URL invalide
        config = OwnCloudConfig(
            server_url="invalid-url",
            username="",
            password="test",
            upload_folder="invalid",  # Ne commence pas par /
        )

        errors = config.validate()
        assert len(errors) >= 3
        assert any("server_url" in error for error in errors)
        assert any("username" in error for error in errors)
        assert any("upload_folder" in error for error in errors)

    def test_config_validation_valid(self):
        """Test avec configuration valide"""
        config = OwnCloudConfig(
            server_url="https://cloud.example.com",
            username="testuser",
            password="testpass",
            upload_folder="/Test",
        )

        errors = config.validate()
        assert len(errors) == 0

    def test_config_default_values(self):
        """Test des valeurs par défaut"""
        config = OwnCloudConfig(
            server_url="https://cloud.example.com",
            username="testuser",
            password="testpass",
            upload_folder="/Test",
        )

        # Valeurs par défaut
        assert config.chunk_size == 8192
        assert config.timeout == 300
        assert config.max_retries == 3
        assert config.retry_delay == 1.0


class TestVideoMetadata:
    """Tests pour les métadonnées vidéo"""

    def test_metadata_creation(self):
        """Test de création de métadonnées"""
        metadata = VideoMetadata(
            filename="test.mp4",
            original_name="original.mp4",
            file_size=1024000,
            duration=10.5,
            width=1920,
            height=1080,
            fps=30.0,
        )

        assert metadata.filename == "test.mp4"
        assert metadata.original_name == "original.mp4"
        assert metadata.file_size == 1024000
        assert metadata.duration == 10.5
        assert metadata.width == 1920
        assert metadata.height == 1080
        assert metadata.fps == 30.0

    def test_metadata_serialization(self):
        """Test de sérialisation des métadonnées"""
        now = datetime.now()
        metadata = VideoMetadata(
            filename="test.mp4",
            original_name="test.mp4",
            file_size=1024,
            created_at=now,
        )

        # Conversion en dict
        data = metadata.to_dict()
        assert isinstance(data, dict)
        assert data["filename"] == "test.mp4"
        assert isinstance(data["created_at"], str)  # Sérialisé en ISO format

        # Reconversion depuis dict
        metadata2 = VideoMetadata.from_dict(data)
        assert metadata2.filename == metadata.filename
        assert isinstance(metadata2.created_at, datetime)

    def test_metadata_optional_fields(self):
        """Test des champs optionnels"""
        metadata = VideoMetadata(
            filename="test.mp4", original_name="test.mp4", file_size=1024
        )

        # Champs optionnels doivent être None par défaut
        assert metadata.duration is None
        assert metadata.width is None
        assert metadata.height is None
        assert metadata.fps is None
        assert metadata.workflow_id is None
        assert metadata.prompt is None


class TestUploadResult:
    """Tests pour les résultats d'upload"""

    def test_upload_result_success(self):
        """Test de création d'un résultat d'upload réussi"""
        result = UploadResult(
            success=True,
            file_path="/test/file.mp4",
            file_size=1024000,
            upload_duration=timedelta(seconds=30),
        )

        assert result.success is True
        assert result.file_path == "/test/file.mp4"
        assert result.file_size == 1024000
        assert result.upload_duration == timedelta(seconds=30)

        # Test calcul vitesse
        speed = result.upload_speed_mbps
        assert speed is not None
        assert speed > 0

    def test_upload_result_failure(self):
        """Test d'un résultat d'upload échoué"""
        result = UploadResult(
            success=False,
            file_path="/test/file.mp4",
            file_size=0,
            error_message="Connection failed",
        )

        assert result.success is False
        assert result.error_message == "Connection failed"

    def test_upload_result_no_duration(self):
        """Test résultat sans durée"""
        result = UploadResult(
            success=True, file_path="/test/file.mp4", file_size=1024000
        )

        assert result.upload_speed_mbps is None


class TestOwnCloudUploader:
    """Tests pour l'uploader OwnCloud"""

    def test_uploader_creation_valid(self):
        """Test de création de l'uploader avec config valide"""
        config = OwnCloudConfig(
            server_url="https://cloud.example.com",
            username="testuser",
            password="testpass",
            upload_folder="/Test",
        )

        uploader = OwnCloudUploader(config)
        assert uploader.config == config
        assert uploader.session is None

    def test_uploader_creation_invalid_config(self):
        """Test avec configuration invalide"""
        config = OwnCloudConfig(
            server_url="invalid", username="", password="", upload_folder="invalid"
        )

        # Devrait lever une ValueError à cause de la validation
        with pytest.raises(ValueError):
            OwnCloudUploader(config)

    def test_filename_generation(self):
        """Test de génération de nom de fichier"""
        config = OwnCloudConfig(
            server_url="https://cloud.example.com",
            username="testuser",
            password="testpass",
            upload_folder="/Cinemagraphs",
        )

        uploader = OwnCloudUploader(config)

        # Test génération basique
        filename = uploader.generate_filename("test.mp4")
        assert filename.startswith("/Cinemagraphs/")
        assert filename.endswith(".mp4")
        assert "test" in filename

        # Test avec workflow ID
        filename_wf = uploader.generate_filename("test.mp4", workflow_id="abc123def456")
        assert "wf_abc123de" in filename_wf

    def test_filename_generation_sanitization(self):
        """Test du nettoyage du nom de fichier"""
        config = OwnCloudConfig(
            server_url="https://cloud.example.com",
            username="testuser",
            password="testpass",
            upload_folder="/Test",
        )

        uploader = OwnCloudUploader(config)

        # Nom avec caractères spéciaux
        filename = uploader.generate_filename("test@#$%file!.mp4", add_timestamp=False)

        # Devrait ne contenir que des caractères alphanumériques et _-
        assert "@" not in filename
        assert "#" not in filename
        assert "!" not in filename


class TestOwnCloudConfigManager:
    """Tests pour le gestionnaire de configuration"""

    @patch.dict(
        os.environ,
        {
            "OWNCLOUD_SERVER_URL": "https://test-server.com",
            "OWNCLOUD_USERNAME": "test-user",
            "OWNCLOUD_PASSWORD": "test-pass",
            "OWNCLOUD_MODEL_FOLDER": "/TestFolder",
        },
    )
    def test_config_from_env(self):
        """Test de chargement depuis variables d'environnement"""
        # Créer un manager sans fichier YAML
        manager = OwnCloudConfigManager(config_file="nonexistent.yaml")

        # Obtenir la config
        config = manager.get_owncloud_config("default")

        assert config.server_url == "https://test-server.com"
        assert config.username == "test-user"
        assert config.password == "test-pass"
        assert config.upload_folder == "/TestFolder"

    def test_config_manager_sharing_config(self):
        """Test récupération config de partage"""
        manager = OwnCloudConfigManager(config_file="nonexistent.yaml")

        sharing_config = manager.get_sharing_config()

        # Devrait avoir les valeurs par défaut
        assert "default_expire_days" in sharing_config
        assert "default_permissions" in sharing_config
        assert "password_protection" in sharing_config

    def test_config_manager_metadata_config(self):
        """Test récupération config métadonnées"""
        manager = OwnCloudConfigManager(config_file="nonexistent.yaml")

        metadata_config = manager.get_metadata_config()

        assert "include_generation_params" in metadata_config
        assert "include_model_info" in metadata_config
        assert "include_prompt" in metadata_config

    @patch(
        "src.owncloud_config.load_dotenv"
    )  # Mock load_dotenv pour qu'il ne charge rien
    @patch.dict(os.environ, {}, clear=True)
    def test_config_missing_credentials(self, mock_load_dotenv):
        """Test avec credentials manquants"""
        # Mock load_dotenv pour qu'il ne fasse rien
        mock_load_dotenv.return_value = None

        manager = OwnCloudConfigManager(
            config_file="nonexistent.yaml", env_file="nonexistent.env"
        )

        # Devrait lever une erreur car credentials manquants
        with pytest.raises(ValueError):
            manager.get_owncloud_config("default")


def test_extract_video_metadata():
    """Test d'extraction de métadonnées vidéo"""
    # Créer un fichier de test temporaire
    import tempfile

    with tempfile.NamedTemporaryFile(suffix=".mp4", delete=False) as tmp_file:
        tmp_file.write(b"fake video content for testing")
        tmp_path = Path(tmp_file.name)

    try:
        metadata = extract_video_metadata(tmp_path)

        assert metadata.filename == tmp_path.name
        assert metadata.original_name == tmp_path.name
        assert metadata.file_size > 0
        assert metadata.format == "mp4"
        assert metadata.created_at is not None

    finally:
        # Nettoyer
        if tmp_path.exists():
            tmp_path.unlink()


@pytest.mark.asyncio
async def test_upload_cinemagraph_mock():
    """Test d'upload de cinemagraph avec mock"""

    # Créer un mock complet de l'uploader
    mock_uploader = Mock(spec=OwnCloudUploader)
    mock_uploader.config = Mock()
    mock_uploader.config.upload_folder = "/Test"

    # Mock des méthodes
    mock_uploader.generate_filename = Mock(return_value="/Test/generated_file.mp4")
    mock_uploader.upload_file = AsyncMock(
        return_value=UploadResult(
            success=True,
            file_path="/Test/generated_file.mp4",
            file_size=1024000,
            upload_duration=timedelta(seconds=10),
        )
    )
    mock_uploader.create_share_link = AsyncMock(
        return_value="https://share.link/abc123"
    )

    # Données de test
    video_data = b"fake video content" * 1000

    # Appeler la fonction
    result = await upload_cinemagraph(
        uploader=mock_uploader,
        video_file=video_data,
        workflow_id="test-workflow-123",
        prompt="test animation prompt",
        generation_params={"steps": 20, "cfg_scale": 7.5},
        create_share=True,
        share_password=None,
    )

    # Vérifications
    mock_uploader.generate_filename.assert_called_once()
    mock_uploader.upload_file.assert_called_once()
    mock_uploader.create_share_link.assert_called_once()

    assert result.success is True
    assert result.share_link == "https://share.link/abc123"
    assert result.file_size == 1024000


@pytest.mark.asyncio
async def test_upload_cinemagraph_mock_failure():
    """Test d'upload échoué"""

    mock_uploader = Mock(spec=OwnCloudUploader)
    mock_uploader.config = Mock()
    mock_uploader.config.upload_folder = "/Test"

    mock_uploader.generate_filename = Mock(return_value="/Test/failed.mp4")
    mock_uploader.upload_file = AsyncMock(
        return_value=UploadResult(
            success=False,
            file_path="/Test/failed.mp4",
            file_size=0,
            error_message="Connection timeout",
        )
    )

    video_data = b"fake video"

    result = await upload_cinemagraph(
        uploader=mock_uploader,
        video_file=video_data,
        workflow_id="test-workflow",
        prompt="test",
        create_share=False,
    )

    assert result.success is False
    assert result.error_message == "Connection timeout"
    assert result.share_link is None


class TestOwnCloudError:
    """Tests pour l'exception OwnCloudError"""

    def test_owncloud_error_creation(self):
        """Test de création d'une exception OwnCloudError"""
        error = OwnCloudError(
            "Test error", status_code=404, details={"reason": "Not found"}
        )

        assert str(error) == "Test error"
        assert error.status_code == 404
        assert error.details == {"reason": "Not found"}

    def test_owncloud_error_without_details(self):
        """Test sans détails"""
        error = OwnCloudError("Simple error")

        assert str(error) == "Simple error"
        assert error.status_code is None
        assert error.details == {}


if __name__ == "__main__":
    # Exécution directe des tests (sans pytest)
    print("🧪 Exécution des tests OwnCloud Uploader...")
    print("=" * 60)

    # Tests de configuration
    print("\n📋 Tests OwnCloudConfig...")
    test_config = TestOwnCloudConfig()
    test_config.test_config_creation_direct()
    test_config.test_config_validation_invalid()
    test_config.test_config_validation_valid()
    test_config.test_config_default_values()
    print("✅ Tests de configuration passés")

    # Tests de métadonnées
    print("\n🎬 Tests VideoMetadata...")
    test_metadata = TestVideoMetadata()
    test_metadata.test_metadata_creation()
    test_metadata.test_metadata_serialization()
    test_metadata.test_metadata_optional_fields()
    print("✅ Tests de métadonnées passés")

    # Tests de résultats
    print("\n📊 Tests UploadResult...")
    test_result = TestUploadResult()
    test_result.test_upload_result_success()
    test_result.test_upload_result_failure()
    test_result.test_upload_result_no_duration()
    print("✅ Tests de résultats passés")

    # Tests d'uploader
    print("\n📤 Tests OwnCloudUploader...")
    test_uploader = TestOwnCloudUploader()
    test_uploader.test_uploader_creation_valid()
    test_uploader.test_filename_generation()
    test_uploader.test_filename_generation_sanitization()
    print("✅ Tests d'uploader passés")

    # Test extraction métadonnées
    print("\n🎥 Test extraction métadonnées...")
    test_extract_video_metadata()
    print("✅ Test d'extraction passé")

    # Tests d'erreur
    print("\n❌ Tests OwnCloudError...")
    test_error = TestOwnCloudError()
    test_error.test_owncloud_error_creation()
    test_error.test_owncloud_error_without_details()
    print("✅ Tests d'erreur passés")

    print("\n" + "=" * 60)
    print("🎉 Tous les tests synchrones sont passés !")
    print("💡 Lancez 'pytest tests/test_owncloud_uploader.py -v' pour les tests async")
