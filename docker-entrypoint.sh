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

if [ ! -d "$MODEL_DIR" ] || [ -z "$(ls -A $MODEL_DIR)" ]; then
    echo ""
    echo "📥 Téléchargement du modèle depuis OwnCloud..."
    echo "   Ceci peut prendre 5-15 minutes..."
    
    python /workspace/scripts/download_models_from_owncloud.py \
        --model "$MODEL_NAME" \
        --target-dir /workspace/comfyui/ComfyUI/models/checkpoints
    
    if [ $? -eq 0 ]; then
        echo "✅ Modèle téléchargé"
        
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

# Configurer les symlinks pour diffusion_models
if [ -f "/workspace/scripts/setup_diffusion_models.sh" ]; then
    echo "🔗 Configuration des symlinks modèles..."
    bash /workspace/scripts/setup_diffusion_models.sh
fi

# ============================================
# PATCH WANVIDEOMODELLOADER (Sharded Support)
# ============================================

echo ""
echo "🔧 Application du patch WanVideoModelLoader..."

python3 << 'PATCH_PYTHON'
import re
import sys

node_file = "/workspace/comfyui/ComfyUI/custom_nodes/ComfyUI-WanVideoWrapper/nodes_model_loading.py"

try:
    with open(node_file, 'r') as f:
        content = f.read()
    
    # Vérifier si déjà patchés
    if 'def load_sharded_safetensors' in content:
        print("✅ Patch déjà appliqué")
        sys.exit(0)
    
    # 1. Ajouter import json
    if 'import json' not in content[:500]:
        content = content.replace('import os, gc, uuid', 'import os, gc, uuid\nimport json')
        print("✅ Import json ajouté")
    
    # 2. Ajouter la fonction
    new_function = '''

def load_sharded_safetensors(model_path_str, device="cpu"):
    """Charge tous les fichiers sharded si un index JSON existe"""
    from pathlib import Path
    from safetensors.torch import load_file
    
    model_path = Path(model_path_str)
    if not model_path.exists():
        return None
    
    parent_dir = model_path.parent
    possible_indices = [
        parent_dir / "diffusion_pytorch_model.safetensors.index.json",
        parent_dir / "high_noise_model.safetensors.index.json",
        parent_dir / f"{model_path.stem}.index.json",
    ]
    
    index_file = None
    for idx_path in possible_indices:
        if idx_path.exists():
            index_file = idx_path
            break
    
    if index_file:
        try:
            with open(index_file) as f:
                index = json.load(f)
            files_needed = set(index['weight_map'].values())
            all_tensors = {}
            for fname in sorted(files_needed):
                fpath = parent_dir / fname
                tensors = load_file(str(fpath), device=device)
                all_tensors.update(tensors)
            return all_tensors
        except Exception as e:
            log.error(f"Erreur chargement sharded: {e}")
            return None
    else:
        try:
            return load_file(str(model_path), device=device)
        except:
            return None
'''
    
    if 'def load_sharded_safetensors' not in content:
        insert_pos = content.find('update_folder_names_and_paths("unet_gguf"')
        insert_pos = content.find('\n', insert_pos) + 1
        content = content[:insert_pos] + new_function + content[insert_pos:]
        print("✅ Fonction load_sharded_safetensors ajoutée")
    
    # 3. Patcher l'appel load_torch_file
    pattern = r'(\s+)sd = load_torch_file\(model_path, device=transformer_load_device, safe_load=True\)'
    replacement = r'''\1# Charger via index JSON (sharded) ou fallback
\1sd = load_sharded_safetensors(model_path, device=transformer_load_device.type if hasattr(transformer_load_device, 'type') else str(transformer_load_device))
\1if sd is None:
\1    sd = load_torch_file(model_path, device=transformer_load_device, safe_load=True)'''
    
    if re.search(pattern, content):
        content = re.sub(pattern, replacement, content)
        print("✅ Appel load_torch_file patché")
    
    with open(node_file, 'w') as f:
        f.write(content)
    
    print("✅ Patch WanVideoModelLoader appliqué!")
    
except Exception as e:
    print(f"❌ Erreur: {e}")
    sys.exit(1)

PATCH_PYTHON

if [ $? -ne 0 ]; then
    echo "❌ Échec application du patch"
    exit 1
fi

# ============================================
# TÉLÉCHARGER LE BON VAE COMFYUI OFFICIEL
# ============================================

echo ""

echo "📥 Configuration du VAE ComfyUI officiel (48 canaux)..."

mkdir -p /workspace/comfyui/ComfyUI/models/vae

if [ ! -f "/workspace/comfyui/ComfyUI/models/vae/vae-kl-f8.safetensors" ]; then
    echo "   Téléchargement du VAE officiel..."
    cd /workspace/comfyui/ComfyUI/models/vae
    wget -q https://huggingface.co/stabilityai/sd-vae-ft-mse-original/resolve/main/diffusion_pytorch_model.safetensors -O vae-kl-f8.safetensors 2>/dev/null || \
    curl -L -o vae-kl-f8.safetensors https://huggingface.co/stabilityai/sd-vae-ft-mse-original/resolve/main/diffusion_pytorch_model.safetensors 2>/dev/null
    
    if [ -f "vae-kl-f8.safetensors" ] && [ -s "vae-kl-f8.safetensors" ]; then
        echo "✅ VAE officiel téléchargé"
    else
        echo "❌ Erreur téléchargement VAE"
        exit 1
    fi
else
    echo "✅ VAE officiel déjà présent"
fi

cd /workspace

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
