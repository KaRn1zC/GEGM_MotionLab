"""
Tests unitaires du registre de modèles.

Vérifie que le registre produit des valeurs identiques au code hardcodé existant,
garantissant la non-régression.
"""

import json
import subprocess
import sys

import pytest

from src.model_registry import (
    CheckpointDetectionConfig,
    DiffusionFileConfig,
    DownloadManifest,
    ModelConfig,
    ModelRegistry,
    ModelTextEncoderConfig,
    ResolutionConfig,
    SharedComponentsConfig,
    VaeConfig,
    VerificationConfig,
    get_registry,
)


@pytest.fixture
def registry() -> ModelRegistry:
    """Instancie un registre frais (pas le singleton)."""
    return ModelRegistry()


# ---------------------------------------------------------------------------
# Tests de base — chargement et structure
# ---------------------------------------------------------------------------

class TestRegistryLoading:
    """Vérifie le chargement correct du YAML."""

    def test_should_load_registry(self, registry: ModelRegistry) -> None:
        """Le registre se charge sans erreur."""
        assert registry is not None

    def test_should_list_all_models(self, registry: ModelRegistry) -> None:
        """Les trois modèles enregistrés sont présents."""
        models = registry.list_models()
        assert "wan2.2-ti2v-5b" in models
        assert "wan2.2-i2v-a14b" in models
        assert "ltx-2.3-i2v-dev" in models
        assert len(models) == 3

    def test_should_return_none_for_unknown_model(self, registry: ModelRegistry) -> None:
        """Un modèle inconnu retourne None, pas une exception."""
        assert registry.get_model("nonexistent") is None
        assert registry.get_diffusion_files("nonexistent") is None
        assert registry.get_vae_config("nonexistent") is None
        assert registry.get_timeout("nonexistent") is None


# ---------------------------------------------------------------------------
# Tests d'équivalence — valeurs identiques au code hardcodé
# ---------------------------------------------------------------------------

class TestEquivalence5B:
    """Vérifie que le registre retourne les mêmes valeurs que le code hardcodé pour le 5B."""

    def test_should_return_correct_diffusion_files(self, registry: ModelRegistry) -> None:
        """verify_diffusion_model.py L32-33 : fichier unique 5B."""
        files = registry.get_diffusion_files("wan2.2-ti2v-5b")
        assert files is not None
        assert len(files) == 1
        assert files[0].filename == "wan2.2_ti2v_5B_fp16.safetensors"

    def test_should_return_correct_diffusion_size(self, registry: ModelRegistry) -> None:
        """verify_diffusion_model.py L63-64 : taille attendue 8-11 GB."""
        files = registry.get_diffusion_files("wan2.2-ti2v-5b")
        assert files[0].min_size_gb == 8.0
        assert files[0].max_size_gb == 11.0

    def test_should_return_correct_vae(self, registry: ModelRegistry) -> None:
        """verify_vae.py L33 et workflow_manager.py L360 : wan2.2_vae.safetensors."""
        vae = registry.get_vae_config("wan2.2-ti2v-5b")
        assert vae is not None
        assert vae.filename == "wan2.2_vae.safetensors"
        assert vae.expected_channels == 48
        assert vae.version == "2.2"

    def test_should_return_correct_timeout(self, registry: ModelRegistry) -> None:
        """routes.py L515 : 5400s pour le 5B."""
        assert registry.get_timeout("wan2.2-ti2v-5b") == 5400

    def test_should_return_correct_model_type(self, registry: ModelRegistry) -> None:
        """workflow_manager.py L53 : model_type = '5b'."""
        model = registry.get_model("wan2.2-ti2v-5b")
        assert model.model_type == "5b"

    def test_should_return_single_checkpoint_type(self, registry: ModelRegistry) -> None:
        """workflow_manager.py : retourne un str (pas un tuple) pour 5B."""
        cd = registry.get_checkpoint_detection("wan2.2-ti2v-5b")
        assert cd.return_type == "single"
        assert cd.primary_files == ["wan2.2_ti2v_5B_fp16.safetensors"]

    def test_should_return_correct_vae_size_range(self, registry: ModelRegistry) -> None:
        """verify_vae.py L34-35 : min 0.5, max 2.0 GB."""
        vae = registry.get_vae_config("wan2.2-ti2v-5b")
        assert vae.min_size_gb == 0.5
        assert vae.max_size_gb == 2.0


