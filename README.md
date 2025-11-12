# 🎬 GEGM MotionLab 🔬

**Studio professionnel de création de cinemagraphs propulsé par l'IA WAN 2.2**

> Transformez vos images statiques en boucles vidéo fluides avec l'intelligence artificielle.

[![License](https://img.shields.io/badge/license-Private-red.svg)](LICENSE)
[![Python](https://img.shields.io/badge/python-3.11-blue.svg)](https://python.org)
[![Docker](https://img.shields.io/badge/docker-ready-green.svg)](https://docker.com)
[![ComfyUI](https://img.shields.io/badge/comfyui-latest-blueviolet.svg)](https://github.com/comfyanonymous/ComfyUI)
[![WAN 2.2](https://img.shields.io/badge/WAN%202.2-production%20ready-green.svg)](https://huggingface.co/wanx)

---

## 🚀 Fonctionnalités

### Interface Professionnelle

- **🎨 Interface GEGM MotionLab** : Interface web moderne et intuitive basée sur Flask
- **🎛️ Paramètres avancés** : Contrôle total avec 12+ paramètres et tooltips éducatifs
- **⚡ Presets intelligents** : 4 configurations prédéfinies (Qualité Max, Équilibré, Rapide, Naturel)
- **🎲 Gestion du Seed** : Reproductibilité garantie des générations

### IA de Pointe

- **🧠 WAN 2.2 5B/14B** : Modèles state-of-the-art image-to-video
  - **5B**: ~13 GB, ~5 min/vidéo (RTX 6000 Ada), $0.064/cinemagraph
  - **14B**: ~28 GB, ~8 min/vidéo (H100 SXM), $0.36/cinemagraph
- **📊 Analyse automatique** : Détection résolution et sélection modèle approprié
- **🎬 Qualité professionnelle** : 720p à 4K avec boucles fluides et anti-flickering

### Architecture Robuste

- **☁️ Déploiement cloud** : RunPod avec GPU professionnel (RTX 6000 Ada ou H100 SXM)
- **🐳 Containerisation** : Docker multi-architecture (AMD64 + ARM64)
- **💾 Gestion modèles** : OwnCloud avec découpe chunks et reconstitution automatique
- **📤 Upload manuel** : Contrôle total des sauvegardes via boutons interface

---

## 📋 Table des matières

1. [Installation rapide](#installation-rapide)
2. [Prérequis](#prérequis)
3. [Stack technologique](#stack-technologique)
4. [Structure du projet](#structure-du-projet)
5. [Configuration VAE](#configuration-vae)
6. [Modèles IA](#modèles-ia)
7. [Interface web](#interface-web)
8. [Workflows ComfyUI](#workflows-comfyui)
9. [Déploiement](#déploiement)
10. [Configuration](#configuration)
11. [Utilisation](#utilisation)
12. [Troubleshooting](#troubleshooting)
13. [Ressources](#ressources)

---

## Installation rapide

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

### Local avec Docker Compose

```bash
# Cloner le projet
git clone <repo>
cd GEGM_MotionLab

# Configurer OwnCloud (optional pour local)
cp .env.example .env
# Éditer .env avec vos credentials OwnCloud (optionnel)

# Démarrer services
docker-compose up -d

# Accéder interface
open http://localhost:5000
```

### Cloud sur RunPod

```bash
# Préparer modèles (voir README_RUNPOD.md)
make sequential-upload-workflow

# Builder image Docker
make runpod-deploy

# Créer Pod RunPod (voir README_RUNPOD.md pour détails)
# 1. Aller https://runpod.io
# 2. Déployer Pod avec image: arnaudboy/comfy_img_to_loop:latest
# 3. 15-20 minutes puis interface prête!
```

---

## Prérequis

### Environnement local

- **GPU NVIDIA** : 40+ GB VRAM (48 GB minimum recommandé)
- **CUDA** : 12.8+
- **Docker** : 20.10+ avec BuildX
- **Docker Compose** : 2.0+
- **Python** : 3.11 (si installation native)
- **RAM** : 8 GB minimum

### Services requis

- **OwnCloud** : Stockage modèles + résultats (voir `.env.example`)
- **RunPod Account** : Pour déploiement cloud (optionnel)
- **rclone** : Synchronisation modèles (voir setup section)

### Éducation préalable

Familiarité recommandée avec:
- Docker et conteneurs
- Ligne de commande (bash/zsh)
- Concepts IA/diffusion (optionnel)
- RunPod UI (pour déploiement cloud)

---

## Stack technologique

| Catégorie | Composant | Version | Rôle |
|-----------|-----------|---------|------|
| **Runtime** | Python | 3.11 | Langage principal |
| **Web** | Flask | 3.0+ | Backend API + interface |
| **IA** | ComfyUI | Latest | Node-based workflow engine |
| **Modèles** | WAN 2.2 5B/14B | Latest | Génération image-to-video |
| **Vision** | CLIP Vision | - | Extraction features images |
| **Deep Learning** | PyTorch | 2.0+ | Framework CUDA 12.8+ |
| **Container** | Docker | 20.10+ | Multi-architecture |
| **Sync** | rclone | Latest | OwnCloud sync |
| **GPU** | NVIDIA CUDA | 12.8+ | Compute backend |

---

## Structure du projet

```
GEGM_MotionLab/
│
├── 📁 docker/
│   ├── Dockerfile                    # Build image multi-stage
│   ├── docker-compose.yml            # Services local/prod
│   ├── docker-compose.runpod.yml     # Overrides RunPod
│   └── docker-entrypoint.sh          # Démarrage Pod
│
├── 📁 web_interface/
│   ├── app.py                        # App Flask principale
│   ├── routes.py                     # Endpoints API REST
│   ├── jobs.py                       # Queue asynchrone
│   ├── 📁 templates/
│   │   ├── base.html
│   │   └── index.html                # Interface GEGM MotionLab
│   └── 📁 static/
│       ├── 📁 css/
│       │   └── style.css
│       └── 📁 js/
│           └── app.js
│
├── 📁 workflows/
│   ├── workflow_manager.py           # Orchestration
│   └── 📁 templates/
│       ├── wan22_i2v.json            # Workflow standard
│       └── wan22_with_upscale.json   # Workflow avec upscale
│
├── 📁 src/
│   ├── 📁 models/                    # Modèles de données
│   │   ├── __init__.py
│   │   └── owncloud_models.py        # OwnCloudConfig, VideoMetadata (résout imports circulaires)
│   ├── logger.py                     # Logging Loguru
│   ├── comfyui_client.py             # WebSocket ComfyUI
│   ├── owncloud_uploader.py          # Upload OwnCloud
│   ├── owncloud_config.py            # Gestionnaire config OwnCloud
│   └── config.py                     # Config app
│
├── 📁 scripts/
│   ├── setup_wan22_native.sh         # Download HF
│   ├── upload_models_to_owncloud.py  # Upload + VAE convert
│   ├── download_models_from_owncloud.py # Download, auto-reconstitue chunks, verify
│   └── reassemble_models.sh          # Reconstitue safetensors depuis chunks
│
├── 📁 config/
│   ├── model_versions.yaml           # URLs modèles
│   └── owncloud.yaml                 # Config OwnCloud
│
├── Dockerfile                        # Production multi-arch
├── docker-compose.yml                # Dev
├── Makefile                          # Automation (70+ targets)
├── requirements.txt                  # ~200 dependencies
├── README.md                         # Ce fichier
├── README_DOCKER.md                  # Guide Docker
└── README_RUNPOD.md                  # Guide RunPod
```

---

## Configuration VAE

### Le problème

Le modèle WAN 2.2 original inclut `Wan2.2_VAE.pth` avec architecture **96 canaux**, incompatible avec le node ComfyUI `WanVideoVAELoader` qui attend **48 canaux**.

**Erreur bloquante:**
```
RuntimeError: Given groups=1, weight of size [96, 48, 3, 3], 
expected input[1, 48, 60, 90] to have 96 channels, but got 48 channels instead
```

### La solution (Novembre 2025)

La solution implémentée en production consiste à **convertir le VAE de 96 à 48 canaux** via script intégré dans le pipeline upload OwnCloud.

**Étapes:**

1. **Conversion** : Script `convert_vae_96_to_48()` dans `upload_models_to_owncloud.py`
   - Réduit `encoder.conv_in.weight`: [96, 48, 3, 3] → [48, 48, 3, 3]
   - Réduit `decoder.conv_out.weight`: [96, 3, 3, 3] → [48, 3, 3, 3]
   - Autres poids: conservés intacts

2. **Suppression original** : VAE non modifié (96 canaux) supprimé pour éviter duplication

3. **Upload OwnCloud** : VAE converti inclus (pas d'exclusion)

4. **Workflow** : Utilise nodes corrects:
   ```json
   {
     "3": {
       "class_type": "WanVideoVAELoader",
       "inputs": {
         "model_name": "Wan2.2_VAE.pth",
         "precision": "bf16"
       }
     }
   }
   ```

5. **Symlink** : `/models/vae/Wan2.2_VAE.pth` créé au démarrage Pod

**Résultat:** ✅ Génération vidéo fonctionnelle sans erreurs VAE

---

## Modèles IA

### WAN 2.2 5B (Production Standard)

| Propriété | Valeur |
|-----------|--------|
| **Nom** | `wan2.2-ti2v-5b` |
| **Taille** | ~13 GB (3 fichiers .safetensors) |
| **Paramètres** | 5 milliards |
| **Résolution max** | 1280x720 (HD) |
| **GPU recommandé** | RTX 6000 Ada 48GB ⭐ |
| **Temps génération** | ~5 min/cinemagraph |
| **Coût RunPod** | $0.77/h (~$0.064/pièce) |

**Cas d'usage:**
- Tests rapides et itérations
- Production volume élevé avec contrainte budgétaire
- Animations résolutions jusqu'à HD

### WAN 2.2 14B (Qualité Premium)

| Propriété | Valeur |
|-----------|--------|
| **Nom** | `wan2.2-i2v-a14b` |
| **Taille** | ~28 GB (3 fichiers .safetensors) |
| **Paramètres** | 14 milliards |
| **Résolution max** | 4K (3840x2160) |
| **GPU recommandé** | H100 SXM 80GB ⭐ |
| **Temps génération** | ~8 min/cinemagraph |
| **Coût RunPod** | $2.69/h (~$0.36/pièce) |

**Cas d'usage:**
- Production premium qualité maximale
- Résolutions 4K
- Animations complexes avec mouvement subtil

### Sélection automatique

Le système détecte automatiquement le modèle approprié selon la résolution uploadée:

```
Résolution image ≤ 1280x720 → WAN 2.2 5B + wan22_i2v.json
Résolution image > 1280x720 → WAN 2.2 14B + wan22_with_upscale.json
```

---

## Interface web

### Architecture

```
http://localhost:5000 ou https://pod-id-5000.proxy.runpod.net
│
├─ Upload Image
│  ├─ Drag & drop ou clic
│  └─ Formats: JPG, PNG, WebP
│
├─ Configuration Paramètres
│  ├─ 4 Presets rapides
│  │  ├─ 💎 Qualité Max (30 steps, 8.0 CFG, $$$)
│  │  ├─ ⚖️ Équilibré (20 steps, 7.5 CFG) ← Recommandé
│  │  ├─ ⚡ Rapide (15 steps, 7.0 CFG)
│  │  └─ 🍃 Naturel (20 steps, 6.0 CFG)
│  │
│  └─ 12+ Paramètres avancés (modifiables individuellement)
│     ├─ Diffusion: Steps, CFG Scale, Denoise
│     ├─ Mouvement: Intensity, Noise Level, Loop Smoothness, Temporal Consistency
│     └─ Experts: Seed, Motion Area, Color Preservation, Frame Blending
│
├─ Génération
│  ├─ Bouton: 🎬 Générer le Cinemagraph
│  └─ Barre progression avec étapes (5-10 min)
│
└─ Résultat
   ├─ ▶️ Aperçu vidéo
   ├─ 📋 Seed utilisé (reproductibilité)
   └─ Actions:
      ├─ ⬇️ Télécharger (backup local)
      ├─ ☁️ Sauvegarder (upload OwnCloud manuel)
      ├─ 🗑️ Supprimer (libérer espace)
      └─ 🔄 Nouvelle (génération suivante)
```

### Paramètres avancés

| Paramètre | Plage | Recommandé | Description |
|-----------|-------|-----------|-------------|
| **Steps** | 5-100 | 20-25 | Itérations diffusion (qualité vs temps) |
| **CFG Scale** | 1-20 | 7-8 | Fidélité image source (1=créatif, 20=fidèle) |
| **Denoise** | 0-100% | 60-80% | Intensité transformation |
| **Motion Intensity** | Subtil/Modéré/Fort/Extrême | Modéré | Quantité mouvement global |
| **Noise Level** | Low/Medium/High | Medium | Détails stochastiques |
| **Loop Smoothness** | None/Basic/Advanced | Advanced | Continuité boucle vidéo |
| **Temporal Consistency** | 0-100% | 70-85% | Anti-flickering |
| **Seed** | -1 ou nombre | -1 | -1=aléatoire, nombre=reproductible |
| **Motion Area** | Full/Center/Edges/Bottom/Top | Full | Zone de mouvement |
| **Color Preservation** | 0-100% | 80-95% | Fidélité couleurs originales |
| **Frame Blending** | 1-7 | 3-4 | Interpolation temporelle |

### Endpoints API REST

**POST `/api/generate`** - Lancer génération
```json
{
  "preset": "balanced",
  "steps": 20,
  "cfg_scale": 7.5
}
```

**GET `/api/jobs/<job_id>`** - Statut génération
- Statuts: `queued`, `processing`, `completed`, `failed`

**GET `/api/download/<job_id>`** - Télécharger vidéo MP4

**POST `/api/upload_owncloud/<job_id>`** - Upload manuel OwnCloud

**GET `/health`** - Health check API

---

## Workflows ComfyUI

### WAN 2.2 Standard (wan22_i2v.json)

**Utilisation:** Images sans upscale nécessaire

**Nodes principaux:**
1. **CheckpointLoader** → Charge modèle WAN 2.2 (5B ou 14B)
2. **CLIPVisionLoader** → Extraction features CLIP
3. **WanVideoVAELoader** → VAE 48 canaux converti (bf16)
4. **WanVideoImageToVideoLatentProcessor** → Image → Latents
5. **WanVideoSampler** → Diffusion sampling (N steps)
6. **WanVideoDecode** → Latents → Pixels vidéo
7. **VHS_VideoCombine** → Encodage H.264 MP4 @ 24fps

**Output:** Vidéo MP4 1280x720 ou 1920x1080

### WAN 2.2 avec Upscale (wan22_with_upscale.json)

**Utilisation:** Images nécessitant upscale

**Étapes supplémentaires après encodage:**
- **Résolution < 720p** → RealESRGAN x4 upscaler (480p → 1920p)
- **Résolution ≥ 720p** → Pyramid Upscale multi-étapes (préservation détails)

**Output:** Vidéo MP4 4K ou ultra-HD

---

## Déploiement

### Local avec Docker Compose

Voir [README_DOCKER.md](README_DOCKER.md)

```bash
docker-compose up -d
# Interface: http://localhost:5000
```

### Cloud sur RunPod

Voir [README_RUNPOD.md](README_RUNPOD.md)

```bash
make sequential-upload-workflow    # Préparer modèles
make runpod-deploy                 # Builder image
# Puis créer Pod RunPod avec GPU recommandé
```

---

## Configuration

### Fichier .env

Copier et éditer:
```bash
cp .env.example .env
```

**Variables critiques:**

```env
# OwnCloud
OWNCLOUD_SERVER_URL=https://www.cloud-gegm.com
OWNCLOUD_USERNAME=your-username
OWNCLOUD_PASSWORD=your-password

# Flask
FLASK_HOST=0.0.0.0
FLASK_PORT=5000
FLASK_DEBUG=false

# ComfyUI
COMFYUI_HOST=127.0.0.1
COMFYUI_PORT=8188
COMFYUI_TIMEOUT=300

# GPU
CUDA_VISIBLE_DEVICES=0
LOG_LEVEL=INFO
```

### Configuration rclone (pour OwnCloud sync)

```bash
rclone config
# Name: owncloud
# Type: webdav
# URL: https://www.cloud-gegm.com/remote.php/dav
# User: your-username
# Password: your-password
```

---

## Utilisation

### Workflow complet

```
1. Accéder interface (localhost:5000 ou RunPod URL)
2. Upload image JPG/PNG/WebP
3. Sélectionner preset (recommandé: "Équilibré")
   OU ajuster paramètres avancés individuellement
4. Cliquer "🎬 Générer le Cinemagraph"
5. Attendre (3-8 min selon GPU et paramètres)
6. Résultat vidéo affichée
7. Actions:
   - ⬇️ Télécharger: Backup local
   - ☁️ Sauvegarder: Upload OwnCloud (manuel)
   - 🗑️ Supprimer: Libérer espace Pod
   - 🔄 Nouvelle: Prochaine génération
```

### Cas d'usage exemples

**Test rapide (Qualité Max déconseillé):**
```
Preset: Rapide → ~3 minutes → Vidéo test
```

**Production recommandée:**
```
Preset: Équilibré → ~5 minutes → Vidéo finalisée
```

**Premium (14B recommandé):**
```
Preset: Qualité Max → ~8 minutes → Meilleure qualité
```

---

## Troubleshooting

### Interface ne démarre pas

```bash
# Vérifier logs
docker-compose logs -f

# Vérifier ports disponibles
netstat -an | grep 5000

# Redémarrer services
docker-compose restart
```

### Erreur VRAM insuffisante

```
OutOfMemoryError: CUDA out of memory
```

**Solutions:**
- Réduire steps (20 → 15)
- Réduire resolution image source
- Passer à GPU supérieur (RunPod)
- Augmenter tile_size pour upscaling

### Erreur VAE (si ancien VAE)

```
RuntimeError: Expected 48 channels, got 96
```

**Solution:** Assurer VAE converti utilisé (setup_diffusion_models.sh)

### Modèles non trouvés

```bash
# Vérifier présence modèles locaux
ls -lh /workspace/comfyui/ComfyUI/models/checkpoints/

# Si manquants, télécharger depuis OwnCloud
python scripts/download_models_from_owncloud.py
```

### Génération très lente

**Vérifications:**
- GPU correctement utilisée: `nvidia-smi`
- Pas d'autres processes GPU: `nvidia-smi -l 1`
- Vérifier temperature GPU (< 75°C idéal)
- Vérifier VRAM utilisation (OK jusqu'à 95%)

### OwnCloud non accessible

```bash
# Vérifier configuration
cat .env | grep OWNCLOUD

# Tester rclone
rclone ls owncloud:/

# Vérifier credentials
rclone config show owncloud
```

---

## Ressources

### Documentation complète
- [GEGM_MotionLab_Documentation.md](GEGM_MotionLab_Documentation.md) - Documentation exhaustive (70+ KB)

### Guides spécifiques
- [README_DOCKER.md](README_DOCKER.md) - Déploiement local Docker
- [README_RUNPOD.md](README_RUNPOD.md) - Déploiement cloud RunPod

### Projets upstream
- [ComfyUI](https://github.com/comfyanonymous/ComfyUI) - Workflow engine
- [ComfyUI-WanVideoWrapper](https://github.com/kijai/ComfyUI-WanVideoWrapper) - WAN 2.2 nodes
- [WAN 2.2 (Hugging Face)](https://huggingface.co/wanx) - Modèles
- [OwnCloud](https://owncloud.com) - Cloud storage

### Support
- Logs détaillés: `/app/logs/` (Docker)
- Health check: `curl http://localhost:5000/health`
- Issues: Consulter logs avant issues

---

## Licence

🔒 Private - Usage interne uniquement

---

## Changelog

### Version 3.1.4 (12 Novembre 2025)
- ✅ Ajout vérification automatique de l'intégrité du T5 Encoder après téléchargement
- ✅ Script `verify_t5_integrity.py` : vérifie taille, format PyTorch, et clés critiques du modèle
- ✅ Intégration dans `setup_wan22_native.sh` : le workflow s'arrête si T5 corrompu/incomplet
- ✅ Protection contre l'upload de fichiers T5 corrompus sur OwnCloud

### Version 3.1.3 (12 Novembre 2025)
- ✅ Correction gestion T5 Encoder : symlink depuis dossier modèle WAN (inclus dans téléchargement)
- ✅ Suppression tentative téléchargement T5 depuis dossier inexistant sur OwnCloud
- ✅ T5 Encoder reconstitué automatiquement avec les chunks du modèle WAN

### Version 3.1.2 (12 Novembre 2025)
- ✅ Installation package `bc` dans Dockerfile (calculs de taille corrects)
- ✅ Reconstitution automatique des chunks AVANT vérification fichiers (`download_models_from_owncloud.py`)
- ✅ Amélioration vérification "modèle déjà présent" (vérifie 3 fichiers safetensors reconstitués)
- ✅ Ajout thread-safety lock à JobManager.get_job() (protection race condition)
- ✅ Génération de cinemagraphs fonctionnelle sur RunPod

### Version 3.1.1 (12 Novembre 2025)
- ✅ Extraction OwnCloudConfig en module séparé (`src/models/owncloud_models.py`)
- ✅ Correction race condition JobManager (thread-safety)
- ✅ Remplacement PyTorch pre-release par versions stables
- ✅ Élimination import circulaire owncloud_uploader/owncloud_config
- ✅ Architecture code améliorée (meilleure testabilité)

### Version 3.1.0 (7 Novembre 2025)
- ✅ Documentation consolidée et mise à jour
- ✅ VAE conversion 96→48 canaux en production
- ✅ Upload manuel OwnCloud (pas automatique)
- ✅ Interface avec 4 presets + 12+ paramètres avancés
- ✅ Workflows wan22_i2v.json et wan22_with_upscale.json

### Version 3.0.0 (29 Octobre 2025)
- Initial production release
- Support WAN 2.2 5B/14B
- Docker deployment
- OwnCloud integration

---

**Last Updated:** 12 novembre 2025
**Status:** ✅ Production Ready
**Version:** 3.1.2
**Maintained by:** GEGM MotionLab Team