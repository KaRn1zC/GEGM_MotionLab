#!/bin/bash
set -e

echo "🚀 Starting Comfy_Img_to_Loop on RunPod..."
echo "======================================================="

# Détecter le GPU
if command -v nvidia-smi &> /dev/null; then
    echo "🎮 GPU Information:"
    nvidia-smi --query-gpu=name,driver_version,memory.total --format=csv,noheader
    echo ""
else
    echo "⚠️  WARNING: nvidia-smi not found"
fi

# Info Python
echo "📋 Environment:"
echo "   Python: $(python --version)"
echo "   PyTorch: $(python -c 'import torch; print(torch.__version__)' 2>/dev/null || echo 'Not installed')"

if python -c 'import torch; exit(0 if torch.cuda.is_available() else 1)' 2>/dev/null; then
    echo "   CUDA Available: Yes"
    echo "   CUDA Version: $(python -c 'import torch; print(torch.version.cuda)')"
    echo "   GPU Count: $(python -c 'import torch; print(torch.cuda.device_count())')"
    echo "   GPU Name: $(python -c 'import torch; print(torch.cuda.get_device_name(0))')"
    echo "   GPU Memory: $(python -c 'import torch; print(f"{torch.cuda.get_device_properties(0).total_memory / 1024**3:.1f} GB")')"
fi

# ============================================
# TÉLÉCHARGEMENT DES MODÈLES DEPUIS OWNCLOUD
# ============================================

# Utiliser OWNCLOUD_MODEL_NAME ou par défaut wan2.2-ti2v-5b
MODEL_NAME="${OWNCLOUD_MODEL_NAME:-wan2.2-ti2v-5b}"
MODEL_DIR="/workspace/comfyui/ComfyUI/models/checkpoints/${MODEL_NAME}"

echo ""
echo "📦 Modèle configuré: $MODEL_NAME"

