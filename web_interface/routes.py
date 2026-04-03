"""
Routes API pour l'interface Flask
"""

import os
import asyncio
from datetime import datetime
from pathlib import Path
from flask import Blueprint, request, jsonify, current_app, send_file, render_template
from werkzeug.utils import secure_filename
import subprocess
import sys


from src.logger import get_logger
from src.comfyui_client import ComfyUISession, WorkflowProgress, test_comfyui_connection
from src.model_registry import get_registry
from src.owncloud_uploader import OwnCloudUploader, upload_cinemagraph
from workflows.workflow_manager import workflow_manager
from web_interface.jobs import JobManager, JobStatus

import time
from PIL import Image


# ============================================
# PROGRESSION TEMPS RÉEL COMFYUI → JOB
# ============================================

_PROGRESS_POSTPROC_START = 0.85   # ffmpeg resize + crossfade


class ComfyUIProgressTracker:
    """
    Traduit la progression brute ComfyUI en progression Job linéaire et fidèle.

    Détection de phase basée sur le taux de progression réel (pas le compteur de resets) :
    - Reset (100% → bas) + progression lente (>7s/update) = sampling
    - Reset (100% → bas) + progression rapide (<7s/update) = VAE decode
    - 100% maintenu sans changement pendant >15s = node silencieux (HAT-L)
    - Progression ultra-rapide (>5%/<0.5s) = VHS_VideoCombine

    Compatible multi-sampling (WAN 14B MoE: 2 phases sampling séparées)
    et single-sampling (LTX 2.3: 1 phase sampling).

    Args:
        job_manager: Gestionnaire de jobs pour les mises à jour
        job_id: ID du job en cours
        total_frames: Nombre total de frames à générer (pour l'estimation HAT-L)
        has_upscale: True si le workflow inclut un upscale HAT-L post-génération
    """

    # Au-delà de ce seuil (secondes entre 2 updates), une phase est classée
    # "sampling" (lente). En-dessous, c'est du VAE decode (rapide).
    # LTX sampling: ~9s/update, WAN sampling: ~34s/update, VAE: ~4s/update
    _RATE_THRESHOLD_SECONDS = 7.0

    def __init__(
        self,
        job_manager: JobManager,
        job_id: str,
        total_frames: int,
        has_upscale: bool,
    ):
        self.job_manager = job_manager
        self.job_id = job_id
        self.total_frames = total_frames
        self.has_upscale = has_upscale

        # État interne
        self._last_comfyui_progress: float = -1.0
        self._last_job_progress: float = 0.05
        self._last_step_label: str = ""

        # Détection de phase par taux de progression
        self._current_phase: str = "setup"
        self._heavy_phase_count: int = 0
        self._last_progress_time: float = time.monotonic()
        self._last_real_change_time: float = time.monotonic()

        # Classification par taux — après un reset, on collecte les 3 premières
        # updates pour mesurer le taux et classifier la phase
        self._pending_classification: bool = False
        self._phase_start_time: float = 0.0
        self._phase_update_count: int = 0

        # Phase silencieuse (HAT-L upscale)
        self._silent_phase_start: float | None = None
        self._silent_phase_estimated_duration: float | None = None
        self._had_vae_phase: bool = False  # Au moins 1 phase rapide (VAE) observée

        # Calibration VAE decode
        self._vae_start_time: float | None = None
        self._vae_progress_count: int = 0
        self._calibrated_time_per_frame: float | None = None

    def __call__(self, workflow: WorkflowProgress) -> None:
        """Appelé toutes les ~2s par wait_for_completion()."""
        now = time.monotonic()

        if workflow.status in ("completed", "error"):
            return

        progress = workflow.progress
        progress_changed = progress != self._last_comfyui_progress

        if progress_changed:
            self._detect_phase(progress, now)
            self._last_comfyui_progress = progress
            self._last_real_change_time = now

        # Détection phase silencieuse : 100% maintenu sans changement > 15s
        # Exige qu'au moins une phase VAE (rapide) ait été observée pour éviter
        # les faux positifs pendant le setup ou entre deux phases de sampling
        time_since_change = now - self._last_real_change_time
        if (
            self._last_comfyui_progress >= 0.99
            and time_since_change > 15.0
            and self._silent_phase_start is None
            and self._had_vae_phase
        ):
            self._enter_silent_phase(now)

        # Calcul progression Job
        job_progress = self._compute_job_progress(progress, now)
        step_label = self._get_step_label(now)

        # Mise à jour si changement significatif (>0.5% ou label différent)
        progress_delta = abs(job_progress - self._last_job_progress)
        if progress_delta >= 0.005 or step_label != self._last_step_label:
            self.job_manager.update_job(
                self.job_id,
                progress=round(job_progress, 3),
                current_step=step_label,
            )
            self._last_job_progress = job_progress
            self._last_step_label = step_label

    def _detect_phase(self, progress: float, now: float) -> None:
        """
        Détecte la phase en cours via le taux de progression.

        Après chaque reset (100% → bas), entre en classification pendante.
        Après 3 updates, mesure le temps moyen entre updates et classifie :
        - > 7s/update → sampling (lent)
        - < 7s/update → VAE decode (rapide)

        Compatible avec WAN 14B MoE (2 phases sampling + 1 VAE)
        et LTX 2.3 (1 sampling + 1 VAE).
        """
        prev = self._last_comfyui_progress
        prev_phase = self._current_phase
        dt = now - self._last_progress_time
        self._last_progress_time = now

        # Ignorer le premier callback (prev=-1 → état initial)
        if prev < 0:
            return

        # Reset de progression : un nouveau node lourd commence
        if prev >= 0.90 and progress < 0.30:
            self._heavy_phase_count += 1
            self._silent_phase_start = None
            self._silent_phase_estimated_duration = None

            # Entrer en classification pendante — on ne sait pas encore
            # si c'est du sampling (lent) ou du VAE decode (rapide)
            self._pending_classification = True
            self._phase_start_time = now
            self._phase_update_count = 0
            self._current_phase = "classifying"

        # Pendant la classification : compter les updates
        elif self._pending_classification:
            self._phase_update_count += 1

            if self._phase_update_count >= 3:
                # Assez de données pour mesurer le taux
                elapsed = now - self._phase_start_time
                avg_interval = elapsed / self._phase_update_count

                if avg_interval > self._RATE_THRESHOLD_SECONDS:
                    # Progression lente → sampling
                    self._current_phase = "sampling"
                else:
                    # Progression rapide → VAE decode
                    self._current_phase = "vae_decode"
                    self._had_vae_phase = True
                    self._vae_start_time = self._phase_start_time
                    self._vae_progress_count = self._phase_update_count

                self._pending_classification = False

        # Progression ultra-rapide (>5% en <0.5s) = VHS_VideoCombine
        elif dt > 0 and dt < 0.5 and (progress - prev) > 0.05:
            if self._current_phase != "combine":
                self._current_phase = "combine"
                self._silent_phase_start = None
                self._pending_classification = False

        # Calibration pendant le VAE decode confirmé
        if self._current_phase == "vae_decode" and self._vae_start_time:
            self._vae_progress_count += 1
            elapsed = now - self._vae_start_time
            if elapsed > 3.0 and self._vae_progress_count > 5:
                vae_time_per_frame = elapsed / self._vae_progress_count
                self._calibrated_time_per_frame = vae_time_per_frame * 1.8

        if prev_phase != self._current_phase:
            logger.info(
                f"Phase progression: {prev_phase} → {self._current_phase} "
                f"(heavy_count={self._heavy_phase_count}, progress={progress:.0%})"
            )

    def _enter_silent_phase(self, now: float) -> None:
        """Active l'estimation temporelle pour le HAT-L upscale."""
        if not self.has_upscale:
            return

        self._current_phase = "upscale"
        self._silent_phase_start = now

        if self._calibrated_time_per_frame:
            self._silent_phase_estimated_duration = (
                self._calibrated_time_per_frame * self.total_frames
            )
        else:
            self._silent_phase_estimated_duration = 6.0 * self.total_frames

        logger.info(
            f"Phase silencieuse (HAT-L upscale) — estimation: "
            f"{self._silent_phase_estimated_duration:.0f}s "
            f"({self.total_frames} frames"
            f"{', calibré' if self._calibrated_time_per_frame else ', fallback 6s/f'})"
        )

    def _compute_job_progress(self, comfyui_progress: float, now: float) -> float:
        """
        Mappe la progression ComfyUI vers la progression Job (5% → 85%).

        Plages :
        - setup (5→10%)     : nodes de configuration rapides
        - sampling (10→35%) : génération latent
        - vae_decode (35→50%) : décodage frames
        - upscale (50→80%)  : HAT-L 4x (estimation temporelle)
        - combine (80→85%)  : VHS_VideoCombine
        """
        phase = self._current_phase

        if phase == "setup":
            return 0.05

        elif phase == "classifying":
            # En attente de classification — garder la dernière valeur connue
            return self._last_job_progress

        elif phase == "sampling":
            return 0.10 + comfyui_progress * 0.25

        elif phase == "vae_decode":
            return 0.35 + comfyui_progress * 0.15

        elif phase == "upscale":
            if self._silent_phase_start and self._silent_phase_estimated_duration:
                elapsed = now - self._silent_phase_start
                ratio = min(elapsed / self._silent_phase_estimated_duration, 0.95)
                return 0.50 + ratio * 0.30
            return 0.50

        elif phase == "combine":
            return 0.80 + comfyui_progress * 0.05

        return 0.05

    def _get_step_label(self, now: float) -> str:
        """Retourne un label humain pour l'étape en cours."""
        phase = self._current_phase

        if phase == "setup":
            return "Chargement du modèle..."
        elif phase == "classifying":
            return "Génération en cours..."
        elif phase == "sampling":
            pct = int(self._last_comfyui_progress * 100)
            return f"Génération du cinemagraph ({pct}%)"
        elif phase == "vae_decode":
            pct = int(self._last_comfyui_progress * 100)
            return f"Décodage vidéo ({pct}%)"
        elif phase == "upscale":
            if self._silent_phase_start and self._silent_phase_estimated_duration:
                elapsed = now - self._silent_phase_start
                remaining = max(0, self._silent_phase_estimated_duration - elapsed)
                minutes = int(remaining // 60)
                seconds = int(remaining % 60)
                if minutes > 0:
                    return f"Upscale HAT-L 4x... ~{minutes}min{seconds:02d}s restantes"
                return f"Upscale HAT-L 4x... ~{seconds}s restantes"
            return "Upscale HAT-L 4x..."
        elif phase == "combine":
            return "Encodage vidéo finale..."

        return "Génération en cours..."


# Cache global pour le modèle HAT 2x (chargé une seule fois)
_hat_2x_model = None


def _hat_2x_upscale(image_path: Path) -> Image.Image | None:
    """
    Upscale une image avec HAT 2x via spandrel (super-résolution ML).

    Charge le modèle au premier appel puis le garde en cache.
    Retourne l'image PIL upscalée 2x, ou None si le modèle est indisponible.

    Args:
        image_path: Chemin vers l'image source

    Returns:
        Image PIL upscalée 2x ou None en cas d'échec
    """
    global _hat_2x_model

    try:
        import torch
        import spandrel
        import numpy as np

        # Chercher le fichier HAT 2x dans les emplacements ComfyUI
        hat_paths = [
            Path("/workspace/comfyui/ComfyUI/models/upscale_models/HAT_SRx2.pth"),
            Path("models/upscale_models/HAT_SRx2.pth"),
        ]
        hat_path = None
        for p in hat_paths:
            if p.exists():
                hat_path = p
                break

        if hat_path is None:
            logger.warning("   HAT_SRx2.pth introuvable dans les dossiers upscale_models")
            return None

        # Charger le modèle (une seule fois)
        if _hat_2x_model is None:
            logger.info(f"   Chargement HAT 2x depuis {hat_path}...")
            _hat_2x_model = spandrel.ModelLoader().load_from_file(hat_path)
            _hat_2x_model = _hat_2x_model.eval()
            if torch.cuda.is_available():
                _hat_2x_model = _hat_2x_model.cuda()
            logger.info("   ✅ HAT 2x chargé")

        # Préparer l'image : PIL → tensor [1, C, H, W] float32 [0, 1]
        with Image.open(image_path) as img:
            img_rgb = img.convert("RGB")
            img_array = np.array(img_rgb).astype(np.float32) / 255.0
            tensor = torch.from_numpy(img_array).permute(2, 0, 1).unsqueeze(0)
            if torch.cuda.is_available():
                tensor = tensor.cuda()

        # Inférence
        with torch.no_grad():
            output = _hat_2x_model(tensor)

        # Tensor → PIL
        output_np = output.squeeze(0).permute(1, 2, 0).clamp(0, 1).cpu().numpy()
        output_np = (output_np * 255).astype(np.uint8)
        return Image.fromarray(output_np)

    except ImportError:
        logger.warning("   spandrel ou torch non disponible pour HAT 2x")
        return None
    except Exception as e:
        logger.warning(f"   Erreur HAT 2x: {e}")
        return None


def find_best_generation_dims(
    width: int, height: int, multiple: int = 32
) -> tuple[int, int]:
    """
    Trouve les dimensions multiples de `multiple` les plus proches du ratio original.

    Teste les 4 combinaisons (floor/ceil) x (width/height) et retourne celle
    qui préserve le mieux le ratio d'aspect, évitant le drift systématique du floor.

    Args:
        width: Largeur à ajuster
        height: Hauteur à ajuster
        multiple: Multiple cible (défaut: 32)

    Returns:
        (width, height) ajustés aux multiples de `multiple` avec ratio optimal
    """
    if width <= 0 or height <= 0:
        return (width, height)

    original_ratio = width / height

    w_floor = (width // multiple) * multiple
    w_ceil = w_floor + (multiple if w_floor != width else 0)
    h_floor = (height // multiple) * multiple
    h_ceil = h_floor + (multiple if h_floor != height else 0)

    candidates = [
        (w_floor, h_floor),
        (w_floor, h_ceil),
        (w_ceil, h_floor),
        (w_ceil, h_ceil),
    ]
    # Filtrer les candidats à 0
    candidates = [(w, h) for w, h in candidates if w > 0 and h > 0]

    return min(candidates, key=lambda c: abs(c[0] / c[1] - original_ratio))


def calculate_optimal_resolution(
    source_width: int, source_height: int, target_width: int, target_height: int
) -> tuple:
    """
    Calcule la résolution optimale en conservant le ratio

    Args:
        source_width, source_height: Résolution source
        target_width, target_height: Résolution demandée

    Returns:
        (final_width, final_height): Résolution ajustée (multiple de 32)
    """
    # Ratio de l'image source
    source_ratio = source_width / source_height

    # Calculer selon le ratio source
    if target_width / target_height > source_ratio:
        # Limité par la hauteur
        raw_height = target_height
        raw_width = int(raw_height * source_ratio)
    else:
        # Limité par la largeur
        raw_width = target_width
        raw_height = int(raw_width / source_ratio)

    # Arrondi intelligent : teste les 4 combinaisons floor/ceil pour le meilleur ratio
    # Requis par le VAE WAN 2.2 (multiples de 32)
    return find_best_generation_dims(raw_width, raw_height)


def calculate_optimal_generation_strategy(
    source_width: int,
    source_height: int,
    target_width: int,
    target_height: int,
    model_name: str | None = None,
) -> dict:
    """
    Calcule la stratégie de génération optimale, adaptée au modèle actif.

    Génère à la résolution cible demandée (ajustée au stride du modèle),
    clampée au max du modèle si elle le dépasse.

    Args:
        source_width, source_height: Dimensions image source (déjà ajustées au stride)
        target_width, target_height: Dimensions cible finales
        model_name: Nom du modèle dans le registre (fallback WAN 2.2 si None)

    Returns:
        dict avec generation_width, generation_height, needs_pregen_resize,
        resize_type, upscale_ratio, total_ratio, use_supersampling,
        dimension_stride, strategy
    """
    from src.model_registry import ResolutionConfig

    # Lookup registre avec fallback WAN 2.2 legacy
    res: ResolutionConfig | None = None
    try:
        registry = get_registry()
        res = registry.get_resolution_config(model_name) if model_name else None
    except Exception:
        pass

    if not res:
        res = ResolutionConfig(
            max_width=1280, max_height=720, dimension_stride=32,
            upscale_trigger_ratio=1.5, supersampling_max_ratio=4.0,
            vae_tiling_pixel_threshold=2073600, vae_tiling_upscale_threshold=4.0,
        )

    max_w = res.max_width
    max_h = res.max_height
    max_pixels = res.max_pixels
    stride = res.dimension_stride

    # Calculer ratios et dimensions
    source_pixels = source_width * source_height
    target_pixels = target_width * target_height
    total_ratio = target_pixels / source_pixels
    aspect_ratio = source_width / source_height

    # Génération = résolution cible, clampée au max du modèle
    # La résolution cible est déjà ajustée au stride par l'appelant
    gen_w = min(target_width, max_w)
    gen_h = min(target_height, max_h)

    # Si le clampage a modifié une dimension, recalculer l'autre pour le ratio
    if gen_w < target_width or gen_h < target_height:
        if aspect_ratio >= (gen_w / gen_h):
            gen_h = int(gen_w / aspect_ratio)
        else:
            gen_w = int(gen_h * aspect_ratio)

    # Ajuster aux multiples du stride
    gen_w, gen_h = find_best_generation_dims(gen_w, gen_h, multiple=stride)

    # Sécurité : ne pas dépasser le max pixels du modèle
    if gen_w * gen_h > max_pixels:
        if aspect_ratio >= (max_w / max_h):
            raw_w = max_w - stride
            raw_h = int(raw_w / aspect_ratio)
        else:
            raw_h = max_h - stride
            raw_w = int(raw_h * aspect_ratio)
        gen_w, gen_h = find_best_generation_dims(raw_w, raw_h, multiple=stride)

    # Déterminer si redimensionnement pré-génération nécessaire
    needs_pregen_resize = gen_w != source_width or gen_h != source_height

    # Déterminer type de redimensionnement pré-génération
    if source_pixels < gen_w * gen_h:
        resize_type = "upscale"
        strategy_desc = f"Upscale HAT 2x + Lanczos pré-génération: {source_width}x{source_height} → {gen_w}x{gen_h}"
    elif source_pixels > gen_w * gen_h:
        resize_type = "downscale"
        strategy_desc = f"Downscale Lanczos pré-génération: {source_width}x{source_height} → {gen_w}x{gen_h}"
    else:
        resize_type = "none"
        strategy_desc = f"Génération directe à résolution source: {gen_w}x{gen_h}"

    # Calculer ratio upscale post-génération
    gen_pixels = gen_w * gen_h
    if gen_pixels == 0:
        gen_w, gen_h = stride, stride
        gen_pixels = gen_w * gen_h
    upscale_ratio = (target_width * target_height) / gen_pixels
    use_supersampling = upscale_ratio <= res.supersampling_max_ratio

    return {
        "generation_width": gen_w,
        "generation_height": gen_h,
        "needs_pregen_resize": needs_pregen_resize,
        "resize_type": resize_type,
        "upscale_ratio": upscale_ratio,
        "total_ratio": total_ratio,
        "use_supersampling": use_supersampling,
        "dimension_stride": stride,
        "strategy": strategy_desc,
    }


logger = get_logger("flask_routes")

# Blueprints
api_bp = Blueprint("api", __name__)
main_bp = Blueprint("main", __name__)


# Helper functions
def allowed_file(filename):
    """Vérifie si l'extension du fichier est autorisée"""
    return (
        "." in filename
        and filename.rsplit(".", 1)[1].lower()
        in current_app.config["ALLOWED_EXTENSIONS"]
    )


def get_file_path(filename):
    """Retourne le chemin complet d'un fichier uploadé"""
    return os.path.join(current_app.config["UPLOAD_FOLDER"], filename)


async def process_cinemagraph_generation(job_id: str):
    """
    Traite la génération d'un cinemagraph de manière asynchrone

    Args:
        job_id: ID du job à traiter
    """
    # Récupérer depuis le contexte Flask
    from flask import current_app as app

    try:
        job_manager = app.job_manager
        comfyui_config = app.comfyui_config
    except RuntimeError:
        # Contexte Flask non disponible - ne devrait jamais arriver après correction #2
        logger.error(f"Contexte Flask non disponible pour job {job_id}")
        return

    job = job_manager.get_job(job_id)

    if not job:
        logger.error(f"Job non trouvé: {job_id}")
        return

    try:
        # 1. Préparer le workflow
        job_manager.update_job(
            job_id,
            status=JobStatus.PROCESSING,
            current_step="Préparation du workflow",
            progress=0.02,
        )

        # Sélection automatique du workflow selon résolution
        img_path = Path(job.input_image)
        with Image.open(job.input_image) as img:
            source_width, source_height = img.size

        # Résolution demandée dans les paramètres (déjà ajustée multiples 32 par generate_cinemagraph)
        target_width = job.parameters.get("width", source_width)
        target_height = job.parameters.get("height", source_height)

        # Dimensions exactes demandées par l'utilisateur (avant ajustement multiples de 32)
        user_target_width = job.parameters.get("user_target_width", target_width)
        user_target_height = job.parameters.get("user_target_height", target_height)

        # Détecter le modèle disponible AVANT le calcul de stratégie
        from workflows.workflow_manager import WorkflowTemplate

        temp_template = WorkflowTemplate({"parameters": {}, "workflow": {}})
        detected_model, model_type = temp_template._detect_available_model()
        logger.info(f"🤖 Modèle détecté: {detected_model} (type: {model_type})")

        # Obtenir la config du modèle depuis le registre (pour stride, seuils, etc.)
        model_cfg = None
        try:
            _registry = get_registry()
            model_cfg = _registry.get_model(detected_model)
        except Exception:
            pass

        # Stride d'alignement depuis le registre (fallback 32)
        stride = 32
        if model_cfg and model_cfg.resolution:
            stride = model_cfg.resolution.dimension_stride

        # Ajuster dimensions source et cible au stride du modèle
        adjusted_source_width, adjusted_source_height = find_best_generation_dims(
            source_width, source_height, multiple=stride
        )
        adjusted_target_width, adjusted_target_height = find_best_generation_dims(
            target_width, target_height, multiple=stride
        )

        # Calculer la stratégie de génération optimale selon le modèle
        strategy = calculate_optimal_generation_strategy(
            adjusted_source_width,
            adjusted_source_height,
            adjusted_target_width,
            adjusted_target_height,
            model_name=detected_model,
        )

        generation_width = strategy["generation_width"]
        generation_height = strategy["generation_height"]
        needs_pregen_resize = strategy["needs_pregen_resize"]
        resize_type = strategy["resize_type"]
        upscale_ratio = strategy["upscale_ratio"]
        use_supersampling = strategy["use_supersampling"]

        image_to_upload = job.input_image
        upload_filename = img_path.name

        # Étape 1: Ajustement multiples de 32 (si nécessaire)
        needs_resize_to_adjusted = (
            adjusted_source_width != source_width
            or adjusted_source_height != source_height
        )

        if needs_resize_to_adjusted:
            logger.info(
                f"📐 Ajustement multiples de {stride}: "
                f"{source_width}x{source_height} → {adjusted_source_width}x{adjusted_source_height}"
            )

            with Image.open(job.input_image) as img:
                resized_img = img.resize(
                    (adjusted_source_width, adjusted_source_height),
                    Image.Resampling.LANCZOS,
                )

                adjusted_path = (
                    img_path.parent / f"{img_path.stem}_adjusted{img_path.suffix}"
                )

                resized_img.save(adjusted_path, quality=95)
                logger.info(f"   ✅ Image ajustée: {adjusted_path.name}")

            image_to_upload = adjusted_path
            upload_filename = adjusted_path.name

        # Étape 2: Redimensionnement pré-génération (HAT 2x pour upscale, Lanczos pour downscale)
        if needs_pregen_resize and (
            generation_width != adjusted_source_width
            or generation_height != adjusted_source_height
        ):
            if resize_type == "upscale":
                logger.info(
                    f"🔼 Upscale HAT 2x + Lanczos pré-génération: "
                    f"{adjusted_source_width}x{adjusted_source_height} → {generation_width}x{generation_height}"
                )

                # HAT 2x via spandrel (ML super-résolution) puis Lanczos downscale vers cible exacte
                hat_2x_result = _hat_2x_upscale(image_to_upload)
                if hat_2x_result is not None:
                    # Lanczos downscale du résultat HAT 2x vers la résolution de génération
                    resized_img = hat_2x_result.resize(
                        (generation_width, generation_height),
                        Image.Resampling.LANCZOS,
                    )
                    logger.info(
                        f"   HAT 2x: {adjusted_source_width}x{adjusted_source_height} → "
                        f"{hat_2x_result.width}x{hat_2x_result.height} → "
                        f"Lanczos: {generation_width}x{generation_height}"
                    )
                else:
                    # Fallback Lanczos si HAT 2x échoue
                    logger.warning("   ⚠️  HAT 2x indisponible, fallback Lanczos")
                    with Image.open(image_to_upload) as img:
                        resized_img = img.resize(
                            (generation_width, generation_height),
                            Image.Resampling.LANCZOS,
                        )
            elif resize_type == "downscale":
                logger.info(
                    f"🔽 Downscale Lanczos pré-génération: "
                    f"{adjusted_source_width}x{adjusted_source_height} → {generation_width}x{generation_height}"
                )
                with Image.open(image_to_upload) as img:
                    resized_img = img.resize(
                        (generation_width, generation_height),
                        Image.Resampling.LANCZOS,
                    )

            pregen_path = (
                img_path.parent / f"{img_path.stem}_pregen{img_path.suffix}"
            )

            resized_img.save(pregen_path, quality=95)
            logger.success(
                f"   ✅ Image préparée pour génération: {pregen_path.name}"
            )

            image_to_upload = pregen_path
            upload_filename = pregen_path.name

        # Logger la stratégie choisie
        logger.info("📐 Stratégie de génération complète:")
        logger.info(f"   Image source originale: {source_width}x{source_height}")
        logger.info(
            f"   Image ajustée (×32): {adjusted_source_width}x{adjusted_source_height}"
        )
        logger.info(f"   Génération vidéo: {generation_width}x{generation_height}")
        logger.info(
            f"   Résolution génération cible: {adjusted_target_width}x{adjusted_target_height}"
        )
        if (
            user_target_width != adjusted_target_width
            or user_target_height != adjusted_target_height
        ):
            logger.info(
                f"   Résolution finale (post-ffmpeg): {user_target_width}x{user_target_height}"
            )

        # Messages sur l'upscale post-génération
        if upscale_ratio > 1.5:
            logger.info(
                f"   Upscale post-génération: {generation_width}x{generation_height} → "
                f"{adjusted_target_width}x{adjusted_target_height} ({upscale_ratio:.2f}x)"
            )

            if use_supersampling:
                logger.success(
                    f"   ✅ Upscale optimal ({upscale_ratio:.2f}x ≤ 4x) - HAT-L 4x + supersampling Lanczos"
                )
            else:
                logger.warning(
                    f"   ⚠️  Upscale élevé ({upscale_ratio:.2f}x > 4x) - HAT-L 4x + {upscale_ratio / 4:.2f}x Lanczos supplémentaire"
                )
                logger.warning(
                    "   Des artefacts peuvent apparaître au-delà de 4x. Qualité optimale garantie jusqu'à 4x."
                )

        # VAE tiling — piloté par le registre
        target_pixels = adjusted_target_width * adjusted_target_height
        if model_cfg and model_cfg.resolution:
            _res = model_cfg.resolution
            enable_vae_tiling = (
                target_pixels > _res.vae_tiling_pixel_threshold
                or upscale_ratio > _res.vae_tiling_upscale_threshold
            )
        else:
            enable_vae_tiling = target_pixels > 2073600 or upscale_ratio > 4.0

        # Sélection workflow — piloté par le registre
        if model_cfg and model_cfg.resolution:
            trigger = model_cfg.resolution.upscale_trigger_ratio
            base_wf = model_cfg.workflow_template
            upscale_wf = model_cfg.workflow_template_upscale or base_wf
        else:
            trigger = 1.5
            base_wf = f"wan22_{model_type}_i2v"
            upscale_wf = f"wan22_{model_type}_with_upscale"

        if upscale_ratio > trigger:
            selected_workflow = upscale_wf

            logger.info(
                f"🔍 Workflow {model_type.upper()} avec upscale sélectionné (ratio: {upscale_ratio:.2f}x)"
            )

            base_params = {
                k: v for k, v in job.parameters.items() if k not in ["width", "height"]
            }
            workflow_params = {
                "input_image": upload_filename,
                "prompt": job.prompt,
                "negative_prompt": job.parameters.get("negative_prompt", ""),
                **base_params,
                "width": generation_width,
                "height": generation_height,
                "target_width": adjusted_target_width,
                "target_height": adjusted_target_height,
                "enable_vae_tiling": enable_vae_tiling,
            }

            expected_output_width = adjusted_target_width
            expected_output_height = adjusted_target_height

            if enable_vae_tiling:
                logger.info(
                    f"🔧 VAE tiling activé (résolution finale: {adjusted_target_width}x{adjusted_target_height}, upscale: {upscale_ratio:.2f}x)"
                )
        else:
            selected_workflow = base_wf

            logger.info(
                f"✅ Workflow {model_type.upper()} standard (ratio: {upscale_ratio:.2f}x)"
            )

            # Pour génération standard, utiliser les dimensions optimales
            # IMPORTANT: Exclure width/height de job.parameters pour éviter conflit
            base_params = {
                k: v for k, v in job.parameters.items() if k not in ["width", "height"]
            }
            workflow_params = {
                "input_image": upload_filename,
                "prompt": job.prompt,
                "negative_prompt": job.parameters.get("negative_prompt", ""),
                **base_params,  # Tous les params sauf width/height
                "width": generation_width,
                "height": generation_height,
                "enable_vae_tiling": enable_vae_tiling,
            }

            # Sortie attendue du workflow standard : résolution de génération
            expected_output_width = generation_width
            expected_output_height = generation_height

            if enable_vae_tiling:
                logger.info(
                    f"🔧 VAE tiling activé (résolution: {generation_width}x{generation_height})"
                )

        workflow = workflow_manager.create_workflow(selected_workflow, workflow_params)

        # 2. Générer le cinemagraph
        # Nombre de frames pour l'estimation de durée (HAT-L upscale)
        gen_frames = workflow_params.get("frames", 81)
        has_upscale = upscale_ratio > trigger

        progress_tracker = ComfyUIProgressTracker(
            job_manager=job_manager,
            job_id=job_id,
            total_frames=gen_frames,
            has_upscale=has_upscale,
        )

        job_manager.update_job(
            job_id, current_step="Lancement de la génération...", progress=0.05
        )

        async with ComfyUISession(comfyui_config) as client:
            # Upload de l'image (originale ou redimensionnée)
            with open(image_to_upload, "rb") as f:
                image_data = f.read()

            # Lancer le workflow
            comfyui_workflow_id = await client.queue_prompt(
                workflow, images={upload_filename: image_data}
            )

            job_manager.update_job(job_id, workflow_id=comfyui_workflow_id)

            # Timeout adapté par modèle — registre d'abord, fallback hardcodé
            try:
                _reg = get_registry()
                workflow_timeout = _reg.get_timeout(detected_model) or (10800 if model_type == "14b" else 5400)
            except Exception:
                workflow_timeout = 10800 if model_type == "14b" else 5400
            logger.info(
                f"⏱️  Timeout workflow {model_type.upper()}: {workflow_timeout}s ({workflow_timeout // 60} min)"
            )

            # Attente avec progression temps réel via le tracker
            workflow_result = await client.wait_for_completion(
                comfyui_workflow_id,
                timeout=workflow_timeout,
                progress_callback=progress_tracker,
            )
            logger.info(
                f"Workflow terminé: {workflow_result.status if hasattr(workflow_result, 'status') else 'completed'}"
            )

            # Vérifier si ComfyUI a remonté une erreur d'exécution
            if hasattr(workflow_result, "status") and workflow_result.status == "error":
                error_msg = getattr(workflow_result, "error_message", "Erreur inconnue")
                raise Exception(f"Erreur ComfyUI: {error_msg}")

            # Récupérer les images de sortie
            job_manager.update_job(
                job_id, current_step="Récupération du résultat", progress=_PROGRESS_POSTPROC_START
            )

            output_images = await client.get_output_images(comfyui_workflow_id)

            if not output_images:
                raise Exception("Aucune vidéo générée")

            # Sauvegarder la vidéo
            output_path = os.path.join(
                app.config["UPLOAD_FOLDER"], f"output_{job_id}.mp4"
            )
            with open(output_path, "wb") as f:
                f.write(output_images[0]["data"])

            # Post-processing : redimensionner vers les dimensions exactes demandées
            # Le VAE WAN 2.2 impose des multiples de 32, ffmpeg ajuste la sortie finale
            output_needs_resize = (
                user_target_width != expected_output_width
                or user_target_height != expected_output_height
            )

            if output_needs_resize:
                logger.info(
                    f"📐 Post-processing ffmpeg: {expected_output_width}x{expected_output_height} → "
                    f"{user_target_width}x{user_target_height}"
                )
                job_manager.update_job(
                    job_id, current_step="Ajustement dimensions finales", progress=0.88
                )

                temp_output = output_path + ".tmp.mp4"
                os.rename(output_path, temp_output)

                try:
                    subprocess.run(
                        [
                            "ffmpeg",
                            "-y",
                            "-i",
                            temp_output,
                            "-vf",
                            f"scale={user_target_width}:{user_target_height}:flags=lanczos",
                            "-c:v",
                            "libx264",
                            "-preset",
                            "ultrafast",
                            "-crf",
                            "1",
                            "-pix_fmt",
                            "yuv420p",
                            "-c:a",
                            "copy",
                            output_path,
                        ],
                        check=True,
                        capture_output=True,
                        text=True,
                    )
                    logger.success(
                        f"   ✅ Dimensions finales: {user_target_width}x{user_target_height}"
                    )
                except subprocess.CalledProcessError as e:
                    logger.error(f"   ❌ Erreur ffmpeg: {e.stderr}")
                    # Restaurer le fichier original en cas d'erreur
                    os.rename(temp_output, output_path)
                    logger.warning("   ⚠️ Sortie conservée aux dimensions de génération")
                finally:
                    # Nettoyer le fichier temporaire s'il existe encore
                    if os.path.exists(temp_output):
                        os.remove(temp_output)

            # Crossfade seamless loop — appliqué à tous les modèles
            # Fond les dernières 0.5s avec les premières pour une boucle sans couture
            fps = job.parameters.get("fps", 24)
            crossfade_duration = 0.5  # secondes
            logger.info(
                f"🔄 Crossfade seamless loop: {crossfade_duration}s à {fps}fps"
            )
            job_manager.update_job(
                job_id,
                current_step="Création boucle seamless",
                progress=0.93,
            )

            # ffmpeg : xfade entre la vidéo et elle-même pour boucle seamless
            probe_result = subprocess.run(
                [
                    "ffprobe", "-v", "error",
                    "-show_entries", "format=duration",
                    "-of", "default=noprint_wrappers=1:nokey=1",
                    output_path,
                ],
                capture_output=True, text=True,
            )
            video_duration = float(probe_result.stdout.strip())
            xfade_offset = video_duration - crossfade_duration

            temp_loop = output_path + ".loop.mp4"
            try:
                subprocess.run(
                    [
                        "ffmpeg", "-y",
                        "-i", output_path,
                        "-i", output_path,
                        "-filter_complex",
                        f"[0:v][1:v]xfade=transition=fade:duration={crossfade_duration}:offset={xfade_offset},trim=0:{xfade_offset},setpts=PTS-STARTPTS",
                        "-c:v", "libx264",
                        "-preset", "fast",
                        "-crf", "18",
                        "-pix_fmt", "yuv420p",
                        temp_loop,
                    ],
                    check=True,
                    capture_output=True,
                    text=True,
                )
                os.replace(temp_loop, output_path)
                logger.success(
                    f"   ✅ Boucle seamless: {xfade_offset:.1f}s "
                    f"(crossfade {crossfade_duration}s)"
                )
            except subprocess.CalledProcessError as e:
                logger.error(f"   ❌ Erreur crossfade: {e.stderr}")
                logger.warning("   ⚠️ Sortie conservée sans crossfade")
            finally:
                if os.path.exists(temp_loop):
                    os.remove(temp_loop)

            job_manager.update_job(job_id, output_video=output_path)

        # 3. Terminer (upload OwnCloud manuel via l'interface)
        job_manager.update_job(
            job_id, status=JobStatus.COMPLETED, progress=1.0, current_step="Terminé"
        )

        logger.success(f"Job {job_id} terminé avec succès")

    except Exception as e:
        logger.error(f"Erreur job {job_id}: {e}")
        import traceback

        logger.error(traceback.format_exc())
        job_manager.update_job(job_id, status=JobStatus.FAILED, error_message=str(e))

    finally:
        # Nettoyer les images redimensionnées temporaires si elles existent
        if (
            needs_resize_to_adjusted or needs_pregen_resize
        ) and image_to_upload.exists():
            try:
                image_to_upload.unlink()
                logger.debug(f"   🗑️ Image temporaire supprimée: {image_to_upload.name}")
            except Exception as cleanup_error:
                logger.warning(
                    f"   ⚠️ Impossible de supprimer {image_to_upload}: {cleanup_error}"
                )


# === ROUTES PRINCIPALES ===


@main_bp.route("/")
def index():
    """Page d'accueil"""
    return render_template("index.html")


# === ROUTES API ===


@api_bp.route("/analyze-image", methods=["POST"])
def analyze_image():
    """
    Analyse une image uploadée et retourne ses dimensions

    Body:
        - image: Fichier image

    Returns:
        JSON avec dimensions source
    """
    if "image" not in request.files:
        return jsonify({"error": "Aucune image fournie"}), 400

    file = request.files["image"]

    if not allowed_file(file.filename):
        return jsonify({"error": "Type de fichier non autorisé"}), 400

    try:
        # Ouvrir l'image avec PIL
        img = Image.open(file.stream)
        width, height = img.size

        return jsonify(
            {
                "width": width,
                "height": height,
                "ratio": round(width / height, 2),
                "format": img.format,
                "mode": img.mode,
            }
        )
    except Exception as e:
        logger.error(f"Erreur analyse image: {e}")
        return jsonify({"error": f"Erreur analyse image: {str(e)}"}), 400


@api_bp.route("/calculate-resolution", methods=["POST"])
def calc_resolution():
    """
    Calcule la résolution optimale et les infos d'upscale

    Body JSON:
        - source_width, source_height: Dimensions source
        - target_width, target_height: Dimensions demandées

    Returns:
        JSON avec résolution finale et infos upscale
    """
    data = request.get_json()

    try:
        # Validation des données avec valeurs par défaut
        source_w = int(data.get("source_width") or 1920)
        source_h = int(data.get("source_height") or 1080)
        target_w = int(data.get("target_width") or source_w)
        target_h = int(data.get("target_height") or source_h)

        # Vérifier que les valeurs sont positives
        if source_w <= 0 or source_h <= 0 or target_w <= 0 or target_h <= 0:
            return jsonify({"error": "Les dimensions doivent être positives"}), 400

        # Calculer résolution finale
        final_w, final_h = calculate_optimal_resolution(
            source_w, source_h, target_w, target_h
        )

        # Ajuster source aux multiples de 32 (arrondi ratio-aware)
        adjusted_source_w, adjusted_source_h = find_best_generation_dims(
            source_w, source_h
        )

        # Détecter le modèle disponible pour calcul stratégie
        from workflows.workflow_manager import WorkflowTemplate

        temp_template = WorkflowTemplate({"parameters": {}, "workflow": {}})
        detected_model, _model_type = temp_template._detect_available_model()

        # Calculer la stratégie de génération complète selon le modèle
        strategy = calculate_optimal_generation_strategy(
            adjusted_source_w,
            adjusted_source_h,
            final_w,
            final_h,
            model_name=detected_model,
        )

        upscale_ratio = strategy["upscale_ratio"]
        use_supersampling = strategy["use_supersampling"]

        # Déterminer le type et la description de l'upscale
        if upscale_ratio <= 1.5:
            upscale_type = "none"
            upscale_description = "Pas d'upscale nécessaire"
        elif use_supersampling:
            upscale_type = "optimal"
            upscale_description = f"Upscale optimal ({upscale_ratio:.2f}x ≤ 4x) - HAT-L 4x + supersampling Lanczos"
        else:
            upscale_type = "elevated"
            upscale_description = f"⚠️ Upscale élevé ({upscale_ratio:.2f}x > 4x) - HAT-L 4x + {upscale_ratio / 4:.2f}x Lanczos. Artefacts possibles."

        # Protection contre division par zéro
        ratio = round(final_w / final_h, 2) if final_h > 0 else 0

        return jsonify(
            {
                "final_width": final_w,
                "final_height": final_h,
                "ratio": ratio,
                "adjusted": (final_w != target_w or final_h != target_h),
                "upscale_ratio": round(upscale_ratio, 2),
                "upscale_type": upscale_type,
                "upscale_description": upscale_description,
            }
        )
    except (KeyError, ValueError) as e:
        return jsonify({"error": f"Paramètres invalides: {str(e)}"}), 400


@api_bp.route("/generate", methods=["POST"])
def generate_cinemagraph():
    """
    Crée un job de génération de cinemagraph

    Body:
        - image: Fichier image
        - prompt: Prompt de génération
        - negative_prompt: Negative prompt (optionnel)
        - target_width, target_height: Résolution demandée
        - duration: Durée en secondes
        - fps: Images par seconde
        - parameters: Autres paramètres JSON
    """
    # Vérifier que ComfyUI est accessible AVANT de créer le job
    try:
        comfyui_accessible = asyncio.run(
            test_comfyui_connection(current_app.comfyui_config)
        )
        if not comfyui_accessible:
            logger.error("ComfyUI inaccessible lors de la requête de génération")
            return (
                jsonify(
                    {
                        "error": "ComfyUI n'est pas accessible. Veuillez réessayer dans quelques instants.",
                        "details": "Le service de génération n'est pas prêt. Cela peut arriver au démarrage.",
                    }
                ),
                503,
            )
    except Exception as e:
        logger.error(f"Erreur lors de la vérification de ComfyUI: {e}")
        return (
            jsonify(
                {
                    "error": "Impossible de vérifier l'état de ComfyUI",
                    "details": str(e),
                }
            ),
            503,
        )

    # Vérifier l'image
    if "image" not in request.files:
        return jsonify({"error": "Aucune image fournie"}), 400

    file = request.files["image"]
    if file.filename == "" or not allowed_file(file.filename):
        return jsonify({"error": "Fichier invalide"}), 400

    # Sauvegarder l'image
    filename = secure_filename(file.filename)
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    filename = f"{timestamp}_{filename}"
    filepath = get_file_path(filename)
    file.save(filepath)

    # Analyser l'image pour obtenir les dimensions source
    try:
        with Image.open(filepath) as img:
            source_width, source_height = img.size
    except Exception as e:
        return jsonify({"error": f"Erreur lecture image: {e}"}), 400

    # Récupérer les paramètres
    prompt = request.form.get("prompt", "")
    negative_prompt = request.form.get("negative_prompt", "")

    # Résolution
    target_width = int(request.form.get("target_width", source_width))
    target_height = int(request.form.get("target_height", source_height))

    final_width, final_height = calculate_optimal_resolution(
        source_width, source_height, target_width, target_height
    )

    # Paramètres temporels
    duration = float(request.form.get("duration", 3.0))  # secondes
    fps = int(request.form.get("fps", 24))
    frames = int(duration * fps)

    # Autres paramètres
    try:
        import json

        parameters = json.loads(request.form.get("parameters", "{}"))
    except (json.JSONDecodeError, TypeError, ValueError):
        parameters = {}

    # Paramètres par défaut
    parameters.setdefault("steps", 20)
    parameters.setdefault("cfg_scale", 7.5)
    parameters.setdefault("noise_level", "high")

    # Ajouter les nouveaux paramètres
    parameters.update(
        {
            "width": final_width,
            "height": final_height,
            "user_target_width": target_width,
            "user_target_height": target_height,
            "frames": frames,
            "fps": fps,
            "duration": duration,
            "negative_prompt": negative_prompt,
        }
    )

    # Créer le job
    job = current_app.job_manager.create_job(
        input_image=filepath, prompt=prompt, parameters=parameters
    )

    # ============================================================
    # CORRECTION: Génération avec contexte Flask
    # ============================================================
    import threading

    # Récupérer l'app Flask et les configs AVANT le thread
    app = current_app._get_current_object()
    job_manager = current_app.job_manager
    comfyui_cfg = current_app.comfyui_config

    def run_async(job_id: str):
        """Exécute la génération async avec contexte Flask"""
        # Créer une nouvelle event loop
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)

        try:
            # Exécuter avec le contexte Flask
            with app.app_context():
                # Restaurer les configs dans le contexte
                current_app.job_manager = job_manager
                current_app.comfyui_config = comfyui_cfg

                loop.run_until_complete(process_cinemagraph_generation(job_id))
        except Exception as e:
            logger.error(f"Erreur dans run_async pour job {job_id}: {e}")
            import traceback

            logger.error(traceback.format_exc())
        finally:
            loop.close()

    thread = threading.Thread(target=run_async, args=(job.job_id,), daemon=True)
    thread.start()
    # ============================================================

    logger.info(f"Génération lancée pour job: {job.job_id}")
    logger.info(
        f"   Résolution: {final_width}x{final_height} ({frames} frames @ {fps}fps)"
    )
    logger.info(f"   Prompt: {prompt[:200]}{'...' if len(prompt) > 200 else ''}")
    if negative_prompt:
        logger.info(f"   Negative: {negative_prompt[:150]}{'...' if len(negative_prompt) > 150 else ''}")
    # Log du workflow qui sera utilisé
    scale_ratio = (final_width * final_height) / (source_width * source_height)
    from workflows.workflow_manager import WorkflowTemplate

    temp_template = WorkflowTemplate({"parameters": {}, "workflow": {}})
    detected_model_name, log_model_type = temp_template._detect_available_model()
    try:
        _reg = get_registry()
        _cfg = _reg.get_model(detected_model_name)
        if _cfg and _cfg.resolution:
            expected_workflow = (
                _cfg.workflow_template_upscale or _cfg.workflow_template
                if scale_ratio > _cfg.resolution.upscale_trigger_ratio
                else _cfg.workflow_template
            )
        else:
            expected_workflow = f"wan22_{log_model_type}_with_upscale" if scale_ratio > 1.5 else f"wan22_{log_model_type}_i2v"
    except Exception:
        expected_workflow = f"wan22_{log_model_type}_with_upscale" if scale_ratio > 1.5 else f"wan22_{log_model_type}_i2v"
    logger.info(f"   Workflow: {expected_workflow} (ratio: {scale_ratio:.2f}x)")

    return jsonify(
        {
            "job_id": job.job_id,
            "status": job.status.value,
            "message": "Génération lancée",
            "resolution": {
                "source": f"{source_width}x{source_height}",
                "final": f"{final_width}x{final_height}",
                "frames": frames,
                "fps": fps,
                "duration": duration,
            },
        }
    ), 202


@api_bp.route("/jobs/<job_id>", methods=["GET"])
def get_job_status(job_id):
    """
    Récupère le statut d'un job

    Args:
        job_id: ID du job

    Returns:
        JSON avec les détails du job
    """
    job = current_app.job_manager.get_job(job_id)

    if not job:
        return jsonify({"error": "Job non trouvé"}), 404

    return jsonify(job.to_dict())


@api_bp.route("/jobs", methods=["GET"])
def list_jobs():
    """
    Liste tous les jobs

    Query params:
        - status: Filtrer par statut (optionnel)
        - limit: Nombre max de résultats (défaut: 50)

    Returns:
        JSON avec liste des jobs
    """
    status_filter = request.args.get("status")
    limit = int(request.args.get("limit", 50))

    # Convertir le statut si fourni
    status_enum = None
    if status_filter:
        try:
            status_enum = JobStatus(status_filter)
        except ValueError:
            return jsonify({"error": f"Statut invalide: {status_filter}"}), 400

    jobs = current_app.job_manager.list_jobs(status=status_enum, limit=limit)

    return jsonify({"jobs": [job.to_dict() for job in jobs], "count": len(jobs)})


@api_bp.route("/jobs/<job_id>", methods=["DELETE"])
def delete_job(job_id):
    """
    Supprime un job terminé

    Args:
        job_id: ID du job

    Returns:
        JSON avec résultat
    """
    success = current_app.job_manager.delete_job(job_id)

    if success:
        return jsonify({"message": "Job supprimé"}), 200
    else:
        return jsonify(
            {"error": "Impossible de supprimer le job (actif ou inexistant)"}
        ), 400


@api_bp.route("/jobs/<job_id>/download", methods=["GET"])
def download_result(job_id):
    """
    Télécharge le résultat d'un job

    Args:
        job_id: ID du job

    Returns:
        Fichier vidéo
    """
    job = current_app.job_manager.get_job(job_id)

    if not job:
        return jsonify({"error": "Job non trouvé"}), 404

    if job.status != JobStatus.COMPLETED:
        return jsonify({"error": "Job non terminé"}), 400

    if not job.output_video or not os.path.exists(job.output_video):
        return jsonify({"error": "Fichier de sortie introuvable"}), 404

    return send_file(
        job.output_video,
        mimetype="video/mp4",
        as_attachment=True,
        download_name=f"cinemagraph_{job_id}.mp4",
    )


@api_bp.route("/jobs/<job_id>/upload-owncloud", methods=["POST"])
def manual_upload_to_owncloud(job_id):
    """
    Upload manuel d'un cinemagraph vers OwnCloud

    Args:
        job_id: ID du job

    Returns:
        JSON avec résultat de l'upload
    """
    job = current_app.job_manager.get_job(job_id)

    if not job:
        return jsonify({"error": "Job non trouvé"}), 404

    if job.status != JobStatus.COMPLETED:
        return jsonify({"error": "Job non terminé"}), 400

    if not job.output_video or not os.path.exists(job.output_video):
        return jsonify({"error": "Fichier de sortie introuvable"}), 404

    if not current_app.owncloud_config:
        return jsonify({"error": "OwnCloud non configuré"}), 503

    # Si déjà uploadé
    if job.owncloud_link:
        return jsonify(
            {
                "success": True,
                "message": "Déjà uploadé",
                "share_link": job.owncloud_link,
            }
        )

    try:
        # Upload synchrone
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)

        async def do_upload():
            async with OwnCloudUploader(current_app.owncloud_config) as uploader:
                result = await upload_cinemagraph(
                    uploader=uploader,
                    video_file=Path(job.output_video),
                    workflow_id=job.workflow_id or job.job_id,
                    prompt=job.prompt,
                    generation_params=job.parameters,
                    create_share=True,
                )
                return result

        upload_result = loop.run_until_complete(do_upload())

        if upload_result.success:
            # Mettre à jour le job
            current_app.job_manager.update_job(
                job_id, owncloud_link=upload_result.share_link
            )

            return jsonify(
                {
                    "success": True,
                    "message": "Upload réussi",
                    "share_link": upload_result.share_link,
                }
            )
        else:
            return jsonify(
                {"success": False, "error": upload_result.error or "Upload échoué"}
            ), 500

    except Exception as e:
        logger.error(f"Erreur upload manuel OwnCloud: {e}")
        return jsonify({"success": False, "error": str(e)}), 500


@api_bp.route("/statistics", methods=["GET"])
def get_statistics():
    """
    Retourne les statistiques des jobs

    Returns:
        JSON avec statistiques
    """
    stats = current_app.job_manager.get_statistics()
    return jsonify(stats)


@api_bp.route("/templates", methods=["GET"])
def list_templates():
    """
    Liste les templates de workflows disponibles

    Returns:
        JSON avec liste des templates
    """
    templates = workflow_manager.list_templates()
    return jsonify({"templates": templates, "count": len(templates)})


@api_bp.route("/config/comfyui", methods=["GET"])
def check_comfyui():
    """
    Vérifie la connexion à ComfyUI

    Returns:
        JSON avec statut ComfyUI
    """
    if not current_app.comfyui_config:
        return jsonify({"error": "ComfyUI non configuré"}), 503

    loop = asyncio.new_event_loop()
    is_connected = loop.run_until_complete(
        test_comfyui_connection(current_app.comfyui_config)
    )

    return jsonify(
        {
            "connected": is_connected,
            "host": current_app.comfyui_config.host,
            "port": current_app.comfyui_config.port,
        }
    )


@api_bp.route("/config/owncloud", methods=["GET"])
def check_owncloud():
    """
    Vérifie la configuration OwnCloud

    Returns:
        JSON avec statut OwnCloud
    """
    if not current_app.owncloud_config:
        return jsonify({"configured": False, "message": "OwnCloud non configuré"})

    return jsonify(
        {
            "configured": True,
            "server": current_app.owncloud_config.server_url,
            "upload_folder": current_app.owncloud_config.upload_folder,
        }
    )


@api_bp.route("/model-info", methods=["GET"])
def get_model_info():
    """
    Retourne les informations sur le modèle actif déployé.

    Détection par filesystem (registre) → fallback env var → 503 si rien.

    Returns:
        JSON avec model_type, model_name, display_name, estimated_time, gpu_recommendation
    """
    try:
        # Répertoires de recherche des modèles
        search_dirs = [
            Path("/workspace/comfyui/ComfyUI/models/diffusion_models"),
            Path("/workspace/comfyui/ComfyUI/models/checkpoints"),
        ]

        # Détection via registre uniquement — plus de fallback hardcodé
        try:
            _reg = get_registry()
            model_priority = _reg.get_detection_priority()
        except Exception:
            model_priority = []

        detected_model: str | None = None
        model_type: str | None = None

        for model_name, m_type in model_priority:
            for models_dir in search_dirs:
                model_path = models_dir / model_name
                if model_path.exists() and any(model_path.glob("*.safetensors")):
                    detected_model = model_name
                    model_type = m_type
                    logger.info(
                        f"✅ API model-info: Modèle détecté: {model_name} (type: {m_type})"
                    )
                    break
            if detected_model:
                break

        # Fallback env var — sans défaut hardcodé
        if not detected_model:
            env_model = os.getenv("OWNCLOUD_MODEL_NAME", "")
            if not env_model:
                logger.error("❌ API model-info: Aucun modèle détecté et OWNCLOUD_MODEL_NAME non défini")
                return jsonify({"error": "Aucun modèle détecté"}), 503
            detected_model = env_model
            logger.warning(
                f"⚠️ API model-info: Utilisation env var: {env_model}"
            )

        # Enrichissement via registre
        try:
            _reg = get_registry()
            model_cfg = _reg.get_model(detected_model)
        except Exception:
            model_cfg = None

        if model_cfg:
            return jsonify(
                {
                    "model_type": model_cfg.model_type,
                    "model_name": detected_model,
                    "display_name": model_cfg.display_name,
                    "estimated_time": model_cfg.estimated_time,
                    "gpu_recommendation": model_cfg.vram_requirement,
                }
            )

        # Registre KO → réponse minimale avec le nom brut
        return jsonify(
            {
                "model_type": model_type or "unknown",
                "model_name": detected_model,
                "display_name": detected_model,
                "estimated_time": "~10 min",
                "gpu_recommendation": "N/A",
            }
        )

    except Exception as e:
        logger.warning(f"Impossible de détecter le modèle: {e}")
        env_model = os.getenv("OWNCLOUD_MODEL_NAME", "")
        if not env_model:
            return jsonify({"error": "Aucun modèle détecté"}), 503

        # Tentative registre sur env var
        try:
            _reg = get_registry()
            model_cfg = _reg.get_model(env_model)
            if model_cfg:
                return jsonify(
                    {
                        "model_type": model_cfg.model_type,
                        "model_name": env_model,
                        "display_name": model_cfg.display_name,
                        "estimated_time": model_cfg.estimated_time,
                        "gpu_recommendation": model_cfg.vram_requirement,
                    }
                )
        except Exception:
            pass

        return jsonify(
            {
                "model_type": "unknown",
                "model_name": env_model,
                "display_name": env_model,
                "estimated_time": "~10 min",
                "gpu_recommendation": "N/A",
            }
        )


@api_bp.route("/jobs/<job_id>/thumbnail", methods=["GET"])
def get_thumbnail(job_id):
    """Retourne une miniature du résultat (placeholder pour l'instant)"""
    # TODO: Extraire la première frame de la vidéo avec ffmpeg ou PIL
    logger.warning(f"Thumbnail placeholder retourné pour job {job_id} - extraction première frame non implémentée")
    import io

    # Placeholder image
    img = Image.new("RGB", (400, 300), color="#667eea")
    img_io = io.BytesIO()
    img.save(img_io, "JPEG")
    img_io.seek(0)

    return send_file(img_io, mimetype="image/jpeg")
