# GEGM MotionLab

**Studio professionnel de cinemagraphs propulsé par WAN 2.2 & LTX 2.3**

[![Python](https://img.shields.io/badge/python-3.11-blue.svg)](https://python.org)
[![Docker](https://img.shields.io/badge/docker-ready-green.svg)](https://docker.com)
[![ComfyUI](https://img.shields.io/badge/comfyui-latest-blueviolet.svg)](https://github.com/comfyanonymous/ComfyUI)
[![WAN 2.2](https://img.shields.io/badge/WAN%202.2-5B%20%2F%2014B%20MoE-success.svg)](https://huggingface.co/Wan-AI)
[![LTX 2.3](https://img.shields.io/badge/LTX%202.3-22B%20DiT-orange.svg)](https://huggingface.co/Lightricks)
[![Version](https://img.shields.io/badge/version-5.1.0-blue.svg)](CHANGELOG.md)

---

## Vue d'ensemble

GEGM MotionLab transforme vos images statiques en **cinemagraphs professionnels** grâce à 3 modèles IA.

**Fonctionnalités :**
- Interface web Flask moderne
- 3 modèles IA : WAN 2.2 (5B, 14B MoE) et LTX 2.3 (22B)
- Paramètres avancés : motion, consistance, boucles fluides
- Qualité 720p à 4K avec upscaling adaptatif
- Pipeline résolution model-agnostic piloté par registre YAML
- Déploiement Docker local ou cloud (RunPod)

---

## Installation Rapide

### Docker Compose (Local)

```bash
git clone https://github.com/KaRn1zC/GEGM_MotionLab.git
cd GEGM_MotionLab
cp .env.example .env
docker-compose up -d
open http://localhost:5000
```

**Prérequis :** Docker 20.10+, GPU NVIDIA 48GB+ VRAM

---

## Stack Technique

| Composant     | Technologie                                        |
| ------------- | -------------------------------------------------- |
| Backend       | Python 3.11 + Flask 3.0                            |
| IA Engine     | ComfyUI + WAN 2.2 (5B/14B MoE) + LTX 2.3 (22B DiT) |
| Deep Learning | PyTorch 2.6 + CUDA 12.8                            |
| Container     | Docker (AMD64)                                     |
| Storage       | OwnCloud + rclone                                  |
| Config        | Registre modèles YAML (model-agnostic)             |

---

## Modèles

### WAN 2.2

| Modèle      | Taille    | GPU Recommandés                 | Temps   |
| ----------- | --------- | ------------------------------- | ------- |
| **5B**      | 9.3 GB    | RTX 6000 Ada, L40, L40S (48GB+) | ~10 min |
| **14B MoE** | 2×28.6 GB | RTX Pro 6000, H100 SXM (80GB+)  | ~28 min |

### LTX 2.3

| Modèle  | Taille  | GPU Recommandés                | Temps   |
| ------- | ------- | ------------------------------ | ------- |
| **22B** | 46.1 GB | RTX Pro 6000, H100 SXM (80GB+) | ~13 min |

---

## Structure Projet

```
GEGM_MotionLab/
├── web_interface/          # Flask app (routes.py, app.py, jobs.py, templates/)
├── workflows/              # ComfyUI workflows + templates
│   ├── workflow_manager.py
│   └── templates/          # 6 JSON (wan22 5b/14b + ltx23, chacun normal + upscale)
├── src/                    # Core modules (comfyui_client, model_registry, owncloud, logger)
├── scripts/                # Utilitaires (setup, download, verify)
├── config/                 # model_registry.yaml, owncloud.yaml, logging.yaml (ref)
├── Dockerfile              # Single-stage CUDA 12.8 (PYTHONPATH=/workspace)
└── requirements.txt        # Dépendances Python (sans PyTorch, installé dans Docker)
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

| Endpoint                 | Méthode | Description       |
| ------------------------ | ------- | ----------------- |
| `/api/generate`          | POST    | Lancer génération |
| `/api/jobs/<job_id>`     | GET     | Statut job        |
| `/api/download/<job_id>` | GET     | Télécharger MP4   |
| `/api/model-info`        | GET     | Info modèle actif |
| `/health`                | GET     | Health check      |

---

## Commandes Makefile

```bash
# Développement
make up                    # Démarrer services
make down                  # Arrêter services
make logs                  # Voir logs

# Workflow modèle (download → upload OwnCloud → clean)
make workflow MODEL=<nom>  # Workflow complet générique
make workflow-5b           # Alias WAN 5B
make workflow-14b          # Alias WAN 14B
make workflow-ltx           # Alias LTX 2.3 22B

# Workflows séquentiels
make workflow-wan-all      # WAN 14B puis 5B
make workflow-all          # Tous les modèles (3)
```

---

## Troubleshooting

| Erreur                 | Solution                         |
| ---------------------- | -------------------------------- |
| CUDA out of memory     | Réduire résolution ou steps      |
| VAE 48/96/128 channels | Vérifier VAE correct pour modèle |
| ComfyUI timeout        | Vérifier modèles présents        |

---

## Ressources

- [ComfyUI](https://github.com/comfyanonymous/ComfyUI)
- [ComfyUI-WanVideoWrapper](https://github.com/kijai/ComfyUI-WanVideoWrapper) (WAN 5B)
- [ComfyUI-WanMoeKSampler](https://github.com/stduhpf/ComfyUI-WanMoeKSampler) (WAN 14B)
- [ComfyUI-LTXVideo](https://github.com/Lightricks/ComfyUI-LTXVideo) (LTX 2.3)
- [WAN 2.2 HuggingFace](https://huggingface.co/Wan-AI)
- [LTX 2.3 HuggingFace](https://huggingface.co/Lightricks)
- [RunPod](https://runpod.io)

---

**Version:** 5.1.0 | **Status:** Production Ready | **Date:** 2026-03-17
