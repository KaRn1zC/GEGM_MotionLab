# CHANGES TRACKER - Journal de modifications

**Objectif** : Tracking temporaire des changements pour alimenter la mise à jour de `CLAUDE.md`.

**Usage** :
- Ajouter une entrée après chaque correction/modification
- Après mise à jour de `CLAUDE.md`, **NETTOYER** ce fichier (garder max 2-3 entrées récentes)

---

## Modifications récentes

### [2026-04-02] - Progression temps réel ComfyUI → UI

**Objectif :** Remplacer la progression figée (0→50%→100%) par un suivi temps réel fidèle de chaque phase du pipeline ComfyUI.

**Problème :**
`routes.py` définissait des milestones hardcodés (10%, 30%, 50%, 80%, 85%, 90%) sans jamais lire la progression réelle de ComfyUI. Le job restait bloqué à 50% pendant toute la génération (~13min). De plus, les nodes sans callback de progression (HAT-L 4x upscale) envoyaient 100% en boucle pendant ~8 minutes.

**Solution :**
1. `comfyui_client.py` — Ajout d'un paramètre `progress_callback` dans `wait_for_completion()`, appelé toutes les 2s avec l'objet `WorkflowProgress`
2. `routes.py` — Nouvelle classe `ComfyUIProgressTracker` : machine à états qui détecte les phases du pipeline (setup→sampling→VAE decode→upscale→combine) et mappe la progression ComfyUI vers le Job
3. Pour le HAT-L 4x (pas de progression interne) : estimation temporelle basée sur `nb_frames × temps/frame`, calibré dynamiquement depuis la vitesse du VAE decode précédent
4. Labels d'étape contextuels avec temps restant estimé pour l'upscale

**Plages de progression :**
- 2% : Préparation du workflow
- 5→10% : Setup/chargement modèle
- 10→35% : Sampling (progression exacte ComfyUI)
- 35→50% : VAE Decode (progression exacte ComfyUI)
- 50→80% : HAT-L 4x Upscale (estimation temporelle adaptative)
- 80→85% : VHS_VideoCombine (progression exacte ComfyUI)
- 85→100% : Post-processing (ffmpeg resize, crossfade, finalisation)

**Fichiers modifiés :**
- `src/comfyui_client.py` — `wait_for_completion()` : paramètre `progress_callback`
- `web_interface/routes.py` — Classe `ComfyUIProgressTracker` + remplacement milestones hardcodés

---

### [2026-03-25] - Fix hallucination LTX 2.3 : text encoder loader + nettoyage workflow (v12.1.0)

**Objectif :** Corriger l'hallucination systématique du modèle LTX 2.3 22B (frame 0 fidèle à l'input, frames 1+ totalement divergentes — structures géométriques sans rapport avec l'image ni les prompts).

**Cause racine :**
Le text encoder loader `LTXVGemmaCLIPModelLoader` (plugin Lightricks) produit des embeddings avec une normalisation **RMSNorm per-token** incompatible. Le diffusion model LTX 2.3 attend le format **global min-max** avec le flag `unprocessed_ltxav_embeds=True`, produit par `LTXAVTextEncoderLoader` (ComfyUI core, `nodes_lt_audio.py`). Sans ce flag, le modèle ne traite pas les embeddings via son connecteur interne → conditioning incompatible → hallucination sur TOUTES les versions (v7 à v12).

**Vérification workflow officiel :**
Le workflow officiel Lightricks (`LTX-2.3_T2V_I2V_Single_Stage_Distilled_Full.json` dans `ComfyUI-LTXVideo/example_workflows/2.3/`) utilise `LTXAVTextEncoderLoader`, PAS `LTXVGemmaCLIPModelLoader`. Confirmé : même fichier Gemma (`gemma_3_12B_it.safetensors` depuis `Comfy-Org/ltx-2`, repo public), seul le loader change.

**Corrections :**
- `workflows/templates/ltx23_i2v.json` — Node 3 : `LTXVGemmaCLIPModelLoader` → `LTXAVTextEncoderLoader`
- `workflows/templates/ltx23_i2v_with_upscale.json` — Idem
- `workflows/workflow_manager.py` — Ajout dérivation `text_encoder_flat` + filtre `_strip_workflow_comments()`
- `docker-entrypoint.sh` — Symlink plat text encoder pour le core loader + fix `hf download` + `.env` info
- `tests/test_model_registry.py` — Correction 3 assertions text encoder path

