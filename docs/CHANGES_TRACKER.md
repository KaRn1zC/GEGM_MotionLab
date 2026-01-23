# CHANGES TRACKER - Journal de modifications

**Objectif** : Tracking temporaire des changements pour alimenter la mise à jour de `CLAUDE.md`.

**Usage** :
- Ajouter une entrée après chaque correction/modification
- Après mise à jour de `CLAUDE.md`, **NETTOYER** ce fichier (garder max 2-3 entrées récentes)

---

## Modifications récentes

### [2026-01-23] - Floor pour calcul multiples de 32 + Actualisation documentation

**Corrections apportées :**

1. **web_interface/routes.py** :
   - `adjust_dimension()` : round → floor (préfère crop à upscale)
   - `floor_to_multiple()` : round → floor
   - `adjust_to_32()` : défaut `prefer_lower=False` → `prefer_round=False` (floor par défaut)
   - Impact : image 1920x1080 → 1920x1056 (crop -24px) au lieu de 1920x1088 (upscale +8px)

2. **Documentation synchronisée** :
   - CLAUDE.md → v4.3.1 : correction loop_smooth=False, alignement multiples 32
   - docs/ARCHITECTURE.md → v4.3.1 : ajout points critiques alignement et pingpong

**Versions templates inchangées :**
- `wan22_5b_i2v.json` : v4.5.1
- `wan22_5b_with_upscale.json` : v3.5.1
- `wan22_14b_i2v.json` : v2.0.5
- `wan22_14b_with_upscale.json` : v2.0.5

---

### [2026-01-22] - Timeout unifié 90 minutes + Mise à jour documentation

**Corrections apportées :**

1. **web_interface/routes.py:490** :
   - Timeout unifié à 5400s (90min) pour tous les workflows (5B et 14B)
   - Permet générations haute résolution + upscale sans timeout

2. **Documentation synchronisée** :
   - CLAUDE.md → v4.3.0
   - README.md, README_DOCKER.md, README_RUNPOD.md → v4.3.0
   - docs/ARCHITECTURE.md → v4.3.0
   - Toutes les versions de templates mises à jour

**Versions actuelles templates :**
- `wan22_5b_i2v.json` : v4.5.1
- `wan22_5b_with_upscale.json` : v3.5.1
- `wan22_14b_i2v.json` : v2.0.5
- `wan22_14b_with_upscale.json` : v2.0.5

---

## WORKFLOW OBLIGATOIRE

**Après chaque correction** :
1. Ajouter entrée `CHANGES_TRACKER.md`
2. MàJ `CLAUDE.md` avec infos essentielles
3. **NETTOYER** fichiers documentation après MàJ
4. **JAMAIS git add/commit/push auto** (uniquement sur demande explicite)
