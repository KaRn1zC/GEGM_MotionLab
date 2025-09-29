"""
Module principal Comfy_Img_to_Loop
Système de génération de cinemagraphs avec WAN 2.2
"""

from .logger import get_logger, setup_logger, auto_configure

# Version du projet
__version__ = "1.0.0"
__author__ = "Comfy_Img_to_Loop Team"
__description__ = "Générateur de cinemagraphs professionnel avec ComfyUI et WAN 2.2"

# Configuration automatique du logger au import
logger = auto_configure()

__all__ = ["get_logger", "setup_logger", "auto_configure", "logger"]
