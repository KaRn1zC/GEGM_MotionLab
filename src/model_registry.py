"""
Registre central des modèles — charge config/model_registry.yaml
et expose des accesseurs typés pour tous les consommateurs du projet.

Interface CLI pour les scripts bash :
    python -m src.model_registry list-models
    python -m src.model_registry get-hf-downloads <model>
    python -m src.model_registry get-expected-files <model>
    python -m src.model_registry get-verification <model>
    python -m src.model_registry get-vae <model>
    python -m src.model_registry get-symlinks <model>
"""

import json
import sys
from dataclasses import dataclass, field
from functools import lru_cache
from pathlib import Path
from typing import Any

import yaml


# ---------------------------------------------------------------------------
# Dataclasses typées
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class DiffusionFileConfig:
    """Configuration d'un fichier de diffusion."""

    filename: str
    hf_path: str
    comfyui_subdir: str
    size_bytes: int
    min_size_gb: float
    max_size_gb: float
    role: str | None  # null | high_noise | low_noise


@dataclass(frozen=True)
class VaeConfig:
    """Configuration du VAE associé à un modèle."""

    filename: str
    hf_path: str
    expected_channels: int
    min_size_gb: float
    max_size_gb: float
    version: str


@dataclass(frozen=True)
class CheckpointDetectionConfig:
    """Paramètres de détection de checkpoint sur le filesystem."""

    primary_files: list[str]
    fallback_files: list[str]
    return_type: str  # single | moe_pair


@dataclass(frozen=True)
class VerificationConfig:
    """Clés critiques pour la vérification d'intégrité."""

    diffusion_keys: list[str]
    vae_keys: list[str]


@dataclass(frozen=True)
class SymlinkConfig:
    """Définition d'un symlink modèle → composant partagé."""

    source: str
    target: str


@dataclass(frozen=True)
class RuntimeConfig:
    """Paramètres d'exécution d'un modèle."""

    timeout_seconds: int
    max_frames: int
    max_fps: int


@dataclass(frozen=True)
class ModelTextEncoderConfig:
    """Text encoder spécifique à un modèle (quand ce n'est pas le T5 partagé)."""

    filename: str
    hf_repo: str
    hf_path: str
    comfyui_subdir: str
    size_bytes: int


@dataclass(frozen=True)
class ResolutionConfig:
    """Capacités de résolution d'un modèle — pilote le pipeline de génération/upscale."""

    max_width: int
    max_height: int
    dimension_stride: int
    upscale_trigger_ratio: float
    supersampling_max_ratio: float
    vae_tiling_pixel_threshold: int
    vae_tiling_upscale_threshold: float

    @property
    def max_pixels(self) -> int:
        """Nombre maximal de pixels pour la résolution native du modèle."""
        return self.max_width * self.max_height


@dataclass(frozen=True)
class ModelConfig:
    """Configuration complète d'un modèle."""

    name: str
    display_name: str
    model_type: str
    architecture: str
    hf_repo: str
    vram_requirement: str
    estimated_time: str
    runtime: RuntimeConfig
    diffusion_files: list[DiffusionFileConfig]
    vae: VaeConfig
    checkpoint_detection: CheckpointDetectionConfig
    workflow_template: str
    verification: VerificationConfig
    symlinks: list[SymlinkConfig]
    resolution: ResolutionConfig | None = None
    workflow_template_upscale: str | None = None
    text_encoder: ModelTextEncoderConfig | None = None


@dataclass(frozen=True)
class TextEncoderConfig:
    """Configuration du text encoder partagé."""

    filename: str
    hf_repo: str
    hf_path: str
    comfyui_subdir: str
    size_bytes: int
    min_size_gb: float
    max_size_gb: float
    critical_keys: list[str]


@dataclass(frozen=True)
class ClipVisionConfig:
    """Configuration du CLIP Vision partagé."""

    filename: str
    url: str
    comfyui_subdir: str
    size_bytes: int


