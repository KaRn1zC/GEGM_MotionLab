# 🎬 Comfy_Img_to_Loop

**Générateur de Cinemagraphs professionnel avec ComfyUI et WAN 2.2**

> Transformez vos images statiques en boucles vidéo captivantes avec l'IA la plus avancée du moment.

## 🚀 Fonctionnalités

- **IA de pointe** : WAN 2.2 14B pour une qualité exceptionnelle
- **Interface intuitive** : Drag & drop, configuration simple
- **Sauvegarde automatique** : Intégration OwnCloud sécurisée  
- **Déploiement cloud** : Template RunPod optimisé
- **Upscaling intelligent** : Pyramid Flow pour la haute résolution

## 📋 Prérequis

- **Python** : 3.11.13
- **Docker** : Version récente
- **GPU** : Recommandé 24GB+ VRAM (A100, H100, RTX 6000 Ada)
- **RunPod** : Compte avec crédits
- **OwnCloud** : Serveur pour la sauvegarde (optionnel)

## 🛠 Installation

### 1. Cloner le projet

```bash
git clone [votre-repo-url]
cd Comfy_Img_to_Loop
```

### 2. Configuration de l'environnement

```bash
# Créer l'environnement virtuel

python3.11 -m venv .venv
source .venv/bin/activate

# Installer les dépendances

pip install -r requirements.txt
```

### 3. Télécharger les modèles

```bash
./scripts/setup_wan22_native.sh
```

### 4. Supprimer les fichiers inutiles pour libérer de l'espace

**1: Supprimer le cache de téléchargement HuggingFace**
```bash
rm -rf models/wan2.2-i2v-a14b/.cache/
```

**2: Supprimer le variant Low noise :**
```bash
rm -rf models/wan2.2-i2v-a14b/low_noise_model/
```

### 5. Construire l'image Docker

```bash
./build.sh all
```

## 🎯 Utilisation rapide

### Déploiement local

```bash
docker-compose up -d
```
Accès : http://localhost:5000

### Déploiement RunPod
1. Uploader l'image Docker vers un registry
2. Créer le template RunPod avec les secrets OwnCloud
3. Déployer le Pod

## 📚 Documentation

- [🔧 Installation détaillée](docs/INSTALL.md)
- [💡 Guide d'utilisation](docs/USAGE.md)
- [🔌 API Documentation](docs/API.md)
- [☁️ Configuration RunPod](docs/RUNPOD_SETUP.md)
- [💡 Les modèles AI ne sont **pas versionnés dans Git** en raison de leur taille (>100GB)]

## 🏗 Architecture

```bash
Comfy_Img_to_Loop/
├── 🐍 src/                    \# Code Python principal
├── 🌐 web_interface/          \# Interface utilisateur
├── 🧠 models/                 \# Modèles IA (WAN 2.2 14B)
├── ⚙️  workflows/             \# Workflows ComfyUI
├── 🐳 docker/                 \# Configuration Docker
└── 📋 scripts/                \# Scripts d'automatisation
```

## 🔧 Technologies utilisées

| Composant | Technologie |
|-----------|-------------|
| **Backend** | Python 3.11, Flask, Loguru |
| **IA** | WAN 2.2 14B, Pyramid Flow, ComfyUI |
| **Frontend** | HTML5/CSS3/JavaScript |
| **Container** | Docker multi-stage |
| **Cloud** | RunPod, OwnCloud |

## 📊 Performance

- **Temps de génération** : 30-120s selon résolution
- **Qualités supportées** : 1080p à 4K
- **Formats** : MP4, GIF, WebM
- **Durée** : 3-10 secondes par boucle

## 🤝 Contribution

Ce projet est privé et destiné à un usage professionnel.

## 📄 License

KaRn1zC & GEGM Group - Tous droits réservés

---

**Développé avec ❤️ pour la création de cinemagraphs d'exception**