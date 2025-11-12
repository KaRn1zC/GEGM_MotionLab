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

# Créer le dossier text_encoders/t5
mkdir -p /workspace/comfyui/ComfyUI/models/text_encoders/t5

# Symlink du T5 pour 5B
if [ -f "/workspace/comfyui/ComfyUI/models/checkpoints/wan2.2-ti2v-5b/models_t5_umt5-xxl-enc-bf16.pth" ]; then
    ln -sf ../../checkpoints/wan2.2-ti2v-5b/models_t5_umt5-xxl-enc-bf16.pth /workspace/comfyui/ComfyUI/models/text_encoders/t5/umt5-xxl-enc-bf16.pth
    echo "✅ Symlink T5 créé: umt5-xxl-enc-bf16.pth (5B)"
fi

# Symlink du T5 pour 14B
if [ -f "/workspace/comfyui/ComfyUI/models/checkpoints/wan2.2-i2v-a14b/models_t5_umt5-xxl-enc-bf16.pth" ]; then
    if [ ! -L "/workspace/comfyui/ComfyUI/models/text_encoders/t5/umt5-xxl-enc-bf16.pth" ]; then
        ln -sf ../../checkpoints/wan2.2-i2v-a14b/models_t5_umt5-xxl-enc-bf16.pth /workspace/comfyui/ComfyUI/models/text_encoders/t5/umt5-xxl-enc-bf16_14B.pth
        echo "✅ Symlink T5 créé: umt5-xxl-enc-bf16_14B.pth (14B)"
    fi
fi

echo "✅ Configuration terminée"
