# 🚀 GEGM MotionLab - Guide RunPod

**Déploiement cloud GPU professionnel sur RunPod**

[![RunPod](https://img.shields.io/badge/runpod-cloud-blueviolet.svg)](https://runpod.io)
[![GPU](https://img.shields.io/badge/GPU-RTX%206000%20Ada%20%2F%20H100-success.svg)](https://runpod.io)
[![Version](https://img.shields.io/badge/version-3.1.8-blue.svg)](CHANGELOG.md)

---

## 📋 Table des matières

1. [Présentation RunPod](#présentation-runpod)
2. [Choix GPU](#choix-gpu)
3. [Prérequis](#prérequis)
4. [Préparation Modèles (v3.1.8)](#préparation-modèles-v318)
5. [Build et Déploiement](#build-et-déploiement)
6. [Créer le Pod](#créer-le-pod)
7. [Utilisation Production](#utilisation-production)
8. [Gestion des Coûts](#gestion-des-coûts)
9. [Troubleshooting](#troubleshooting)

---

## 🌐 Présentation RunPod

**RunPod** est une plateforme cloud spécialisée en GPU computing avec facturation à la minute.

### Avantages

- ✅ GPUs haute-performance (RTX 6000 Ada 48GB, H100 SXM 80GB)
- ✅ Facturation à la minute (pas d'engagement)
- ✅ Déploiement rapide (<1 minute)
- ✅ Intégration Docker native
- ✅ API REST complète

### Inconvénients

- ❌ Coûts variables selon GPU ($0.77-$3.59/heure)
- ❌ Stockage Pod éphémère (destruction après arrêt)
- ❌ Modèles à télécharger au démarrage (~15-20 min)

**Recommandation :** Utiliser RunPod pour production / tests haute-performance uniquement.

---

## 🎮 Choix GPU

### Pour WAN 2.2 5B (Production Standard)

| GPU | VRAM | Temps/vidéo | Coût/h | Coût/vidéo | Vidéos/h |
|-----|------|-------------|--------|------------|----------|
| **RTX 6000 Ada** ⭐ | 48GB | ~5 min | $0.77 | $0.064 | 12 |
| **H100 SXM** | 80GB | ~2.5 min | $2.69 | $0.112 | 24 |
| **H200 SXM** | 141GB | ~2 min | $3.59 | $0.120 | 30 |

**Recommandation :** **RTX 6000 Ada** - Meilleur rapport coût/qualité

---

### Pour WAN 2.2 14B (Qualité Premium)

| GPU | VRAM | Temps/vidéo | Coût/h | Coût/vidéo | Vidéos/h |
|-----|------|-------------|--------|------------|----------|
| RTX 6000 Ada | 48GB | ❌ Trop petit | - | - | - |
| **H100 SXM** ⭐ | 80GB | ~8 min | $2.69 | $0.36 | 7 |
| **H200 SXM** | 141GB | ~5 min | $3.59 | $0.30 | 12 |

**Recommandation :** **H100 SXM** - Bon compromis coût/vitesse

---

## 🔧 Prérequis

### Services Cloud

- **Compte RunPod** : https://runpod.io (crédit carte requis)
- **OwnCloud** : Serveur avec 35+ GB espace libre
- **Docker Hub** (optionnel) : Pour push image custom

### Machine Locale

- **rclone** : Installé et configuré
- **Docker** : 20.10+ avec BuildX
- **Espace disque** : 100 GB libre

### Vérification

```bash
# rclone
rclone --version

# Docker
docker --version
docker buildx version
```

**Installation rclone :**
```bash
# macOS
brew install rclone

# Linux
curl https://rclone.org/install.sh | sudo bash

# Windows
# Télécharger depuis https://rclone.org/downloads/
```

---

## 📦 Préparation Modèles (v3.1.8)

**⏱️ Durée :** 60-90 minutes (dépend connexion)
**💾 Espace :** 30-40 GB local

### Étape 1: Configuration rclone

**Une seule fois :**

```bash
# Lancer configuration interactive
rclone config

# Créer remote "owncloud"
n) New remote
name> owncloud
Storage> webdav
URL> https://your-server.com
vendor> owncloud
user> your-username
password> your-password
bearer_token> (laisser vide)
(accepter le reste par défaut)
```

**Tester connexion :**
```bash
rclone ls owncloud:/GEGM_ComfyUI/Models/
```

---

### Étape 2: Workflow Complet (v3.1.8)

**Workflow automatisé avec fusion + double vérification :**

```bash
# 1. Téléchargement HuggingFace + Fusion + Vérifications
./scripts/setup_wan22_native.sh wan2.2-ti2v-5b

# Ce script exécute automatiquement :
# → Download depuis HuggingFace (23 fichiers, ~11 GB)
# → Fusion safetensors : 3 fichiers → 1 fichier (18.63 GB)
# → Vérification modèle diffusion (blocks.14.ffn.0.weight)
# → Vérification T5 Encoder (blocks.14.ffn.gate.0.weight)
# → Suppression fichiers sharded (économie 18.5 GB)

# 2. Conversion VAE + Upload OwnCloud
make full-workflow-5b

# Ce make exécute automatiquement :
# → Conversion VAE 96ch → 48ch
# → Découpe modèle diffusion fusionné (10 chunks de 2GB)
# → Découpe T5 Encoder (6 chunks de 2GB)
# → Suppression fichiers originaux (économie ~31 GB)
# → Upload OwnCloud (35 fichiers, ~31.8 GB)
# → Vérification upload
# → Nettoyage local (libération espace)
```

**Résultat :**
- ✅ 35 fichiers uploadés sur OwnCloud (~31.8 GB)
- ✅ Modèle diffusion fusionné (fichier unique)
- ✅ Double vérification (diffusion + T5)
- ✅ VAE converti (48 canaux)

---

### Vérification Upload

```bash
# Lister fichiers uploadés
make rclone-list

# Vérifier intégrité
make rclone-verify

# Compter fichiers
rclone ls owncloud:/GEGM_ComfyUI/Models/wan2.2-ti2v-5b/ | wc -l
# Devrait afficher: 35
```

---

## 🐳 Build et Déploiement

### Build Image Docker

```bash
# Build multi-arch + push Docker Hub
make runpod-deploy

# Équivalent manuel
docker buildx build \
  --platform linux/amd64,linux/arm64 \
  --file docker/Dockerfile \
  --tag arnaudboy/comfy_img_to_loop:latest \
  --tag arnaudboy/comfy_img_to_loop:3.1.8 \
  --push \
  .
```

**Tags créés :**
- `arnaudboy/comfy_img_to_loop:latest` (toujours la dernière)
- `arnaudboy/comfy_img_to_loop:3.1.8` (version spécifique)

---

### Build Rapide (AMD64 uniquement)

```bash
# Pour tests rapides
make runpod-deploy-quick

# Build uniquement AMD64
docker buildx build \
  --platform linux/amd64 \
  --file docker/Dockerfile \
  --tag arnaudboy/comfy_img_to_loop:latest \
  --push \
  .
```

**Temps de build :** 10-15 minutes

---

## 🚀 Créer le Pod

### Via Interface RunPod

1. **Aller sur** https://runpod.io/console/pods
2. **Cliquer** "Deploy" ou "+" (nouveau Pod)
3. **Sélectionner GPU** :
   - WAN 2.2 5B → **RTX 6000 Ada 48GB**
   - WAN 2.2 14B → **H100 SXM 80GB**
4. **Configuration Pod** :

```yaml
Container Image: arnaudboy/comfy_img_to_loop:latest
Container Disk: 100 GB (minimum)
Volume Disk: 0 GB (pas nécessaire)

Expose HTTP Ports: 5000

Environment Variables:
  OWNCLOUD_SERVER_URL=https://your-server.com
  OWNCLOUD_USERNAME=your-username
  OWNCLOUD_PASSWORD=your-password
  OWNCLOUD_MODEL_FOLDER=/GEGM_ComfyUI/Models
  LOG_LEVEL=INFO
```

5. **Deploy Pod**

---

### Temps Démarrage

```
00:00  → Pod créé
00:30  → Image Docker pulled
01:00  → Container démarré
02:00  → Download modèles OwnCloud commencé
15:00  → Reconstitution modèles terminée
16:00  → Symlinks T5 créés
17:00  → ComfyUI démarré
19:00  → Flask app ready ✅
```

**Total :** ~20 minutes

---

### Accéder au Pod

**URL générée automatiquement :**
```
https://<pod-id>-5000.proxy.runpod.net
```

**Exemple :**
```
https://abc123def456-5000.proxy.runpod.net
```

**Ports exposés :**
- **5000** : Interface web Flask
- **8188** : ComfyUI API (non exposé par défaut)

---

## 🎯 Utilisation Production

### Génération Cinemagraph

1. Ouvrir URL Pod dans navigateur
2. Uploader image (JPG/PNG)
3. Choisir preset ou ajuster paramètres
4. Cliquer "Générer"
5. Attendre ~5-8 min (selon GPU)
6. Télécharger vidéo MP4

---

### Monitoring

**Via Interface RunPod :**
- GPU usage (VRAM, utilisation)
- CPU/RAM
- Network I/O
- Logs container

**Via API :**
```bash
# Health check
curl https://<pod-id>-5000.proxy.runpod.net/health

# Statut job
curl https://<pod-id>-5000.proxy.runpod.net/api/jobs/<job_id>
```

---

### Logs

**Méthode 1 : Interface RunPod**
- Onglet "Logs" du Pod
- Stream temps réel

**Méthode 2 : runpodctl (CLI)**
```bash
# Installer runpodctl
curl -sL https://github.com/runpod/runpodctl/releases/latest/download/runpodctl-linux-amd64 \
  -o runpodctl && chmod +x runpodctl

# Voir logs
./runpodctl logs <pod-id>
```

---

## 💰 Gestion des Coûts

### Optimisation Coûts

**Stratégies :**
1. **Arrêter Pod après utilisation** (facturation minute)
2. **Utiliser RTX 6000 Ada pour 5B** (pas H100)
3. **Batch processing** (traiter plusieurs images)
4. **Auto-stop** (configurer timeout inactivité)

---

### Calcul Coûts

**Exemple session 6h - RTX 6000 Ada ($0.77/h) :**

| Durée | Coût | Vidéos (5 min/vidéo) | Coût/vidéo |
|-------|------|----------------------|-----------|
| 1h | $0.77 | 12 | $0.064 |
| 3h | $2.31 | 36 | $0.064 |
| 6h | $4.62 | 72 | $0.064 |

**Exemple session 6h - H100 SXM ($2.69/h) :**

| Durée | Coût | Vidéos (8 min/vidéo) | Coût/vidéo |
|-------|------|----------------------|-----------|
| 1h | $2.69 | 7 | $0.38 |
| 3h | $8.07 | 21 | $0.38 |
| 6h | $16.14 | 42 | $0.38 |

---

### Alerte Coûts

**Configuration recommandée :**
- Limite dépense journalière : $50
- Alerte email : 80% limite
- Auto-stop inactivité : 30 minutes

---

## 🐛 Troubleshooting

### Pod ne démarre pas

**Symptôme :** Container status "Exited" ou "Error"

**Diagnostic :**
```bash
# Voir logs
runpodctl logs <pod-id>

# Dans interface RunPod
# Onglet "Logs" → Voir erreurs
```

**Causes fréquentes :**
- Variables OwnCloud manquantes/incorrectes
- Container Disk insuffisant (<100GB)
- Image Docker non trouvée

---

### Modèles ne se téléchargent pas

**Symptôme :** Pod démarre mais reste à "Downloading models..."

**Solutions :**
```bash
# Vérifier credentials OwnCloud dans variables Pod

# Tester connexion rclone manuellement
# Dans container :
rclone ls owncloud:/GEGM_ComfyUI/Models/

# Vérifier espace disque
df -h
```

**Fix :**
- Corriger variables OwnCloud
- Augmenter Container Disk (>100GB)
- Vérifier firewall OwnCloud

---

### ComfyUI timeout

**Symptôme :** "ComfyUI failed to start after 3 minutes"

**Diagnostic :**
```bash
# Voir logs ComfyUI
tail -f /workspace/logs/comfyui.log

# Vérifier symlink T5
ls -la /workspace/comfyui/ComfyUI/models/text_encoders/t5/
readlink /workspace/comfyui/ComfyUI/models/text_encoders/t5/umt5-xxl-enc-bf16.pth
```

**Solutions :**
- Vérifier modèles présents
- Vérifier symlink T5 (doit pointer vers fichier existant)
- Vérifier VRAM GPU (48GB+ requis)

---

### Génération échoue

**Symptôme :** Job status "failed" avec erreur

**Erreurs fréquentes :**

| Erreur | Cause | Solution |
|--------|-------|----------|
| `KeyError: 'blocks.14.ffn.0.weight'` | Modèle diffusion non fusionné | Re-uploader modèle (v3.1.8) |
| `CUDA out of memory` | VRAM insuffisante | Réduire résolution/steps |
| `Expected 48 channels, got 96` | VAE non converti | Re-uploader modèle (v3.1.8) |

**Fix :**
```bash
# Re-uploader modèle avec fusion (v3.1.8)
./scripts/setup_wan22_native.sh wan2.2-ti2v-5b
make full-workflow-5b

# Rebuild image Docker
make runpod-deploy

# Redéployer Pod avec nouvelle image
```

---

### VRAM insuffisante

**Symptôme :** `RuntimeError: CUDA out of memory`

**Solutions :**
1. Choisir GPU supérieur (H100 vs RTX 6000)
2. Réduire résolution image source
3. Réduire steps (20→15)
4. Redémarrer Pod (libère VRAM)

---

### Pod lent/lag

**Causes :**
- GPU overloadé (autres Pods sur même machine)
- Réseau saturé
- Disque I/O

**Solutions :**
- Choisir région différente
- Stopper/redémarrer Pod
- Filtrer "Community Cloud" vs "Secure Cloud"

---

## 📊 Benchmarks

### WAN 2.2 5B - RTX 6000 Ada

| Résolution | Steps | CFG | Temps | VRAM |
|------------|-------|-----|-------|------|
| 640x480 | 15 | 7.0 | ~3 min | 18 GB |
| 1280x720 | 20 | 7.5 | ~5 min | 32 GB |
| 1920x1080 | 25 | 8.0 | ~8 min | 45 GB |

---

### WAN 2.2 14B - H100 SXM

| Résolution | Steps | CFG | Temps | VRAM |
|------------|-------|-----|-------|------|
| 1280x720 | 20 | 7.5 | ~5 min | 48 GB |
| 1920x1080 | 25 | 8.0 | ~8 min | 62 GB |
| 3840x2160 (4K) | 30 | 8.5 | ~15 min | 76 GB |

---

## 📝 Notes Importantes

### Workflow v3.1.8

**Points critiques :**
1. **Fusion safetensors** : AVANT upload (pas sur Pod)
2. **Double vérification** : Modèle diffusion + T5 Encoder
3. **VAE converti** : 96ch → 48ch (automatique)
4. **Symlinks absolus** : T5 Encoder (chemins complets)

**Fichiers uploadés (35 total) :**
- 10 chunks modèle diffusion fusionné (2GB chacun)
- 6 chunks T5 Encoder (2GB chacun)
- 19 fichiers config/metadata

---

### Sécurité

**Bonnes pratiques :**
- Ne pas commit credentials OwnCloud dans Git
- Utiliser variables d'environnement Pod
- Limiter durée vie Pods (auto-stop)
- Backup vidéos régulièrement

---

### Performance

**Optimisations :**
- Réseau : Choisir région proche OwnCloud
- GPU : Filtrer "High Availability" si critique
- Disque : NVMe si disponible (Container Disk)

---

## 🔗 Ressources

- [RunPod Documentation](https://docs.runpod.io)
- [RunPod API Reference](https://graphql-spec.runpod.io)
- [runpodctl CLI](https://github.com/runpod/runpodctl)
- [RunPod Community](https://discord.gg/runpod)

---

**Version actuelle :** 3.1.8 (2025-11-14)
**Image Docker :** `arnaudboy/comfy_img_to_loop:latest`
**Workflow :** Fusion safetensors + double vérification ✅
