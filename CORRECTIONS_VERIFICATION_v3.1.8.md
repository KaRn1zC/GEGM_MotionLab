# Corrections Vérification d'Intégrité - v3.1.8

Date: 2025-11-14
Auteur: Claude Code

## Résumé

Correction majeure de la logique de vérification d'intégrité suite à une confusion entre les clés du **modèle de diffusion WAN 2.2** et celles du **T5 Encoder**.

---

## ❌ Problème identifié

### Le bug
Le script `verify_t5_integrity.py` vérifiait les **MAUVAISES clés** :
- Il cherchait `blocks.*.ffn.0.weight` dans le fichier T5
- **MAIS** ces clés appartiennent au **modèle de diffusion**, pas au T5 !

### Ordre d'exécution incorrect
Dans `setup_wan22_native.sh`, l'ordre était :
1. Téléchargement
2. **Vérification T5** ❌ (avant fusion)
3. Fusion safetensors
4. Suppression sharded

**Résultat** : Erreur systématique car les clés vérifiées n'existaient pas dans le T5.

---

## ✅ Corrections apportées

### 1. Nouveau script `verify_diffusion_model.py`

**Créé** : `scripts/verify_diffusion_model.py`

Vérifie le **modèle de diffusion fusionné** (`diffusion_pytorch_model.safetensors`) avec les **bonnes clés** :

```python
critical_keys = [
    "blocks.0.ffn.0.weight",   # Premier bloc
    "blocks.14.ffn.0.weight",  # Bloc milieu (causait l'erreur !)
    "blocks.23.ffn.0.weight",  # Dernier bloc
]
```

**Fonctionnement** :
- Vérifie que le fichier fusionné existe
- Charge avec `safetensors.torch.safe_open()`
- Vérifie les clés critiques du modèle de diffusion
- Vérifie les dimensions des tenseurs
- Tailles attendues : 5B (~18.6 GB), 14B (~28 GB)

### 2. Script `verify_t5_integrity.py` corrigé

**Modifié** : Clés critiques du T5 Encoder

**AVANT** (INCORRECT) :
```python
critical_keys = [
    "token_embedding.weight",
    "blocks.0.ffn.0.weight",      # ❌ N'existe PAS dans T5 !
    "blocks.14.ffn.0.weight",     # ❌ N'existe PAS dans T5 !
    "blocks.23.ffn.0.weight",     # ❌ N'existe PAS dans T5 !
    "final_norm.weight",          # ❌ N'existe PAS dans T5 !
]
```

**APRÈS** (CORRECT) :
```python
critical_keys = [
    "token_embedding.weight",
    "blocks.0.ffn.gate.0.weight",   # ✅ Structure réelle du T5
    "blocks.0.ffn.fc1.weight",      # ✅ Structure réelle du T5
    "blocks.14.ffn.gate.0.weight",  # ✅ Structure réelle du T5
    "blocks.14.ffn.fc1.weight",     # ✅ Structure réelle du T5
    "blocks.23.ffn.gate.0.weight",  # ✅ Structure réelle du T5
    "blocks.23.ffn.fc2.weight",     # ✅ Structure réelle du T5
    "norm.weight",                  # ✅ (pas "final_norm.weight")
]
```

**Structure réelle du T5 Encoder** :
- 242 clés au total
- Blocs : `blocks.0` à `blocks.23` (24 layers)
- Structure FFN : `blocks.*.ffn.gate.0.weight`, `blocks.*.ffn.fc1.weight`, `blocks.*.ffn.fc2.weight`
- Norm final : `norm.weight` (pas "final_norm.weight")

### 3. Ordre d'exécution corrigé dans `setup_wan22_native.sh`

**AVANT** :
```bash
1. Téléchargement
2. Vérification T5 ❌ (avant fusion)
3. Fusion safetensors
4. Suppression sharded
```

**APRÈS** :
```bash
1. Téléchargement
2. Fusion safetensors ✅
3. Vérification modèle de diffusion ✅ (nouveau)
4. Vérification T5 ✅
5. Suppression sharded ✅
```

