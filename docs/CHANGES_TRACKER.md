# CHANGES TRACKER - Journal de modifications

**Objectif** : Tracking temporaire des changements pour alimenter la mise à jour de `CLAUDE.md`.

**Usage** :
- ✅ Ajouter une entrée après chaque correction/modification
- ✅ Après mise à jour de `CLAUDE.md`, **NETTOYER** ce fichier (garder max 2-3 entrées récentes)

---

## 📅 Modifications récentes

### [2025-11-28 16:00] - Système universel images avec redimensionnement physique

**Problème** : Mismatch tensoriel persistant malgré ajustement paramètres
- L'ajustement des paramètres workflow ne suffit pas
- Le node `LoadImage` charge l'image avec ses dimensions originales
- Conflit dimensions image réelle vs dimensions workflow

**Solution complète** :
- **Redimensionnement physique** de l'image AVANT upload à ComfyUI
- Création copie temporaire redimensionnée (LANCZOS haute qualité)
- Upload de l'image redimensionnée au lieu de l'originale
- Nettoyage automatique (finally block)
- Correction `ZeroDivisionError` dans `/api/calculate-resolution`
- **Ajustement automatique multiples de 16** (VAE compression factor)
- **Workflow upscale** : Génération à résolution source, RealESRGAN upscale après

**Fichiers modifiés** :
- `web_interface/routes.py` : Pipeline complet traitement images

**Impact** :
- ✅ Système vraiment universel (accepte n'importe quelle image)
- ✅ Ajustement transparent et automatique
- ✅ Qualité préservée (algorithme LANCZOS)

---

### [2025-11-28 11:00] - Architecture workflows v4.0/v2.0 (WanVideoEncode + WanVideoEmptyEmbeds)

**Problème** : RuntimeError "expected input to have 48 channels, but got 96 channels instead"

**Cause** : Node `WanVideoImageToVideoEncode` incompatible avec wrapper récent (commit `44feb24`)

**Solution** : Remplacement architecture basée sur workflow officiel Kijai
```
Node 7: WanVideoEncode (encode image → latents)
Node 7b: WanVideoEmptyEmbeds (latents → embeds)
Node 8: WanVideoSampler (connexion [7b, 0])
```

**Fichiers modifiés** :
- `workflows/templates/wan22_i2v.json` : v3.0.0 → v4.0.0
- `workflows/templates/wan22_with_upscale.json` : v1.0.0 → v2.0.0
- `docker-entrypoint.sh` : VAE copie (`cp`) au lieu de symlink

**Impact** :
- ✅ Compatible avec wrapper récent
- ✅ Architecture alignée workflows officiels
- ⚠️ BREAKING CHANGE : anciens workflows incompatibles

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
