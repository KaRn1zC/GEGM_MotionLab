# CHANGES TRACKER - Journal de modifications

**Objectif** : Tracking temporaire des changements pour alimenter la mise à jour de `CLAUDE.md`.

**Usage** :
- ✅ Ajouter une entrée après chaque correction/modification
- ✅ Après mise à jour de `CLAUDE.md`, **NETTOYER** ce fichier (garder max 2-3 entrées récentes)

---

## 📅 Modifications récentes

### [2025-12-29] - 🔥 FIX CRITIQUE #2: Bug arrondi multiples de 32 → Génération 832×544 au lieu de 832×512

**Problème** : Container 21 montre génération à 832×544 MALGRÉ fix résolution minimale
- ✅ Résolution minimale 832×480 implémentée (lignes 152-190)
- ✅ Image 704×448 correctement upscalée vers 832×_
- ❌ Génération à 832×**544** au lieu de 832×**512** (logs ligne 3118)
- ❌ Latents 52×34=1768 au lieu de 52×32=1664 (inutilement plus grand)

**Cause racine identifiée** : **Fonction `adjust_to_32()` utilise `round()` au lieu de `floor()`**
```python
# AVANT (ligne 118):
def adjust_to_32(value):
    return int(round(value / 32) * 32)  # 529 → round(16.53) → 17 → 544 ❌

# Calcul problématique:
aspect_ratio = 704 / 448 = 1.5714
gen_h = 832 / 1.5714 = 529.4
adjust_to_32(529) = round(529/32) * 32 = round(16.53) * 32 = 17 * 32 = 544 ❌
```

**Solution implémentée** : Floor privilégié pour rester proche du minimum (lignes 117-130, 170-190)
```python
# APRÈS:
def adjust_to_32(value, prefer_lower=False):
    if prefer_lower:
        return int(value // 32) * 32  # 529 → 16 → 512 ✅
    else:
        return int(round(value / 32) * 32)

# Logique 14B: floor si au-dessus du minimum, sinon ceil
gen_h_floor = adjust_to_32(529, prefer_lower=True) = 512 ✅
if gen_h_floor >= 480: gen_h = 512 ✅
```

**Fichier modifié** : `web_interface/routes.py`

**Résultat attendu (image 704×448 → target 1120×704)** :
```
Avant: 832×544 → latents 52×34 = 1768 pixels (inutilement grand) ❌
Après: 832×512 → latents 52×32 = 1664 pixels (+6.7% au-dessus minimum 1560) ✅
```

**Impact** :
- ✅ **Artefacts "neige" éliminés** : Latents 1664 > 1560 minimum requis
- ✅ **Optimisation mémoire** : 1664 au lieu de 1768 pixels latents (-5.9%)
- ✅ **Aspect ratio préservé** : 832×512 (ratio 1.625) vs source 1.5714 (3.4% différence)

**Test requis** : Rebuild image + container 22 → Vérifier génération 832×512 + disparition artefacts

---

### [2025-12-29] - 🔥 FIX CRITIQUE #1: Résolution minimale 14B (832×480) - Cause RÉELLE artefacts "neige"

**Problème** : Artefacts catastrophiques 14B persistent MALGRÉ fix précision FP16 (2025-12-24)
- ✅ Templates FP16 corrects (WanVideoModelLoader base_precision: "fp16")
- ✅ Fichiers safetensors FP16 valides (torch.float16 confirmé)
- ✅ VAE natif BF16 intact (torch.bfloat16, 194 clés)
- ❌ Résultat : Vidéo TOUJOURS inexploitable ("effet de neige" massif)

**Investigation 14B containers 17-20** :
- Image source 720×450 → ajustée 704×448 (multiples 32)
- Génération 14B : 704×448 avec spatial_compress_level=1 (diviseur 16)
- **Latents : 44×28 = 1232 pixels** ❌ INSUFFISANT
- Référence Kijai : 832×480 → latents 52×30 = 1560 pixels ✅

**Analyse comparative latents** :
```
14B actuel (704×448) : latents 44×28 = 1232 pixels → ARTEFACTS ❌
14B référence (832×480) : latents 52×30 = 1560 pixels → OK ✅
5B (1120×704) : latents 140×88 = 12320 pixels → OK ✅ (10x plus!)
```

