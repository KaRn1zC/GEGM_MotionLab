# 🤖 Guide des Modèles - Comfy_Img_to_Loop

## Modèles principaux

### WAN 2.2 14B (Image-to-Video)
- **Usage**: Génération de cinemagraphs à partir d'images
- **Taille**: 28.4 GB
- **VRAM**: 24GB+ requis
- **Résolutions**: 480p, 720p, 1080p
- **Durée max**: 10 secondes

### Pyramid Flow SD3 768p
- **Usage**: Upscaling et amélioration de qualité vidéo
- **Taille**: 2.8 GB  
- **VRAM**: 8GB+ requis
- **Fonction**: 384p/480p → 768p

## Custom Nodes requis

### ComfyUI-WanVideoWrapper
- **Repository**: https://github.com/kijai/ComfyUI-WanVideoWrapper
- **Fonction**: Interface WAN 2.2 dans ComfyUI
- **Dépendances**: torch>=2.0, transformers>=4.30

### ComfyUI-PyramidFlowWrapper  
- **Repository**: https://github.com/kijai/ComfyUI-PyramidFlowWrapper
- **Fonction**: Interface Pyramid Flow dans ComfyUI
- **Auto-download**: Oui

## Configuration GPU recommandée

| GPU | VRAM | Résolution max | Performance |
|-----|------|----------------|-------------|
| RTX 4090 | 24GB | 720p | Bonne |
| RTX 6000 Ada | 48GB | 1080p | Excellente |
| A100 | 80GB | 1080p+ | Optimale |
| H100 | 80GB | 1080p+ | Optimale |