class TestEquivalence14B:
    """Vérifie que le registre retourne les mêmes valeurs que le code hardcodé pour le 14B."""

    def test_should_return_correct_diffusion_files(self, registry: ModelRegistry) -> None:
        """verify_diffusion_model.py L35-37 : deux fichiers high/low noise."""
        files = registry.get_diffusion_files("wan2.2-i2v-a14b")
        assert files is not None
        assert len(files) == 2
        filenames = [f.filename for f in files]
        assert "wan2.2_i2v_high_noise_14B_fp16.safetensors" in filenames
        assert "wan2.2_i2v_low_noise_14B_fp16.safetensors" in filenames

    def test_should_return_correct_diffusion_sizes(self, registry: ModelRegistry) -> None:
        """verify_diffusion_model.py L65-66 : taille 25-32 GB chacun."""
        files = registry.get_diffusion_files("wan2.2-i2v-a14b")
        for f in files:
            assert f.min_size_gb == 25.0
            assert f.max_size_gb == 32.0

    def test_should_return_correct_vae(self, registry: ModelRegistry) -> None:
        """verify_vae.py L39 et workflow_manager.py L357 : wan_2.1_vae.safetensors."""
        vae = registry.get_vae_config("wan2.2-i2v-a14b")
        assert vae is not None
        assert vae.filename == "wan_2.1_vae.safetensors"
        assert vae.expected_channels == 16
        assert vae.version == "2.1"

    def test_should_return_correct_timeout(self, registry: ModelRegistry) -> None:
        """routes.py L515 : 10800s pour le 14B."""
        assert registry.get_timeout("wan2.2-i2v-a14b") == 10800

    def test_should_return_moe_pair_checkpoint_type(self, registry: ModelRegistry) -> None:
        """workflow_manager.py : retourne tuple (high, low) pour 14B."""
        cd = registry.get_checkpoint_detection("wan2.2-i2v-a14b")
        assert cd.return_type == "moe_pair"
        assert len(cd.primary_files) == 2

    def test_should_return_correct_roles(self, registry: ModelRegistry) -> None:
        """Les rôles high_noise et low_noise sont bien assignés."""
        files = registry.get_diffusion_files("wan2.2-i2v-a14b")
        roles = {f.role for f in files}
        assert roles == {"high_noise", "low_noise"}


class TestDetectionPriority:
    """Vérifie la priorité de détection (identique au code hardcodé)."""

    def test_should_return_ltx_dev_first(self, registry: ModelRegistry) -> None:
        """LTX 2.3 22B > WAN 14B > WAN 5B."""
        priority = registry.get_detection_priority()
        assert priority == [
            ("ltx-2.3-i2v-dev", "dev"),
            ("wan2.2-i2v-a14b", "14b"),
            ("wan2.2-ti2v-5b", "5b"),
        ]


# ---------------------------------------------------------------------------
# Tests composants partagés
# ---------------------------------------------------------------------------

class TestSharedComponents:
    """Vérifie les composants partagés (T5, CLIP, upscalers)."""

    def test_should_return_t5_encoder(self, registry: ModelRegistry) -> None:
        """verify_t5_integrity.py L31 : umt5_xxl_fp16.safetensors."""
        shared = registry.get_shared_components()
        assert shared.text_encoder.filename == "umt5_xxl_fp16.safetensors"
        assert shared.text_encoder.min_size_gb == 10.0

    def test_should_return_t5_critical_keys(self, registry: ModelRegistry) -> None:
        """verify_t5_integrity.py L102-112 : 9 clés critiques."""
        shared = registry.get_shared_components()
        keys = shared.text_encoder.critical_keys
        assert len(keys) == 9
        assert "shared.weight" in keys
        assert "encoder.final_layer_norm.weight" in keys

    def test_should_return_clip_vision(self, registry: ModelRegistry) -> None:
        """setup_wan22_native.sh L354 : clip-vit-large-patch14-336.safetensors."""
        shared = registry.get_shared_components()
        assert shared.clip_vision.filename == "clip-vit-large-patch14-336.safetensors"

    def test_should_return_upscalers(self, registry: ModelRegistry) -> None:
        """HAT-L 4x (post-gen) + HAT 2x (pré-gen), tous deux requis."""
        shared = registry.get_shared_components()
        assert len(shared.upscalers) == 2
        names = {u.filename for u in shared.upscalers}
        assert "HAT-L_SRx4_ImageNet-pretrain.pth" in names
        assert "HAT_SRx2.pth" in names

        # Les deux sont requis (non optionnels)
        by_name = {u.filename: u for u in shared.upscalers}
        assert by_name["HAT-L_SRx4_ImageNet-pretrain.pth"].optional is False
        assert by_name["HAT_SRx2.pth"].optional is False


