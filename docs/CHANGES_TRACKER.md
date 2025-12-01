# CHANGES TRACKER - Journal de modifications

**Objectif** : Tracking temporaire des changements pour alimenter la mise à jour de `CLAUDE.md`.

**Usage** :
- ✅ Ajouter une entrée après chaque correction/modification
- ✅ Après mise à jour de `CLAUDE.md`, **NETTOYER** ce fichier (garder max 2-3 entrées récentes)

---

## 📅 Modifications récentes

### [2025-12-01 16:30] - Correction durée vidéo (limites frames/fps workflows)

**Problème** : Vidéos générées trop courtes malgré paramètres corrects
- Demande utilisateur : 5 secondes @ 24fps (120 frames)
- Résultat obtenu : ~1 seconde seulement
- Artéfacts visuels présents avec upscale 4K

**Cause identifiée** :
- **Workflow manager** : Clamp automatique des valeurs entières au `max` du template (lignes 284-291)
- **wan22_with_upscale.json** : `max: 32` frames (insuffisant pour 5s)
- **wan22_i2v.json** : `max: 48` frames (insuffisant pour 5s)
- Calcul : 120 frames demandés → clampés à 32 → 32/24fps = 1.33 secondes

**Solution implémentée** :
- Augmentation limites `frames` : 32/48 → **240** (permet 10s @ 24fps)
- Augmentation limites `fps` : 24/30 → **60** (permet slow-motion fluide)

**Fichiers modifiés** :
- `workflows/templates/wan22_with_upscale.json` lignes 52-65 : max frames 32→240, max fps 24→60
- `workflows/templates/wan22_i2v.json` lignes 44-57 : max frames 48→240, max fps 30→60

**Impact** :
- ✅ Vidéos générées respectent la durée demandée (5s = 120 frames @ 24fps)
- ✅ Support vidéos longues jusqu'à 10 secondes @ 24fps (240 frames)
- ✅ Support slow-motion/high framerate jusqu'à 60fps
- ⚠️ Artefacts visuels nécessitent investigation séparée (compression H264, qualité upscale)

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
