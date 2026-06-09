"""Configuration globale du backend.

Centralise les chemins et constantes. Quand l'app est packagée (PyInstaller),
les données et la base SQLite sont stockées dans %APPDATA%/appli-rentree.
En développement, elles vont dans le dossier `data/` à côté du code.
"""
from __future__ import annotations

import os
import sys
from pathlib import Path


def _racine_donnees() -> Path:
    """Détermine où stocker la base SQLite et les fichiers utilisateur.

    - En mode "frozen" (PyInstaller / Tauri sidecar) → `%APPDATA%/appli-rentree`
    - En dev → `<projet>/data`
    """
    if getattr(sys, "frozen", False):
        # Forcé par run_backend.py au démarrage
        if env := os.environ.get("APPLI_RENTREE_DATA_DIR"):
            return Path(env)
        appdata = Path(os.environ.get("APPDATA", str(Path.home())))
        return appdata / "appli-rentree"
    # En dev : à la racine du projet
    return Path(__file__).resolve().parent.parent / "data"


RACINE_DONNEES: Path = _racine_donnees()
DOSSIER_INPUT: Path = RACINE_DONNEES / "input"
DOSSIER_OUTPUT: Path = RACINE_DONNEES / "output"
CHEMIN_DB: Path = RACINE_DONNEES / "appli_rentree.db"

# Création paresseuse des dossiers
for d in (RACINE_DONNEES, DOSSIER_INPUT, DOSSIER_OUTPUT):
    d.mkdir(parents=True, exist_ok=True)

# Port d'écoute par défaut du backend
PORT_DEFAUT: int = 8020
