# 🐳 GEGM MotionLab - Guide Docker

Guide complet de déploiement containerisé pour GEGM MotionLab en environnement local.

[![Docker](https://img.shields.io/badge/docker-20.10+-blue.svg)](https://docker.com)
[![Docker Compose](https://img.shields.io/badge/docker%20compose-2.0+-blue.svg)](https://docs.docker.com/compose)

---

## 📋 Table des matières

1. [Architecture Docker](#architecture-docker)
2. [Prérequis](#prérequis)
3. [Installation et démarrage](#installation-et-démarrage)
4. [Configuration](#configuration)
5. [Gestion des services](#gestion-des-services)
6. [Volumes et persistance](#volumes-et-persistance)
7. [Build custom](#build-custom)
8. [Troubleshooting](#troubleshooting)

---

## Architecture Docker

### Stratégie multi-stage

Le **Dockerfile** utilise une stratégie multi-stage pour minimiser la taille de l'image finale:

```dockerfile
# Stage 1: Base CUDA
FROM nvidia/cuda:12.8.1-cudnn-runtime-ubuntu22.04 AS base
# GPU runtime + librairies CUDA 12.8

# Stage 2: Builder
FROM base AS builder
# Installation dépendances
# Compilation wheels Python
# Build dependencies temporaires

# Stage 3: Runtime
FROM base AS runtime
# Copie wheels du builder
# ComfyUI + dépendances
# Configuration entrypoint
# Image finale ~8GB
```

### Taille optimisée

| Variante | Taille | Contenu | Usage |
|----------|--------|---------|-------|
| **Image légère** | ~8 GB | Runtime + ComfyUI | ✅ Actuellement utilisée |
| **Modèles séparés** | - | WAN 2.2 5B/14B (41GB) | Téléchargés au démarrage Pod |
| **Total complet** | ~49 GB | Image + modèles | Non utilisé (trop volumineux) |

**Avantage:** Image légère permet:
- ✅ Déploiement rapide RunPod (~10 sec démarrage)
- ✅ Push/pull rapide Docker Hub
- ✅ Modèles téléchargés depuis OwnCloud au démarrage (~5-10 min)

---

## Prérequis

### Système local

- **Docker** : 20.10+ avec BuildX
- **Docker Compose** : 2.0+
- **GPU NVIDIA** : 40+ GB VRAM minimum (48GB recommandé)
- **CUDA** : 12.8+ sur machine hôte (optionnel pour hôte)
- **RAM** : 8 GB minimum
- **Espace disque** : 100 GB minimum
  - ~8 GB image Docker
  - ~13-28 GB modèles WAN 2.2
  - ~40-50 GB working/output

### Commandes requises

```bash
# Vérifier Docker
docker --version       # Doit être 20.10+
docker-compose --version  # Doit être 2.0+

# Vérifier GPU NVIDIA (optionnel)
nvidia-smi            # Si pas disponible sur hôte, OK (Docker l'a)
```

### Accès au registre Docker

- Compte Docker Hub OU
- Registre privé configuré
- (Optionnel pour développement local)

---

## Installation et démarrage

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

### Démarrage rapide (recommended)

```bash
# 1. Cloner le projet
git clone <repo-url>
cd GEGM_MotionLab

# 2. Copier template configuration
cp .env.example .env
# Éditer .env si besoin (optionnel pour local)

# 3. Démarrer services
docker-compose up -d

# 4. Attendre démarrage (30-60 secondes)
sleep 30

# 5. Vérifier statut
docker-compose ps
docker-compose logs

# 6. Accéder interface
open http://localhost:5000
```

### Démarrage pas à pas

#### Étape 1: Build image

```bash
# Build local (sans modèles)
docker-compose build

# Output: Image ID: sha256:abc123...
# Taille: ~8GB
# Durée: 10-15 minutes (première fois)
```

#### Étape 2: Configurer variables d'environnement

```bash
# Copier template
cp .env.example .env

# Éditer (si besoin d'OwnCloud)
nano .env
```

**Variables principales pour local:**
```env
FLASK_HOST=0.0.0.0
FLASK_PORT=5000
FLASK_DEBUG=false

COMFYUI_HOST=127.0.0.1
COMFYUI_PORT=8188

LOG_LEVEL=INFO
```

**Si vous utiliserez OwnCloud (optionnel pour local):**
```env
OWNCLOUD_SERVER_URL=https://www.cloud-gegm.com
OWNCLOUD_USERNAME=votre-username
OWNCLOUD_PASSWORD=votre-password
```

#### Étape 3: Démarrer les services

```bash
# Démarrage en arrière-plan
docker-compose up -d

# OU démarrage au premier plan (logs visibles)
docker-compose up
```

#### Étape 4: Vérifier démarrage

```bash
# Vérifier statut services
docker-compose ps
# Status: "healthy" pour comfy_img_to_loop

# Voir logs détaillés
docker-compose logs -f

# Attendre messages:
# "ComfyUI started successfully"
# "Flask app started on 0.0.0.0:5000"
```

#### Étape 5: Accéder l'interface

```bash
# Ouvrir navigateur
open http://localhost:5000

# OU direct URL
curl http://localhost:5000/health
# Response: {"status":"healthy",...}
```

---

## Configuration

### Docker Compose Configuration

**Fichier: docker-compose.yml**

```yaml
services:
  comfy_img_to_loop:
    image: arnaudboy/comfy_img_to_loop:latest
    build: .
    container_name: gegm_motionlab
    restart: unless-stopped
    
    # GPU Configuration
    deploy:
      resources:
        reservations:
          devices:
            - driver: nvidia
              count: 1
              capabilities: [gpu]
    
    # Réseau et ports
    ports:
      - "5000:5000"    # Flask interface
      - "8188:8188"    # ComfyUI API
    
    # Variables d'environnement
    env_file:
      - .env
    
    # Volumes (persistance)
    volumes:
      - ./logs:/app/logs              # Logs application
      - ./uploads:/app/uploads        # Images uploadées
      - ./output:/app/output          # Vidéos générées
      - ./config:/app/config          # Configuration
    
    # Vérification santé
    healthcheck:
      test: ["CMD", "curl", "-f", "http://localhost:5000/health"]
      interval: 30s
      timeout: 10s
      retries: 3
      start_period: 60s
    
    # Limites ressources
    mem_limit: 16g
    memswap_limit: 16g
```

### Variables d'environnement

| Variable | Valeur | Description |
|----------|--------|-------------|
| `FLASK_HOST` | `0.0.0.0` | Adresse d'écoute Flask |
| `FLASK_PORT` | `5000` | Port Flask |
| `FLASK_DEBUG` | `false` | Debug mode (false en prod) |
| `COMFYUI_HOST` | `127.0.0.1` | Host ComfyUI (localhost) |
| `COMFYUI_PORT` | `8188` | Port ComfyUI |
| `COMFYUI_TIMEOUT` | `300` | Timeout WebSocket (sec) |
| `LOG_LEVEL` | `INFO` | Level logging (INFO/DEBUG/WARNING) |
| `CUDA_VISIBLE_DEVICES` | `0` | GPU IDs (0 pour premier GPU) |

**Pour OwnCloud (optionnel):**

| Variable | Exemple | Description |
|----------|---------|-------------|
| `OWNCLOUD_SERVER_URL` | `https://cloud.example.com` | URL serveur OwnCloud |
| `OWNCLOUD_USERNAME` | `user@example.com` | Username |
| `OWNCLOUD_PASSWORD` | `password` | Mot de passe |
| `OWNCLOUD_MODEL_FOLDER` | `/GEGM_ComfyUI/Models` | Dossier modèles |

---

## Gestion des services

### Commandes essentielles

#### Démarrage/Arrêt

```bash
# Démarrer en arrière-plan
docker-compose up -d

# Démarrer au premier plan (logs visibles)
docker-compose up

# Arrêter services
docker-compose stop

# Arrêter et supprimer conteneurs
docker-compose down

# Arrêter et nettoyer tout (volumes inclus)
docker-compose down -v
```

#### Logs et monitoring

```bash
# Logs en temps réel
docker-compose logs -f

# Logs service spécifique
docker-compose logs -f comfy_img_to_loop

# Logs dernières 100 lignes
docker-compose logs --tail=100

# Logs avec timestamps
docker-compose logs -f --timestamps
```

#### Vérification statut

```bash
# Vérifier statut services
docker-compose ps

# Vérifier health check
docker-compose ps --no-trunc

# Vérifier disque utilisé
docker system df

# Vérifier réseau services
docker-compose exec comfy_img_to_loop \
  curl http://127.0.0.1:8188/system_stats
```

#### Nettoyage et maintenance

```bash
# Redémarrer service
docker-compose restart

# Rebuild image sans cache
docker-compose build --no-cache

# Nettoyer images inutilisées
docker image prune -a --force

# Nettoyer volumes inutilisés
docker volume prune -f

# Nettoyer tout
docker system prune -a --volumes -f
```

---

## Volumes et persistance

### Types de volumes

| Mount Path | Type | Persistence | Purpose |
|---|---|---|---|
| `/app/logs` | Volume local | ✅ Persistant | Logs application |
| `/app/uploads` | Volume local | ✅ Persistant | Images uploadées (temporaire) |
| `/app/output` | Volume local | ✅ Persistant | Vidéos générées (avant upload OwnCloud) |
| `/app/config` | Volume local | ✅ Persistant | Configuration application |
| `/workspace/comfyui` | Volume interne | ❌ Éphémère* | ComfyUI + modèles |

\* Les modèles sont téléchargés au démarrage depuis OwnCloud sur RunPod

### Gestion des volumes

**Voir disque utilisé:**
```bash
docker-compose exec comfy_img_to_loop \
  df -h /app /workspace

# Output:
# /app       50G  10G  40G  20%  (uploads + output)
# /workspace 500G 40G 460G  8%  (modèles + working)
```

**Nettoyer uploads/output locales:**
```bash
# Local directory
rm -rf ./output/*
rm -rf ./uploads/*

# Ou via Docker
docker-compose exec comfy_img_to_loop \
  sh -c "rm -rf /app/output/* /app/uploads/*"
```

**Backup volumes:**
```bash
# Backup complet
docker-compose exec comfy_img_to_loop \
  tar -czf - /app/output | gzip > backup.tar.gz

# Restore
gunzip < backup.tar.gz | \
  docker-compose exec -T comfy_img_to_loop \
  tar -xzf - -C /
```

---

## Build custom

### Builder image localement

```bash
# Build standard
docker build -t gegm-motionlab:latest .

# Build multi-arch (amd64 + arm64)
docker buildx build --platform linux/amd64,linux/arm64 \
  --tag gegm-motionlab:latest \
  .

# Build avec tag personnalisé
docker build -t gegm-motionlab:dev \
  --build-arg PYTHON_VERSION=3.11 \
  .
```

### Push vers registre

```bash
# Tag pour Docker Hub
docker tag gegm-motionlab:latest \
  username/comfy_img_to_loop:latest

# Login Docker Hub
docker login

# Push
docker push username/comfy_img_to_loop:latest

# Multi-arch avec buildx + push
docker buildx build --platform linux/amd64,linux/arm64 \
  --tag username/comfy_img_to_loop:latest \
  --push .
```

### Override docker-compose local

**Fichier: docker-compose.override.yml**
```yaml
services:
  comfy_img_to_loop:
    build:
      context: .
      dockerfile: Dockerfile
      args:
        PYTHON_VERSION: "3.11"
    
    environment:
      FLASK_DEBUG: "true"
      LOG_LEVEL: "DEBUG"
    
    ports:
      - "5000:5000"
      - "8188:8188"
      - "6006:6006"  # TensorBoard (optionnel)
    
    volumes:
      - .:/app  # Code hot-reload
      - ./logs:/app/logs
```

**Utilisation:**
```bash
docker-compose up  # Utilise automatiquement les overrides
```

---

## Troubleshooting

### Services ne démarrent pas

**Symptôme:** `docker-compose up` échoue immédiatement

```bash
# 1. Vérifier logs
docker-compose logs

# 2. Vérifier image existe
docker images | grep gegm

# 3. Vérifier ports disponibles
netstat -an | grep 5000
lsof -i :5000

# 4. Tuer process utilisant port
sudo lsof -ti :5000 | xargs kill -9

# 5. Rebuild image
docker-compose build --no-cache

# 6. Redémarrer Docker daemon
sudo systemctl restart docker
```

### GPU non utilisée

**Symptôme:** `nvidia-smi` dans container affiche pas de GPU

```bash
# 1. Vérifier GPU hôte
nvidia-smi

# 2. Vérifier driver Docker NVIDIA
docker run --rm --gpus all nvidia/cuda:12.8.1-base \
  nvidia-smi

# 3. Si erreur, réinstaller Docker NVIDIA
# macOS: docker-compose inclut déjà support GPU
# Linux: apt install nvidia-docker2

# 4. Vérifier configuration docker-compose
docker-compose config | grep -A 10 "deploy:"

# 5. Test GPU dans container
docker-compose exec comfy_img_to_loop \
  python -c "import torch; print(torch.cuda.is_available())"
```

### VRAM insuffisante

**Symptôme:** `CUDA out of memory` lors génération

```bash
# 1. Vérifier VRAM utilisée
docker-compose exec comfy_img_to_loop \
  nvidia-smi

# 2. Réduire steps dans interface (20 → 15)

# 3. Augmenter memory limits dans docker-compose.yml
mem_limit: 32g  # Si GPU a suffisant
memswap_limit: 32g

# 4. Vérifier autres processes GPU
nvidia-smi -l 1  # Refresh toutes les secondes

# 5. Redémarrer container
docker-compose restart
```

### Modèles non trouvés

**Symptôme:** Erreur "Checkpoint not found"

```bash
# 1. Vérifier présence modèles locaux
docker-compose exec comfy_img_to_loop \
  ls -lh /workspace/comfyui/ComfyUI/models/checkpoints/

# 2. Si vides, télécharger depuis HF
docker-compose exec comfy_img_to_loop \
  bash -c "cd /app && \
    python scripts/setup_wan22_native.sh"

# 3. OU télécharger depuis OwnCloud
# Note: Ce script détecte automatiquement chunks/mapping.txt et
# reconstitue les fichiers safetensors AVANT la vérification d'intégrité
docker-compose exec comfy_img_to_loop \
  python scripts/download_models_from_owncloud.py

# 4. Vérifier taille modèles
docker-compose exec comfy_img_to_loop \
  du -sh /workspace/comfyui/ComfyUI/models/checkpoints/
```

### Erreur VAE (96 vs 48 canaux)

**Symptôme:** `RuntimeError: Expected 48 channels, got 96`

```bash
# 1. Vérifier VAE utilisé
docker-compose exec comfy_img_to_loop \
  ls -l /workspace/comfyui/ComfyUI/models/vae/

# 2. Si pas présent, créer symlinks (VAE, modèles WAN)
# Note: T5 Encoder est maintenant téléchargé directement vers
# /workspace/comfyui/ComfyUI/models/text_encoders/t5/ par docker-entrypoint.sh
# setup_diffusion_models.sh ne crée plus de symlinks T5
docker-compose exec comfy_img_to_loop \
  bash -c "cd /app && \
    bash scripts/setup_diffusion_models.sh"

# 3. Vérifier VAE converti existe
docker-compose exec comfy_img_to_loop \
  ls -l /workspace/comfyui/ComfyUI/models/checkpoints/wan*/Wan2.2_VAE.pth

# 4. Si pas converti, reconvertir
docker-compose exec comfy_img_to_loop \
  python -c "from upload_models_to_owncloud import convert_vae_96_to_48; ..."
```

### Connexion ComfyUI échoue

**Symptôme:** "Failed to connect to ComfyUI" dans logs

```bash
# 1. Vérifier port ComfyUI
docker-compose logs | grep -i "8188\|comfyui started"

# 2. Tester connexion locale
docker-compose exec comfy_img_to_loop \
  curl -s http://127.0.0.1:8188/system_stats | python -m json.tool

# 3. Vérifier health check
docker-compose exec comfy_img_to_loop \
  curl -s http://localhost:5000/health

# 4. Augmenter COMFYUI_TIMEOUT
# .env: COMFYUI_TIMEOUT=600  (au lieu de 300)

# 5. Redémarrer
docker-compose restart
```

### OwnCloud ne se connecte pas

**Symptôme:** "OwnCloud authentication failed"

```bash
# 1. Vérifier configuration
cat .env | grep OWNCLOUD

# 2. Tester rclone
docker-compose exec comfy_img_to_loop \
  rclone ls owncloud:/GEGM_ComfyUI/Models

# 3. Vérifier credentials
docker-compose exec comfy_img_to_loop \
  rclone config show owncloud

# 4. Test connexion directe
curl -u username:password \
  https://cloud-gegm.com/remote.php/webdav

# 5. Ajouter debug logs
LOG_LEVEL=DEBUG docker-compose up
```

### Disque plein

**Symptôme:** "No space left on device"

```bash
# 1. Vérifier espace disque
docker-compose exec comfy_img_to_loop \
  df -h /

# 2. Nettoyer output videos
rm -rf ./output/*

# 3. Nettoyer uploads temporaires
rm -rf ./uploads/*

# 4. Nettoyer logs
docker-compose exec comfy_img_to_loop \
  rm -rf /app/logs/*.log

# 5. Nettoyer Docker
docker system prune -a --volumes -f

# 6. Verifier espace à nouveau
df -h
```

---

## Conseils de performance

### Optimiser build time

```bash
# Utiliser cache layers
docker-compose build

# Ou builder sans cache (plus lent)
docker-compose build --no-cache

# Multi-stage: seulement runtime dans final image
# Réduit taille ~75%
```

### Optimiser runtime

```bash
# 1. GPU memory allocation
PYTORCH_CUDA_ALLOC_CONF=max_split_size_mb:1024

# 2. Réduire steps pour tests rapides
# Interface: Preset "Rapide" = 15 steps

# 3. Réduire logs verbosity en production
LOG_LEVEL=WARNING

# 4. Augmenter memory limits si VRAM ample
mem_limit: 32g
```

---

## Commandes Makefile utiles

```bash
# Démarrage rapide
make up                          # docker-compose up -d

# Voir logs
make logs                        # docker-compose logs -f

# Arrêter
make down                        # docker-compose down

# Rebuild
make rebuild                     # docker-compose build --no-cache

# Nettoyage
make clean                       # Remove volumes

# Deployer sur RunPod
make runpod-deploy              # Build + push multi-arch

# Voir tous les targets
make help
```

---

## Ressources

- [Docker Documentation](https://docs.docker.com)
- [Docker Compose Documentation](https://docs.docker.com/compose)
- [NVIDIA Docker Documentation](https://github.com/NVIDIA/nvidia-docker)
- [README.md](README.md) - Documentation principale
- [README_RUNPOD.md](README_RUNPOD.md) - Déploiement RunPod

---

**Last Updated:** 12 novembre 2025
**Status:** ✅ Production Ready
**Version:** 3.1.2