# 🎬 Comfy_Img_to_Loop

**Générateur de Cinemagraphs professionnel avec ComfyUI et WAN 2.2**

> Transformez vos images statiques en boucles vidéo captivantes avec l'IA la plus avancée du moment.

## 🚀 Fonctionnalités

- **IA de pointe** : WAN 2.2 14B pour une qualité exceptionnelle
- **Interface intuitive** : Drag & drop, configuration simple
- **Sauvegarde automatique** : Intégration OwnCloud sécurisée  
- **Déploiement cloud** : Template RunPod optimisé
- **Upscaling intelligent** : Pyramid Flow pour la haute résolution
- **Les modèles AI ne sont pas versionnés dans Git en raison de leur taille (>100GB)**

## 📋 Prérequis

- **Python** : 3.11.13
- **Docker** : Version récente
- **GPU** : Recommandé 24GB+ VRAM (B200, H200, A100, H100, RTX 6000 Ada)
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
```

```bash
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

## Template pour utilisation du fichier logger configuré avec loguru

```python
"""
Description du fichier
"""

import sys
from pathlib import Path

# Import du système de logging centralisé
sys.path.append(str(Path(__file__).parent.parent))
from src.logger import get_logger, setup_logger

# Configuration du logger pour ce script
logger = get_logger("nom_du_module")

def main():
    """Fonction principale"""
    logger.info("🚀 Démarrage du script")
    
    # Votre code ici
    
    logger.success("✅ Script terminé avec succès")

if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        logger.warning("Script interrompu par l'utilisateur")
        sys.exit(1)
    except Exception as e:
        logger.error(f"Erreur inattendue: {e}")
        sys.exit(1)
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

## 🧠 Recommandations GPU

- **WAN 2.2 5B** :
    **RTX 6000 Ada 48Gb** pour meilleur rapport performance prix
    **H100 SXM 80Gb** pour gagner en vitesse en conservant un coût raisonnable
    
- **WAN 2.2 14B** :
    **H100 SXM 80Gb** pour meilleur rapport performance prix
    **H200 SXM 141Gb** pour gagner en vitesse en conservant un coût raisonnable

## 📊 Performance

- **Temps de génération** : 30-600s selon résolution
- **Qualités supportées** : de 720p jusqu'à 4K
- **Formats** : MP4, GIF, WebM
- **Durée** : 3-10 secondes par boucle

## 🤝 Contribution

Ce projet est privé et destiné à un usage professionnel.

## 📄 License

KaRn1zC & GEGM Group - Tous droits réservés

---

**Développé avec ❤️ pour la création de cinemagraphs d'exception**