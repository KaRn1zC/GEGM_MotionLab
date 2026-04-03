# GEGM MotionLab - Guide RunPod

**Déploiement cloud GPU sur RunPod**

[![RunPod](https://img.shields.io/badge/runpod-cloud-blueviolet.svg)](https://runpod.io)
[![GPU](https://img.shields.io/badge/GPU-RTX%206000%20%2F%20H100-success.svg)](https://runpod.io)
[![Version](https://img.shields.io/badge/version-5.1.0-blue.svg)](CHANGELOG.md)

---

## Choix GPU

### GPU 48GB+ (WAN 5B)

| Priorité | GPU              | VRAM | WAN 5B  |
| -------- | ---------------- | ---- | ------- |
| 1        | **RTX 6000 Ada** | 48GB | ~10 min |
| 2        | **L40**          | 48GB | ~10 min |
| 3        | **L40S**         | 48GB | ~10 min |

### GPU 80GB+ (WAN 14B / LTX 2.3 22B)

| Priorité | GPU                 | VRAM | WAN 14B | LTX 2.3 22B |
| -------- | ------------------- | ---- | ------- | ----------- |
| 1        | **RTX Pro 6000**    | 96GB | ~28 min | ~13 min     |
| 2        | **RTX Pro 6000 WK** | 96GB | ~28 min | ~13 min     |
| 3        | **H100 SXM**        | 80GB | ~28 min | ~13 min     |

---

## Prérequis

### Services
- **RunPod** : Compte avec crédit
- **OwnCloud** : Serveur avec 50+ GB

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

### Workflow Complet (un seul modèle)

```bash
# WAN 2.2
make workflow MODEL=wan2.2-ti2v-5b     # ou wan2.2-i2v-a14b

# LTX 2.3
make workflow MODEL=ltx-2.3-i2v-dev
```

Chaque workflow : Download HF → Vérification intégrité → Upload OwnCloud → Deep clean local.

### Workflows séquentiels (plusieurs modèles)

```bash
make workflow-wan-all      # WAN 14B puis 5B
make workflow-all          # Tous les modèles (3)
```

### Vérification Upload

```bash
make rclone-verify MODEL=wan2.2-ti2v-5b
make rclone-verify MODEL=ltx-2.3-i2v-dev
rclone ls owncloud:/GEGM_ComfyUI/Models/
```

---

## Build et Déploiement

### Production (branche main)

```bash
make runpod-deploy           # Build + push → :latest
make runpod-deploy-nocache   # Idem sans cache (rebuild complet)
```

**Image :** `arnaudboy/comfy_img_to_loop:latest`

### Test (branche debug)

```bash
make runpod-deploy-test           # Build + push → :test
make runpod-deploy-test-nocache   # Idem sans cache (rebuild complet)
```

**Image :** `arnaudboy/comfy_img_to_loop:test`

### Workflow deux branches

```bash
# PRODUCTION — code stable validé
git checkout main
make runpod-deploy       # → arnaudboy/comfy_img_to_loop:latest

# TEST — expérimentation
git checkout debug
make runpod-deploy-test  # → arnaudboy/comfy_img_to_loop:test
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

- **WAN 5B :** RTX 6000 Ada, L40, L40S (48GB+)
- **WAN 14B / LTX 2.3 22B :** RTX Pro 6000, RTX Pro 6000 WK, H100 SXM (80GB+)

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
4. Générer (~10-28 min selon modèle)
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
- RTX 6000 Ada pour WAN 5B (pas H100)
- Batch processing
- Auto-stop inactivité

### Calcul

**RTX 6000 Ada ($0.77/h) :**
| Durée | Coût  | Vidéos (LTX) | Vidéos (WAN 5B) |
| ----- | ----- | ------------ | --------------- |
| 1h    | $0.77 | 30           | 12              |
| 6h    | $4.62 | 180          | 72              |

**H100 SXM ($2.69/h) :**
| Durée | Coût   | Vidéos (LTX) | Vidéos (WAN 14B) |
| ----- | ------ | ------------ | ---------------- |
| 1h    | $2.69  | 30           | 7                |
| 6h    | $16.14 | 180          | 42               |

---

## Troubleshooting

| Problème                | Solution                            |
| ----------------------- | ----------------------------------- |
| Pod ne démarre pas      | Vérifier variables OwnCloud         |
| Modèles non téléchargés | Vérifier credentials rclone         |
| ComfyUI timeout         | Vérifier VRAM GPU                   |
| CUDA out of memory      | GPU supérieur ou réduire résolution |

### Logs

```bash
# Via runpodctl
./runpodctl logs <pod-id>
```

---

## Notes Importantes

### Architecture WAN 14B MoE
- 2 fichiers requis : high_noise + low_noise
- Switching boundary=0.9 (10% high, 90% low)
- GPU 80GB+ obligatoire

### Architecture LTX 2.3
- Checkpoint unique avec VAE intégré
- Text encoder Gemma 3 12B (pas T5)
- Boucle seamless native (LTXVLoopingSampler)

### Sécurité
- Ne pas commit credentials dans Git
- Variables d'environnement Pod
- Limiter durée vie Pods

---

## Ressources

- [RunPod Documentation](https://docs.runpod.io)
- [runpodctl CLI](https://github.com/runpod/runpodctl)

---

**Version:** 5.1.0 | **Images:** `arnaudboy/comfy_img_to_loop:latest` (prod) / `:test` (debug) | **Date:** 2026-03-17
