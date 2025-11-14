#!/bin/bash
set -e

# Argument: nom du modèle spécifique ou "all" (défaut)
MODEL="${1:-all}"

echo "🎬 Setup WAN 2.2 avec support natif ComfyUI"
echo "=============================================="

# Vérifier l'environnement virtuel
if [[ "$VIRTUAL_ENV" != *".venv"* ]]; then
    echo "❌ Environnement .venv non activé"
    exit 1
fi

echo "✅ Environnement virtuel: $VIRTUAL_ENV"

# Étape 1: Installer huggingface-cli
echo "📦 Installation huggingface-cli..."
pip install -q "huggingface_hub[cli]"

# Étape 2: Créer les dossiers modèles
echo "📁 Création des dossiers de modèles..."
mkdir -p models/{wan2.2-i2v-a14b,wan2.2-ti2v-5b}

# Étape 3: Test de connexion Hugging Face
echo "🔗 Test de connexion Hugging Face..."
if hf auth whoami 2>/dev/null; then
    echo "✅ Connecté à Hugging Face"
else
    echo "ℹ️  Pas connecté à HF (modèles publics OK)"
fi

# Étape 4: Téléchargement selon le modèle demandé
if [ "$MODEL" = "all" ]; then
    echo ""
    echo "📥 Téléchargement des deux modèles..."
    echo ""

    echo "📦 Modèle 1/2: WAN 2.2 TI2V 5B (9.4GB)..."
    hf download Wan-AI/Wan2.2-TI2V-5B --local-dir ./models/wan2.2-ti2v-5b
    echo "✅ WAN 2.2 5B téléchargé"

    echo ""
    echo "🔧 Fusion des fichiers safetensors (5B)..."
    python scripts/merge_safetensors.py wan2.2-ti2v-5b
    if [ $? -ne 0 ]; then
        echo "❌ ÉCHEC: Fusion safetensors 5B"
        exit 1
    fi

    echo ""
    echo "🔍 Vérification intégrité modèle de diffusion (5B)..."
    python scripts/verify_diffusion_model.py wan2.2-ti2v-5b
    if [ $? -ne 0 ]; then
        echo "❌ ÉCHEC: Modèle de diffusion 5B corrompu ou incomplet"
        exit 1
    fi

    echo ""
    echo "🔍 Vérification intégrité T5 Encoder (5B)..."
    python scripts/verify_t5_integrity.py wan2.2-ti2v-5b
    if [ $? -ne 0 ]; then
        echo "❌ ÉCHEC: T5 Encoder 5B corrompu ou incomplet"
        exit 1
    fi

    echo ""
    echo "🗑️  Suppression des fichiers sharded (5B)..."
    rm -f models/wan2.2-ti2v-5b/diffusion_pytorch_model-0000[123]-of-00003.safetensors
    rm -f models/wan2.2-ti2v-5b/diffusion_pytorch_model.safetensors.index.json
    echo "✅ Fichiers sharded supprimés (économie ~18.5 GB)"

    echo ""
    echo "📦 Modèle 2/2: WAN 2.2 I2V 14B (27.8GB)..."
    hf download Wan-AI/Wan2.2-I2V-A14B --local-dir ./models/wan2.2-i2v-a14b
    echo "✅ WAN 2.2 14B téléchargé"

    echo ""
    echo "🔧 Fusion des fichiers safetensors (14B)..."
    python scripts/merge_safetensors.py wan2.2-i2v-a14b
    if [ $? -ne 0 ]; then
        echo "❌ ÉCHEC: Fusion safetensors 14B"
        exit 1
    fi

    echo ""
    echo "🔍 Vérification intégrité modèle de diffusion (14B)..."
    python scripts/verify_diffusion_model.py wan2.2-i2v-a14b
    if [ $? -ne 0 ]; then
        echo "❌ ÉCHEC: Modèle de diffusion 14B corrompu ou incomplet"
        exit 1
    fi

    echo ""
    echo "🔍 Vérification intégrité T5 Encoder (14B)..."
    python scripts/verify_t5_integrity.py wan2.2-i2v-a14b
    if [ $? -ne 0 ]; then
        echo "❌ ÉCHEC: T5 Encoder 14B corrompu ou incomplet"
        exit 1
    fi

    echo ""
    echo "🗑️  Suppression des fichiers sharded (14B)..."
    rm -f models/wan2.2-i2v-a14b/diffusion_pytorch_model-*-of-*.safetensors
    rm -f models/wan2.2-i2v-a14b/diffusion_pytorch_model.safetensors.index.json
    echo "✅ Fichiers sharded supprimés"

