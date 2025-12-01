# CHANGES TRACKER - Journal de modifications

**Objectif** : Tracking temporaire des changements pour alimenter la mise à jour de `CLAUDE.md`.

**Usage** :
- ✅ Ajouter une entrée après chaque correction/modification
- ✅ Après mise à jour de `CLAUDE.md`, **NETTOYER** ce fichier (garder max 2-3 entrées récentes)

---

## 📅 Modifications récentes

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

### [2025-12-01 11:30] - Correction alignement dimensions: 16 → 32

**Problème** : RuntimeError "The size of tensor a (2464) must match the size of tensor b (2520)"
- Image redimensionnée à 720x448 (multiple de 16)
- VAE avec `spatial_compress_level: 1` convertissait automatiquement 720 → 704 (multiple de 32)
- Node `WanVideoEmptyEmbeds` recevait width=720 mais VAE attendait width=704
- Mismatch: 44 latents (704/16) vs 45 latents (720/16)

**Cause identifiée** :
- Avec `spatial_compress_level: 1`, le VAE nécessite des dimensions **multiples de 32**, pas 16
- VAE_STRIDE = (4, 8, 8), mais compression spatiale level 1 double le facteur → (4, 16, 16)
- Workflow officiel 5B utilise 832x480 (tous deux multiples de 32!)

**Solution implémentée** :
- Modifié `web_interface/routes.py` lignes 40-42, 126-128
- Changé facteur d'alignement de 16 → **32** dans `round_to_multiple()` et `adjust_dimension()`
- Ajouté commentaires explicatifs sur `spatial_compress_level=1`
- Mis à jour docstrings

**Fichiers modifiés** :
- `web_interface/routes.py` : Alignement 16 → 32

**Impact** :
- ✅ Résout définitivement le mismatch tensoriel avec spatial_compress_level=1
- ✅ Dimensions automatiquement ajustées aux multiples de 32
- ✅ Compatible avec workflow officiel 5B (832x480)
- 📐 Exemple: 720x450 → **704x448** (au lieu de 720x448)

---

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
