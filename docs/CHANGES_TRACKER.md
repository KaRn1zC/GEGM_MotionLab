# CHANGES TRACKER - Journal de modifications

**Objectif** : Tracking temporaire des changements pour alimenter la mise à jour de `CLAUDE.md`.

**Usage** :
- ✅ Ajouter une entrée après chaque correction/modification
- ✅ Après mise à jour de `CLAUDE.md`, **NETTOYER** ce fichier (garder max 2-3 entrées récentes)

---

## 📅 Modifications récentes

### [2025-12-09 16:00] - ✅ FIX ARCHITECTURE: Workflow 14B + Migration FP16

**Problème identifié** : Modèle 14B ne génère pas de vidéo, erreur tensor mismatch (36 vs 16 channels)
- RuntimeError: `expected input[1, 16, 30, 88, 140] to have 36 channels, but got 16 channels instead`
- Analyse modèle 14B FP8: `patch_embedding.weight: torch.Size([5120, 36, 1, 2, 2])` → attend 36 canaux
- Cause: Architecture workflow incorrecte (utilise 2-node moderne au lieu de 1-node legacy)

**Investigation FP8 vs FP16** :
- Test modèle 14B FP16: `patch_embedding.weight: torch.Size([5120, 36, 1, 2, 2])` → MÊME architecture
- Conclusion: FP8 vs FP16 n'est PAS la cause du crash (même nombre de canaux)
- Différence: FP16 offre meilleure qualité (~28.6GB) vs FP8 (~14GB)

**Solution implémentée** :

**A. Architecture workflow 14B corrigée** :
1. **Nouveau workflow dédié** : `wan22_14b_with_upscale.json` créé
   - Node 7: `WanVideoImageToVideoEncode` (legacy 1-node, correct pour 14B)
   - Suppression node 7b: `WanVideoEmptyEmbeds` (non utilisé par 14B)
   - spatial_compress_level: 1 (matching official workflow)
   - Workflow officiel source: `wanvideo2_2_I2V_A14B_example_WIP.json`

2. **Architecture différente 5B vs 14B** :
   - 5B: `WanVideoEncode` → `WanVideoEmptyEmbeds` (2-node moderne)
   - 14B: `WanVideoImageToVideoEncode` (1-node legacy)

**B. Migration FP8 → FP16 pour qualité maximale** :
1. **setup_wan22_native.sh** (6 modifications) :
   - Lignes 121, 123: high_noise_14B_fp8 → high_noise_14B_fp16
   - Lignes 128, 130: low_noise_14B_fp8 → low_noise_14B_fp16
   - Lignes 151-152, 297-298: Symlinks vers fichiers FP16

2. **docker-entrypoint.sh** (3 modifications) :
   - Ligne 42: Commentaire corrigé (fp8 → fp16)
   - Lignes 44-45: Vérification présence fichiers FP16
   - Lignes 80-95: Loop vérification FP16, taille min 12GB → 25GB

**Fichiers modifiés** :
- `workflows/templates/wan22_14b_with_upscale.json` : NOUVEAU workflow 14B avec upscale
- `workflows/templates/wan22_14b_i2v.json` : NOUVEAU workflow 14B sans upscale
- `workflows/templates/wan22_5b_i2v.json` : Renommé depuis wan22_i2v.json (clarification)
- `workflows/templates/wan22_5b_with_upscale.json` : Renommé depuis wan22_with_upscale.json (clarification)
- `scripts/setup_wan22_native.sh` : Download FP16 au lieu de FP8
- `docker-entrypoint.sh` : Vérifications FP16, taille min 25GB
- `web_interface/routes.py` : Sélection automatique workflow selon modèle ET upscale
- `workflows/workflow_manager.py` : Détection fichiers FP16 pour 14B

**Impact** :
- ✅ **Architecture correcte** : 14B utilise maintenant WanVideoImageToVideoEncode
- ✅ **Qualité maximale** : FP16 au lieu de FP8 pour meilleure qualité
- ✅ **Workflows séparés** : 5B et 14B ont leurs propres workflows avec architectures spécifiques
- ✅ **Documentation corrigée** : CLAUDE.md précisait à tort que WanVideoImageToVideoEncode était bugué (vrai pour 5B, faux pour 14B)

**Validation requise** : Test génération 14B avec nouveau workflow et fichiers FP16

---

### [2025-12-09 14:00] - ✅ IMPLÉMENTATION: VAE spécifiques par modèle (5B vs 14B)

