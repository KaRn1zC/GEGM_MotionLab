#!/bin/bash
set -e

echo "📦 Installing ComfyUI for RunPod B200/H200..."
echo "==============================================="

# Créer le dossier comfyui
mkdir -p /workspace/comfyui
cd /workspace/comfyui

# Cloner ComfyUI
echo "Cloning ComfyUI repository..."
git clone https://github.com/comfyanonymous/ComfyUI.git
cd ComfyUI

# Installer les dépendances
echo "Installing ComfyUI dependencies..."
pip install --no-cache-dir -r requirements.txt

# Installer les custom nodes nécessaires
cd custom_nodes

# ComfyUI-VideoHelperSuite (pour VHS_VideoCombine)
echo "Installing VideoHelperSuite..."
git clone https://github.com/Kosinkadink/ComfyUI-VideoHelperSuite.git
cd ComfyUI-VideoHelperSuite
pip install --no-cache-dir -r requirements.txt
cd ..

# ComfyUI-WanVideoWrapper (pour WAN 2.2 support)
echo "Installing WanVideoWrapper..."
git clone https://github.com/kijai/ComfyUI-WanVideoWrapper.git
cd ComfyUI-WanVideoWrapper

# Installer les dépendances
if [ -f requirements.txt ]; then
    echo "Installing WanVideoWrapper dependencies..."
    pip install --no-cache-dir -r requirements.txt
else
    echo "⚠️ No requirements.txt found in WanVideoWrapper, using manual install"
    pip install --no-cache-dir diffusers transformers accelerate
fi

# Pas de patches nécessaires - WanVideoWrapper fonctionne nativement
cd ..

cd /workspace/comfyui/ComfyUI

# Créer les dossiers de modèles
echo "Creating model directories..."
mkdir -p models/checkpoints/wan2.2-i2v-a14b
mkdir -p models/vae
mkdir -p models/loras
mkdir -p models/upscale_models
mkdir -p models/controlnet

echo ""
echo "✅ ComfyUI installed successfully"
echo "📦 Models will be copied during Docker build"
echo ""
