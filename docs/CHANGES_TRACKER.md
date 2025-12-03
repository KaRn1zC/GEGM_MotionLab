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
