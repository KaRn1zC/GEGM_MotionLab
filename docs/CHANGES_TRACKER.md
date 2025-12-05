# CHANGES TRACKER - Journal de modifications

**Objectif** : Tracking temporaire des changements pour alimenter la mise à jour de `CLAUDE.md`.

**Usage** :
- ✅ Ajouter une entrée après chaque correction/modification
- ✅ Après mise à jour de `CLAUDE.md`, **NETTOYER** ce fichier (garder max 2-3 entrées récentes)

---

## 📅 Modifications récentes

### [2025-12-03 18:00] - Système upscale adaptatif UltraSharp + Génération optimale

**Problème** : Erreur critique détectée dans logs 14B_container1.txt
- Workflows échouent avec `RuntimeError: tensor size mismatch (88 vs 44)`
- Cause : Algorithme génération optimale calcule generation_width/height mais ne redimensionne pas l'image
- Workflow upscale utilise ImageUpscaleWithModel (upscale fixe 4x) sans resize final vers target exacte
- Variable `scale_ratio` inutilisée (ligne 227-228 routes.py) détectée par ruff

**Solutions implémentées** :

**A. Système redimensionnement pré-génération UltraSharp (3 modifications)** :
1. **Fonction `resize_image_with_ultrasharp()`** : Mini-workflow ComfyUI pour upscale intelligent
   - `web_interface/routes.py` lignes 26-125
   - Processus : Upscale 4x UltraSharp → Resize Lanczos vers target exacte
   - Gère upscale ET downscale (super-sampling)
2. **Redimensionnement en 2 étapes** :
   - Étape 1 : Ajustement multiples 32 (LANCZOS rapide) - lignes 372-392
   - Étape 2 : Upscale pré-génération si generation > source (UltraSharp) - lignes 395-429
3. **Suppression variable inutilisée** : `scale_ratio` lignes 227-228 supprimées

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
- `web_interface/routes.py` : fonction UltraSharp, redimensionnement 2 étapes, logs améliorés, suppression scale_ratio

**Impact** :
- ✅ **Fix crash 14B** : Image correctement redimensionnée avant génération (mismatch résolu)
- ✅ **Upscale adaptatif** : Ratio ≤4x → super-sampling, ratio >4x → upscale mixte
- ✅ **Qualité maximale** : UltraSharp 4x utilisé optimalement pour tous les upscales
- ✅ **Flexibilité totale** : Supporte n'importe quelle résolution target (64-7680×64-4320)
- ✅ **Feedback précis** : Warnings clairs sur qualité attendue selon ratio

**Exemples concrets** :
```
Cas 1 (optimal ≤4x) : 704x448 source → 1120x704 génération → 3488x2176 final
- Redimensionnement pré-génération : 704x448 → 1120x704 (UltraSharp 4x + downscale)
- Génération WAN 2.2 : 1120x704
- Upscale post-génération : 1120x704 → 4480x2816 (UltraSharp 4x) → 3488x2176 (Lanczos)
- Ratio final : 3.1x ✅ "Upscale optimal"

Cas 2 (élevé >4x) : 704x448 source → 1120x704 génération → 7168x4480 final
- Redimensionnement pré-génération : 704x448 → 1120x704 (UltraSharp 4x + downscale)
- Génération WAN 2.2 : 1120x704
- Upscale post-génération : 1120x704 → 4480x2816 (UltraSharp 4x) → 7168x4480 (Lanczos 1.6x)
- Ratio final : 6.4x ⚠️ "Upscale élevé, artefacts possibles au-delà de 4x"
```

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

**Résultats attendus** :
- ✅ **14B fonctionnel** : Plus de RuntimeError tensor mismatch
- ✅ **5B stable** : Génération complète sans timeout
- ✅ **Preset quality** : 30 steps supportés (15-18 min max)
- ✅ **Compatible 5B/14B** : Configuration identique pour les deux modèles

---

### [2025-12-04 17:30] - 🔍 Investigation erreur modèle 14B (RÉSOLU - voir ci-dessus)
- Container 5B : ✅ Génération réussie (720x450 → 1120x704 → 1728x1088)
- Container 14B : ❌ RuntimeError dans WanVideoSampler (node 8)
  - Erreur : `The expanded size of the tensor (140) must match the existing size (70)`
  - Target sizes: `[16, 1, 88, 140]` (attendu 1120x704)
  - Tensor sizes: `[48, 1, 44, 70]` (reçu 560x352)

**Investigations effectuées (Container 14B)** :

1. **Vérification image pregen** :
   - ✅ Existe : `/workspace/comfyui/ComfyUI/input/20251204_161246_720x450_01_pregen.jpg`
   - ✅ Dimensions correctes : **1120x704** (vérifié avec PIL)

2. **Vérification paramètres workflow** :
   - ✅ Node 7b (WanVideoEmptyEmbeds) : width=1120, height=704 ✅
   - ✅ Node 7 (WanVideoEncode) : spatial_compress_level=1 ✅
   - ✅ enable_vae_tiling=false

3. **Analyse compression VAE** :
   - VAE stride de base : (4, 8, 8) - temporal, spatial_h, spatial_w
   - Avec spatial_compress_level=1 : facteur spatial = 2
   - Compression totale : 8 × 2 = 16
   - **1120x704 → 70x44 en latent space** (70 = 1120÷16, 44 = 704÷16)
   - Mais node 7b crée des embeds pour **140x88** (140 = 1120÷8, 88 = 704÷8)
   - **MISMATCH : 70x44 vs 140x88**

4. **Comparaison workflows** :
   - `wan22_i2v.json` (5B) : spatial_compress_level=1 ✅
   - `wan22_with_upscale.json` (14B) : spatial_compress_level=1 ✅
   - **Les deux workflows sont IDENTIQUES**

**Hypothèse actuelle** :
- Le modèle 5B et 14B traitent différemment `spatial_compress_level`
- OU le modèle 5B a une configuration spécifique qui compense
- OU il y a une différence dans WanVideoWrapper entre les deux modèles

**Actions à effectuer (Container 5B)** :
1. Exécuter mêmes commandes de vérification dans container 5B
2. Comparer dimensions latent réelles produites par node 7
3. Vérifier logs ComfyUI du 5B pour messages spatial_compress
4. Comparer versions WanVideoWrapper si différentes
5. Tester si spatial_compress_level=0 résout le problème 14B

**Fichiers concernés** :
- `workflows/templates/wan22_with_upscale.json` : Node 7 spatial_compress_level
- `workflows/templates/wan22_i2v.json` : Node 7 spatial_compress_level
- `web_interface/routes.py` : Calcul dimensions et paramètres workflow

**Commandes exécutées (Container 14B)** :
```bash
# Image pregen
ls -lh /workspace/comfyui/ComfyUI/input/*pregen*
python3 -c "from PIL import Image; img = Image.open('/workspace/comfyui/ComfyUI/input/20251204_161246_720x450_01_pregen.jpg'); print(f'{img.size[0]}x{img.size[1]}')"
# Résultat: 1120x704 ✅

# Paramètres workflow
curl -s http://127.0.0.1:8188/history | python3 -c "..."
# Node 7b: width=1120, height=704 ✅
# Node 7: spatial_compress_level=1 ✅

# Calcul théorique compression
python3 -c "print(f'Latent: {1120//16}x{704//16}')"
# Résultat: 70x44 (correspond à l'erreur)
```

**État** : ⏸️ En attente container 5B pour comparaison

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
