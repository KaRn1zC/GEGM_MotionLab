#!/usr/bin/env python3
"""
Convertit le VAE WAN 96 canaux → 48 canaux compatible ComfyUI
À exécuter AVANT l'upload sur OwnCloud
"""

import torch
import os
import sys


def convert_vae_96_to_48ch(model_name="wan2.2-ti2v-5b"):
    """Convertit le VAE d'un modèle WAN de 96ch à 48ch"""

    model_dir = f"models/{model_name}"
    vae_source = os.path.join(model_dir, "Wan2.2_VAE.pth")
    vae_temp = os.path.join(model_dir, "Wan2.2_VAE_48ch_temp.pth")

    print(f"\n🔄 Conversion VAE {model_name}: 96ch → 48ch")
    print(f"   Source: {vae_source}")

    # Vérifier que le fichier source existe
    if not os.path.exists(vae_source):
        print(f"   ❌ VAE source non trouvé: {vae_source}")
        return False

    try:
        print("   📥 Chargement VAE 96ch...")
        vae_state = torch.load(vae_source, map_location="cpu")

        channels_reduced = 0
        for key in list(vae_state.keys()):
            param = vae_state[key]

            # Réduire couches encoder (96 en entrée)
            if "encoder" in key and ("weight" in key or "bias" in key):
                if param.dim() >= 2 and param.shape[-1] == 96:
                    vae_state[key] = param[..., :48]
                    channels_reduced += 1

            # Réduire couches decoder (96 en sortie)
            if "decoder" in key and "weight" in key:
                if param.dim() >= 2 and param.shape[0] == 96:
                    vae_state[key] = param[:48, ...]
                    channels_reduced += 1

        # Sauvegarder le VAE converti temporairement
        print("   💾 Sauvegarde VAE 48ch (temp)...")
        torch.save(vae_state, vae_temp)

        # Remplacer l'original
        os.replace(vae_temp, vae_source)

        print(f"   ✅ VAE converti ({channels_reduced} couches réduites)")
        print(f"   ✅ {vae_source} (48ch) - prêt pour upload")
        return True

    except Exception as e:
        print(f"   ❌ Erreur conversion: {e}")
        if os.path.exists(vae_temp):
            os.remove(vae_temp)
        return False


if __name__ == "__main__":
    model = sys.argv[1] if len(sys.argv) > 1 else "wan2.2-ti2v-5b"
    success = convert_vae_96_to_48ch(model)
    sys.exit(0 if success else 1)
