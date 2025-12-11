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
# TÉLÉCHARGEMENT DES MODÈLES (UPSTREAM + FALLBACK OWNCLOUD)
# ============================================

# Utiliser OWNCLOUD_MODEL_NAME ou par défaut wan2.2-ti2v-5b
MODEL_NAME="${OWNCLOUD_MODEL_NAME:-wan2.2-ti2v-5b}"
MODEL_DIR="/workspace/comfyui/ComfyUI/models/checkpoints/${MODEL_NAME}"

echo ""
echo "📦 Modèle configuré: $MODEL_NAME"

# Vérifier la présence des fichiers ComfyUI Native (Comfy-Org)
# 5B: wan2.2_ti2v_5B_fp16.safetensors
# 14B: wan2.2_i2v_high_noise_14B_fp16.safetensors + wan2.2_i2v_low_noise_14B_fp16.safetensors
if { [ "$MODEL_NAME" = "wan2.2-ti2v-5b" ] && [ ! -f "$MODEL_DIR/wan2.2_ti2v_5B_fp16.safetensors" ]; } || \
   { [ "$MODEL_NAME" = "wan2.2-i2v-a14b" ] && { [ ! -f "$MODEL_DIR/wan2.2_i2v_high_noise_14B_fp16.safetensors" ] || \
                                                  [ ! -f "$MODEL_DIR/wan2.2_i2v_low_noise_14B_fp16.safetensors" ]; }; }; then

    DOWNLOAD_SUCCESS=false
    USE_OWNCLOUD_FALLBACK=false

    # ========================================
    # ÉTAPE 1: HEALTHCHECK UPSTREAM
    # ========================================
    echo ""
    echo "🔍 Vérification de la disponibilité des sources upstream..."
    echo "   (HuggingFace + GitHub)"

    # Désactiver exit-on-error temporairement pour capturer le exit code
    set +e
    python /workspace/scripts/check_upstream_health.py "$MODEL_NAME"
    HEALTHCHECK_EXIT_CODE=$?
    set -e  # Réactiver exit-on-error

    if [ $HEALTHCHECK_EXIT_CODE -eq 0 ]; then
        echo ""
        echo "✅ Sources upstream disponibles et versions correctes"
        echo "📥 Téléchargement depuis upstream (HuggingFace + GitHub)..."
        echo "   Ceci peut prendre 10-30 minutes selon la connexion..."

        # ========================================
        # ÉTAPE 2: TÉLÉCHARGEMENT UPSTREAM
        # ========================================
        if [ -f "/workspace/scripts/setup_wan22_native.sh" ]; then
            bash /workspace/scripts/setup_wan22_native.sh "$MODEL_NAME"

            if [ $? -eq 0 ]; then
                echo ""
                echo "✅ Téléchargement upstream réussi"

                # Déplacer les fichiers vers le répertoire ComfyUI
                echo "📦 Déplacement des fichiers vers ComfyUI..."
                mkdir -p /workspace/comfyui/ComfyUI/models/checkpoints

                # Déplacer le dossier du modèle
                if [ -d "/workspace/models/$MODEL_NAME" ]; then
                    mv /workspace/models/$MODEL_NAME /workspace/comfyui/ComfyUI/models/checkpoints/
                    echo "   ✅ Modèle déplacé: $MODEL_NAME"
                fi

                # Déplacer diffusion_models, text_encoders, vae si présents
                for dir in diffusion_models text_encoders vae; do
                    if [ -d "/workspace/models/$dir" ]; then
                        mv /workspace/models/$dir /workspace/comfyui/ComfyUI/models/checkpoints/
                        echo "   ✅ Dossier déplacé: $dir"
                    fi
                done

                # Recréer les symlinks dans le dossier du modèle (fix: symlinks cassés après déplacement)
                echo "🔗 Recréation des symlinks dans $MODEL_NAME..."
                cd /workspace/comfyui/ComfyUI/models/checkpoints
                if [ -d "$MODEL_NAME" ]; then
                    cd "$MODEL_NAME"
                    # Supprimer les symlinks cassés
                    find . -maxdepth 1 -type l -delete

                    # Recréer les symlinks avec les bons chemins relatifs
                    if [ "$MODEL_NAME" = "wan2.2-ti2v-5b" ]; then
                        ln -sf ../diffusion_models/wan2.2_ti2v_5B_fp16.safetensors .
                        ln -sf ../text_encoders/umt5_xxl_fp16.safetensors .
                        ln -sf ../vae/wan2.2_vae.safetensors .
                        echo "   ✅ Symlinks 5B recréés"
                    elif [ "$MODEL_NAME" = "wan2.2-i2v-a14b" ]; then
                        ln -sf ../diffusion_models/wan2.2_i2v_high_noise_14B_fp16.safetensors .
                        ln -sf ../diffusion_models/wan2.2_i2v_low_noise_14B_fp16.safetensors .
                        ln -sf ../text_encoders/umt5_xxl_fp16.safetensors .
                        ln -sf ../vae/wan_2.1_vae.safetensors .
                        echo "   ✅ Symlinks 14B recréés"
                    fi
                    cd /workspace
                fi

                # Nettoyer le dossier models temporaire
                rm -rf /workspace/models

                DOWNLOAD_SUCCESS=true
            else
                echo ""
                echo "❌ Échec du téléchargement upstream"
                echo "🧹 Nettoyage des fichiers partiels..."

                # Cleanup des fichiers partiels
                python /workspace/scripts/cleanup_partial_downloads.py --model "$MODEL_NAME"

                echo "⚠️  Basculement vers OwnCloud (fallback)..."
                USE_OWNCLOUD_FALLBACK=true
            fi
        else
            echo "❌ Script setup_wan22_native.sh non trouvé"
            echo "⚠️  Basculement vers OwnCloud (fallback)..."
            USE_OWNCLOUD_FALLBACK=true
        fi

    else
        echo ""
        echo "⚠️  Sources upstream non disponibles ou versions différentes"
        echo "   Raisons possibles:"
        echo "   - Nouvelle version upstream détectée (nécessite validation)"
        echo "   - Fichiers temporairement indisponibles"
        echo "   - Erreur réseau"
        echo ""
        echo "→ Basculement vers OwnCloud (version stable et testée)"
        USE_OWNCLOUD_FALLBACK=true
    fi

    # ========================================
    # ÉTAPE 3: FALLBACK OWNCLOUD SI NÉCESSAIRE
    # ========================================
    if [ "$USE_OWNCLOUD_FALLBACK" = true ]; then
        echo ""
        echo "📥 Téléchargement depuis OwnCloud (fallback)..."
        echo "   Version stable et testée"
        echo "   Ceci peut prendre 5-15 minutes..."

        python /workspace/scripts/download_models_from_owncloud.py \
            --model "$MODEL_NAME" \
            --target-dir /workspace/comfyui/ComfyUI/models/checkpoints

        if [ $? -eq 0 ]; then
            echo "✅ Modèle téléchargé depuis OwnCloud"
            DOWNLOAD_SUCCESS=true
        else
            echo "❌ Échec téléchargement depuis OwnCloud"
            echo "⚠️  Vérifiez les credentials OwnCloud"
            exit 1
        fi
    fi

    # ========================================
    # ÉTAPE 4: VÉRIFICATION POST-TÉLÉCHARGEMENT
    # ========================================
    if [ "$DOWNLOAD_SUCCESS" = true ]; then
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
            # 14B: vérifier les deux fichiers high/low noise FP16 (~28GB chacun)
            for file in "wan2.2_i2v_high_noise_14B_fp16.safetensors" "wan2.2_i2v_low_noise_14B_fp16.safetensors"; do
                if [ ! -f "$MODEL_DIR/$file" ]; then
                    echo "❌ Fichier manquant: $file"
                    exit 1
                fi

                size=$(stat -f%z "$MODEL_DIR/$file" 2>/dev/null || stat -c%s "$MODEL_DIR/$file" 2>/dev/null)
                size_gb=$(echo "scale=2; $size / 1024 / 1024 / 1024" | bc)

                if [ $size -lt 25000000000 ]; then
                    echo "❌ $file incomplet: $size_gb GB (minimum 25GB)"
                    exit 1
                fi

                echo "✅ $file: $size_gb GB"
            done
        fi

        echo "✅ Tous les fichiers diffusion sont complets (ComfyUI Native)"

        # ============================================
        # RECONSTITUTION DES FICHIERS DÉCOUPÉS (si OwnCloud fallback)
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
        echo "❌ Échec téléchargement - tous les chemins ont échoué"
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
    echo "   Chemin source 5B: $VAE_SOURCE (1.41 GB)"
