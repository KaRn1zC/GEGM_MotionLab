#!/bin/bash
set -e

# Détection du répertoire du script (pour chemins absolus)
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

# Argument: nom du modèle spécifique ou "all" (défaut)
MODEL="${1:-all}"

echo "🎬 Setup WAN 2.2 - Version ComfyUI Native (Comfy-Org)"
echo "====================================================="

# Vérifier l'environnement virtuel (sauf sur Docker/RunPod)
# Docker/RunPod : Python installé globalement, pas de venv nécessaire
if [[ ! -f "/.dockerenv" ]] && [[ -z "$RUNPOD_POD_ID" ]] && [[ "$PWD" != "/workspace"* ]]; then
    # Environnement local : vérifier venv requis
    if [[ "$VIRTUAL_ENV" != *".venv"* ]]; then
        echo "❌ Environnement .venv non activé (requis en local)"
        echo "   Activez-le avec: source .venv/bin/activate"
        exit 1
    fi
    echo "✅ Environnement virtuel: $VIRTUAL_ENV"
else
    # Docker/RunPod : skip vérification venv
    echo "✅ Environnement Docker/RunPod détecté (Python global)"
fi

# Étape 1: Installer huggingface-cli
echo "📦 Installation huggingface-cli..."
pip install -q "huggingface_hub"

# Étape 2: Créer les dossiers modèles (structure ComfyUI native)
echo "📁 Création des dossiers de modèles (structure ComfyUI)..."
mkdir -p models/{diffusion_models,text_encoders,vae}
mkdir -p models/wan2.2-ti2v-5b  # Pour compatibilité avec upload/download existant
mkdir -p models/wan2.2-i2v-a14b

# Étape 3: Test de connexion Hugging Face
echo "🔗 Test de connexion Hugging Face..."
if hf auth whoami 2>/dev/null; then
    echo "✅ Connecté à Hugging Face"
else
    echo "ℹ️  Pas connecté à HF (modèles publics OK)"
fi

# Repository Comfy-Org (version repackagée pour ComfyUI)
REPO="Comfy-Org/Wan_2.2_ComfyUI_Repackaged"

