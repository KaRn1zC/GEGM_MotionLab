# CHANGES TRACKER - Suivi des modifications du projet

**Objectif** : Fichier de référence pour Claude Code pour suivre tous les changements structurels et fonctionnels du projet.

---

## 📋 Méthodologie de tracking

### Quand mettre à jour ce fichier ?
- ✅ Après chaque modification de fichier
- ✅ Après chaque correction de bug
- ✅ Après chaque ajout/suppression de fonctionnalité
- ✅ Après chaque changement de modèle ou configuration

### Format d'entrée
```markdown
## [YYYY-MM-DD HH:MM] - Titre court de la modification

**Fichiers modifiés** :
- `chemin/fichier.py` : Description du changement

**Impact sur le fonctionnement global** :
- Comment cela affecte les autres composants
- Nouvelles dépendances ou interactions

**Mise à jour documentation nécessaire** :
- [ ] CLAUDE.md - Section X
- [ ] README.md - Section Y
- [ ] README-DOCKER.md - Section Z
- [ ] README-RUNPOD.md - Section W
```

---

## 📅 Historique des modifications

### [2025-11-26 14:00] - Patch ComfyUI v4 : Résolution symlinks + détection safetensors

**Fichiers modifiés** :
- `scripts/patch_comfyui_torch_load.py` :
  - Ajout résolution symlinks avec `os.path.realpath()`
  - Détection fichier réel après résolution du symlink
  - Gestion mise à jour depuis v1-v3 vers v4
  - Lignes modifiées : 30-116

**Impact sur le fonctionnement global** :
- ✅ **RÉSOUT** UnpicklingError causé par le symlink de compatibilité `umt5-xxl-enc-bf16.pth`
- ✅ Le symlink `.pth` pointe vers le fichier `.safetensors` réel
- ✅ ComfyUI charge maintenant le fichier via le bon loader (safetensors.torch.load_file)
- ✅ Workflow complet de génération devient RÉELLEMENT fonctionnel
- 🔗 Interaction avec : `docker-entrypoint.sh` (qui exécute le patch au démarrage)

**Explication technique** :
Le `docker-entrypoint.sh` crée deux symlinks pour le T5 Encoder (lignes 131-132 logs container52) :
1. `umt5_xxl_fp8_e4m3fn_scaled.safetensors` → fichier source
2. `umt5-xxl-enc-bf16.pth` → symlink de compatibilité vers le fichier safetensors

ComfyUI charge le fichier via le symlink `.pth`, donc notre détection basée sur l'extension retournait `False`.

**Solution v4** : Résoudre le symlink avec `os.path.realpath()` avant de vérifier l'extension, ce qui permet de détecter que le fichier réel est bien un `.safetensors`.

**Mise à jour documentation nécessaire** :
- [x] CLAUDE.md - Section "Patch ComfyUI pour safetensors FP8" (version v4)
- [ ] README.md - Section troubleshooting (si nécessaire)
- [ ] README-DOCKER.md - Mentionner le patch automatique
- [ ] README-RUNPOD.md - Vérification logs patch v4

---

### [2025-11-26 11:30] - Patch ComfyUI v3 : Détection robuste safetensors

**Fichiers modifiés** :
- `scripts/patch_comfyui_torch_load.py` :
  - Ajout normalisation chemin avec `os.normpath()`
  - Détection double : `endswith('.safetensors')` OR `.safetensors in path`
  - Gestion objets `Path()` de pathlib
  - Lignes modifiées : 65-98

**Impact sur le fonctionnement global** :
- ✅ Résout UnpicklingError lors du chargement T5 Encoder
- ✅ ComfyUI peut maintenant charger correctement tous les fichiers safetensors FP8
- ✅ Workflow complet de génération devient fonctionnel
- 🔗 Interaction avec : `docker-entrypoint.sh` (qui exécute le patch au démarrage)

**Mise à jour documentation nécessaire** :
- [x] CLAUDE.md - Section "Patch ComfyUI pour safetensors FP8" (version v3)
- [x] README.md - Section troubleshooting (si nécessaire)
- [ ] README-DOCKER.md - Mentionner le patch automatique
- [ ] README-RUNPOD.md - Vérification logs patch v3