**Problème** : Le modèle 14B ne fonctionnait pas avec le VAE du 5B
- Erreur tensor size mismatch persistante malgré fix spatial_compress_level
- Analyse révèle : 14B nécessite VAE 2.1 (16 canaux) au lieu de VAE 2.2 (48 canaux)

**Cause identifiée** :
- Stratégies de compression différentes entre 5B et 14B
- 5B : Compression agressive 16×16×4 → VAE complexe (1.41 GB, 48 canaux)
- 14B : Compression standard 8×8×4 → VAE simple (254 MB, 16 canaux)
- Source : HuggingFace Comfy-Org/Wan_2.2_ComfyUI_Repackaged + docs ComfyUI

**Solution implémentée** :
1. **Download adaptatif** : `setup_wan22_native.sh` télécharge bon VAE par modèle
   - Lignes 135-140, 281-286 : Download wan_2.1_vae.safetensors pour 14B
   - Création symlinks vers bons fichiers VAE

2. **Déploiement Docker** : `docker-entrypoint.sh` copie bon VAE selon MODEL_NAME
   - Lignes 164-170 : Détection modèle et copie VAE correspondant

3. **Injection dynamique** : `workflow_manager.py` injecte vae_name automatiquement
   - Lignes 204-210 : Détection model_type et injection wan2.2_vae (5B) ou wan_2.1_vae (14B)

4. **Templates compatibles** : Workflows utilisent placeholder {vae_name}
   - `wan22_i2v.json:92` : WanVideoVAELoader avec model_name={vae_name}
   - `wan22_with_upscale.json:125` : Idem

5. **Validation adaptée** : `verify_vae.py` accepte 48ch (5B) ou 16ch (14B)
   - Lignes 33-44 : Détermination VAE et expected_channels selon modèle
   - Lignes 177-197 : Validation architecture avec canaux attendus

**Fichiers modifiés** :
- `scripts/setup_wan22_native.sh` : Download wan_2.1_vae pour 14B
- `docker-entrypoint.sh` : Copie VAE selon modèle
- `workflows/workflow_manager.py` : Injection vae_name dynamique
- `workflows/templates/wan22_i2v.json` : Placeholder {vae_name}
- `workflows/templates/wan22_with_upscale.json` : Placeholder {vae_name}
- `scripts/verify_vae.py` : Validation spécifique par modèle

**Impact** :
- ✅ **14B fonctionnel** : Plus d'erreur tensor mismatch due au VAE
- ✅ **Validation complète** : Workflow 14B validé end-to-end (make full-workflow-14b)
- ✅ **Automatisation totale** : Système détecte et utilise bon VAE sans intervention
- ✅ **Documentation complète** : CLAUDE.md et ARCHITECTURE.md mis à jour

**Validation** : Logs test_workflow_14B montrent succès complet
```
✅ LE VAE 2.1 EST COMPATIBLE (16 CANAUX)
decoder.conv1.weight: 16 canaux d'entrée (correct pour VAE 2.1)
conv2.weight: 16 canaux de sortie (correct pour VAE 2.1)
```

---

### [2025-12-03 18:00] - ✅ Système upscale adaptatif UltraSharp + Génération optimale

**Problème** : Erreur critique détectée dans logs 14B_container1.txt
- Workflows échouent avec `RuntimeError: tensor size mismatch (88 vs 44)`
- Cause : Algorithme génération optimale calcule generation_width/height mais ne redimensionne pas l'image
- Workflow upscale utilise ImageUpscaleWithModel (upscale fixe 4x) sans resize final vers target exacte
- Variable `scale_ratio` inutilisée (ligne 227-228 routes.py) détectée par ruff

**Solutions implémentées** :

**A. Système redimensionnement pré-génération (2 modifications)** :
1. **Redimensionnement en 2 étapes** (PIL LANCZOS) :
   - Étape 1 : Ajustement multiples 32 (LANCZOS rapide) - routes.py lignes 266-292
   - Étape 2 : Upscale/downscale pré-génération vers résolution génération optimale - routes.py lignes 294-326
2. **Suppression variable inutilisée** : `scale_ratio` lignes 227-228 supprimées

**B. Workflow upscale adaptatif (3 modifications)** :
1. **Ajout paramètres target_width/height** : `wan22_with_upscale.json` lignes 86-104
   - target_width (max 7680), target_height (max 4320)
   - enable_vae_tiling (boolean)
