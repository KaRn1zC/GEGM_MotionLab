# GEGM MotionLab - Guide Docker

**Déploiement containerisé local et cloud**

[![Docker](https://img.shields.io/badge/docker-20.10+-blue.svg)](https://docker.com)
[![Platform](https://img.shields.io/badge/platform-AMD64-success.svg)](https://docs.docker.com/build/building/multi-platform/)
[![Version](https://img.shields.io/badge/version-5.1.0-blue.svg)](CHANGELOG.md)

---

## Architecture Docker

### Single-stage Build

```dockerfile
# Base CUDA 12.8.1 + Python 3.11 + PyTorch nightly cu128
FROM nvidia/cuda:12.8.1-cudnn-runtime-ubuntu22.04
WORKDIR /workspace

# Dépendances Python + ComfyUI + custom nodes + Flask app
# Modèles téléchargés au démarrage (pas inclus dans l'image)
```

### Stratégie Modèles

| Approche | Taille Image | Avantage |
|----------|--------------|----------|
| **Image sans modèles** | ~8 GB | Push/pull rapide |
| Modèles au démarrage | +15-20 min | Téléchargement upstream ou OwnCloud (fallback) |

---

## Prérequis

- **Docker** : 20.10+ avec BuildX
- **Docker Compose** : 2.0+
- **GPU NVIDIA** : 48GB+ VRAM (optionnel pour dev)
- **Espace disque** : 100 GB

```bash
docker --version
docker compose version
nvidia-smi  # optionnel
```

---

## Configuration

### Variables (.env)

```bash
cp .env.example .env
```

```env
# Flask
FLASK_HOST=0.0.0.0
FLASK_PORT=5000

# ComfyUI
COMFYUI_HOST=127.0.0.1
COMFYUI_PORT=8188

# OwnCloud (optionnel local, requis RunPod)
OWNCLOUD_SERVER_URL=https://your-server.com
OWNCLOUD_USERNAME=your-username
OWNCLOUD_PASSWORD=your-password
OWNCLOUD_MODEL_FOLDER=/GEGM_ComfyUI/Models
```

### docker-compose.yml

```yaml
services:
  comfy_img_to_loop:
    build:
      context: .
      dockerfile: Dockerfile
    ports:
      - "5000:5000"   # Flask
      - "8188:8188"   # ComfyUI
    volumes:
      - ./logs:/workspace/logs
      - ./web_interface/uploads:/workspace/web_interface/uploads
    deploy:
      resources:
        reservations:
          devices:
            - driver: nvidia
              count: all
              capabilities: [gpu]
```

---

## Développement Local

### Démarrage

```bash
git clone <repo>
cd GEGM_MotionLab
cp .env.example .env
docker compose up -d
open http://localhost:5000
```

### Commandes

```bash
# Démarrer/Arrêter
docker compose up -d
docker compose down

# Logs
docker compose logs -f

# Rebuild
docker compose up -d --build
docker compose build --no-cache

# Shell container
docker compose exec comfy_img_to_loop /bin/bash

# Stats
docker stats
```

---

## Build & Déploiement

```bash
make runpod-deploy              # Build + push → :latest (production)
make runpod-deploy-test         # Build + push → :test (expérimentation)
make runpod-deploy-nocache      # Idem sans cache (rebuild complet)
make runpod-deploy-test-nocache # Idem sans cache
```

---

## Volumes

| Volume | Container | Usage |
|--------|-----------|-------|
| `./logs` | `/workspace/logs` | Logs application |
| `./web_interface/uploads` | `/workspace/web_interface/uploads` | Images uploadées |
| `./config` | `/workspace/config` | Configuration (lecture seule) |
| `./workflows/templates` | `/workspace/workflows/templates` | Templates workflows (lecture seule) |

---

## Entrypoint

**Fichier :** `/workspace/docker-entrypoint.sh`

L'entrypoint est **registry-aware** : il consulte `config/model_registry.yaml` pour déterminer les fichiers à télécharger, les symlinks à créer et les vérifications à effectuer. Supporte WAN 2.2 et LTX 2.3 sans modification.

```
1. Configuration rclone (si OwnCloud)
2. Download modèles via registre (multi-repo, chunks si OwnCloud)
3. Reconstitution chunks
4. Création symlinks (T5 pour WAN, Gemma pour LTX)
5. Démarrage ComfyUI (background)
6. Health check (180s timeout)
7. Démarrage Flask (foreground)
```

---

## Troubleshooting

### Build échoue

```bash
docker builder prune -a
docker compose build --no-cache
df -h  # Vérifier espace
```

### Container crash

```bash
docker compose logs comfy_img_to_loop
docker compose run --rm comfy_img_to_loop /bin/bash
```

### GPU non détecté

```bash
docker compose exec comfy_img_to_loop nvidia-smi
docker run --rm --gpus all nvidia/cuda:12.8.1-base-ubuntu22.04 nvidia-smi
```

### ComfyUI inaccessible

```bash
docker compose exec comfy_img_to_loop curl http://localhost:8188/system_stats
docker compose exec comfy_img_to_loop tail -f /workspace/logs/comfyui.log
```

---

## Requirements Python

| Fichier | Contenu | Usage |
|---------|---------|-------|
| `requirements.txt` | SANS PyTorch (installé séparément avec CUDA) | Docker |

**Raison :** Dockerfile installe PyTorch optimisé GPU

---

## Optimisations

### Layers cachés
- Base CUDA → cache efficace
- PyTorch → réutilisé
- App → rebuild rapide

### Image finale
- Image single-stage (~8 GB sans modèles)
- Nettoyage cache apt/pip automatique
- Modèles téléchargés au démarrage du container via entrypoint

---

## Ressources

- [Docker Documentation](https://docs.docker.com)
- [NVIDIA Container Toolkit](https://github.com/NVIDIA/nvidia-docker)
- [Docker BuildX](https://docs.docker.com/build/building/multi-platform/)

---

**Version:** 5.1.0 | **Image:** `arnaudboy/comfy_img_to_loop:latest` | **Date:** 2026-03-17
