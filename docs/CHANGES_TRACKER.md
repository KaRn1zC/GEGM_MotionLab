# CHANGES TRACKER - Journal de modifications

**Objectif** : Tracking temporaire des changements pour alimenter la mise à jour de `CLAUDE.md`.

**Usage** :
- ✅ Ajouter une entrée après chaque correction/modification
- ✅ Après mise à jour de `CLAUDE.md`, **NETTOYER** ce fichier (garder max 2-3 entrées récentes)

---

## 📅 Modifications récentes

### [2025-12-10 PM #3] - ✅ FIX CRITIQUE: verify_diffusion_model.py références FP8 manquées

**Problème** : Workflow échouait avec "Fichier introuvable: wan2.2_i2v_high_noise_14B_fp8_scaled.safetensors"
- Script de vérification cherchait encore fichiers FP8 au lieu de FP16
- Oublié lors de l'audit initial des références FP8

**Solution implémentée** :

**scripts/verify_diffusion_model.py** (4 corrections) :
- Ligne 37: `wan2.2_i2v_high_noise_14B_fp8_scaled.safetensors` → `wan2.2_i2v_high_noise_14B_fp16.safetensors`
- Ligne 38: `wan2.2_i2v_low_noise_14B_fp8_scaled.safetensors` → `wan2.2_i2v_low_noise_14B_fp16.safetensors`
- Ligne 66: Tailles attendues (12.0, 16.0) GB → (25.0, 32.0) GB (pour ~28.6 GB FP16)
- Ligne 67: Tailles attendues (12.0, 16.0) GB → (25.0, 32.0) GB (pour ~28.6 GB FP16)

**Fichiers modifiés** :
- `scripts/verify_diffusion_model.py` : Correction références FP8 → FP16 + tailles attendues

**Impact** :
- ✅ **Workflows fonctionnels** : `workflow-5b`, `workflow-14b`, `workflow-both` peuvent s'exécuter
- ✅ **Vérification correcte** : Accepte fichiers FP16 de ~28.6 GB (au lieu de rejeter car >16 GB)
- ✅ **Cohérence totale** : Plus AUCUNE référence FP8 dans le projet

---

### [2025-12-10 PM #2] - ✅ SIMPLIFICATION WORKFLOWS: 3 commandes principales avec deep-clean

**Objectif** : Simplifier les workflows Makefile pour clarté et automatisation complète

**Problème initial** :
- Trop de commandes similaires (`full-workflow-5b`, `full-workflow-14b`, `sequential-upload-workflow`, `full-upload-workflow`)
- Pas de deep-clean automatique après workflows
- Workflow séquentiel pouvait surcharger le disque

**Solution implémentée** :

**A. Création `_models-deep-clean-auto`** (Makefile lignes 106-120) :
- Version non-interactive de `models-deep-clean` pour automation
- Supprime TOUT : modèles, VAE, T5, CLIP, upscalers, chunks, cache
- Pas de confirmation requise (usage interne workflows)

**B. Trois workflows principaux simplifiés** :

1. **`make workflow-5b`** (lignes 213-244) :
   - Download modèle 5B + composants (9.3GB + 14GB partagés)
   - Vérifications intégrité automatiques
   - Split et upload vers OwnCloud
   - Vérification upload
   - **Deep clean automatique** (libère ~120GB)

2. **`make workflow-14b`** (lignes 179-211) :
   - Download modèle 14B + composants (57GB + 14GB partagés)
   - Vérifications intégrité automatiques
   - Split et upload vers OwnCloud
   - Vérification upload
   - **Deep clean automatique** (libère ~120GB)

3. **`make workflow-both`** (lignes 246-280) :
   - **SÉQUENTIEL** : Exécute workflow-14b, PUIS workflow-5b
   - Deep clean après chaque modèle (évite surcharge disque)
   - Vérification finale des deux uploads
   - Total : ~140GB max utilisé (au lieu de 180GB en parallèle)

**Fichiers modifiés** :
- `Makefile` : Workflows simplifiés + deep-clean auto + documentation

**Impact** :
- ✅ **3 commandes claires** : Une par modèle + une séquentielle
- ✅ **Deep clean automatique** : Libération disque garantie après chaque workflow
- ✅ **Vérifications complètes** : Download → Vérif → Split → Upload → Vérif → Clean
- ✅ **Séquentiel optimisé** : Évite surcharge disque (14B → clean → 5B → clean)
- ✅ **Documentation inline** : Header explicatif dans Makefile
- ✅ **Anciennes commandes supprimées** : Plus de confusion

---

### [2025-12-10 PM] - ✅ CORRECTIONS AUDIT: FP8→FP16 + CLIP/Upscalers OwnCloud (Option A)

