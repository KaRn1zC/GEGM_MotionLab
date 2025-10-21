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
MODEL_DIR="/workspace/comfyui/ComfyUI/models/diffusion_models/${MODEL_NAME}"

echo ""
echo "📦 Modèle configuré: $MODEL_NAME"

if [ ! -d "$MODEL_DIR" ] || [ -z "$(ls -A $MODEL_DIR)" ]; then
    echo ""
    echo "📥 Téléchargement du modèle depuis OwnCloud..."
    echo "   Ceci peut prendre 5-15 minutes..."
    
    python /workspace/scripts/download_models_from_owncloud.py \
        --model "$MODEL_NAME" \
        --target-dir /workspace/comfyui/ComfyUI/models/diffusion_models
    
    if [ $? -eq 0 ]; then
        echo "✅ Modèle téléchargé"
        
        # ============================================
        # RECONSTITUTION DES FICHIERS DÉCOUPÉS
        # ============================================
        
        CHUNKS_DIR="$MODEL_DIR/chunks"
        if [ -d "$CHUNKS_DIR" ] && [ -f "$CHUNKS_DIR/mapping.txt" ]; then
            echo ""
            echo "🔧 Reconstitution des fichiers découpés..."
            
            # Télécharger le script de reconstitution
            echo "📥 Téléchargement du script de reconstitution..."
            rclone copy owncloud:/GEGM_ComfyUI/scripts/reassemble_models.sh /tmp/
            chmod +x /tmp/reassemble_models.sh
            
            # Exécuter la reconstitution
            /tmp/reassemble_models.sh "$MODEL_DIR"
            
            if [ $? -eq 0 ]; then
                echo "✅ Fichiers reconstitués"
            else
                echo "❌ Échec de la reconstitution"
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

# Démarrer ComfyUI
echo ""
echo "🎨 Starting ComfyUI on port 8188..."
cd /workspace/comfyui/ComfyUI

nohup python main.py \
    --listen 0.0.0.0 \
    --port 8188 \
    --preview-method auto \
    > /workspace/logs/comfyui.log 2>&1 &

COMFYUI_PID=$!
echo "   ComfyUI PID: $COMFYUI_PID"

echo "   Waiting for ComfyUI..."
for i in {1..30}; do
    if curl -s http://localhost:8188 > /dev/null 2>&1; then
        echo "   ✅ ComfyUI ready!"
        break
    fi
    if [ "$i" -eq 30 ]; then
        echo "   ⚠️  Check logs: /workspace/logs/comfyui.log"
    fi
    sleep 2
done

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
