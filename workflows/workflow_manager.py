"""
Gestionnaire de workflows pour ComfyUI
Charge et applique les templates de workflows avec paramètres
"""

import json
import sys
from pathlib import Path
from typing import Any
from datetime import datetime
import copy

# Import du système de logging centralisé
from src.logger import get_logger
from src.model_registry import get_registry

logger = get_logger("workflow_manager")


class WorkflowTemplate:
    """Représente un template de workflow avec ses paramètres"""

    def __init__(self, template_data: dict[str, Any]):
        self.name = template_data.get("name", "Unknown")
        self.description = template_data.get("description", "")
        self.version = template_data.get("version", "1.0.0")
        self.parameters = template_data.get("parameters", {})
        self.workflow = template_data.get("workflow", {})
        self.metadata = template_data.get("metadata", {})
        self.model_family = template_data.get("model_family", "wan22")
        self._template = template_data

        logger.debug(f"Template chargé: {self.name} v{self.version}")

    def _detect_available_model(self) -> tuple[str, str]:
        """
        Détecte automatiquement quel modèle est disponible sur le filesystem.

        Cherche dans diffusion_models (WAN) et checkpoints (LTX, WAN fallback).

        Returns:
            tuple: (model_name, model_type)
        """
        import os

        # Répertoires de recherche (WAN: diffusion_models, LTX: checkpoints)
        search_dirs = [
            Path("/workspace/comfyui/ComfyUI/models/diffusion_models"),
            Path("/workspace/comfyui/ComfyUI/models/checkpoints"),
        ]
        # Filtrer les répertoires existants
        existing_dirs = [d for d in search_dirs if d.exists()]
        comfyui_models_dir = existing_dirs[0] if existing_dirs else search_dirs[0]

        # Priorité depuis le registre (fallback hardcodé si registre échoue)
        try:
            registry = get_registry()
            model_priority = registry.get_detection_priority()
        except Exception:
            model_priority = [
                ("wan2.2-i2v-a14b", "14b"),
                ("wan2.2-ti2v-5b", "5b"),
            ]

        for model_name, model_type in model_priority:
            # Chercher dans tous les répertoires existants (diffusion_models + checkpoints)
            for search_dir in existing_dirs:
                model_path = search_dir / model_name
                if model_path.exists() and any(model_path.glob("*.safetensors")):
                    logger.info(f"✅ Modèle détecté: {model_name} (type: {model_type})")
                    return model_name, model_type

        # Fallback: Variable d'environnement
        env_model = os.getenv("OWNCLOUD_MODEL_NAME", "wan2.2-ti2v-5b")
        # Déduire model_type depuis le registre ou le nom
        fallback_type = "5b"
        try:
            registry_model = get_registry().get_model(env_model)
            if registry_model:
                fallback_type = registry_model.model_type
        except Exception:
            if "14b" in env_model.lower() or "a14b" in env_model.lower():
                fallback_type = "14b"
            elif "dev" in env_model.lower() and "ltx" in env_model.lower():
                fallback_type = "dev"
        logger.warning(
            f"⚠️ Aucun modèle trouvé, utilisation variable env: {env_model} (type: {fallback_type})"
        )
        return env_model, fallback_type

    def _get_model_checkpoint_path(self, model_name: str) -> str | tuple[str, str]:
        """
        Retourne le chemin du checkpoint selon le type de modèle

        Args:
            model_name: Nom du dossier (wan2.2-ti2v-5b ou wan2.2-i2v-a14b)

        Returns:
            str: Chemin du fichier checkpoint (5B)
            tuple[str, str]: (high_noise_path, low_noise_path) pour 14B MoE
        """

        # Chemins possibles des modèles
        comfyui_models_dir = Path("comfyui/ComfyUI/models/checkpoints")

        # Variante 1: Environnement RunPod
        if not comfyui_models_dir.exists():
            comfyui_models_dir = Path("/workspace/comfyui/ComfyUI/models/checkpoints")

        # Variante 2: Local
        if not comfyui_models_dir.exists():
            comfyui_models_dir = Path("../comfyui/ComfyUI/models/checkpoints")

        model_path = comfyui_models_dir / model_name

        # Essayer le registre pour les modèles non-legacy
        result = self._get_checkpoint_from_registry(model_name, model_path)
        if result is not None:
            return result

        # Code legacy existant (5B, 14B) — INCHANGÉ
        # Détection automatique selon la structure des fichiers (ComfyUI Native)
        if "5b" in model_name.lower():
            # Modèle 5B : chercher le fichier ComfyUI Native (Comfy-Org)
            comfyui_native_checkpoint = model_path / "wan2.2_ti2v_5B_fp16.safetensors"
            if comfyui_native_checkpoint.exists():
                logger.info(
                    f"✅ Modèle 5B ComfyUI Native détecté : {comfyui_native_checkpoint.name}"
                )
                return f"{model_name}/{comfyui_native_checkpoint.name}"

            # Fallback : ancien format fusionné (v3.1.8)
            merged_checkpoint = model_path / "diffusion_pytorch_model.safetensors"
            if merged_checkpoint.exists():
                logger.warning(
                    f"⚠️  Ancien format fusionné détecté : {merged_checkpoint.name}"
                )
                logger.warning(
                    "   Recommandation : re-télécharger depuis Comfy-Org avec setup_wan22_native.sh"
                )
                return f"{model_name}/{merged_checkpoint.name}"

            # Fallback : si fichiers sharded encore présents (très ancienne version)
            checkpoint_files = list(
                model_path.glob("diffusion_pytorch_model-*.safetensors")
            )
            if checkpoint_files:
                first_checkpoint = sorted(checkpoint_files)[0]
                logger.warning(
                    f"⚠️  Fichiers sharded détectés (obsolète) : {first_checkpoint.name}"
                )
                logger.warning(
                    "   Recommandation : re-télécharger depuis Comfy-Org avec setup_wan22_native.sh"
                )
                return f"{model_name}/{first_checkpoint.name}"

        elif "14b" in model_name.lower() or "a14b" in model_name.lower():
            # Modèle 14B MoE : chercher les DEUX fichiers ComfyUI Native FP16 (Comfy-Org)
            # Architecture MoE = high_noise expert + low_noise expert
            comfyui_native_high = (
                model_path / "wan2.2_i2v_high_noise_14B_fp16.safetensors"
            )
            comfyui_native_low = (
                model_path / "wan2.2_i2v_low_noise_14B_fp16.safetensors"
            )

            # DEBUG: Lister TOUS les fichiers dans le dossier du modèle
            if model_path.exists():
                all_files = list(model_path.glob("*.safetensors"))
                logger.info(f"🔍 Fichiers dans {model_path}:")
                for f in all_files:
                    logger.info(f"   - {f.name} ({f.stat().st_size / 1024**3:.2f} GB)")
            else:
                logger.error(f"❌ Le dossier {model_path} n'existe pas!")

            # Vérifier les DEUX fichiers MoE
            if comfyui_native_high.exists() and comfyui_native_low.exists():
                high_path = f"{model_name}/{comfyui_native_high.name}"
                low_path = f"{model_name}/{comfyui_native_low.name}"
                logger.info("✅ Modèle 14B MoE ComfyUI Native FP16 détecté :")
                logger.info(f"   - High-noise expert: {comfyui_native_high.name}")
                logger.info(f"   - Low-noise expert: {comfyui_native_low.name}")
                # Retourner un tuple (high_path, low_path) pour MoE
                return (high_path, low_path)
            elif comfyui_native_high.exists():
                # Fallback: seulement high_noise disponible (ancien workflow)
                checkpoint_path = f"{model_name}/{comfyui_native_high.name}"
                logger.warning("⚠️ Seul le modèle high_noise trouvé - MoE incomplet!")
                logger.warning(
                    "   Fichier manquant: wan2.2_i2v_low_noise_14B_fp16.safetensors"
                )
                logger.warning(
                    "   La qualité sera dégradée (artefacts 'neige' probables)"
                )
                return checkpoint_path

            # Fallback : ancien format fusionné (v3.1.8)
            merged_checkpoint = model_path / "diffusion_pytorch_model.safetensors"
            if merged_checkpoint.exists():
                logger.warning(
                    f"⚠️  Ancien format fusionné détecté : {merged_checkpoint.name}"
                )
                logger.warning(
                    "   Recommandation : re-télécharger depuis Comfy-Org avec setup_wan22_native.sh"
                )
                return f"{model_name}/{merged_checkpoint.name}"

            # Fallback : très ancienne architecture MoE
            checkpoint_file = model_path / "high_noise_model.safetensors"
            if checkpoint_file.exists():
                logger.warning("⚠️ Ancienne architecture MoE détectée")
                logger.warning(
                    "   Recommandation : re-télécharger depuis Comfy-Org avec setup_wan22_native.sh"
                )
                return f"{model_name}/high_noise_model.safetensors"

        # Fallback : retourner le premier safetensors trouvé
        all_checkpoints = list(model_path.glob("*.safetensors"))
        if all_checkpoints:
            fallback_checkpoint = sorted(all_checkpoints)[0]
            logger.warning(
                f"⚠️ Utilisation du fallback checkpoint: {fallback_checkpoint.name}"
            )
            return f"{model_name}/{fallback_checkpoint.name}"

        # Dernier fallback
        logger.error("❌ Aucun checkpoint trouvé !")
        return f"{model_name}/model.safetensors"

    def _get_checkpoint_from_registry(
        self, model_name: str, model_path: Path
    ) -> str | tuple[str, str] | None:
        """
        Résout le chemin checkpoint via le registre pour les modèles non-legacy.

        Les modèles 5B/14B passent dans le code legacy (plus robuste avec ses
        multiples fallbacks). Seuls les futurs modèles ajoutés au registre
        passent ici.

        Args:
            model_name: Nom du dossier modèle
            model_path: Chemin absolu vers le dossier du modèle

        Returns:
            Chemin(s) checkpoint si trouvé via registre, None sinon (→ fallback legacy)
        """
        # Les modèles legacy gardent leur code éprouvé
        if "5b" in model_name.lower() or "14b" in model_name.lower():
            return None

        try:
            registry = get_registry()
            cd = registry.get_checkpoint_detection(model_name)
            if not cd:
                return None

            if cd.return_type == "moe_pair" and len(cd.primary_files) >= 2:
                high = model_path / cd.primary_files[0]
                low = model_path / cd.primary_files[1]
                if high.exists() and low.exists():
                    return (
                        f"{model_name}/{cd.primary_files[0]}",
                        f"{model_name}/{cd.primary_files[1]}",
                    )
            else:
                for fname in cd.primary_files:
                    fpath = model_path / fname
                    if fpath.exists():
                        return f"{model_name}/{fname}"

            # Fallback fichiers alternatifs
            for fname in cd.fallback_files:
                fpath = model_path / fname
                if fpath.exists():
                    logger.warning(f"⚠️ Registre: fallback détecté pour {model_name}: {fname}")
                    return f"{model_name}/{fname}"

        except Exception as e:
            logger.debug(f"Registre indisponible pour {model_name}: {e}")

        return None

    def _generate_random_seed(self) -> int:
        """Génère un seed aléatoire valide (>= 0)"""
        import random

        return random.randint(0, 2**31 - 1)

    def _transform_frontend_params(self, params: dict[str, Any]) -> dict[str, Any]:
        """
        Transforme les paramètres high-level du frontend en paramètres low-level ComfyUI

        Mapping des paramètres:
        - denoise (0-100) → influence sur shift
        - motion_intensity (subtle/moderate/intense) → shift (5.0/7.0/9.0)
        - noise_level (low/medium/high) → ajustement shift
        - consistency (0-100) → riflex_freq_index (0-2)
        - color_preservation (0-100) → ajustement cfg_scale
        - motion_area (full/center/edges) → ajout au prompt
        - frame_blending (1-10) → info seulement (non supporté directement)

        Note: pingpong est toujours désactivé (false). WAN 2.2 ne dispose pas de
        mécanisme de boucle seamless natif — la boucle est gérée en post-processing.

        Args:
            params: Paramètres du frontend

        Returns:
            dict: Paramètres transformés pour ComfyUI
        """
        transformed = params.copy()

        # === SHIFT (contrôle intensité du mouvement) ===
        # Base shift selon motion_intensity
        motion_intensity = params.get("motion_intensity", "moderate")
        base_shift = {
            "subtle": 4.0,  # Mouvement très léger
            "moderate": 5.0,  # Mouvement normal (défaut)
            "intense": 7.0,  # Mouvement prononcé
        }.get(motion_intensity, 5.0)

        # Ajuster selon noise_level
        noise_level = params.get("noise_level", "high")
        noise_modifier = {
            "low": -1.0,  # Moins de bruit = plus stable
            "medium": 0.0,  # Neutre
            "high": 1.0,  # Plus de bruit = plus créatif
        }.get(noise_level, 0.0)

        # Ajuster selon denoise (0-100)
        denoise = params.get("denoise", 75)
        # denoise 50 = neutre, <50 = plus stable, >50 = plus créatif
        denoise_modifier = (denoise - 50) / 50 * 1.0  # -1.0 à +1.0

        # Calculer shift final (clamp entre 3.0 et 10.0)
        final_shift = base_shift + noise_modifier + denoise_modifier
        final_shift = max(3.0, min(10.0, final_shift))
        transformed["shift"] = round(final_shift, 1)

        # === RIFLEX_FREQ_INDEX (cohérence temporelle) ===
        # consistency 0-100 → riflex 0-2
        consistency = params.get("consistency", 80)
        if consistency >= 85:
            transformed["riflex_freq_index"] = 2  # Très stable
        elif consistency >= 60:
            transformed["riflex_freq_index"] = 1  # Équilibré
        else:
            transformed["riflex_freq_index"] = 0  # Plus créatif

        # === PINGPONG désactivé ===
        # pingpong=true crée un effet miroir (aller-retour) non souhaité pour cinemagraphs
        transformed["pingpong"] = False

        # === FRAMES: compensation crossfade post-processing ===
        # Le crossfade seamless consomme ~0.5s de frames (fusionnées entre fin et début).
        # On ajoute ces frames pour que la durée finale corresponde à la demande.
        fps = params.get("fps", 24)
        crossfade_frames = int(0.5 * fps)
        desired_frames = params.get("frames", 72)
        frames = desired_frames + crossfade_frames
        transformed["frames"] = frames
        output_frames = frames - crossfade_frames

        # === CFG_SCALE ajusté selon color_preservation ===
        base_cfg = params.get("cfg_scale", 7.5)
        color_pres = params.get("color_preservation", 70)
        # Plus de préservation couleur = CFG plus élevé (suit plus le prompt)
        cfg_modifier = (color_pres - 50) / 100 * 2.0  # -1.0 à +1.0
        final_cfg = base_cfg + cfg_modifier
        final_cfg = max(3.0, min(15.0, final_cfg))
        transformed["cfg_scale"] = round(final_cfg, 1)

        # === PROMPT ENGINEERING pour motion_area ===
        motion_area = params.get("motion_area", "full")
        prompt = params.get("prompt", "")

        if motion_area == "center" and "center" not in prompt.lower():
            # Ajouter instruction pour mouvement au centre
            transformed["prompt"] = (
                f"{prompt}, movement focused in center, static edges"
            )
        elif motion_area == "edges" and "edge" not in prompt.lower():
            # Ajouter instruction pour mouvement sur les bords
            transformed["prompt"] = f"{prompt}, movement on edges only, static center"

        # === LOG des transformations ===
        logger.info("🔧 Transformation paramètres frontend → ComfyUI:")
        logger.info(
            f"   frames={frames} générées → ~{output_frames} en sortie "
            f"(crossfade {crossfade_frames}f), demandé={desired_frames}"
        )
        logger.info(
            f"   motion_intensity={motion_intensity}, noise_level={noise_level}, denoise={denoise}%"
        )
        logger.info(f"   → shift={transformed['shift']} (base={base_shift})")
        logger.info(
            f"   consistency={consistency}% → riflex_freq_index={transformed['riflex_freq_index']}"
        )
        logger.info(
            f"   color_preservation={color_pres}% → cfg_scale={transformed['cfg_scale']}"
        )
        if motion_area != "full":
            logger.info(f"   motion_area={motion_area} → prompt modifié")

        # === MAPPING steps → steps_generation pour templates upscale ===
        # Certains templates utilisent steps_generation au lieu de steps
        if "steps" in params:
            transformed["steps_generation"] = params["steps"]

        # Info sur paramètres non supportés
        frame_blending = params.get("frame_blending", 3)
        if frame_blending != 3:
            logger.warning(
                f"   ⚠️ frame_blending={frame_blending} (non supporté - valeur ignorée)"
            )

        return transformed

    def _transform_frontend_params_ltx23(self, params: dict[str, Any]) -> dict[str, Any]:
        """
        Transforme les paramètres frontend en paramètres LTX 2.3 ComfyUI.

        Pipeline officiel : SamplerCustomAdvanced + LTXVImgToVideoConditionOnly.
        STG/CFG fixés par apply_parameters() selon valeurs officielles Lightricks 22B.
        Frames doit être N×8+1.

        Le pipeline LTX utilise pingpong (aller-retour) pour créer l'effet de boucle,
        car LTXVLoopingSampler est un système de tiling temporel (pas de boucle native).
        Pingpong double les frames en sortie : N générées → 2N-2 en sortie.
        On divise donc les frames demandées par 2 avant génération.

        Args:
            params: Paramètres du frontend

        Returns:
            dict: Paramètres transformés pour LTX 2.3
        """
        transformed = params.copy()

        # === FRAMES: arrondir au N×8+1 (pas de pingpong, crossfade en post-processing) ===
        # Le crossfade consomme ~12 frames (0.5s à 24fps) pour la boucle seamless.
        # On ajoute ces frames à la demande pour que la durée finale soit correcte.
        crossfade_frames = 12
        desired_frames = params.get("frames", 121)
        gen_target = desired_frames + crossfade_frames
        # Arrondir au N×8+1 le plus proche
        n = round((gen_target - 1) / 8)
        n = max(1, n)
        frames = n * 8 + 1
        transformed["frames"] = frames
        # Frames de sortie réelles après crossfade
        output_frames = frames - crossfade_frames

        # === I2V STRENGTH (force du conditionnement image dans le latent) ===
        # 0.7 = valeur officielle Lightricks 22B pour I2V (noise_mask=0.3 sur frame 0)
        # Baisser en dessous de 0.7 donne plus de liberté au modèle mais risque
        # de générer du mouvement de caméra au lieu d'animation d'éléments.
        transformed["i2v_strength"] = 0.7

        # === PROMPT ENGINEERING cinemagraph (spécifique LTX 2.3) ===
        # LTX 2.3 génère naturellement du mouvement de caméra — on le contraint
        # explicitement via le prompt car il n'a pas de contrôle caméra natif
        motion_area = params.get("motion_area", "full")
        prompt = params.get("prompt", "")
        if motion_area == "center" and "center" not in prompt.lower():
            transformed["prompt"] = f"{prompt}, movement focused in center, static edges"
        elif motion_area == "edges" and "edge" not in prompt.lower():
            transformed["prompt"] = f"{prompt}, movement on edges only, static center"

        current_prompt = transformed.get("prompt", prompt)
        # Directives caméra statique + cinemagraph
        cinemagraph_suffix = "static camera, fixed frame, locked tripod shot, seamless loop, cinemagraph"
        if "static camera" not in current_prompt.lower():
            transformed["prompt"] = f"{current_prompt}, {cinemagraph_suffix}"

        # === STEPS: forcé à 15 pour LTX 2.3 22B ===
        # Le modèle est calibré pour 15 steps (officiel Lightricks 22B).
        # Au-delà, sur-convergence : le sampler lisse toute variance temporelle → vidéo statique.
        # La LoRA distilled + ClownSampler_Beta res_2s compensent le faible nombre de steps.
        ltx23_steps = 15
        steps_from_user = params.get("steps", 15)
        if steps_from_user != ltx23_steps:
            logger.info(
                f"   ⚠️  Steps forcé: {steps_from_user} → {ltx23_steps} "
                f"(LTX 2.3 22B calibré pour {ltx23_steps} steps)"
            )
        transformed["steps"] = ltx23_steps
        transformed["steps_generation"] = ltx23_steps

        # === CFG VIDEO (guidance vidéo du MultimodalGuider) ===
        # Valeur officielle Lightricks 22B = 3.0.
        # Un CFG plus élevé produit de l'instabilité et du camera drift au lieu
        # de renforcer l'adhérence au prompt (testé avec CFG 6/7/8 — container23).
        ltx23_cfg = 3.0
        cfg_from_user = params.get("cfg_scale", 3.0)
        if cfg_from_user != ltx23_cfg:
            logger.info(
                f"   ⚠️  CFG forcé: {cfg_from_user} → {ltx23_cfg} "
                f"(LTX 2.3 22B calibré pour CFG={ltx23_cfg})"
            )
        video_cfg = ltx23_cfg
        transformed["cfg_scale"] = video_cfg

        # === STG STRING VALUES (full path officiel Lightricks 22B) ===
        transformed["stg_sigmas"] = "1.0"
        transformed["stg_cfg_values"] = str(video_cfg)
        transformed["stg_scale_values"] = "1"
        transformed["stg_rescale_values"] = "0.9"
        transformed["stg_layers_indices"] = "[28]"

        # === LOG ===
        logger.info("🔧 Transformation paramètres frontend → LTX 2.3:")
        logger.info(
            f"   frames={frames} générées (N×8+1) → ~{output_frames} en sortie (crossfade {crossfade_frames}f), "
            f"demandé={desired_frames}"
        )
        logger.info(f"   i2v_strength={transformed['i2v_strength']}")
        logger.info(
            f"   Full path officiel: MultimodalGuider(VIDEO CFG={video_cfg}/STG=1/rescale=0.9 + AUDIO CFG=7), "
            f"ClownSampler_Beta(exponential/res_2s, eta=0.25), LoRA=0.2, {ltx23_steps} steps, pipeline AV"
        )

        return transformed

    def apply_parameters(self, params: dict[str, Any]) -> dict[str, Any]:
        """
        Applique les paramètres au template et retourne le workflow final

        Args:
            params: Paramètres à appliquer

        Returns:
            dict: Workflow ComfyUI prêt à l'emploi
        """
        # Dispatcher la transformation selon la famille de modèle du template
        if self.model_family == "ltx23":
            transformed_params = self._transform_frontend_params_ltx23(params)
        else:
            transformed_params = self._transform_frontend_params(params)

        # Valider les paramètres transformés
        validated_params = self._validate_parameters(transformed_params)

        # Détecter et injecter le modèle automatiquement
        if "model_name" not in validated_params:
            detected_model, model_type = self._detect_available_model()
            validated_params["model_name"] = detected_model
            validated_params["model_type"] = model_type
            logger.info(
                f"🤖 Modèle auto-détecté: {detected_model} (type: {model_type})"
            )

        # Injecter le bon nom de VAE — registre d'abord, fallback legacy
        try:
            registry = get_registry()
            vae_config = registry.get_vae_config(validated_params["model_name"])
        except Exception:
            vae_config = None

        if vae_config:
            validated_params["vae_name"] = vae_config.filename
            logger.info(f"📦 VAE {vae_config.version}: {vae_config.filename}")
        elif validated_params.get("model_type") == "14b":
            validated_params["vae_name"] = "wan_2.1_vae.safetensors"
            logger.info("📦 VAE 14B: wan_2.1_vae.safetensors (254 MB - VAE 2.1)")
        else:
            validated_params["vae_name"] = "wan2.2_vae.safetensors"
            logger.info("📦 VAE 5B: wan2.2_vae.safetensors (1.41 GB - VAE 2.2)")

        # Injecter le text encoder model-spécifique (LTX → Gemma, WAN → T5 hardcodé dans template)
        try:
            registry = get_registry()
            model_cfg = registry.get_model(validated_params["model_name"])
            if model_cfg and model_cfg.text_encoder:
                te_path = f"{model_cfg.text_encoder.filename}"
                validated_params["text_encoder_path"] = te_path
                # Nom plat pour LTXAVTextEncoderLoader (ComfyUI core, pipeline AV officiel)
                # "gemma_3_12B_it/text_encoder/model.safetensors" → "gemma_3_12B_it.safetensors"
                te_flat = te_path.split("/")[0] + ".safetensors"
                validated_params["text_encoder_flat"] = te_flat
                logger.info(f"📝 Text encoder: {te_flat} (AV loader)")
        except Exception:
            pass

        # Construire le chemin de checkpoint adapté au modèle
        checkpoint_path = self._get_model_checkpoint_path(validated_params["model_name"])

        # Gérer le cas MoE 14B (tuple de deux chemins)
        if isinstance(checkpoint_path, tuple):
            high_path, low_path = checkpoint_path
            validated_params["checkpoint_path_high"] = high_path
            validated_params["checkpoint_path_low"] = low_path
            # Garder checkpoint_path pour compatibilité (pointe vers high_noise)
            validated_params["checkpoint_path"] = high_path
            logger.info("📁 Chemins checkpoint MoE 14B:")
            logger.info(f"   - High-noise: {high_path}")
            logger.info(f"   - Low-noise: {low_path}")
        else:
            validated_params["checkpoint_path"] = checkpoint_path
            logger.info(f"📁 Chemin checkpoint: {checkpoint_path}")

        # Configuration full path officielle Lightricks LTX 2.3 22B.
        # Source : workflow officiel LTX-2.3_T2V_I2V_Single_Stage (full path).
        # STGGuiderAdvanced(CFG=3, STG=1, rescale=0.9, cfg_star_rescale=false),
        # ClownSampler_Beta(res_2s, eta=0.25), LoRA strength=0.2, 15 steps.
        if (
            self.model_family == "ltx23"
            and validated_params.get("model_type") == "dev"
        ):
            validated_params["stg_sigmas"] = "1.0"
            validated_params["stg_cfg_values"] = "3"
            validated_params["stg_scale_values"] = "1"
            validated_params["stg_rescale_values"] = "0.9"
            validated_params["stg_layers_indices"] = "[28]"

            # LoRA distilled — le chemin est injecte, la strength (0.2) est dans le template
            validated_params["lora_path"] = "ltx-2.3-22b-distilled-lora-384.safetensors"
            logger.info("🔗 LoRA distilled: ltx-2.3-22b-distilled-lora-384.safetensors (strength=0.2)")

            logger.info(
                "📎 LTX 2.3 22B — full path officiel Lightricks "
                "(MultimodalGuider, pipeline AV, ClownSampler_Beta res_2s, LoRA=0.2)"
            )

        # Remplacer seed=-1 par un seed aléatoire
        if "seed" in validated_params and validated_params["seed"] == -1:
            validated_params["seed"] = self._generate_random_seed()
            logger.info(f"🎲 Seed aléatoire généré: {validated_params['seed']}")

        # Cloner le workflow pour éviter les modifications
        workflow = copy.deepcopy(self.workflow)

        # Remplacer les placeholders EN GARDANT LES TYPES
        workflow = self._substitute_params_recursive(workflow, validated_params)

        # Remplacements spéciaux
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        workflow = self._substitute_params_recursive(workflow, {"timestamp": timestamp})

        # Nettoyage : supprimer les clés _comment* du workflow avant envoi à ComfyUI
        # ComfyUI attend uniquement des dicts de nodes (class_type + inputs) à chaque clé
        workflow = self._strip_workflow_comments(workflow)

        logger.info(
            f"Workflow {self.name} préparé avec {len(validated_params)} paramètres"
        )
        return workflow

    @staticmethod
    def _strip_workflow_comments(workflow: dict[str, Any]) -> dict[str, Any]:
        """
        Supprime les clés _comment* du workflow avant envoi à ComfyUI.

        Les clés _comment_section_* au top-level sont des strings (pas des dicts de nodes)
        et provoquent un crash ComfyUI (HTTP 500). Les clés _comment dans les nodes sont
        inoffensives mais supprimées par précaution.

        Args:
            workflow: Workflow ComfyUI avec potentielles clés commentaires

        Returns:
            dict: Workflow nettoyé, prêt pour ComfyUI
        """
        cleaned = {}
        for key, value in workflow.items():
            if key.startswith("_comment"):
                continue
            if isinstance(value, dict):
                cleaned[key] = {
                    k: v for k, v in value.items() if not k.startswith("_comment")
                }
            else:
                cleaned[key] = value
        return cleaned

    def _substitute_params_recursive(self, obj: Any, params: dict[str, Any]) -> Any:
        """
        Substitue les paramètres de manière récursive EN GARDANT LES TYPES
        Args:
            obj: Objet à traiter
            params: Paramètres de substitution
        Returns:
            Objet avec paramètres substitués
        """
        if isinstance(obj, dict):
            return {
                k: self._substitute_params_recursive(v, params) for k, v in obj.items()
            }
        elif isinstance(obj, list):
            return [self._substitute_params_recursive(item, params) for item in obj]
        elif isinstance(obj, str):
            # Si c'est EXACTEMENT un placeholder complet, retourner avec le type original
            for param_name, param_value in params.items():
                placeholder = f"{{{param_name}}}"
                if obj == placeholder:
                    # Retourner le type original (int, float, etc.)
                    return param_value

            # Sinon, c'est une substitution partielle dans une string
            result = obj
            for param_name, param_value in params.items():
                placeholder = f"{{{param_name}}}"
                if placeholder in result:
                    # Vérifier si c'est la SEULE valeur
                    if result == placeholder:
                        return param_value
                    # Sinon remplacer dans la string
                    result = result.replace(placeholder, str(param_value))
            return result
        else:
            return obj

    def _validate_parameters(self, params: dict[str, Any]) -> dict[str, Any]:
        """Valide et normalise les paramètres selon les règles du template"""
        validated = {}

        for param_name, param_config in self.parameters.items():
            # Obtenir la valeur (fournie ou par défaut)
            if param_name in params:
                value = params[param_name]
            elif param_config.get("default") is not None:
                value = param_config["default"]
            elif param_config.get("required", False):
                raise ValueError(f"Paramètre requis manquant: {param_name}")
            else:
                continue

            # Validation selon le type
            param_type = param_config.get("type", "string")

            if param_type == "integer":
                value = int(value)
                min_val = param_config.get("min")
                max_val = param_config.get("max")
                if min_val is not None and value < min_val:
                    value = min_val
                if max_val is not None and value > max_val:
                    value = max_val

            elif param_type == "float":
                value = float(value)
                min_val = param_config.get("min")
                max_val = param_config.get("max")
                if min_val is not None and value < min_val:
                    value = min_val
                if max_val is not None and value > max_val:
                    value = max_val

            elif param_type == "string":
                value = str(value)
                enum_values = param_config.get("enum")
                if enum_values and value not in enum_values:
                    raise ValueError(
                        f"Valeur invalide pour {param_name}: {value}. Valeurs acceptées: {enum_values}"
                    )

            validated[param_name] = value

        logger.debug(f"Paramètres validés: {list(validated.keys())}")
        return validated