# Étape 4: Téléchargement selon le modèle demandé
if [ "$MODEL" = "all" ]; then
    echo ""
    echo "📥 Téléchargement des deux modèles depuis $REPO..."
    echo ""

    # === MODÈLE 5B ===
    echo "📦 Modèle 1/2: WAN 2.2 TI2V 5B (ComfyUI Native)..."
    echo ""

    # Dossier temporaire pour téléchargement
    TEMP_DL="./models/.temp_download"
    mkdir -p "$TEMP_DL"

    # 1. Diffusion model (~9.3 GB)
    echo "  1/3: Diffusion model (~9.3 GB)..."
    hf download "$REPO" \
        split_files/diffusion_models/wan2.2_ti2v_5B_fp16.safetensors \
        --local-dir "$TEMP_DL"
    mv "$TEMP_DL/split_files/diffusion_models/wan2.2_ti2v_5B_fp16.safetensors" ./models/diffusion_models/

    # 2. Text encoder (~11.4 GB) - partagé entre 5B et 14B
    echo "  2/3: Text encoder FP16 (~11.4 GB)..."
    hf download "$REPO" \
        split_files/text_encoders/umt5_xxl_fp16.safetensors \
        --local-dir "$TEMP_DL"
    mv "$TEMP_DL/split_files/text_encoders/umt5_xxl_fp16.safetensors" ./models/text_encoders/

    # 3. VAE 5B (~600 MB)
    echo "  3/3: VAE 5B (~600 MB)..."
    hf download "$REPO" \
        split_files/vae/wan2.2_vae.safetensors \
        --local-dir "$TEMP_DL"
    mv "$TEMP_DL/split_files/vae/wan2.2_vae.safetensors" ./models/vae/

    # Nettoyer le dossier temporaire
    rm -rf "$TEMP_DL"

    echo "✅ WAN 2.2 5B téléchargé"

    # Créer dossier wan2.2-ti2v-5b avec symlinks pour compatibilité
    echo ""
    echo "🔗 Création de symlinks pour compatibilité upload/download..."
    mkdir -p models/wan2.2-ti2v-5b
    ln -sf ../diffusion_models/wan2.2_ti2v_5B_fp16.safetensors models/wan2.2-ti2v-5b/
    ln -sf ../text_encoders/umt5_xxl_fp16.safetensors models/wan2.2-ti2v-5b/
    ln -sf ../vae/wan2.2_vae.safetensors models/wan2.2-ti2v-5b/
    echo "✅ Symlinks créés"

    # Vérification intégrité 5B
    echo ""
    echo "🔍 Vérification intégrité modèle de diffusion (5B)..."
    python "$SCRIPT_DIR/verify_diffusion_model.py" wan2.2-ti2v-5b
    if [ $? -ne 0 ]; then
        echo "❌ ÉCHEC: Modèle de diffusion 5B corrompu ou incomplet"
        exit 1
    fi

    echo ""
    echo "🔍 Vérification intégrité Text Encoder (5B)..."
    python "$SCRIPT_DIR/verify_t5_integrity.py" wan2.2-ti2v-5b
    if [ $? -ne 0 ]; then
        echo "❌ ÉCHEC: Text Encoder 5B corrompu ou incomplet"
        exit 1
    fi

    echo ""
    echo "🔍 Vérification intégrité VAE (5B)..."
    python "$SCRIPT_DIR/verify_vae.py" wan2.2-ti2v-5b
    if [ $? -ne 0 ]; then
        echo "❌ ÉCHEC: VAE 5B corrompu ou incomplet"
        exit 1
    fi

    # === MODÈLE 14B ===
    echo ""
    echo "📦 Modèle 2/2: WAN 2.2 I2V 14B (ComfyUI Native)..."
    echo ""

    # 1. Diffusion high noise
    echo "  1/4: Diffusion high noise FP16..."
    hf download "$REPO" \
        split_files/diffusion_models/wan2.2_i2v_high_noise_14B_fp16.safetensors \
        --local-dir "$TEMP_DL"
    mv "$TEMP_DL/split_files/diffusion_models/wan2.2_i2v_high_noise_14B_fp16.safetensors" ./models/diffusion_models/

    # 2. Diffusion low noise
    echo "  2/4: Diffusion low noise FP16..."
    hf download "$REPO" \
        split_files/diffusion_models/wan2.2_i2v_low_noise_14B_fp16.safetensors \
        --local-dir "$TEMP_DL"
    mv "$TEMP_DL/split_files/diffusion_models/wan2.2_i2v_low_noise_14B_fp16.safetensors" ./models/diffusion_models/

    # 3. Text encoder FP16 (déjà téléchargé pour 5B)
    echo "  3/4: Text encoder FP16 (déjà téléchargé)"

    # 4. VAE 14B (wan_2.1_vae.safetensors - 254 MB - spécifique au 14B)
    echo "  4/4: VAE 14B (wan_2.1_vae.safetensors - 254 MB)..."
    hf download "$REPO" \
        split_files/vae/wan_2.1_vae.safetensors \
        --local-dir "$TEMP_DL"
    mv "$TEMP_DL/split_files/vae/wan_2.1_vae.safetensors" ./models/vae/

    # Nettoyer le dossier temporaire
    rm -rf "$TEMP_DL"

    echo "✅ WAN 2.2 14B téléchargé"

    # Créer dossier wan2.2-i2v-a14b avec symlinks
    echo ""
    echo "🔗 Création de symlinks pour compatibilité 14B..."
    mkdir -p models/wan2.2-i2v-a14b
    ln -sf ../diffusion_models/wan2.2_i2v_high_noise_14B_fp16.safetensors models/wan2.2-i2v-a14b/
    ln -sf ../diffusion_models/wan2.2_i2v_low_noise_14B_fp16.safetensors models/wan2.2-i2v-a14b/
    ln -sf ../text_encoders/umt5_xxl_fp16.safetensors models/wan2.2-i2v-a14b/
    ln -sf ../vae/wan_2.1_vae.safetensors models/wan2.2-i2v-a14b/
    echo "✅ Symlinks créés"

    # Vérification intégrité 14B
    echo ""
    echo "🔍 Vérification intégrité modèle de diffusion (14B)..."
    python "$SCRIPT_DIR/verify_diffusion_model.py" wan2.2-i2v-a14b
    if [ $? -ne 0 ]; then
        echo "❌ ÉCHEC: Modèle de diffusion 14B corrompu ou incomplet"
        exit 1
    fi

    echo ""
    echo "🔍 Vérification intégrité Text Encoder (14B)..."
    python "$SCRIPT_DIR/verify_t5_integrity.py" wan2.2-i2v-a14b
    if [ $? -ne 0 ]; then
        echo "❌ ÉCHEC: Text Encoder 14B corrompu ou incomplet"
        exit 1
    fi

    echo ""
    echo "🔍 Vérification intégrité VAE (14B)..."
    python "$SCRIPT_DIR/verify_vae.py" wan2.2-i2v-a14b
    if [ $? -ne 0 ]; then
        echo "❌ ÉCHEC: VAE 14B corrompu ou incomplet"
        exit 1
    fi

