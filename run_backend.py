"""Point d'entrée pour PyInstaller.

Ce fichier est l'entrée du bundle PyInstaller car `backend/main.py` utilise
des imports relatifs qui ne fonctionnent pas en script direct.

Quand il est figé (frozen), il stocke les données dans %APPDATA% au lieu du
dossier de l'exécutable (qui est en lecture seule sur l'installation NSIS).
"""
from __future__ import annotations

import os
import sys
from pathlib import Path

# Quand frozen, on force le dossier de données dans %APPDATA%.
# La config (backend.config) lit cette variable d'environnement.
if getattr(sys, "frozen", False):
    appdata = Path(os.environ.get("APPDATA", str(Path.home())))
    racine = appdata / "appli-rentree"
    racine.mkdir(parents=True, exist_ok=True)
    os.environ["APPLI_RENTREE_DATA_DIR"] = str(racine)

import uvicorn  # noqa: E402

from backend.main import app  # noqa: E402
from backend.config import PORT_DEFAUT  # noqa: E402


def main() -> None:
    port = PORT_DEFAUT
    # Le sidecar Tauri peut passer un port via --port
    for i, arg in enumerate(sys.argv[1:], 1):
        if arg == "--port" and i < len(sys.argv) - 1:
            port = int(sys.argv[i + 1])
        elif arg.startswith("--port="):
            port = int(arg.split("=", 1)[1])
    uvicorn.run(app, host="127.0.0.1", port=port, log_level="info")


if __name__ == "__main__":
    main()