**Raison** :
- Le modèle de diffusion doit être fusionné **AVANT** vérification (sinon les clés sont dispersées dans 3 fichiers)
- Le T5 est déjà dans un fichier unique, donc peut être vérifié à tout moment après téléchargement
- Les vérifications **AVANT** suppression sharded permettent de garder une copie de secours en cas d'erreur

**Modifié dans 4 endroits** :
1. Cas "all" - modèle 5B
2. Cas "all" - modèle 14B
3. Cas "wan2.2-i2v-a14b"
4. Cas "wan2.2-ti2v-5b"

---

## 🎯 Résultat attendu

### Workflow complet (make full-workflow-5b)

```bash
📥 Téléchargement WAN 2.2 TI2V 5B (9.4GB)...
  → diffusion_pytorch_model-00001-of-00003.safetensors
  → diffusion_pytorch_model-00002-of-00003.safetensors
  → diffusion_pytorch_model-00003-of-00003.safetensors
  → models_t5_umt5-xxl-enc-bf16.pth
  → Wan2.2_VAE.pth
✅ WAN 2.2 5B téléchargé

🔧 Fusion des fichiers safetensors...
  → Lecture des 3 fichiers sharded
  → Fusion en diffusion_pytorch_model.safetensors (18.63 GB, 825 clés)
✅ Fichier fusionné

🔍 Vérification intégrité modèle de diffusion...
  → Chargement diffusion_pytorch_model.safetensors
  → Vérification clé blocks.0.ffn.0.weight ✅
  → Vérification clé blocks.14.ffn.0.weight ✅
  → Vérification clé blocks.23.ffn.0.weight ✅
✅ Modèle de diffusion COMPLET et VALIDE

🔍 Vérification intégrité T5 Encoder...
  → Chargement models_t5_umt5-xxl-enc-bf16.pth (10.58 GB, 242 clés)
  → Vérification clé token_embedding.weight ✅
  → Vérification clé blocks.0.ffn.gate.0.weight ✅
  → Vérification clé blocks.14.ffn.fc1.weight ✅
  → Vérification clé blocks.23.ffn.fc2.weight ✅
  → Vérification clé norm.weight ✅
✅ T5 Encoder COMPLET et VALIDE

🗑️  Suppression des fichiers sharded...
✅ Fichiers sharded supprimés (économie ~18.5 GB)
```

---

## 📊 Impact

### Fichiers créés
- `scripts/verify_diffusion_model.py` (nouveau, 224 lignes)

### Fichiers modifiés
- `scripts/verify_t5_integrity.py` (clés corrigées, lignes 105-113 et 155-157)
- `scripts/setup_wan22_native.sh` (ordre corrigé, 4 emplacements)

### Protection renforcée
- **2 vérifications d'intégrité** au lieu d'1 (diffusion + T5)
- **Détection précoce** des fichiers corrompus (avant upload sur OwnCloud)
- **Messages d'erreur clairs** avec solutions détaillées

---

## 🔍 Différence clés T5 vs Diffusion

### Modèle de diffusion (`diffusion_pytorch_model.safetensors`)
```
Structure : blocks.*.ffn.0.weight
Exemple : blocks.14.ffn.0.weight
```

### T5 Encoder (`models_t5_umt5-xxl-enc-bf16.pth`)
```
Structure : blocks.*.ffn.{gate|fc1|fc2}.0.weight
Exemple : blocks.14.ffn.gate.0.weight
          blocks.14.ffn.fc1.weight
          blocks.14.ffn.fc2.weight
```

**Confusion initiale** : Le nom "blocks.14.ffn.*.weight" existe dans les deux, mais avec des sous-structures différentes !

---

## ✅ Validation

### Test du workflow complet
```bash
# Supprimer le modèle actuel
rm -rf models/wan2.2-ti2v-5b

# Relancer le téléchargement avec vérifications corrigées
./scripts/setup_wan22_native.sh wan2.2-ti2v-5b

# Vérifier les logs
# ✅ Fusion OK
# ✅ Vérification diffusion OK
# ✅ Vérification T5 OK
# ✅ Suppression sharded OK
```

---

**Corrections effectuées avec succès !** Le workflow v3.1.8 est maintenant robuste et vérifie correctement les deux modèles séparément.
