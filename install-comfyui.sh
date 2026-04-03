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

# ComfyUI-PyramidFlowWrapper (pour RealESRGAN upscale video)
echo "Installing PyramidFlowWrapper..."
git clone https://github.com/kijai/ComfyUI-PyramidFlowWrapper.git
cd ComfyUI-PyramidFlowWrapper
if [ -f requirements.txt ]; then
    pip install --no-cache-dir -r requirements.txt
fi
cd ..

# ComfyUI-WanMoeKSampler (pour MoE WAN 2.2 14B - switching high/low noise experts)
echo "Installing WanMoeKSampler (MoE support for 14B)..."
git clone https://github.com/stduhpf/ComfyUI-WanMoeKSampler.git
cd ComfyUI-WanMoeKSampler
if [ -f requirements.txt ]; then
    pip install --no-cache-dir -r requirements.txt
fi
cd ..

# ComfyUI-LTXVideo (pour LTX 2.3 — looping sampler, STG guidance, Gemma encoder)
echo "Installing LTXVideo (LTX 2.3 support)..."
git clone https://github.com/Lightricks/ComfyUI-LTXVideo.git
cd ComfyUI-LTXVideo
if [ -f requirements.txt ]; then
    pip install --no-cache-dir -r requirements.txt
fi
cd ..

# RES4LYF (ClownSampler_Beta — solveur ODE haute qualite, full path officiel LTX 2.3 22B)
echo "Installing RES4LYF (ClownSampler_Beta for LTX 2.3 full path)..."
git clone https://github.com/ClownsharkBatwing/RES4LYF.git
cd RES4LYF
if [ -f requirements.txt ]; then
    pip install --no-cache-dir -r requirements.txt
fi
cd ..

cd /workspace/comfyui/ComfyUI

# Créer les dossiers de modèles
echo "Creating model directories..."
mkdir -p models/checkpoints/wan2.2-i2v-a14b
mkdir -p models/checkpoints/ltx-2.3-i2v-dev
mkdir -p models/vae
mkdir -p models/loras
mkdir -p models/upscale_models
mkdir -p models/controlnet
mkdir -p models/text_encoders
mkdir -p models/latent_upscale_models

echo ""
echo "✅ ComfyUI installed successfully"
echo "📦 Models will be copied during Docker build"
echo ""
