# CHANGES TRACKER - Journal de modifications

**Objectif** : Tracking temporaire des changements pour alimenter la mise à jour de `CLAUDE.md`.

**Usage** :
- ✅ Ajouter une entrée après chaque correction/modification
- ✅ Après mise à jour de `CLAUDE.md`, **NETTOYER** ce fichier (garder max 2-3 entrées récentes)

---

## 📅 Modifications récentes

### [2025-12-30] - Nettoyage templates 14B + Stratégie upscale unifiée

**Modifications apportées** :

#### 1. Retrait paramètres obsolètes des templates 14B
- `spatial_compress_level` et `temporal_compress_level` retirés de Node 7 (WanVideoImageToVideoEncode)
- Ces paramètres n'apparaissent pas dans la documentation officielle du node actuel
- Peuvent avoir été des paramètres legacy silencieusement ignorés

**Templates modifiés** (v1.7.0 → v1.8.0) :
- `workflows/templates/wan22_14b_with_upscale.json`
- `workflows/templates/wan22_14b_i2v.json`

#### 2. Stratégie upscale 14B alignée sur 5B
- Suppression logique spécifique 14B (résolution minimale forcée 832×480)
- Les deux modèles utilisent maintenant la même stratégie :
  - Upscale/downscale pré-génération vers ~720p max
  - Génération à résolution optimale (~720p)
  - Post-génération : UltraSharp 4x + Lanczos vers target

**Fichier modifié** : `web_interface/routes.py` (fonction `calculate_optimal_generation_strategy`)

**Justification** :
- Documentation officielle WAN 2.2 confirme support 480P et 720P pour 14B
- Workflow officiel Kijai utilise 832×480 par défaut mais pas comme minimum absolu
- Simplification du code (une seule stratégie au lieu de deux)

---

### [2025-12-30] - Analyse approfondie workflow 14B (recherche sources officielles)

**Recherche effectuée** sur :
- [Kijai GitHub ComfyUI-WanVideoWrapper](https://github.com/kijai/ComfyUI-WanVideoWrapper)
- [ComfyUI Official Docs](https://docs.comfy.org/tutorials/video/wan/wan2_2)
- [HuggingFace Wan-AI](https://huggingface.co/Wan-AI/Wan2.2-I2V-A14B)

**Résultats** :
- Précisions confirmées : FP16 (modèle) + BF16 (VAE/T5) ✅
- VAE correct : `wan_2.1_vae.safetensors` pour 14B ✅
- Architecture : `WanVideoImageToVideoEncode` pour 14B ✅
- Paramètres `spatial_compress_level` et `temporal_compress_level` : Non documentés dans API actuelle

---

## 🔄 WORKFLOW OBLIGATOIRE

**Après chaque correction** :
1. ✅ Ajouter entrée `CHANGES_TRACKER.md`
2. ✅ MàJ `CLAUDE.md` avec infos essentielles
3. ✅ MàJ `ARCHITECTURE.md` si changement architectural
4. ✅ **NETTOYER `CHANGES_TRACKER.md`** (max 2-3 entrées, ~60 lignes)
5. ✅ **NETTOYER `ARCHITECTURE.md`** (supprimer obsolète)
6. ⏸️ Attendre demande utilisateur pour README