elif [ "$MODEL" = "wan2.2-ti2v-5b" ]; then
    echo ""
    echo "📥 Téléchargement WAN 2.2 TI2V 5B depuis $REPO..."
    echo ""

    # Dossier temporaire pour téléchargement
    TEMP_DL="./models/.temp_download"
    mkdir -p "$TEMP_DL"

    # 1. Diffusion model (~9.3 GB)
    echo "  1/3: Diffusion model (~9.3 GB)..."
    hf download "$REPO" \
        split_files/diffusion_models/wan2.2_ti2v_5B_fp16.safetensors \
        --local-dir "$TEMP_DL"
    mv "$TEMP_DL/split_files/diffusion_models/wan2.2_ti2v_5B_fp16.safetensors" ./models/diffusion_models/

    # 2. Text encoder FP16 (~11.4 GB)
    echo "  2/3: Text encoder FP16 (~11.4 GB)..."
    hf download "$REPO" \
        split_files/text_encoders/umt5_xxl_fp16.safetensors \
        --local-dir "$TEMP_DL"
    mv "$TEMP_DL/split_files/text_encoders/umt5_xxl_fp16.safetensors" ./models/text_encoders/

    # 3. VAE (~600 MB)
    echo "  3/3: VAE 5B (~600 MB)..."
    hf download "$REPO" \
        split_files/vae/wan2.2_vae.safetensors \
        --local-dir "$TEMP_DL"
    mv "$TEMP_DL/split_files/vae/wan2.2_vae.safetensors" ./models/vae/

    # Nettoyer le dossier temporaire
    rm -rf "$TEMP_DL"

    echo "✅ WAN 2.2 5B téléchargé"

    # Créer dossier wan2.2-ti2v-5b avec symlinks
    echo ""
    echo "🔗 Création de symlinks pour compatibilité..."
    mkdir -p models/wan2.2-ti2v-5b
    ln -sf ../diffusion_models/wan2.2_ti2v_5B_fp16.safetensors models/wan2.2-ti2v-5b/
    ln -sf ../text_encoders/umt5_xxl_fp16.safetensors models/wan2.2-ti2v-5b/
    ln -sf ../vae/wan2.2_vae.safetensors models/wan2.2-ti2v-5b/
    echo "✅ Symlinks créés"

    # Vérifications
    echo ""
    echo "🔍 Vérification intégrité modèle de diffusion..."
    python "$SCRIPT_DIR/verify_diffusion_model.py" wan2.2-ti2v-5b
    if [ $? -ne 0 ]; then
        echo "❌ ÉCHEC: Modèle de diffusion corrompu ou incomplet"
        exit 1
    fi

    echo ""
    echo "🔍 Vérification intégrité Text Encoder..."
    python "$SCRIPT_DIR/verify_t5_integrity.py" wan2.2-ti2v-5b
    if [ $? -ne 0 ]; then
        echo "❌ ÉCHEC: Text Encoder corrompu ou incomplet"
        exit 1
    fi

    echo ""
    echo "🔍 Vérification intégrité VAE..."
    python "$SCRIPT_DIR/verify_vae.py" wan2.2-ti2v-5b
    if [ $? -ne 0 ]; then
        echo "❌ ÉCHEC: VAE corrompu ou incomplet"
        exit 1
    fi