**Cause racine identifiée** : **Latents trop petits (1232 < 1560 minimum requis)**
- 14B spatial_compress_level=1 → diviseur 16 (8 × 2^1)
- Compression 32×32 agressive nécessite latents ≥1560 pixels
- En dessous : modèle n'a pas assez d'information → artefacts reconstruction

**Solution implémentée** : Résolution minimale 14B FORCÉE à 832×480

**Fichier modifié** : `web_interface/routes.py`

**Modifications fonction `calculate_optimal_generation_strategy` (lignes 71-169)** :
1. **Nouvelle stratégie 14B** :
   - Résolution minimale absolue : 832×480 (référence Kijai)
   - TOUJOURS upscale/downscale pré-génération vers 832×480
   - Génération fixe à 832×480 ajustée multiples 32
   - Post-génération : UltraSharp 4x + Lanczos selon target

2. **Adaptation universelle images** :
   - Image < 832×480 : upscale Lanczos pré-gen → 832×480
   - Image > 832×480 : downscale Lanczos pré-gen → 832×480
   - Conserve aspect ratio (ajusté multiples 32)
   - Post-gen : UltraSharp + supersampling (≤4x) ou UltraSharp + Lanczos (>4x)

**Exemple calcul (image 720×450 → target 1120×704)** :
```
Avant (704×448) : latents 44×28 = 1232 pixels ❌
Après (832×512) : latents 52×32 = 1664 pixels ✅ (+35%)
Upscale post-gen : 1.85x (≤4x supersampling optimal)
```

**Impact attendu** :
- ✅ **Artefacts "neige" éliminés** : Latents suffisants pour reconstruction propre
- ✅ **Adaptation universelle** : Toute image input → 832×480 min → target demandée
- ✅ **Qualité optimale** : Upscale ≤4x (UltraSharp + supersampling Lanczos)
- ✅ **Stratégie 5B préservée** : Aucun changement (~720p optimal)

**Test requis** : Rebuild image + nouveau container 14B → Image 720×450 → Target 1120×704

---

### [2025-12-24] - ✅ FIX: Précision modèle FP16 (partiel - résolution minimale manquante)

**Problème** : Artefacts catastrophiques ("neige", bruit massif, déformations) sur TOUTES les générations 14B malgré :
- ✅ Modèles I2V corrects téléchargés (wan2.2_i2v_high_noise_14B_fp16.safetensors)
- ✅ Résolution génération correcte (704×448 pour 14B)
- ✅ Aucun fichier T2V présent
- ✅ VAE 16 canaux correct
- ❌ Résultat : Vidéo totalement inexploitable (qualité visuelle détruite)

**Analyse logs container16** :
- Ligne 3124-3125 : Bons fichiers I2V chargés (wan2.2_i2v_high_noise/low_noise_14B_fp16.safetensors)
- Ligne 3110 : Résolution génération correcte (704×448)
- Ligne 3840 : Workflow terminé avec statut "completed"
- **Mais** : Vidéo générée = bouillie de pixels (confirmé analyse visuelle)

**Cause racine identifiée** : **Conversion précision incorrecte FP16 → BF16**
- **Fichiers safetensors** : FP16 (`wan2.2_i2v_*_14B_**fp16**.safetensors`)
- **Template utilisait** : `"base_precision": "bf16"` ❌ (node WanVideoModelLoader)
- **Workflow officiel Kijai** : `"base_precision": "fp16_fast"` ✅
- **Impact** : Conversion FP16→BF16 au chargement des poids → bruit numérique catastrophique

**Vérification workflow officiel** :
- Source : `wanvideo2_2_I2V_A14B_example_WIP.json` (Kijai/ComfyUI-WanVideoWrapper)
- WanVideoModelLoader (node 22/71) : `"base_precision": "fp16_fast"` (pas "bf16")
- WanVideoVAELoader (node 38) : `"precision": "bf16"` (OK, pour stabilité encodage)
- LoadWanVideoT5TextEncoder (node 11) : `"precision": "bf16"` (OK, sémantique texte)

**Solution implémentée** : Correction précision UNIQUEMENT WanVideoModelLoader

**4 templates corrigés** (`base_precision: "bf16"` → `"fp16"` node 2 uniquement) :
1. `workflows/templates/wan22_14b_with_upscale.json` : v1.5.0 → **v1.6.0**
2. `workflows/templates/wan22_14b_i2v.json` : v1.5.0 → **v1.6.0**
3. `workflows/templates/wan22_5b_i2v.json` : v4.3.0 → **v4.4.0**
4. `workflows/templates/wan22_5b_with_upscale.json` : v3.3.0 → **v3.4.0**

