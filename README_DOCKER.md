# 🐳 GEGM MotionLab - Docker Deployment

Guide complet de déploiement containerisé pour GEGM MotionLab.

## ⚠️ Architecture Importante

**Image Docker Légère : ~8GB (sans modèles)**

Les modèles WAN 2.2 (5B/14B) ne sont **PAS inclus** dans l'image Docker pour éviter une taille excessive (35-40GB).

**Workflow de déploiement :**
1. Build image Docker légère (~8GB)
2. Modèles stockés sur OwnCloud (découpés en chunks)
3. Pod RunPod télécharge les modèles au démarrage depuis OwnCloud

**Démarrage du Pod RunPod :**
1. Le conteneur démarre (~10 secondes)
2. Script `docker-entrypoint.sh` s'exécute
3. Téléchargement automatique des modèles depuis OwnCloud (~5-10 min)
4. Reconstitution des chunks en modèles complets
5. Démarrage de ComfyUI et Flask
6. 🎬 Interface GEGM MotionLab prête !

**Voir [README_RUNPOD.md](README_RUNPOD.md) pour le workflow complet de préparation.**

---

## 🚀 Quick Start

### Prérequis

- **Docker** : 20.10+ avec BuildX
- **Docker Compose** : 2.0+
- **RAM** : 8GB minimum
- **Stockage** : 15GB pour l'image (sans modèles)
- **GPU** : NVIDIA avec CUDA 12.8+ (pour production)

### 1. Configuration

Créez \`.env\` à la racine du projet :

```bash
cp .env.example .env
# Éditez .env avec vos identifiants OwnCloud
```

**Contenu de \`.env\` :**

```env
# OwnCloud Configuration
OWNCLOUD_SERVER_URL=https://www.cloud-gegm.com
OWNCLOUD_USERNAME=votre-username
OWNCLOUD_PASSWORD=votre-password
OWNCLOUD_MODEL_FOLDER=/GEGM_ComfyUI/Models
OWNCLOUD_CINEMAGRAPH_FOLDER=/GEGM_ComfyUI/Cinemagraphs

# Flask Configuration
FLASK_HOST=0.0.0.0
FLASK_PORT=5000
FLASK_DEBUG=false
SECRET_KEY=change-me-in-production

# ComfyUI Configuration
COMFYUI_HOST=127.0.0.1
COMFYUI_PORT=8188

# Logging
LOG_LEVEL=INFO
```

### 2. Build & Démarrage

```bash
# Build de l'image
docker-compose build

# Démarrer les services
docker-compose up -d

# Vérifier les logs
docker-compose logs -f
```

### 3. Accès

- **Interface Web** : http://localhost:5000
- **API Health** : http://localhost:5000/health
- **ComfyUI** : http://localhost:8188

---

## 📦 Architecture Docker

### Multi-Stage Build Optimisé

**Stage 1: Base CUDA**
- Base: `nvidia/cuda:12.8.1-cudnn-runtime-ubuntu22.04`
- Installation Python 3.11
- Dépendances système (FFmpeg, rclone, etc.)

**Stage 2: Builder**
- Installation dépendances Python
- Build des wheels pour accélération

**Stage 3: Runtime**
- Copie des dépendances buildées
- Ajout ComfyUI
- **Script de téléchargement modèles depuis OwnCloud**
- Configuration entrypoint
- Healthcheck intégré

### Taille de l'Image

| Variante | Taille | Modèles | Notes |
|----------|--------|---------|-------|
| **Légère (production)** | ~8GB | ❌ Téléchargés au démarrage | **Utilisée actuellement** |
| Complète 5B | ~18-20GB | ✅ WAN 2.2 5B inclus | Non utilisée |
| Complète 14B | ~35-40GB | ✅ WAN 2.2 14B inclus | Non utilisée |

**Avantages de l'architecture légère :**
- ✅ Build rapide (~10-15 min vs 30-60 min)
- ✅ Push rapide (~5-10 min vs 1-2h)
- ✅ Image Docker Hub légère
- ✅ Flexibilité : choix du modèle au démarrage du Pod

**Inconvénient :**
- ⚠️ Téléchargement modèles au premier démarrage Pod (~5-10 min)

## 🔧 Workflow de Préparation des Modèles

Les modèles WAN 2.2 sont gérés via OwnCloud avec découpe automatique.

**Voir [README.md](README.md) section "Préparation de l'Image Docker pour RunPod"** pour :
- Téléchargement des modèles localement
- Découpe automatique en chunks (>8GB → morceaux de 2GB)
- Upload via rclone sur OwnCloud
- Vérification de l'upload

**Commandes principales :**
```
make download-models # Télécharger modèles
make sequential-upload-workflow # Upload séquentiel (économe)
make rclone-verify # Vérifier upload
```

## 🏗️ Build Multi-Architecture

Support AMD64 (RunPod/serveurs) + ARM64 (Mac M1/M2/M3).

### Setup BuildX (une fois)

```bash
# Créer le builder multi-arch
docker buildx create --name multiarch-builder --use
docker buildx inspect --bootstrap
```

### Build Multi-Arch

```bash
# Build pour AMD64 + ARM64
docker buildx build \
  --platform linux/amd64,linux/arm64 \
  --tag arnaudboy/comfy_img_to_loop:latest \
  --push \
  .

