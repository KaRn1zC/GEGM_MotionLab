#!/bin/bash
set -e

echo "📂 Configuration des modèles pour WanVideoWrapper..."

# Créer le dossier diffusion_models
mkdir -p /workspace/comfyui/ComfyUI/models/diffusion_models

cd /workspace/comfyui/ComfyUI/models/diffusion_models

# Symlink pour 5B
if [ -d "../checkpoints/wan2.2-ti2v-5b" ]; then
    ln -sf ../checkpoints/wan2.2-ti2v-5b wan2.2-ti2v-5b
    echo "✅ Symlink créé: wan2.2-ti2v-5b"
fi

# Symlink pour 14B
if [ -d "../checkpoints/wan2.2-i2v-a14b" ]; then
    ln -sf ../checkpoints/wan2.2-i2v-a14b wan2.2-i2v-a14b
    echo "✅ Symlink créé: wan2.2-i2v-a14b"
fi

# Gestion du T5 Encoder
echo "📂 Configuration du T5 Encoder..."

# Note: Le T5 Encoder est maintenant téléchargé séparément depuis OwnCloud
# par docker-entrypoint.sh AVANT l'exécution de ce script.
# Les anciennes lignes qui créaient des symlinks vers les T5 dans les dossiers
# des modèles ont été supprimées car ces fichiers T5 sont incorrects/corrompus.

# Le T5 Encoder correct se trouve désormais à:
# /workspace/comfyui/ComfyUI/models/text_encoders/t5/umt5-xxl-enc-bf16.pth

# Créer le dossier text_encoders/t5 au cas où
mkdir -p /workspace/comfyui/ComfyUI/models/text_encoders/t5

# Vérifier que le T5 encoder a bien été téléchargé
if [ -f "/workspace/comfyui/ComfyUI/models/text_encoders/t5/umt5-xxl-enc-bf16.pth" ]; then
    echo "✅ T5 Encoder détecté: $(du -h /workspace/comfyui/ComfyUI/models/text_encoders/t5/umt5-xxl-enc-bf16.pth | cut -f1)"
else
    echo "⚠️  T5 Encoder non trouvé - WAN 2.2 ne fonctionnera pas!"
fi

echo "✅ Configuration terminée"
