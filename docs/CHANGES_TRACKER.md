# CHANGES TRACKER - Journal de modifications

**Objectif** : Tracking temporaire des changements pour alimenter la mise à jour de `CLAUDE.md`.

**Usage** :
- ✅ Ajouter une entrée après chaque correction/modification
- ✅ Après mise à jour de `CLAUDE.md`, **NETTOYER** ce fichier (garder max 2-3 entrées récentes)

---

## 📅 Modifications récentes

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