@dataclass(frozen=True)
class UpscalerConfig:
    """Configuration d'un upscaler."""

    filename: str
    url: str
    comfyui_subdir: str
    optional: bool


@dataclass(frozen=True)
class SharedComponentsConfig:
    """Composants partagés entre tous les modèles."""

    text_encoder: TextEncoderConfig
    clip_vision: ClipVisionConfig
    upscalers: list[UpscalerConfig]


@dataclass(frozen=True)
class DownloadManifest:
    """Manifeste de téléchargement HuggingFace pour un modèle."""

    repo: str                     # Repo principal (diffusion + vae)
    files: list[dict[str, str]]   # [{hf_path, dest_subdir, filename, repo}]


# ---------------------------------------------------------------------------
# Registre (singleton via @lru_cache)
# ---------------------------------------------------------------------------

def _find_registry_path() -> Path:
    """Résout le chemin vers model_registry.yaml quel que soit le contexte d'exécution."""
    candidates = [
        Path("config/model_registry.yaml"),
        Path("/workspace/config/model_registry.yaml"),
        Path(__file__).resolve().parent.parent / "config" / "model_registry.yaml",
    ]
    for p in candidates:
        if p.exists():
            return p
    raise FileNotFoundError(
        "config/model_registry.yaml introuvable. "
        f"Chemins testés : {[str(c) for c in candidates]}"
    )


def _parse_diffusion_file(raw: dict[str, Any]) -> DiffusionFileConfig:
    """Parse un bloc diffusion_files en dataclass."""
    return DiffusionFileConfig(
        filename=raw["filename"],
        hf_path=raw["hf_path"],
        comfyui_subdir=raw["comfyui_subdir"],
        size_bytes=raw["size_bytes"],
        min_size_gb=raw["min_size_gb"],
        max_size_gb=raw["max_size_gb"],
        role=raw.get("role"),
    )


def _parse_model_text_encoder(raw: dict[str, Any] | None) -> ModelTextEncoderConfig | None:
    """Parse un bloc text_encoder model-spécifique optionnel."""
    if not raw:
        return None
    return ModelTextEncoderConfig(
        filename=raw["filename"],
        hf_repo=raw["hf_repo"],
        hf_path=raw["hf_path"],
        comfyui_subdir=raw["comfyui_subdir"],
        size_bytes=raw["size_bytes"],
    )


def _parse_resolution(raw: dict[str, Any] | None) -> ResolutionConfig | None:
    """Parse un bloc resolution optionnel en dataclass."""
    if not raw:
        return None
    return ResolutionConfig(
        max_width=raw["max_width"],
        max_height=raw["max_height"],
        dimension_stride=raw["dimension_stride"],
        upscale_trigger_ratio=float(raw["upscale_trigger_ratio"]),
        supersampling_max_ratio=float(raw["supersampling_max_ratio"]),
        vae_tiling_pixel_threshold=raw["vae_tiling_pixel_threshold"],
        vae_tiling_upscale_threshold=float(raw["vae_tiling_upscale_threshold"]),
    )