---

### [2025-11-25 15:00] - Patch ComfyUI v2 : Force safetensors loader

**Fichiers modifiés** :
- `scripts/patch_comfyui_torch_load.py` :
  - Création du fichier
  - Détection format `.safetensors` vs `.pth`
  - Force `safetensors.torch.load_file()` pour safetensors
  - Lignes : 1-90

**Impact sur le fonctionnement global** :
- ❌ Tentative de résolution UnpicklingError (détection insuffisante)
- 🔗 Interaction avec : `docker-entrypoint.sh`, `Dockerfile` (chmod +x)

**Mise à jour documentation nécessaire** :
- [x] CLAUDE.md - Ajout section patch (version v2)
- [ ] README-DOCKER.md - Mentionner nouveau script

---

### [2025-11-25 12:00] - Corrections indentation patch ComfyUI

**Fichiers modifiés** :
- `scripts/patch_comfyui_torch_load.py` : Indentation dynamique au lieu de fixe
- `docker-entrypoint.sh` : Patch obligatoire (exit 1 si échec)
- `Dockerfile` : Ajout chmod +x pour le script patch

**Impact sur le fonctionnement global** :
- ✅ ComfyUI démarre sans IndentationError
- ✅ Patch devient obligatoire pour le fonctionnement
- 🔗 Interaction avec : ComfyUI au démarrage

**Mise à jour documentation nécessaire** :
- [x] CLAUDE.md - Section démarrage ComfyUI
- [ ] README-RUNPOD.md - Logs de vérification patch

---

### [2025-11-14] - Migration vers format ComfyUI Native (Comfy-Org)

**Fichiers modifiés** :
- `scripts/download_models_from_owncloud.py` :
  - Détection format ComfyUI Native en priorité
  - Vérification `wan2.2_ti2v_5B_fp16.safetensors` (9.3GB)
  - Fallback vers format fusionné local

- `docker-entrypoint.sh` :
  - Vérification fichiers selon format (5B vs 14B)
  - Configuration symlinks pour T5 Encoder FP8

**Impact sur le fonctionnement global** :
- ✅ Modèles téléchargés depuis OwnCloud sont au format natif ComfyUI
- ✅ T5 Encoder en format FP8 quantized (6.27 GB au lieu de 10.58 GB)
- ✅ VAE déjà compatible 48 canaux (pas de conversion nécessaire)
- 🔗 Interaction avec : `workflows/workflow_manager.py` (détection modèle)

**Mise à jour documentation nécessaire** :
- [x] CLAUDE.md - Section "Modèles WAN 2.2" (format ComfyUI Native)
- [ ] README.md - Section installation/setup
- [ ] README-RUNPOD.md - Téléchargement modèles

---

## 📊 État actuel du projet (snapshot)

### Modèles
- **Format** : ComfyUI Native (Comfy-Org)
- **5B** : `wan2.2_ti2v_5B_fp16.safetensors` (9.31 GB)
- **T5 Encoder** : `umt5_xxl_fp8_e4m3fn_scaled.safetensors` (6.27 GB, FP8 quantized)
- **VAE** : `wan2.2_vae.safetensors` (48 canaux, compatible nativement)

### Architecture
- **Flask** (5000) : Interface web
- **ComfyUI** (8188) : Engine génération
- **Communication** : WebSocket
- **Storage** : OwnCloud + rclone

### Fichiers critiques
- `scripts/patch_comfyui_torch_load.py` : Patch ComfyUI pour safetensors FP8 (v3)
- `docker-entrypoint.sh` : Orchestration démarrage (download + patch + ComfyUI)
- `workflows/workflow_manager.py` : Sélection template + paramètres
- `src/comfyui_client.py` : Communication WebSocket avec ComfyUI

### Dépendances
- PyTorch 2.10.dev (CUDA 12.8)
- safetensors (chargement T5 FP8)
- ComfyUI + ComfyUI-WanVideoWrapper (custom nodes)

---

## 🎯 Checklist de mise à jour documentation

### Quand l'utilisateur demande "Actualise la documentation"

