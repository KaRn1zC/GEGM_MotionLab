# Architecture technique - GEGM MotionLab

**Dernière mise à jour** : 2026-03-16 (v4.4.0 - Nettoyage dead code + modernisation)
**Objectif** : Référence technique compacte pour alimenter la mise à jour de `CLAUDE.md`

---

## Composants principaux

### Flask (Port 5000)
- Interface web + API REST
- Queue de jobs asynchrone
- Communication WebSocket avec ComfyUI

**Fichiers clés** : `web_interface/app.py`, `routes.py`, `jobs.py`

### ComfyUI (Port 8188)
- Engine de génération WAN 2.2
- Custom nodes : WanVideoWrapper (5B), WanMoeKSampler (14B), VideoHelperSuite
- Format : ComfyUI Native (Comfy-Org)

**Chemins** : `/workspace/comfyui/ComfyUI/`

### Workflow Manager
- Sélection template (5B: wan22_5b_i2v, 14B: wan22_14b_i2v)
- Détection modèle auto (5B vs 14B MoE)
- Injection chemins checkpoint via `validated_params["model_name"]` (5B: single, 14B: tuple high/low)

**Fichier** : `workflows/workflow_manager.py`

### Client WebSocket ComfyUI (v3.5.3)
- Communication bidirectionnelle Flask ↔ ComfyUI
- **Détection fin workflow** : Message `executing` avec `node = null`
- **Gestion messages binaires** : Skip images preview
- **Récupération outputs** : Clés "images" ET "gifs"

**Fichier** : `src/comfyui_client.py`

---

## Modèles WAN 2.2 (Format ComfyUI Native)

### Modèle 5B (Architecture Kijai Wrapper)
- **Fichier** : `wan2.2_ti2v_5B_fp16.safetensors` (9.31 GB)
- **VAE** : wan2.2_vae.safetensors (1.41GB, 48ch)
- **Workflow** : WanVideoEncode → WanVideoEmptyEmbeds → WanVideoSampler → WanVideoDecode
- **Template** : `wan22_5b_i2v.json` (v4.5.1)

### Modèle 14B MoE (Architecture Native ComfyUI)
- **Fichiers** (2 experts) :
  - `wan2.2_i2v_high_noise_14B_fp16.safetensors` (~28.6 GB) - Early denoising (layout)
  - `wan2.2_i2v_low_noise_14B_fp16.safetensors` (~28.6 GB) - Late denoising (details)
- **VAE** : wan_2.1_vae.safetensors (254MB, 16ch)
- **Workflow v2.0.0** : UNETLoader×2 → ModelSamplingSD3×2 → WanMoeKSampler → VAEDecode
- **MoE Params** : boundary=0.9 (I2V), sigma_shift=5.0, cfg=3.5
- **Template** : `wan22_14b_i2v.json` (v2.0.5)

### T5 Encoder (partagé)
- **Fichier** : `umt5_xxl_fp16.safetensors` (11.4 GB, 412 clés)

---

## Architecture Workflows

### 5B (Kijai Wrapper)
```
Node 2: WanVideoModelLoader
Node 7: WanVideoEncode → Node 7b: WanVideoEmptyEmbeds
Node 8: WanVideoSampler (image_embeds: [7b,0])
Node 9: WanVideoDecode
```

### 14B MoE (Native ComfyUI + WanMoeKSampler)
```
Node 2: UNETLoader (high_noise) → Node 6: ModelSamplingSD3 (shift=5.0)
Node 2b: UNETLoader (low_noise) → Node 6b: ModelSamplingSD3 (shift=5.0)
Node 4: CLIPLoader (T5) → Node 5/5b: CLIPTextEncode (pos/neg)
Node 7: WanImageToVideo → (positive, negative, latent)
Node 8: WanMoeKSampler (high=[6], low=[6b], boundary=0.9)
Node 9: VAEDecode
```

**MoE Switching** : 10% steps high_noise (layout), 90% steps low_noise (refinement)

---

## Chemins critiques (RunPod)

- Modèles 5B : `/workspace/comfyui/ComfyUI/models/checkpoints/wan2.2-ti2v-5b/`
- Modèles 14B : `/workspace/comfyui/ComfyUI/models/checkpoints/wan2.2-i2v-a14b/`
  - high_noise + low_noise dans même dossier
- T5 : `/workspace/comfyui/ComfyUI/models/text_encoders/t5/`
- VAE : `/workspace/comfyui/ComfyUI/models/vae/`

---

## Custom Nodes Requis

1. **ComfyUI-WanVideoWrapper** (Kijai) - Pour 5B
2. **ComfyUI-WanMoeKSampler** (stduhpf) - Pour 14B MoE
3. **ComfyUI-VideoHelperSuite** (Kosinkadink) - VHS_VideoCombine
4. **ComfyUI-PyramidFlowWrapper** (Kijai) - Upscale

**Installation** : `install-comfyui.sh`

---

## Points critiques

1. **Architecture 5B ≠ 14B** : 5B utilise Kijai Wrapper, 14B utilise nodes natifs + WanMoeKSampler
2. **MoE OBLIGATOIRE 14B** : Les 2 fichiers (high/low noise) sont REQUIS, sinon artefacts "neige"
3. **VAE spécifiques** : 5B=wan2.2_vae (48ch), 14B=wan_2.1_vae (16ch) - NON INTERCHANGEABLES
4. **workflow_manager.py** : Retourne tuple pour 14B, injecte checkpoint_path_high/low
5. **Timeouts** : 5400s (5B), 10800s (14B) - défaut WebSocket 5400s
6. **VRAM** : 5B=48GB+, 14B=80GB+
7. **Alignement résolutions** : Multiples de 32 avec floor (préfère crop à upscale)
8. **pingpong** : Toujours False (vraie boucle seamless, pas d'effet miroir)
9. **PYTHONPATH** : `/workspace` dans Dockerfile, pas de `sys.path.append` dans le code
10. **Typing** : Annotations Python 3.11+ (`dict`, `list`, `X | None`) dans tous les modules
