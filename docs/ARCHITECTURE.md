# Architecture technique - GEGM MotionLab

**Dernière mise à jour** : 2025-11-26

---

## Vue d'ensemble

GEGM MotionLab est un studio professionnel de création de cinemagraphs propulsé par WAN 2.2, transformant des images statiques en boucles vidéo fluides.

```
┌─────────────────────────────────────────────────────────────┐
│                    GEGM MotionLab                           │
├─────────────────────────────────────────────────────────────┤
│                                                             │
│  ┌──────────────┐        ┌──────────────┐                  │
│  │    Flask     │◄──────►│   ComfyUI    │                  │
│  │   (5000)     │ WebSocket│   (8188)    │                  │
│  └──────────────┘        └──────────────┘                  │
│         │                        │                          │
│         │                        │                          │
│  ┌──────▼──────┐        ┌───────▼────────┐                │
│  │  Web UI     │        │  WAN 2.2 Model │                │
│  │  Job Queue  │        │  T5 Encoder    │                │
│  │  OwnCloud   │        │  VAE 48ch      │                │
│  └─────────────┘        └────────────────┘                │
│                                                             │
└─────────────────────────────────────────────────────────────┘
```

---

## Composants principaux

### 1. Flask Application (Port 5000)

**Fichiers** :
- `web_interface/app.py` : Application principale
- `web_interface/routes.py` : API REST endpoints
- `web_interface/jobs.py` : Queue de jobs asynchrone

**Responsabilités** :
- Interface web utilisateur
- Gestion de la queue de génération
- Upload/download de fichiers
- Communication avec ComfyUI via WebSocket

**Endpoints principaux** :
- `POST /api/generate` : Lancer une génération
- `GET /api/jobs/<job_id>` : Statut d'un job
- `GET /api/download/<job_id>` : Télécharger vidéo générée

### 2. ComfyUI Engine (Port 8188)

**Installation** : Via `install-comfyui.sh`

**Custom Nodes** :
- `ComfyUI-WanVideoWrapper` : Intégration WAN 2.2

**Responsabilités** :
- Chargement des modèles (diffusion, T5, VAE)
- Exécution des workflows de génération
- Génération frame par frame
- Upscale pyramidal (si résolution > 720p)

**API** :
- WebSocket `/ws` : Monitoring temps réel
- `POST /prompt` : Soumission workflow
- `GET /system_stats` : Health check

### 3. Workflow Manager

**Fichier** : `workflows/workflow_manager.py`

**Responsabilités** :
- Chargement des templates (wan22_i2v, wan22_with_upscale)
- Détection automatique du modèle (5B vs 14B)
- Configuration des paramètres (résolution, frames, seed)
- Sélection du workflow selon résolution

**Templates** :
- `wan22_i2v.json` : Standard (≤720p)
- `wan22_with_upscale.json` : Avec upscale pyramidal (>720p)

### 4. ComfyUI Client

**Fichier** : `src/comfyui_client.py`

**Responsabilités** :
- Connexion WebSocket avec ComfyUI
- Soumission de workflows
- Monitoring de progression
- Récupération des vidéos générées

**Fonctionnement** :
1. Connexion WebSocket
2. Upload image
3. Soumission workflow
4. Monitoring messages (execution_start, executing, executed, execution_error)
5. Récupération fichier généré

---

## Flux de génération complet

### 1. Soumission utilisateur

```
Utilisateur → Upload image → Flask
                             ↓
                      Analyse résolution
                             ↓
                   Création job (UUID)
                             ↓
                    Queue "processing"
```

### 2. Préparation workflow

```
Job Manager → Workflow Manager
                     ↓
           Détection modèle (5B/14B)
                     ↓
        Sélection template (i2v / upscale)
                     ↓
         Configuration paramètres
              (résolution, frames, seed)
                     ↓
              Workflow JSON prêt
```

### 3. Exécution ComfyUI

```
ComfyUI Client → Upload image vers ComfyUI
                        ↓
                 Soumission workflow
                        ↓
              ComfyUI traite le workflow:
                        ↓
          ┌─────────────┴─────────────┐
          ↓                           ↓
    Load Image (10)          Load T5 Encoder (5)
          ↓                           ↓
    Load Diffusion Model         Encode Text
          ↓                           ↓
          └────────►Génération◄───────┘
                        ↓
                  120 frames générés
                        ↓
              Upscale (si >720p)
                        ↓
                  Encode MP4
                        ↓
              Vidéo sauvegardée
```

### 4. Récupération résultat