# ---------------------------------------------------------------------------
# Tests manifeste de téléchargement
# ---------------------------------------------------------------------------

class TestDownloadManifest:
    """Vérifie la construction du manifeste HF."""

    def test_should_build_5b_manifest(self, registry: ModelRegistry) -> None:
        """Le manifeste 5B inclut diffusion + VAE + T5."""
        manifest = registry.get_hf_download_manifest("wan2.2-ti2v-5b")
        assert manifest is not None
        assert manifest.repo == "Comfy-Org/Wan_2.2_ComfyUI_Repackaged"
        # 1 diffusion + 1 vae + 1 t5 = 3 fichiers
        assert len(manifest.files) == 3

    def test_should_build_14b_manifest(self, registry: ModelRegistry) -> None:
        """Le manifeste 14B inclut 2 diffusion + VAE + T5."""
        manifest = registry.get_hf_download_manifest("wan2.2-i2v-a14b")
        assert manifest is not None
        # 2 diffusion + 1 vae + 1 t5 = 4 fichiers
        assert len(manifest.files) == 4

    def test_should_return_none_for_unknown(self, registry: ModelRegistry) -> None:
        """Modèle inconnu → None."""
        assert registry.get_hf_download_manifest("nonexistent") is None


# ---------------------------------------------------------------------------
# Tests verification config
# ---------------------------------------------------------------------------

class TestVerificationConfig:
    """Vérifie les clés de vérification d'intégrité."""

    def test_should_return_diffusion_keys_5b(self, registry: ModelRegistry) -> None:
        """verify_diffusion_model.py L131-135 : 3 clés critiques."""
        ver = registry.get_verification_config("wan2.2-ti2v-5b")
        assert ver is not None
        assert "blocks.0.ffn.0.weight" in ver.diffusion_keys
        assert "blocks.14.ffn.0.weight" in ver.diffusion_keys
        assert "blocks.23.ffn.0.weight" in ver.diffusion_keys

    def test_should_return_vae_keys(self, registry: ModelRegistry) -> None:
        """verify_vae.py L115-123 : 7 clés critiques."""
        ver = registry.get_verification_config("wan2.2-ti2v-5b")
        assert len(ver.vae_keys) == 7
        assert "decoder.conv1.weight" in ver.vae_keys


# ---------------------------------------------------------------------------
# Tests symlinks
# ---------------------------------------------------------------------------

class TestSymlinks:
    """Vérifie les définitions de symlinks."""

    def test_should_return_5b_symlinks(self, registry: ModelRegistry) -> None:
        """setup_wan22_native.sh L93-95 : 3 symlinks pour 5B."""
        symlinks = registry.get_symlinks("wan2.2-ti2v-5b")
        assert symlinks is not None
        assert len(symlinks) == 3
        targets = {s.target for s in symlinks}
        assert "wan2.2_ti2v_5B_fp16.safetensors" in targets
        assert "umt5_xxl_fp16.safetensors" in targets
        assert "wan2.2_vae.safetensors" in targets

    def test_should_return_14b_symlinks(self, registry: ModelRegistry) -> None:
        """setup_wan22_native.sh L161-164 : 4 symlinks pour 14B."""
        symlinks = registry.get_symlinks("wan2.2-i2v-a14b")
        assert symlinks is not None
        assert len(symlinks) == 4


# ---------------------------------------------------------------------------
# Tests CLI
# ---------------------------------------------------------------------------