class WorkflowManager:
    """Gestionnaire central des templates et workflows"""

    def __init__(self, templates_dir: str = "workflows/templates"):
        self.templates_dir = Path(templates_dir)
        self.templates: dict[str, WorkflowTemplate] = {}

        # Charger tous les templates au démarrage
        self.load_templates()

    def load_templates(self):
        """Charge tous les templates depuis le dossier templates"""
        if not self.templates_dir.exists():
            logger.warning(f"Dossier templates inexistant: {self.templates_dir}")
            return

        loaded_count = 0
        for template_file in self.templates_dir.glob("*.json"):
            try:
                with open(template_file, "r", encoding="utf-8") as f:
                    template_data = json.load(f)

                template = WorkflowTemplate(template_data)
                template_id = template_file.stem
                self.templates[template_id] = template
                loaded_count += 1

                logger.info(f"Template chargé: {template_id} - {template.name}")

            except Exception as e:
                logger.error(f"Erreur chargement template {template_file}: {e}")

        logger.info(f"✅ {loaded_count} templates chargés")

    def get_template(self, template_id: str) -> WorkflowTemplate | None:
        """Récupère un template par son ID"""
        return self.templates.get(template_id)

    def list_templates(self) -> list[dict[str, str]]:
        """Liste tous les templates disponibles"""
        return [
            {
                "id": template_id,
                "name": template.name,
                "description": template.description,
                "version": template.version,
            }
            for template_id, template in self.templates.items()
        ]

    def create_workflow(
        self, template_id: str, parameters: dict[str, Any]
    ) -> dict[str, Any]:
        """
        Crée un workflow en appliquant les paramètres à un template

        Args:
            template_id: ID du template à utiliser
            parameters: Paramètres à appliquer

        Returns:
            dict: Workflow ComfyUI prêt
        """
        template = self.get_template(template_id)
        if not template:
            raise ValueError(f"Template non trouvé: {template_id}")

        workflow = template.apply_parameters(parameters)
        logger.success(f"✅ Workflow créé depuis template {template_id}")

        return workflow

    def validate_template_parameters(
        self, template_id: str, parameters: dict[str, Any]
    ) -> dict[str, str]:
        """
        Valide les paramètres d'un template sans créer le workflow

        Returns:
            dict: Rapport de validation {param_name: status}
        """
        template = self.get_template(template_id)
        if not template:
            raise ValueError(f"Template non trouvé: {template_id}")

        validation_report = {}

        for param_name, param_config in template.parameters.items():
            if param_name in parameters:
                try:
                    # Essayer la validation
                    template._validate_parameters({param_name: parameters[param_name]})
                    validation_report[param_name] = "valid"
                except Exception as e:
                    validation_report[param_name] = f"error: {str(e)}"
            elif param_config.get("required", False):
                validation_report[param_name] = "missing_required"
            else:
                validation_report[param_name] = "using_default"

        return validation_report

    def validate_workflow(self, workflow_id: str) -> dict[str, Any]:
        """
        Valide un workflow et retourne un rapport

        Args:
            workflow_id: ID du workflow à valider

        Returns:
            dict: Rapport de validation
        """
        template = self.get_template(workflow_id)

        if not template:
            return {"valid": False, "errors": [f"Template {workflow_id} non trouvé"]}

        report = {
            "valid": True,
            "warnings": [],
            "errors": [],
            "info": {
                "name": template.name,
                "version": template.version,
                "node_count": len(template.workflow),
                "parameter_count": len(template.parameters),
            },
        }

        # Vérifier les nœuds
        for node_id, node in template.workflow.items():
            if "class_type" not in node:
                report["errors"].append(f"Nœud {node_id}: class_type manquant")
                report["valid"] = False

            if "inputs" not in node:
                report["warnings"].append(f"Nœud {node_id}: aucun input défini")

        # Vérifier les paramètres
        for param_name, param_config in template.parameters.items():
            if "type" not in param_config:
                report["errors"].append(f"Paramètre {param_name}: type manquant")
                report["valid"] = False

        return report

    def get_workflow_info(self, workflow_id: str) -> dict[str, Any | None]:
        """
        Retourne les informations détaillées d'un workflow

        Args:
            workflow_id: ID du workflow

        Returns:
            dict: Informations du workflow
        """
        template = self.get_template(workflow_id)

        if not template:
            return None

        return {
            "id": workflow_id,
            "name": template.name,
            "description": template.description,
            "version": template.version,
            "parameters": {
                name: {
                    "type": config.get("type"),
                    "default": config.get("default"),
                    "required": config.get("required", False),
                    "description": config.get("description", ""),
                    "min": config.get("min"),
                    "max": config.get("max"),
                    "enum": config.get("enum"),
                }
                for name, config in template.parameters.items()
            },
            "metadata": template.metadata,
            "node_count": len(template.workflow),
            "tags": template.metadata.get("tags", []),
        }

    def list_workflows_by_tag(self, tag: str) -> list[dict[str, str]]:
        """
        Liste les workflows par tag

        Args:
            tag: Tag à filtrer

        Returns:
            list: Workflows correspondants
        """
        workflows = []

        for workflow_id, template in self.templates.items():
            tags = template.metadata.get("tags", [])
            if tag in tags:
                workflows.append(
                    {
                        "id": workflow_id,
                        "name": template.name,
                        "description": template.description,
                    }
                )

        return workflows

    def get_parameter_schema(self, workflow_id: str) -> dict[str, Any | None]:
        """
        Retourne le schéma JSON des paramètres d'un workflow

        Args:
            workflow_id: ID du workflow

        Returns:
            dict: Schéma JSON des paramètres
        """
        template = self.get_template(workflow_id)

        if not template:
            return None

        schema = {"type": "object", "properties": {}, "required": []}

        for param_name, param_config in template.parameters.items():
            param_type = param_config.get("type", "string")

            # Mapper types Python vers JSON Schema
            type_mapping = {
                "string": "string",
                "integer": "integer",
                "float": "number",
                "boolean": "boolean",
            }

            json_type = type_mapping.get(param_type, "string")

            param_schema = {
                "type": json_type,
                "description": param_config.get("description", ""),
            }

            # Ajouter contraintes
            if "min" in param_config:
                param_schema["minimum"] = param_config["min"]
            if "max" in param_config:
                param_schema["maximum"] = param_config["max"]
            if "enum" in param_config:
                param_schema["enum"] = param_config["enum"]
            if "default" in param_config:
                param_schema["default"] = param_config["default"]

            schema["properties"][param_name] = param_schema

            # Ajouter aux required si nécessaire
            if param_config.get("required", False):
                schema["required"].append(param_name)

        return schema


# Instance globale du gestionnaire
workflow_manager = WorkflowManager()

if __name__ == "__main__":
    # Test du gestionnaire de workflows
    from src.logger import setup_logger

    # Configurer le logger pour voir les outputs
    setup_logger(level="INFO")

    logger.info("🧪 Test du gestionnaire de workflows")

    # Lister les templates
    templates = workflow_manager.list_templates()
    logger.info(f"Templates disponibles: {len(templates)}")

    for template_info in templates:
        logger.info(f"  - {template_info['id']}: {template_info['name']}")

    # Test de création de workflow
    if templates:
        template_id = templates[0]["id"]
        test_params = {
            "input_image": "test.jpg",
            "prompt": "gentle water movement",
            "steps": 25,
        }

        try:
            workflow = workflow_manager.create_workflow(template_id, test_params)
            logger.success(f"✅ Workflow test créé avec {len(workflow)} nœuds")
        except Exception as e:
            logger.error(f"❌ Erreur création workflow: {e}")

    logger.info("Test terminé")
