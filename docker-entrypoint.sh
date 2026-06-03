#!/bin/bash
set -e

echo "🚀 Starting GEGM MotionLab on RunPod..."
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

# ============================================
# VÉRIFICATION CUDA (obligatoire avant tout téléchargement)
# ============================================
# Tentatives avec délai — sur RunPod le GPU peut mettre quelques secondes
# à devenir disponible après le démarrage du container
CUDA_OK=false
MAX_CUDA_RETRIES=5
for attempt in $(seq 1 $MAX_CUDA_RETRIES); do
    if python -c 'import torch; exit(0 if torch.cuda.is_available() else 1)' 2>/dev/null; then
        CUDA_OK=true
        break
    fi
    if [ $attempt -lt $MAX_CUDA_RETRIES ]; then
        echo "   ⏳ CUDA non disponible (tentative $attempt/$MAX_CUDA_RETRIES), retry dans 5s..."
        sleep 5
    fi
done

if [ "$CUDA_OK" = true ]; then
    echo "   CUDA Available: Yes"
    echo "   CUDA Version: $(python -c 'import torch; print(torch.version.cuda)')"
    echo "   GPU Count: $(python -c 'import torch; print(torch.cuda.device_count())')"
    echo "   GPU Name: $(python -c 'import torch; print(torch.cuda.get_device_name(0))')"
    echo "   GPU Memory: $(python -c 'import torch; print(f"{torch.cuda.get_device_properties(0).total_memory / 1024**3:.1f} GB")')"
else
    echo ""
    echo "❌ ERREUR FATALE: PyTorch ne peut pas initialiser CUDA"
    echo "======================================================="
    echo "   nvidia-smi détecte le GPU, mais torch.cuda.is_available() = False"
    echo ""
    echo "   📋 Diagnostic:"
    echo "   PyTorch: $(python -c 'import torch; print(torch.__version__)' 2>/dev/null)"
    echo "   CUDA compilé: $(python -c 'import torch; print(torch.version.cuda)' 2>/dev/null)"
    echo "   Driver GPU: $(nvidia-smi --query-gpu=driver_version --format=csv,noheader 2>/dev/null)"
    echo "   GPU: $(nvidia-smi --query-gpu=name --format=csv,noheader 2>/dev/null)"
    echo ""
    # Capturer l'erreur exacte de PyTorch
    echo "   🔍 Erreur PyTorch:"
    python -c "
import torch
try:
    torch.cuda.init()
except Exception as e:
    print(f'      {type(e).__name__}: {e}')
" 2>&1 | head -5
    echo ""
    echo "   💡 Causes probables:"
    echo "      - PyTorch nightly (--pre) incompatible avec ce GPU/driver"
    echo "      - Reconstruire l'image avec un PyTorch stable ou un nightly testé"
    echo "      - Vérifier la compatibilité driver $(nvidia-smi --query-gpu=driver_version --format=csv,noheader 2>/dev/null) + CUDA $(python -c 'import torch; print(torch.version.cuda)' 2>/dev/null)"
    echo "======================================================="
    # Attente longue pour éviter la boucle de restart RunPod
    echo ""
    echo "⏸️  Pause 5 minutes avant exit (évite la boucle de restart)..."
    echo "   Consultez ces logs, puis arrêtez le pod manuellement."
    sleep 300
    exit 1
fi

# ============================================
# TÉLÉCHARGEMENT DES MODÈLES (UPSTREAM + FALLBACK OWNCLOUD)
# ============================================

# Modèle à charger (obligatoire)
MODEL_NAME="${OWNCLOUD_MODEL_NAME:-}"
if [ -z "$MODEL_NAME" ]; then
    echo "❌ OWNCLOUD_MODEL_NAME non défini"
    echo "   Modèles disponibles:"
    python -m src.model_registry list-models 2>/dev/null || echo "   (registre indisponible)"
    exit 1
fi
MODEL_DIR="/workspace/comfyui/ComfyUI/models/checkpoints/${MODEL_NAME}"

echo ""
echo "📦 Modèle configuré: $MODEL_NAME"

