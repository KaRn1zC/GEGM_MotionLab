# CHANGES TRACKER - Journal de modifications

**Objectif** : Tracking temporaire des changements pour alimenter la mise à jour de `CLAUDE.md`.

**Usage** :
- Ajouter une entrée après chaque correction/modification
- Après mise à jour de `CLAUDE.md`, **NETTOYER** ce fichier (garder max 2-3 entrées récentes)

---

## Modifications récentes

### [2025-12-31] - FIX CRITIQUE: Architecture MoE 14B (2 experts high/low noise)

**Cause racine des artefacts "neige" identifiée** :
- Le modèle WAN 2.2 14B utilise une architecture **Mixture of Experts (MoE)** avec DEUX modèles distincts
- Nos templates n'utilisaient qu'UN SEUL modèle (high_noise) → artefacts catastrophiques

**Architecture MoE officielle** :
- `wan2.2_i2v_high_noise_14B_fp16.safetensors` : Expert early denoising (layout, structure)
- `wan2.2_i2v_low_noise_14B_fp16.safetensors` : Expert late denoising (détails, raffinement)
- **Switching I2V** : boundary=0.9 (10% high_noise, 90% low_noise)
- **Paramètres totaux** : 27B (2×14B), mais seulement 14B actifs par step

**Modifications apportées** :

1. **install-comfyui.sh** : Ajout installation `ComfyUI-WanMoeKSampler` (stduhpf)
2. **workflow_manager.py** :
   - `_get_model_checkpoint_path()` retourne tuple (high_path, low_path) pour 14B
   - `apply_parameters()` injecte `checkpoint_path_high` et `checkpoint_path_low`
3. **Templates 14B v2.0.0** (BREAKING CHANGE) :
   - Migration de Kijai WanVideoWrapper vers nodes natifs ComfyUI
   - 2× UNETLoader (high_noise + low_noise)
   - CLIPLoader (T5) + CLIPTextEncode (positive/negative)
   - ModelSamplingSD3 (sigma_shift=5.0 pour I2V)
   - WanImageToVideo (I2V conditioning)
   - WanMoeKSampler (boundary=0.9, cfg=3.5)
   - VAEDecode (au lieu de WanVideoDecode)

**Sources** :
- [ComfyUI-WanMoeKSampler](https://github.com/stduhpf/ComfyUI-WanMoeKSampler)
- [HuggingFace Wan2.2-I2V-A14B](https://huggingface.co/Wan-AI/Wan2.2-I2V-A14B)
- [ComfyUI Official Docs WAN 2.2](https://docs.comfy.org/tutorials/video/wan/wan2_2)

---

## WORKFLOW OBLIGATOIRE

**Après chaque correction** :
1. Ajouter entrée `CHANGES_TRACKER.md`
2. MàJ `CLAUDE.md` avec infos essentielles
3. MàJ `ARCHITECTURE.md` si changement architectural
4. **NETTOYER** fichiers documentation (max lignes définies)
5. Attendre demande utilisateur pour README
6. **JAMAIS git add/commit/push auto** (uniquement sur demande explicite)
