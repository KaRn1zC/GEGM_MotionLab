# Architecture technique - GEGM MotionLab

**Dernière mise à jour** : 2026-03-17 (v5.1.0 - Pipeline model-agnostic complet)
**Objectif** : Référence technique compacte du système

---

## Composants principaux

### Flask (Port 5000)
- Interface web + API REST
- Queue de jobs asynchrone
- Communication WebSocket avec ComfyUI

**Fichiers clés** : `web_interface/app.py`, `routes.py`, `jobs.py`

### ComfyUI (Port 8188)
- Engine de génération multi-modèles (WAN 2.2 + LTX 2.3)
- Custom nodes : WanVideoWrapper (5B), WanMoeKSampler (14B), LTXVideo (LTX 2.3), VideoHelperSuite
- Format : ComfyUI Native (Comfy-Org)

**Chemins** : `/workspace/comfyui/ComfyUI/`

### Registre Modèles
- Source de vérité unique : `config/model_registry.yaml`
- Module Python : `src/model_registry.py` (singleton via `get_registry()`)
- Pipeline model-agnostic : résolution, téléchargement, vérification — tout piloté par YAML
- CLI bash pour les scripts : `python -m src.model_registry <commande> [modèle]`

### Workflow Manager
- Sélection template automatique via registre
- Détection modèle auto (priorité : LTX 2.3 22B > WAN 14B > WAN 5B)
- Transformation paramètres frontend → ComfyUI (model-family-specific)

**Fichier** : `workflows/workflow_manager.py`

### Client WebSocket ComfyUI (v3.5.3)
- Communication bidirectionnelle Flask ↔ ComfyUI
- **Détection fin workflow** : Message `executing` avec `node = null`
- **Gestion messages binaires** : Skip images preview
- **Récupération outputs** : Clés "images" ET "gifs"

**Fichier** : `src/comfyui_client.py`

---

## Modèles (Format ComfyUI Native)

### WAN 2.2 5B (Kijai Wrapper)
- **Fichier** : `wan2.2_ti2v_5B_fp16.safetensors` (9.31 GB)
- **VAE** : wan2.2_vae.safetensors (1.41GB, 48ch)
- **Text encoder** : T5 partagé (umt5_xxl_fp16.safetensors, 11.4GB)
- **Template** : `wan22_5b_i2v.json` (v4.5.1)

### WAN 2.2 14B MoE (Native ComfyUI)
- **Fichiers** (2 experts) :
  - `wan2.2_i2v_high_noise_14B_fp16.safetensors` (~28.6 GB)
  - `wan2.2_i2v_low_noise_14B_fp16.safetensors` (~28.6 GB)
- **VAE** : wan_2.1_vae.safetensors (254MB, 16ch)
- **Text encoder** : T5 partagé
- **Template** : `wan22_14b_i2v.json` (v2.0.5)

### LTX 2.3 22B DiT (Lightricks)
- **Fichier** : `ltx-2.3-22b-dev.safetensors` (46.1GB)
- **VAE** : intégré dans le checkpoint (128ch)
- **Text encoder** : Gemma 3 12B (model-spécifique, pas T5)
- **Template** : `ltx23_i2v.json` (v1.0.0)

---

## Architecture Workflows

### WAN 5B (Kijai Wrapper)
```
Node 2: WanVideoModelLoader
Node 7: WanVideoEncode → Node 7b: WanVideoEmptyEmbeds
Node 8: WanVideoSampler (image_embeds: [7b,0])
Node 9: WanVideoDecode
```

### WAN 14B MoE (Native + WanMoeKSampler)
```
Node 2: UNETLoader (high_noise) → Node 6: ModelSamplingSD3 (shift=5.0)
Node 2b: UNETLoader (low_noise) → Node 6b: ModelSamplingSD3 (shift=5.0)
Node 4: CLIPLoader (T5) → Node 5/5b: CLIPTextEncode (pos/neg)
Node 7: WanImageToVideo → (positive, negative, latent)
Node 8: WanMoeKSampler (high=[6], low=[6b], boundary=0.9)
Node 9: VAEDecode
```