elif [ "$MODEL" = "wan2.2-ti2v-5b" ]; then
    echo ""
    echo "📥 Téléchargement WAN 2.2 TI2V 5B depuis $REPO..."
    echo ""

    # Dossier temporaire pour téléchargement
    TEMP_DL="./models/.temp_download"
    mkdir -p "$TEMP_DL"

    # 1. Diffusion model (~9.3 GB)
    echo "  1/3: Diffusion model (~9.3 GB)..."
    hf download "$REPO" \
        split_files/diffusion_models/wan2.2_ti2v_5B_fp16.safetensors \
        --local-dir "$TEMP_DL"
    mv "$TEMP_DL/split_files/diffusion_models/wan2.2_ti2v_5B_fp16.safetensors" ./models/diffusion_models/

    # 2. Text encoder FP16 (~11.4 GB)
    echo "  2/3: Text encoder FP16 (~11.4 GB)..."
    hf download "$REPO" \
        split_files/text_encoders/umt5_xxl_fp16.safetensors \
        --local-dir "$TEMP_DL"
    mv "$TEMP_DL/split_files/text_encoders/umt5_xxl_fp16.safetensors" ./models/text_encoders/

    # 3. VAE 5B (~600 MB)
    echo "  3/3: VAE 5B (~600 MB)..."
    hf download "$REPO" \
        split_files/vae/wan2.2_vae.safetensors \
        --local-dir "$TEMP_DL"
    mv "$TEMP_DL/split_files/vae/wan2.2_vae.safetensors" ./models/vae/

    # Nettoyer le dossier temporaire
    rm -rf "$TEMP_DL"

    echo "✅ WAN 2.2 5B téléchargé"

    # Créer dossier wan2.2-ti2v-5b avec symlinks
    echo ""
    echo "🔗 Création de symlinks pour compatibilité..."
    mkdir -p models/wan2.2-ti2v-5b
    ln -sf ../diffusion_models/wan2.2_ti2v_5B_fp16.safetensors models/wan2.2-ti2v-5b/
    ln -sf ../text_encoders/umt5_xxl_fp16.safetensors models/wan2.2-ti2v-5b/
    ln -sf ../vae/wan2.2_vae.safetensors models/wan2.2-ti2v-5b/
    echo "✅ Symlinks créés"

    # Vérifications
    echo ""
    echo "🔍 Vérification intégrité modèle de diffusion..."
    python "$SCRIPT_DIR/verify_diffusion_model.py" wan2.2-ti2v-5b
    if [ $? -ne 0 ]; then
        echo "❌ ÉCHEC: Modèle de diffusion corrompu ou incomplet"
        exit 1
    fi

    echo ""
    echo "🔍 Vérification intégrité Text Encoder..."
    python "$SCRIPT_DIR/verify_t5_integrity.py" wan2.2-ti2v-5b
    if [ $? -ne 0 ]; then
        echo "❌ ÉCHEC: Text Encoder corrompu ou incomplet"
        exit 1
    fi

    echo ""
    echo "🔍 Vérification intégrité VAE..."
    python "$SCRIPT_DIR/verify_vae.py" wan2.2-ti2v-5b
    if [ $? -ne 0 ]; then
        echo "❌ ÉCHEC: VAE corrompu ou incomplet"
        exit 1
    fi

