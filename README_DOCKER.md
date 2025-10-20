# 🐳 Comfy_Img_to_Loop - Docker Deployment

Déploiement containerisé professionnel de Comfy_Img_to_Loop.

## 🚀 Quick Start

### Prérequis
- Docker 20.10+
- Docker Compose 2.0+
- 4GB RAM minimum
- 10GB espace disque

### 1. Configuration

Créez un fichier `.env` à la racine :

```
cp .env.example .env

# Éditez .env avec vos identifiants OwnCloud
```

### 2. Démarrage

# Construction et démarrage

```
make build
make up
```

# Ou en une commande

```
# Utiliser le Makefile ou docker-compose
make build && make up
```

### 3. Accès

- **Interface Web**: http://localhost:5000
- **API Health**: http://localhost:5000/health
- **API Docs**: http://localhost:5000/api/templates

---

## 📦 Commandes Make

| Commande | Description |
|----------|-------------|
| `make help` | Afficher l'aide |
| `make build` | Construire l'image |
| `make up` | Démarrer les services |
| `make down` | Arrêter les services |
| `make restart` | Redémarrer |
| `make logs` | Voir les logs |
| `make shell` | Shell interactif |
| `make test` | Exécuter les tests |
| `make health` | Health check |
| `make clean` | Nettoyer |

---

## 🏗️ Architecture Docker

### Multi-stage Build

**Stage 1: Builder**
- Installation des dépendances de compilation
- Build des packages Python

**Stage 2: Runtime**
- Image légère (Python slim)
- FFmpeg pré-installé
- Utilisateur non-root
- Healthcheck intégré

### Taille optimisée
- Image finale: ~500MB (vs 1.5GB sans optimisation)
- Layers cachés pour build rapide
- Pas de dépendances de compilation inutiles

---

## 📂 Volumes

| Volume | Description |
|--------|-------------|
| `./logs` | Logs de l'application |
| `./web_interface/uploads` | Fichiers uploadés |
| `./config` | Configuration (lecture seule) |
| `./workflows/templates` | Templates de workflows |

---

## 🌐 Variables d'Environnement

### Flask

```
FLASK_HOST=0.0.0.0
FLASK_PORT=5000
FLASK_DEBUG=false
SECRET_KEY=your-secret-key
```

### ComfyUI

```
COMFYUI_HOST=127.0.0.1  \# ou 'comfyui' si en Docker
COMFYUI_PORT=8188
```

### OwnCloud

```
OWNCLOUD_SERVER_URL=https://your-server.com
OWNCLOUD_USERNAME=your-username
OWNCLOUD_PASSWORD=your-password
OWNCLOUD_MODEL_FOLDER=/Cinemagraphs
```

### Logging

```
LOG_LEVEL=INFO  \# DEBUG, INFO, WARNING, ERROR
```

---

## 🔧 Mode Développement

```
# Démarrer avec hot reload

make dev

# Ou

docker-compose -f docker-compose.yml -f docker-compose.override.yml up
```

En mode dev :
- Hot reload du code
- Debug logs activés
- Volumes montés pour le code source

---

## 🚀 Mode Production

```
# Démarrer en production

make prod

# Ou

docker-compose -f docker-compose.yml up -d
```

Optimisations production :
- Code copié dans l'image (pas de volumes)
- Debug désactivé
- Restart automatique
- Healthcheck actif

---

## 🏥 Health Check

Le conteneur expose un endpoint de santé :

```
# Via make

make health

# Via curl

curl http://localhost:5000/health

# Réponse

{
"status": "healthy",
"services": {
"flask": "ok",
"comfyui": "ok",
"owncloud": "ok"
}
}
```

---

## 🧪 Tests dans Docker

```
# Tous les tests

make test

# Tests workflows

make test-workflows

# Shell interactif pour débug

make shell
pytest tests/ -v
```

---

## 📊 Monitoring

```
# Voir les stats en temps réel

make stats

# Voir les logs

make logs

# Logs de l'app uniquement

make logs-app
```

---

## 🔒 Sécurité

✅ **Best Practices Appliquées:**
- Utilisateur non-root (UID 1000)
- Image slim (surface d'attaque réduite)
- Secrets via variables d'environnement
- Healthcheck pour auto-healing
- Restart policy configuré

---

## 🐛 Troubleshooting

### Le conteneur ne démarre pas

```
# Voir les logs

make logs

# Vérifier la config

docker-compose config
```

### Erreur de connexion ComfyUI

```
# Vérifier que ComfyUI est accessible

docker exec comfy_img_to_loop curl http://comfyui:8188
```

### Problème de permissions

```
# Les volumes doivent être accessibles par UID 1000

sudo chown -R 1000:1000 logs/ web_interface/uploads/
```

---

## 🧹 Nettoyage

```
# Arrêter et supprimer les volumes

make clean

# Rebuild from scratch

make rebuild
```

---

## 📝 Notes

- **GPU Support**: Pour activer le GPU avec ComfyUI, décommentez la section `deploy` dans `docker-compose.yml`
- **Production**: Changez `SECRET_KEY` et utilisez un reverse proxy (nginx/traefik)
- **Scaling**: Utilisez Docker Swarm ou Kubernetes pour multi-instances

---

## 🆘 Support

- **Issues**: https://github.com/KaRn1zC/Comfy_Img_to_Loop/issues
- **Docs**: Voir README principal
- **Contact**: arnaud.boy@gegmgroup.com

## Tests de la containerisation

```bash
# 1. Build de l'image
docker-compose build

# 2. Démarrage
docker-compose up -d

# 3. Vérifier les logs
docker-compose logs -f

# 4. Health check
curl http://localhost:5000/health

# 5. Tester l'interface
open http://localhost:5000

# 6. Tests dans le conteneur
docker-compose exec comfy_img_to_loop pytest tests/ -v

# 7. Arrêt
docker-compose down
```