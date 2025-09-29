#!/bin/bash

set -e

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
pip install "huggingface_hub[cli]"

# Étape 2: Créer les dossiers modèles
echo "📁 Création des dossiers de modèles..."
mkdir -p models/{wan2.2-i2v-a14b,wan2.2-ti2v-5b,pyramid-flow}
mkdir -p models/{diffusion_models,vae,text_encoders,checkpoints}

# Étape 3: Test de connexion Hugging Face
echo "🔗 Test de connexion Hugging Face..."
if hf auth whoami 2>/dev/null; then
    echo "✅ Connecté à Hugging Face"
else
    echo "ℹ️  Pas connecté à HF (modèles publics OK)"
fi

# Étape 4: Choix du modèle à télécharger
echo ""
echo "🤖 Quel modèle WAN 2.2 voulez-vous télécharger ?"
echo "1. WAN 2.2 TI2V 5B (Recommandé - 9.4GB, 12GB+ VRAM)"
echo "2. WAN 2.2 I2V 14B (Avancé - 27.8GB, 24GB+ VRAM)"
echo "3. Les deux modèles"
echo "4. Aucun (setup seulement)"
echo ""

read -p "Votre choix [1-4]: " choice

case $choice in
    1)
        echo "📥 Téléchargement WAN 2.2 TI2V 5B..."
        hf download Wan-AI/Wan2.2-TI2V-5B --local-dir ./models/wan2.2-ti2v-5b
        echo "✅ WAN 2.2 5B téléchargé"
        ;;
    2)
        echo "📥 Téléchargement WAN 2.2 I2V 14B (peut prendre 30+ minutes)..."
        hf download Wan-AI/Wan2.2-I2V-A14B --local-dir ./models/wan2.2-i2v-a14b
        echo "✅ WAN 2.2 14B téléchargé"
        ;;
    3)
        echo "📥 Téléchargement des deux modèles..."
        hf download Wan-AI/Wan2.2-TI2V-5B --local-dir ./models/wan2.2-ti2v-5b &
        hf download Wan-AI/Wan2.2-I2V-A14B --local-dir ./models/wan2.2-i2v-a14b
        wait
        echo "✅ Tous les modèles téléchargés"
        ;;
    4)
        echo "⚠️ Aucun modèle téléchargé - setup uniquement"
        ;;
    *)
        echo "❌ Choix invalide"
        exit 1
        ;;
esac

# Étape 5: Vérification des téléchargements
echo ""
echo "🔍 Vérification des modèles téléchargés..."
find models/ -name "*.safetensors" -o -name "*.bin" | while read file; do
    size=$(du -h "$file" | cut -f1)
    echo "✅ $file ($size)"
done

# Étape 6: Instructions finales
echo ""
echo "🎉 Setup WAN 2.2 terminé !"
echo ""
echo "📋 Prochaines étapes:"
echo "1. Démarrer ComfyUI avec: cd comfyui && python main.py"
echo "2. Installer ComfyUI Manager depuis l'interface"
echo "3. Installer les custom nodes via Manager"
echo "4. Utiliser les nodes natifs WAN 2.2"
echo ""
echo "🔧 Nodes WAN 2.2 natifs dans ComfyUI:"
echo "   • WAN Diffusion Model Loader"
echo "   • WAN Sampler"
echo "   • WAN Text Encoder"
echo "   • WAN VAE"
echo ""
echo "📖 Documentation: https://docs.comfy.org/tutorials/video/wan/wan2_2"

