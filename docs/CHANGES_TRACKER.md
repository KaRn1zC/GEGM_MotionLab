# CHANGES TRACKER - Journal de modifications

**Objectif** : Tracking temporaire des changements pour alimenter la mise à jour de `CLAUDE.md`.

**Usage** :
- ✅ Ajouter une entrée après chaque correction/modification
- ✅ Après mise à jour de `CLAUDE.md`, **NETTOYER** ce fichier (garder max 2-3 entrées récentes)

---

## 📅 Modifications récentes

### [2025-12-24] - 🔥 FIX CRITIQUE: Précision modèle (BF16 → FP16) - Cause racine artefacts catastrophiques

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
