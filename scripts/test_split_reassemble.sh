#!/bin/bash
# Test de découpe et reconstitution du T5 Encoder
# Usage: ./scripts/test_split_reassemble.sh wan2.2-ti2v-5b

set -e

MODEL_NAME="${1:-wan2.2-ti2v-5b}"
MODEL_DIR="models/$MODEL_NAME"
T5_FILE="$MODEL_DIR/models_t5_umt5-xxl-enc-bf16.pth"
TEST_DIR="test_chunks_$$"

echo "🧪 Test de découpe/reconstitution du T5 Encoder"
echo "================================================"
echo "Modèle: $MODEL_NAME"
echo "Fichier T5: $T5_FILE"
echo ""

# Vérifier que le fichier T5 existe
if [ ! -f "$T5_FILE" ]; then
    echo "❌ Fichier T5 introuvable: $T5_FILE"
    echo "   Téléchargez d'abord le modèle:"
    echo "   ./scripts/setup_wan22_native.sh $MODEL_NAME"
    exit 1
fi

# Créer dossier de test
mkdir -p "$TEST_DIR"

echo "📊 Fichier original:"
ls -lh "$T5_FILE"
echo ""

# Calculer checksum original
echo "🔐 Calcul checksum original..."
ORIGINAL_SHA256=$(shasum -a 256 "$T5_FILE" | cut -d' ' -f1)
ORIGINAL_SIZE=$(stat -f%z "$T5_FILE" 2>/dev/null || stat -c%s "$T5_FILE" 2>/dev/null)
echo "   SHA256: $ORIGINAL_SHA256"
echo "   Taille: $ORIGINAL_SIZE bytes"
echo ""

# Découper en chunks de 2GB
echo "📦 Découpe en chunks de 2GB..."
CHUNK_SIZE=$((2 * 1024 * 1024 * 1024))
split -b $CHUNK_SIZE "$T5_FILE" "$TEST_DIR/t5_chunk_"

# Lister les chunks
echo ""
echo "📋 Chunks créés:"
ls -lh "$TEST_DIR"/t5_chunk_* | awk '{print "   " $9 " - " $5}'
CHUNK_COUNT=$(ls -1 "$TEST_DIR"/t5_chunk_* | wc -l | tr -d ' ')
echo "   Total: $CHUNK_COUNT chunks"
echo ""

# Reconstituer
echo "🔨 Reconstitution depuis les chunks..."
cat "$TEST_DIR"/t5_chunk_* > "$TEST_DIR/t5_reconstituted.pth"

# Vérifier taille
RECONSTITUTED_SIZE=$(stat -f%z "$TEST_DIR/t5_reconstituted.pth" 2>/dev/null || stat -c%s "$TEST_DIR/t5_reconstituted.pth" 2>/dev/null)
echo "   Taille reconstituée: $RECONSTITUTED_SIZE bytes"

if [ "$ORIGINAL_SIZE" != "$RECONSTITUTED_SIZE" ]; then
    echo ""
    echo "❌ ERREUR: Taille différente!"
    echo "   Original:      $ORIGINAL_SIZE bytes"
    echo "   Reconstitué:   $RECONSTITUTED_SIZE bytes"
    echo "   Différence:    $((RECONSTITUTED_SIZE - ORIGINAL_SIZE)) bytes"
    rm -rf "$TEST_DIR"
    exit 1
fi

echo "   ✅ Taille identique"
echo ""

# Calculer checksum reconstitué
echo "🔐 Calcul checksum reconstitué..."
RECONSTITUTED_SHA256=$(shasum -a 256 "$TEST_DIR/t5_reconstituted.pth" | cut -d' ' -f1)
echo "   SHA256: $RECONSTITUTED_SHA256"
echo ""

# Comparer
if [ "$ORIGINAL_SHA256" = "$RECONSTITUTED_SHA256" ]; then
    echo "================================================"
    echo "✅ TEST RÉUSSI!"
    echo "   Les checksums sont identiques"
    echo "   La découpe/reconstitution fonctionne correctement"
    echo "================================================"
    SUCCESS=true
else
    echo "================================================"
    echo "❌ TEST ÉCHOUÉ!"
    echo "   Les checksums sont DIFFÉRENTS"
    echo "   Original:      $ORIGINAL_SHA256"
    echo "   Reconstitué:   $RECONSTITUTED_SHA256"
    echo ""
    echo "   ⚠️  PROBLÈME DÉTECTÉ dans la découpe/reconstitution"
    echo "================================================"
    SUCCESS=false
fi

echo ""

# Vérifier intégrité PyTorch du fichier reconstitué
echo "🔍 Vérification intégrité PyTorch du T5 reconstitué..."

# Créer structure de dossier compatible avec verify_t5_integrity.py
mkdir -p "$TEST_DIR/$MODEL_NAME"
mv "$TEST_DIR/t5_reconstituted.pth" "$TEST_DIR/$MODEL_NAME/models_t5_umt5-xxl-enc-bf16.pth"

python3 scripts/verify_t5_integrity.py $MODEL_NAME --base-dir "$TEST_DIR"
VERIFY_RESULT=$?

echo ""

if [ $VERIFY_RESULT -eq 0 ]; then
    echo "✅ Vérification PyTorch réussie"
else
    echo "❌ Vérification PyTorch échouée"
    SUCCESS=false
fi

# Nettoyer
echo ""
echo "🗑️  Nettoyage..."
rm -rf "$TEST_DIR"
echo "✅ Dossier de test supprimé"

echo ""
if [ "$SUCCESS" = true ]; then
    echo "🎉 Tous les tests sont passés avec succès!"
    exit 0
else
    echo "❌ Certains tests ont échoué"
    exit 1
fi
