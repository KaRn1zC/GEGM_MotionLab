# CHANGES TRACKER - Journal de modifications

**Objectif** : Tracking temporaire des changements pour alimenter la mise à jour de `CLAUDE.md`.

**Usage** :
- ✅ Ajouter une entrée après chaque correction/modification
- ✅ Après mise à jour de `CLAUDE.md`, **NETTOYER** ce fichier (garder max 2-3 entrées récentes)

---

## 📅 Modifications récentes

### [2025-12-01 14:00] - Support récupération vidéos (clé "gifs")

**Problème** : Workflow terminé avec succès mais "Aucune vidéo générée"
- Workflow ComfyUI se termine correctement
- Fonction `get_output_images()` retourne 0 fichiers
- Erreur : "Récupéré 0 images pour workflow"

**Cause identifiée** :
- Node `VHS_VideoCombine` génère des vidéos avec la clé **"gifs"** (standard VideoHelperSuite)
- La fonction `get_output_images()` cherchait uniquement la clé **"images"** (SaveImage nodes)
- Les vidéos MP4 générées n'étaient pas détectées

**Solution implémentée** :
- Ajout support clé "gifs" dans `get_output_images()`
- Fonction renommée conceptuellement pour gérer images ET vidéos
- Détection automatique du format (images ou vidéos)

**Fichiers modifiés** :
- `src/comfyui_client.py` lignes 487-546 : Support "gifs" + "images"

**Impact** :
- ✅ Vidéos MP4 correctement récupérées depuis VHS_VideoCombine
- ✅ Compatible images (SaveImage) et vidéos (VHS_VideoCombine)
- ✅ Génération cinemagraph fonctionnelle de bout en bout

---

### [2025-12-01 13:00] - Correction détection fin workflow et gestion WebSocket

**Problème CRITIQUE** : Workflow bloqué indéfiniment sans jamais se terminer
- Workflow reste en état "processing" jusqu'au timeout (600s)
- Erreurs UTF-32 répétées: `'utf-32-be' codec can't decode bytes...`
- Progressions aberrantes affichées (10000%, 80000%, etc.)
- Log "Exécution nœud None" sans action

**Cause identifiée** :
1. **Détection de fin manquante** : ComfyUI envoie `executing` avec `node = null` pour signaler la fin, mais le code ne détectait pas ce signal
2. **Messages binaires** : Tentative de décoder tous les messages WebSocket comme JSON texte (ComfyUI envoie aussi des images preview)
3. **Normalisation progression** : ComfyUI envoie parfois des valeurs 0-100 (déjà en %), affichées avec `.1%` qui multiplie par 100

**Solution implémentée** :
- **Détection fin workflow** : Check `node_id is None` → marquer workflow "completed"
- **Skip messages binaires** : Vérifier `isinstance(message, bytes)` et ignorer proprement
- **Normalisation progression** : Diviser par 100 si valeur > 1.0

**Fichiers modifiés** :
- `src/comfyui_client.py` lignes 236-257 : Gestion messages binaires
- `src/comfyui_client.py` lignes 271-290 : Normalisation progression
- `src/comfyui_client.py` lignes 292-314 : Détection fin workflow (CRITIQUE)

**Impact** :
- ✅ Workflow se termine immédiatement après génération (au lieu de timeout 10min)
- ✅ Plus d'erreurs UTF-32 dans les logs
- ✅ Progressions normalisées (0-100%)
- ✅ Log clair "✅ Workflow terminé avec succès"
- 🚀 Génération de cinemagraph fonctionnelle de bout en bout

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
