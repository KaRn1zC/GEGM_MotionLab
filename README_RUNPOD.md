# 🚀 GEGM MotionLab - RunPod Deployment Guide

Guide complet de déploiement cloud sur RunPod avec GPUs professionnels.

**✨ NOUVEAUTÉS v2.0 :**

- Interface GEGM MotionLab rebranding complet
- Paramètres avancés avec tooltips interactifs
- Upload manuel OwnCloud (pas d'upload auto)
- Gestion intelligente du stockage Pod
- Support WAN 2.2 5B et 14B

---

## 📋 Prérequis

### GPU Recommandés

**WAN 2.2 5B (Production Standard) :**

- ⭐ **RTX 6000 Ada 48GB** : $0.77/h (~5 min/cinéma, $0.064/pièce)
- **H100 SXM 80GB** : $2.69/h (~2.5 min/cinéma, $0.11/pièce) - Vitesse

**WAN 2.2 14B (Qualité Premium) :**

- ⭐ **H100 SXM 80GB** : $2.69/h (~8 min/cinéma, $0.36/pièce)
- **H200 SXM 141GB** : $3.59/h (~5 min/cinéma, $0.30/pièce) - Vitesse

### Stockage

- **Container Disk** : 100GB minimum (uploads/logs)
- **Modèles WAN 2.2** : Se télécharge et se réassemble automatiquement

### Services

- **RunPod Account** : Avec crédits
- **Docker Hub** : Pour push de l'image (ou utiliser registry public)
- **OwnCloud** : Serveur de sauvegarde (optionnel)

---

## 🐳 Préparation de l'Image Docker

### Architecture : Image Légère + Modèles OwnCloud

**Stratégie adoptée :**
```
Image Docker (~8GB) OwnCloud (~37GB modèles)
                    ↓ ↓
RunPod Pod ← Télécharge modèles au démarrage
```

**Avantages :**

- ✅ Image Docker légère (~8GB vs 35-40GB)
- ✅ Build rapide (~10-15 min)
- ✅ Push Docker Hub rapide (~5-10 min)
- ✅ Flexibilité : choix du modèle 5B ou 14B au démarrage

**Inconvénient :**

- ⚠️ Téléchargement modèles au 1er démarrage Pod (~5-10 min)

---

## 📦 Workflow de Préparation Complet

### Prérequis Locaux

- **Python 3.11+** avec environnement virtuel activé
- **rclone** configuré pour OwnCloud
- **Docker** + **BuildX** pour multi-architecture
- **Espace disque** : 30GB minimum (workflow séquentiel)

### Configuration rclone (Une Fois Seulement)

**1. Installer rclone :**
macOS
```
brew install rclone
```

Linux
```
curl https://rclone.org/install.sh | sudo bash
```

**2. Configurer rclone pour OwnCloud :**
```
rclone config
```

Suivre les instructions :

- Name: owncloud
- Type: webdav
- URL: https://www.cloud-gegm.com/remote.php/dav
- Vendor: owncloud
- User: votre-username
- Password: votre-password

**3. Tester la connexion :**
```
make rclone-check
```

---

### Étape 1 : Télécharger les Modèles Localement

Télécharger les modèles (choix interactif)
```
make download-models
```

**Choix disponibles :**

- **Option 1** : WAN 2.2 5B (~11GB)
- **Option 2** : WAN 2.2 14B (~28GB)

**Astuce :** Vous pouvez télécharger un seul modèle si l'espace disque est limité.

---

### Étape 2 : Découper et Uploader sur OwnCloud

#### **Méthode Recommandée : Workflow Séquentiel** ⭐

**Avantage : Nécessite seulement ~30GB d'espace disque**

Workflow complet séquentiel :

1. Download 14B → Split → Upload → Clean
2. Download 5B → Split → Upload → Clean
3. Upload script de reconstitution
    ```
    make sequential-upload-workflow
    ```


**Ce que fait cette commande :**

```
┌─────────────────────────────────────────────────────────┐
│ 1. Télécharge modèle 14B (~28GB) │
│ 2. Découpe les fichiers >8GB en chunks de 2GB │
│ 3. Upload sur OwnCloud │
│ 4. Vérifie l'upload │
│ 5. Supprime les fichiers locaux (libère ~28GB) │
│ ───────────────────────────────────────────────────── │
│ 6. Télécharge modèle 5B (~11GB) │
│ 7. Découpe les fichiers >8GB en chunks de 2GB │
│ 8. Upload sur OwnCloud │
│ 9. Vérifie l'upload │
│ 10. Supprime les fichiers locaux (libère ~11GB) │
│ ───────────────────────────────────────────────────── │
│ 11. Upload script reassemble_models.sh │
└─────────────────────────────────────────────────────────┘
```

✅ Résultat : Tous les modèles sur OwnCloud, machine locale propre

**Durée totale estimée :** 45-90 minutes (dépend de votre connexion)

#### **Méthode Alternative : Workflow Complet**

**Nécessite ~54GB d'espace disque libre**

Télécharge TOUS les modèles, puis upload, puis clean
```
make full-upload-workflow
```

#### **Commandes Individuelles (Si Besoin)**

Upload modèle 14B seulement
```
make full-workflow-14b
```

Upload modèle 5B seulement
```
make full-workflow-5b
```

Upload script de reconstitution
```
make rclone-upload-reassemble-script
```

---

### Étape 3 : Vérifier l'Upload sur OwnCloud

**Vérifier la taille et présence des modèles :**
```
make rclone-verify
```

**Sortie attendue :**
📦 Modèle 14B:
Total objects: 156
Total size: 27.8 GB

📦 Modèle 5B:
Total objects: 87
Total size: 10.9 GB


**Lister les fichiers uploadés :**
```
make rclone-list
```

---

### Étape 4 : Nettoyer les Fichiers Locaux

**⚠️ Optionnel : Les workflows automatiques nettoient déjà**

Si vous avez utilisé des commandes individuelles :

Nettoyage profond (modèles + chunks + cache)
```
make models-deep-clean
```

Vérifier l'espace libéré
df -h .

---

### Étape 5 : Build et Push de l'Image Docker

#### **Option 1 : Déploiement Complet (Multi-Arch)** ⭐

Build AMD64 + ARM64 + Push Docker Hub (avec vérification OwnCloud)
```
make runpod-deploy
```

**Ce que fait cette commande :**

1. ✅ Vérifie la connexion OwnCloud
2. ✅ Configure Docker BuildX (multi-arch)
3. ✅ Build pour AMD64 (RunPod) + ARM64 (Mac M1/M2/M3)
4. ✅ Push vers Docker Hub

**Durée :** ~15-30 minutes

#### **Option 2 : Déploiement Rapide (AMD64 Seulement)**

Build AMD64 seulement + Push (plus rapide)
```
make runpod-deploy-quick
```

**Durée :** ~10-15 minutes

---

### Étape 6 : Vérifier l'Image sur Docker Hub

**URL :** https://hub.docker.com/r/arnaudboy/comfy_img_to_loop

**Vérifiez que les tags suivants existent :**

- `arnaudboy/comfy_img_to_loop:runpod`
- `arnaudboy/comfy_img_to_loop:latest`

---

## 📊 Résumé des Commandes Make


| Commande                          | Description                     | Espace Requis |
| --------------------------------- | ------------------------------- | ------------- |
| `make sequential-upload-workflow` | Workflow séquentiel (économe)   | ~30GB         |
| `make full-upload-workflow`       | Workflow complet (tous modèles) | ~54GB         |
| `make full-workflow-14b`          | Upload modèle 14B uniquement    | ~28GB         |
| `make full-workflow-5b`           | Upload modèle 5B uniquement     | ~11GB         |
| `make rclone-verify`              | Vérifier uploads OwnCloud       | -             |
| `make runpod-deploy`              | Build + Push image (multi-arch) | -             |
| `make runpod-deploy-quick`        | Build + Push image (AMD64 only) | -             |
| `make models-deep-clean`          | Nettoyage complet local         | -             |

---

## 🚀 Déploiement sur RunPod

### Étape 5 : Créer le Pod

**1. Aller sur https://runpod.io**

**2. Cliquer sur "Deploy" → "New Pod"**

**3. Configuration du Pod :**

**GPU :**

**Pour WAN 2.2 5B :**
- ⭐ **RTX 6000 Ada 48GB** ($0.77/h) - Recommandé
- **H100 SXM 80GB** ($2.69/h) - Vitesse pure

**Pour WAN 2.2 14B :**
- ⭐ **H100 SXM 80GB** ($2.69/h) - Recommandé
- **H200 SXM 141GB** ($3.99/h) - Vitesse max

**Container Configuration :**

```
Container Image: votreusername/comfy_img_to_loop:latest (pas nécessaire)
Container Disk: 100 GB minimum (par défaut)
Volume Disk: 0GB (modèles téléchargés au démarrage)
Expose HTTP Ports: 5000 (déjà renseigné)
Expose TCP Ports: (laisser vide)
Environment Variables : déjà renseignées dans le template via secrets
```

**4. Démarrer le Pod**

Cliquez sur "Deploy" et attendez le démarrage.
Le Pod doit télécharger l'image Docker, le modèle découpé en plusieurs parties puis installer le container et réassembler le modèle, le temps d'attente est donc relativement long (30mins à 1h).
Une fois toutes les étapes réalisées l'interface est indiqué comme "Actif" et la génération de cinemagraphs peut commencer

---

## ⚡ Démarrage Instantané

**✨ AVANTAGE MAJEUR :** Modèles pré-installés dans l'image Docker !

**Logs de démarrage attendus :**

```
🚀 Starting GEGM MotionLab on RunPod...
🎮 GPU: NVIDIA RTX 6000 Ada (48GB VRAM)
📦 ComfyUI: Installing...
✅ Models found in image:

- WAN 2.2 I2V 5B: 11GB ✅
- High noise model: ✅
- VAE: ✅
- Text encoders: ✅
  🎨 Starting ComfyUI...
  🌐 Starting Flask web interface...
  🎬 GEGM MotionLab ready!

Web Interface: https://xxxxx-5000.proxy.runpod.net
```

---

## 🌐 Accès à l'Interface

RunPod génère automatiquement une URL publique :

```
https://your-pod-id-5000.proxy.runpod.net
```

### Test de Connexion

```
# Health check

curl https://your-pod-id-5000.proxy.runpod.net/health

# Réponse attendue

{
"status": "healthy",
"services": {
"flask": "ok",
"comfyui": "ok",
"owncloud": "ok"
}
}
```

---

## 🎨 Utilisation de GEGM MotionLab

### Workflow de Production

**1. Accéder à l'interface**

```
https://your-pod-id-5000.proxy.runpod.net
```

**2. Upload d'image**

- Drag & drop ou cliquez "Choisir une image"
- Formats supportés : JPG, PNG, WebP
- Résolution recommandée : 1280x720 ou supérieure

**3. Configuration des paramètres**

**Presets rapides :**

- 💎 **Qualité Max** : 30 steps, CFG 8, denoise 80% (~8 min)
- ⚖️ **Équilibré** : 20 steps, CFG 7.5, denoise 75% (~5 min) ✅ Recommandé
- ⚡ **Rapide** : 15 steps, CFG 7, denoise 70% (~3 min)
- 🍃 **Naturel** : 20 steps, CFG 6, mouvement subtil (~5 min)

**Ou paramètres avancés (section dépliable) :**

- Steps : 5-100 (recommandé : 20-25)
- CFG Scale : 1-20 (recommandé : 7-8)
- Denoise : 0-100% (recommandé : 60-80%)
- Motion Intensity : Subtil / Modéré / Fort / Extrême
- Seed : -1 (aléatoire) ou nombre fixe (reproductibilité)
- - 8 autres paramètres avec tooltips explicatifs

**4. Génération**

Cliquez "🎬 Générer le Cinemagraph" et attendez :

- Prévisualisation en temps réel du statut
- Barre de progression
- Temps estimé affiché

**5. Résultat**

Une fois terminé :

- ▶️ Aperçu vidéo intégré
- 🎲 Seed utilisé affiché (pour reproductibilité)
- ⬇️ **Télécharger** : Backup local
- ☁️ **Sauvegarder** : Upload manuel OwnCloud
- 🗑️ **Supprimer** : Libérer l'espace Pod
- 🔄 **Nouvelle** : Recommencer

**⚠️ Important :** Les fichiers non sauvegardés sur OwnCloud seront perdus à la fermeture du Pod !

---

## 💾 Gestion du Stockage Pod

### Workflow Optimisé

```
Génération 1 → Aperçu → ❌ Pas satisfait → Clic "Supprimer"
Génération 2 → Aperçu → ❌ Pas satisfait → Clic "Supprimer"
Génération 3 → Aperçu → ✅ PARFAIT !
                ↓
Clic "Télécharger" (backup local)
                ↓
Clic "Sauvegarder" (OwnCloud permanent)
```

**Avantages :**

- ✅ 1 seul fichier uploadé sur OwnCloud (le bon)
- ✅ Pod léger (pas de pollution)
- ✅ OwnCloud organisé
- ✅ Économie de bande passante

### Suppression Automatique

Le système ne fait **PAS d'upload automatique** sur OwnCloud. Vous devez explicitement cliquer "☁️ Sauvegarder" pour ne pas perdre le travail généré.

---

## 💰 Coûts RunPod Détaillés

### WAN 2.2 5B

**GPU Recommandé : RTX 6000 Ada 48GB ($0.77/h)**

| Usage            | Durée | Coût Session | Cinemagraphs | Coût/Pièce |
| ---------------- | ----- | ------------ | ------------ | ---------- |
| Test rapide      | 2h    | $1.54        | ~24          | $0.064     |
| Session normale  | 6h    | $4.62        | ~72          | $0.064     |
| Journée complète | 8h    | $6.16        | ~96          | $0.064     |

**Alternative H100 SXM 80GB ($2.69/h) :**

| Usage            | Durée | Coût Session | Cinemagraphs | Coût/Pièce |
| ---------------- | ----- | ------------ | ------------ | ---------- |
| Test rapide      | 2h    | $5.38        | ~48          | $0.11      |
| Session normale  | 6h    | $16.14       | ~144         | $0.11      |
| Journée complète | 8h    | $21.52       | ~192         | $0.11      |

**Mensuel (10 sessions de 6h) :**
- RTX 6000 Ada : $46.20/mois (~720 cinemagraphs)
- H100 SXM : $161.40/mois (~1440 cinemagraphs)

---

### WAN 2.2 14B

**GPU Recommandé : H100 SXM 80GB ($2.69/h)**

| Usage            | Durée | Coût Session | Cinemagraphs | Coût/Pièce |
| ---------------- | ----- | ------------ | ------------ | ---------- |
| Test rapide      | 2h    | $5.38        | ~15          | $0.36      |
| Session normale  | 6h    | $16.14       | ~45          | $0.36      |
| Journée complète | 8h    | $21.52       | ~60          | $0.36      |

**Alternative H200 SXM 141GB ($3.99/h) :**

| Usage            | Durée | Coût Session | Cinemagraphs | Coût/Pièce |
| ---------------- | ----- | ------------ | ------------ | ---------- |
| Test rapide      | 2h    | $7.98        | ~20          | $0.40      |
| Session normale  | 6h    | $23.94       | ~60          | $0.40      |
| Journée complète | 8h    | $31.92       | ~80          | $0.40      |

**Mensuel (10 sessions de 6h) :**
- H100 SXM : $161.40/mois (~450 cinemagraphs)
- H200 SXM : $239.40/mois (~600 cinemagraphs)

---

## 🐛 Troubleshooting RunPod

### Pod ne démarre pas

```
# 1. Vérifier les logs RunPod

# Dans l'interface RunPod, cliquer sur "Logs"

# 2. Vérifier l'image Docker existe

# Sur Docker Hub : https://hub.docker.com/r/votreusername/comfy_img_to_loop

# 3. Vérifier les variables d'environnement

# OwnCloud credentials corrects ?
```

### Erreur "Modèles introuvables"

```
# Se connecter au Pod via SSH (bouton "Connect")

# Vérifier la présence des modèles

ls -lh /app/models/wan2.2-i2v-a5b/high_noise_model/

# Si absents, l'image Docker n'a pas inclus les modèles

# → Rebuild l'image avec les modèles en local
```

### ComfyUI ne répond pas

```
# SSH dans le Pod

# Vérifier le processus ComfyUI

ps aux | grep "python main.py"

# Voir les logs ComfyUI

cat /workspace/logs/comfyui.log

# Redémarrer ComfyUI

pkill -f "python main.py"
cd /workspace/comfyui/ComfyUI
python main.py --listen 0.0.0.0 --port 8188
```

### Upload OwnCloud échoue

```
# Tester la connexion depuis le Pod

curl -u username:password https://www.cloud-gegm.com/remote.php/dav/files/username/

# Vérifier les credentials dans les variables d'environnement

env | grep OWNCLOUD
```

### Interface web inaccessible

```
# Vérifier que le port 5000 est exposé

# Dans RunPod : Container Configuration → Expose HTTP Ports : 5000

# Tester en local dans le Pod

curl http://localhost:5000/health

# Si OK en local mais pas accessible de l'extérieur

# → Problème de configuration RunPod proxy
```

---

## 🔒 Sécurité

### Best Practices

- ✅ **Variables d'environnement** : Pas de credentials hardcodés
- ✅ **HTTPS uniquement** : OwnCloud via HTTPS
- ✅ **Utilisateur non-root** : UID 1000 dans Docker
- ✅ **Pas de données sensibles** : Dans l'image Docker
- ✅ **Secrets RunPod** : Utiliser "Secure Cloud" pour credentials

---

## ✅ Checklist de Déploiement

**Préparation Locale :**

- [ ] Modèles uploadés sur OwnCloud (via make sequential-upload-workflow)
- [ ] Vérification upload OwnCloud (make rclone-verify)
- [ ] Image Docker buildée (make runpod-deploy)
- [ ] Image pushée sur Docker Hub

**Configuration RunPod :**

- [ ] Pod créé avec GPU approprié (RTX 6000 Ada ou H100 SXM)
- [ ] Container Image configurée (votreusername/comfy_img_to_loop:latest)
- [ ] Container Disk : 100GB minimum
- [ ] Port 5000 exposé
- [ ] Variables d'environnement OwnCloud configurées
- [ ] Pod démarré avec succès

**Validation :**

- [ ] Health check répond "healthy"
- [ ] Interface web accessible
- [ ] ComfyUI fonctionne
- [ ] Test de génération réussi
- [ ] Upload OwnCloud manuel fonctionne
- [ ] Téléchargement local fonctionne
- [ ] Suppression de job fonctionne

---

## 🎯 Workflow Complet Résumé

```
# ═══════════════════════════════════════════════════════

# 1. PRÉPARATION LOCALE (une fois seulement)

# ═══════════════════════════════════════════════════════

# Télécharger les modèles

source .venv/bin/activate
./scripts/setup_wan22_native.sh \# Choisir option 1 ou 2

# Nettoyer

rm -rf models/wan2.2-i2v-_/.cache/
rm -rf models/wan2.2-i2v-_/low_noise_model/

# Vérifier

du -sh models/wan2.2-i2v-\* \# Devrait afficher ~11GB ou ~28GB

# Build Docker avec modèles inclus

docker buildx build \
--platform linux/amd64 \
--tag votreusername/comfy_img_to_loop:latest \
--push \
.

# Push vers Docker Hub

docker push votreusername/comfy_img_to_loop:latest

# ═══════════════════════════════════════════════════════

# 2. DÉPLOIEMENT RUNPOD

# ═══════════════════════════════════════════════════════

# Interface web RunPod :

# - GPU : RTX 6000 Ada (5B) ou H100 SXM 80GB (14B)

# - Image : votreusername/comfy_img_to_loop:latest

# - Container Disk : 100GB

# - Port : 5000

# - Env vars : OwnCloud credentials

# Démarrer le Pod → Attendre 30-60 minutes

# ═══════════════════════════════════════════════════════

# 3. UTILISATION

# ═══════════════════════════════════════════════════════

# Accéder à l'interface

https://xxxxx-5000.proxy.runpod.net

# Upload image → Choisir preset → Générer

# Résultat satisfait ?

# ✅ Télécharger (local)

# ✅ Sauvegarder (OwnCloud)

# ✅ Noter le seed (reproductibilité)

# Résultat non satisfait ?

# ❌ Supprimer (libérer Pod)

# 🔄 Nouvelle génération
```

---

## 📚 Ressources Complémentaires

- **[README Principal](README.md)** : Vue d'ensemble du projet
- **[Guide Docker](README_DOCKER.md)** : Déploiement local
- **RunPod Documentation** : https://docs.runpod.io
- **WAN 2.2 GitHub** : https://github.com/Wan-Video/Wan2.2

---

## 🆘 Support

- **Documentation** : Voir `/docs`
- **RunPod Discord** : https://discord.gg/runpod
- **Issues GitHub** : GitHub Issues (projet privé)
- **Contact** : arnaud.boy@gegmgroup.com

---

**© 2025 by KaRn1zC for GEGM Group - RunPod deployment guide v2.0**

**Développé avec ❤️ pour la création de cinemagraphs sur cloud GPU professionnel**
