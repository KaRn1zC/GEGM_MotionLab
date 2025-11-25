#!/usr/bin/env python3
"""
Convertit le VAE WAN 96 canaux → 48 canaux compatible ComfyUI
À exécuter AVANT l'upload sur OwnCloud OU après téléchargement sur Pod
"""

import torch
import os
import sys


def convert_vae_96_to_48ch(model_dir=None, model_name="wan2.2-ti2v-5b"):
    """Convertit le VAE d'un modèle WAN de 96ch à 48ch"""

    # Support pour chemin absolu (Pod) ou relatif (local)
    if model_dir is None:
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
        print("   📥 Chargement VAE...")
        vae_state = torch.load(vae_source, map_location="cpu", weights_only=False)

        # Vérifier si déjà converti (check encoder.conv_in.weight)
        if "encoder.conv_in.weight" in vae_state:
            conv_in_shape = vae_state["encoder.conv_in.weight"].shape
            if conv_in_shape[0] == 48:  # Déjà converti
                print(f"   ✅ VAE déjà converti en 48ch (shape={list(conv_in_shape)})")
                return True

        channels_reduced = 0
        for key in list(vae_state.keys()):
            param = vae_state[key]

            # Réduire TOUTES les couches avec 96 canaux en sortie (shape[0])
            # Ceci inclut encoder.conv_in, decoder.conv_out, etc.
            if param.dim() >= 2 and param.shape[0] == 96:
                vae_state[key] = param[:48, ...]
                channels_reduced += 1
                print(f"   🔧 Réduit {key}: {list(param.shape)} → {list(vae_state[key].shape)}")

            # Réduire couches avec 96 canaux en entrée (shape[1] pour conv)
            elif param.dim() >= 2 and param.shape[1] == 96:
                vae_state[key] = param[:, :48, ...]
                channels_reduced += 1
                print(f"   🔧 Réduit {key}: {list(param.shape)} → {list(vae_state[key].shape)}")

        if channels_reduced == 0:
            print("   ⚠️  Aucune couche 96ch détectée (peut-être déjà converti)")
            return True

        # Sauvegarder le VAE converti temporairement
        print(f"   💾 Sauvegarde VAE 48ch ({channels_reduced} couches modifiées)...")
        torch.save(vae_state, vae_temp)

        # Remplacer l'original
        os.replace(vae_temp, vae_source)

        print(f"   ✅ VAE converti: {channels_reduced} couches réduites 96ch → 48ch")
        print(f"   ✅ {vae_source} (48ch) - prêt pour usage")
        return True

    except Exception as e:
        print(f"   ❌ Erreur conversion: {e}")
        import traceback
        traceback.print_exc()
        if os.path.exists(vae_temp):
            os.remove(vae_temp)
        return False


if __name__ == "__main__":
    if len(sys.argv) > 2:
        # Mode Pod: python convert_vae_channels.py <model_dir> <model_name>
        model_dir = sys.argv[1]
        model_name = sys.argv[2]
        success = convert_vae_96_to_48ch(model_dir, model_name)
    elif len(sys.argv) > 1:
        # Mode local: python convert_vae_channels.py <model_name>
        model_name = sys.argv[1]
        success = convert_vae_96_to_48ch(model_name=model_name)
    else:
        # Défaut
        success = convert_vae_96_to_48ch()

    sys.exit(0 if success else 1)
