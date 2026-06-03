"""
Module principal GEGM MotionLab
Système de génération de cinemagraphs avec WAN 2.2
"""

from .logger import get_logger, setup_logger, auto_configure

# Version du projet
__version__ = "1.0.0"
__author__ = "GEGM MotionLab Team"
__description__ = "Générateur de cinemagraphs professionnel avec ComfyUI et WAN 2.2"

# Pas d'auto-configuration à l'import pour éviter les effets de bord
# (psutil, torch, etc.). La configuration se fait explicitement via
# setup_logger() dans app.py ou les scripts qui en ont besoin.
# get_logger() initialise le logger paresseusement au premier appel.
logger = None

__all__ = ["get_logger", "setup_logger", "auto_configure", "logger"]