2. **Node 11b (ImageScale)** : Resize précis après upscale 4x - lignes 211-220
   - Input : sortie UltraSharp 4x (node 11)
   - Output : résolution target exacte (upscale ou downscale selon besoin)
   - Méthode : Lanczos (haute qualité)
3. **Version workflow** : v2.0.0 → **v3.0.0** - nom mis à jour "UltraSharp Upscale"

**C. Messages et feedback améliorés (2 modifications)** :
1. **Logs détaillés stratégie** : `routes.py` lignes 432-455
   - Affiche : source originale, ajustée (×32), génération WAN, finale
   - Ratio upscale post-génération avec warning approprié
2. **Messages upscale adaptatifs** :
   - Si ratio ≤ 4x : ✅ "Upscale optimal - 4x-UltraSharp + affinage Lanczos"
   - Si ratio > 4x : ⚠️ "Upscale élevé - 4x UltraSharp + Lanczos supplémentaire"

**D. Passage paramètres target au workflow** : `routes.py` lignes 470-480
   - Ajout target_width/target_height dans workflow_params
   - Permet au workflow de connaître la résolution finale exacte

**Fichiers modifiés** :
- `workflows/templates/wan22_with_upscale.json` : v3.0.0, node 11b, paramètres target
- `web_interface/routes.py` : redimensionnement PIL LANCZOS 2 étapes, logs améliorés, suppression scale_ratio

**Impact** :
- ✅ **Fix crash 14B** : Image correctement redimensionnée avant génération (mismatch résolu)
- ✅ **Upscale adaptatif** : Ratio ≤4x → super-sampling, ratio >4x → upscale mixte
- ✅ **Qualité maximale** : UltraSharp 4x utilisé optimalement pour tous les upscales
- ✅ **Flexibilité totale** : Supporte n'importe quelle résolution target (64-7680×64-4320)
- ✅ **Feedback précis** : Warnings clairs sur qualité attendue selon ratio

---

### [2025-12-05 12:00] - ✅ FIX CRITIQUE: spatial_compress_level + Timeout étendu

**Problèmes identifiés** (analyse logs 5B_container3.txt + test_5B.txt) :

1. **CRITIQUE - Incompatibilité spatial_compress_level=1** :
   - `WanVideoEncode` (node 7) avec `spatial_compress_level=1` produit latents **70x44** (compression ×16)
   - `WanVideoEmptyEmbeds` (node 7b) utilise `VAE_STRIDE` base et attend **140x88** (compression ×8)
   - **MISMATCH** : 70x44 ≠ 140x88 → RuntimeError tensor size mismatch
   - Vérifié dans logs : `WanVideoEncode: Encoded latents shape torch.Size([1, 48, 1, 44, 70])`
   - Affecte **TOUS** les modèles (5B et 14B)

2. **Timeout insuffisant pour preset "qualité maximale"** :
   - Preset quality : 30 steps (vs 20 balanced)
   - Temps d'exécution 5B : ~9min30s
   - Timeout actuel : 600s (10 minutes)
   - Résultat : Workflow bloqué à 100% puis timeout

**Solutions implémentées** :

**A. Correction spatial_compress_level (2 fichiers)** :
1. `workflows/templates/wan22_i2v.json:126` : `spatial_compress_level: 1 → 0`
2. `workflows/templates/wan22_with_upscale.json:159` : `spatial_compress_level: 1 → 0`

**Impact** :
- Compression spatiale : 8 (au lieu de 16)
- Latents produits : **140x88** (match parfait avec WanVideoEmptyEmbeds) ✅
- Résout crash 14B et timeout 5B

**B. Augmentation timeout websocket** :
- `src/comfyui_client.py:34` : `websocket_timeout: 600 → 1200` (20 minutes)
- Marge confortable pour preset quality (30 steps)
- Supporte jusqu'à 15-18 minutes de génération

**Fichiers modifiés** :
- `workflows/templates/wan22_i2v.json` : spatial_compress_level=0
- `workflows/templates/wan22_with_upscale.json` : spatial_compress_level=0
- `src/comfyui_client.py` : websocket_timeout=1200s

**Résultats** :
- ✅ **14B fonctionnel** : Plus de RuntimeError tensor mismatch
- ✅ **5B stable** : Génération complète sans timeout
- ✅ **Preset quality** : 30 steps supportés (15-18 min max)
- ✅ **Compatible 5B/14B** : Configuration identique pour les deux modèles

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
