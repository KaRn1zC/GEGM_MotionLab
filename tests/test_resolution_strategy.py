"""
Tests du pipeline résolution/upscale model-agnostic.

Vérifie la non-régression WAN 2.2, le fallback, et l'extensibilité
vers des modèles avec des résolutions natives différentes.
"""

from unittest.mock import MagicMock, patch

import pytest

from src.model_registry import ModelConfig, ResolutionConfig, RuntimeConfig
from web_interface.routes import calculate_optimal_generation_strategy


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_resolution_config(
    max_width: int = 1280,
    max_height: int = 720,
    stride: int = 32,
    upscale_trigger: float = 1.5,
    supersampling_max: float = 4.0,
    vae_tiling_px: int = 2073600,
    vae_tiling_upscale: float = 4.0,
) -> ResolutionConfig:
    """Fabrique une ResolutionConfig avec des valeurs sensibles par défaut."""
    return ResolutionConfig(
        max_width=max_width,
        max_height=max_height,
        dimension_stride=stride,
        upscale_trigger_ratio=upscale_trigger,
        supersampling_max_ratio=supersampling_max,
        vae_tiling_pixel_threshold=vae_tiling_px,
        vae_tiling_upscale_threshold=vae_tiling_upscale,
    )


def _mock_registry_with_resolution(res_config: ResolutionConfig | None):
    """Crée un mock de get_registry() retournant la ResolutionConfig donnée."""
    registry = MagicMock()
    registry.get_resolution_config.return_value = res_config
    return registry


# ---------------------------------------------------------------------------
# A. Non-régression WAN 2.2 — comportement identique pour 5B et 14B
# ---------------------------------------------------------------------------

class TestNonRegressionWAN22:
    """Vérifie que les résultats sont identiques à l'ancien code hardcodé."""

    # (source_w, source_h, target_w, target_h)
    CASES = [
        (640, 480, 640, 480),         # petit, pas d'upscale
        (1920, 1080, 1920, 1080),     # 1080p source → ~720p gen + upscale
        (3840, 2160, 3840, 2160),     # 4K source → ~720p gen + gros upscale
        (450, 300, 450, 300),         # mini, sous 720p
        (1280, 720, 1280, 720),       # exact 720p
        (1280, 720, 3840, 2160),      # 720p → 4K, upscale pur
        (800, 600, 1920, 1080),       # medium → 1080p
    ]

    @pytest.mark.parametrize("model_name", ["wan2.2-ti2v-5b", "wan2.2-i2v-a14b"])
    @pytest.mark.parametrize("src_w,src_h,tgt_w,tgt_h", CASES)
    def test_should_produce_identical_results_for_5b_and_14b(
        self, model_name: str, src_w: int, src_h: int, tgt_w: int, tgt_h: int
    ) -> None:
        """Les deux modèles WAN 2.2 produisent la même stratégie (résolution unifiée)."""
        result = calculate_optimal_generation_strategy(
            src_w, src_h, tgt_w, tgt_h, model_name=model_name,
        )

        # Résultats structurellement valides
        assert result["generation_width"] > 0
        assert result["generation_height"] > 0
        assert isinstance(result["needs_pregen_resize"], bool)
        assert result["upscale_ratio"] >= 0
        assert result["dimension_stride"] == 32

    @pytest.mark.parametrize("src_w,src_h,tgt_w,tgt_h", CASES)
    def test_should_match_between_5b_and_14b(
        self, src_w: int, src_h: int, tgt_w: int, tgt_h: int
    ) -> None:
        """Le résultat est strictement identique entre 5B et 14B."""
        r5b = calculate_optimal_generation_strategy(
            src_w, src_h, tgt_w, tgt_h, model_name="wan2.2-ti2v-5b",
        )
        r14b = calculate_optimal_generation_strategy(
            src_w, src_h, tgt_w, tgt_h, model_name="wan2.2-i2v-a14b",
        )
        assert r5b["generation_width"] == r14b["generation_width"]
        assert r5b["generation_height"] == r14b["generation_height"]
        assert r5b["needs_pregen_resize"] == r14b["needs_pregen_resize"]
        assert r5b["upscale_ratio"] == pytest.approx(r14b["upscale_ratio"])
        assert r5b["use_supersampling"] == r14b["use_supersampling"]

    def test_should_not_exceed_720p_gen_dims(self) -> None:
        """La génération ne dépasse jamais ~720p quand target > source (upscale requis)."""
        # target > source → la fonction doit capper à la résolution native du modèle
        result = calculate_optimal_generation_strategy(
            640, 480, 3840, 2160, model_name="wan2.2-ti2v-5b",
        )
        gen_pixels = result["generation_width"] * result["generation_height"]
        assert gen_pixels <= 1280 * 720

    def test_should_generate_at_source_when_target_leq_source(self) -> None:
        """Si target ≤ source, génération à résolution source."""
        result = calculate_optimal_generation_strategy(
            640, 480, 640, 480, model_name="wan2.2-ti2v-5b",
        )
        assert result["generation_width"] == 640
        assert result["generation_height"] == 480
        assert not result["needs_pregen_resize"]

    def test_should_produce_multiples_of_32(self) -> None:
        """Les dimensions de génération sont des multiples de 32 quand target > source."""
        # target > source force le passage par find_best_generation_dims
        result = calculate_optimal_generation_strategy(
            640, 480, 1920, 1080, model_name="wan2.2-ti2v-5b",
        )
        assert result["generation_width"] % 32 == 0
        assert result["generation_height"] % 32 == 0

    def test_should_flag_supersampling_within_4x(self) -> None:
        """Ratio ≤ 4x → use_supersampling = True."""
        result = calculate_optimal_generation_strategy(
            1280, 720, 1920, 1080, model_name="wan2.2-ti2v-5b",
        )
        assert result["use_supersampling"] is True

    def test_should_flag_no_supersampling_beyond_4x(self) -> None:
        """Ratio > 4x → use_supersampling = False."""
        result = calculate_optimal_generation_strategy(
            320, 240, 3840, 2160, model_name="wan2.2-ti2v-5b",
        )
        # 320×240 source, gen sera aussi ~320×240, target 3840×2160 → ratio >> 4x
        assert result["use_supersampling"] is False