**Audit complet effectué** : Vérification minutieuse de tous les workflows

**Problèmes critiques corrigés** :

1. **docker-entrypoint.sh ligne 72** : Appel incorrect `setup_wan22_native.sh --model` → `setup_wan22_native.sh`
   - Script attend argument positionnel, pas option --model

2. **download_models_from_owncloud.py lignes 30, 31, 72, 75** : Références FP8 obsolètes → FP16
   - Modèle 14B utilise FP16 depuis migration
   - Correction: `wan2.2_i2v_*_14B_fp8_scaled` → `wan2.2_i2v_*_14B_fp16`

3. **Makefile models-deep-clean** : Manquait clip_vision/ et upscale_models/
   - Ajout lignes 110-111 : `rm -rf models/clip_vision` et `rm -rf models/upscale_models`
   - Nettoyage complet maintenant (~2.5 GB supplémentaires)

4. **ARCHITECTURAL: CLIP/Upscalers non uploadés sur OwnCloud** (Option A implémentée)

**Solution Option A** : Symlinks dans dossiers modèles

**A. setup_wan22_native.sh (lignes 468-511)** :
- Après download CLIP/upscalers dans `models/clip_vision/` et `models/upscale_models/`
- Création symlinks relatifs dans `models/{model_name}/clip_vision/` et `models/{model_name}/upscale_models/`
- Symlinks pour 5B ET 14B selon le mode (all/5b/14b)
- `split_and_upload.py` utilise déjà `--copy-links` → upload automatique du contenu réel

**B. docker-entrypoint.sh (lignes 281-364)** :
- Section complètement réécrite : "CLIP VISION + UPSCALERS"
- Logique en 3 étapes pour chaque composant :
  1. Vérifier si présent dans `$MODEL_DIR/{clip_vision|upscale_models}/` (depuis OwnCloud)
  2. Si oui → copier vers dossiers globaux ComfyUI
  3. Si non → fallback upstream (HuggingFace/GitHub)
- Priorité OwnCloud, fallback upstream automatique

**Fichiers modifiés** :
- `docker-entrypoint.sh` : Correction appel + logique CLIP/upscalers depuis OwnCloud
- `scripts/download_models_from_owncloud.py` : FP8 → FP16 (3 occurrences)
- `Makefile` : models-deep-clean + clip_vision + upscale_models
- `scripts/setup_wan22_native.sh` : Création symlinks CLIP/upscalers dans models/{model_name}/

**Impact** :
- ✅ **Upload OwnCloud complet** : Modèles + VAE + T5 + CLIP + Upscalers (TOUT inclus)
- ✅ **Download OwnCloud complet** : Composants partagés inclus dans backup
- ✅ **Fallback intelligent** : Si OwnCloud manque CLIP/upscalers → upstream automatique
- ✅ **Nettoyage complet** : models-deep-clean supprime TOUT (~2.5 GB ajoutés)
- ✅ **Cohérence FP16** : Plus de références FP8 obsolètes
- ✅ **Workflow fonctionnel** : `make full-workflow-5b/14b` upload TOUT sur OwnCloud

---

### [2025-12-10 AM] - ✅ SYSTÈME UPSTREAM + CLIP/Upscalers: Download + Healthcheck + Fallback OwnCloud

**Objectif** : Système professionnel de téléchargement avec upstream prioritaire et fallback automatique

**Problème initial** :
- Composants partagés (CLIP Vision, upscalers) téléchargés uniquement dans container, pas localement
- Pas de vérification version upstream avant download
- Pas de cleanup automatique en cas d'échec download
- Makefile appelait `setup_wan22_native.sh` avec argument modèle individuel non supporté

**Solution implémentée** :

**A. Système de métadonnées et healthcheck** :
1. **models_metadata.json** (NOUVEAU) : Référence des tailles attendues pour détection version
   - Modèles 5B et 14B (fichiers diffusion + VAE + T5)
   - Composants partagés (CLIP Vision, UltraSharp, RealESRGAN)
   - Tolérance ±1% pour variations compression

2. **check_upstream_health.py** (NOUVEAU) : Healthcheck upstream avant download
   - Vérifie disponibilité sources (HuggingFace + GitHub)
   - Compare tailles fichiers via HEAD requests (rapide, pas de download)
   - Détecte nouvelles versions upstream automatiquement
   - Logging Loguru détaillé

3. **cleanup_partial_downloads.py** (NOUVEAU) : Nettoyage fichiers partiels si échec
   - Vérifie intégrité basée sur taille attendue (±1%)
   - Supprime fichiers incomplets/corrompus
   - Nettoie dossiers temporaires (chunks, .temp_download)

