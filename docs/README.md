# Documentation - GEGM MotionLab

Ce dossier contient toute la documentation technique du projet.

---

## 📁 Structure

```
docs/
├── README.md                    # Ce fichier
├── CHANGES_TRACKER.md           # 🎯 Journal de bord des modifications (pour Claude)
├── ARCHITECTURE.md              # Architecture technique détaillée
└── sessions/                    # Historique des sessions de corrections
    ├── 2025-11-26_container51_corrections.md
    ├── 2025-11-26_container50_corrections.md
    └── ...
```

---

## 📄 Fichiers principaux

### `CHANGES_TRACKER.md` 🎯

**Objectif** : Fichier de référence pour Claude Code pour suivre TOUS les changements du projet.

**Contenu** :
- Historique chronologique des modifications
- Impact de chaque modification sur le fonctionnement global
- Checklist de mise à jour de la documentation
- État actuel du projet (snapshot)

**Utilisation** :
- Claude met à jour ce fichier après chaque modification
- Quand l'utilisateur demande "Actualise la documentation", Claude lit ce fichier pour savoir quoi mettre à jour
- Cocher les checkboxes après mise à jour de la documentation

### `ARCHITECTURE.md`

**Objectif** : Documentation technique détaillée de l'architecture du système.

**Contenu** :
- Vue d'ensemble des composants (Flask, ComfyUI, registre, workflow manager)
- Modèles WAN 2.2 + LTX 2.3 (architecture, fichiers, templates)
- Architecture workflows (5B, 14B MoE, LTX 2.3)
- Pipeline de téléchargement local (Makefile, setup script, registre)
- Custom nodes requis
- Points critiques

**Public** : Développeurs, DevOps, contributeurs techniques

### `sessions/`

**Objectif** : Archivage des sessions de corrections et analyses.

**Convention de nommage** : `YYYY-MM-DD_containerXX_type.md`

**Types** :
- `analyse.md` : Analyse détaillée d'un fichier de logs
- `corrections.md` : Corrections appliquées suite à l'analyse
- `debug.md` : Sessions de debugging

**Utilisation** : Référence historique, ne pas modifier après archivage

---

## 🔄 Workflow de mise à jour

### 1. Modification d'un fichier

Claude ajoute une entrée dans `CHANGES_TRACKER.md` :
```markdown
### [YYYY-MM-DD HH:MM] - Titre de la modification

**Fichiers modifiés** :
- `chemin/fichier.py` : Description

**Impact sur le fonctionnement global** :
- Impact sur autres composants
- Nouvelles dépendances

**Mise à jour documentation nécessaire** :
- [ ] CLAUDE.md - Section X
- [ ] README.md - Section Y
- [ ] README_DOCKER.md - Section Z
- [ ] README_RUNPOD.md - Section W
```

### 2. Demande de mise à jour

Utilisateur : "Actualise la documentation"

Claude :
1. Lit `CHANGES_TRACKER.md` en entier
2. Identifie les modifications non documentées (checkbox `[ ]`)
3. Lit les fichiers de documentation actuels
4. Propose les mises à jour pour chaque fichier
5. Applique après validation
6. Coche les checkboxes `[x]`

### 3. Archivage (si nécessaire)

Fichiers de corrections/analyses temporaires → `docs/sessions/`

---

## 📚 Autres fichiers de documentation (racine projet)

### `CLAUDE.md`

**Objectif** : Guide optimisé pour la compréhension et la mémoire de Claude Code.

**Style** : Technique, détaillé, structuré pour l'IA

**Contenu** :
- Vue d'ensemble du projet
- Structure détaillée
- Points critiques
- Scripts clés
- Workflow complet
- Configuration
- Troubleshooting

**Mise à jour** : Sur demande explicite de l'utilisateur

### `README.md` (racine)

**Objectif** : Documentation utilisateur générale.

**Style** : Professionnel, esthétique, accessible

**Contenu** :
- Présentation du projet
- Installation
- Configuration
- Utilisation
- API
- Troubleshooting

**Mise à jour** : Sur demande explicite de l'utilisateur

### `README_DOCKER.md`

**Objectif** : Guide de déploiement Docker.

**Style** : Orienté DevOps

**Contenu** :
- Build de l'image
- Configuration Docker
- docker-compose
- Variables d'environnement
- Troubleshooting Docker

**Mise à jour** : Sur demande explicite de l'utilisateur

### `README_RUNPOD.md`

**Objectif** : Guide de déploiement RunPod.

**Style** : Guide de déploiement pas-à-pas

**Contenu** :
- Préparation locale
- Déploiement RunPod
- Configuration Pod
- Logs de vérification
- Troubleshooting RunPod

**Mise à jour** : Sur demande explicite de l'utilisateur

---

## 💡 Best practices

### Pour Claude Code

**Après chaque modification** :
1. ✅ Mettre à jour `CHANGES_TRACKER.md`
2. ✅ Décrire l'impact global
3. ✅ Cocher les sections de doc à mettre à jour
4. ⏸️ Attendre la demande de l'utilisateur pour actualiser

**Lors de la demande "Actualise la documentation"** :
1. ✅ Lire `CHANGES_TRACKER.md` complet
2. ✅ Identifier les modifs non documentées
3. ✅ Lire les 4 fichiers de doc actuels
4. ✅ Proposer les mises à jour
5. ✅ Appliquer après validation
6. ✅ Cocher les checkboxes

### Pour les développeurs

**Avant de modifier du code** :
1. Lire `ARCHITECTURE.md` pour comprendre l'impact
2. Vérifier `CHANGES_TRACKER.md` pour les modifications récentes

**Après modification** :
1. Informer Claude des changements
2. Claude mettra à jour `CHANGES_TRACKER.md`
3. Demander "Actualise la documentation" quand nécessaire

---

## 📝 Templates

### Template CHANGES_TRACKER.md

```markdown
### [YYYY-MM-DD HH:MM] - Titre court

**Fichiers modifiés** :
- `chemin/fichier.ext` :
  - Description détaillée
  - Lignes modifiées
  - Raison

**Impact sur le fonctionnement global** :
- Impact sur autres composants
- Nouvelles dépendances
- Changements de comportement
- 🔗 Interaction avec : (fichiers/composants)

**Mise à jour documentation nécessaire** :
- [ ] CLAUDE.md - Section X
- [ ] README.md - Section Y
- [ ] README_DOCKER.md - Section Z
- [ ] README_RUNPOD.md - Section W

**Notes additionnelles** :
- Informations contextuelles
```

### Template session (docs/sessions/)

```markdown
# [Type] Container XX - [Titre]

**Date** : YYYY-MM-DD
**Container** : containerXX
**GPU** : [Type GPU]

## Analyse

[Analyse détaillée]

## Corrections appliquées

[Liste des corrections]

## Résultat

[Résultat attendu/obtenu]
```

---

## 🔗 Liens utiles

- **Projet** : `/Users/aboy/Documents/GEGM/Comfy_Img_to_Loop/`
- **CLAUDE.md** : `../CLAUDE.md`
- **README.md** : `../README.md`
- **README_DOCKER.md** : `../README_DOCKER.md`
- **README_RUNPOD.md** : `../README_RUNPOD.md`
