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

echo "✅ Configuration terminée"