**Étape 1** : Analyser CHANGES_TRACKER.md
- Identifier toutes les modifications non documentées (checkbox `[ ]`)
- Identifier les changements depuis la dernière mise à jour

**Étape 2** : Lire les fichiers actuels
- `CLAUDE.md` : Comprendre la structure actuelle
- `README.md` : Style et niveau de détail
- `README-DOCKER.md` : Focus Docker
- `README-RUNPOD.md` : Focus RunPod

**Étape 3** : Mettre à jour CLAUDE.md
- Version incrémentée
- Section "Dernières modifications" actualisée
- Sections techniques mises à jour (architecture, fichiers critiques, etc.)
- **Style** : Technique, détaillé, optimisé pour la compréhension de Claude

**Étape 4** : Mettre à jour README.md
- Conserver le style professionnel et esthétique
- Mettre à jour les sections concernées par les changements
- **Style** : Clair, accessible, documentation utilisateur

**Étape 5** : Mettre à jour README-DOCKER.md
- Focus sur les aspects Docker (Dockerfile, docker-compose, etc.)
- Mettre à jour les instructions de build/deploy
- **Style** : Orienté DevOps

**Étape 6** : Mettre à jour README-RUNPOD.md
- Focus sur le déploiement RunPod
- Mettre à jour les logs à vérifier, troubleshooting
- **Style** : Guide de déploiement

**Étape 7** : Cocher les checkboxes dans CHANGES_TRACKER.md
- Marquer `[x]` pour toutes les mises à jour effectuées

---

## 📝 Template d'ajout de modification

```markdown
### [YYYY-MM-DD HH:MM] - Titre court de la modification

**Fichiers modifiés** :
- `chemin/fichier.ext` :
  - Description détaillée du changement
  - Lignes modifiées (si pertinent)
  - Raison du changement

**Impact sur le fonctionnement global** :
- Impact sur les autres composants
- Nouvelles dépendances
- Changements de comportement
- 🔗 Interaction avec : (lister les fichiers/composants impactés)

**Mise à jour documentation nécessaire** :
- [ ] CLAUDE.md - Section X
- [ ] README.md - Section Y
- [ ] README-DOCKER.md - Section Z
- [ ] README-RUNPOD.md - Section W

**Notes additionnelles** :
- Toute information contextuelle importante
```

---

## 🔍 Sections à surveiller dans chaque fichier de documentation

### CLAUDE.md
- **Version** : À incrémenter à chaque changement significatif
- **Dernières modifications** : Top 3-5 changements récents
- **Points Critiques** : Nouvelles fonctionnalités/corrections importantes
- **Structure du projet** : Si ajout/suppression de fichiers
- **Scripts Clés** : Si modification de scripts
- **Workflow Complet** : Si changement de processus

### README.md
- **Installation** : Si nouvelles dépendances
- **Configuration** : Si nouvelles variables d'environnement
- **Utilisation** : Si nouvelles fonctionnalités
- **Troubleshooting** : Si nouveaux problèmes/solutions

### README-DOCKER.md
- **Dockerfile** : Si modifications dans la construction
- **Variables d'environnement** : Si nouvelles variables
- **Build process** : Si changements dans le build
- **Troubleshooting Docker** : Si nouveaux problèmes

### README-RUNPOD.md
- **Déploiement** : Si changements dans le processus
- **Logs de vérification** : Si nouveaux logs à surveiller
- **Configuration Pod** : Si nouveaux paramètres
- **Troubleshooting RunPod** : Si nouveaux problèmes spécifiques

---

## 💡 Rappel pour Claude Code

**Lors de chaque modification de fichier** :
1. Ajouter une entrée dans ce CHANGES_TRACKER.md
2. Décrire l'impact sur le fonctionnement global
3. Cocher les sections de documentation à mettre à jour
4. Attendre la demande explicite de l'utilisateur pour actualiser la documentation complète

**Lors de la demande "Actualise la documentation"** :
1. Lire ce CHANGES_TRACKER.md en entier
2. Identifier toutes les modifications non documentées
3. Lire les 4 fichiers de documentation actuels
4. Proposer les mises à jour pour chaque fichier
5. Appliquer après validation de l'utilisateur
6. Cocher les checkboxes de mise à jour effectuée