class TestCLI:
    """Vérifie l'interface CLI (python -m src.model_registry)."""

    def test_should_list_models(self) -> None:
        """list-models affiche les deux modèles."""
        result = subprocess.run(
            [sys.executable, "-m", "src.model_registry", "list-models"],
            capture_output=True, text=True,
        )
        assert result.returncode == 0
        assert "wan2.2-ti2v-5b" in result.stdout
        assert "wan2.2-i2v-a14b" in result.stdout

    def test_should_get_hf_downloads_json(self) -> None:
        """get-hf-downloads retourne du JSON valide."""
        result = subprocess.run(
            [sys.executable, "-m", "src.model_registry", "get-hf-downloads", "wan2.2-ti2v-5b"],
            capture_output=True, text=True,
        )
        assert result.returncode == 0
        data = json.loads(result.stdout)
        assert "repo" in data
        assert "files" in data

    def test_should_fail_for_unknown_model(self) -> None:
        """get-hf-downloads avec modèle inconnu → exit code 1."""
        result = subprocess.run(
            [sys.executable, "-m", "src.model_registry", "get-hf-downloads", "nonexistent"],
            capture_output=True, text=True,
        )
        assert result.returncode == 1

    def test_should_get_vae_json(self) -> None:
        """get-vae retourne le bon filename."""
        result = subprocess.run(
            [sys.executable, "-m", "src.model_registry", "get-vae", "wan2.2-i2v-a14b"],
            capture_output=True, text=True,
        )
        assert result.returncode == 0
        data = json.loads(result.stdout)
        assert data["filename"] == "wan_2.1_vae.safetensors"

    def test_should_get_expected_files(self) -> None:
        """get-expected-files retourne la bonne structure."""
        result = subprocess.run(
            [sys.executable, "-m", "src.model_registry", "get-expected-files", "wan2.2-i2v-a14b"],
            capture_output=True, text=True,
        )
        assert result.returncode == 0
        data = json.loads(result.stdout)
        assert len(data) == 2  # high + low noise

    def test_should_get_symlinks(self) -> None:
        """get-symlinks retourne les symlinks attendus."""
        result = subprocess.run(
            [sys.executable, "-m", "src.model_registry", "get-symlinks", "wan2.2-ti2v-5b"],
            capture_output=True, text=True,
        )
        assert result.returncode == 0
        data = json.loads(result.stdout)
        assert len(data) == 3


# ---------------------------------------------------------------------------
# Tests LTX 2.3
# ---------------------------------------------------------------------------

class TestEquivalenceLTX23Dev:
    """Vérifie le registre pour LTX 2.3 22B."""

    def test_should_return_correct_model_type(self, registry: ModelRegistry) -> None:
        """model_type = 'dev'."""
        model = registry.get_model("ltx-2.3-i2v-dev")
        assert model is not None
        assert model.model_type == "dev"

    def test_should_return_correct_diffusion_file(self, registry: ModelRegistry) -> None:
        """Fichier unique BF16 dev."""
        files = registry.get_diffusion_files("ltx-2.3-i2v-dev")
        assert len(files) == 1
        assert files[0].filename == "ltx-2.3-22b-dev.safetensors"

    def test_should_return_bf16_text_encoder(self, registry: ModelRegistry) -> None:
        """Text encoder Gemma 3 12B BF16 (full precision)."""
        model = registry.get_model("ltx-2.3-i2v-dev")
        assert model.text_encoder.filename == "gemma_3_12B_it/text_encoder/model.safetensors"

    def test_should_return_correct_timeout(self, registry: ModelRegistry) -> None:
        """Timeout 7200s pour LTX 2.3 22B."""
        assert registry.get_timeout("ltx-2.3-i2v-dev") == 7200

    def test_should_return_correct_resolution(self, registry: ModelRegistry) -> None:
        """Résolution 1280x736 (gen max optimisée LTX 2.3)."""
        res = registry.get_resolution_config("ltx-2.3-i2v-dev")
        assert res is not None
        assert res.max_width == 1280
        assert res.max_height == 736
        assert res.dimension_stride == 32
        assert res.upscale_trigger_ratio == 1.3