elif [ "$MODEL_NAME" = "wan2.2-i2v-a14b" ]; then
    VAE_SOURCE="$MODEL_DIR/wan_2.1_vae.safetensors"
    echo "   Chemin source 14B: $VAE_SOURCE (254 MB - VAE 2.1 spécifique au 14B)"
fi

if [ -f "$VAE_SOURCE" ]; then
    # Copier le VAE au lieu de créer un symlink (fix: WanVideoVAELoader ne suit pas toujours les symlinks)
    cp "$VAE_SOURCE" "$VAE_DIR/$(basename $VAE_SOURCE)"
    echo "   ✅ VAE copié: $VAE_DIR/$(basename $VAE_SOURCE)"
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
    # Créer symlink
    ln -sf "$T5_SOURCE" "$T5_DIR/umt5_xxl_fp16.safetensors"
    echo "   ✅ Symlink créé: $T5_DIR/umt5_xxl_fp16.safetensors"
else
    echo "   ⚠️ T5 Encoder non trouvé: $T5_SOURCE"
fi

# ============================================
# CLIP VISION + UPSCALERS (depuis OwnCloud ou fallback upstream)
# ============================================

echo ""
echo "🔧 Configuration CLIP Vision + Upscalers..."

CLIP_VISION_DIR="/workspace/comfyui/ComfyUI/models/clip_vision"
CLIP_VISION_FILE="$CLIP_VISION_DIR/clip-vit-large-patch14-336.safetensors"
UPSCALE_DIR="/workspace/comfyui/ComfyUI/models/upscale_models"
ULTRASHARP_FILE="$UPSCALE_DIR/4x-UltraSharp.pth"
REALESRGAN_FILE="$UPSCALE_DIR/RealESRGAN_x4plus.pth"