# Bootstrap: propriétés du modèle depuis le registre (un seul appel Python)
set +e
BOOTSTRAP_OUTPUT=$(python3 -c "
import sys
sys.path.insert(0, '/workspace')
from src.model_registry import get_registry
registry = get_registry()
m = registry.get_model('$MODEL_NAME')
if not m:
    sys.exit(1)
shared = registry.get_shared_components()
vae_int = 'true' if m.vae.filename == 'integrated' else 'false'
vae_fn = '' if m.vae.filename == 'integrated' else m.vae.filename
has_te = 'true' if m.text_encoder else 'false'
te_fn = m.text_encoder.filename if m.text_encoder else ''
has_sym = 'true' if m.symlinks else 'false'
print(f'MODEL_ARCH={m.architecture}')
print(f'DISPLAY_NAME=\"{m.display_name}\"')
print(f'VAE_INTEGRATED={vae_int}')
print(f'VAE_FILENAME={vae_fn}')
print(f'HAS_MODEL_TE={has_te}')
print(f'MODEL_TE_FILENAME={te_fn}')
print(f'HAS_SYMLINKS={has_sym}')
print(f'SHARED_TE_FILENAME={shared.text_encoder.filename}')
" 2>/dev/null)
BOOTSTRAP_EXIT=$?
set -e

if [ $BOOTSTRAP_EXIT -ne 0 ]; then
    echo "❌ Modèle '$MODEL_NAME' inconnu du registre"
    echo "   Modèles disponibles:"
    python -m src.model_registry list-models 2>/dev/null || echo "   (registre indisponible)"
    exit 1
fi
eval "$BOOTSTRAP_OUTPUT"

echo "   Modèle: $DISPLAY_NAME (arch=$MODEL_ARCH)"

# ========================================
# NETTOYAGE: Supprimer d'éventuels anciens modèles T2V ou formats obsolètes
# ========================================
echo ""
echo "🧹 Nettoyage des anciens modèles (si présents)..."

CHECKPOINTS_DIR="/workspace/comfyui/ComfyUI/models/checkpoints"

# Lister tous les dossiers dans checkpoints pour debugging
if [ -d "$CHECKPOINTS_DIR" ]; then
    echo "📂 Dossiers présents dans checkpoints/:"
    ls -la "$CHECKPOINTS_DIR" | grep "^d" || echo "   (aucun dossier)"
fi

# Supprimer les anciens formats connus du 14B (T2V, Diffusers, formats obsolètes)
OBSOLETE_PATTERNS=(
    "Wan2.1*"
    "*T2V*"
    "*t2v*"
    "*Diffusers*"
    "*diffusers*"
    "high_noise_model"
    "low_noise_model"
)

CLEANED=0
for pattern in "${OBSOLETE_PATTERNS[@]}"; do
    # Fichiers obsolètes
    FOUND=$(find "$CHECKPOINTS_DIR" -name "$pattern" -type f 2>/dev/null)
    if [ -n "$FOUND" ]; then
        find "$CHECKPOINTS_DIR" -name "$pattern" -type f -delete 2>/dev/null
        echo "   🗑️  Supprimé: $pattern"
        CLEANED=$((CLEANED + 1))
    fi
    # Dossiers obsolètes
    FOUND=$(find "$CHECKPOINTS_DIR" -name "$pattern" -type d 2>/dev/null)
    if [ -n "$FOUND" ]; then
        find "$CHECKPOINTS_DIR" -name "$pattern" -type d -exec rm -rf {} + 2>/dev/null
        echo "   🗑️  Dossier supprimé: $pattern"
        CLEANED=$((CLEANED + 1))
    fi
done

if [ $CLEANED -eq 0 ]; then
    echo "   ✅ Rien à nettoyer"
else
    echo "   ✅ $CLEANED élément(s) nettoyé(s)"
fi
echo ""

# Vérifier la présence des fichiers via registre
NEED_DOWNLOAD=false
EXPECTED_JSON=$(python -m src.model_registry get-expected-files "$MODEL_NAME" 2>/dev/null)
if [ $? -eq 0 ] && [ -n "$EXPECTED_JSON" ]; then
    NEED_DOWNLOAD=$(echo "$EXPECTED_JSON" | python3 -c "
import sys, json, os
files = json.load(sys.stdin)
for f in files:
    path = os.path.join('$MODEL_DIR', f['filename'])
    if not os.path.isfile(path):
        print('true')
        sys.exit(0)
print('false')
")
else
    echo "❌ Impossible de vérifier les fichiers (registre indisponible)"
    exit 1
fi

if [ "$NEED_DOWNLOAD" = "true" ]; then

    DOWNLOAD_SUCCESS=false
    USE_OWNCLOUD_FALLBACK=false

    # ========================================
    # ÉTAPE 1: HEALTHCHECK UPSTREAM (informatif)
    # ========================================
    echo ""
    echo "🔍 Vérification de la disponibilité des sources upstream..."
    echo "   (HuggingFace + GitHub)"

    set +e
    python /workspace/scripts/check_upstream_health.py "$MODEL_NAME"
    HEALTHCHECK_EXIT_CODE=$?
    set -e

    if [ $HEALTHCHECK_EXIT_CODE -eq 0 ]; then
        echo ""
        echo "✅ Sources upstream disponibles et versions correctes"
    else
        echo ""
        echo "⚠️  Healthcheck: versions différentes ou erreur réseau (informatif)"
        echo "   → Tentative de téléchargement upstream quand même..."
    fi

    # ========================================
    # ÉTAPE 2: TÉLÉCHARGEMENT UPSTREAM (toujours tenté)
    # ========================================
    echo ""
    echo "📥 Téléchargement depuis upstream (HuggingFace + GitHub)..."
    echo "   Ceci peut prendre 10-30 minutes selon la connexion..."

    if [ -f "/workspace/scripts/setup_wan22_native.sh" ]; then
        set +e
        bash /workspace/scripts/setup_wan22_native.sh "$MODEL_NAME"
        SETUP_EXIT_CODE=$?
        set -e

        if [ $SETUP_EXIT_CODE -eq 0 ]; then
            echo ""
            echo "✅ Téléchargement upstream réussi"

            # Déplacer les fichiers vers le répertoire ComfyUI
            echo "📦 Déplacement des fichiers vers ComfyUI..."
            COMFYUI_MODELS="/workspace/comfyui/ComfyUI/models"
            mkdir -p "$COMFYUI_MODELS/checkpoints"

            # Déplacer le dossier modèle si existant (WAN: contient les symlinks)
            if [ -d "/workspace/models/$MODEL_NAME" ]; then
                mv "/workspace/models/$MODEL_NAME" "$COMFYUI_MODELS/checkpoints/"
                echo "   ✅ Modèle déplacé: $MODEL_NAME"
            fi

            # Déplacer diffusion_models/ et vae/ dans checkpoints/ (WAN uniquement, n'existe pas pour LTX)
            for dir in diffusion_models vae; do
                if [ -d "/workspace/models/$dir" ]; then
                    mv "/workspace/models/$dir" "$COMFYUI_MODELS/checkpoints/"
                    echo "   ✅ Dossier déplacé: $dir"
                fi
            done

            # Text encoders — destination selon le type
            if [ -d "/workspace/models/text_encoders" ]; then
                if [ "$HAS_MODEL_TE" = "true" ]; then
                    # Text encoder propre au modèle (Gemma) → directement dans text_encoders/
                    mkdir -p "$COMFYUI_MODELS/text_encoders"
                    for f in /workspace/models/text_encoders/*.safetensors; do
                        [ -f "$f" ] && mv "$f" "$COMFYUI_MODELS/text_encoders/"
                    done
                    echo "   ✅ Text encoder déplacé dans text_encoders/"
                else
                    # T5 partagé → checkpoints/text_encoders/ (pour les symlinks WAN)
                    mv "/workspace/models/text_encoders" "$COMFYUI_MODELS/checkpoints/"
                    echo "   ✅ Dossier déplacé: text_encoders"
                fi
            fi

            # Déplacer les checkpoints loose dans le dossier modèle (LTX: fichiers dans models/checkpoints/)
            if [ -d "/workspace/models/checkpoints" ]; then
                mkdir -p "$COMFYUI_MODELS/checkpoints/$MODEL_NAME"
                for f in /workspace/models/checkpoints/*.safetensors; do
                    [ -f "$f" ] && mv "$f" "$COMFYUI_MODELS/checkpoints/$MODEL_NAME/"
                done
                echo "   ✅ Checkpoints déplacés dans $MODEL_NAME/"
            fi

            # Recréer les symlinks si nécessaire
            if [ "$HAS_SYMLINKS" = "true" ]; then
                echo "🔗 Recréation des symlinks dans $MODEL_NAME..."
                cd "$COMFYUI_MODELS/checkpoints"
                if [ -d "$MODEL_NAME" ]; then
                    cd "$MODEL_NAME"
                    find . -maxdepth 1 -type l -delete

                    SYMLINKS_JSON=$(python -m src.model_registry get-symlinks "$MODEL_NAME" 2>/dev/null)
                    if [ $? -eq 0 ] && [ -n "$SYMLINKS_JSON" ]; then
                        echo "$SYMLINKS_JSON" | python3 -c "
import sys, json, os
for s in json.load(sys.stdin):
    os.symlink(s['source'], s['target'])
"
                        echo "   ✅ Symlinks $MODEL_NAME recréés"
                    else
                        echo "   ⚠️ Impossible de recréer les symlinks (registre indisponible)"
                    fi
                    cd /workspace
                fi
            fi

            # Nettoyer le dossier models temporaire
            rm -rf /workspace/models

            DOWNLOAD_SUCCESS=true
        else
            echo ""
            echo "❌ Échec du téléchargement upstream"
            echo "🧹 Nettoyage des fichiers partiels..."
            python /workspace/scripts/cleanup_partial_downloads.py --model "$MODEL_NAME"
            echo "⚠️  Basculement vers OwnCloud (fallback)..."
            USE_OWNCLOUD_FALLBACK=true
        fi
    else
        echo "❌ Script setup_wan22_native.sh non trouvé"
        echo "⚠️  Basculement vers OwnCloud (fallback)..."
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

        # Chemin de base après déplacement
        CHECKPOINTS_BASE="/workspace/comfyui/ComfyUI/models/checkpoints"
        DIFFUSION_DIR="$CHECKPOINTS_BASE/diffusion_models"

        # Vérification générique via registre (tous modèles)
        set +e
        python3 -c "
import os, sys
sys.path.insert(0, '/workspace')
from src.model_registry import get_registry
registry = get_registry()
files = registry.get_diffusion_files('$MODEL_NAME')
if not files:
    print('❌ Modèle inconnu du registre')
    sys.exit(1)
for f in files:
    # Chercher dans MODEL_DIR d'abord, puis dans checkpoints/<comfyui_subdir>/
    path = os.path.join('$MODEL_DIR', f.filename)
    if not os.path.isfile(path):
        alt = os.path.join('$CHECKPOINTS_BASE', f.comfyui_subdir, f.filename)
        if os.path.isfile(alt):
            path = alt
        else:
            print(f'❌ Fichier manquant: {f.filename}')
            sys.exit(1)
    size_gb = os.path.getsize(path) / (1024**3)
    if size_gb < f.min_size_gb:
        print(f'❌ {f.filename} incomplet: {size_gb:.2f} GB (min: {f.min_size_gb} GB)')
        sys.exit(1)
    print(f'✅ {f.filename}: {size_gb:.2f} GB')
"
        VERIFY_EXIT=$?
        set -e
        if [ $VERIFY_EXIT -ne 0 ]; then
            exit 1
        fi

        echo "✅ Tous les fichiers sont complets"

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
# SETUP DIFFUSION MODELS (modèles avec symlinks uniquement)
# ============================================

if [ "$HAS_SYMLINKS" = "true" ]; then
    echo ""
    echo "🔗 Configuration des modèles et encodeurs ($DISPLAY_NAME)..."

    if [ -f "/workspace/scripts/setup_diffusion_models.sh" ]; then
        bash /workspace/scripts/setup_diffusion_models.sh
    fi
fi

# ============================================
# VAE COMFYUI
# ============================================

if [ "$VAE_INTEGRATED" = "true" ]; then
    # VAE intégré dans le checkpoint, rien à configurer
    echo ""
    echo "✅ VAE intégré dans le checkpoint ($DISPLAY_NAME)"
else
    # VAE séparé à copier vers /models/vae/
    echo ""
    echo "🔧 Configuration VAE ($DISPLAY_NAME)..."

    VAE_DIR="/workspace/comfyui/ComfyUI/models/vae"
    mkdir -p "$VAE_DIR"

    CHECKPOINTS_BASE="/workspace/comfyui/ComfyUI/models/checkpoints"
    VAE_BASE="$CHECKPOINTS_BASE/vae"
    VAE_SOURCE="$VAE_BASE/$VAE_FILENAME"
    echo "   Chemin source: $VAE_SOURCE"

    if [ -f "$VAE_SOURCE" ]; then
        cp "$VAE_SOURCE" "$VAE_DIR/$VAE_FILENAME"
        echo "   ✅ VAE copié: $VAE_DIR/$VAE_FILENAME"
    else
        echo "   ⚠️ VAE non trouvé: $VAE_SOURCE"
    fi
fi

# ============================================
# TEXT ENCODER
# ============================================

if [ "$HAS_MODEL_TE" = "true" ]; then
    # Text encoder propre au modèle (ex: Gemma 3 12B pour LTX 2.3)
    #
    # STRUCTURE REQUISE par LTXVGemmaCLIPModelLoader (gemma_encoder.py) :
    # Le node fait path.parents[1] sur le fichier sélectionné pour trouver le model_root.
    # Il faut donc une structure imbriquée à 2 niveaux :
    #
    #   text_encoders/<model_dir>/text_encoder/model.safetensors  ← sélectionné dans ComfyUI
    #   text_encoders/<model_dir>/text_encoder/config.json
    #   text_encoders/<model_dir>/text_encoder/tokenizer.*
    #
    # Ainsi parents[1] = <model_dir>/ = le bon model_root pour les globs récursifs.
    #
    # MODEL_TE_FILENAME du registre = chemin relatif complet, ex:
    #   "gemma_3_12B_it_fp8_scaled/text_encoder/model.safetensors"
    echo ""
    echo "🔧 Configuration Text Encoder ($MODEL_TE_FILENAME)..."

    TE_DIR="/workspace/comfyui/ComfyUI/models/text_encoders"

    # Sous-dossier cible = répertoire parent du model.safetensors dans le chemin registre
    TE_SUBDIR="$TE_DIR/$(dirname "$MODEL_TE_FILENAME")"
    TE_TARGET_BASENAME="$(basename "$MODEL_TE_FILENAME")"
    mkdir -p "$TE_SUBDIR"

    # Nom du fichier plat HF (premier segment du chemin + .safetensors)
    # Ex: "gemma_3_12B_it_fp8_scaled/text_encoder/model.safetensors" → "gemma_3_12B_it_fp8_scaled.safetensors"
    TE_FLAT_NAME="$(echo "$MODEL_TE_FILENAME" | cut -d'/' -f1).safetensors"

    # Recherche du fichier safetensors source et placement dans la structure imbriquée
    if [ -f "$TE_SUBDIR/$TE_TARGET_BASENAME" ]; then
        echo "   ✅ $(dirname "$MODEL_TE_FILENAME")/$TE_TARGET_BASENAME déjà en place"
    elif [ -f "$TE_DIR/$MODEL_TE_FILENAME" ]; then
        # Déjà dans la structure imbriquée correcte (redondant mais sûr)
        echo "   ✅ $MODEL_TE_FILENAME déjà en structure imbriquée"
    elif [ -f "$TE_DIR/$TE_FLAT_NAME" ]; then
        # Fichier plat HF à la racine de text_encoders/ → déplacer vers structure imbriquée
        mv "$TE_DIR/$TE_FLAT_NAME" "$TE_SUBDIR/$TE_TARGET_BASENAME"
        echo "   ✅ $TE_FLAT_NAME → $(dirname "$MODEL_TE_FILENAME")/$TE_TARGET_BASENAME"
    elif [ -f "$MODEL_DIR/$TE_FLAT_NAME" ]; then
        # Fichier plat HF dans le dossier checkpoints du modèle → déplacer
        mv "$MODEL_DIR/$TE_FLAT_NAME" "$TE_SUBDIR/$TE_TARGET_BASENAME"
        echo "   ✅ $TE_FLAT_NAME (depuis checkpoints) → $(dirname "$MODEL_TE_FILENAME")/$TE_TARGET_BASENAME"
    else
        echo "   ⚠️ Text encoder non trouvé: $MODEL_TE_FILENAME"
        echo "   Recherche dans: $TE_DIR/, $MODEL_DIR/ (fichier plat: $TE_FLAT_NAME)"
    fi

    # Fichiers Gemma depuis le plugin LTXVideo (tokenizer + config, bundlés dans le repo)
    PLUGIN_GEMMA_CONFIGS="/workspace/comfyui/ComfyUI/custom_nodes/ComfyUI-LTXVideo/gemma_configs"
    if [ -d "$PLUGIN_GEMMA_CONFIGS" ]; then
        echo "   🔧 Installation fichiers Gemma dans $(dirname "$MODEL_TE_FILENAME")/..."
        for f in tokenizer.model tokenizer.json tokenizer_config.json preprocessor_config.json processor_config.json; do
            if [ -f "$PLUGIN_GEMMA_CONFIGS/$f" ] && [ ! -f "$TE_SUBDIR/$f" ]; then
                cp "$PLUGIN_GEMMA_CONFIGS/$f" "$TE_SUBDIR/"
            fi
        done
        # config.json pour from_pretrained() — gemma3cfg.json = architecture Gemma 3 12B
        if [ -f "$PLUGIN_GEMMA_CONFIGS/gemma3cfg.json" ] && [ ! -f "$TE_SUBDIR/config.json" ]; then
            cp "$PLUGIN_GEMMA_CONFIGS/gemma3cfg.json" "$TE_SUBDIR/config.json"
        fi
        echo "   ✅ Fichiers Gemma installés dans structure imbriquée"
        echo "   📂 $(dirname "$MODEL_TE_FILENAME")/ → config + tokenizer + $TE_TARGET_BASENAME"
    else
        echo "   ⚠️ Plugin LTXVideo non trouvé — fichiers Gemma absents"
    fi

    # Symlink plat pour LTXAVTextEncoderLoader (ComfyUI core, pipeline AV officiel)
    # LTXAVTextEncoderLoader attend un fichier plat dans text_encoders/
    # alors que LTXVGemmaCLIPModelLoader utilise la structure imbriquée
    if [ -f "$TE_SUBDIR/$TE_TARGET_BASENAME" ] && [ ! -f "$TE_DIR/$TE_FLAT_NAME" ]; then
        ln -sf "$(dirname "$MODEL_TE_FILENAME")/$TE_TARGET_BASENAME" "$TE_DIR/$TE_FLAT_NAME"
        echo "   🔗 Symlink: $TE_FLAT_NAME → $(dirname "$MODEL_TE_FILENAME")/$TE_TARGET_BASENAME"
    fi

    # Nettoyage ancienne structure plate (si migration)
    for old_file in config.json tokenizer.model tokenizer.json tokenizer_config.json preprocessor_config.json processor_config.json model.safetensors; do
        if [ -f "$TE_DIR/$old_file" ]; then
            rm -f "$TE_DIR/$old_file"
        fi
    done

else
    # Text encoder partagé (T5)
    echo ""
    echo "🔧 Configuration T5 Encoder ($SHARED_TE_FILENAME)..."

    T5_DIR="/workspace/comfyui/ComfyUI/models/text_encoders/t5"
    mkdir -p "$T5_DIR"

    CHECKPOINTS_BASE="/workspace/comfyui/ComfyUI/models/checkpoints"
    T5_BASE="$CHECKPOINTS_BASE/text_encoders"
    T5_SOURCE="$T5_BASE/$SHARED_TE_FILENAME"
    echo "   Chemin source: $T5_SOURCE"

    if [ -f "$T5_SOURCE" ]; then
        ln -sf "$T5_SOURCE" "$T5_DIR/$SHARED_TE_FILENAME"
        echo "   ✅ Symlink créé: $T5_DIR/$SHARED_TE_FILENAME"
    else
        echo "   ⚠️ T5 Encoder non trouvé: $T5_SOURCE"
    fi
fi

# ============================================
# CLIP VISION + UPSCALERS
# ============================================

echo ""
echo "🔧 Configuration composants partagés..."

UPSCALE_DIR="/workspace/comfyui/ComfyUI/models/upscale_models"
HAT_L_4X_FILE="$UPSCALE_DIR/HAT-L_SRx4_ImageNet-pretrain.pth"
HAT_2X_FILE="$UPSCALE_DIR/HAT_SRx2.pth"

mkdir -p "$UPSCALE_DIR"

# Chemins possibles depuis OwnCloud
OWNCLOUD_HAT_L_4X="$MODEL_DIR/upscale_models/HAT-L_SRx4_ImageNet-pretrain.pth"
OWNCLOUD_HAT_2X="$MODEL_DIR/upscale_models/HAT_SRx2.pth"

# CLIP Vision (modèles sans text encoder propre — ceux avec Gemma n'en ont pas besoin)
if [ "$HAS_MODEL_TE" != "true" ]; then
    CLIP_VISION_DIR="/workspace/comfyui/ComfyUI/models/clip_vision"
    CLIP_VISION_FILE="$CLIP_VISION_DIR/clip-vit-large-patch14-336.safetensors"
    mkdir -p "$CLIP_VISION_DIR"

    OWNCLOUD_CLIP="$MODEL_DIR/clip_vision/clip-vit-large-patch14-336.safetensors"

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
else
    echo "  ℹ️  CLIP Vision non requis ($DISPLAY_NAME utilise un text encoder propre)"
fi

# HAT-L 4x (post-génération)
if [ -f "$OWNCLOUD_HAT_L_4X" ]; then
    echo "  ✅ HAT-L 4x trouvé dans OwnCloud, copie..."
    cp "$OWNCLOUD_HAT_L_4X" "$HAT_L_4X_FILE"
    echo "  ✅ HAT-L 4x copié depuis OwnCloud ($(du -h $HAT_L_4X_FILE | cut -f1))"
elif [ ! -f "$HAT_L_4X_FILE" ]; then
    echo "  📥 HAT-L 4x absent, téléchargement upstream (~158MB)..."
    wget -q --show-progress \
        "https://huggingface.co/jaideepsingh/upscale_models/resolve/main/HAT/HAT-L_SRx4_ImageNet-pretrain.pth" \
        -O "$HAT_L_4X_FILE"

    if [ $? -eq 0 ]; then
        echo "  ✅ HAT-L 4x téléchargé upstream ($(du -h $HAT_L_4X_FILE | cut -f1))"
    else
        echo "  ⚠️ Échec téléchargement HAT-L 4x (non bloquant)"
    fi
else
    echo "  ✅ HAT-L 4x déjà présent: $(du -h $HAT_L_4X_FILE | cut -f1)"
fi

# HAT 2x (pré-génération)
if [ -f "$OWNCLOUD_HAT_2X" ]; then
    echo "  ✅ HAT 2x trouvé dans OwnCloud, copie..."
    cp "$OWNCLOUD_HAT_2X" "$HAT_2X_FILE"
    echo "  ✅ HAT 2x copié depuis OwnCloud ($(du -h $HAT_2X_FILE | cut -f1))"
elif [ ! -f "$HAT_2X_FILE" ]; then
    echo "  📥 HAT 2x absent, téléchargement upstream (~81MB)..."
    wget -q --show-progress \
        "https://huggingface.co/jaideepsingh/upscale_models/resolve/main/HAT/HAT_SRx2.pth" \
        -O "$HAT_2X_FILE"

    if [ $? -eq 0 ]; then
        echo "  ✅ HAT 2x téléchargé upstream ($(du -h $HAT_2X_FILE | cut -f1))"
    else
        echo "  ⚠️ Échec téléchargement HAT 2x (non bloquant)"
    fi
else
    echo "  ✅ HAT 2x déjà présent: $(du -h $HAT_2X_FILE | cut -f1)"
fi

echo "✅ Configuration CLIP Vision + Upscalers terminée"

# ============================================
# LORA DISTILLED (LTX 2.3 uniquement)
# ============================================

if [ "$MODEL_ARCH" = "dit" ]; then
    LORA_DIR="/workspace/comfyui/ComfyUI/models/loras"
    LORA_FILE="$LORA_DIR/ltx-2.3-22b-distilled-lora-384.safetensors"
    mkdir -p "$LORA_DIR"

    if [ -f "$LORA_FILE" ]; then
        echo "  ✅ LoRA distilled déjà présente: $(du -h "$LORA_FILE" | cut -f1)"
    else
        echo "  📥 LoRA distilled absente, téléchargement upstream (~7.6GB)..."
        set +e
        hf download "Lightricks/LTX-2.3" \
            "ltx-2.3-22b-distilled-lora-384.safetensors" \
            --local-dir "$LORA_DIR"
        LORA_EXIT=$?
        set -e

        if [ $LORA_EXIT -eq 0 ] && [ -f "$LORA_FILE" ]; then
            echo "  ✅ LoRA distilled téléchargée: $(du -h "$LORA_FILE" | cut -f1)"
        else
            echo "  ⚠️ Échec téléchargement LoRA distilled (non bloquant — le workflow fonctionnera sans)"
        fi
    fi
else
    echo ""
    echo "  ℹ️  LoRA distilled non requise (modèle $DISPLAY_NAME)"
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
    echo "ℹ️  .env non présent (config via YAML + variables d'environnement)"
fi

echo ""
echo "🎬 GEGM MotionLab ready on RunPod!"
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