elif [ "$MODEL" = "wan2.2-i2v-a14b" ]; then
    echo ""
    echo "📥 Téléchargement WAN 2.2 I2V 14B depuis $REPO..."
    echo ""

    # Dossier temporaire pour téléchargement
    TEMP_DL="./models/.temp_download"
    mkdir -p "$TEMP_DL"

    # 1. Diffusion high noise
    echo "  1/4: Diffusion high noise FP16..."
    hf download "$REPO" \
        split_files/diffusion_models/wan2.2_i2v_high_noise_14B_fp16.safetensors \
        --local-dir "$TEMP_DL"
    mv "$TEMP_DL/split_files/diffusion_models/wan2.2_i2v_high_noise_14B_fp16.safetensors" ./models/diffusion_models/

    # 2. Diffusion low noise
    echo "  2/4: Diffusion low noise FP16..."
    hf download "$REPO" \
        split_files/diffusion_models/wan2.2_i2v_low_noise_14B_fp16.safetensors \
        --local-dir "$TEMP_DL"
    mv "$TEMP_DL/split_files/diffusion_models/wan2.2_i2v_low_noise_14B_fp16.safetensors" ./models/diffusion_models/

    # 3. Text encoder FP16
    echo "  3/4: Text encoder FP16 (~11.4 GB)..."
    hf download "$REPO" \
        split_files/text_encoders/umt5_xxl_fp16.safetensors \
        --local-dir "$TEMP_DL"
    mv "$TEMP_DL/split_files/text_encoders/umt5_xxl_fp16.safetensors" ./models/text_encoders/

    # 4. VAE 14B (wan_2.1_vae.safetensors - 254 MB - spécifique au 14B)
    echo "  4/4: VAE 14B (wan_2.1_vae.safetensors - 254 MB)..."
    hf download "$REPO" \
        split_files/vae/wan_2.1_vae.safetensors \
        --local-dir "$TEMP_DL"
    mv "$TEMP_DL/split_files/vae/wan_2.1_vae.safetensors" ./models/vae/

    # Nettoyer le dossier temporaire
    rm -rf "$TEMP_DL"

    echo "✅ WAN 2.2 14B téléchargé"

    # Créer dossier wan2.2-i2v-a14b avec symlinks
    echo ""
    echo "🔗 Création de symlinks pour compatibilité..."
    mkdir -p models/wan2.2-i2v-a14b
    ln -sf ../diffusion_models/wan2.2_i2v_high_noise_14B_fp16.safetensors models/wan2.2-i2v-a14b/
    ln -sf ../diffusion_models/wan2.2_i2v_low_noise_14B_fp16.safetensors models/wan2.2-i2v-a14b/
    ln -sf ../text_encoders/umt5_xxl_fp16.safetensors models/wan2.2-i2v-a14b/
    ln -sf ../vae/wan_2.1_vae.safetensors models/wan2.2-i2v-a14b/
    echo "✅ Symlinks créés"

    # Vérifications
    echo ""
    echo "🔍 Vérification intégrité modèle de diffusion..."
    python "$SCRIPT_DIR/verify_diffusion_model.py" wan2.2-i2v-a14b
    if [ $? -ne 0 ]; then
        echo "❌ ÉCHEC: Modèle de diffusion corrompu ou incomplet"
        exit 1
    fi

    echo ""
    echo "🔍 Vérification intégrité Text Encoder..."
    python "$SCRIPT_DIR/verify_t5_integrity.py" wan2.2-i2v-a14b
    if [ $? -ne 0 ]; then
        echo "❌ ÉCHEC: Text Encoder corrompu ou incomplet"
        exit 1
    fi

    echo ""
    echo "🔍 Vérification intégrité VAE..."
    python "$SCRIPT_DIR/verify_vae.py" wan2.2-i2v-a14b
    if [ $? -ne 0 ]; then
        echo "❌ ÉCHEC: VAE corrompu ou incomplet"
        exit 1
    fi

else
    echo "❌ Modèle invalide: $MODEL"
    echo "Usage: $0 [all|wan2.2-i2v-a14b|wan2.2-ti2v-5b]"
    exit 1
fi

# === COMPOSANTS PARTAGÉS (CLIP + UPSCALERS) ===
echo ""
echo "📦 Téléchargement des composants partagés..."
echo ""

