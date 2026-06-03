echo "🔍 Validation de la configuration Docker"
echo "========================================"

# Couleurs
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

errors=0
warnings=0

# Fonction de check
check_file() {
    if [ -f "$1" ]; then
        echo -e "${GREEN}✅${NC} $1"
    else
        echo -e "${RED}❌${NC} $1 MANQUANT"
        ((errors++))
    fi
}

check_executable() {
    if [ -x "$1" ]; then
        echo -e "${GREEN}✅${NC} $1 (exécutable)"
    else
        echo -e "${YELLOW}⚠️${NC} $1 (pas exécutable)"
        ((warnings++))
    fi
}

# Vérification des fichiers obligatoires
echo ""
echo "📁 Fichiers obligatoires:"
check_file "Dockerfile"
check_file ".dockerignore"
check_file "docker-compose.yml"

echo ""
echo "📜 Scripts:"
check_executable "docker-entrypoint.sh"
check_executable "install-comfyui.sh"

echo ""
echo "🔧 Fichiers optionnels:"
check_file "docker-compose.override.yml"
check_file "Makefile"

# Vérifier qu'il n'y a PAS de dossier docker/
echo ""
echo "🚫 Vérification anti-duplication:"
if [ -d "docker/" ]; then
    echo -e "${RED}❌${NC} Dossier docker/ existe (doit être supprimé)"
    ((errors++))
else
    echo -e "${GREEN}✅${NC} Pas de dossier docker/ (correct)"
fi

# Vérifier les modèles
echo ""
echo "🤖 Vérification des modèles:"
if [ -d "models/wan2.2-i2v-a14b/high_noise_model" ]; then
    size=$(du -sh models/wan2.2-i2v-a14b/ 2>/dev/null | cut -f1)
    echo -e "${GREEN}✅${NC} Modèles WAN 2.2 présents ($size)"
else
    echo -e "${YELLOW}⚠️${NC} Modèles WAN 2.2 manquants"
    echo "   💡 Exécutez: ./scripts/setup_wan22_native.sh"
    ((warnings++))
fi

# Résumé
echo ""
echo "========================================"
if [ $errors -eq 0 ] && [ $warnings -eq 0 ]; then
    echo -e "${GREEN}✅ VALIDATION RÉUSSIE${NC}"
    echo "Prêt pour docker build !"
    exit 0
elif [ $errors -eq 0 ]; then
    echo -e "${YELLOW}⚠️ VALIDATION OK AVEC AVERTISSEMENTS${NC}"
    echo "Warnings: $warnings"
    exit 0
else
    echo -e "${RED}❌ VALIDATION ÉCHOUÉE${NC}"
    echo "Erreurs: $errors | Warnings: $warnings"
    exit 1
fi