# Ou via Makefile
make runpod-build
```

---

## 📂 Volumes Docker

| Volume      | Path Container                 | Description                          |
| ----------- | ------------------------------ | ------------------------------------ |
| **uploads** | \`/app/web_interface/uploads\` | Images uploadées (temporaire)        |
| **logs**    | \`/app/logs\`                  | Logs application                     |
| **models**  | \`/app/models\`                | Modèles IA (optionnel si pré-inclus) |
| **output**  | \`/app/output\`                | Cinemagraphs générés                 |

### Montage des Volumes

**docker-compose.yml :**

```yaml
services:
  comfy_img_to_loop:
    volumes:
      - ./logs:/app/logs
      - ./web_interface/uploads:/app/web_interface/uploads
      - ./output:/app/output
      # Optionnel : monter les modèles si non inclus dans l'image
      # - ./models:/app/models:ro
```

---

## 🌐 Variables d'Environnement

### Flask (Backend)

| Variable        | Défaut      | Description                 |
| --------------- | ----------- | --------------------------- |
| \`FLASK_HOST\`  | \`0.0.0.0\` | Adresse d'écoute            |
| \`FLASK_PORT\`  | \`5000\`    | Port de l'interface         |
| \`FLASK_DEBUG\` | \`false\`   | Mode debug (dev uniquement) |
| \`SECRET_KEY\`  | _(requis)_  | Clé secrète Flask           |

### ComfyUI

| Variable            | Défaut        | Description                  |
| ------------------- | ------------- | ---------------------------- |
| \`COMFYUI_HOST\`    | \`127.0.0.1\` | Host ComfyUI                 |
| \`COMFYUI_PORT\`    | \`8188\`      | Port API ComfyUI             |
| \`COMFYUI_TIMEOUT\` | \`300\`       | Timeout connexion (secondes) |

### OwnCloud

| Variable                        | Description                  |
| ------------------------------- | ---------------------------- |
| \`OWNCLOUD_SERVER_URL\`         | URL du serveur (https://...) |
| \`OWNCLOUD_USERNAME\`           | Username OwnCloud            |
| \`OWNCLOUD_PASSWORD\`           | Mot de passe                 |
| \`OWNCLOUD_MODEL_FOLDER\`       | Dossier des modèles          |
| \`OWNCLOUD_CINEMAGRAPH_FOLDER\` | Dossier des cinemagraphs     |

### Logging

| Variable      | Valeurs                                     | Description    |
| ------------- | ------------------------------------------- | -------------- |
| \`LOG_LEVEL\` | \`DEBUG\`, \`INFO\`, \`WARNING\`, \`ERROR\` | Niveau de logs |

---

## 🔧 Modes de Déploiement

### Mode Développement

```bash
# Démarrer avec hot reload
docker-compose -f docker-compose.yml -f docker-compose.dev.yml up

# Ou via Makefile
make dev
```

**Features dev :**

- ✅ Code source monté en volume (hot reload)
- ✅ Debug logs activés
- ✅ Pas de restart automatique
- ✅ Ports exposés pour debug

### Mode Production

```bash
# Démarrer en production
docker-compose up -d

# Ou via Makefile
make prod
```

**Features prod :**

- ✅ Code copié dans l'image (pas de volumes)
- ✅ Restart automatique (\`unless-stopped\`)
- ✅ Healthcheck actif
- ✅ Logs structurés

---

## 🏥 Health Check

Le conteneur expose un endpoint de santé.

### Test Health Check

```bash
# Via curl
curl http://localhost:5000/health

# Réponse attendue
{
  "status": "healthy",
  "services": {
    "flask": "ok",
    "comfyui": "ok",
    "owncloud": "ok"
  },
  "timestamp": "2025-10-21T12:00:00Z"
}
```

### Configuration Docker

**docker-compose.yml :**

```yaml
healthcheck:
  test: ["CMD", "curl", "-f", "http://localhost:5000/health"]
  interval: 30s
  timeout: 10s
  retries: 3
  start_period: 60s
```

---

## 📊 Monitoring & Logs

### Voir les Logs

```bash
# Logs en temps réel
docker-compose logs -f

# Logs d'un service spécifique
docker-compose logs -f comfy_img_to_loop

# Logs avec timestamps
docker-compose logs -f -t
```

### Logs Structurés

Les logs sont au format JSON structuré (Loguru) :

```json
{
  "timestamp": "2025-10-21 12:00:00",
  "level": "INFO",
  "module": "routes",
  "message": "Job abc-123 started",
  "extra": {
    "job_id": "abc-123",
    "user_ip": "192.168.1.1"
  }
}
```

### Statistiques en Temps Réel

```bash
# Stats conteneurs
docker stats