**B. Modifications setup_wan22_native.sh** :
1. **CLIP + Upscalers download** (lignes 334-397) : Download composants partagés
   - CLIP Vision (~2.4 GB) depuis HuggingFace
   - 4x-UltraSharp (~67 MB) depuis HuggingFace
   - RealESRGAN (~64 MB) depuis GitHub Releases

2. **Support download individuel 5B** (lignes 251-318, NOUVEAU) :
   - Ajout elif branch pour `wan2.2-ti2v-5b`
   - Download diffusion + T5 + VAE
   - Création symlinks compatibilité
   - Vérifications intégrité

3. **Fix symlinks 14B FP16** (lignes 297-298) :
   - Correction: pointaient vers fichiers FP8 au lieu de FP16
   - Symlinks corrigés vers `*_fp16.safetensors`

**C. Modifications docker-entrypoint.sh** (lignes 29-209) :
Logique complète upstream + fallback :
1. **ÉTAPE 1 - Healthcheck** (lignes 50-58) : `check_upstream_health.py` vérifie disponibilité
2. **ÉTAPE 2 - Download upstream** (lignes 60-95) : Si healthcheck OK → `setup_wan22_native.sh`
3. **ÉTAPE 3 - Fallback OwnCloud** (lignes 97-129) : Si healthcheck KO ou download échoue → OwnCloud
4. **ÉTAPE 4 - Vérification** (lignes 132-209) : Validation fichiers + reconstitution chunks si OwnCloud

**Workflow download** :
```bash
1. Healthcheck upstream (HEAD requests rapides)
2a. Si OK → Download upstream (HuggingFace + GitHub)
2b. Si échec → Cleanup + Fallback OwnCloud
3. Vérification intégrité
4. Reconstitution chunks (si OwnCloud)
```

**Fichiers créés** :
- `models_metadata.json` : Référence tailles fichiers
- `scripts/check_upstream_health.py` : Healthcheck + détection version
- `scripts/cleanup_partial_downloads.py` : Cleanup fichiers partiels

**Fichiers modifiés** :
- `scripts/setup_wan22_native.sh` : CLIP + upscalers + branch 5B + fix symlinks FP16
- `docker-entrypoint.sh` : Healthcheck + fallback OwnCloud + cleanup automatique

**Impact** :
- ✅ **Download complet** : Tous composants téléchargés localement (models + CLIP + upscalers)
- ✅ **Détection version** : Healthcheck détecte nouvelles versions upstream automatiquement
- ✅ **Fallback automatique** : Bascule sur OwnCloud si upstream KO
- ✅ **Cleanup intelligent** : Suppression fichiers partiels en cas d'échec
- ✅ **Makefile fonctionnel** : `full-workflow-5b/14b` fonctionnent avec download individuel
- ✅ **Logging professionnel** : Loguru pour tous les scripts (healthcheck, cleanup)

---


## 📝 Template pour nouvelle entrée

```markdown
### [YYYY-MM-DD HH:MM] - Titre court

**Problème** : Description du problème rencontré

**Cause** : Cause identifiée (si applicable)

**Solution** : Solution implémentée

**Fichiers modifiés** :
- `fichier.py` : Changement effectué

**Impact** :
- ✅ Impact principal sur le fonctionnement
```

---

## 🔄 WORKFLOW OBLIGATOIRE (Auto-enforcement)

**RÈGLES À SUIVRE SYSTÉMATIQUEMENT APRÈS CHAQUE CORRECTION** :

1. ✅ **Ajouter entrée** dans `CHANGES_TRACKER.md` (clair, court, concis)
2. ✅ **Mettre à jour `CLAUDE.md`** avec les informations essentielles
3. ✅ **Mettre à jour `ARCHITECTURE.md`** si changement architectural
4. ✅ **NETTOYER `CHANGES_TRACKER.md`** après mise à jour de CLAUDE.md (garder max 2-3 entrées, ~60 lignes max)
5. ✅ **NETTOYER `ARCHITECTURE.md`** (supprimer sections obsolètes)
6. ⏸️ **Attendre demande utilisateur** pour mise à jour README

**IMPORTANT** : Ces règles doivent être appliquées **automatiquement** sans que l'utilisateur ait besoin de le rappeler, et doivent être **mémorisées d'une session à l'autre**.

---

## 🧹 Rappel de nettoyage

Ce fichier doit rester **court et pertinent** (max 60 lignes pour les modifications récentes).
Après chaque mise à jour de `CLAUDE.md`, supprimer les anciennes entrées et ne garder que les 2-3 dernières.
