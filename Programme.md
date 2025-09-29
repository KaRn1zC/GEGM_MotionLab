# Plan complet étape par étape

## **PHASE 1 : STRUCTURE INITIALE DU PROJET**

### Étape 1.1 : Création de la structure de dossiers

- Créer le projet VSCode "Comfy_Img_to_Loop"
- Créer l'arborescence complète des dossiers
- Initialiser Git et .gitignore
- Créer les fichiers README et documentation


### Étape 1.2 : Configuration de l'environnement Python

- Créer l'environnement virtuel `.venv` (Python 3.11.13)
- Installer les dépendances de base
- Configurer VSCode pour le projet
- Créer requirements.txt


## **PHASE 2 : GESTION DES MODÈLES ET TÉLÉCHARGEMENTS**

### Étape 2.1 : Configuration des versions de modèles

- Créer `config/model_versions.yaml` (WAN 2.2 14B uniquement + Pyramid Flow)
- Définir les URLs et checksums exacts
- Configuration des custom nodes requis


### Étape 2.2 : Script de téléchargement intelligent

- Développer `scripts/setup_wan22_native.sh` optimisé qui :
- Télécharge les modèles localement
- Script de nettoyage et mise à jour
- Validation d'intégrité des modèles
- Système de versioning local


## **PHASE 3 : INTERFACE WEB ET API**

### Étape 3.1 : Configuration du logger

- Créer `src/logger.py` avec loguru
- Configuration des niveaux de logs
- Rotation et persistance des logs


### Étape 3.2 : Client ComfyUI

- Développer `src/comfyui_client.py`
- API WebSocket pour le monitoring
- Gestion des workflows et prompts
- Gestion des erreurs et timeouts


### Étape 3.3 : Module de sauvegarde OwnCloud

- Créer `src/owncloud_uploader.py`
- Authentification et upload sécurisé
- Génération de liens de partage
- Gestion des métadonnées vidéo


### Étape 3.4 : Interface Flask principale

- Développer `web_interface/app.py`
- Routes API complètes
- Gestion des jobs asynchrones
- Intégration OwnCloud


### Étape 3.5 : Interface utilisateur HTML/CSS/JS

- Template HTML responsive
- Interface drag \& drop pour images
- Gestion des prompts et paramètres
- Monitoring en temps réel des tâches
- Interface de sauvegarde OwnCloud


## **PHASE 4 : WORKFLOWS COMFYUI**

### Étape 4.1 : Workflows de base

- Créer `workflows/wan22_cinemagraph.json`
- Créer `workflows/pyramid_upscale.json`
- Paramétrage dynamique des workflows
- Tests et validation


## **PHASE 5 : CONTAINERISATION DOCKER**

### Étape 5.1 : Dockerfile multi-stage optimisé

- Stage de préparation des modèles
- Stage de production optimisé
- Configuration des volumes et ports
- Optimisations de performance


### Étape 5.2 : Scripts de démarrage

- `docker/startup_production.sh`
- Gestion intelligente des volumes
- Préchargement des modèles
- Healthchecks et monitoring


### Étape 5.3 : Script de build automatisé

- `build.sh` avec toutes les étapes
- Tests d'intégrité
- Gestion des versions
- Push vers registry


## **PHASE 6 : DÉPLOIEMENT RUNPOD**

### Étape 6.1 : Configuration des secrets RunPod

- Configuration des variables OwnCloud
- Secrets chiffrés pour la sécurité
- Variables d'environnement du template


### Étape 6.2 : Création du template RunPod privé

- Configuration du template
- Upload de l'image Docker
- Tests de déploiement
- Documentation d'utilisation


## **PHASE 7 : TESTS ET VALIDATION**

### Étape 7.1 : Tests locaux

- Tests unitaires des composants
- Tests d'intégration
- Validation des workflows
- Tests de performance


### Étape 7.2 : Tests sur RunPod

- Déploiement et tests complets
- Validation de la sauvegarde OwnCloud
- Tests de différentes résolutions/formats
- Optimisation finale