**Bug secondaire corrigé :** Les clés `_comment_section_*` dans `ltx23_i2v.json` (strings au top-level du workflow dict) causaient un HTTP 500 de ComfyUI. Supprimées + filtre défensif ajouté.

---

### [2026-03-24] - REFONTE pipeline LTX 2.3 I2V — conformité workflow officiel Lightricks (v8.0.0)

**Objectif :** Corriger l'hallucination totale du modèle LTX 2.3 22B. Le pipeline v7.0.0 utilisait `LTXVAddGuideAdvanced` sans `LTXVPreprocess` ni `LTXVConditioning`, causant une divergence complète dès frame 1 (image d'input correcte en frame 0, puis hallucination pure).

**Cause racine :**
1. `LTXVPreprocess` (ComfyUI core, `comfy_extras/nodes_lt.py`) était absent — l'image entrait dans le VAE sans compression CRF H.264, créant un décalage avec la distribution d'entraînement du modèle
2. `LTXVConditioning` (ComfyUI core, `comfy_extras/nodes_lt.py`) était absent — le conditioning n'avait pas d'info de frame_rate, le modèle perdait toute cohérence temporelle
3. `LTXVAddGuideAdvanced` (Lightricks plugin) n'est PAS utilisé dans le workflow officiel Lightricks I2V — son ajout sans `LTXVPreprocess` créait des signaux de conditioning contradictoires

**Erreur documentaire :** CLAUDE.md affirmait que `LTXVPreprocess` et `LTXVConditioning` "N'EXISTENT PAS". C'est faux — ils existent dans ComfyUI core (pas dans le plugin Lightricks). Cette erreur a mené à un pipeline fondamentalement incorrect.

**Fichiers modifiés :**
- `workflows/templates/ltx23_i2v.json` — v7.0.0 → v8.0.0 : +LTXVPreprocess (crf=18), +LTXVConditioning (frame_rate), -LTXVAddGuideAdvanced
- `workflows/templates/ltx23_i2v_with_upscale.json` — idem
- `CLAUDE.md` — correction architecture LTX 2.3, notes critiques, référence nodes

**Pipeline v8.0.0 :**
```
LoadImage → LTXVPreprocess(crf=18) → LTXVImgToVideoConditionOnly(strength=0.7)
CLIPTextEncode → LTXVConditioning(frame_rate) → STGGuiderAdvanced
SamplerCustomAdvanced → VAEDecode → VHS_VideoCombine(pingpong=true)
```

---

### [2026-03-17] - Pipeline model-agnostic Makefile + setup script (v5.1.0)

**Objectif :** Le pipeline local (download → split → upload → clean) était hardcodé WAN 2.2. Désormais entièrement piloté par le registre modèles, compatible LTX 2.3 sans modification.

**Fichiers modifiés :**
- `src/model_registry.py` — `DownloadManifest` multi-repo : chaque fichier porte son propre `repo` (corrige le bug Gemma/Lightricks)
- `scripts/setup_wan22_native.sh` — Fallback registre fonctionnel : download multi-repo, vérification T5 conditionnelle, symlinks et vérification finale généralisés
- `Makefile` — Toutes les cibles modèle-agnostic (download-models, models-clean, rclone-verify exigent MODEL=), alias LTX (workflow-ltx-fast/pro/all), workflow-all (4 modèles), workflow-wan-all remplace workflow-both
- `config/model_registry.yaml` — Display names raccourcis (WAN 2.2 5B, LTX 2.3 22B Fast/Pro)

**Bugs corrigés :**
- `DownloadManifest.repo` unique → multi-repo (LTX Gemma serait téléchargé depuis le mauvais repo)
- `verify_t5_integrity.py` appelé pour tous les modèles → conditionnel (skip pour LTX qui utilise Gemma)
- `_models-deep-clean-auto` hardcodé `wan2.2-*` → boucle dynamique `models/*/`

**Documentation synchronisée :**
- [x] CLAUDE.md → v5.1.0
- [x] README.md → v5.1.0
- [x] README_DOCKER.md → v5.1.0
- [x] README_RUNPOD.md → v5.1.0
- [x] docs/ARCHITECTURE.md → v5.1.0
- [x] GUIDE_DOCUMENTATION.md → v5.1.0

---

