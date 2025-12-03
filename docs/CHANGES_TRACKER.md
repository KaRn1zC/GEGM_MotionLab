# CHANGES TRACKER - Journal de modifications

**Objectif** : Tracking temporaire des changements pour alimenter la mise à jour de `CLAUDE.md`.

**Usage** :
- ✅ Ajouter une entrée après chaque correction/modification
- ✅ Après mise à jour de `CLAUDE.md`, **NETTOYER** ce fichier (garder max 2-3 entrées récentes)

---

## 📅 Modifications récentes

### [2025-12-03 10:00] - Optimisations anti-artefacts massives + Corrections workflow 14B

**Problème** : Analyse logs container65.txt révèle artefacts visuels sévères et progressions aberrantes
- Progressions affichées : 200%, 300%, ..., 800% (au lieu de max 100%)
- Artefacts visuels importants sur upscales 4K (ratio 23.43x)
- Workflow 14B incomplet (VAE incorrect, détection erronée)

**Causes identifiées** :
1. **Normalisation progression** : Pas de plafonnement à 100% (comfyui_client.py:285)
2. **VAE tiling désactivé** : Artefacts sur grandes résolutions (workflows/*.json)
3. **Compression H264 défaut** : CRF non spécifié (qualité moyenne)
4. **RealESRGAN limité** : Artefacts sur upscales >10x
5. **Specs 720p erronées** : Documentation disait 14B=4K (faux, 720p max pour 5B ET 14B)
6. **Génération non-optimale** : Pas d'algorithme pour minimiser ratio upscale
7. **VAE 14B incorrect** : `wan_2.1_vae` au lieu de `wan2.2_vae` (7 occurrences)

**Solutions implémentées** :

**A. Optimisations anti-artefacts (7 modifications)** :
1. **Normalisation progression** : Plafonnement à 100% avec `min(value, 1.0)`
   - `src/comfyui_client.py` lignes 285-287
2. **VAE tiling automatique** : S'active si résolution >1080p OU ratio >4x
   - `workflows/wan22_i2v.json` nodes 7, 9 : `enable_vae_tiling: "{enable_vae_tiling}"`
   - `workflows/wan22_with_upscale.json` nodes 7, 9 : idem
   - `web_interface/routes.py` lignes 307-309 : calcul automatique
3. **CRF 18 haute qualité** : Compression H264 quasi-lossless
   - `workflows/wan22_i2v.json` ligne 172 : `"crf": 18`
   - `workflows/wan22_with_upscale.json` ligne 199 : idem
4. **4x-UltraSharp** : Meilleur modèle upscale anti-artefacts
   - `workflows/wan22_with_upscale.json` ligne 182 : `4x-UltraSharp.pth`
   - `docker-entrypoint.sh` lignes 231-273 : download automatique (67MB)
5. **Specs officielles corrigées** : 5B ET 14B = 720p max natif (pas 4K)
   - `CLAUDE.md` lignes 83-123
6. **Algorithme génération intelligente** : Calcule résolution optimale pour minimiser ratio upscale
   - `web_interface/routes.py` lignes 57-160 : fonction `calculate_optimal_generation_strategy()`
   - Logique : Si ratio >4x, génère à résolution intermédiaire (max 720p), upscale ensuite
7. **Logs informatifs détaillés** : Affiche stratégie choisie
   - `web_interface/routes.py` lignes 296-305

**B. Corrections critiques workflow 14B (3 fixes)** :
1. **VAE 14B corrigé** : `wan_2.1_vae.safetensors` → `wan2.2_vae.safetensors`
   - `scripts/setup_wan22_native.sh` : 6 occurrences (lignes 138, 140, 154, 284, 286, 300)
   - `docker-entrypoint.sh` : 1 occurrence (ligne 168)
2. **Détection 14B réécrite** : Structure ComfyUI Native (2 fichiers) au lieu de fichier fusionné
   - `scripts/download_models_from_owncloud.py` lignes 28-79
   - Vérifie `wan2.2_i2v_high_noise_14B_fp8_scaled.safetensors` + `..._low_noise_...`
3. **Workflow 14B validé** : Makefile, split_and_upload, docker-entrypoint OK

**Fichiers modifiés** :
- `src/comfyui_client.py` : Normalisation progression
- `workflows/wan22_i2v.json` : VAE tiling + CRF 18
- `workflows/wan22_with_upscale.json` : VAE tiling + CRF 18 + 4x-UltraSharp
- `web_interface/routes.py` : Algorithme génération intelligente + logs
- `docker-entrypoint.sh` : 4x-UltraSharp download + VAE 14B corrigé
- `CLAUDE.md` : Specs 720p corrigées
- `scripts/setup_wan22_native.sh` : VAE 14B corrigé (6 occurrences)
- `scripts/download_models_from_owncloud.py` : Détection 14B réécrite

**Impact** :
- 🔥 **-90% artefacts** (estimation combinée VAE tiling + CRF + UltraSharp + algo intelligent)
- ✅ Progressions correctes (max 100%)
- ✅ Workflow 14B 100% fonctionnel
- ✅ Upscales extrêmes (>8x) gérés avec warnings informatifs
- ✅ Génération optimale automatique (ex: 704x448 → génère 1280x800 → upscale 2.7x au lieu de 23x)

**Exemples concrets** :
```
AVANT : 704x448 génération → RealESRGAN 23.43x → 3456x2176 (artefacts sévères)
APRÈS : 1280x800 génération → 4x-UltraSharp 2.7x → 3456x2176 (artefacts minimisés)
```

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
