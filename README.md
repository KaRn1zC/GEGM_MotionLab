# 🎬 GEGM MotionLab 🔬

**Studio professionnel de création de cinemagraphs propulsé par l'IA WAN 2.2**

> Transformez vos images statiques en boucles vidéo avec l'intelligence artificielle.

[![License](https://img.shields.io/badge/license-Private-red.svg)](LICENSE)
[![Python](https://img.shields.io/badge/python-3.11.13-blue.svg)](https://python.org)
[![Docker](https://img.shields.io/badge/docker-ready-green.svg)](https://docker.com)

---

## 🚀 Fonctionnalités

### Interface Professionnelle

- **🎨 Interface GEGM MotionLab** : Interface web moderne et intuitive
- **🎛️ Paramètres avancés** : Contrôle total avec tooltips éducatifs
- **⚡ Presets intelligents** : Qualité Max, Équilibré, Rapide, Naturel
- **🎲 Gestion du Seed** : Reproductibilité des générations

### IA de Pointe

- **🧠 WAN 2.2 5B/14B** : Modèles state-of-the-art pour image-to-video
- **📊 Analyse automatique** : Détection et optimisation des résolutions
- **🎬 Qualité professionnelle** : 720p à 4K avec boucles fluides

### Cloud & Stockage

- **☁️ Upload manuel OwnCloud** : Contrôle total sur la sauvegarde
- **🗑️ Gestion intelligente du stockage** : Suppression des tests ratés
- **💾 Téléchargement local** : Backup de sécurité intégré

### Déploiement

- **🐳 Docker multi-architecture** : AMD64 + ARM64 (Mac M1/M2/M3)
- **🚀 RunPod optimisé** : Image légère + modèles OwnCloud
- **📦 Modèles via OwnCloud** : Téléchargés au démarrage du Pod (~5-10 min)
- **🔧 Workflow automatisé** : rclone + découpe automatique des fichiers

---

## 📋 Prérequis

### Développement Local

- **Python** : 3.11.13
- **GPU** : 24GB+ VRAM recommandé (NVIDIA avec CUDA 12.8+)
- **Stockage** : 50GB pour modèles + workspace
- **OS** : Linux, macOS, Windows (WSL2)

### Production Cloud (RunPod)

- **GPU Recommandés** :
  - **WAN 2.2 5B** : RTX 6000 Ada 48GB ($0.77/h) ⭐ ou H100 SXM 80GB ($2.69/h)
  - **WAN 2.2 14B** : H100 SXM 80GB ($2.69/h) ⭐ ou H200 SXM 141GB ($3.99/h)
- **Stockage** : 10GB container disk minimum
- **Réseau** : Connexion stable pour téléchargement modèles OwnCloud

### Services Externes

- **OwnCloud** : Serveur pour sauvegarde (optionnel mais recommandé)
- **Docker Hub** : Compte pour push des images (production)

---

## 🛠 Installation

### 1. Cloner le Projet

```bash
git clone https://github.com/KaRn1zC/GEGM_MotionLab.git
cd GEGM_MotionLab
```

### 2. Configuration de l'Environnement Virtuel .venv

```bash

# Créer et activer l'environnement virtuel

python3.11 -m venv .venv
source .venv/bin/activate # Linux/Mac

# .venv\Scripts\activate # Windows

# Installer les dépendances

pip install -r requirements.txt
```

### 3. Création du fichier de variables d'environnement .env

Créer un fichier de variables d'environnements `.env` à la racine.
Se baser sur le contenu du fichier `.env.example` et remplacer les valeurs par ses propres informations.

---

## 🐳 Préparation de l'Image Docker pour RunPod

### Architecture : Image Légère + Modèles OwnCloud

**Stratégie adoptée :**
```
Image Docker (~8GB) OwnCloud (~37GB modèles)
                    ↓ ↓
RunPod Pod ← Télécharge modèles au démarrage
```

**Avantages :**

- ✅ Image Docker légère (~8GB vs 35-40GB)
- ✅ Build rapide (~10-15 min)
- ✅ Push Docker Hub rapide (~5-10 min)
- ✅ Flexibilité : choix du modèle 5B ou 14B au démarrage

**Inconvénient :**

- ⚠️ Téléchargement modèles au 1er démarrage Pod (~5-10 min)

---

### Workflow de Préparation Complet

#### Prérequis

- **rclone** configuré pour OwnCloud
- **Docker BuildX** pour multi-architecture
- **Espace disque** : 30GB minimum (workflow séquentiel)

#### Étape 1 : Configuration rclone (Une Fois)

Installer rclone
```
brew install rclone # macOS
```

OU
```
curl https://rclone.org/install.sh | sudo bash # Linux
```

Configurer rclone
```
rclone config
```

Name: owncloud
Type: webdav
URL: https://www.cloud-gegm.com/remote.php/dav
Vendor: owncloud
User: votre-username
Password: votre-password

Tester
```
make rclone-check
```

#### Étape 2 : Télécharger les Modèles

Télécharger les modèles (choix interactif)
```
make download-models
```

Ou manuellement :
```
./scripts/setup_wan22_native.sh
```

#### Étape 3 : Uploader sur OwnCloud

**Méthode Recommandée : Workflow Séquentiel (économe en espace)**

Workflow complet : download → split → upload → clean
Nécessite seulement ~30GB d'espace disque
```
make sequential-upload-workflow
```

**Workflow détaillé :**
Download modèle 14B (~28GB) → Split → Upload → Clean

Download modèle 5B (~11GB) → Split → Upload → Clean

Upload script de reconstitution
✅ Résultat : Tous les modèles sur OwnCloud, machine propre

**Commandes individuelles (si besoin) :**

Upload modèle 14B seulement
```
make full-workflow-14b
```

Upload modèle 5B seulement
```
make full-workflow-5b
```

Upload script de reconstitution
```
make rclone-upload-reassemble-script
```

#### Étape 4 : Vérifier l'Upload

Vérifier la taille et présence des modèles
```
make rclone-verify
```

Lister les fichiers uploadés
```
make rclone-list
```

#### Étape 5 : Build et Push de l'Image Docker

Build multi-architecture + Push Docker Hub
```
make runpod-deploy
```

Ou version rapide (AMD64 seulement)
```
make runpod-deploy-quick
```

**Durée totale du workflow :** 60-120 minutes (dépend de votre connexion)

---

### Commandes Makefile Principales

| Commande                          | Description                               | Espace Requis |
| --------------------------------- | ----------------------------------------- | ------------- |
| `make download-models`            | Télécharger modèles localement            | ~37GB         |
| `make sequential-upload-workflow` | Workflow séquentiel (économe)             | ~30GB         |
| `make full-upload-workflow`       | Workflow complet (tous modèles d'un coup) | ~54GB         |
| `make rclone-verify`              | Vérifier uploads OwnCloud                 | -             |
| `make rclone-list`                | Lister fichiers sur OwnCloud              | -             |
| `make runpod-deploy`              | Build + Push image (multi-arch)           | -             |
| `make runpod-deploy-quick`        | Build + Push image (AMD64 only)           | -             |
| `make models-deep-clean`          | Nettoyage complet local                   | -             |

---

### Commandes rclone Détaillées

Upload individuel des modèles
```
make rclone-upload-14b # Upload modèle 14B (découpe auto si >8GB)
make rclone-upload-5b # Upload modèle 5B (découpe auto si >8GB)
make rclone-upload-all # Upload TOUS les modèles + script
```

Workflows séquentiels (économie d'espace)
```
make full-workflow-14b # 14B: Download → Split → Upload → Clean
make full-workflow-5b # 5B: Download → Split → Upload → Clean
```

Gestion
```
make rclone-check # Vérifier configuration rclone
make models-size # Afficher taille modèles locaux
make models-deep-clean # Nettoyer cache + chunks + modèles locaux
```

---

### 3. Préparation pour RunPod

Voir la section **"🐳 Préparation de l'Image Docker pour RunPod"** ci-dessus pour :

- Téléchargement des modèles
- Upload sur OwnCloud via rclone
- Build et push de l'image Docker

---

## 🎯 Utilisation Rapide

### Déploiement Local

```bash

# Démarrer ComfyUI

cd /path/to/ComfyUI
python main.py --listen 0.0.0.0 --port 8188

# Démarrer l'interface web (nouveau terminal)

cd /path/to/GEGM_MotionLab
source .venv/bin/activate
python scripts/run_web_interface.py
```

**Accès** : http://localhost:5000

### Déploiement Docker Local

```bash

# Build et démarrage

docker-compose up -d

# Vérifier les logs

docker-compose logs -f

# Health check

curl http://localhost:5000/health
```

### Déploiement RunPod

Voir [README_RUNPOD.md](README_RUNPOD.md) pour le guide complet.

---

## 🎨 Interface GEGM MotionLab

### Paramètres Avancés avec Tooltips

#### 🎛️ Section Diffusion

- **Steps (5-100)** : Nombre d'itérations de diffusion
  - Recommandé : 20-25 steps pour production
- **CFG Scale (1-20)** : Adhérence au prompt
  - Recommandé : 7-8 pour équilibre créatif/précision
- **Denoise (0-100%)** : Force de transformation
  - Recommandé : 60-80% pour équilibre

#### 🌊 Section Mouvement

- **Motion Intensity** : Subtil / Modéré / Fort / Extrême
- **Noise Level** : Low / Medium / High
- **Loop Smoothness** : None / Basic / Advanced
- **Temporal Consistency (0-100%)** : Anti-flickering

#### 🔬 Section Experts

- **Seed** : Graine aléatoire pour reproductibilité
  - -1 = aléatoire à chaque fois
  - Nombre fixe = résultat identique
- **Motion Area** : Full / Center / Edges / Bottom / Top
- **Color Preservation (0-100%)** : Fidélité couleurs
- **Frame Blending (1-7)** : Interpolation temporelle

### Presets Rapides

| Preset            | Steps | CFG | Denoise | Usage              |
| ----------------- | ----- | --- | ------- | ------------------ |
| 💎 **Qualité Max** | 30    | 8.0 | 80%     | Production premium |
| ⚖️ **Équilibré**   | 20    | 7.5 | 75%     | Défaut recommandé  |
| ⚡ **Rapide**      | 15    | 7.0 | 70%     | Tests rapides      |
| 🍃 **Naturel**     | 20    | 6.0 | 65%     | Mouvement subtil   |

### Workflow de Production

```
1. Upload image → Analyse automatique
2. Sélectionner preset ou ajuster paramètres
3. Générer → Aperçu en temps réel
4. Si satisfait :
   - ⬇️ Télécharger (backup local)
   - ☁️ Sauvegarder (OwnCloud)
   - 📋 Noter le seed pour variations
5. Si non satisfait :
   - 🗑️ Supprimer (libérer Pod)
   - 🔄 Nouvelle génération
```

---

## 🧠 Recommandations GPU RunPod

### WAN 2.2 5B (Production Standard)

| GPU              | VRAM | Prix/h    | Temps/Cinéma | Coût/Cinéma | Note              |
| ---------------- | ---- | --------- | ------------ | ----------- | ----------------- |
| **RTX 6000 Ada** | 48GB | **$0.77** | 5 min        | **$0.064**  | ⭐⭐⭐⭐⭐ Optimal     |
| **H100 SXM**     | 80GB | **$2.69** | 2.5 min      | **$0.11**   | ⭐⭐⭐⭐ Vitesse pure |

**Recommandation : RTX 6000 Ada** (meilleur rapport qualité/prix)

---

### WAN 2.2 14B (Qualité Premium)

| GPU          | VRAM  | Prix/h    | Temps/Cinéma | Coût/Cinéma | Note             |
| ------------ | ----- | --------- | ------------ | ----------- | ---------------- |
| **H100 SXM** | 80GB  | **$2.69** | 8 min        | **$0.36**   | ⭐⭐⭐⭐⭐ Optimal    |
| **H200 SXM** | 141GB | **$3.99** | 6 min        | **$0.40**   | ⭐⭐⭐⭐ Vitesse max |

**Recommandation : H100 SXM** (meilleur compromis perf/prix)

---

### Résumé des Choix

WAN 2.2 5B → RTX 6000 Ada (défaut) ou H100 SXM (vitesse)
WAN 2.2 14B → H100 SXM (défaut) ou H200 SXM (vitesse max)

### Coûts Mensuels Estimés

**WAN 2.2 5B (10 sessions de 6h/mois) :**

- RTX 6000 Ada : $46.20/mois (~720 cinemagraphs)
- H100 SXM : $161.40/mois (~1440 cinemagraphs)

**WAN 2.2 14B (10 sessions de 6h/mois) :**

- H100 SXM : $161.40/mois (~450 cinemagraphs)
- H200 SXM : $239.40/mois (~600 cinemagraphs)

## 🏗 Architecture Projet

```bash
GEGM_MotionLab/
├── 🐍 src/ # Code Python core
│ ├── comfyui_client.py # Client API ComfyUI
│ ├── owncloud_uploader.py # Gestion OwnCloud
│ └── logger.py # Logging Loguru
├── 🌐 web_interface/ # Interface Flask
│ ├── templates/
│ │ ├── index.html # Interface principale
│ │ └── base.html # Template de base
│ ├── routes.py # Routes API
│ ├── app.py # Application Flask
│ └── jobs.py # Gestion jobs async
├── 🧠 models/ # Modèles IA (non versionné Git)
│ ├── wan2.2-i2v-a5b/ # WAN 2.2 5B
│ └── wan2.2-i2v-a14b/ # WAN 2.2 14B
├── ⚙️ workflows/ # Workflows ComfyUI
│ ├── templates/ # Templates JSON
│ └── workflow_manager.py # Gestionnaire
├── 🐳 docker/ # Configuration Docker
│ ├── Dockerfile # Multi-arch build
│ └── docker-entrypoint.sh # Entrypoint RunPod
├── 📋 scripts/                # Scripts d'automatisation
│   ├── setup_wan22_native.sh  # Setup modèles
│   ├── reassemble_models.sh   # Reconstitution chunks OwnCloud
│   ├── split_and_upload.py    # Découpe et upload rclone
│   └── run_web_interface.py   # Lancement interface
├── 📝 config/ # Configuration
│ └── owncloud.yaml # Config OwnCloud
└── 📚 docs/ # Documentation
├── README.md # Ce fichier
├── README_DOCKER.md # Guide Docker
└── README_RUNPOD.md # Guide RunPod
```

---

## 🔧 Technologies Utilisées

| Composant     | Stack Technique                     |
| ------------- | ----------------------------------- |
| **Backend**   | Python 3.11, Flask, asyncio         |
| **Frontend**  | HTML5/CSS3/JavaScript (Vanilla)     |
| **IA**        | WAN 2.2 5B/14B, ComfyUI             |
| **Logging**   | Loguru (structured logs)            |
| **Container** | Docker multi-stage, BuildX          |
| **Cloud**     | RunPod GPU, OwnCloud Storage        |
| **API**       | REST API, JSON, WebSocket (ComfyUI) |

---

## 📊 Performance

### WAN 2.2 5B (RTX 6000 Ada)

- **Résolution** : 720p (1280x720)
- **Durée** : 5 secondes (120 frames @ 24fps)
- **Temps génération** : ~5 minutes
- **Coût** : ~$0.064/cinemagraph

### WAN 2.2 14B (H100 SXM 80GB)

- **Résolution** : 720p (1280x720)
- **Durée** : 5 secondes (121 frames @ 24fps)
- **Temps génération** : ~8 minutes
- **Coût** : ~$0.36/cinemagraph

### Formats Supportés

- **Entrée** : JPG, PNG, WebP
- **Sortie** : MP4 (H.264)
- **Résolutions** : 720p à 4K (optimisation automatique)

---

## 📚 Documentation Complète

- **[🐳 Guide Docker](README_DOCKER.md)** : Déploiement local containerisé
- **[🚀 Guide RunPod](README_RUNPOD.md)** : Déploiement cloud production
- **[🔧 API Reference](docs/API.md)** : Documentation API complète
- **[💡 Guide Utilisateur](docs/USAGE.md)** : Utilisation interface

---

## 🐛 Troubleshooting

### ComfyUI ne répond pas

```bash

# Vérifier que ComfyUI est démarré

ps aux | grep "python main.py"

# Tester l'API

curl http://localhost:8188/system_stats

# Redémarrer ComfyUI

cd /path/to/ComfyUI
python main.py --listen 0.0.0.0 --port 8188
```

### Erreur upload OwnCloud

```bash

# Tester la connexion OwnCloud

python scripts/test_owncloud_uploader.py

# Vérifier les credentials dans config/owncloud.yaml

```

### Modèles introuvables

```bash

# Vérifier la présence des modèles

ls -lh models/wan2.2-i2v-a5b/high_noise_model/

# Re-télécharger si nécessaire

./scripts/setup_wan22_native.sh
```

---

## 🔒 Sécurité & Licence

### Sécurité

- ✅ Utilisateur non-root dans Docker
- ✅ Secrets via variables d'environnement
- ✅ OwnCloud HTTPS uniquement
- ✅ Pas de credentials dans le code

### Licence

- **Projet** : Propriétaire GEGM Group
- **Modèles WAN 2.2** : Apache 2.0 (usage commercial autorisé)
- **ComfyUI** : GPL-3.0

**© 2025 KaRn1zC & GEGM Group - Tous droits réservés**

---

## 🤝 Contribution

Ce projet est privé et destiné à un usage professionnel interne GEGM.

---

## 📞 Support

- **Documentation** : Voir `/docs`
- **Issues** : GitHub Issues (projet privé)
- **Contact** : arnaud.boy@gegmgroup.com

---

**Développé avec ❤️ pour la création de cinemagraphs d'exception**