```
ComfyUI → Notification "execution_success"
             ↓
    ComfyUI Client récupère fichier
             ↓
         Sauvegarde dans /app/output/
             ↓
    Job statut → "completed"
             ↓
    Utilisateur télécharge MP4
```

---

## Modèles et encodeurs

### Format ComfyUI Native (Comfy-Org)

#### Modèle 5B
- **Fichier** : `wan2.2_ti2v_5B_fp16.safetensors` (9.31 GB)
- **Résolution max** : 1280x720
- **GPU requis** : RTX 6000 Ada 48GB ou équivalent
- **Temps de génération** : ~5 minutes (120 frames)

#### Modèle 14B
- **Fichier** : `wan2.2_i2v_high_noise_14B_fp8_scaled.safetensors` + `wan2.2_i2v_low_noise_14B_fp8_scaled.safetensors`
- **Résolution max** : 4K
- **GPU requis** : H100 SXM 80GB
- **Temps de génération** : ~8 minutes

#### T5 Encoder (partagé 5B/14B)
- **Fichier** : `umt5_xxl_fp8_e4m3fn_scaled.safetensors` (6.27 GB)
- **Format** : FP8 quantized (SafeTensors)
- **Clés** : 412
- **Particularité** : Nécessite patch ComfyUI pour chargement correct

#### VAE
- **Fichier** : `wan2.2_vae.safetensors`
- **Canaux** : 48 (compatible natif ComfyUI)
- **Taille** : ~1 GB

---

## Patch ComfyUI pour safetensors FP8

### Problématique

ComfyUI peut mal détecter les fichiers safetensors FP8 et essayer de les charger avec `torch.load()` (format pickle) au lieu de `safetensors.torch.load_file()`, causant une erreur `_pickle.UnpicklingError`.

### Solution : `scripts/patch_comfyui_torch_load.py` (v3)

**Fonctionnement** :
1. Détecte la fonction `load_torch_file()` dans `comfy/utils.py`
2. Remplace la ligne `torch.load()` par un bloc conditionnel :
   - **Si fichier safetensors** : Utilise `safetensors.torch.load_file()`
   - **Sinon** : Utilise `torch.load()` avec `weights_only=False`

**Détection robuste** :
```python
# Normalisation du chemin
ckpt_str = str(ckpt) if not isinstance(ckpt, str) else ckpt
ckpt_normalized = os.normpath(ckpt_str)

# Détection double
is_safetensors = ckpt_normalized.endswith('.safetensors') or '.safetensors' in ckpt_normalized
```

**Application** : Automatique au démarrage via `docker-entrypoint.sh` (ligne 280)

**Vérification** : Logs doivent montrer :
```
✅ Patch appliqué avec succès
   - Détection robuste des fichiers safetensors (normalisation chemin)
   - Force safetensors.torch.load_file() pour fichiers .safetensors
```

---

## Scripts critiques

### `docker-entrypoint.sh`

**Rôle** : Orchestration du démarrage sur RunPod

**Étapes** :
1. Affichage infos système (GPU, Python, PyTorch)
2. Téléchargement modèles depuis OwnCloud (si absent)
3. Reconstitution fichiers découpés
4. Vérification intégrité (diffusion + T5)
5. Configuration symlinks (modèles, VAE, T5)
6. Téléchargement CLIP Vision + RealESRGAN
7. **Application patch ComfyUI (CRITIQUE)**
8. Démarrage ComfyUI (port 8188)
9. Health check (180s timeout)
10. Démarrage Flask (port 5000)

### `scripts/download_models_from_owncloud.py`

**Rôle** : Téléchargement et vérification modèles

**Fonctionnement** :
1. Configuration rclone avec credentials OwnCloud
2. Download via rclone sync
3. Reconstitution fichiers découpés (si chunks présents)
4. Vérification format ComfyUI Native (prioritaire)
5. Vérification T5 Encoder (intégrité)

**Formats détectés** :
- **Priorité 1** : ComfyUI Native (wan2.2_ti2v_5B_fp16.safetensors)
- **Priorité 2** : Format fusionné local (diffusion_pytorch_model.safetensors)
- **Fallback** : Format sharded (obsolète)

### `scripts/reassemble_models.sh`

**Rôle** : Reconstitution fichiers découpés

**Fonctionnement** :
1. Lit `chunks/mapping.txt`
2. Concatène les chunks avec `cat`
3. Supprime les chunks après reconstitution

### `workflows/workflow_manager.py`

**Rôle** : Gestion des workflows ComfyUI

