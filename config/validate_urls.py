#!/usr/bin/env python3
"""
Script de validation adapté pour la stratégie native ComfyUI + huggingface-cli
"""

import requests
import yaml
from pathlib import Path
from loguru import logger
import subprocess
from typing import Dict, List, Tuple

def load_model_config(config_path: str = "config/model_versions.yaml") -> Dict:
    """Charge la configuration des modèles"""
    try:
        with open(config_path, 'r') as f:
            return yaml.safe_load(f)
    except Exception as e:
        logger.error(f"Erreur configuration: {e}")
        return {}

def validate_repository_url(repo_url: str) -> Tuple[bool, str]:
    """Valide un repository Git"""
    try:
        if repo_url.endswith('.git'):
            web_url = repo_url[:-4]
        else:
            web_url = repo_url
            
        response = requests.get(web_url, timeout=10)
        
        if response.status_code == 200:
            return True, "Repository valide"
        else:
            return False, f"HTTP {response.status_code}"
            
    except Exception as e:
        return False, str(e)

def validate_huggingface_repo(repo_id: str) -> Tuple[bool, str]:
    """Valide un repository HuggingFace"""
    try:
        url = f"https://huggingface.co/{repo_id}"
        response = requests.get(url, timeout=10)
        
        if response.status_code == 200:
            return True, "Repository HF accessible"
        else:
            return False, f"HTTP {response.status_code}"
    except Exception as e:
        return False, str(e)

def check_huggingface_cli() -> Tuple[bool, str]:
    """Vérifie que huggingface-cli est installé"""
    try:
        result = subprocess.run(['huggingface-cli', '--help'], 
                              capture_output=True, text=True, timeout=10)
        if result.returncode == 0:
            return True, "CLI installé"
        else:
            return False, "CLI non fonctionnel"
    except FileNotFoundError:
        return False, "CLI non installé"
    except Exception as e:
        return False, str(e)

def main():
    """Fonction principale de validation adaptée"""
    print("🔍 Validation ComfyUI Native + HuggingFace - Comfy_Img_to_Loop")
    print("=" * 65)
    
    config = load_model_config()
    if not config:
        return 1
    
    # 1. Vérifier huggingface-cli
    print("\n🤗 Validation HuggingFace CLI...")
    hf_ok, hf_msg = check_huggingface_cli()
    hf_icon = "✅" if hf_ok else "❌"
    print(f"{hf_icon} HuggingFace CLI: {hf_msg}")
    
    if not hf_ok:
        print("💡 Installation: pip install 'huggingface_hub[cli]'")
    
    # 2. Valider les repositories HuggingFace
    models = config.get('models', {})
    if models:
        print(f"\n🤖 Validation de {len(models)} repositories HuggingFace...")
        hf_results = []
        
        for model_name, model_info in models.items():
            repo = model_info.get('repository', '')
            if repo:
                print(f"🔍 {model_name}: {repo}")
                is_valid, info = validate_huggingface_repo(repo)
                hf_results.append((model_name, is_valid, info))
    
    # 3. Valider les custom nodes
    custom_nodes = config.get('custom_nodes', {})
    print(f"\n🔌 Validation de {len(custom_nodes)} custom nodes...")
    
    node_results = []
    for node_name, node_info in custom_nodes.items():
        repo_url = node_info.get('repository', '')
        if repo_url:
            print(f"🔍 {node_name}: {repo_url}")
            is_valid, info = validate_repository_url(repo_url)
            node_results.append((node_name, is_valid, info))
    
    # Résumé
    print("\n" + "=" * 65)
    print("📊 RÉSUMÉ DE LA VALIDATION")
    print("=" * 65)
    
    # CLI HuggingFace
    print(f"\n🤗 HUGGINGFACE CLI:")
    print(f"{hf_icon} {hf_msg}")
    
    # Repositories HF
    if models:
        print(f"\n🤖 REPOSITORIES HUGGINGFACE:")
        valid_hf = 0
        for name, is_valid, info in hf_results:
            icon = "✅" if is_valid else "❌"
            print(f"{icon} {name:25} | {info}")
            if is_valid:
                valid_hf += 1
        print(f"   📈 Score HF: {valid_hf}/{len(hf_results)}")
    
    # Custom nodes
    print(f"\n🔌 CUSTOM NODES:")
    valid_nodes = 0
    for name, is_valid, info in node_results:
        icon = "✅" if is_valid else "❌"
        print(f"{icon} {name:25} | {info}")
        if is_valid:
            valid_nodes += 1
    print(f"   �� Score nodes: {valid_nodes}/{len(node_results)}")
    
    # Score global et recommandations
    total_valid = (1 if hf_ok else 0) + valid_nodes + (valid_hf if models else 0)
    total_items = 1 + len(node_results) + (len(hf_results) if models else 0)
    
    print(f"\n🎯 SCORE GLOBAL: {total_valid}/{total_items}")
    
    # Recommandations
    print("\n💡 PROCHAINES ÉTAPES:")
    if not hf_ok:
        print("1. ❌ Installer huggingface-cli: pip install 'huggingface_hub[cli]'")
    else:
        print("1. ✅ HuggingFace CLI prêt")
    
    if valid_nodes >= len(node_results) - 1:  # Au moins 2/3 nodes OK
        print("2. ✅ Custom nodes accessibles")
    else:
        print("2. ⚠️  Vérifier les custom nodes manquants")
    
    if total_valid >= total_items - 1:
        print("3. 🚀 PRÊT ! Exécuter: ./scripts/setup_wan22_native.sh")
        return 0
    else:
        print("3. ⚠️  Corriger les problèmes avant setup")
        return 1

if __name__ == "__main__":
    import sys
    sys.exit(main())