### [2026-03-16] - Intégration LTX 2.3 (v5.0.0)

**Objectif :** Ajouter LTX 2.3 (DiT 22B, Lightricks) comme modèle disponible dans le pipeline. Deux variantes : Distilled FP8 (48GB+, 8 steps) et Dev BF16 (80GB+, 40 steps).

**Nouveaux fichiers :**
- `workflows/templates/ltx23_i2v.json` — Template I2V avec boucle seamless native (LTXVLoopingSampler + STG guidance)
- `workflows/templates/ltx23_i2v_with_upscale.json` — Template I2V + HAT-L 4x upscale

**Fichiers modifiés :**
- `config/model_registry.yaml` — 2 modèles LTX 2.3 (distilled + dev) avec text_encoder Gemma 3 12B, VAE intégré, résolution 1080p
- `src/model_registry.py` — `ModelTextEncoderConfig` dataclass, champ `text_encoder` sur `ModelConfig`, manifeste skip VAE intégré
- `workflows/workflow_manager.py` — `_transform_frontend_params_ltx23()`, dispatch model_family, injection text_encoder, détection multi-répertoire
- `install-comfyui.sh` — ComfyUI-LTXVideo (Lightricks), répertoires LTX
- `tests/test_model_registry.py` — 22 tests ajoutés (LTX distilled, dev, manifeste, text encoder)

**Différences architecturales LTX 2.3 vs WAN 2.2 :**
- Text encoder : Gemma 3 12B (pas T5) — champ `text_encoder` model-spécifique dans registre
- VAE : intégré dans le checkpoint (128 canaux, pas de fichier séparé)
- Boucle : native via LTXVLoopingSampler (first+last frame conditioning)
- Guidance : STG (Spatio-Temporal Guidance) au lieu de shift/riflex_freq_index
- Frames : contrainte N×8+1 (9, 17, 25, ..., 241)

---

### [2026-03-16] - Pipeline résolution/upscale model-agnostic (v4.6.0)

**Objectif :** Le pipeline de résolution, upscale et supersampling est désormais piloté par le registre modèles. Changer de modèle = changer les valeurs YAML. Zéro modification du code Python d'orchestration.

**Nouveaux fichiers :**
- `tests/test_resolution_strategy.py` — 34 tests (non-régression WAN 2.2, fallback, extensibilité stride/résolution)

**Fichiers modifiés :**
- `config/model_registry.yaml` — bloc `resolution` + `workflow_template_upscale` sur les 2 modèles
- `src/model_registry.py` — `ResolutionConfig` dataclass, champs optionnels sur `ModelConfig`, parsing, accesseurs
- `web_interface/routes.py` — `calculate_optimal_generation_strategy()` model-agnostic (registre → fallback WAN 2.2), sélection workflow, VAE tiling, stride alignment pilotés par le registre
- `tests/test_model_registry.py` — 10 tests ajoutés pour `ResolutionConfig` et accesseurs

**Principe architectural :**
- Registre YAML = les **nombres** (résolution max, stride, seuils)
- Templates workflow JSON = le **comportement** (noeuds ComfyUI, upscale method)
- Code Python = orchestration **générique** (zéro `if model == "xxx"`)

---

### [2026-03-16] - Registre modèles extensible (v4.5.0)

**Objectif :** Ajouter un nouveau modèle = 1 entrée YAML + 1 template workflow JSON. Zéro modification Python/bash/Makefile.

**Nouveaux fichiers :**
- `config/model_registry.yaml` — source de vérité unique (remplace model_versions.yaml + model_metadata.json)
- `src/model_registry.py` — module Python + CLI bash (dataclasses typées, singleton)
- `tests/test_model_registry.py` — 35 tests (équivalence, CLI, composants partagés)

**Fichiers modifiés (approche hybride registre → fallback legacy) :**
- `workflows/workflow_manager.py` — detection_priority, VAE, checkpoint via registre
- `scripts/verify_diffusion_model.py` — fichiers, tailles, clés critiques via registre
- `scripts/verify_vae.py` — config VAE, canaux, clés critiques via registre
- `scripts/verify_t5_integrity.py` — filename T5, clés critiques via registre
- `scripts/download_models_from_owncloud.py` — verify_model_files() via registre
- `web_interface/routes.py` — timeout, model_priority, model-info via registre
- `scripts/setup_wan22_native.sh` — branche registre pour modèles non-legacy
- `docker-entrypoint.sh` — check fichiers, symlinks, VAE via registre
- `Makefile` — targets génériques `workflow` et `rclone-upload` + alias rétrocompatibles

