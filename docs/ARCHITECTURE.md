# Architecture technique - GEGM MotionLab

**Dernière mise à jour** : 2025-12-24 (v3.16.0 - Fix Précision Modèles FP16)
**Objectif** : Référence technique compacte pour alimenter la mise à jour de `CLAUDE.md`

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
  - `wan2.2_i2v_high_noise_14B_fp16.safetensors` (~28.6 GB)
  - `wan2.2_i2v_low_noise_14B_fp16.safetensors` (~28.6 GB)
- **Résolution max native** : **720p** (identique 5B, upscale requis pour >720p)
- **GPU** : H100 SXM 80GB
- **Qualité** : Supérieure au 5B (MoE architecture + FP16)
- **Template** : `wan22_14b_with_upscale.json` (architecture différente du 5B)
- **Architecture workflow** : `WanVideoImageToVideoEncode` (1-node legacy)

### T5 Encoder (partagé 5B/14B)
- **Fichier** : `umt5_xxl_fp16.safetensors` (11.4 GB)
- **Format** : FP16 (officiellement supporté par WanVideoWrapper)
- **Clés** : 412

### VAE (CRITIQUE - Spécifiques par modèle)
- **5B** : `wan2.2_vae.safetensors` (1.41 GB, 48 canaux, compression 16×16×4)
- **14B** : `wan_2.1_vae.safetensors` (254 MB, 16 canaux, compression 8×8×4)
- **NON INTERCHANGEABLES** : Workflow manager injecte automatiquement le bon VAE

---

## Chemins critiques (RunPod)

- Modèles 5B : `/workspace/comfyui/ComfyUI/models/checkpoints/wan2.2-ti2v-5b/`
- Modèles 14B : `/workspace/comfyui/ComfyUI/models/checkpoints/wan2.2-i2v-a14b/`
- Output : `/app/output/` (vidéos), `/app/uploads/` (images), `/app/logs/`

---

## Workflow de démarrage (RunPod)

1. Affichage infos système (GPU, Python, PyTorch)
2. Download modèles OwnCloud (si absent)
3. Reconstitution fichiers découpés
4. Vérification intégrité (diffusion + T5 FP16) - **UTILISE CHEMINS RÉELS**
5. Configuration symlinks (modèles, VAE, T5)
6. Download CLIP Vision + modèles upscale (4x-UltraSharp, RealESRGAN backup)
7. Démarrage ComfyUI (port 8188)
8. Health check (180s timeout)
9. Démarrage Flask (port 5000)

**Fichier** : `docker-entrypoint.sh`

**Point critique étape 4** :
- ⚠️ Vérification utilise chemins réels (pas symlinks) après move des fichiers
- Chemins : `$DIFFUSION_DIR/wan2.2_ti2v_5B_fp16.safetensors`, `$VAE_BASE/wan2.2_vae.safetensors`, `$T5_BASE/umt5_xxl_fp16.safetensors`
- Évite faux négatifs (0 GB) qui causent restart (lignes 177-340)

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

Python 3.11 + Flask 3.0+ + PyTorch 2.10.dev (CUDA 12.8) + ComfyUI (WanVideoWrapper, PyramidFlowWrapper, VideoHelperSuite) + SafeTensors (ComfyUI Native) + NVIDIA GPU 48GB+ VRAM

---

## Points critiques

1. **Architecture workflow DIFFÉRENTE** : 5B et 14B utilisent des architectures de nodes DIFFÉRENTES
   - 5B: `WanVideoEncode` → `WanVideoEmptyEmbeds` (2-node moderne)
   - 14B: `WanVideoImageToVideoEncode` (1-node legacy) avec 4 paramètres REQUIS (v1.1.0+)
     - start_latent_strength: 1.0, end_latent_strength: 1.0, noise_aug_strength: 0.0, force_offload: false
   - Templates: `wan22_5b_i2v.json` (5B) vs `wan22_14b_with_upscale.json` (14B)
2. **VAE spécifiques** : 5B et 14B utilisent des VAE DIFFÉRENTS et NON INTERCHANGEABLES
   - 5B: wan2.2_vae.safetensors (1.41 GB, 48 canaux)
   - 14B: wan_2.1_vae.safetensors (254 MB, 16 canaux)
   - Injection automatique par workflow_manager.py
3. **Mixed precision REQUIS (v3.16.0+)** : Architecture mixte pour éviter artefacts catastrophiques
   - WanVideoModelLoader (node 2): `base_precision: "fp16"` (match fichiers safetensors FP16)
   - WanVideoVAELoader (node 3): `precision: "bf16"` (stabilité numérique encodage)
   - WanVideoTextEncodeCached (node 5): `precision: "bf16"` (préservation sémantique)
   - ⚠️ CRITIQUE: base_precision="bf16" sur node 2 cause conversion FP16→BF16 → bruit massif
   - Conforme workflow officiel Kijai (wanvideo2_2_I2V_A14B_example_WIP.json)
   - Templates corrigés: v1.6.0 (14B), v4.4.0/v3.4.0 (5B)
4. **Récupération vidéos** : get_output_images() DOIT chercher clés "gifs" (VHS_VideoCombine) ET "images" (SaveImage)
5. **Détection fin workflow** : Le client WebSocket DOIT détecter `node = null` (sinon timeout différencié : 1200s pour 5B, 1800s pour 14B)
6. **Sélection auto** : Image ≤720p → 5B, >720p → 14B + upscale
7. **VRAM** : 48GB minimum (5B), 80GB+ (14B FP16)
8. **Vérification fichiers** : docker-entrypoint.sh DOIT utiliser chemins réels (pas symlinks) pour éviter restart (lignes 177-340)
9. **Optimisations GPU (v3.14.0+)** : Templates configurés pour GPU 95GB sans offload inutile
   - WanVideoModelLoader: `load_device: "main_device"` (conforme API WanVideoWrapper, garde modèle en GPU)
   - WanVideoSampler: `force_offload: false` (pas true)
   - Accélération ~3-5x (5B: 10-15min → 3-5min, 14B: timeout → 6-12min)
   - Usage VRAM: 5B ~24.5GB (70GB marge), 14B ~67GB (28GB marge)
   - Valeurs API acceptées: "main_device" (GPU) ou "offload_device" (CPU/GPU offload)
