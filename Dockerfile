# Dockerfile optimisé pour RunPod
# Modèles téléchargés depuis OwnCloud
FROM nvidia/cuda:12.8.1-cudnn-runtime-ubuntu22.04

# Métadonnées
LABEL maintainer="GEGM <arnaud.boy@gegmgroup.com>"
LABEL description="Comfy_Img_to_Loop pour RunPod - Modèles OwnCloud"
LABEL version="2.0.0-runpod-owncloud"
LABEL cuda.version="12.8.1"

# Variables d'environnement
ENV DEBIAN_FRONTEND=noninteractive \
    PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1 \
    CUDA_HOME=/usr/local/cuda \
    PATH=/usr/local/cuda/bin:$PATH \
    LD_LIBRARY_PATH=/usr/local/cuda/lib64:$LD_LIBRARY_PATH

# Installer Python 3.11 et dépendances système
RUN apt-get update && apt-get install -y --no-install-recommends \
    python3.11 \
    python3.11-dev \
    python3-pip \
    python3.11-venv \
    build-essential \
    cmake \
    git \
    wget \
    curl \
    rclone \
    ffmpeg \
    libavcodec-extra \
    libjpeg-dev \
    libpng-dev \
    libwebp-dev \
    net-tools \
    && rm -rf /var/lib/apt/lists/* \
    && apt-get clean

# Créer liens symboliques Python
RUN ln -sf /usr/bin/python3.11 /usr/bin/python && \
    ln -sf /usr/bin/python3.11 /usr/bin/python3

# Mettre à jour pip
RUN python -m pip install --upgrade pip setuptools wheel

# Créer les dossiers RunPod standards
RUN mkdir -p /workspace /runpod-volume

# Définir le workspace comme répertoire de travail
WORKDIR /workspace

# Copier et installer les dépendances Python
COPY requirements.txt .

# Installer PyTorch AVANT les autres dépendances
RUN pip install --upgrade --pre torch torchvision torchaudio \
    --index-url https://download.pytorch.org/whl/nightly/cu128

# Installer les dépendances de base (sans WAN pour l'instant)
RUN pip install --no-cache-dir -r requirements.txt

# Installer bitsandbytes après PyTorch
RUN pip install --upgrade bitsandbytes

# Nettoyage
RUN pip cache purge && \
    find /opt/venv -name "*.pyc" -delete && \
    find /opt/venv -name "__pycache__" -type d -exec rm -rf {} + || true

# Copier le code de l'application (SANS les modèles)
COPY --exclude=models . /workspace/

# ============================================
# Installation de ComfyUI (sans modèles)
# ============================================

# Installer ComfyUI
RUN /workspace/install-comfyui.sh

# Vérifier les dépendances critiques WAN 2.2
RUN python -c "import torch; import diffusers; import transformers; print('✅ WAN dependencies OK')" || \
    (echo "❌ Missing dependencies" && exit 1)

# Les modèles seront téléchargés depuis OwnCloud au démarrage
# Voir docker-entrypoint.sh

# ============================================

# Créer les dossiers nécessaires
RUN mkdir -p \
    /workspace/logs \
    /workspace/web_interface/uploads \
    /workspace/comfyui/ComfyUI/models/diffusion_models

# Rendre les scripts exécutables
RUN chmod +x /workspace/docker-entrypoint.sh && \
    chmod +x /workspace/scripts/download_models_from_owncloud.py

# Exposer les ports
EXPOSE 5000 8188

# Healthcheck
HEALTHCHECK --interval=30s --timeout=10s --start-period=120s --retries=3 \
    CMD curl -f http://localhost:5000/health || exit 1

# Point d'entrée
ENTRYPOINT ["/workspace/docker-entrypoint.sh"]

# Commande par défaut
CMD ["python", "scripts/run_web_interface.py"]
