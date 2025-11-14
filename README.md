# 🎬 GEGM MotionLab 🔬

**Studio professionnel de création de cinemagraphs propulsé par WAN 2.2**

> Transformez vos images statiques en boucles vidéo fluides avec l'intelligence artificielle.

[![License](https://img.shields.io/badge/license-Private-red.svg)](LICENSE)
[![Python](https://img.shields.io/badge/python-3.11-blue.svg)](https://python.org)
[![Docker](https://img.shields.io/badge/docker-ready-green.svg)](https://docker.com)
[![ComfyUI](https://img.shields.io/badge/comfyui-latest-blueviolet.svg)](https://github.com/comfyanonymous/ComfyUI)
[![WAN 2.2](https://img.shields.io/badge/WAN%202.2-5B%20%2F%2014B-success.svg)](https://huggingface.co/wanx)
[![Version](https://img.shields.io/badge/version-3.1.8-blue.svg)](CHANGELOG.md)

---

## 🎯 Vue d'ensemble

GEGM MotionLab transforme vos images statiques en **cinemagraphs professionnels** (vidéos en boucle) grâce aux modèles IA **WAN 2.2** de dernière génération.

**Fonctionnalités clés :**
- 🎨 Interface web moderne (Flask)
- 🧠 2 modèles IA (5B/14B) sélectionnés automatiquement
- ⚡ Presets intelligents + 12 paramètres avancés
- 🎬 Qualité 720p à 4K avec boucles fluides
- ☁️ Déploiement local (Docker) ou cloud (RunPod)
- 💾 Gestion modèles automatisée (OwnCloud + rclone)

---

## 🚀 Installation Rapide

### Option 1: Local avec Docker Compose

```bash
# Cloner le projet
git clone <repo>
cd GEGM_MotionLab

# Configuration (optionnelle pour local)
cp .env.example .env

# Démarrer
docker-compose up -d

# Accéder
open http://localhost:5000
```

**Prérequis :** Docker 20.10+, GPU NVIDIA 48GB+ VRAM

### Option 2: Cloud sur RunPod

```bash
# 1. Préparer modèles localement
./scripts/setup_wan22_native.sh wan2.2-ti2v-5b
make full-workflow-5b

# 2. Builder et déployer image Docker
make runpod-deploy

# 3. Créer Pod sur RunPod
# GPU: RTX 6000 Ada (5B) ou H100 SXM (14B)
# Image: arnaudboy/comfy_img_to_loop:latest
# Port: 5000
```

**Pour plus de détails :** Voir [README_RUNPOD.md](README_RUNPOD.md)

---

## 🏗️ Stack Technique

| Composant | Technologie | Version |
|-----------|-------------|---------|
| **Backend** | Python + Flask | 3.11 + 3.0+ |
| **IA Engine** | ComfyUI + WAN 2.2 | Latest + 5B/14B |
| **Deep Learning** | PyTorch + CUDA | 2.10+ + 12.8+ |
| **Container** | Docker multi-arch | 20.10+ |
| **Storage** | OwnCloud + rclone | - |
| **GPU** | NVIDIA | 48GB+ VRAM |

---

## 📁 Structure Projet

```
GEGM_MotionLab/
├── web_interface/          # Flask app
│   ├── app.py
│   ├── routes.py
│   └── jobs.py
│
├── workflows/              # ComfyUI workflows
│   ├── workflow_manager.py
│   └── templates/
│       ├── wan22_i2v.json           # ≤720p
│       └── wan22_with_upscale.json  # >720p
│
├── src/                    # Core modules
│   ├── comfyui_client.py
│   ├── owncloud_uploader.py
│   └── logger.py
│
├── scripts/                # Utilitaires
│   ├── setup_wan22_native.sh         # Download + fusion + vérif
│   ├── merge_safetensors.py          # Fusion 3→1 fichier (v3.1.8)
│   ├── verify_diffusion_model.py     # Vérif diffusion (v3.1.8)
│   ├── verify_t5_integrity.py        # Vérif T5
│   ├── convert_vae_channels.py       # VAE 96→48ch
│   └── split_and_upload.py           # Découpe + upload
│
├── docker/
│   ├── Dockerfile
│   ├── docker-compose.yml
│   └── docker-entrypoint.sh
│
├── requirements.txt        # Dépendances AVEC PyTorch (local)
├── requirements-base.txt   # Dépendances SANS PyTorch (Docker)
└── Makefile               # 70+ commandes automation
```

---

## ⚙️ Configuration

### Variables d'environnement (.env)

```env
# Flask
FLASK_HOST=0.0.0.0
FLASK_PORT=5000

# ComfyUI
COMFYUI_HOST=127.0.0.1
COMFYUI_PORT=8188
COMFYUI_TIMEOUT=300

# OwnCloud (requis pour RunPod)
OWNCLOUD_SERVER_URL=https://your-server.com
OWNCLOUD_USERNAME=your-username
OWNCLOUD_PASSWORD=your-password
OWNCLOUD_MODEL_FOLDER=/GEGM_ComfyUI/Models

# GPU
CUDA_VISIBLE_DEVICES=0
LOG_LEVEL=INFO
```

### Dépendances Python

**⚠️ IMPORTANT - 2 fichiers distincts :**

| Fichier | Contenu | Usage |
|---------|---------|-------|
| **requirements.txt** | AVEC PyTorch | Développement local |
| **requirements-base.txt** | SANS PyTorch | Docker/RunPod |

**Raison :** Le Dockerfile installe PyTorch optimisé pour le GPU cible.

**Installation :**
```bash
# Local
pip install -r requirements.txt

# Docker (automatique via Dockerfile)
# pip install -r requirements-base.txt
```

---

## 🧠 Modèles WAN 2.2

| Modèle | Taille | Résolution | GPU | Temps | Coût RunPod |
|--------|--------|------------|-----|-------|-------------|
| **5B** | 13 GB | ≤1280x720 | RTX 6000 Ada 48GB | ~5 min | $0.064/vidéo |
| **14B** | 28 GB | 4K | H100 SXM 80GB | ~8 min | $0.36/vidéo |

**Sélection automatique :**
- Image ≤1280x720 → WAN 2.2 5B
- Image >1280x720 → WAN 2.2 14B

---

## ⚡ Points Critiques (v3.1.8)

### 1. Configuration VAE

**Problème :** VAE original = 96 canaux, ComfyUI attend 48 canaux

**Solution :** Conversion automatique via `convert_vae_channels.py`
```bash
python scripts/convert_vae_channels.py wan2.2-ti2v-5b
# Réduit encoder/decoder: 96ch → 48ch
```

---

### 2. Fusion Safetensors (CRITIQUE)

**Problème :** ComfyUI ne supporte PAS les modèles sharded (3 fichiers)

**Solution :** Fusionner AVANT upload via `merge_safetensors.py`
```bash
python scripts/merge_safetensors.py wan2.2-ti2v-5b
# 3 fichiers → diffusion_pytorch_model.safetensors (18.63 GB)
```

**Fichiers supprimés après fusion :**
- `diffusion_pytorch_model-00001-of-00003.safetensors`
- `diffusion_pytorch_model-00002-of-00003.safetensors`
- `diffusion_pytorch_model-00003-of-00003.safetensors`
- `diffusion_pytorch_model.safetensors.index.json`

---

### 3. Double Vérification (CRITIQUE)

**⚠️ 2 fichiers distincts avec clés différentes :**

| Fichier | Clés | Script |
|---------|------|--------|
| **Modèle diffusion** | `blocks.*.ffn.0.weight` | `verify_diffusion_model.py` |
| **T5 Encoder** | `blocks.*.ffn.{gate\|fc1\|fc2}.0.weight` | `verify_t5_integrity.py` |

**Vérification :**
```bash
# Modèle de diffusion fusionné
python scripts/verify_diffusion_model.py wan2.2-ti2v-5b

# T5 Encoder
python scripts/verify_t5_integrity.py wan2.2-ti2v-5b
```

---

## 🔄 Workflow Complet (v3.1.8)

### Local (avant upload)

```bash
# 1. Téléchargement + Fusion + Vérifications
./scripts/setup_wan22_native.sh wan2.2-ti2v-5b
# → Download HF (23 fichiers)
# → Fusion safetensors (3 → 1)
# → Vérif modèle diffusion
# → Vérif T5 Encoder
# → Suppression fichiers sharded (économie 18.5 GB)

# 2. Conversion VAE + Upload OwnCloud
make full-workflow-5b
# → Conversion VAE 96ch → 48ch
# → Découpe en chunks (10 diffusion + 6 T5)
# → Suppression originaux (économie ~31 GB)
# → Upload OwnCloud (35 fichiers, ~31.8 GB)
# → Vérification upload
# → Nettoyage local
```

### Pod RunPod (démarrage automatique)

```bash
# Automatique via docker-entrypoint.sh
1. Download chunks depuis OwnCloud
2. Reconstitution modèles
3. Création symlink T5
4. Démarrage ComfyUI
5. Health check (180s)
6. Flask app ready
```

---

## 📊 API REST

| Endpoint | Méthode | Description |
|----------|---------|-------------|
| `/api/generate` | POST | Lancer génération |
| `/api/jobs/<job_id>` | GET | Statut job |
| `/api/download/<job_id>` | GET | Télécharger vidéo |
| `/health` | GET | Health check |

---

## 🛠️ Commandes Makefile

### Développement
```bash
make up          # Démarrer services
make down        # Arrêter services
make logs        # Voir logs
make rebuild     # Rebuild images
```

### Modèles
```bash
make download-models       # Download depuis HF
make full-workflow-5b      # Workflow complet 5B
make full-workflow-14b     # Workflow complet 14B
make rclone-list          # Lister OwnCloud
make models-deep-clean    # Nettoyer modèles locaux
```

### Déploiement
```bash
make runpod-deploy        # Build multi-arch + push
make runpod-deploy-quick  # Build AMD64 uniquement
```

---

## 🐛 Troubleshooting Rapide

### ComfyUI ne démarre pas
```bash
# Vérifier logs
docker-compose logs comfyui

# Vérifier symlink T5
ls -la /workspace/.../text_encoders/t5/
```

### Erreur VAE
**Symptôme :** `RuntimeError: Expected 48 channels, got 96`
**Solution :** Assurer VAE converti (48ch)

### VRAM insuffisante
**Solutions :**
- Réduire steps (20→15)
- Réduire résolution image
- Choisir GPU supérieur

---

## 📚 Documentation Complète

- **[README_DOCKER.md](README_DOCKER.md)** - Guide Docker (architecture, build, volumes)
- **[README_RUNPOD.md](README_RUNPOD.md)** - Guide RunPod (déploiement cloud, GPU, coûts)
- **[CLAUDE.md](CLAUDE.md)** - Guide développeur (architecture interne)

---

## 🔗 Ressources

- [ComfyUI](https://github.com/comfyanonymous/ComfyUI) - Workflow engine
- [ComfyUI-WanVideoWrapper](https://github.com/kijai/ComfyUI-WanVideoWrapper) - WAN 2.2 nodes
- [WAN 2.2 sur HuggingFace](https://huggingface.co/wanx) - Modèles IA
- [RunPod](https://runpod.io) - GPU cloud platform

---

## 📝 Notes

**Version actuelle :** 3.1.8 (2025-11-14)
**Status :** Production Ready
**Dernière validation :** Workflow complet testé localement ✅

**Points d'attention :**
- VAE : Toujours 48 canaux (conversion automatique)
- Fusion : AVANT upload (pas sur Pod)
- Vérifications : 2 scripts séparés (diffusion + T5)
- Symlinks : Chemins absolus (T5 Encoder)
- GPU : 48GB+ VRAM minimum

**Architecture :**
- Flask (5000) → Interface web
- ComfyUI (8188) → Engine génération IA
- WebSocket → Communication Flask ↔ ComfyUI
- OwnCloud + rclone → Stockage modèles
