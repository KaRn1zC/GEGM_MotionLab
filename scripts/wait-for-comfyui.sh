#!/bin/bash
# Script utilitaire pour attendre que ComfyUI soit prêt
# Usage: ./wait-for-comfyui.sh [timeout_seconds]

set -e

TIMEOUT="${1:-180}"  # Timeout par défaut: 3 minutes
COMFYUI_HOST="${COMFYUI_HOST:-127.0.0.1}"
COMFYUI_PORT="${COMFYUI_PORT:-8188}"
COMFYUI_URL="http://${COMFYUI_HOST}:${COMFYUI_PORT}"

echo "🔍 Attente de ComfyUI sur ${COMFYUI_URL}..."
echo "   Timeout: ${TIMEOUT}s"

START_TIME=$(date +%s)
READY=false

while true; do
    CURRENT_TIME=$(date +%s)
    ELAPSED=$((CURRENT_TIME - START_TIME))

    if [ "$ELAPSED" -ge "$TIMEOUT" ]; then
        echo ""
        echo "❌ Timeout atteint (${TIMEOUT}s) - ComfyUI non disponible"
        exit 1
    fi

    # Tester l'endpoint /system_stats
    if curl -s -f "${COMFYUI_URL}/system_stats" > /dev/null 2>&1; then
        READY=true
        break
    fi

    # Afficher un point de progression toutes les 5 secondes
    if [ $((ELAPSED % 5)) -eq 0 ]; then
        echo -n "."
    fi

    sleep 1
done

echo ""
echo "✅ ComfyUI est prêt ! (après ${ELAPSED}s)"

# Afficher les stats système
echo ""
echo "📊 Stats ComfyUI:"
curl -s "${COMFYUI_URL}/system_stats" | python3 -m json.tool 2>/dev/null || echo "  (stats non disponibles)"

exit 0
