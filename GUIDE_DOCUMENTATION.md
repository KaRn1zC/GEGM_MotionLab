# Guide du système de documentation - GEGM MotionLab

**Créé le** : 2025-11-26
**Objectif** : Maintenir une documentation toujours à jour et optimisée

---

## 🎯 Système mis en place

### Vue d'ensemble

J'ai créé un **système de tracking intelligent** qui me permet de :

1. ✅ Suivre TOUS les changements structurels et individuels du projet
2. ✅ Comprendre l'impact de chaque modification sur le fonctionnement global
3. ✅ Mettre à jour `CLAUDE.md` de façon optimale pour ma compréhension
4. ✅ Mettre à jour les 3 `README.md` en conservant leur style propre
5. ✅ Tout garder à jour sur demande explicite

---

## 📁 Structure de documentation créée

```
Comfy_Img_to_Loop/
├── CLAUDE.md                       # Guide pour Claude (technique détaillé)
├── README.md                       # Documentation utilisateur (professionnel)
├── README-DOCKER.md                # Guide Docker (DevOps)
├── README-RUNPOD.md                # Guide RunPod (déploiement)
├── GUIDE_DOCUMENTATION.md          # 📖 Ce fichier (guide du système)
│
└── docs/
    ├── README.md                   # Explication du dossier docs
    ├── CHANGES_TRACKER.md          # 🎯 FICHIER CLÉ - Journal de bord
    ├── ARCHITECTURE.md             # Architecture technique détaillée
    │
    └── sessions/                   # Archivage des sessions
        ├── 2025-11-26_container51_corrections.md
        └── ...
```

---

## 🔑 Fichier clé : `docs/CHANGES_TRACKER.md`

### C'est quoi ?

Mon **journal de bord personnel** que je mets à jour après chaque modification. C'est ma "mémoire externe" du projet.

### Contenu

Pour chaque modification, j'enregistre :

```markdown
### [2025-11-26 11:30] - Patch ComfyUI v3

**Fichiers modifiés** :
- `scripts/patch_comfyui_torch_load.py` :
  - Normalisation chemin
  - Détection double safetensors
  - Lignes 65-98

**Impact sur le fonctionnement global** :
- ✅ Résout UnpicklingError T5 Encoder
- ✅ Workflow complet fonctionnel
- 🔗 Interaction avec : docker-entrypoint.sh

**Mise à jour documentation nécessaire** :
- [ ] CLAUDE.md - Section "Patch ComfyUI"
- [ ] README-RUNPOD.md - Logs de vérification
```

### Pourquoi c'est important ?

Quand tu me demanderas "Actualise la documentation", je lirai ce fichier pour savoir :
- Quelles modifications ont été faites depuis la dernière mise à jour
- Quelles sections de documentation doivent être mises à jour
- Quel est l'état actuel du projet

---

## 🔄 Comment ça fonctionne en pratique ?

### 1. Lors d'une modification de fichier

**Ce que je fais automatiquement** :

```
┌─────────────────────────────────────┐
│ Modification d'un fichier           │
└─────────────┬───────────────────────┘
              ↓
┌─────────────────────────────────────┐
│ J'ajoute une entrée dans            │
│ docs/CHANGES_TRACKER.md             │
│ avec :                              │
│ - Fichiers modifiés                 │
│ - Impact global                     │
│ - Sections doc à mettre à jour []   │
└─────────────┬───────────────────────┘
              ↓
┌─────────────────────────────────────┐
│ J'attends ta demande explicite      │
│ pour actualiser la documentation    │
└─────────────────────────────────────┘
```

**Ce que tu NE verras PAS** : Je ne vais pas automatiquement mettre à jour `CLAUDE.md` ou les `README` après chaque petite modification. Cela polluerait le projet.

### 2. Quand tu veux actualiser la documentation

**Tu dis** :
```
"Actualise la documentation"
```

ou plus spécifique :
```
"Mets à jour CLAUDE.md et README-RUNPOD.md avec les modifications depuis container51"
```

**Ce que je fais** :