# Créer dossiers pour composants partagés
mkdir -p models/clip_vision
mkdir -p models/upscale_models

# CLIP Vision (~2.4 GB) - Requis pour tous les modèles
CLIP_FILE="models/clip_vision/clip-vit-large-patch14-336.safetensors"
if [ ! -f "$CLIP_FILE" ] || [ ! -s "$CLIP_FILE" ]; then
    echo "  1/3: CLIP Vision (~2.4 GB)..."
    curl -L --progress-bar \
        "https://huggingface.co/h94/IP-Adapter/resolve/main/models/image_encoder/model.safetensors" \
        -o "$CLIP_FILE"

    if [ $? -eq 0 ] && [ -s "$CLIP_FILE" ]; then
        FILE_SIZE=$(du -h "$CLIP_FILE" | cut -f1)
        echo "  ✅ CLIP Vision téléchargé ($FILE_SIZE)"
    else
        echo "  ❌ Échec téléchargement CLIP Vision"
        rm -f "$CLIP_FILE"
        exit 1
    fi
else
    echo "  ✅ CLIP Vision déjà présent: $(du -h $CLIP_FILE | cut -f1)"
fi

# 4x-UltraSharp (~67 MB) - Upscaler haute qualité
ULTRASHARP_FILE="models/upscale_models/4x-UltraSharp.pth"
if [ ! -f "$ULTRASHARP_FILE" ]; then
    echo "  2/3: 4x-UltraSharp (~67 MB)..."
    curl -L -# \
        "https://huggingface.co/lokCX/4x-Ultrasharp/resolve/main/4x-UltraSharp.pth" \
        -o "$ULTRASHARP_FILE"

    if [ $? -eq 0 ]; then
        echo "  ✅ 4x-UltraSharp téléchargé ($(du -h $ULTRASHARP_FILE | cut -f1))"
    else
        echo "  ⚠️ Échec téléchargement 4x-UltraSharp (non bloquant)"
    fi
else
    echo "  ✅ 4x-UltraSharp déjà présent: $(du -h $ULTRASHARP_FILE | cut -f1)"
fi

# RealESRGAN (~64 MB) - Upscaler backup (optionnel)
REALESRGAN_FILE="models/upscale_models/RealESRGAN_x4plus.pth"
if [ ! -f "$REALESRGAN_FILE" ]; then
    echo "  3/3: RealESRGAN (~64 MB, optionnel)..."

    # Retry jusqu'à 3 fois avec délai croissant (GitHub peut être temporairement indisponible)
    RETRY_COUNT=0
    MAX_RETRIES=3
    SUCCESS=false

    while [ $RETRY_COUNT -lt $MAX_RETRIES ] && [ "$SUCCESS" = false ]; do
        if [ $RETRY_COUNT -gt 0 ]; then
            WAIT_TIME=$((RETRY_COUNT * 2))
            echo "  ⏳ Retry $RETRY_COUNT/$MAX_RETRIES après ${WAIT_TIME}s..."
            sleep $WAIT_TIME
        fi

        curl -L -# --connect-timeout 10 --max-time 60 \
            "https://github.com/xinntao/Real-ESRGAN/releases/download/v0.1.0/RealESRGAN_x4plus.pth" \
            -o "$REALESRGAN_FILE" 2>/dev/null

        if [ $? -eq 0 ] && [ -f "$REALESRGAN_FILE" ] && [ -s "$REALESRGAN_FILE" ]; then
            echo "  ✅ RealESRGAN téléchargé ($(du -h $REALESRGAN_FILE | cut -f1))"
            SUCCESS=true
        else
            rm -f "$REALESRGAN_FILE"  # Nettoyer fichier partiel
            RETRY_COUNT=$((RETRY_COUNT + 1))
        fi
    done

    if [ "$SUCCESS" = false ]; then
        echo "  ⚠️ RealESRGAN indisponible après $MAX_RETRIES tentatives (non bloquant)"
        echo "     GitHub Releases peut être temporairement inaccessible"
        echo "     Le système fonctionnera avec 4x-UltraSharp uniquement"
    fi