**Fonctions clés** :
- `_detect_available_model()` : Détecte quel modèle est présent (5B/14B)
- `_get_model_checkpoint_path()` : Retourne le chemin du checkpoint selon le modèle
- `prepare_workflow()` : Configure le workflow avec les paramètres utilisateur

---

## Communication ComfyUI ↔ Flask

### WebSocket Protocol

**Messages ComfyUI → Flask** :
- `execution_start` : Début d'exécution d'un workflow
- `executing` : Exécution d'un nœud spécifique
- `executed` : Nœud terminé avec succès
- `execution_cached` : Nœuds en cache utilisés
- `execution_error` : Erreur lors de l'exécution
- `execution_success` : Workflow terminé avec succès

**Messages Flask → ComfyUI** :
- `POST /prompt` : Soumission d'un workflow JSON

---

## Déploiement

### Local (développement)

```bash
# Installation dépendances
pip install -r requirements.txt

# Download modèles
./scripts/setup_wan22_native.sh wan2.2-ti2v-5b
make full-workflow-5b

# Démarrage
docker-compose up
```

### RunPod (production)

```bash
# Build image
make runpod-deploy

# Déploiement
1. GPU: RTX 6000 Ada (5B) ou H100 (14B)
2. Image: arnaudboy/comfy_img_to_loop:latest
3. Container Disk: 100GB min
4. Expose: Port 5000
5. Variables env: OWNCLOUD_* (config/owncloud.yaml)
```

**Temps de démarrage** : 15-20 minutes (download modèles)

---

## Variables d'environnement

### Obligatoires (RunPod)
```env
OWNCLOUD_SERVER_URL=https://www.cloud-gegm.com
OWNCLOUD_USERNAME=your-username
OWNCLOUD_PASSWORD=your-password
OWNCLOUD_MODEL_FOLDER=/GEGM_ComfyUI/Models
```

### Optionnelles
```env
OWNCLOUD_MODEL_NAME=wan2.2-ti2v-5b  # ou wan2.2-i2v-a14b
FLASK_HOST=0.0.0.0
FLASK_PORT=5000
COMFYUI_HOST=127.0.0.1
COMFYUI_PORT=8188
LOG_LEVEL=INFO
```

---

## Chemins critiques (RunPod)

### Modèles
```
/workspace/comfyui/ComfyUI/models/checkpoints/wan2.2-ti2v-5b/
├── wan2.2_ti2v_5B_fp16.safetensors       # Modèle diffusion
├── umt5_xxl_fp8_e4m3fn_scaled.safetensors # T5 Encoder
├── wan2.2_vae.safetensors                 # VAE 48ch
└── config.json
```

### Symlinks
```
# Diffusion models
/workspace/comfyui/ComfyUI/models/diffusion_models/wan2.2-ti2v-5b
→ /workspace/comfyui/ComfyUI/models/checkpoints/wan2.2-ti2v-5b

# VAE
/workspace/comfyui/ComfyUI/models/vae/wan2.2_vae.safetensors
→ /workspace/comfyui/ComfyUI/models/checkpoints/wan2.2-ti2v-5b/wan2.2_vae.safetensors

# T5 Encoder
/workspace/comfyui/ComfyUI/models/text_encoders/t5/umt5_xxl_fp8_e4m3fn_scaled.safetensors
→ /workspace/comfyui/ComfyUI/models/checkpoints/wan2.2-ti2v-5b/umt5_xxl_fp8_e4m3fn_scaled.safetensors
```

### Output
```
/app/output/        # Vidéos générées
/app/uploads/       # Images uploadées
/app/logs/          # Logs application
```

---

## Stack technique

### Backend
- Python 3.11
- Flask 3.0+
- PyTorch 2.10.dev (CUDA 12.8)
- safetensors (chargement FP8)

### ComfyUI
- ComfyUI (latest)
- ComfyUI-WanVideoWrapper (custom nodes)
- diffusers, transformers (HuggingFace)

### Infrastructure
- Docker multi-arch (AMD64 + ARM64)
- NVIDIA CUDA 12.8.1
- Ubuntu 22.04

### Storage
- OwnCloud (modèles)
- rclone (sync)

---

## Performance

### Modèle 5B (RTX 6000 Ada 48GB)
- **Résolution** : 720x450 → 3456x2160 (upscale)
- **Frames** : 120 @ 24fps = 5 secondes
- **Temps** : ~5-7 minutes
- **VRAM** : ~35-40 GB

### Modèle 14B (H100 SXM 80GB)
- **Résolution** : Jusqu'à 4K
- **Frames** : 120 @ 24fps = 5 secondes
- **Temps** : ~8-10 minutes
- **VRAM** : ~65-70 GB