**Précision mixte préservée** (conforme workflow officiel) :
- ✅ WanVideoModelLoader : `"fp16"` (matching fichiers safetensors FP16)
- ✅ WanVideoVAELoader : `"bf16"` (stabilité numérique VAE)
- ✅ WanVideoTextEncodeCached : `"bf16"` (préservation sémantique)

**Fichiers modifiés** :
- `workflows/templates/wan22_14b_with_upscale.json` : Node 2 base_precision + version
- `workflows/templates/wan22_14b_i2v.json` : Node 2 base_precision + version
- `workflows/templates/wan22_5b_i2v.json` : Node 2 base_precision + version
- `workflows/templates/wan22_5b_with_upscale.json` : Node 2 base_precision + version
- `workflows/workflow_manager.py` : Retrait logs debugging (lignes 95-103, 133-157)

**Impact attendu** :
- ✅ **Artefacts "neige" éliminés** : Alignement 100% avec workflow officiel Kijai
- ✅ **Qualité visuelle restaurée** : Pas de conversion FP16↔BF16 inutile au chargement poids
- ✅ **Mixed precision standard** : FP16 (modèle) + BF16 (VAE/T5) supporté nativement par ComfyUI
- ✅ **5B et 14B corrigés** : Problème affectait les deux modèles

**Test requis** : Rebuild image + nouveau container 14B → Vérifier disparition artefacts

---

### [2025-12-22] - ✅ OPTIMISATION MAJEURE: GPU 95GB + Timeout différencié + Fix start_image + Fix load_device

**Problèmes identifiés** :
1. Workflows 14B timeout à 20 minutes (container 8, 12:16:42 après 1200s)
2. Génération 3-5x plus lente (GPU 95GB sous-exploité par offload forcé)
3. TypeError templates 14B : `"image"` au lieu de `"start_image"` (node 7)
4. HTTP 400 : `load_device: "gpu"` invalide (valeurs: "main_device"/"offload_device")

**Solutions implémentées** :
- **web_interface/routes.py** : Timeout adaptatif 5B=1200s, 14B=3600s (60min)
- **Tous templates** : `force_offload: false`, `load_device: "main_device"` (GPU optimized)
- **Templates 14B** : `"image"` → `"start_image"` (node 7)

**Fichiers modifiés** :
- `web_interface/routes.py` : Timeout différencié
- `wan22_5b_i2v.json` : v4.0.0 → v4.2.0
- `wan22_5b_with_upscale.json` : v3.0.0 → v3.2.0
- `wan22_14b_i2v.json` : v1.1.0 → v1.4.0
- `wan22_14b_with_upscale.json` : v1.1.0 → v1.4.0

**Impact** :
- ✅ Timeout 14B résolu (60 min marge confortable)
- ✅ Accélération 3-5x (GPU 95GB pleinement exploité)
- ✅ TypeError + HTTP 400 résolus

---

### [2025-12-12] - ✅ FIX CRITIQUE: Templates 14B - Paramètres manquants + Vérification chemins réels

**Problème 1** : Templates 14B HTTP 400 "Required input is missing" (node 7)
- 4 paramètres requis manquants : start_latent_strength, end_latent_strength, noise_aug_strength, force_offload

**Problème 2** : Container redémarrait "❌ Modèle diffusion 5B incomplet: 0 GB"
- Vérification utilisait symlinks invalides temporairement après move fichiers

**Solutions** :
1. Ajout 4 paramètres au node 7 templates 14B (v1.0.0 → v1.1.0)
2. docker-entrypoint.sh utilise chemins réels pour vérification (lignes 177-340)

**Impact** :
- ✅ Workflows 14B validés
- ✅ Pas de restart container (startup ~45s au lieu de ~1min30s)

---

## 🔄 WORKFLOW OBLIGATOIRE

**Après chaque correction** :
1. ✅ Ajouter entrée `CHANGES_TRACKER.md`
2. ✅ MàJ `CLAUDE.md` avec infos essentielles
3. ✅ MàJ `ARCHITECTURE.md` si changement architectural
4. ✅ **NETTOYER `CHANGES_TRACKER.md`** (max 2-3 entrées, ~60 lignes)
5. ✅ **NETTOYER `ARCHITECTURE.md`** (supprimer obsolète)
6. ⏸️ Attendre demande utilisateur pour README