elif [ "$MODEL" = "wan2.2-i2v-a14b" ]; then
    echo ""
    echo "📥 Téléchargement WAN 2.2 I2V 14B (27.8GB)..."
    hf download Wan-AI/Wan2.2-I2V-A14B --local-dir ./models/wan2.2-i2v-a14b
    echo "✅ WAN 2.2 14B téléchargé"

    echo ""
    echo "🔧 Fusion des fichiers safetensors..."
    python scripts/merge_safetensors.py wan2.2-i2v-a14b
    if [ $? -ne 0 ]; then
        echo "❌ ÉCHEC: Fusion safetensors"
        exit 1
    fi

    echo ""
    echo "🔍 Vérification intégrité modèle de diffusion..."
    python scripts/verify_diffusion_model.py wan2.2-i2v-a14b
    if [ $? -ne 0 ]; then
        echo "❌ ÉCHEC: Modèle de diffusion corrompu ou incomplet"
        exit 1
    fi

    echo ""
    echo "🔍 Vérification intégrité T5 Encoder..."
    python scripts/verify_t5_integrity.py wan2.2-i2v-a14b
    if [ $? -ne 0 ]; then
        echo "❌ ÉCHEC: T5 Encoder corrompu ou incomplet"
        exit 1
    fi

    echo ""
    echo "🗑️  Suppression des fichiers sharded..."
    rm -f models/wan2.2-i2v-a14b/diffusion_pytorch_model-*-of-*.safetensors
    rm -f models/wan2.2-i2v-a14b/diffusion_pytorch_model.safetensors.index.json
    echo "✅ Fichiers sharded supprimés"

elif [ "$MODEL" = "wan2.2-ti2v-5b" ]; then
    echo ""
    echo "📥 Téléchargement WAN 2.2 TI2V 5B (9.4GB)..."
    hf download Wan-AI/Wan2.2-TI2V-5B --local-dir ./models/wan2.2-ti2v-5b
    echo "✅ WAN 2.2 5B téléchargé"

    echo ""
    echo "🔧 Fusion des fichiers safetensors..."
    python scripts/merge_safetensors.py wan2.2-ti2v-5b
    if [ $? -ne 0 ]; then
        echo "❌ ÉCHEC: Fusion safetensors"
        exit 1
    fi

    echo ""
    echo "🔍 Vérification intégrité modèle de diffusion..."
    python scripts/verify_diffusion_model.py wan2.2-ti2v-5b
    if [ $? -ne 0 ]; then
        echo "❌ ÉCHEC: Modèle de diffusion corrompu ou incomplet"
        exit 1
    fi

    echo ""
    echo "🔍 Vérification intégrité T5 Encoder..."
    python scripts/verify_t5_integrity.py wan2.2-ti2v-5b
    if [ $? -ne 0 ]; then
        echo "❌ ÉCHEC: T5 Encoder corrompu ou incomplet"
        exit 1
    fi

    echo ""
    echo "🗑️  Suppression des fichiers sharded..."
    rm -f models/wan2.2-ti2v-5b/diffusion_pytorch_model-0000[123]-of-00003.safetensors
    rm -f models/wan2.2-ti2v-5b/diffusion_pytorch_model.safetensors.index.json
    echo "✅ Fichiers sharded supprimés (économie ~18.5 GB)"

else
    echo "❌ Modèle invalide: $MODEL"
    echo "Usage: $0 [all|wan2.2-i2v-a14b|wan2.2-ti2v-5b]"
    exit 1
fi

# Étape 5: Vérification des téléchargements
echo ""
echo "🔍 Vérification des modèles téléchargés..."
if [ "$MODEL" = "all" ] || [ "$MODEL" = "wan2.2-i2v-a14b" ]; then
    if [ -d "models/wan2.2-i2v-a14b" ]; then
        size=$(du -sh models/wan2.2-i2v-a14b | cut -f1)
        echo "✅ wan2.2-i2v-a14b ($size)"
    fi
fi

if [ "$MODEL" = "all" ] || [ "$MODEL" = "wan2.2-ti2v-5b" ]; then
    if [ -d "models/wan2.2-ti2v-5b" ]; then
        size=$(du -sh models/wan2.2-ti2v-5b | cut -f1)
        echo "✅ wan2.2-ti2v-5b ($size)"
    fi
fi

echo ""
echo "✅ Setup WAN 2.2 terminé !"