# Vérifier la présence des fichiers ComfyUI Native (Comfy-Org)
# 5B: wan2.2_ti2v_5B_fp16.safetensors
# 14B: wan2.2_i2v_high_noise_14B_fp8_scaled.safetensors + wan2.2_i2v_low_noise_14B_fp8_scaled.safetensors
if { [ "$MODEL_NAME" = "wan2.2-ti2v-5b" ] && [ ! -f "$MODEL_DIR/wan2.2_ti2v_5B_fp16.safetensors" ]; } || \
   { [ "$MODEL_NAME" = "wan2.2-i2v-a14b" ] && { [ ! -f "$MODEL_DIR/wan2.2_i2v_high_noise_14B_fp8_scaled.safetensors" ] || \
                                                  [ ! -f "$MODEL_DIR/wan2.2_i2v_low_noise_14B_fp8_scaled.safetensors" ]; }; }; then
    echo ""
    echo "📥 Téléchargement du modèle depuis OwnCloud..."
    echo "   Ceci peut prendre 5-15 minutes..."
    
    python /workspace/scripts/download_models_from_owncloud.py \
        --model "$MODEL_NAME" \
        --target-dir /workspace/comfyui/ComfyUI/models/checkpoints
    
    if [ $? -eq 0 ]; then
        echo "✅ Modèle téléchargé"

        echo ""
        echo "🔍 Vérification des fichiers téléchargés (ComfyUI Native)..."

        # Vérifier selon le modèle (ComfyUI Native format from Comfy-Org)
        if [ "$MODEL_NAME" = "wan2.2-ti2v-5b" ]; then
            # 5B: vérifier wan2.2_ti2v_5B_fp16.safetensors (~9.3GB)
            if [ ! -f "$MODEL_DIR/wan2.2_ti2v_5B_fp16.safetensors" ]; then
                echo "❌ Fichier manquant: wan2.2_ti2v_5B_fp16.safetensors"
                exit 1
            fi

            size=$(stat -f%z "$MODEL_DIR/wan2.2_ti2v_5B_fp16.safetensors" 2>/dev/null || stat -c%s "$MODEL_DIR/wan2.2_ti2v_5B_fp16.safetensors" 2>/dev/null)
            size_gb=$(echo "scale=2; $size / 1024 / 1024 / 1024" | bc)

            if [ $size -lt 8000000000 ]; then
                echo "❌ Modèle diffusion 5B incomplet: $size_gb GB (minimum 8GB)"
                exit 1
            fi

            echo "✅ wan2.2_ti2v_5B_fp16.safetensors: $size_gb GB"

        elif [ "$MODEL_NAME" = "wan2.2-i2v-a14b" ]; then
            # 14B: vérifier les deux fichiers high/low noise (~14GB chacun)
            for file in "wan2.2_i2v_high_noise_14B_fp8_scaled.safetensors" "wan2.2_i2v_low_noise_14B_fp8_scaled.safetensors"; do
                if [ ! -f "$MODEL_DIR/$file" ]; then
                    echo "❌ Fichier manquant: $file"
                    exit 1
                fi

                size=$(stat -f%z "$MODEL_DIR/$file" 2>/dev/null || stat -c%s "$MODEL_DIR/$file" 2>/dev/null)
                size_gb=$(echo "scale=2; $size / 1024 / 1024 / 1024" | bc)

                if [ $size -lt 12000000000 ]; then
                    echo "❌ $file incomplet: $size_gb GB (minimum 12GB)"
                    exit 1
                fi

                echo "✅ $file: $size_gb GB"
            done
        fi

        echo "✅ Tous les fichiers diffusion sont complets (ComfyUI Native)"
        
        # ============================================
        # RECONSTITUTION DES FICHIERS DÉCOUPÉS
        # ============================================
        
        CHUNKS_DIR="$MODEL_DIR/chunks"
        if [ -d "$CHUNKS_DIR" ] && [ -f "$CHUNKS_DIR/mapping.txt" ]; then
            echo ""
            echo "🔧 Reconstitution des fichiers découpés..."
            
            # Utiliser le script local
            if [ -f "/workspace/scripts/reassemble_models.sh" ]; then
                /workspace/scripts/reassemble_models.sh "$MODEL_DIR"
                
                if [ $? -eq 0 ]; then
                    echo "✅ Fichiers reconstitués et chunks supprimés"
                else
                    echo "❌ Échec de la reconstitution"
                    exit 1
                fi
            else
                echo "❌ Script reassemble_models.sh non trouvé"
                exit 1
            fi
        else
            echo "   Pas de chunks à reconstituer"
        fi

    else
        echo "❌ Échec téléchargement modèles"
        echo "⚠️  Vérifiez les credentials OwnCloud"
        exit 1
    fi
else
    echo ""
    echo "✅ Modèle déjà présent: $MODEL_NAME"
    du -sh "$MODEL_DIR"
fi

# ============================================
# SETUP DIFFUSION MODELS
# ============================================
# Configuration des symlinks pour diffusion_models et T5 Encoder
# Note: Le T5 Encoder est inclus dans le dossier du modèle WAN
# et sera symlinké par setup_diffusion_models.sh

echo ""
echo "🔗 Configuration des modèles et encodeurs..."

if [ -f "/workspace/scripts/setup_diffusion_models.sh" ]; then
    bash /workspace/scripts/setup_diffusion_models.sh
fi

# ============================================
# VAE COMFYUI (ComfyUI Native - déjà compatible 48 canaux)
# ============================================

echo ""
echo "✅ VAE ComfyUI Native inclus dans le modèle (déjà compatible 48 canaux)"

# Créer symlinks vers /models/vae/ pour WanVideoVAELoader
VAE_DIR="/workspace/comfyui/ComfyUI/models/vae"
mkdir -p "$VAE_DIR"

# Déterminer le nom du fichier VAE selon le modèle
if [ "$MODEL_NAME" = "wan2.2-ti2v-5b" ]; then
    VAE_SOURCE="$MODEL_DIR/wan2.2_vae.safetensors"
    echo "   Chemin source 5B: $VAE_SOURCE"