else
    echo "  ✅ RealESRGAN déjà présent: $(du -h $REALESRGAN_FILE | cut -f1)"
fi

echo "✅ Composants partagés téléchargés"

# === CRÉATION SYMLINKS COMPOSANTS PARTAGÉS DANS DOSSIERS MODÈLES ===
echo ""
echo "🔗 Création de symlinks vers composants partagés dans dossiers modèles..."

# Pour upload sur OwnCloud : créer symlinks dans models/{model_name}/
# split_and_upload.py utilise --copy-links donc uploadera le contenu réel

if [ "$MODEL" = "all" ] || [ "$MODEL" = "wan2.2-ti2v-5b" ]; then
    echo "  Modèle 5B: Ajout symlinks CLIP + Upscalers..."
    mkdir -p models/wan2.2-ti2v-5b/clip_vision
    mkdir -p models/wan2.2-ti2v-5b/upscale_models

    # Symlinks relatifs (plus robustes)
    if [ -f "$CLIP_FILE" ]; then
        ln -sf ../../clip_vision/clip-vit-large-patch14-336.safetensors models/wan2.2-ti2v-5b/clip_vision/
    fi
    if [ -f "$ULTRASHARP_FILE" ]; then
        ln -sf ../../upscale_models/4x-UltraSharp.pth models/wan2.2-ti2v-5b/upscale_models/
    fi
    if [ -f "$REALESRGAN_FILE" ]; then
        ln -sf ../../upscale_models/RealESRGAN_x4plus.pth models/wan2.2-ti2v-5b/upscale_models/
    fi
    echo "  ✅ Symlinks 5B créés"
fi

if [ "$MODEL" = "all" ] || [ "$MODEL" = "wan2.2-i2v-a14b" ]; then
    echo "  Modèle 14B: Ajout symlinks CLIP + Upscalers..."
    mkdir -p models/wan2.2-i2v-a14b/clip_vision
    mkdir -p models/wan2.2-i2v-a14b/upscale_models

    # Symlinks relatifs (plus robustes)
    if [ -f "$CLIP_FILE" ]; then
        ln -sf ../../clip_vision/clip-vit-large-patch14-336.safetensors models/wan2.2-i2v-a14b/clip_vision/
    fi
    if [ -f "$ULTRASHARP_FILE" ]; then
        ln -sf ../../upscale_models/4x-UltraSharp.pth models/wan2.2-i2v-a14b/upscale_models/
    fi
    if [ -f "$REALESRGAN_FILE" ]; then
        ln -sf ../../upscale_models/RealESRGAN_x4plus.pth models/wan2.2-i2v-a14b/upscale_models/
    fi
    echo "  ✅ Symlinks 14B créés"
fi

echo "✅ Symlinks composants partagés créés (seront uploadés avec les modèles)"

# Étape 5: Vérification des téléchargements
echo ""
echo "🔍 Vérification des modèles téléchargés..."
if [ "$MODEL" = "all" ] || [ "$MODEL" = "wan2.2-i2v-a14b" ]; then
    if [ -d "models/wan2.2-i2v-a14b" ]; then
        size=$(du -sh models/wan2.2-i2v-a14b | cut -f1)
        echo "✅ wan2.2-i2v-a14b ($size - symlinks)"
    fi
fi

if [ "$MODEL" = "all" ] || [ "$MODEL" = "wan2.2-ti2v-5b" ]; then
    if [ -d "models/wan2.2-ti2v-5b" ]; then
        size=$(du -sh models/wan2.2-ti2v-5b | cut -f1)
        echo "✅ wan2.2-ti2v-5b ($size - symlinks)"
    fi
fi

echo ""
echo "📂 Structure des fichiers (ComfyUI native):"
echo "   models/diffusion_models/ - Modèles de diffusion"
echo "   models/text_encoders/ - Text encoders"
echo "   models/vae/ - VAE"
echo ""
echo "✅ Setup WAN 2.2 terminé (Version ComfyUI Native) !"
echo "ℹ️  Repository: $REPO"
