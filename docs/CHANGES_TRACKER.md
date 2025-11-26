# CHANGES TRACKER - Journal de modifications

**Objectif** : Tracking temporaire des changements pour alimenter la mise à jour de `CLAUDE.md`.

**Usage** :
- ✅ Ajouter une entrée après chaque correction/modification
- ✅ Après mise à jour de `CLAUDE.md`, **NETTOYER** ce fichier (garder max 2-3 entrées récentes)

---

## 📅 Modifications récentes

### [2025-11-26 17:00] - Migration T5 Encoder FP8 scaled → FP16

**Raison** : ComfyUI-WanVideoWrapper refuse les T5 FP8 scaled (ValueError)

**Fichiers modifiés** :
- `scripts/setup_wan22_native.sh` : Download `umt5_xxl_fp16.safetensors` (11.4 GB)
- `scripts/verify_t5_integrity.py` : Vérification FP16 (10-12 GB attendu)
- `scripts/setup_diffusion_models.sh` : Symlinks vers FP16
- `docker-entrypoint.sh` : T5_SOURCE vers FP16, suppression section patch (lignes 276-285)
- **SUPPRIMÉ** : `scripts/patch_comfyui_torch_load.py` (obsolète avec FP16)

**Impact** :
- ✅ Résout ValueError "fp8 scaled is not supported by this node"
- ✅ Solution officielle (pas de patch nécessaire)
- ⚠️ T5 plus gros : 11.4 GB vs 6.74 GB (OK avec L40S 44GB)

**Documentation mise à jour** :
- [x] `CLAUDE.md` (v3.3.0)
- [x] `docs/ARCHITECTURE.md`
- [x] `docs/CHANGES_TRACKER.md` (nettoyé)

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
