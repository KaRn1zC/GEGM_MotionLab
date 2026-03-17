# GEGM MotionLab - Guide RunPod

**Déploiement cloud GPU sur RunPod**

[![RunPod](https://img.shields.io/badge/runpod-cloud-blueviolet.svg)](https://runpod.io)
[![GPU](https://img.shields.io/badge/GPU-RTX%206000%20%2F%20H100-success.svg)](https://runpod.io)
[![Version](https://img.shields.io/badge/version-4.3.1-blue.svg)](CHANGELOG.md)

---

## Choix GPU

### WAN 2.2 5B (Standard)

| Priorité | GPU | VRAM | Temps |
|----------|-----|------|-------|
| 1 | **RTX 6000 Ada** | 48GB | ~5 min |
| 2 | **L40** | 48GB | ~5 min |
| 3 | **L40S** | 48GB | ~5 min |
| - | Autre GPU | 48GB+ | Variable |

**Minimum requis :** 48GB VRAM

### WAN 2.2 14B MoE (Premium)

| Priorité | GPU | VRAM | Temps |
|----------|-----|------|-------|
| 1 | **RTX Pro 6000** | 96GB | ~8 min |
| 2 | **RTX Pro 6000 WK** | 96GB | ~8 min |
| 3 | **H100 SXM** | 80GB | ~8 min |
| - | Autre GPU | 80GB+ | Variable |

**Minimum requis :** 80GB VRAM

---

## Prérequis

### Services
- **RunPod** : Compte avec crédit
- **OwnCloud** : Serveur avec 35+ GB

### Local
- **rclone** : Installé et configuré
- **Docker** : 20.10+ avec BuildX
- **Espace disque** : 100 GB libre

```bash
# Vérification
rclone --version
docker --version
docker buildx version
```

---

## Préparation Modèles

### Configuration rclone (une fois)

```bash
rclone config

# Créer remote "owncloud"
n) New remote
name> owncloud
Storage> webdav
URL> https://your-server.com
vendor> owncloud
user> your-username
password> your-password

# Tester
rclone ls owncloud:/GEGM_ComfyUI/Models/
```

### Workflow Complet

```bash
# 1. Download + Fusion + Vérification
./scripts/setup_wan22_native.sh wan2.2-ti2v-5b

# 2. Upload OwnCloud
make full-workflow-5b

# Pour 14B
./scripts/setup_wan22_native.sh wan2.2-i2v-a14b
make full-workflow-14b
```

### Vérification Upload

```bash
make rclone-list
rclone ls owncloud:/GEGM_ComfyUI/Models/wan2.2-ti2v-5b/ | wc -l
# 5B: ~35 fichiers | 14B: ~45 fichiers
```

---

## Build et Déploiement

### Production (branche main)

```bash
# Build multi-arch + push Docker Hub → :latest
make runpod-deploy

# Build rapide AMD64 uniquement → :latest
make runpod-deploy-quick
```

**Image :** `arnaudboy/comfy_img_to_loop:latest`

### Test (branche debug)

```bash
# Build rapide AMD64 uniquement → :test
make runpod-deploy-quick-test

# Build multi-arch + push → :test
make runpod-deploy-test
```

**Image :** `arnaudboy/comfy_img_to_loop:test`

### Workflow deux branches

```bash
# PRODUCTION — code stable validé
git checkout main
make runpod-deploy-quick       # → arnaudboy/comfy_img_to_loop:latest

# TEST — expérimentation
git checkout debug
make runpod-deploy-quick-test  # → arnaudboy/comfy_img_to_loop:test
```

Sur RunPod, créer 2 templates séparés :
- **Template prod** : image `arnaudboy/comfy_img_to_loop:latest`
- **Template test** : image `arnaudboy/comfy_img_to_loop:test`

---

## Créer le Pod

### Configuration

```yaml
Container Image: arnaudboy/comfy_img_to_loop:latest
Container Disk: 100 GB
Expose HTTP Ports: 5000

Environment Variables:
  OWNCLOUD_SERVER_URL=https://your-server.com
  OWNCLOUD_USERNAME=your-username
  OWNCLOUD_PASSWORD=your-password
  OWNCLOUD_MODEL_FOLDER=/GEGM_ComfyUI/Models
```

### GPU Recommandé

- **5B :** RTX 6000 Ada, L40, L40S (ou 48GB+ VRAM)
- **14B MoE :** RTX Pro 6000, RTX Pro 6000 WK, H100 SXM (ou 80GB+ VRAM)

### Temps Démarrage

```
00:00  Pod créé
00:30  Image pulled
02:00  Download modèles OwnCloud
15:00  Reconstitution modèles
17:00  ComfyUI démarré
19:00  Flask ready
```

**Total :** ~20 minutes

### Accès

```
https://<pod-id>-5000.proxy.runpod.net
```

---

## Utilisation

1. Ouvrir URL Pod
2. Uploader image (JPG/PNG)
3. Configurer paramètres
4. Générer (~5-8 min)
5. Télécharger MP4

### API

```bash
# Health check
curl https://<pod-id>-5000.proxy.runpod.net/health

# Statut job
curl https://<pod-id>-5000.proxy.runpod.net/api/jobs/<job_id>
```

---

## Gestion Coûts

### Optimisation
- Arrêter Pod après utilisation
- RTX 6000 Ada pour 5B (pas H100)
- Batch processing
- Auto-stop inactivité

### Calcul

**RTX 6000 Ada ($0.77/h) :**
| Durée | Coût | Vidéos |
|-------|------|--------|
| 1h | $0.77 | 12 |
| 6h | $4.62 | 72 |

**H100 SXM ($2.69/h) :**
| Durée | Coût | Vidéos |
|-------|------|--------|
| 1h | $2.69 | 7 |
| 6h | $16.14 | 42 |

---

## Troubleshooting

| Problème | Solution |
|----------|----------|
| Pod ne démarre pas | Vérifier variables OwnCloud |
| Modèles non téléchargés | Vérifier credentials rclone |
| ComfyUI timeout | Vérifier VRAM GPU |
| CUDA out of memory | GPU supérieur ou réduire résolution |

### Logs

```bash
# Via runpodctl
./runpodctl logs <pod-id>
```

---

## Notes Importantes

### Architecture 14B MoE
- 2 fichiers requis : high_noise + low_noise
- Switching boundary=0.9 (10% high, 90% low)
- GPU 80GB+ obligatoire

### Sécurité
- Ne pas commit credentials dans Git
- Variables d'environnement Pod
- Limiter durée vie Pods

---

## Ressources

- [RunPod Documentation](https://docs.runpod.io)
- [runpodctl CLI](https://github.com/runpod/runpodctl)

---

**Version:** 4.4.0 | **Images:** `arnaudboy/comfy_img_to_loop:latest` (prod) / `:test` (debug) | **Date:** 2026-03-16