```
┌─────────────────────────────────────┐
│ 1. Je lis docs/CHANGES_TRACKER.md   │
│    en entier                        │
└─────────────┬───────────────────────┘
              ↓
┌─────────────────────────────────────┐
│ 2. J'identifie toutes les modifs    │
│    non documentées (checkbox [ ])   │
└─────────────┬───────────────────────┘
              ↓
┌─────────────────────────────────────┐
│ 3. Je lis les fichiers de doc       │
│    actuels pour comprendre le style │
│    - CLAUDE.md                      │
│    - README.md                      │
│    - README-DOCKER.md               │
│    - README-RUNPOD.md               │
└─────────────┬───────────────────────┘
              ↓
┌─────────────────────────────────────┐
│ 4. Je te PROPOSE les mises à jour   │
│    pour chaque fichier              │
│    (tu peux valider/refuser)        │
└─────────────┬───────────────────────┘
              ↓
┌─────────────────────────────────────┐
│ 5. J'applique les mises à jour      │
│    validées                         │
└─────────────┬───────────────────────┘
              ↓
┌─────────────────────────────────────┐
│ 6. Je coche les checkboxes [x]      │
│    dans CHANGES_TRACKER.md          │
└─────────────────────────────────────┘
```

### 3. Respect du style de chaque fichier

**CLAUDE.md** :
- ✅ Style : Technique, détaillé, structuré pour IA
- ✅ Niveau de détail : Maximum (architecture, scripts, chemins, commandes)
- ✅ Sections : Structure projet, Points Critiques, Workflow Complet, Troubleshooting
- ✅ Format : Markdown avec tableaux, code blocks, chemins absolus

**README.md** :
- ✅ Style : Professionnel, esthétique, accessible
- ✅ Niveau de détail : Moyen (utilisateur final)
- ✅ Sections : Présentation, Installation, Configuration, Utilisation, API
- ✅ Format : Markdown avec badges, emojis, exemples clairs

**README-DOCKER.md** :
- ✅ Style : Orienté DevOps
- ✅ Niveau de détail : Focus Docker uniquement
- ✅ Sections : Build, Configuration, docker-compose, Variables, Troubleshooting
- ✅ Format : Markdown avec commandes Docker, docker-compose

**README-RUNPOD.md** :
- ✅ Style : Guide pas-à-pas de déploiement
- ✅ Niveau de détail : Focus RunPod uniquement
- ✅ Sections : Préparation, Déploiement, Configuration, Logs, Troubleshooting
- ✅ Format : Markdown avec étapes numérotées, logs à vérifier

---

## 📝 Exemples concrets

### Exemple 1 : Petite modification

**Situation** : Tu modifies une variable d'environnement dans `.env.example`

**Ce que je fais** :
1. ✅ J'ajoute une entrée dans `docs/CHANGES_TRACKER.md`
2. ⏸️ J'attends ta demande pour mettre à jour la doc

**Pourquoi ?** Une petite modification ne nécessite pas de mettre à jour immédiatement tous les README.

---

### Exemple 2 : Modification importante

**Situation** : On passe du modèle WAN 2.2 5B au modèle 14B par défaut

**Ce que je fais** :
1. ✅ J'ajoute une entrée détaillée dans `docs/CHANGES_TRACKER.md` :
   - Fichiers modifiés (workflow_manager.py, docker-entrypoint.sh, etc.)
   - Impact global (nouvelles dépendances GPU, changement de résolution max, etc.)
   - Checkboxes pour toutes les sections de doc à mettre à jour

**Quand tu dis "Actualise la documentation"** :
1. ✅ Je lis l'entrée du tracker
2. ✅ Je mets à jour :
   - `CLAUDE.md` : Section "Modèles WAN 2.2" (détails techniques 14B)
   - `README.md` : Section "Configuration" (nouveau modèle par défaut)
   - `README-DOCKER.md` : Variables d'environnement (OWNCLOUD_MODEL_NAME)
   - `README-RUNPOD.md` : GPU requis (H100 au lieu de RTX 6000)
3. ✅ Je coche toutes les checkboxes [x]

---

### Exemple 3 : Ajout d'un nouveau fichier

**Situation** : Tu crées un nouveau script `scripts/optimize_vae.py`

**Ce que je fais** :
1. ✅ J'ajoute une entrée dans `docs/CHANGES_TRACKER.md` :
   - Nouveau fichier créé
   - Rôle du fichier
   - Impact sur le workflow
   - Interactions avec autres fichiers

**Quand tu dis "Actualise la documentation"** :
1. ✅ Je mets à jour :
   - `CLAUDE.md` : Section "Scripts Clés" (ajout optimize_vae.py)
   - `ARCHITECTURE.md` : Si le script change l'architecture
   - `README.md` : Si l'utilisateur doit connaître ce script
   - Autres README si pertinent

---

## ✅ Avantages de ce système

### Pour toi

1. ✅ **Contrôle total** : Tu décides quand mettre à jour la documentation
2. ✅ **Pas de pollution** : Les fichiers ne changent que quand tu le demandes
3. ✅ **Historique complet** : `docs/CHANGES_TRACKER.md` = journal de bord complet
4. ✅ **Archivage** : Sessions de correction dans `docs/sessions/`