def _parse_model(name: str, raw: dict[str, Any]) -> ModelConfig:
    """Parse un bloc modèle complet en dataclass."""
    rt = raw["runtime"]
    vae = raw["vae"]
    cd = raw["checkpoint_detection"]
    ver = raw["verification"]

    return ModelConfig(
        name=name,
        display_name=raw["display_name"],
        model_type=raw["model_type"],
        architecture=raw["architecture"],
        hf_repo=raw["hf_repo"],
        vram_requirement=raw["vram_requirement"],
        estimated_time=raw["estimated_time"],
        runtime=RuntimeConfig(
            timeout_seconds=rt["timeout_seconds"],
            max_frames=rt["max_frames"],
            max_fps=rt["max_fps"],
        ),
        diffusion_files=[_parse_diffusion_file(f) for f in raw["diffusion_files"]],
        vae=VaeConfig(
            filename=vae["filename"],
            hf_path=vae["hf_path"],
            expected_channels=vae["expected_channels"],
            min_size_gb=vae["min_size_gb"],
            max_size_gb=vae["max_size_gb"],
            version=vae["version"],
        ),
        checkpoint_detection=CheckpointDetectionConfig(
            primary_files=cd["primary_files"],
            fallback_files=cd["fallback_files"],
            return_type=cd["return_type"],
        ),
        workflow_template=raw["workflow_template"],
        verification=VerificationConfig(
            diffusion_keys=ver["diffusion_keys"],
            vae_keys=ver["vae_keys"],
        ),
        symlinks=[
            SymlinkConfig(source=s["source"], target=s["target"])
            for s in raw.get("symlinks", [])
        ],
        resolution=_parse_resolution(raw.get("resolution")),
        workflow_template_upscale=raw.get("workflow_template_upscale"),
        text_encoder=_parse_model_text_encoder(raw.get("text_encoder")),
    )


def _parse_shared(raw: dict[str, Any]) -> SharedComponentsConfig:
    """Parse le bloc shared_components."""
    te = raw["text_encoder"]
    cv = raw["clip_vision"]

    return SharedComponentsConfig(
        text_encoder=TextEncoderConfig(
            filename=te["filename"],
            hf_repo=te["hf_repo"],
            hf_path=te["hf_path"],
            comfyui_subdir=te["comfyui_subdir"],
            size_bytes=te["size_bytes"],
            min_size_gb=te["min_size_gb"],
            max_size_gb=te["max_size_gb"],
            critical_keys=te["critical_keys"],
        ),
        clip_vision=ClipVisionConfig(
            filename=cv["filename"],
            url=cv["url"],
            comfyui_subdir=cv["comfyui_subdir"],
            size_bytes=cv["size_bytes"],
        ),
        upscalers=[
            UpscalerConfig(
                filename=u["filename"],
                url=u["url"],
                comfyui_subdir=u["comfyui_subdir"],
                optional=u["optional"],
            )
            for u in raw.get("upscalers", [])
        ],
    )


