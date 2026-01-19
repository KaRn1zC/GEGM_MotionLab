# CHANGES TRACKER - Journal de modifications

**Objectif** : Tracking temporaire des changements pour alimenter la mise à jour de `CLAUDE.md`.

**Usage** :
- Ajouter une entrée après chaque correction/modification
- Après mise à jour de `CLAUDE.md`, **NETTOYER** ce fichier (garder max 2-3 entrées récentes)

---

## Modifications récentes

### [2026-01-19] - FIX: Désactivation pingpong pour vraie boucle seamless

**Problème identifié :**
- `pingpong=true` créait un effet miroir (5s avant + 5s arrière = 10s)
- Comportement souhaité : vraie boucle qui recommence au début (5s en boucle infinie)

**Corrections apportées :**

1. **workflow_manager.py** :
   - `transformed["pingpong"] = False` (toujours false, plus de calcul dynamique)

2. **Tous les templates** (pingpong hardcodé à false) :
   - `wan22_5b_i2v.json` : v4.5.0 → v4.5.1
   - `wan22_5b_with_upscale.json` : v3.5.0 → v3.5.1
   - `wan22_14b_i2v.json` : v2.0.3 → v2.0.4
   - `wan22_14b_with_upscale.json` : v2.0.3 → v2.0.4

**Paramètres shift corrigés dans 14B :**
- `wan22_14b_i2v.json` : v2.0.4 → v2.0.5
- `wan22_14b_with_upscale.json` : v2.0.4 → v2.0.5
- Nodes 6, 6b (ModelSamplingSD3): `shift: 5.0` → `shift: "{shift}"`
- Node 8 (WanMoeKSampler): `sigma_shift: 5.0` → `sigma_shift: "{shift}"`
- Ajout définition paramètre `shift` dans section parameters

---

### [2026-01-19] - Synchronisation Documentation

**Intégré dans CLAUDE.md v4.2.0 :**
- Section "Presets & Prompts Optimisés" ajoutée
- Preset Cinemagraph recommandé documenté
- Negative prompt par défaut et structure prompt

---

## WORKFLOW OBLIGATOIRE

**Après chaque correction** :
1. Ajouter entrée `CHANGES_TRACKER.md`
2. MàJ `CLAUDE.md` avec infos essentielles
3. **NETTOYER** fichiers documentation après MàJ
4. **JAMAIS git add/commit/push auto** (uniquement sur demande explicite)