# Ou via Makefile
make stats
```

---

## 🧪 Tests dans Docker

### Exécuter les Tests

```bash
# Tous les tests
docker-compose exec comfy_img_to_loop pytest tests/ -v

# Tests d'un module spécifique
docker-compose exec comfy_img_to_loop pytest tests/test_routes.py -v

# Avec couverture
docker-compose exec comfy_img_to_loop pytest --cov=src --cov-report=html
```

### Shell Interactif

```bash
# Accéder au shell
docker-compose exec comfy_img_to_loop /bin/bash

# Ou via Makefile
make shell
```

---

## 🐛 Troubleshooting

### Conteneur Ne Démarre Pas

```bash
# Voir les logs de démarrage
docker-compose logs comfy_img_to_loop

# Vérifier la configuration
docker-compose config

# Rebuild from scratch
docker-compose down -v
docker-compose build --no-cache
docker-compose up -d
```

### Erreur de Connexion ComfyUI

```bash
# Vérifier que ComfyUI écoute sur 0.0.0.0
docker-compose exec comfy_img_to_loop curl http://127.0.0.1:8188/system_stats

# Vérifier les logs ComfyUI
docker-compose logs comfyui
```

### Problèmes de Permissions

```bash
# Les volumes doivent être accessibles par UID 1000
sudo chown -R 1000:1000 logs/ web_interface/uploads/ output/

# Vérifier les permissions dans le conteneur
docker-compose exec comfy_img_to_loop ls -la /app/logs
```

### Modèles Introuvables

```bash
# Vérifier la présence des modèles dans l'image
docker-compose exec comfy_img_to_loop ls -lh /app/models/

# Si modèles non inclus, monter le volume
# docker-compose.yml :
volumes:
  - ./models:/app/models:ro
```

### OwnCloud Upload Échoue

```bash
# Tester la connexion OwnCloud
docker-compose exec comfy_img_to_loop python -c "
from src.owncloud_uploader import OwnCloudUploader
import asyncio
async def test():
    config = {'server_url': 'https://...', 'username': '...', 'password': '...'}
    async with OwnCloudUploader(config) as uploader:
        print('✅ Connexion OwnCloud OK')
asyncio.run(test())
"
```

---

## 🔒 Sécurité

### Best Practices Appliquées

- ✅ **Utilisateur non-root** : UID 1000 dans le conteneur
- ✅ **Image slim** : Surface d'attaque réduite
- ✅ **Secrets via env vars** : Pas de credentials hardcodés
- ✅ **Healthcheck** : Auto-healing des services
- ✅ **Restart policy** : \`unless-stopped\` en production

### Recommandations Production

```yaml
# docker-compose.prod.yml
services:
  comfy_img_to_loop:
    restart: unless-stopped
    environment:
      - FLASK_DEBUG=false
      - SECRET_KEY=${SECRET_KEY} # Depuis secrets manager
    networks:
      - internal
    # Pas d'exposition directe, utiliser un reverse proxy
    expose:
      - "5000"

  nginx:
    image: nginx:alpine
    ports:
      - "443:443"
    volumes:
      - ./nginx.conf:/etc/nginx/nginx.conf:ro
      - ./ssl:/etc/nginx/ssl:ro
    networks:
      - internal
      - external
```

---

## 🧹 Nettoyage

### Arrêter et Nettoyer

```bash
# Arrêter les services
docker-compose down

# Supprimer les volumes (⚠️ perte de données)
docker-compose down -v

# Supprimer l'image
docker rmi arnaudboy/comfy_img_to_loop:latest

# Nettoyer Docker complet
docker system prune -a --volumes
```

---

## 📝 Makefile Commands

Commandes disponibles via \`make\` :

| Commande         | Description           |
| ---------------- | --------------------- |
| \`make help\`    | Afficher l'aide       |
| \`make build\`   | Construire l'image    |
| \`make up\`      | Démarrer les services |
| \`make down\`    | Arrêter les services  |
| \`make restart\` | Redémarrer            |
| \`make logs\`    | Voir les logs         |
| \`make shell\`   | Shell interactif      |
| \`make test\`    | Exécuter les tests    |
| \`make health\`  | Health check          |
| \`make stats\`   | Statistiques          |
| \`make clean\`   | Nettoyer              |
| \`make rebuild\` | Rebuild from scratch  |

---

## 🆘 Support

- **Documentation** : Voir [README.md](README.md) principal
- **RunPod** : Voir [README_RUNPOD.md](README_RUNPOD.md)
- **Issues** : GitHub Issues (projet privé)
- **Contact** : arnaud.boy@gegmgroup.com

---

**© 2025 GEGM Group - Docker deployment guide v2.0**
