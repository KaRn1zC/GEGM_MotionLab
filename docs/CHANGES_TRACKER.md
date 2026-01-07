# CHANGES TRACKER - Journal de modifications

**Objectif** : Tracking temporaire des changements pour alimenter la mise à jour de `CLAUDE.md`.

**Usage** :
- Ajouter une entrée après chaque correction/modification
- Après mise à jour de `CLAUDE.md`, **NETTOYER** ce fichier (garder max 2-3 entrées récentes)

---

## Modifications récentes

### [2026-01-07] - VALIDATION: Tests Production Réussis (5B + 14B)

**Containers testés** :
- `5B_container17.txt` : GPU RTX 6000 Ada (47.5GB) - SUCCESS
- `14B_container27.txt` : GPU RTX PRO 6000 Blackwell (95GB) - SUCCESS

**Validation complète** :
- Transformation paramètres frontend → ComfyUI opérationnelle
- Architecture MoE 14B (2 experts high/low noise) fonctionnelle
- Templates 5B v4.5.0 et 14B v2.0.2 validés en production

---

## WORKFLOW OBLIGATOIRE

**Après chaque correction** :
1. Ajouter entrée `CHANGES_TRACKER.md`
2. MàJ `CLAUDE.md` avec infos essentielles
3. **NETTOYER** fichiers documentation après MàJ
4. **JAMAIS git add/commit/push auto** (uniquement sur demande explicite)