### LTX 2.3 (LTXVLoopingSampler + STG)
```
CheckpointLoaderSimple (MODEL + VAE intégré)
LTXVGemmaCLIPModelLoader (Gemma 3 12B) → CLIPTextEncode
STGGuiderAdvanced (stg_block_idx, stg_scale)
LTXVLoopingSampler (cond_image_indices="0, N" → boucle seamless)
VAEDecode → VHS_VideoCombine
```

---

## Pipeline de téléchargement local (Makefile + setup script)

```
make workflow MODEL=<nom>
    │
    ├── 1. setup_wan22_native.sh <model>
    │       ├── WAN legacy (hardcodé) si model ∈ {5b, 14b, all}
    │       └── Registre fallback (model-agnostic) sinon :
    │           ├── get-hf-downloads → manifeste multi-repo (repo par fichier)
    │           ├── hf download $file_repo $hf_path pour chaque fichier
    │           ├── get-symlinks → création symlinks modèle
    │           ├── verify_diffusion_model.py
    │           ├── verify_t5_integrity.py (seulement si T5 partagé)
    │           └── verify_vae.py (gère "integrated")
    │
    ├── 2. split_and_upload.py --model <model>
    │       └── Découpe >4GB + upload OwnCloud
    │
    ├── 3. rclone size → vérification upload
    │
    └── 4. _models-deep-clean-auto → nettoyage local
```

---

## Chemins critiques (RunPod)

- Modèles WAN 5B : `/workspace/comfyui/ComfyUI/models/checkpoints/wan2.2-ti2v-5b/`
- Modèles WAN 14B : `/workspace/comfyui/ComfyUI/models/checkpoints/wan2.2-i2v-a14b/`
- Modèles LTX : `/workspace/comfyui/ComfyUI/models/checkpoints/ltx-2.3-i2v-dev/`
- T5 partagé : `/workspace/comfyui/ComfyUI/models/text_encoders/t5/`
- Text encoders LTX : `/workspace/comfyui/ComfyUI/models/text_encoders/`
- VAE : `/workspace/comfyui/ComfyUI/models/vae/`

---

## Custom Nodes Requis

1. **ComfyUI-WanVideoWrapper** (Kijai) - WAN 2.2 5B
2. **ComfyUI-WanMoeKSampler** (stduhpf) - WAN 2.2 14B MoE
3. **ComfyUI-VideoHelperSuite** (Kosinkadink) - VHS_VideoCombine (tous modèles)
4. **ComfyUI-LTXVideo** (Lightricks) - LTX 2.3 (LTXVLoopingSampler, STGGuider, Gemma loader)

**Installation** : `install-comfyui.sh`

---

## Points critiques

1. **Architecture 5B ≠ 14B** : 5B utilise Kijai Wrapper, 14B utilise nodes natifs + WanMoeKSampler
2. **MoE OBLIGATOIRE 14B** : Les 2 fichiers (high/low noise) sont REQUIS, sinon artefacts
3. **VAE spécifiques** : 5B=wan2.2_vae (48ch), 14B=wan_2.1_vae (16ch), LTX=intégré (128ch) — NON INTERCHANGEABLES
4. **LTX ≠ WAN** : Gemma (pas T5), VAE intégré, STG guidance (pas shift/riflex), frames N×8+1
5. **Timeouts** : 5400s (WAN 5B), 10800s (WAN 14B), 7200s (LTX 2.3 22B)
6. **VRAM** : 48GB+ (WAN 5B), 80GB+ (WAN 14B, LTX 2.3 22B)
7. **Alignement résolutions** : Multiples de 32 avec floor (préfère crop à upscale)
8. **Registre modèles** : `config/model_registry.yaml` = source de vérité unique
9. **Manifeste multi-repo** : chaque fichier porte son `repo` (LTX : checkpoint Lightricks, Gemma Comfy-Org)
10. **PYTHONPATH** : `/workspace` dans Dockerfile, pas de `sys.path.append` dans le code
