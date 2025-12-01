# Architecture technique - GEGM MotionLab

**Dernière mise à jour** : 2025-12-01
**Objectif** : Référence technique compacte pour alimenter la mise à jour de `CLAUDE.md`

---

## Vue d'ensemble

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

### Flask (Port 5000)
- Interface web + API REST
- Queue de jobs asynchrone
- Communication WebSocket avec ComfyUI

**Fichiers clés** :
- `web_interface/app.py`, `routes.py`, `jobs.py`

### ComfyUI (Port 8188)
- Engine de génération WAN 2.2
- Custom nodes : WanVideoWrapper, PyramidFlowWrapper
- Format : ComfyUI Native (Comfy-Org)

**Chemins** :
- `/workspace/comfyui/ComfyUI/`

### Workflow Manager
- Sélection template (wan22_i2v, wan22_with_upscale)
- Détection modèle auto (5B vs 14B)
- Configuration paramètres

**Fichier** : `workflows/workflow_manager.py`

### Client WebSocket ComfyUI (v3.5.3)
- Communication bidirectionnelle Flask ↔ ComfyUI
- **Détection fin workflow** : Message `executing` avec `node = null` → marquer "completed"
- **Gestion messages binaires** : Skip proprement les images preview (évite erreurs UTF-32)
- **Normalisation progression** : Auto-détection format 0-1 vs 0-100
- **Récupération outputs** : Support clés "images" (SaveImage) ET "gifs" (VHS_VideoCombine)
- Monitoring temps réel des nœuds en exécution

**Fichier** : `src/comfyui_client.py`

**Points critiques** :
- Ligne 236-257 : Gestion messages binaires
- Ligne 271-290 : Normalisation progression
- Ligne 292-314 : Détection fin workflow (CRITIQUE)
- Ligne 487-546 : Récupération images/vidéos (CRITIQUE)

---

## Modèles WAN 2.2 (Format ComfyUI Native)

### Modèle 5B
- **Fichier** : `wan2.2_ti2v_5B_fp16.safetensors` (9.31 GB)
- **Résolution max** : 1280x720
- **GPU** : RTX 6000 Ada 48GB
- **Template** : `wan22_i2v.json`

### Modèle 14B
- **Fichiers** :
  - `wan2.2_i2v_high_noise_14B_fp8_scaled.safetensors`
  - `wan2.2_i2v_low_noise_14B_fp8_scaled.safetensors`
- **Résolution max** : 4K
- **GPU** : H100 SXM 80GB
- **Template** : `wan22_with_upscale.json`

### T5 Encoder (partagé 5B/14B)
- **Fichier** : `umt5_xxl_fp16.safetensors` (11.4 GB)
- **Format** : FP16 (officiellement supporté par WanVideoWrapper)
- **Clés** : 412

### VAE
- **Fichier** : `wan2.2_vae.safetensors` (~1 GB)
- **Canaux** : 48 (compatible natif)

---

## Chemins critiques (RunPod)

### Modèles
```
/workspace/comfyui/ComfyUI/models/checkpoints/wan2.2-ti2v-5b/
├── wan2.2_ti2v_5B_fp16.safetensors       # 9.31 GB
├── umt5_xxl_fp16.safetensors             # 11.4 GB
├── wan2.2_vae.safetensors                # ~1 GB
└── config.json
```

### Symlinks T5
```
/workspace/comfyui/ComfyUI/models/text_encoders/t5/
├── umt5_xxl_fp16.safetensors → (source)
└── umt5-xxl-enc-bf16.pth → (compatibilité)
```

### Output
```
/app/output/        # Vidéos générées
/app/uploads/       # Images uploadées
/app/logs/          # Logs application
```

---

## Workflow de démarrage (RunPod)

1. Affichage infos système (GPU, Python, PyTorch)
2. Download modèles OwnCloud (si absent)
3. Reconstitution fichiers découpés
4. Vérification intégrité (diffusion + T5 FP16)
5. Configuration symlinks (modèles, VAE, T5)
6. Download CLIP Vision + RealESRGAN
7. Démarrage ComfyUI (port 8188)
8. Health check (180s timeout)
9. Démarrage Flask (port 5000)

**Fichier** : `docker-entrypoint.sh`

---

## Variables d'environnement (RunPod)

### Obligatoires
```env
OWNCLOUD_SERVER_URL=https://www.cloud-gegm.com
OWNCLOUD_USERNAME=your-username
OWNCLOUD_PASSWORD=your-password
OWNCLOUD_MODEL_FOLDER=/GEGM_ComfyUI/Models
```

### Optionnelles
```env
OWNCLOUD_MODEL_NAME=wan2.2-ti2v-5b
FLASK_HOST=0.0.0.0
FLASK_PORT=5000
COMFYUI_HOST=127.0.0.1
COMFYUI_PORT=8188
```

---

## Stack technique

- **Python** : 3.11
- **Flask** : 3.0+
- **PyTorch** : 2.10.dev + CUDA 12.8
- **ComfyUI** : latest
- **Custom Nodes** : WanVideoWrapper, PyramidFlowWrapper, VideoHelperSuite
- **Format modèles** : SafeTensors (ComfyUI Native)
- **GPU** : NVIDIA 48GB+ VRAM

---

## Notes importantes

1. **Récupération vidéos** : get_output_images() DOIT chercher clés "gifs" (VHS_VideoCombine) ET "images" (SaveImage)
2. **Détection fin workflow** : Le client WebSocket DOIT détecter `node = null` (sinon timeout 600s)
3. **Messages binaires WebSocket** : Ignorer proprement les images preview pour éviter erreurs UTF-32
4. **T5 FP16** : Utilise FP16 (11.4 GB) officiellement supporté par WanVideoWrapper
5. **Workflows JSON** : Référencent les vrais fichiers `.safetensors` (pas de symlinks artificiels)
6. **Pas de patch nécessaire** : Architecture simplifiée, chargement natif
7. **Sélection auto** : Image ≤720p → 5B, >720p → 14B + upscale
8. **VRAM** : 48GB minimum (5B), 80GB (14B)