class ModelRegistry:
    """
    Registre central des modèles — chargé depuis config/model_registry.yaml.

    Fournit des accesseurs typés pour tous les consommateurs (Python et bash via CLI).
    Instanciation unique via get_registry().
    """

    def __init__(self, yaml_path: Path | None = None) -> None:
        path = yaml_path or _find_registry_path()
        with open(path, encoding="utf-8") as fh:
            data = yaml.safe_load(fh)

        self._models: dict[str, ModelConfig] = {
            name: _parse_model(name, raw)
            for name, raw in data.get("models", {}).items()
        }
        self._shared: SharedComponentsConfig = _parse_shared(data["shared_components"])
        self._detection_priority: list[str] = data.get("detection_priority", [])

    # --- Accesseurs modèles ---

    def get_model(self, name: str) -> ModelConfig | None:
        """Retourne la config complète d'un modèle, ou None si inconnu."""
        return self._models.get(name)

    def list_models(self) -> list[str]:
        """Liste les noms de tous les modèles enregistrés."""
        return list(self._models.keys())

    def get_detection_priority(self) -> list[tuple[str, str]]:
        """Retourne la liste de priorité [(model_name, model_type)] pour la détection auto."""
        result: list[tuple[str, str]] = []
        for name in self._detection_priority:
            model = self._models.get(name)
            if model:
                result.append((name, model.model_type))
        return result

    def get_diffusion_files(self, name: str) -> list[DiffusionFileConfig] | None:
        """Retourne les fichiers de diffusion d'un modèle, ou None si inconnu."""
        model = self._models.get(name)
        return model.diffusion_files if model else None

    def get_vae_config(self, name: str) -> VaeConfig | None:
        """Retourne la config VAE d'un modèle, ou None si inconnu."""
        model = self._models.get(name)
        return model.vae if model else None

    def get_checkpoint_detection(self, name: str) -> CheckpointDetectionConfig | None:
        """Retourne la config de détection checkpoint, ou None si inconnu."""
        model = self._models.get(name)
        return model.checkpoint_detection if model else None

    def get_workflow_template(self, name: str) -> str | None:
        """Retourne l'ID du template workflow associé, ou None si inconnu."""
        model = self._models.get(name)
        return model.workflow_template if model else None

    def get_timeout(self, name: str) -> int | None:
        """Retourne le timeout en secondes, ou None si inconnu."""
        model = self._models.get(name)
        return model.runtime.timeout_seconds if model else None

    def get_verification_config(self, name: str) -> VerificationConfig | None:
        """Retourne les clés de vérification, ou None si inconnu."""
        model = self._models.get(name)
        return model.verification if model else None

    def get_symlinks(self, name: str) -> list[SymlinkConfig] | None:
        """Retourne les symlinks à créer, ou None si inconnu."""
        model = self._models.get(name)
        return model.symlinks if model else None

    def get_resolution_config(self, name: str) -> ResolutionConfig | None:
        """Retourne la config de résolution d'un modèle, ou None si inconnu/absent."""
        model = self._models.get(name)
        return model.resolution if model else None

    def get_upscale_workflow_template(self, name: str) -> str | None:
        """Retourne l'ID du template workflow upscale, ou None si inconnu/absent."""
        model = self._models.get(name)
        return model.workflow_template_upscale if model else None

    # --- Accesseurs composants partagés ---

    def get_shared_components(self) -> SharedComponentsConfig:
        """Retourne la config des composants partagés (T5, CLIP, upscalers)."""
        return self._shared

    # --- Manifeste de téléchargement ---

    def get_hf_download_manifest(self, name: str) -> DownloadManifest | None:
        """
        Construit le manifeste de téléchargement HuggingFace pour un modèle.

        Inclut les fichiers de diffusion, le VAE et le text encoder (partagé ou model-spécifique).
        Chaque fichier porte son propre champ 'repo' pour gérer les modèles multi-repo (ex: LTX).
        """
        model = self._models.get(name)
        if not model:
            return None

        files: list[dict[str, str]] = []

        # Fichiers de diffusion
        for df in model.diffusion_files:
            files.append({
                "hf_path": df.hf_path,
                "dest_subdir": df.comfyui_subdir,
                "filename": df.filename,
                "repo": model.hf_repo,
            })

        # VAE — skip si intégré dans le checkpoint
        if model.vae.filename != "integrated":
            files.append({
                "hf_path": model.vae.hf_path,
                "dest_subdir": "vae",
                "filename": model.vae.filename,
                "repo": model.hf_repo,
            })

        # Text encoder — model-spécifique ou T5 partagé
        if model.text_encoder:
            files.append({
                "hf_path": model.text_encoder.hf_path,
                "dest_subdir": model.text_encoder.comfyui_subdir,
                "filename": model.text_encoder.filename,
                "repo": model.text_encoder.hf_repo,
            })
        else:
            te = self._shared.text_encoder
            files.append({
                "hf_path": te.hf_path,
                "dest_subdir": te.comfyui_subdir,
                "filename": te.filename,
                "repo": te.hf_repo,
            })

        return DownloadManifest(repo=model.hf_repo, files=files)

    def get_expected_files(self, name: str) -> list[dict[str, Any]] | None:
        """
        Retourne la liste des fichiers attendus avec leurs tailles minimales.

        Utilisé par docker-entrypoint.sh pour vérifier la présence des fichiers.
        """
        model = self._models.get(name)
        if not model:
            return None

        result: list[dict[str, Any]] = []
        for df in model.diffusion_files:
            result.append({
                "filename": df.filename,
                "min_size_gb": df.min_size_gb,
                "subdir": df.comfyui_subdir,
            })
        return result