### Pour moi (Claude)

1. ✅ **Mémoire persistante** : Je peux toujours relire `CHANGES_TRACKER.md`
2. ✅ **Contexte global** : Je comprends l'impact de chaque modification
3. ✅ **Mise à jour précise** : Je sais exactement quoi mettre à jour
4. ✅ **Cohérence** : Je respecte le style de chaque fichier

---

## 🎯 Commandes que tu peux utiliser

### Mise à jour complète

```
"Actualise la documentation"
```
→ Je mets à jour tous les fichiers (CLAUDE.md + 3 README)

### Mise à jour ciblée

```
"Mets à jour CLAUDE.md uniquement"
"Mets à jour README-RUNPOD.md avec les changements de patch v3"
```
→ Je mets à jour seulement les fichiers demandés

### Vérification de l'état

```
"Quelles modifications ne sont pas encore documentées ?"
```
→ Je lis `CHANGES_TRACKER.md` et liste les checkboxes `[ ]`

### Archivage

```
"Archive les fichiers de correction du container51 dans docs/sessions/"
```
→ Je déplace les fichiers temporaires

---

## 📋 Checklist pour toi

### Après une session de modifications importantes

- [ ] Les modifications sont fonctionnelles et testées
- [ ] Claude a mis à jour `docs/CHANGES_TRACKER.md` (vérifier)
- [ ] Décider si mise à jour doc nécessaire maintenant ou plus tard
- [ ] Si maintenant : "Actualise la documentation"
- [ ] Si plus tard : Attendre la prochaine session

### Périodiquement (recommandé : toutes les 2-3 sessions)

- [ ] "Actualise la documentation"
- [ ] Vérifier que les 4 fichiers de doc sont cohérents
- [ ] Archiver les fichiers temporaires dans `docs/sessions/`
- [ ] Commit git si nécessaire

---

## 🚀 Prochaines étapes

### Immédiatement

1. ✅ Système de tracking créé
2. ✅ `docs/CHANGES_TRACKER.md` initialisé avec les modifications récentes
3. ✅ `docs/ARCHITECTURE.md` créé
4. ⏸️ Attente de ta demande pour mettre à jour `CLAUDE.md` et les `README`

### Quand tu voudras

Tu pourras me dire :
```
"Actualise la documentation avec toutes les modifications depuis la création du système de tracking"
```

Et je mettrai à jour :
- `CLAUDE.md` (version 3.2.0 avec patch v3, système de tracking, etc.)
- `README.md` (si nécessaire)
- `README-DOCKER.md` (patch automatique, etc.)
- `README-RUNPOD.md` (logs patch v3, vérifications, etc.)

---

## 💡 Bonnes pratiques

### Pour toi

1. ✅ Faire les modifications tranquillement
2. ✅ Tester que tout fonctionne
3. ✅ Demander "Actualise la documentation" quand tu juges pertinent
4. ✅ Ne pas hésiter à demander des mises à jour ciblées ("juste CLAUDE.md")

### Pour moi

1. ✅ Toujours mettre à jour `CHANGES_TRACKER.md` après une modification
2. ✅ Décrire l'impact global, pas juste le changement isolé
3. ✅ Attendre ta demande explicite pour actualiser la doc
4. ✅ Respecter le style de chaque fichier lors des mises à jour

---

## 📞 Questions / Support

Si tu as besoin de :
- Voir l'état actuel du tracking : "Montre-moi les modifications non documentées"
- Comprendre l'impact d'une modification : "Explique l'impact de [modification X]"
- Mettre à jour une section spécifique : "Mets à jour la section X de CLAUDE.md"

Demande-moi ! Je suis là pour ça. 😊

---

## 🎬 Conclusion

**Ce système te permet de** :
- ✅ Modifier le projet librement sans polluer la documentation
- ✅ Garder un historique complet de toutes les modifications
- ✅ Actualiser la documentation quand TU le décides
- ✅ Avoir une doc toujours à jour et cohérente

**Je m'occupe de** :
- ✅ Tracker toutes les modifications dans `CHANGES_TRACKER.md`
- ✅ Comprendre l'impact global de chaque changement
- ✅ Mettre à jour la doc sur demande en respectant le style de chaque fichier
- ✅ Cocher les checkboxes pour savoir ce qui est documenté

**Tu n'as qu'à dire** : "Actualise la documentation" quand tu le juges nécessaire ! 🚀
