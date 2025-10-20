#!/usr/bin/env python3
"""
Découpe automatiquement les fichiers >8GB et upload sur OwnCloud
Usage: python scripts/split_and_upload.py --model wan2.2-i2v-a14b
"""

import os
import sys
import subprocess
import argparse
from pathlib import Path

# Configuration
MAX_FILE_SIZE = 8 * 1024 * 1024 * 1024  # 8GB
CHUNK_SIZE = 2 * 1024 * 1024 * 1024  # 2GB


def get_file_size(file_path):
    """Retourne la taille en bytes"""
    return os.path.getsize(file_path)


def format_size(size_bytes):
    """Format size en GB"""
    return f"{size_bytes / 1e9:.2f} GB"


def split_large_file(file_path, chunks_dir):
    """Découpe un fichier en morceaux de 2GB"""
    file_path = Path(file_path)
    chunks_dir = Path(chunks_dir)
    chunks_dir.mkdir(parents=True, exist_ok=True)

    # Nom des chunks
    chunk_prefix = file_path.stem + "_chunk_"

    print(
        f"📦 Découpage de {file_path.name} ({format_size(get_file_size(file_path))})..."
    )

    # Commande split
    cmd = [
        "split",
        "-b",
        str(CHUNK_SIZE),
        str(file_path),
        str(chunks_dir / chunk_prefix),
    ]

    result = subprocess.run(cmd, capture_output=True, text=True)

    if result.returncode != 0:
        print(f"❌ Erreur lors du découpage: {result.stderr}")
        sys.exit(1)

    # Lister les chunks créés
    chunks = sorted(chunks_dir.glob(f"{chunk_prefix}*"))
    print(f"✅ {len(chunks)} chunks créés")
    for chunk in chunks:
        print(f"   - {chunk.name} ({format_size(get_file_size(chunk))})")

    return file_path.name, [c.name for c in chunks]


def create_mapping_file(mapping, chunks_dir):
    """Crée mapping.txt avec la liste des fichiers découpés"""
    mapping_file = chunks_dir / "mapping.txt"

    with open(mapping_file, "w") as f:
        for original_file, chunks in mapping.items():
            f.write(f"FILE:{original_file}\n")
            for chunk in chunks:
                f.write(f"CHUNK:{chunk}\n")
            f.write("\n")

    print(f"✅ Mapping créé: {mapping_file}")


def process_model_dir(model_dir, owncloud_remote):
    """Traite un dossier de modèle"""
    model_dir = Path(model_dir)
    chunks_dir = model_dir / "chunks"

    print(f"\n🔍 Scan de {model_dir}...")

    # Trouver les fichiers >8GB
    files_to_split = []
    for file_path in model_dir.rglob("*"):
        if file_path.is_file() and file_path.parent.name != "chunks":
            size = get_file_size(file_path)
            if size > MAX_FILE_SIZE:
                rel_path = file_path.relative_to(model_dir)
                files_to_split.append((file_path, rel_path))
                print(f"⚠️  Fichier trop gros: {rel_path} ({format_size(size)})")

    # Découper
    mapping = {}
    if files_to_split:
        print(f"\n📦 Découpage de {len(files_to_split)} fichier(s)...")
        for file_path, rel_path in files_to_split:
            original_name, chunks = split_large_file(file_path, chunks_dir)
            mapping[original_name] = chunks

        create_mapping_file(mapping, chunks_dir)
    else:
        print("✅ Aucun fichier >8GB à découper")

    # Upload avec TOUS les paramètres optimaux
    print(f"\n📤 Upload vers {owncloud_remote}...")
    print("   Durée estimée: ~30 min pour les chunks + 2-3h pour le reste")

    upload_cmd = [
        "rclone",
        "copy",
        str(model_dir),
        owncloud_remote,
        "--progress",
        "--transfers",
        "2",  # 2 transferts parallèles (chunks plus rapides)
        "--retries",
        "10",
        "--low-level-retries",
        "10",
        "--timeout",
        "1h",
        "--contimeout",
        "60s",
        "--stats",
        "30s",
        "--size-only",
        "--no-update-modtime",
        "--exclude",
        ".DS_Store",
        "--exclude",
        "nohup.out",
        "--exclude",
        ".cache/**",
        "--skip-links",
        "-vv",
    ]

    result = subprocess.run(upload_cmd)

    if result.returncode != 0:
        print("❌ Erreur lors de l'upload")
        sys.exit(1)

    print("✅ Upload terminé")


def main():
    parser = argparse.ArgumentParser(description="Découpe et upload les modèles")
    parser.add_argument(
        "--model", required=True, help="Nom du modèle (ex: wan2.2-i2v-a14b)"
    )
    args = parser.parse_args()

    model_dir = Path(f"models/{args.model}")
    if not model_dir.exists():
        print(f"❌ Dossier {model_dir} introuvable")
        sys.exit(1)

    owncloud_remote = f"owncloud:/GEGM_ComfyUI/Models/{args.model}/"

    print("🚀 Démarrage de l'upload avec découpe automatique")
    print(f"📂 Source: {model_dir}")
    print(f"☁️  Destination: {owncloud_remote}")

    process_model_dir(model_dir, owncloud_remote)

    print("\n🎉 Processus terminé avec succès !")


if __name__ == "__main__":
    main()
