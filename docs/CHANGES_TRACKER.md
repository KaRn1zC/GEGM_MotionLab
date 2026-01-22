# CHANGES TRACKER - Journal de modifications

**Objectif** : Tracking temporaire des changements pour alimenter la mise à jour de `CLAUDE.md`.

**Usage** :
- Ajouter une entrée après chaque correction/modification
- Après mise à jour de `CLAUDE.md`, **NETTOYER** ce fichier (garder max 2-3 entrées récentes)

---

## Modifications récentes

### [2026-01-22] - Timeout unifié 90 minutes + Mise à jour documentation

**Corrections apportées :**

1. **web_interface/routes.py:490** :
   - Timeout unifié à 5400s (90min) pour tous les workflows (5B et 14B)
   - Permet générations haute résolution + upscale sans timeout

2. **Documentation synchronisée** :
   - CLAUDE.md → v4.3.0
   - README.md, README_DOCKER.md, README_RUNPOD.md → v4.3.0
   - docs/ARCHITECTURE.md → v4.3.0
   - Toutes les versions de templates mises à jour

**Versions actuelles templates :**
- `wan22_5b_i2v.json` : v4.5.1
- `wan22_5b_with_upscale.json` : v3.5.1
- `wan22_14b_i2v.json` : v2.0.5
- `wan22_14b_with_upscale.json` : v2.0.5

---

## WORKFLOW OBLIGATOIRE

**Après chaque correction** :
1. Ajouter entrée `CHANGES_TRACKER.md`
2. MàJ `CLAUDE.md` avec infos essentielles
3. **NETTOYER** fichiers documentation après MàJ
4. **JAMAIS git add/commit/push auto** (uniquement sur demande explicite)