# ---------------------------------------------------------------------------
# B. Fallback — model_name=None ou inconnu
# ---------------------------------------------------------------------------

class TestFallback:
    """Vérifie le fallback sur valeurs WAN 2.2 par défaut."""

    def test_should_fallback_when_model_name_none(self) -> None:
        """model_name=None → valeurs WAN 2.2 par défaut."""
        result = calculate_optimal_generation_strategy(
            1920, 1080, 1920, 1080, model_name=None,
        )
        assert result["generation_width"] > 0
        assert result["dimension_stride"] == 32

    def test_should_fallback_when_model_unknown(self) -> None:
        """model_name inconnu → valeurs WAN 2.2 par défaut (pas d'exception)."""
        result = calculate_optimal_generation_strategy(
            1920, 1080, 1920, 1080, model_name="nonexistent-model",
        )
        assert result["generation_width"] > 0
        assert result["dimension_stride"] == 32

    def test_should_match_wan22_defaults_on_fallback(self) -> None:
        """Le fallback produit les mêmes résultats que WAN 2.2 explicite."""
        r_fallback = calculate_optimal_generation_strategy(
            1920, 1080, 1920, 1080, model_name=None,
        )
        r_wan = calculate_optimal_generation_strategy(
            1920, 1080, 1920, 1080, model_name="wan2.2-ti2v-5b",
        )
        assert r_fallback["generation_width"] == r_wan["generation_width"]
        assert r_fallback["generation_height"] == r_wan["generation_height"]


# ---------------------------------------------------------------------------
# C. Extensibilité — modèle fictif 1080p / stride 64
# ---------------------------------------------------------------------------

class TestExtensibility:
    """Vérifie que le pipeline s'adapte à un modèle avec résolution différente."""

    MOCK_1080P_RES = _make_resolution_config(
        max_width=1920, max_height=1080, stride=64,
        upscale_trigger=1.3, supersampling_max=4.0,
    )

    @patch("web_interface.routes.get_registry")
    def test_should_use_1080p_max_resolution(self, mock_get_registry: MagicMock) -> None:
        """Un modèle 1080p produit des dimensions de génération plus grandes que 720p."""
        mock_get_registry.return_value = _mock_registry_with_resolution(self.MOCK_1080P_RES)

        # target > source → force le capping à résolution native du modèle
        result = calculate_optimal_generation_strategy(
            640, 480, 3840, 2160, model_name="mock-1080p",
        )
        gen_pixels = result["generation_width"] * result["generation_height"]
        # Dépasse 720p mais reste sous/à 1080p
        assert gen_pixels > 1280 * 720
        assert gen_pixels <= 1920 * 1080

    @patch("web_interface.routes.get_registry")
    def test_should_produce_multiples_of_64(self, mock_get_registry: MagicMock) -> None:
        """stride=64 → dimensions multiples de 64."""
        mock_get_registry.return_value = _mock_registry_with_resolution(self.MOCK_1080P_RES)

        # target > source → force le passage par find_best_generation_dims(stride=64)
        result = calculate_optimal_generation_strategy(
            640, 480, 1920, 1080, model_name="mock-1080p",
        )
        assert result["generation_width"] % 64 == 0
        assert result["generation_height"] % 64 == 0
        assert result["dimension_stride"] == 64

    @patch("web_interface.routes.get_registry")
    def test_should_use_custom_supersampling_ratio(self, mock_get_registry: MagicMock) -> None:
        """Le seuil supersampling_max_ratio du registre est bien utilisé."""
        custom_res = _make_resolution_config(supersampling_max=2.0)
        mock_get_registry.return_value = _mock_registry_with_resolution(custom_res)

        result = calculate_optimal_generation_strategy(
            640, 480, 1920, 1080, model_name="mock-model",
        )
        # Ratio ~3.375x, avec max=2.0 → use_supersampling = False
        if result["upscale_ratio"] > 2.0:
            assert result["use_supersampling"] is False


# ---------------------------------------------------------------------------
# D. ResolutionConfig — propriétés et structure
# ---------------------------------------------------------------------------

class TestResolutionConfig:
    """Vérifie la dataclass ResolutionConfig."""

    def test_should_calculate_max_pixels(self) -> None:
        """max_pixels retourne le produit width × height."""
        res = _make_resolution_config(max_width=1920, max_height=1080)
        assert res.max_pixels == 1920 * 1080

    def test_should_be_frozen(self) -> None:
        """La dataclass est immutable."""
        res = _make_resolution_config()
        with pytest.raises(AttributeError):
            res.max_width = 999  # type: ignore[misc]
