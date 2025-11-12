# 🚀 GEGM MotionLab - Guide RunPod

Guide complet de déploiement cloud sur RunPod avec GPUs professionnels.

[![RunPod](https://img.shields.io/badge/runpod-cloud-blueviolet.svg)](https://runpod.io)
[![GPU](https://img.shields.io/badge/GPU-RTX%206000%20Ada%20%2F%20H100-green.svg)](https://runpod.io)

---

## 📋 Table des matières

1. [Présentation RunPod](#présentation-runpod)
2. [Prérequis](#prérequis)
3. [Préparation des modèles](#préparation-des-modèles)
4. [Configuration rclone](#configuration-rclone)
5. [Build et déploiement image](#build-et-déploiement-image)
6. [Créer le Pod](#créer-le-pod)
7. [Utilisation en production](#utilisation-en-production)
8. [Gestion des coûts](#gestion-des-coûts)
9. [Troubleshooting](#troubleshooting)

---

## Présentation RunPod

### Qu'est-ce que RunPod?

**RunPod** est une plateforme cloud spécialisée dans le GPU computing. Elle propose des GPUs professionnels (RTX 6000 Ada, H100 SXM, H200 SXM) à la demande avec facturation à la minute.

**Avantages:**
- ✅ GPUs haute-performance (RTX 6000 Ada 48GB, H100 SXM 80GB)
- ✅ Facturation à la minute (pas d'engagement)
- ✅ Déploiement rapide (< 1 minute)
- ✅ Intégration simple avec Docker
- ✅ API et UI intuitive

**Inconvénients:**
- ❌ Coûts variables selon GPU choisi ($0.77-$3.59/heure)
- ❌ Stockage Pod éphémère (destruction après)
- ❌ Modèles à télécharger à chaque démarrage

---

## Prérequis

### Compte et services

- **Compte RunPod** : https://runpod.io (gratuit, crédit requis)
- **OwnCloud** : Serveur avec stockage modèles (41GB minimum)
- **rclone** : Installé localement (Windows/macOS/Linux)
- **Docker Hub** (optionnel) : Pour push image multi-arch

### GPU recommandés

**Pour WAN 2.2 5B (Production Standard):**

| GPU | VRAM | Vitesse | Coût/h | Cinemagraphs/h |
|-----|------|---------|--------|-------------------|
| **RTX 6000 Ada** ⭐ | 48GB | ~5 min | $0.77 | 12 |
| **H100 SXM** | 80GB | ~2.5 min | $2.69 | 24 |
| **H200 SXM** | 141GB | ~2 min | $3.59 | 30 |

**Pour WAN 2.2 14B (Qualité Premium):**

| GPU | VRAM | Vitesse | Coût/h | Cinemagraphs/h |
|-----|------|---------|--------|-------------------|
| **H100 SXM** ⭐ | 80GB | ~8 min | $2.69 | 7 |
| **H200 SXM** | 141GB | ~5 min | $3.59 | 12 |
| **RTX 6000 Ada** | 48GB | ❌ Trop petit | - | - |

**Sélection recommandée:**
- 🏆 **5B sur RTX 6000 Ada** : Meilleur rapport coût/qualité ($0.064/cinémagraph)
- 🏆 **14B sur H100 SXM** : Meilleur rapport qualité/vitesse ($0.36/cinémagraph)

### Configuration machine locale

```bash
# Vérifier rclone
which rclone
rclone --version

# Si pas installé
# macOS: brew install rclone
# Linux: curl https://rclone.org/install.sh | sudo bash
# Windows: Télécharger depuis https://rclone.org/downloads/
```

---

## Préparation des modèles

**⏱️ Durée totale:** 45-90 minutes (dépend connexion internet)  
**💾 Espace requis:** 30-40 GB

### Étape 1: Configurer rclone

**Configuration OwnCloud une seule fois:**

```bash
# Lancer configuration interactive
rclone config

# Répondre aux prompts:
# Name: owncloud
# Type: webdav
# URL: https://www.cloud-gegm.com/remote.php/dav
# Vendor: owncloud
# User: votre-username
# Password: votre-password

# Tester connexion
rclone ls owncloud:/GEGM_ComfyUI/Models/
```

### Étape 2: Télécharger modèles depuis Hugging Face

**Option A: Automatique (recommandé)**

```bash
# Via Makefile
make download-models

# Ou script manuel
./scripts/setup_wan22_native.sh
```

**Option B: Manuel**

```bash
# Installer HF CLI
pip install huggingface-hub

# Download 5B (~13GB)
huggingface-cli download wanx/wan2.2-ti2v-5b \
  --local-dir ./models/wan2.2-ti2v-5b \
  --repo-type model

# Download 14B (~28GB)
huggingface-cli download wanx/wan2.2-i2v-a14b \
  --local-dir ./models/wan2.2-i2v-a14b \
  --repo-type model
```

**Durée estimée:** 30-45 minutes
**Output:** Modèles dans `./models/wan2.2-{ti2v-5b,i2v-a14b}/`

### Étape 3: Uploader vers OwnCloud (Workflow séquentiel)

**⭐ Recommandé (économe en espace disque): 30GB requis**

```bash
# Via Makefile
make sequential-upload-workflow
```

**Qu'est-ce que ça fait:**

```
Workflow séquentiel (30GB espace local)
├─ Download modèle 14B (~28GB)
├─ Split en chunks 2GB
├─ Upload OwnCloud via rclone
├─ Vérifier upload
├─ Supprimer fichiers locaux ✓ Libère 28GB
│
├─ Download modèle 5B (~11GB)
├─ Split en chunks 2GB
├─ Upload OwnCloud via rclone
├─ Vérifier upload
├─ Supprimer fichiers locaux ✓ Libère 11GB
│
└─ Upload script reassemble_models.sh

Note: Sur le Pod RunPod, download_models_from_owncloud.py détecte
automatiquement chunks/mapping.txt et reconstitue les fichiers
safetensors AVANT la vérification d'intégrité.
```

**Commandes individuelles (si besoin):**

```bash
# Upload 14B complet
make full-workflow-14b

# Upload 5B complet
make full-workflow-5b

# Vérifier upload réussi
make rclone-verify

# Voir résumé
# 📦 Modèle 14B: Total size: 27.8 GB, objects: 156
# 📦 Modèle 5B: Total size: 10.9 GB, objects: 87
```

**Durée estimée:** 45-90 minutes (dépend bande passante)

### Étape 4: Vérifier intégrité upload

```bash
# Lister fichiers OwnCloud
make rclone-list

# Output attendu:
# /GEGM_ComfyUI/Models/wan2.2-14b/
#   diffusion_pytorch_model-00001-of-00003.safetensors
#   diffusion_pytorch_model-00002-of-00003.safetensors
#   diffusion_pytorch_model-00003-of-00003.safetensors
#   Wan2.2_VAE.pth

# Vérifier checksums
make rclone-verify-checksums
```

---

## Configuration rclone

### Installation

```bash
# macOS
brew install rclone

# Linux
curl https://rclone.org/install.sh | sudo bash

# Windows
# Télécharger depuis https://rclone.org/downloads/
# Extraire et ajouter au PATH
```

### Configuration OwnCloud

**Méthode interactive (recommandée):**

```bash
rclone config

# Prompts:
# -> New remote? -> n (nouveau)
# -> Name: -> owncloud
# -> Type: -> webdav
# -> URL: -> https://www.cloud-gegm.com/remote.php/dav
# -> Vendor: -> owncloud
# -> User: -> votre-username
# -> Password: -> votre-password
# -> Edit advanced config? -> n
# -> Confirm? -> y
```

**Vérifier configuration:**

```bash
# Lister contenu
rclone ls owncloud:/

# Voir config stockée
rclone config show owncloud

# Test accès
rclone ls owncloud:/GEGM_ComfyUI/Models/
```

### Commandes rclone utiles

```bash
# Lister fichiers
rclone ls owncloud:/GEGM_ComfyUI/Models/

# Copier fichier
rclone copy fichier.pth \
  owncloud:/GEGM_ComfyUI/Models/

# Copier dossier complet
rclone copy ./models/wan2.2-5b/ \
  owncloud:/GEGM_ComfyUI/Models/wan2.2-5b/

# Télécharger fichier
rclone copy \
  owncloud:/GEGM_ComfyUI/Models/fichier.pth \
  ./local_folder/

# Vérifier taille distante
rclone size owncloud:/GEGM_ComfyUI/Models/
```

---

## Build et déploiement image

> Le projet utilise deux fichiers de dépendances :
> - **`requirements.txt`** contient l’ensemble des dépendances, y compris PyTorch et ses modules (torch, torchvision, torchaudio).
> - **`requirements-base.txt`** est identique à `requirements.txt` SANS ces trois lignes :
>   ```>   torch>=2.5.0,<2.6.0 >   torchaudio>=2.5.0,<2.6.0 >   torchvision>=0.20.0,<0.21.0 >  ```
>
> Cette organisation permet :
> - **En local** : Utiliser `requirements.txt` pour que `pip install -r requirements.txt` installe également PyTorch, nécessaire pour exécuter les scripts d’upload/download, VAE, découpage/reconstitution, etc.
> - **En production Docker/RunPod** : L’installation de PyTorch, optimisée pour le GPU cible, se fait directement dans le Dockerfile. Par conséquent, on n’installe dans le conteneur que les dépendances de `requirements-base.txt` (donc sans écraser la version de torch installée par le Dockerfile).
>
> **Important** :
> - En local, toujours utiliser `requirements.txt`
> - En cloud/Docker, le Dockerfile doit appeler `pip install -r requirements-base.txt` après l’installation du bon PyTorch

### Build local

```bash
# Build image standard (AMD64)
docker build -t gegm-motionlab:latest .

# Durée: 10-15 minutes
# Taille résultante: ~8GB
```

### Build et push multi-architecture

**Prérequis:** Compte Docker Hub + buildx

```bash
# 1. Setup buildx
docker buildx create --use

# 2. Login Docker Hub
docker login

# 3. Build multi-arch + push
docker buildx build --platform linux/amd64,linux/arm64 \
  --tag username/comfy_img_to_loop:latest \
  --push .

# Durée: 30-45 minutes
# Tailles générées:
# - linux/amd64: ~8.5GB
# - linux/arm64: ~8.2GB
# - Manifest: ~400MB
```

### Via Makefile

**Recommandé (wrapper automatisé):**

```bash
# Build multi-arch + push
make runpod-deploy

# OU version rapide (AMD64 uniquement)
make runpod-deploy-quick

# Voir image créée
docker images | grep gegm
```

---

## Créer le Pod

### Préparation

1. Aller sur **https://runpod.io**
2. Créer compte (gratuit) et ajouter crédits
3. Aller sur "Pods" → "Deploy"

### Création du Pod

#### Étape 1: Sélectionner GPU

**Pour WAN 2.2 5B (recommandé):**
- **RTX 6000 Ada 48GB** - Cliquer "Deploy" ($0.77/h)

**Pour WAN 2.2 14B (qualité max):**
- **H100 SXM 80GB** - Cliquer "Deploy" ($2.69/h)

#### Étape 2: Configuration Pod

| Paramètre | Valeur | Notes |
|-----------|--------|-------|
| **Pod Name** | `gegm-motionlab` | Identifiant unique |
| **Container Image** | `arnaudboy/comfy_img_to_loop:latest` | Docker Hub official |
| **Container Disk** | `100 GB` | Minimum requis |
| **Volume Disk** | `0 GB` | Pas nécessaire (ephemeral) |
| **CPU** | `8-16 cores` | Auto-sélectionné |
| **Memory** | `16-32 GB` | Auto-sélectionné |

#### Étape 3: Configuration réseau

- **Expose HTTP Port**: `5000` (interface Flask)
- **HTTP Port Label**: `GEGM MotionLab`
- Laisser autres ports fermés

#### Étape 4: Déployer

1. Vérifier configuration
2. Cliquer "Deploy Pod"
3. Attendre ~30-60 secondes

### Démarrage Pod

**Après création, RunPod affiche:**

```
Pod ID: abc-1234-xyz
Connection Status: Running
Pod URL: https://abc-1234-xyz-5000.proxy.runpod.net
```

**Vérification automatique des modèles:**

Au démarrage, `docker-entrypoint.sh` vérifie la présence des 3 fichiers safetensors reconstitués (`diffusion_pytorch_model-0000X-of-00003.safetensors`) pour déterminer si le modèle doit être téléchargé. Cette vérification garantit que les fichiers complets existent (pas seulement le dossier ou les chunks).

**Durée démarrage Pod:**

```
T+0s:       Pod boot
T+10s:      Docker container starts
T+60s:      docker-entrypoint.sh executes
T+60-70s:   Vérification modèles présents (3 fichiers safetensors)
T+70-150s:  Si absents: Download WAN model depuis OwnCloud (inclut T5 Encoder)
T+150-200s: Reconstitution automatique chunks (safetensors + T5)
T+200-210s: Exécution setup_diffusion_models.sh (crée symlinks VAE/WAN/T5)
T+210-260s: Download VAE, CLIP Vision, RealESRGAN
T+260-270s: Vérification intégrité fichiers reconstitués
T+270-320s: ComfyUI startup
T+320s:     Flask app ready
────────────────────────────
T+120-600s: GEGM MotionLab accessible
Total: 15-20 minutes before interface available
```

**Vérifier démarrage:**

```bash
# Attendre 5 minutes, puis tester
curl https://abc-1234-xyz-5000.proxy.runpod.net/health

# Response: {"status":"healthy",...}
```

---

## Utilisation en production

### Accès interface

```
https://pod-id-5000.proxy.runpod.net
```

Remplacer `pod-id` avec votre Pod ID de RunPod.

### Workflow type

```
1. Accéder URL Pod
   ↓
2. Upload image JPG/PNG
   ↓
3. Sélectionner preset ou paramètres
   ├─ Qualité Max (30 steps, ~8 min)
   ├─ Équilibré (20 steps, ~5 min) ← Recommandé
   ├─ Rapide (15 steps, ~3 min)
   └─ Naturel (20 steps, ~5 min)
   ↓
4. Cliquer "🎬 Générer le Cinemagraph"
   ↓
5. Attendre génération
   ├─ Barre progression affichée
   ├─ Étapes: Modèle → Diffusion → Upscale → Encoding
   └─ Temps: 3-8 min selon GPU/paramètres
   ↓
6. Résultat vidéo affichée
   ↓
7. Actions:
   ├─ ⬇️ Télécharger: Backup local
   ├─ ☁️ Sauvegarder: Upload OwnCloud (manuel)
   ├─ 🗑️ Supprimer: Libérer espace
   └─ 🔄 Nouvelle: Prochaine génération
```

### Gestion Pod

**Voir logs Pod:**
```bash
# Via RunPod dashboard
# Cliquer "Logs" dans Pod details

# OU via terminal (si SSH disponible)
ssh root@pod-ip
tail -f /app/logs/app.log
```

**Monitorer ressources:**
```bash
# GPU usage
curl pod-url:5000/api/stats
```

**Arrêter Pod (économiser crédits):**
1. RunPod dashboard
2. Cliquer Pod
3. "Pause" (pause) ou "Stop" (arrêt complet)

**Reprendre Pod:**
1. Dashboard
2. "Resume"
3. Redémarrage et téléchargement modèles (~20 min)

---

## Gestion des coûts

### Calcul coûts

**Pour WAN 2.2 5B (RTX 6000 Ada):**

```
Coût GPU: $0.77/hour
Temps génération: ~5 minutes par cinemagraph

Calcul par cinemagraph:
($0.77 / 60 min) × 5 min = $0.064/cinemagraph

Calcul pour session 6h:
$0.77 × 6h = $4.62
→ ~72 cinemagraphs

Mensuel (10 sessions):
$4.62 × 10 = $46.20
```

**Pour WAN 2.2 14B (H100 SXM):**

```
Coût GPU: $2.69/hour
Temps génération: ~8 minutes par cinemagraph

Calcul par cinemagraph:
($2.69 / 60 min) × 8 min = $0.36/cinemagraph

Calcul pour session 6h:
$2.69 × 6h = $16.14
→ ~45 cinemagraphs

Mensuel (10 sessions):
$16.14 × 10 = $161.40
```

### Optimisation des coûts

**1. Créer Pod uniquement si besoin immédiat**
```bash
- Avant: $0/heure
- Pendant utilisation: $0.77-$2.69/heure
- Après: $0/heure (Pod détruit)
→ Économie: ~90% vs Pod permanent
```

**2. Réduire time/generation**
```bash
- Preset "Rapide" (15 steps): -40% temps
- Réduire résolution source: -30% temps
- Résultat: Coûts réduits proportionnellement
```

**3. Batch processing (si possible)**
```bash
- Session 6h: $4.62 (5B) ou $16.14 (14B)
- Générer ~72 (5B) ou ~45 (14B) cinemagraphs par session
- Meilleur rapport que Pod permanent
```

**4. Sélectionner GPU approprié**
```bash
- 5B sur RTX 6000 Ada: Moins cher ($0.77/h vs $2.69/h)
- 14B sur H100: Plus rapide compensant coût extra
- Calculer breakeven selon besoins
```

---

## Troubleshooting

### Pod ne démarre pas

**Symptôme:** Pod reste en "Starting..." après 2-3 minutes

```bash
# 1. Attendre plus longtemps (15-20 min)
#    Docker pull image + démarrage services
#    Normal si première fois

# 2. Vérifier logs via RunPod dashboard
#    Chercher erreurs dans container output

# 3. Si bloqué:
#    - Pause Pod
#    - Resume Pod
#    - Redémarrage complet
```

### Modèles ne téléchargent pas

**Symptôme:** Erreur "Models not found" après 10 min démarrage

```bash
# 1. Vérifier logs
#    RunPod dashboard → Logs
#    Chercher "download" ou "rclone"

# 2. Vérifier OwnCloud accessible
#    - Credentials corrects?
#    - URL OwnCloud valide?
#    - Modèles présents sur OwnCloud?

# 3. Tester rclone localement
rclone ls owncloud:/GEGM_ComfyUI/Models/

# 4. Si erreur connexion OwnCloud:
#    - Vérifier .env dans container
#    - docker-entrypoint.sh lance le download

# 5. Vérifier reconstitution automatique des chunks
#    Si chunks/mapping.txt présent, reassemble_models.sh est appelé automatiquement
#    Chercher dans logs: "Reconstitution des fichiers découpés..."
#    Vérifier que les 3 fichiers safetensors sont créés:
#      - diffusion_pytorch_model-00001-of-00003.safetensors
#      - diffusion_pytorch_model-00002-of-00003.safetensors
#      - diffusion_pytorch_model-00003-of-00003.safetensors
```

### Interface ne répond pas

**Symptôme:** `connection refused` ou timeout

```bash
# 1. Attendre 20+ minutes
#    Modèles téléchargement + reconstitution longue

# 2. Vérifier Pod statut
#    RunPod dashboard → Voir si "Running"

# 3. Tester health check
curl pod-url-5000.proxy.runpod.net/health

# 4. Si timeout timeout:
#    - Vérifier bande passante OwnCloud
#    - Vérifier taille Pod disk restante
#    - Pause/Resume Pod
```

### VRAM insuffisante

**Symptôme:** `CUDA out of memory` lors génération

```bash
# 1. Vérifier GPU utilisée
#    RTX 6000 Ada (48GB) pour 5B? OK
#    H100 SXM (80GB) pour 14B? OK

# 2. Réduire steps dans interface
#    20 steps → 15 steps

# 3. Réduire résolution image
#    Source 4K → 1280x720

# 4. Dernier recours:
#    Changer vers GPU supérieur (plus cher)
```

### OwnCloud erreur connexion

**Symptôme:** Logs montrent "OwnCloud auth failed"

```bash
# 1. Vérifier credentials .env
OWNCLOUD_SERVER_URL=https://www.cloud-gegm.com
OWNCLOUD_USERNAME=correct?
OWNCLOUD_PASSWORD=correct?

# 2. Tester rclone localement
rclone ls owncloud:/

# 3. Vérifier OwnCloud serveur
#    - Serveur accessible via HTTPS?
#    - URL valide?
#    - Credentials actifs?

# 4. Solution temporaire:
#    Modèles pré-téléchargés sur NAS/cloud
#    Uploader via S3 au lieu OwnCloud
```

### Génération très lente

**Symptôme:** 5 min → 15+ min pour génération

```bash
# 1. Vérifier GPU utilisée
nvidia-smi
# "No GPU" → Pod GPU défaillante, stop/resume

# 2. Vérifier temp GPU
# > 75°C → Thermal throttling, normal

# 3. Vérifier VRAM utilisation
# > 95% → Spilling en RAM, lent

# 4. Vérifier CPU/memory Pod
# > 90% → Ressources insuffisantes

# 5. Solution:
#    - Réduire steps (20 → 15)
#    - Changer GPU vers plus puissante
```

### Coûts plus élevés que prévu

**Symptôme:** Bills RunPod > estimation

```bash
# 1. Vérifier Pod reste-t-elle active
#    Dashboard → Voir si running 24/7?
#    → Détruire Pod après usage!

# 2. Vérifier GPU facturée
#    Pod details → Voir GPU selectionnée
#    Dépend GPU: $0.77-$3.59/h

# 3. Optimiser:
#    - Utiliser RTX 6000 Ada pour 5B (moins cher)
#    - Créer Pod seulement si besoin
#    - Pause Pod si pas utilisation prolongée

# 4. Voir facturation
#    RunPod dashboard → Billing
#    Détail coûts par Pod
```

---

## Checklist préalable

Avant créer Pod en production:

- [ ] Modèles uploadés sur OwnCloud (41GB)
- [ ] rclone configuré et testé localement
- [ ] Image Docker buildée et testée localement
- [ ] Credentials OwnCloud validés
- [ ] Compte RunPod créé avec crédits
- [ ] GPU choisi et coûts calculés
- [ ] Docstring UI comprise (presets, paramètres)
- [ ] Plan de nettoyage OwnCloud (après sessions)

---

## Ressources

### Documentation

- [README.md](README.md) - Documentation principale
- [README_DOCKER.md](README_DOCKER.md) - Déploiement Docker local
- [GEGM_MotionLab_Documentation.md](GEGM_MotionLab_Documentation.md) - Documentation exhaustive

### Services externes

- [RunPod](https://runpod.io) - GPU cloud platform
- [OwnCloud](https://owncloud.com) - Self-hosted cloud storage
- [rclone](https://rclone.org) - File sync tool
- [Docker Hub](https://hub.docker.com) - Container registry

### Modèles et tools

- [WAN 2.2 (Hugging Face)](https://huggingface.co/wanx) - Modèles IA
- [ComfyUI](https://github.com/comfyanonymous/ComfyUI) - Workflow engine
- [ComfyUI-WanVideoWrapper](https://github.com/kijai/ComfyUI-WanVideoWrapper) - WAN nodes

---

**Last Updated:** 12 novembre 2025
**Status:** ✅ Production Ready
**Version:** 3.1.4