@lru_cache(maxsize=1)
def get_registry(yaml_path: str | None = None) -> ModelRegistry:
    """Retourne l'instance singleton du registre."""
    path = Path(yaml_path) if yaml_path else None
    return ModelRegistry(yaml_path=path)


# ---------------------------------------------------------------------------
# Interface CLI (pour les scripts bash)
# ---------------------------------------------------------------------------

def _cli_list_models(registry: ModelRegistry) -> None:
    """Affiche la liste des modèles enregistrés."""
    for name in registry.list_models():
        model = registry.get_model(name)
        print(f"{name}  ({model.display_name})")


def _cli_get_hf_downloads(registry: ModelRegistry, model_name: str) -> None:
    """Affiche le manifeste de téléchargement en JSON."""
    manifest = registry.get_hf_download_manifest(model_name)
    if not manifest:
        print(f"Modèle inconnu: {model_name}", file=sys.stderr)
        sys.exit(1)
    print(json.dumps({"repo": manifest.repo, "files": manifest.files}, indent=2))


def _cli_get_expected_files(registry: ModelRegistry, model_name: str) -> None:
    """Affiche les fichiers attendus en JSON."""
    files = registry.get_expected_files(model_name)
    if files is None:
        print(f"Modèle inconnu: {model_name}", file=sys.stderr)
        sys.exit(1)
    print(json.dumps(files, indent=2))


def _cli_get_verification(registry: ModelRegistry, model_name: str) -> None:
    """Affiche les clés de vérification en JSON."""
    config = registry.get_verification_config(model_name)
    if not config:
        print(f"Modèle inconnu: {model_name}", file=sys.stderr)
        sys.exit(1)
    print(json.dumps({
        "diffusion_keys": config.diffusion_keys,
        "vae_keys": config.vae_keys,
    }, indent=2))


def _cli_get_vae(registry: ModelRegistry, model_name: str) -> None:
    """Affiche la config VAE en JSON."""
    vae = registry.get_vae_config(model_name)
    if not vae:
        print(f"Modèle inconnu: {model_name}", file=sys.stderr)
        sys.exit(1)
    print(json.dumps({
        "filename": vae.filename,
        "hf_path": vae.hf_path,
        "expected_channels": vae.expected_channels,
        "min_size_gb": vae.min_size_gb,
        "max_size_gb": vae.max_size_gb,
        "version": vae.version,
    }, indent=2))


def _cli_get_symlinks(registry: ModelRegistry, model_name: str) -> None:
    """Affiche les symlinks à créer en JSON."""
    symlinks = registry.get_symlinks(model_name)
    if symlinks is None:
        print(f"Modèle inconnu: {model_name}", file=sys.stderr)
        sys.exit(1)
    print(json.dumps(
        [{"source": s.source, "target": s.target} for s in symlinks],
        indent=2,
    ))


def main() -> None:
    """Point d'entrée CLI : python -m src.model_registry <commande> [modèle]."""
    if len(sys.argv) < 2:
        print("Usage: python -m src.model_registry <commande> [modèle]", file=sys.stderr)
        print("Commandes: list-models, get-hf-downloads, get-expected-files, "
              "get-verification, get-vae, get-symlinks", file=sys.stderr)
        sys.exit(1)

    command = sys.argv[1]
    registry = get_registry()

    if command == "list-models":
        _cli_list_models(registry)
    elif command in ("get-hf-downloads", "get-expected-files", "get-verification",
                     "get-vae", "get-symlinks"):
        if len(sys.argv) < 3:
            print(f"Usage: python -m src.model_registry {command} <model_name>", file=sys.stderr)
            sys.exit(1)
        model_name = sys.argv[2]
        dispatch = {
            "get-hf-downloads": _cli_get_hf_downloads,
            "get-expected-files": _cli_get_expected_files,
            "get-verification": _cli_get_verification,
            "get-vae": _cli_get_vae,
            "get-symlinks": _cli_get_symlinks,
        }
        dispatch[command](registry, model_name)
    else:
        print(f"Commande inconnue: {command}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
