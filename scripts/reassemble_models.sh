#!/bin/bash
# Reconstitue automatiquement les fichiers découpés
# Usage: ./reassemble_models.sh /workspace/models

set -e

MODEL_BASE_DIR="${1:-/workspace/models}"

echo "🔧 Reconstitution des fichiers découpés..."
echo "📂 Base dir: $MODEL_BASE_DIR"

# Parcourir tous les dossiers chunks
find "$MODEL_BASE_DIR" -type d -name "chunks" | while read chunks_dir; do
    parent_dir=$(dirname "$chunks_dir")
    mapping_file="$chunks_dir/mapping.txt"
    
    echo ""
    echo "📦 Traitement de $chunks_dir"
    
    if [ ! -f "$mapping_file" ]; then
        echo "⚠️  Pas de mapping.txt, skip"
        continue
    fi
    
    # Lire le mapping
    current_file=""
    current_chunks=()
    
    while IFS= read -r line; do
        if [[ $line == FILE:* ]]; then
            # Nouveau fichier
            if [ -n "$current_file" ]; then
                # Reconstituer le fichier précédent
                output_file="$parent_dir/$current_file"
                
                if [ -f "$output_file" ]; then
                    echo "✅ $current_file déjà reconstitué"
                else
                    echo "🔨 Reconstitution de $current_file..."
                    
                    # Construire la commande cat
                    chunk_paths=()
                    for chunk in "${current_chunks[@]}"; do
                        chunk_paths+=("$chunks_dir/$chunk")
                    done
                    
                    cat "${chunk_paths[@]}" > "$output_file"
                    
                    if [ $? -eq 0 ]; then
                        file_size=$(du -h "$output_file" | cut -f1)
                        echo "✅ $current_file reconstitué ($file_size)"
                    else
                        echo "❌ Erreur reconstitution de $current_file"
                        rm -f "$output_file"
                    fi
                fi
            fi
            
            # Nouveau fichier
            current_file="${line#FILE:}"
            current_chunks=()
            
        elif [[ $line == CHUNK:* ]]; then
            # Ajouter un chunk
            chunk_name="${line#CHUNK:}"
            current_chunks+=("$chunk_name")
        fi
    done < "$mapping_file"
    
    # Dernier fichier
    if [ -n "$current_file" ]; then
        output_file="$parent_dir/$current_file"
        
        if [ -f "$output_file" ]; then
            echo "✅ $current_file déjà reconstitué"
        else
            echo "🔨 Reconstitution de $current_file..."
            
            chunk_paths=()
            for chunk in "${current_chunks[@]}"; do
                chunk_paths+=("$chunks_dir/$chunk")
            done
            
            cat "${chunk_paths[@]}" > "$output_file"
            
            if [ $? -eq 0 ]; then
                file_size=$(du -h "$output_file" | cut -f1)
                echo "✅ $current_file reconstitué ($file_size)"
            else
                echo "❌ Erreur reconstitution de $current_file"
                rm -f "$output_file"
            fi
        fi
    fi
    
    # Optionnel: supprimer les chunks
    # echo "🗑️  Suppression des chunks..."
    # rm -rf "$chunks_dir"
done

echo ""
echo "✅ Reconstitution terminée"
