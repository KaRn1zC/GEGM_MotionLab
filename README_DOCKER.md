# 🐳 GEGM MotionLab - Guide Docker

**Déploiement containerisé pour environnement local et RunPod**

[![Docker](https://img.shields.io/badge/docker-20.10+-blue.svg)](https://docker.com)
[![Docker Compose](https://img.shields.io/badge/docker%20compose-2.0+-blue.svg)](https://docs.docker.com/compose)
[![Multi-arch](https://img.shields.io/badge/platform-AMD64%20%2F%20ARM64-success.svg)](https://docs.docker.com/build/building/multi-platform/)

---

## 📋 Table des matières

1. [Architecture Docker](#architecture-docker)
2. [Prérequis](#prérequis)
3. [Configuration](#configuration)
4. [Développement Local](#développement-local)
5. [Build Multi-arch](#build-multi-arch)
6. [Volumes et Persistance](#volumes-et-persistance)
7. [Troubleshooting](#troubleshooting)

---

## 🏗️ Architecture Docker

### Dockerfile Multi-stage

Le **Dockerfile** utilise une stratégie multi-stage pour optimiser la taille de l'image :

```dockerfile
# Stage 1: Base CUDA
FROM nvidia/cuda:12.8.1-cudnn-runtime-ubuntu22.04 AS base
# → GPU runtime + librairies CUDA 12.8

# Stage 2: Builder
FROM base AS builder
# → Installation PyTorch optimisé GPU
# → Compilation wheels Python
# → Build dependencies temporaires

# Stage 3: Runtime
FROM base AS runtime
# → Copie wheels du builder
# → ComfyUI + custom nodes
# → Scripts + dépendances app
# → Configuration entrypoint
```

**Avantages :**
- ✅ Image finale légère (~8 GB)
- ✅ Pas de build tools dans runtime
- ✅ Couches optimisées et cachées

---

### Stratégie Modèles

| Approche | Taille | Avantages | Inconvénients |
|----------|--------|-----------|---------------|
| **Image légère** ⭐ | ~8 GB | Push/pull rapide, démarrage Pod <10s | Download modèles au démarrage (~15-20 min) |
| **Image avec modèles** | ~49 GB | Modèles préchargés | Push/pull lent, image volumineuse |

**Choix actuel :** Image légère + téléchargement modèles depuis OwnCloud au démarrage Pod

**Raison :**
- RunPod a une connexion rapide vers OwnCloud
- Temps total démarrage identique (~20 min)
- Image Docker maintenue à jour facilement

---

## 🔧 Prérequis

### Système Local

- **Docker** : 20.10+ avec BuildX
- **Docker Compose** : 2.0+
- **GPU NVIDIA** : 48GB+ VRAM recommandé (optionnel pour dev sans génération)
- **RAM** : 8 GB minimum
- **Espace disque** : 100 GB minimum

### Vérification

```bash
# Docker
docker --version       # ≥20.10
docker compose version # ≥2.0

# GPU NVIDIA (optionnel pour local)
nvidia-smi
```

---

## ⚙️ Configuration

### Variables d'environnement

Le fichier `.env` configure l'ensemble du stack. Créer depuis le template :

```bash
cp .env.example .env
```

**Variables principales :**

```env
# Flask
FLASK_HOST=0.0.0.0
FLASK_PORT=5000
FLASK_DEBUG=false

# ComfyUI
COMFYUI_HOST=127.0.0.1
COMFYUI_PORT=8188
COMFYUI_TIMEOUT=300

# OwnCloud (optionnel local, requis RunPod)
OWNCLOUD_SERVER_URL=https://your-server.com
OWNCLOUD_USERNAME=your-username
OWNCLOUD_PASSWORD=your-password
OWNCLOUD_MODEL_FOLDER=/GEGM_ComfyUI/Models

# GPU
CUDA_VISIBLE_DEVICES=0
LOG_LEVEL=INFO
```

---

### docker-compose.yml

Le fichier définit 2 services :

```yaml
services:
  # Service principal (Flask + ComfyUI)
  comfy_img_to_loop:
    build:
      context: .
      dockerfile: docker/Dockerfile
    ports:
      - "5000:5000"    # Flask app
      - "8188:8188"    # ComfyUI
    volumes:
      - ./output:/app/output
      - ./uploads:/app/uploads
      - ./logs:/app/logs
    env_file:
      - .env
    deploy:
      resources:
        reservations:
          devices:
            - driver: nvidia
              count: all
              capabilities: [gpu]
```

**Ports exposés :**
- **5000** : Interface web Flask
- **8188** : ComfyUI API (WebSocket + HTTP)

---

## 🚀 Développement Local

### Démarrage rapide

```bash
# Cloner projet
git clone <repo>
cd GEGM_MotionLab

# Configuration
cp .env.example .env
# Éditer .env (OwnCloud optionnel pour local)

# Build et démarrer
docker compose up -d

# Suivre logs
docker compose logs -f

# Accéder interface
open http://localhost:5000
```

---

### Commandes utiles

```bash
# Démarrer services
docker compose up -d

# Arrêter services
docker compose down

# Voir logs
docker compose logs -f

# Logs d'un service spécifique
docker compose logs -f comfy_img_to_loop

# Rebuild après modification code
docker compose up -d --build

# Rebuild complet (sans cache)
docker compose build --no-cache
docker compose up -d

# Shell dans le container
docker compose exec comfy_img_to_loop /bin/bash

# Redémarrer service
docker compose restart comfy_img_to_loop

# Voir stats ressources
docker stats
```

---

### Fichiers montés (volumes)

| Volume hôte | Container | Usage |
|-------------|-----------|-------|
| `./output` | `/app/output` | Vidéos générées |
| `./uploads` | `/app/uploads` | Images uploadées |
| `./logs` | `/app/logs` | Logs application |

**Avantages :**
- ✅ Fichiers persistent après arrêt container
- ✅ Accès direct depuis hôte
- ✅ Backup facilité

---

## 🏗️ Build Multi-arch

### Build pour RunPod (AMD64 + ARM64)

```bash
# Build multi-architecture + push Docker Hub
make runpod-deploy

# Équivalent manuel
docker buildx build \
  --platform linux/amd64,linux/arm64 \
  --file docker/Dockerfile \
  --tag arnaudboy/comfy_img_to_loop:latest \
  --tag arnaudboy/comfy_img_to_loop:3.1.8 \
  --push \
  .
```

**Plateformes supportées :**
- `linux/amd64` : RunPod, serveurs x86_64
- `linux/arm64` : Apple Silicon M1/M2/M3

---

### Build rapide (AMD64 uniquement)

```bash
# Build AMD64 seulement (plus rapide)
make runpod-deploy-quick

# Équivalent manuel
docker buildx build \
  --platform linux/amd64 \
  --file docker/Dockerfile \
  --tag arnaudboy/comfy_img_to_loop:latest \
  --push \
  .
```

**Utilisation :** Développement et tests rapides

---

## 📦 Volumes et Persistance

### Volumes Docker Compose

Le `docker-compose.yml` définit des volumes bind (liaison hôte ↔ container) :

```yaml
volumes:
  - ./output:/app/output         # Vidéos générées
  - ./uploads:/app/uploads       # Images uploadées
  - ./logs:/app/logs             # Logs Flask + ComfyUI
```

**Création automatique :** Les dossiers sont créés automatiquement s'ils n'existent pas.

---

### Volumes RunPod

Sur RunPod, les volumes sont éphémères par défaut. Le workflow télécharge les modèles au démarrage :

```bash
# Automatique via docker-entrypoint.sh
1. Vérifier présence modèles locaux
2. Si absents → download depuis OwnCloud
3. Reconstitution chunks
4. Création symlinks
5. Démarrage ComfyUI + Flask
```

**Container Disk RunPod :** 100 GB minimum recommandé

---

## 🔍 Inspection Image

### Vérifier contenu image

```bash
# Lister layers
docker history arnaudboy/comfy_img_to_loop:latest

# Taille image
docker images arnaudboy/comfy_img_to_loop

# Scanner vulnerabilités (optionnel)
docker scan arnaudboy/comfy_img_to_loop:latest

# Inspecter metadata
docker inspect arnaudboy/comfy_img_to_loop:latest
```

---

### Entrypoint et CMD

**Entrypoint :** `/workspace/docker-entrypoint.sh`

**Workflow au démarrage :**
1. Affichage bannière GEGM MotionLab
2. Configuration rclone (si OwnCloud configuré)
3. Download modèles depuis OwnCloud (si absents)
4. Reconstitution chunks → modèles complets
5. Création symlinks T5 Encoder
6. Démarrage ComfyUI (background)
7. Health check ComfyUI (180s timeout)
8. Démarrage Flask app (foreground)

---

## 🐛 Troubleshooting

### Image ne build pas

**Symptôme :** Erreur pendant `docker compose build`

**Solutions :**
```bash
# Nettoyer cache build
docker builder prune -a

# Rebuild sans cache
docker compose build --no-cache

# Vérifier espace disque
df -h
docker system df
```

---

### Container crash au démarrage

**Symptôme :** Container démarre puis s'arrête immédiatement

**Diagnostic :**
```bash
# Voir logs container
docker compose logs comfy_img_to_loop

# Voir derniers logs avant crash
docker logs <container_id> --tail 100

# Lancer en mode interactif
docker compose run --rm comfy_img_to_loop /bin/bash
```

**Causes fréquentes :**
- Variables d'environnement manquantes (`.env`)
- GPU non accessible (nvidia-docker-runtime)
- VRAM insuffisante

---

### ComfyUI ne démarre pas

**Symptôme :** Flask démarre mais ComfyUI inaccessible sur port 8188

**Diagnostic :**
```bash
# Vérifier logs ComfyUI
docker compose exec comfy_img_to_loop tail -f /workspace/logs/comfyui.log

# Vérifier processus
docker compose exec comfy_img_to_loop ps aux | grep comfyui

# Vérifier port
docker compose exec comfy_img_to_loop netstat -tulpn | grep 8188

# Health check manuel
docker compose exec comfy_img_to_loop curl http://localhost:8188/system_stats
```

**Solutions :**
- Vérifier symlink T5 (chemins absolus requis)
- Vérifier modèles téléchargés
- Augmenter timeout health check (180s par défaut)

---

### GPU non détecté

**Symptôme :** Container démarre mais GPU non disponible

**Diagnostic :**
```bash
# Dans container
docker compose exec comfy_img_to_loop nvidia-smi

# Vérifier runtime NVIDIA
docker run --rm --gpus all nvidia/cuda:12.8.1-base-ubuntu22.04 nvidia-smi
```

**Solutions :**
```bash
# Installer nvidia-docker (si manquant)
distribution=$(. /etc/os-release;echo $ID$VERSION_ID)
curl -s -L https://nvidia.github.io/nvidia-docker/gpgkey | sudo apt-key add -
curl -s -L https://nvidia.github.io/nvidia-docker/$distribution/nvidia-docker.list | \
  sudo tee /etc/apt/sources.list.d/nvidia-docker.list

sudo apt-get update
sudo apt-get install -y nvidia-docker2
sudo systemctl restart docker

# Vérifier configuration Docker daemon
cat /etc/docker/daemon.json
# Devrait contenir:
{
  "runtimes": {
    "nvidia": {
      "path": "nvidia-container-runtime",
      "runtimeArgs": []
    }
  }
}
```

---

### Modèles non téléchargés (RunPod)

**Symptôme :** Container démarre mais modèles absents

**Diagnostic :**
```bash
# Vérifier variables OwnCloud
docker compose exec comfy_img_to_loop env | grep OWNCLOUD

# Vérifier rclone
docker compose exec comfy_img_to_loop rclone ls owncloud:/

# Logs download
docker compose logs | grep "Download"
```

**Solutions :**
- Vérifier credentials OwnCloud dans `.env`
- Tester connexion rclone manuellement
- Vérifier espace disque container (100GB min)

---

### VRAM insuffisante

**Symptôme :** `CUDA out of memory`

**Solutions :**
```bash
# Vérifier VRAM disponible
docker compose exec comfy_img_to_loop nvidia-smi

# Libérer VRAM
docker compose restart comfy_img_to_loop

# Réduire paramètres génération
# - Steps: 20 → 15
# - Résolution: 1280x720 → 640x480
```

---

## 📝 Notes Importantes

### Requirements Python

**⚠️ 2 fichiers distincts :**

- **`requirements.txt`** : AVEC PyTorch (local)
- **`requirements-base.txt`** : SANS PyTorch (Docker)

**Raison :** Le Dockerfile installe PyTorch optimisé pour le GPU :

```dockerfile
# Dans Dockerfile (stage builder)
RUN pip3 install torch==2.6.0.dev20241121+cu128 \
    torchvision==0.20.0.dev20241121+cu128 \
    torchaudio==2.5.0.dev20241121+cu128 \
    --index-url https://download.pytorch.org/whl/nightly/cu128

# Puis installation autres dépendances
RUN pip3 install -r requirements-base.txt
```

---

### Optimisations Image

**Layers cachés :**
- Base CUDA → rarement change → cache efficace
- PyTorch → change peu → réutilisé
- Dépendances app → change souvent → rebuild rapide

**Multi-stage build :**
- Builder stage (~15 GB) → non conservé
- Runtime stage (~8 GB) → image finale

**Nettoyage automatique :**
- Suppression cache apt/pip
- Suppression build tools
- Suppression fichiers temporaires

---

## 🔗 Ressources

- [Docker Documentation](https://docs.docker.com)
- [Docker Compose Reference](https://docs.docker.com/compose/compose-file/)
- [NVIDIA Container Toolkit](https://github.com/NVIDIA/nvidia-docker)
- [Docker BuildX](https://docs.docker.com/build/building/multi-platform/)

---

**Version actuelle :** 3.1.8 (2025-11-14)
**Image Docker :** `arnaudboy/comfy_img_to_loop:latest`
**Registre :** Docker Hub