# Structure finale du projet "Comfy_Img_to_Loop"

```
Comfy_Img_to_Loop/
├── .venv/                           # Environnement Python 3.11.13
├── .git/                           # Git repository
├── .gitignore                      # Git ignore
├── README.md                       # Documentation principale
├── requirements.txt                # Dépendances Python
├── build.sh                        # Script de build automatisé
│
├── config/
│   ├── model_versions.yaml         # Configuration versions WAN 2.2 14B
│   └── app_config.yaml            # Configuration application
│
├── scripts/
│   ├── download_models.py          # Téléchargement WAN 2.2 14B + Pyramid
│   ├── update_versions.py          # Gestion des versions
│   └── cleanup_old_models.py       # Nettoyage
│
├── src/
│   ├── __init__.py
│   ├── logger.py                   # Configuration loguru
│   ├── comfyui_client.py          # Client API ComfyUI
│   ├── owncloud_uploader.py       # Module sauvegarde OwnCloud
│   ├── video_processor.py         # Traitement vidéo (upscaling, etc.)
│   └── main.py                    # Point d'entrée principal
│
├── web_interface/
│   ├── app.py                     # Flask app principale
│   ├── templates/
│   │   ├── index.html             # Interface utilisateur principale
│   │   ├── status.html            # Page de statut des tâches
│   │   └── history.html           # Historique des générations
│   └── static/
│       ├── css/
│       │   └── style.css          # Styles CSS responsifs
│       ├── js/
│       │   └── app.js             # JavaScript pour l'interface
│       └── images/
│           └── favicon.ico        # Assets statiques
│
├── workflows/
│   ├── wan22_cinemagraph.json     # Workflow principal WAN 2.2
│   ├── pyramid_upscale.json       # Workflow upscaling
│   └── templates/                 # Templates de workflows
│
├── models/                        # Modèles téléchargés localement
│   ├── checkpoints/
│   │   └── wan_2.2_14b.safetensors
│   ├── vae/
│   ├── clip/
│   ├── custom_nodes/
│   │   ├── ComfyUI-WAN2Wrapper/
│   │   └── ComfyUI-PyramidFlowWrapper/
│   └── versions.json              # Tracking des versions installées
│
├── comfyui/                       # ComfyUI téléchargé localement
│   ├── main.py
│   ├── requirements.txt
│   └── ...                        # Code ComfyUI complet
│
├── docker/
│   ├── Dockerfile                 # Multi-stage optimisé
│   ├── .dockerignore             # Optimisation build context
│   ├── startup_production.sh     # Script de démarrage
│   └── docker-compose.yml        # Pour tests locaux
│
├── tests/
│   ├── __init__.py
│   ├── test_comfyui_client.py    # Tests unitaires
│   ├── test_owncloud.py          # Tests sauvegarde
│   └── test_workflows.py         # Tests workflows
│
├── logs/                         # Logs de l'application (via loguru)
├── outputs/                      # Vidéos générées localement
├── uploads/                      # Images uploadées
└── docs/
    ├── INSTALL.md                # Guide d'installation
    ├── USAGE.md                  # Guide d'utilisation
    ├── API.md                    # Documentation API
    └── RUNPOD_SETUP.md          # Guide setup RunPod
```

# Récapitulatif des technologies utilisées

**Backend :**

- Python 3.11.13 avec environnement `.venv`
- Flask pour l'API web
- Loguru pour les logs structurés
- Requests + WebSocket pour ComfyUI
- pyocclient pour OwnCloud

**AI/ML :**

- WAN 2.2 14B uniquement (modèle le plus puissant)
- Pyramid Flow pour l'upscaling
- ComfyUI comme orchestrateur

**Frontend :**

- HTML5/CSS3/JavaScript vanilla (interface moderne)
- Drag \& drop pour les images
- Monitoring temps réel des tâches
- Interface responsive

**Infrastructure :**

- Docker multi-stage optimisé
- RunPod avec template privé + secrets
- Network Volume pour persistance optionnelle
- OwnCloud pour sauvegarde automatique