elif [ "$MODEL_NAME" = "wan2.2-i2v-a14b" ]; then
    VAE_SOURCE="$MODEL_DIR/wan_2.1_vae.safetensors"
    echo "   Chemin source 14B: $VAE_SOURCE"
fi

if [ -f "$VAE_SOURCE" ]; then
    # Créer symlink avec le nouveau nom
    ln -sf "$VAE_SOURCE" "$VAE_DIR/$(basename $VAE_SOURCE)"
    echo "   ✅ Symlink créé: $VAE_DIR/$(basename $VAE_SOURCE)"

    # Créer symlink de compatibilité avec l'ancien nom pour les workflows
    ln -sf "$VAE_SOURCE" "$VAE_DIR/Wan2.2_VAE.pth"
    echo "   ✅ Symlink de compatibilité: $VAE_DIR/Wan2.2_VAE.pth"
else
    echo "   ⚠️ VAE non trouvé: $VAE_SOURCE"
fi

# ============================================
# T5 ENCODER (ComfyUI Native - FP16)
# ============================================

echo ""
echo "✅ T5 Encoder ComfyUI Native (FP16)"

# Créer symlinks pour T5 Encoder
T5_DIR="/workspace/comfyui/ComfyUI/models/text_encoders/t5"
mkdir -p "$T5_DIR"

# Le T5 est le même pour 5B et 14B (partagé)
T5_SOURCE="$MODEL_DIR/umt5_xxl_fp16.safetensors"
echo "   Chemin source: $T5_SOURCE"

if [ -f "$T5_SOURCE" ]; then
    # Créer symlink avec le nom officiel
    ln -sf "$T5_SOURCE" "$T5_DIR/umt5_xxl_fp16.safetensors"
    echo "   ✅ Symlink créé: $T5_DIR/umt5_xxl_fp16.safetensors"

    # Créer symlink de compatibilité avec l'ancien nom pour les workflows
    ln -sf "$T5_SOURCE" "$T5_DIR/umt5-xxl-enc-bf16.pth"
    echo "   ✅ Symlink de compatibilité: $T5_DIR/umt5-xxl-enc-bf16.pth"
else
    echo "   ⚠️ T5 Encoder non trouvé: $T5_SOURCE"
fi

# Télécharger CLIP Vision si absent
CLIP_VISION_DIR="/workspace/comfyui/ComfyUI/models/clip_vision"
CLIP_VISION_FILE="$CLIP_VISION_DIR/clip-vit-large-patch14-336.safetensors"


if [ ! -f "$CLIP_VISION_FILE" ] || [ ! -s "$CLIP_VISION_FILE" ]; then
    echo ""
    echo "📥 Téléchargement de CLIP Vision (requis pour WAN 2.2, ~2.4GB)..."
    mkdir -p "$CLIP_VISION_DIR"
    
    # Utiliser le repo h94/IP-Adapter qui contient le bon fichier SafeTensors
    wget --progress=bar:force \
        "https://huggingface.co/h94/IP-Adapter/resolve/main/models/image_encoder/model.safetensors" \
        -O "$CLIP_VISION_FILE"
    
    if [ $? -eq 0 ] && [ -s "$CLIP_VISION_FILE" ]; then
        FILE_SIZE=$(du -h "$CLIP_VISION_FILE" | cut -f1)
        echo "✅ CLIP Vision téléchargé ($FILE_SIZE)"
    else
        echo "❌ Échec téléchargement CLIP Vision"
        rm -f "$CLIP_VISION_FILE"
        exit 1
    fi
else
    echo ""
    echo "✅ CLIP Vision déjà présent: $(du -h $CLIP_VISION_FILE | cut -f1)"
fi

# Télécharger RealESRGAN si absent
UPSCALE_DIR="/workspace/comfyui/ComfyUI/models/upscale_models"
UPSCALE_FILE="$UPSCALE_DIR/RealESRGAN_x4plus.pth"