**Fichiers supprimés :**
- `config/model_versions.yaml` (inutilisé, remplacé par registre)
- `config/model_metadata.json` (info marketing, fusionnée dans registre)

---

### [2026-03-16] - Nettoyage complet du projet (v4.4.0)

**Corrections en 6 phases :**

**Phase 1 - Dead files supprimés :**
- `web_interface/static/js/app.js` (ancien frontend Bootstrap, remplacé par index.html Tailwind)
- `web_interface/static/css/style.css` (idem)
- `web_interface/templates/base.html` (idem)
- `scripts/convert_vae_channels.py` (convertisseur VAE .pth obsolète, format safetensors natif)
- `scripts/wait-for-comfyui.sh` (logique dupliquée dans docker-entrypoint.sh)
- `config/model_versions.yaml.backup` (backup inutilisé)

**Phase 2 - Documentation et config :**
- `config/logging.yaml` : ajout commentaire "référence uniquement, non chargé par l'app"
- `docker-compose.yml` : volumes `/app/` corrigés en `/workspace/` (cohérence avec Dockerfile WORKDIR)
- `docker-compose.override.yml` : idem
- `README_DOCKER.md` : description multi-stage corrigée en single-stage, chemins `/app/` → `/workspace/`

**Phase 3 - Templates erreur :**
- `web_interface/templates/404.html` : page Tailwind standalone créée (était vide)
- `web_interface/templates/500.html` : idem

**Phase 4 - Bug fixes :**
- `workflows/workflow_manager.py:365` : `detected_model` → `validated_params["model_name"]` (NameError latent)
- `scripts/setup_wan22_native.sh` : bloc elif dupliqué supprimé (lignes 261-328)
- `src/comfyui_client.py:34` : `websocket_timeout = 1200` → `5400` (valeur réelle)
- `web_interface/routes.py:get_thumbnail()` : ajout logger.warning sur le placeholder
- `src/owncloud_uploader.py:list_files()` : ajout logger.warning + TODO sur le stub

**Phase 5 - Dead code Python :**
- `src/comfyui_client.py` : supprimé `create_wan22_workflow()` (class_types obsolètes)
- `src/__init__.py` : `auto_configure()` retiré de l'import (évite side effects psutil/torch)
- `tests/test_comfyui_client.py` : mise à jour (retrait import + test obsolètes)

**Phase 6 - Code quality :**
- Typing modernisé (10 fichiers) : `Dict` → `dict`, `Optional[X]` → `X | None`, etc.
- Requirements nettoyés (~130 packages inutilisés retirés : mlflow, fastapi, pandas, etc.)
- `sys.path.append` retiré de 24 fichiers, remplacé par `PYTHONPATH=/workspace` dans Dockerfile
- `pyproject.toml` : ajout `[tool.setuptools.packages.find]` pour `pip install -e .`
- Imports orphelins (`import sys`, `from pathlib import Path`) nettoyés dans 11 fichiers

**Corrections tests pré-existants :**
- `tests/test_workflows.py` : réécrit (anciens noms `wan22_i2v` → `wan22_5b_i2v`, ajout tests 14B/MoE)
- `tests/test_comfyui_client.py` : assertions types corrigées (`"100"` → `100`)

**Versions templates inchangées :**
- `wan22_5b_i2v.json` : v4.5.1
- `wan22_5b_with_upscale.json` : v3.5.1
- `wan22_14b_i2v.json` : v2.0.5
- `wan22_14b_with_upscale.json` : v2.0.5

**Documentation synchronisée :**
- [x] CLAUDE.md → v4.4.0
- [x] README.md → v4.4.0
- [x] README_DOCKER.md → v4.4.0
- [x] docs/ARCHITECTURE.md → v4.4.0
- [x] GUIDE_DOCUMENTATION.md → structure mise à jour

---

## WORKFLOW OBLIGATOIRE

**Après chaque correction** :
1. Ajouter entrée `CHANGES_TRACKER.md`
2. MàJ `CLAUDE.md` avec infos essentielles
3. **NETTOYER** fichiers documentation après MàJ
4. **JAMAIS git add/commit/push auto** (uniquement sur demande explicite)
