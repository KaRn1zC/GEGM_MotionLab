#!/usr/bin/env python3
"""
Patch ComfyUI pour permettre le chargement des fichiers safetensors FP8 avec PyTorch 2.6+

Problème : PyTorch 2.6+ utilise weights_only=True par défaut, ce qui empêche
le chargement des fichiers safetensors FP8 du T5 Encoder WAN 2.2 ComfyUI Native.

Solution : Modifier comfy/utils.py pour utiliser weights_only=False lors du
chargement des fichiers .pth et .safetensors.
"""

import sys
from pathlib import Path


def patch_comfyui_utils():
    """Patch le fichier comfy/utils.py pour permettre le chargement safetensors FP8"""

    comfyui_utils = Path("/workspace/comfyui/ComfyUI/comfy/utils.py")

    if not comfyui_utils.exists():
        print(f"❌ Fichier non trouvé: {comfyui_utils}")
        return False

    print(f"🔧 Patch de {comfyui_utils}...")

    # Lire le contenu
    content = comfyui_utils.read_text()

    # Vérifier si déjà patché (v4 avec symlink resolution)
    if "ckpt_real = os.path.realpath(ckpt_normalized)" in content:
        print("✅ Déjà patché (v4), aucune modification nécessaire")
        return True

    # Vérifier si patché avec une ancienne version (v1-v3)
    old_patch_detected = "# PATCH FP8: Force safetensors loading" in content
    if old_patch_detected:
        print("⚠️  Ancienne version du patch détectée (v1-v3)")
        print("   → Mise à jour vers v4 (résolution symlinks)...")

    # Trouver la fonction load_torch_file
    lines = content.splitlines()

    # Chercher la ligne qui contient "def load_torch_file"
    func_start_idx = None
    for i, line in enumerate(lines):
        if "def load_torch_file" in line:
            func_start_idx = i
            break

    if func_start_idx is None:
        print("❌ Fonction load_torch_file non trouvée")
        return False

    # Trouver la ligne à remplacer
    target_line_idx = None
    indent = ""

    for i in range(func_start_idx, min(func_start_idx + 150, len(lines))):
        line = lines[i]
        # Chercher soit la ligne originale, soit la ligne du vieux patch
        if ("torch.load(ckpt, map_location=device, weights_only=True" in line or
            (old_patch_detected and "pl_sd = torch.load(ckpt, map_location=device, weights_only=False" in line)):
            target_line_idx = i
            # Extraire l'indentation
            indent = line[: len(line) - len(line.lstrip())]
            break

    if target_line_idx is None:
        print("❌ Ligne torch.load non trouvée")
        return False

    # Si ancien patch détecté, on doit supprimer tout le bloc de l'ancien patch
    lines_to_remove = 1
    if old_patch_detected:
        # Compter combien de lignes du patch sont présentes
        # L'ancien patch v3 avait ~16 lignes
        for offset in range(1, 20):
            if target_line_idx - offset < 0:
                break
            if "# PATCH FP8: Force safetensors loading" in lines[target_line_idx - offset]:
                lines_to_remove = offset + 1
                target_line_idx = target_line_idx - offset
                indent = lines[target_line_idx][: len(lines[target_line_idx]) - len(lines[target_line_idx].lstrip())]
                break

    # Créer le patch complet qui force le chargement safetensors pour les fichiers .safetensors
    new_lines = [
        f"{indent}# PATCH FP8: Force safetensors loading for .safetensors files",
        f"{indent}# ComfyUI peut mal détecter les fichiers safetensors FP8 (T5 Encoder)",
        f"{indent}# et essayer de les charger avec torch.load() au lieu de safetensors",
        f"{indent}",
        f"{indent}# Convertir le chemin en string et normaliser",
        f"{indent}import os",
        f"{indent}ckpt_str = str(ckpt) if not isinstance(ckpt, str) else ckpt",
        f"{indent}ckpt_normalized = os.path.normpath(ckpt_str)",
        f"{indent}",
        f"{indent}# Résoudre les symlinks pour obtenir le fichier réel",
        f"{indent}# Important: le symlink umt5-xxl-enc-bf16.pth pointe vers .safetensors",
        f"{indent}ckpt_real = os.path.realpath(ckpt_normalized)",
        f"{indent}",
        f"{indent}# Détecter les fichiers safetensors de manière robuste",
        f"{indent}# Vérifier à la fois le chemin original ET le chemin réel (après résolution symlink)",
        f"{indent}is_safetensors = ckpt_real.endswith('.safetensors') or '.safetensors' in ckpt_real",
        f"{indent}",
        f"{indent}if is_safetensors:",
        f"{indent}    # Forcer le chargement safetensors pour les fichiers .safetensors",
        f"{indent}    import safetensors.torch",
        f"{indent}    pl_sd = safetensors.torch.load_file(ckpt, device=str(device))",
        f"{indent}else:",
        f"{indent}    # Fichier .pth classique - utiliser torch.load avec weights_only=False",
        f"{indent}    pl_sd = torch.load(ckpt, map_location=device, weights_only=False, **torch_args)",
    ]

    # Remplacer les lignes (1 ligne si non patché, tout le bloc si ancien patch)
    lines[target_line_idx : target_line_idx + lines_to_remove] = new_lines

    # Écrire le contenu modifié
    comfyui_utils.write_text("\n".join(lines))

    print("✅ Patch appliqué avec succès (v4)")
    print("   - Résolution des symlinks avec os.path.realpath()")
    print("   - Détection robuste des fichiers safetensors (normalisation chemin)")
    print("   - Force safetensors.torch.load_file() pour fichiers .safetensors")
    print("   - weights_only=True → weights_only=False pour fichiers .pth")
    print("   Raison: Compatibilité safetensors FP8 + symlinks (T5 Encoder WAN 2.2)")

    return True


if __name__ == "__main__":
    success = patch_comfyui_utils()
    sys.exit(0 if success else 1)