class TestDownloadManifestLTX:
    """Vérifie le manifeste de téléchargement pour LTX 2.3."""

    def test_should_build_dev_manifest(self, registry: ModelRegistry) -> None:
        """Le manifeste LTX 2.3 22B inclut diffusion + text encoder BF16."""
        manifest = registry.get_hf_download_manifest("ltx-2.3-i2v-dev")
        assert manifest is not None
        assert manifest.repo == "Lightricks/LTX-2.3"
        assert len(manifest.files) == 2
        filenames = [f["filename"] for f in manifest.files]
        assert "gemma_3_12B_it/text_encoder/model.safetensors" in filenames

    def test_should_not_include_t5_for_ltx(self, registry: ModelRegistry) -> None:
        """LTX utilise Gemma, pas T5 — le manifeste ne doit pas inclure T5."""
        manifest = registry.get_hf_download_manifest("ltx-2.3-i2v-dev")
        filenames = [f["filename"] for f in manifest.files]
        assert "umt5_xxl_fp16.safetensors" not in filenames
        assert "gemma_3_12B_it/text_encoder/model.safetensors" in filenames


# ---------------------------------------------------------------------------
# Tests ResolutionConfig et accesseurs
# ---------------------------------------------------------------------------

class TestResolutionConfig:
    """Vérifie le parsing et les accesseurs du bloc resolution."""

    def test_should_parse_5b_resolution(self, registry: ModelRegistry) -> None:
        """Le bloc resolution du 5B est correctement parsé."""
        res = registry.get_resolution_config("wan2.2-ti2v-5b")
        assert res is not None
        assert res.max_width == 1280
        assert res.max_height == 736
        assert res.dimension_stride == 32
        assert res.upscale_trigger_ratio == 1.5
        assert res.supersampling_max_ratio == 4.0
        assert res.vae_tiling_pixel_threshold == 2073600
        assert res.vae_tiling_upscale_threshold == 4.0

    def test_should_parse_14b_resolution(self, registry: ModelRegistry) -> None:
        """Le bloc resolution du 14B est identique au 5B (WAN 2.2 unifié)."""
        res = registry.get_resolution_config("wan2.2-i2v-a14b")
        assert res is not None
        assert res.max_width == 1280
        assert res.max_height == 736
        assert res.dimension_stride == 32

    def test_should_calculate_max_pixels(self, registry: ModelRegistry) -> None:
        """max_pixels retourne 1280 × 736 = 942080."""
        res = registry.get_resolution_config("wan2.2-ti2v-5b")
        assert res.max_pixels == 1280 * 736

    def test_should_return_none_for_unknown(self, registry: ModelRegistry) -> None:
        """Modèle inconnu → None."""
        assert registry.get_resolution_config("nonexistent") is None

    def test_should_return_upscale_workflow_5b(self, registry: ModelRegistry) -> None:
        """Le template upscale du 5B est bien wan22_5b_with_upscale."""
        assert registry.get_upscale_workflow_template("wan2.2-ti2v-5b") == "wan22_5b_with_upscale"

    def test_should_return_upscale_workflow_14b(self, registry: ModelRegistry) -> None:
        """Le template upscale du 14B est bien wan22_14b_with_upscale."""
        assert registry.get_upscale_workflow_template("wan2.2-i2v-a14b") == "wan22_14b_with_upscale"

    def test_should_return_none_upscale_for_unknown(self, registry: ModelRegistry) -> None:
        """Modèle inconnu → None pour le template upscale."""
        assert registry.get_upscale_workflow_template("nonexistent") is None

    def test_should_expose_resolution_on_model_config(self, registry: ModelRegistry) -> None:
        """ModelConfig expose le champ resolution."""
        model = registry.get_model("wan2.2-ti2v-5b")
        assert model.resolution is not None
        assert isinstance(model.resolution, ResolutionConfig)

    def test_should_expose_upscale_template_on_model_config(self, registry: ModelRegistry) -> None:
        """ModelConfig expose le champ workflow_template_upscale."""
        model = registry.get_model("wan2.2-ti2v-5b")
        assert model.workflow_template_upscale == "wan22_5b_with_upscale"


# ---------------------------------------------------------------------------
# Test singleton
# ---------------------------------------------------------------------------

class TestSingleton:
    """Vérifie le pattern singleton."""

    def test_should_return_same_instance(self) -> None:
        """get_registry() retourne toujours la même instance."""
        r1 = get_registry()
        r2 = get_registry()
        assert r1 is r2