mkdir -p "$CLIP_VISION_DIR"
mkdir -p "$UPSCALE_DIR"

# Chemins possibles des composants depuis OwnCloud (uploadés avec le modèle)
OWNCLOUD_CLIP="$MODEL_DIR/clip_vision/clip-vit-large-patch14-336.safetensors"
OWNCLOUD_ULTRASHARP="$MODEL_DIR/upscale_models/4x-UltraSharp.pth"
OWNCLOUD_REALESRGAN="$MODEL_DIR/upscale_models/RealESRGAN_x4plus.pth"

# CLIP Vision
if [ -f "$OWNCLOUD_CLIP" ]; then
    echo "  ✅ CLIP Vision trouvé dans OwnCloud, copie..."
    cp "$OWNCLOUD_CLIP" "$CLIP_VISION_FILE"
    echo "  ✅ CLIP Vision copié depuis OwnCloud ($(du -h $CLIP_VISION_FILE | cut -f1))"
elif [ ! -f "$CLIP_VISION_FILE" ] || [ ! -s "$CLIP_VISION_FILE" ]; then
    echo "  📥 CLIP Vision absent, téléchargement upstream (~2.4GB)..."
    wget --progress=bar:force \
        "https://huggingface.co/h94/IP-Adapter/resolve/main/models/image_encoder/model.safetensors" \
        -O "$CLIP_VISION_FILE"

    if [ $? -eq 0 ] && [ -s "$CLIP_VISION_FILE" ]; then
        echo "  ✅ CLIP Vision téléchargé upstream ($(du -h $CLIP_VISION_FILE | cut -f1))"
    else
        echo "  ❌ Échec téléchargement CLIP Vision"
        rm -f "$CLIP_VISION_FILE"
        exit 1
    fi
else
    echo "  ✅ CLIP Vision déjà présent: $(du -h $CLIP_VISION_FILE | cut -f1)"
fi

# 4x-UltraSharp
if [ -f "$OWNCLOUD_ULTRASHARP" ]; then
    echo "  ✅ 4x-UltraSharp trouvé dans OwnCloud, copie..."
    cp "$OWNCLOUD_ULTRASHARP" "$ULTRASHARP_FILE"
    echo "  ✅ 4x-UltraSharp copié depuis OwnCloud ($(du -h $ULTRASHARP_FILE | cut -f1))"
elif [ ! -f "$ULTRASHARP_FILE" ]; then
    echo "  📥 4x-UltraSharp absent, téléchargement upstream (~67MB)..."
    wget -q --show-progress \
        "https://huggingface.co/lokCX/4x-Ultrasharp/resolve/main/4x-UltraSharp.pth" \
        -O "$ULTRASHARP_FILE"

    if [ $? -eq 0 ]; then
        echo "  ✅ 4x-UltraSharp téléchargé upstream ($(du -h $ULTRASHARP_FILE | cut -f1))"
    else
        echo "  ⚠️ Échec téléchargement 4x-UltraSharp (non bloquant)"
    fi
else
    echo "  ✅ 4x-UltraSharp déjà présent: $(du -h $ULTRASHARP_FILE | cut -f1)"
fi

# RealESRGAN
if [ -f "$OWNCLOUD_REALESRGAN" ]; then
    echo "  ✅ RealESRGAN trouvé dans OwnCloud, copie..."
    cp "$OWNCLOUD_REALESRGAN" "$REALESRGAN_FILE"
    echo "  ✅ RealESRGAN copié depuis OwnCloud ($(du -h $REALESRGAN_FILE | cut -f1))"
elif [ ! -f "$REALESRGAN_FILE" ]; then
    echo "  📥 RealESRGAN absent, téléchargement upstream (~64MB)..."
    wget -q --show-progress \
        "https://github.com/xinntao/Real-ESRGAN/releases/download/v0.1.0/RealESRGAN_x4plus.pth" \
        -O "$REALESRGAN_FILE"

    if [ $? -eq 0 ]; then
        echo "  ✅ RealESRGAN téléchargé upstream ($(du -h $REALESRGAN_FILE | cut -f1))"
    else
        echo "  ⚠️ Échec téléchargement RealESRGAN (non bloquant)"
    fi
else
    echo "  ✅ RealESRGAN déjà présent: $(du -h $REALESRGAN_FILE | cut -f1)"
fi

echo "✅ Configuration CLIP Vision + Upscalers terminée"

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
