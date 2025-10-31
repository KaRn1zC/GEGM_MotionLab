#!/usr/bin/env python3
"""
Fix VAE channels mismatch in WanVideoImageToVideoEncode
Réduit les CLIP embeddings de 96 à 48 canaux pour compatibilité VAE WAN 5B
"""

import sys
from pathlib import Path


def fix_wan_vae_channels():
    """Applique le fix de manière sûre"""

    node_file = Path(
        "/workspace/comfyui/ComfyUI/custom_nodes/ComfyUI-WanVideoWrapper/nodes.py"
    )

    if not node_file.exists():
        print(f"❌ Fichier non trouvé: {node_file}")
        return False

    try:
        with open(node_file, "r", encoding="utf-8") as f:
            lines = f.readlines()

        # Chercher la ligne exacte à patcher (ligne 963 environ)
        # Pattern: "clip_context": clip_embeds.get("clip_embeds", None) if clip_embeds is not None else None,

        found = False
        for i, line in enumerate(lines):
            if (
                '"clip_context": clip_embeds.get("clip_embeds"' in line
                and "if clip_embeds is not None" in line
            ):
                print(f"✅ Found ligne {i + 1}: {line.strip()[:80]}")

                # Insérer le fix APRÈS cette ligne
                indent = len(line) - len(line.lstrip())
                fix_lines = [
                    " " * indent
                    + "# FIX: Réduire CLIP embeddings de 96 à 48 canaux (VAE WAN 5B)\n",
                    " " * indent
                    + 'if clip_embeds is not None and "clip_embeds" in clip_embeds:\n',
                    " " * (indent + 4) + 'clip_tensor = clip_embeds["clip_embeds"]\n',
                    " " * (indent + 4)
                    + 'if hasattr(clip_tensor, "shape") and len(clip_tensor.shape) >= 2:\n',
                    " " * (indent + 8) + "if clip_tensor.shape[1] == 96:\n",
                    " " * (indent + 12)
                    + 'clip_embeds["clip_embeds"] = clip_tensor[:, :48, ...]\n',
                ]

                # Insérer après cette ligne
                lines = lines[: i + 1] + fix_lines + lines[i + 1 :]
                found = True
                break

        if not found:
            print("❌ Pattern non trouvé dans le fichier")
            return False

        # Écrire le fichier patché
        with open(node_file, "w", encoding="utf-8") as f:
            f.writelines(lines)

        print("✅ Patch appliqué avec succès!")
        return True

    except Exception as e:
        print(f"❌ Erreur: {e}")
        import traceback

        traceback.print_exc()
        return False


if __name__ == "__main__":
    success = fix_wan_vae_channels()
    sys.exit(0 if success else 1)
