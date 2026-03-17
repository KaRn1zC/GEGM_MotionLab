# CHANGES TRACKER - Journal de modifications

**Objectif** : Tracking temporaire des changements pour alimenter la mise à jour de `CLAUDE.md`.

**Usage** :
- Ajouter une entrée après chaque correction/modification
- Après mise à jour de `CLAUDE.md`, **NETTOYER** ce fichier (garder max 2-3 entrées récentes)

---

## Modifications récentes

### [2026-03-16] - Intégration LTX 2.3 (v5.0.0)

**Objectif :** Ajouter LTX 2.3 (DiT 22B, Lightricks) comme modèle disponible dans le pipeline. Deux variantes : Distilled FP8 (48GB+, 8 steps) et Dev BF16 (80GB+, 40 steps).

**Nouveaux fichiers :**
- `workflows/templates/ltx23_i2v.json` — Template I2V avec boucle seamless native (LTXVLoopingSampler + STG guidance)
- `workflows/templates/ltx23_i2v_with_upscale.json` — Template I2V + UltraSharp 4x upscale (v2 future : latent upsampler natif)

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
