# GEGM MotionLab

**Studio professionnel de cinemagraphs propulsé par WAN 2.2**

[![Python](https://img.shields.io/badge/python-3.11-blue.svg)](https://python.org)
[![Docker](https://img.shields.io/badge/docker-ready-green.svg)](https://docker.com)
[![ComfyUI](https://img.shields.io/badge/comfyui-latest-blueviolet.svg)](https://github.com/comfyanonymous/ComfyUI)
[![WAN 2.2](https://img.shields.io/badge/WAN%202.2-5B%20%2F%2014B%20MoE-success.svg)](https://huggingface.co/Wan-AI)
[![Version](https://img.shields.io/badge/version-4.3.0-blue.svg)](CHANGELOG.md)

---

## Vue d'ensemble

GEGM MotionLab transforme vos images statiques en **cinemagraphs professionnels** grâce aux modèles IA WAN 2.2.

**Fonctionnalités :**
- Interface web Flask moderne
- 2 modèles IA : 5B (standard) et 14B MoE (premium)
- Paramètres avancés : motion, consistance, boucles fluides
- Qualité 720p à 4K avec upscaling adaptatif
- Déploiement Docker local ou cloud (RunPod)

---

## Installation Rapide

### Docker Compose (Local)

```bash
git clone <repo>
cd GEGM_MotionLab
cp .env.example .env
docker-compose up -d
open http://localhost:5000
```

**Prérequis :** Docker 20.10+, GPU NVIDIA 48GB+ VRAM

### RunPod (Cloud)

```bash
# Préparer modèles
./scripts/setup_wan22_native.sh wan2.2-ti2v-5b
make full-workflow-5b

# Déployer
make runpod-deploy
```

Voir [README_RUNPOD.md](README_RUNPOD.md) pour le guide complet.

---

## Stack Technique

| Composant | Technologie |
|-----------|-------------|
| Backend | Python 3.11 + Flask 3.0 |
| IA Engine | ComfyUI + WAN 2.2 (5B/14B MoE) |
| Deep Learning | PyTorch 2.6 + CUDA 12.8 |
| Container | Docker multi-arch |
| Storage | OwnCloud + rclone |

---

## Modèles WAN 2.2

| Modèle | Taille | GPU Recommandés | Temps |
|--------|--------|-----------------|-------|
| **5B** | 9.3 GB | RTX 6000 Ada, L40, L40S (ou 48GB+ VRAM) | ~5 min |
| **14B MoE** | 2×28.6 GB | RTX Pro 6000, RTX Pro 6000 WK, H100 SXM (ou 80GB+ VRAM) | ~8 min |

**Architecture 14B MoE :** 2 experts (high_noise + low_noise) avec switching boundary=0.9

---

## Structure Projet

```
GEGM_MotionLab/
├── web_interface/          # Flask app (routes.py, app.py, jobs.py)
├── workflows/              # ComfyUI workflows + templates
│   ├── workflow_manager.py
│   └── templates/          # wan22_{5b|14b}_{i2v|with_upscale}.json
├── src/                    # Core modules
├── scripts/                # Utilitaires (setup, download, verify)
├── docker/                 # Dockerfile, docker-compose.yml
├── requirements.txt        # Dépendances AVEC PyTorch (local)
└── requirements-base.txt   # Dépendances SANS PyTorch (Docker)
```

---

## Configuration

### Variables d'environnement (.env)

```env
# Flask
FLASK_HOST=0.0.0.0
FLASK_PORT=5000

# ComfyUI
COMFYUI_HOST=127.0.0.1
COMFYUI_PORT=8188

# OwnCloud (requis RunPod)
OWNCLOUD_SERVER_URL=https://your-server.com
OWNCLOUD_USERNAME=your-username
OWNCLOUD_PASSWORD=your-password
OWNCLOUD_MODEL_FOLDER=/GEGM_ComfyUI/Models
```

---

## API REST

| Endpoint | Méthode | Description |
|----------|---------|-------------|
| `/api/generate` | POST | Lancer génération |
| `/api/jobs/<job_id>` | GET | Statut job |
| `/api/download/<job_id>` | GET | Télécharger MP4 |
| `/api/model-info` | GET | Info modèle actif |
| `/health` | GET | Health check |

---

## Commandes Makefile

```bash
# Développement
make up              # Démarrer services
make down            # Arrêter services
make logs            # Voir logs

# Modèles
make full-workflow-5b   # Workflow complet 5B
make full-workflow-14b  # Workflow complet 14B

# Déploiement
make runpod-deploy      # Build multi-arch + push
```

---

## Troubleshooting

| Erreur | Solution |
|--------|----------|
| CUDA out of memory | Réduire résolution ou steps |
| VAE 48/96 channels | Vérifier VAE correct pour modèle |
| ComfyUI timeout | Vérifier modèles présents |

---

## Documentation

- [README_DOCKER.md](README_DOCKER.md) - Guide Docker
- [README_RUNPOD.md](README_RUNPOD.md) - Guide RunPod
- [CLAUDE.md](CLAUDE.md) - Guide développeur

---

## Ressources

- [ComfyUI](https://github.com/comfyanonymous/ComfyUI)
- [ComfyUI-WanVideoWrapper](https://github.com/kijai/ComfyUI-WanVideoWrapper)
- [ComfyUI-WanMoeKSampler](https://github.com/stduhpf/ComfyUI-WanMoeKSampler)
- [WAN 2.2 HuggingFace](https://huggingface.co/Wan-AI)
- [RunPod](https://runpod.io)

---

**Version:** 4.3.0 | **Status:** Production Ready | **Date:** 2026-01-22