if [ ! -f "$UPSCALE_FILE" ]; then
    echo ""
    echo "📥 Téléchargement de RealESRGAN (requis pour upscale)..."
    mkdir -p "$UPSCALE_DIR"
    
    wget -q --show-progress \
        "https://github.com/xinntao/Real-ESRGAN/releases/download/v0.1.0/RealESRGAN_x4plus.pth" \
        -O "$UPSCALE_FILE"
    
    if [ $? -eq 0 ]; then
        echo "✅ RealESRGAN téléchargé ($(du -h $UPSCALE_FILE | cut -f1))"
    else
        echo "⚠️ Échec téléchargement RealESRGAN (upscale désactivé)"
    fi
else
    echo ""
    echo "✅ RealESRGAN déjà présent: $(du -h $UPSCALE_FILE | cut -f1)"
fi

# ============================================
# COMFYUI
# ============================================

if [ ! -d "/workspace/comfyui/ComfyUI" ]; then
    echo ""
    echo "📦 Installing ComfyUI..."
    /workspace/install-comfyui.sh
else
    echo ""
    echo "✅ ComfyUI installed"
fi

# ============================================
# Démarrer ComfyUI
echo ""
echo "🎨 Starting ComfyUI on port 8188..."
cd /workspace/comfyui/ComfyUI

# Créer le dossier de logs
mkdir -p /workspace/logs

nohup python main.py \
    --listen 0.0.0.0 \
    --port 8188 \
    --preview-method auto \
    > /workspace/logs/comfyui.log 2>&1 &

COMFYUI_PID=$!
echo "   ComfyUI PID: $COMFYUI_PID"

echo "   Waiting for ComfyUI (up to 3 minutes)..."
COMFYUI_READY=false

for i in {1..90}; do
    # Vérifier que le processus est toujours actif
    if ! kill -0 $COMFYUI_PID 2>/dev/null; then
        echo ""
        echo "   ❌ ComfyUI process died! Last 20 lines of log:"
        tail -n 20 /workspace/logs/comfyui.log
        exit 1
    fi

    # Tester l'endpoint /system_stats (plus fiable que la racine)
    if curl -s http://localhost:8188/system_stats > /dev/null 2>&1; then
        echo ""
        echo "   ✅ ComfyUI ready!"
        COMFYUI_READY=true
        break
    fi

    # Afficher un point de progression toutes les 10 secondes
    if [ $((i % 5)) -eq 0 ]; then
        echo -n "."
    fi

    sleep 2
done

echo ""

if [ "$COMFYUI_READY" = false ]; then
    echo ""
    echo "   ❌ ComfyUI failed to start after 3 minutes"
    echo "   📋 Last 30 lines of ComfyUI log:"
    echo "   ================================================"
    tail -n 30 /workspace/logs/comfyui.log
    echo "   ================================================"
    echo ""
    echo "   💡 Common issues:"
    echo "      - Missing dependencies (check requirements.txt)"
    echo "      - GPU not available (check nvidia-smi)"
    echo "      - Model files corrupted or missing"
    echo "      - Out of memory"
    exit 1
fi

cd /workspace

# Dossiers
mkdir -p logs web_interface/uploads

# .env
if [ -f ".env" ]; then
    echo ""
    echo "✅ .env file found"
else
    echo ""
    echo "⚠️  WARNING: .env not found"
fi

echo ""
echo "🎬 Comfy_Img_to_Loop ready on RunPod!"
echo "   Web Interface: Port 5000"
echo "   ComfyUI API: http://localhost:8188"
echo "======================================================="
echo ""

# Variables
export FLASK_HOST=${FLASK_HOST:-0.0.0.0}
export FLASK_PORT=${FLASK_PORT:-5000}
export COMFYUI_HOST=${COMFYUI_HOST:-127.0.0.1}
export COMFYUI_PORT=${COMFYUI_PORT:-8188}

exec "$@"
