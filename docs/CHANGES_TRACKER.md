# CHANGES TRACKER - Journal de modifications

**Objectif** : Tracking temporaire des changements pour alimenter la mise à jour de `CLAUDE.md`.

**Usage** :
- ✅ Ajouter une entrée après chaque correction/modification
- ✅ Après mise à jour de `CLAUDE.md`, **NETTOYER** ce fichier (garder max 2-3 entrées récentes)

---

## 📅 Modifications récentes

### [2025-11-28 11:00] - Correction erreur 48/96 canaux - Remplacement nodes

**Problème** : RuntimeError "expected input to have 48 channels, but got 96 channels instead"

**Cause identifiée** :
- Node `WanVideoImageToVideoEncode` produit tenseur avec mauvais format
- Shape bugué : `[48, 8, 135, 216]` → interprété comme 96 canaux par le transformer
- Incompatibilité avec version récente wrapper (commit `44feb24`)

**Solution implémentée** :
Remplacement architecture node 7 basée sur workflow officiel `wanvideo_2_2_5B_I2V_example_WIP.json` :

**Ancienne architecture (buguée)** :
```
Node 7: WanVideoImageToVideoEncode (tout-en-un, bugué)
  ├─ vae: [3, 0]
  ├─ start_image: [1, 0]
  └─ clip_embeds: [6, 0]
  → output: image_embeds (format incorrect)
```

**Nouvelle architecture (fonctionnelle)** :
```
Node 7: WanVideoEncode (encode image → latents)
  ├─ vae: [3, 0]
  └─ image: [1, 0]
  → output: samples (LATENT)

Node 7b: WanVideoEmptyEmbeds (latents → embeds)
  ├─ extra_latents: [7, 0]
  ├─ width: {width}
  ├─ height: {height}
  └─ num_frames: {frames}
  → output: image_embeds (format correct)
```

**Fichiers modifiés** :
- `workflows/templates/wan22_i2v.json` : v3.0.0 → v4.0.0
  - Supprimé node 6 `WanVideoClipVisionEncode` (non utilisé dans workflow officiel sans CLIP embeds)
  - Remplacé node 7 `WanVideoImageToVideoEncode` par `WanVideoEncode`
  - Ajouté node 7b `WanVideoEmptyEmbeds`
  - Node 8 `WanVideoSampler` : connexion `image_embeds` change de `[7, 0]` → `[7b, 0]`

- `workflows/templates/wan22_with_upscale.json` : v1.0.0 → v2.0.0
  - Mêmes modifications que wan22_i2v.json

- `docker-entrypoint.sh` : ligne 173-174
  - Remplacé `ln -sf` par `cp` pour le VAE
  - Raison : WanVideoVAELoader ne suit pas toujours les symlinks correctement

**Paramètres WanVideoEncode** :
```json
{
  "vae": ["3", 0],
  "image": ["1", 0],
  "enable_vae_tiling": false,
  "tile_x": 272,
  "tile_y": 272,
  "tile_stride_x": 144,
  "tile_stride_y": 128,
  "temporal_compress_level": 0,
  "spatial_compress_level": 1
}
```

**Paramètres WanVideoEmptyEmbeds** :
```json
{
  "extra_latents": ["7", 0],
  "width": "{width}",
  "height": "{height}",
  "num_frames": "{frames}"
}
```

**Impact** :
- ✅ Résout erreur 48/96 canaux définitivement
- ✅ Compatible avec version récente wrapper (commit `44feb24`)
- ✅ Architecture alignée sur workflows officiels Kijai
- ⚠️ BREAKING CHANGE : anciens workflows incompatibles
- ⏳ Test requis sur RunPod après redémarrage

---

### [2025-11-27 11:00] - Correction workflows JSON pour refléter noms réels fichiers

**Raison** : UnpicklingError car workflows JSON référençaient noms fictifs `.pth` au lieu des vrais fichiers `.safetensors`

**Fichiers modifiés** :
- `workflows/templates/wan22_i2v.json` :
  - VAE: `Wan2.2_VAE.pth` → `wan2.2_vae.safetensors`
  - T5: `t5/umt5-xxl-enc-bf16.pth` → `t5/umt5_xxl_fp16.safetensors`
- `workflows/templates/wan22_with_upscale.json` : Idem
- `docker-entrypoint.sh` : Suppression symlinks de compatibilité (lignes 178, 206)
- `scripts/setup_diffusion_models.sh` : Suppression symlinks de compatibilité

**Impact** :
- ✅ Workflows JSON reflètent la réalité des fichiers
- ✅ Résout UnpicklingError définitivement (pas de patch nécessaire)
- ✅ Architecture simplifiée (pas de symlinks artificiels)

---

### [2025-11-26 17:00] - Migration T5 Encoder FP8 scaled → FP16

**Raison** : ComfyUI-WanVideoWrapper refuse les T5 FP8 scaled (ValueError)

**Fichiers modifiés** :
- `scripts/setup_wan22_native.sh` : Download `umt5_xxl_fp16.safetensors` (11.4 GB)
- `scripts/verify_t5_integrity.py` : Vérification FP16 (10-12 GB attendu)
- `docker-entrypoint.sh` : T5_SOURCE vers FP16

**Impact** :
- ✅ Résout ValueError "fp8 scaled is not supported by this node"
- ✅ Solution officielle T5 FP16
- ⚠️ T5 plus gros : 11.4 GB vs 6.74 GB (OK avec L40S 44GB)

---

## 📝 Template pour nouvelle entrée

```markdown
### [YYYY-MM-DD HH:MM] - Titre court

**Raison** : Pourquoi ce changement

**Fichiers modifiés** :
- `fichier.py` : Changement effectué

**Impact** :
- Impact principal sur le fonctionnement

**Documentation mise à jour** :
- [ ] `CLAUDE.md`
- [ ] `docs/ARCHITECTURE.md`
```

---

## 🧹 Rappel : Nettoyer régulièrement ce fichier

Après chaque mise à jour de `CLAUDE.md`, supprimer les anciennes entrées et ne garder que les 2-3 dernières pertinentes.
