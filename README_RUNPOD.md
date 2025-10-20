# 🚀 Comfy_Img_to_Loop - Déploiement RunPod B200/H200

Guide complet de déploiement sur RunPod avec GPUs B200/H200.

**✨ NOUVEAUTÉ : Modèles AI PRÉ-INSTALLÉS dans l'image Docker**

## 📋 Prérequis

- **GPU**: B200 (96GB VRAM) ou H200 (141GB VRAM)
- **CUDA**: 12.8.1 (pré-installé dans l'image)
- **Stockage local**: 30GB pour les modèles WAN 2.2
- **Connexion**: Bonne connexion pour push Docker (~35GB)

---

## 📦 Préparation Locale (Une fois seulement)

### Étape 1: Télécharger les Modèles WAN 2.2

**Important** : Les modèles doivent être téléchargés **AVANT** de build l'image Docker.

```
# Activer l'environnement virtuel

source .venv/bin/activate

# Exécuter le script de setup (choix interactif)

./scripts/setup_wan22_native.sh
```

**Choix recommandé pour RunPod :**
- **Option 2** : WAN 2.2 I2V 14B (27.8GB, pour B200/H200)

**Structure attendue après téléchargement :**
```
models/
└── wan2.2-i2v-a14b/
├── high_noise_model/
│   ├── diffusion_pytorch_model-00001-of-00006.safetensors
│   ├── diffusion_pytorch_model-00002-of-00006.safetensors
│   ├── diffusion_pytorch_model-00003-of-00006.safetensors
│   ├── diffusion_pytorch_model-00004-of-00006.safetensors
│   ├── diffusion_pytorch_model-00005-of-00006.safetensors
│   ├── diffusion_pytorch_model-00006-of-00006.safetensors
│   └── diffusion_pytorch_model.safetensors.index.json
├── models_t5_umt5-xxl-enc-bf16.pth
├── Wan2.1_VAE.pth
└── google/umt5-xxl/...
```

### Vérification

```
# Vérifier la présence des modèles

ls -lh models/wan2.2-i2v-a14b/high_noise_model/

# Vérifier la taille totale

du -sh models/wan2.2-i2v-a14b/

```
Vous devriez voir **~28-30GB** au total.

---

## 🐳 Build et Déploiement

### Étape 2: Build l'Image Docker (avec modèles inclus)

```
# Build l'image (inclut automatiquement les modèles du dossier models/)

docker build -t arnaudboy/comfy_img_to_loop:runpod .

# Le build peut prendre 10-20 minutes

# L'image finale fera ~35-40GB
```

**Pendant le build, Docker va :**
1. Installer les dépendances système
2. Installer PyTorch avec CUDA 12.8
3. Cloner et installer ComfyUI
4. **COPIER vos modèles locaux dans l'image**
5. Vérifier la présence des modèles

### Étape 3: Vérifier l'Image

```
# Vérifier la taille de l'image

docker images | grep arnaudboy/comfy_img_to_loop

# Devrait afficher ~35-40GB
```

### Étape 4: Push vers Docker Hub

```
# Login Docker Hub

docker login

# Push l'image (peut prendre 30-90 minutes selon connexion)

docker push arnaudboy/comfy_img_to_loop:runpod
```

**⏱️ Temps estimés de push :**
- 100 Mbps : ~1h30
- 500 Mbps : ~20 min
- 1 Gbps : ~10 min

---

## 🚀 Déploiement sur RunPod

### Étape 5: Créer le Pod

1. Aller sur https://runpod.io
2. Cliquer sur **"Deploy"**
3. Sélectionner:
   - **GPU**: B200 ou H200
   - **Container Image**: `arnaudboy/comfy_img_to_loop:runpod`
   - **Container Disk**: 10GB minimum (pour uploads/logs)
   - **Volume Storage**: Optionnel (modèles déjà dans l'image)
   - **Expose HTTP Ports**: `5000`

4. **Variables d'environnement** (section Environment Variables):

```
OWNCLOUD_SERVER_URL=https://www.cloud-gegm.com
OWNCLOUD_USERNAME=votre-username
OWNCLOUD_PASSWORD=votre-password
OWNCLOUD_MODEL_FOLDER=/GEGM_ComfyUI/Models
LOG_LEVEL=INFO
```

5. **Démarrer le Pod**

---

## ⚡ Démarrage Instant

**✨ AVANTAGE MAJEUR :** Les modèles sont déjà dans l'image Docker !

Lors du premier démarrage (~30-60 secondes) :
```
🚀 Starting Comfy_Img_to_Loop on RunPod B200/H200...
🎮 GPU: NVIDIA B200 (96GB VRAM)
📦 ComfyUI already installed
✅ Models found in image:

- WAN 2.2 I2V 14B: 27.8GB
- High noise model: ✅
- VAE: ✅
- Text encoders: ✅
🎨 Starting ComfyUI...
🎬 Comfy_Img_to_Loop is ready!
Web Interface: https://xxxx-5000.proxy.runpod.net
```

---

## 🌐 Accès à l'Interface

RunPod génère automatiquement une URL publique :

```
https://your-pod-id-5000.proxy.runpod.net
```

### Test Health Check

```
curl https://your-pod-id-5000.proxy.runpod.net/health
```

**Réponse attendue :**

```
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

## 📊 Comparaison : Avec vs Sans Modèles Inclus

| Aspect | Sans Modèles | **Avec Modèles Inclus** |
|--------|-------------|------------------------|
| **Démarrage** | 15-20 min | ✅ **30-60 secondes** |
| **Téléchargement** | À chaque Pod | ✅ **Jamais** |
| **Taille image** | ~7GB | ~35-40GB |
| **Coûts démarrage** | +$1-2 | ✅ **$0** |
| **Fiabilité** | Dépend réseau | ✅ **100%** |
| **Version modèles** | Variable | ✅ **Fixée** |

---

## 💰 Coûts RunPod

| GPU | VRAM | Prix/h | Démarrage |
|-----|------|--------|-----------|
| **B200** | 96GB | ~$3.99 | Instant ✅ |
| **H200** | 141GB | ~$4.99 | Instant ✅ |

**Économie** : ~$1-2 économisés par démarrage (pas de download)

---

## 🔧 Utilisation

### Générer un Cinemagraph

1. Aller sur l'interface web RunPod
2. Upload une image
3. Définir le prompt (ex: "gentle and natural water movement...")
4. Ajuster les paramètres (steps, fps, frames)
5. Cliquer sur "Générer"

Le résultat sera automatiquement uploadé sur OwnCloud avec un lien de partage.

---

## 🐛 Troubleshooting

### Modèles manquants au démarrage

```
# Se connecter au Pod via SSH

# Vérifier la présence des modèles

ls -lh /workspace/comfyui/ComfyUI/models/diffusion_models/wan2.2-i2v-a14b/
```

Si les modèles sont absents, le build Docker n'a pas copié les modèles locaux.

**Solution :**
1. Vérifier que `models/wan2.2-i2v-a14b/` existe localement
2. Vérifier que `.dockerignore` ne bloque pas `models/`
3. Rebuild l'image

### Image trop volumineuse pour push

Si votre connexion est lente pour push 35GB :

**Option A :** Push depuis un serveur avec meilleure connexion
**Option B :** Utiliser Docker Hub automated build (upload code, build dans le cloud)

### ComfyUI ne démarre pas

```
# Voir les logs ComfyUI

cat /workspace/logs/comfyui.log

# Redémarrer ComfyUI

pkill -f "python main.py"
cd /workspace/comfyui/ComfyUI
python main.py --listen 0.0.0.0 --port 8188
```

---

## ✅ Checklist de Déploiement

- [ ] Modèles WAN 2.2 téléchargés localement (`./scripts/setup_wan22_native.sh`)
- [ ] Modèles vérifiés dans `models/wan2.2-i2v-a14b/` (~28GB)
- [ ] Image Docker buildée (~35-40GB)
- [ ] Image pushée sur Docker Hub
- [ ] Pod RunPod créé avec B200/H200
- [ ] Variables d'environnement OwnCloud configurées
- [ ] Health check répond "healthy"
- [ ] Test de génération réussi
- [ ] Upload OwnCloud fonctionnel

---

## 🎯 Workflow Complet Résumé

```
# 1. Télécharger les modèles (une fois, 30-60 min)

source .venv/bin/activate
./scripts/setup_wan22_native.sh

# Choisir option 2 (WAN 2.2 I2V 14B)

# 2. Vérifier les modèles

du -sh models/wan2.2-i2v-a14b/

# Devrait afficher ~28-30GB

# 3. Build Docker avec modèles inclus (10-20 min)

docker build -t arnaudboy/comfy_img_to_loop:runpod .

# 4. Push vers Docker Hub (30-90 min selon connexion)

docker login
docker push arnaudboy/comfy_img_to_loop:runpod

# 5. Déployer sur RunPod

# → Interface web RunPod

# → Image: votre-user/comfy:runpod

# → GPU: B200 ou H200

# → Env vars: OwnCloud credentials

# 6. Accès immédiat

# → Pod prêt en 30-60 secondes

# → Générer des cinemagraphs instantanément
```

---

## 🆘 Support

- **RunPod Discord**: https://discord.gg/runpod
- **Issues GitHub**: https://github.com/your-org/comfy_img_to_loop
- **Contact**: arnaud.boy@gegmgroup.com

---

## 📝 Notes Importantes

- Les modèles WAN 2.2 sont sous licence **Apache 2.0** (usage commercial autorisé)
- L'image Docker finale fait ~35-40GB (normal avec modèles inclus)
- Le push vers Docker Hub peut prendre du temps mais se fait **une seule fois**
- Une fois sur RunPod, le démarrage est **instantané** (30-60s)
- Pas besoin de volume persistant pour les modèles (déjà dans l'image)