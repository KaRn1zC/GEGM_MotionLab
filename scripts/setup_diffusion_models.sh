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

# Symlink du T5 FP16 (partagé entre 5B et 14B)
# IMPORTANT: Utiliser chemin ABSOLU pour éviter problèmes de symlink cassé
if [ -f "/workspace/comfyui/ComfyUI/models/checkpoints/wan2.2-ti2v-5b/umt5_xxl_fp16.safetensors" ]; then
    ln -sf /workspace/comfyui/ComfyUI/models/checkpoints/wan2.2-ti2v-5b/umt5_xxl_fp16.safetensors \
           /workspace/comfyui/ComfyUI/models/text_encoders/t5/umt5_xxl_fp16.safetensors
    echo "✅ Symlink T5 créé: umt5_xxl_fp16.safetensors"

    # Créer symlink de compatibilité
    ln -sf /workspace/comfyui/ComfyUI/models/checkpoints/wan2.2-ti2v-5b/umt5_xxl_fp16.safetensors \
           /workspace/comfyui/ComfyUI/models/text_encoders/t5/umt5-xxl-enc-bf16.pth
    echo "✅ Symlink de compatibilité: umt5-xxl-enc-bf16.pth"
elif [ -f "/workspace/comfyui/ComfyUI/models/checkpoints/wan2.2-i2v-a14b/umt5_xxl_fp16.safetensors" ]; then
    ln -sf /workspace/comfyui/ComfyUI/models/checkpoints/wan2.2-i2v-a14b/umt5_xxl_fp16.safetensors \
           /workspace/comfyui/ComfyUI/models/text_encoders/t5/umt5_xxl_fp16.safetensors
    echo "✅ Symlink T5 créé: umt5_xxl_fp16.safetensors (14B)"

    # Créer symlink de compatibilité
    ln -sf /workspace/comfyui/ComfyUI/models/checkpoints/wan2.2-i2v-a14b/umt5_xxl_fp16.safetensors \
           /workspace/comfyui/ComfyUI/models/text_encoders/t5/umt5-xxl-enc-bf16.pth
    echo "✅ Symlink de compatibilité: umt5-xxl-enc-bf16.pth"
fi

echo "✅ Configuration terminée"
