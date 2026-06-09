"""Application FastAPI — point d'entrée du backend.

Lancée comme sidecar par Tauri (binaire bundlé via PyInstaller), ou directement
en dev via `start_backend.ps1` / `uvicorn backend.main:app --reload --port 8020`.
"""
from __future__ import annotations

import os

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from backend.routers import import_charlemagne

app = FastAPI(
    title="Appli Rentrée — Backend",
    description=(
        "Backend de l'application de préparation de la rentrée scolaire de "
        "l'Ensemble Scolaire du Kreisker (ESK). Sert le frontend Tauri/Svelte."
    ),
    version="0.1.0",
)

# CORS : le frontend Svelte tourne sur Vite dev (5173) ou en prod via Tauri.
# En prod, le frontend est servi via le scheme tauri://, mais en dev il est
# distinct du backend, donc on ouvre largement.
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/api/health")
def health() -> dict:
    """Sonde de vie du backend (utilisée par Tauri au démarrage)."""
    return {"ok": True, "version": app.version}


@app.post("/api/shutdown")
async def shutdown() -> dict:
    """Arrêt propre — appelé par Tauri à la fermeture de l'app."""
    import threading
    import time

    def _exit() -> None:
        time.sleep(0.3)
        os._exit(0)

    threading.Thread(target=_exit, daemon=True).start()
    return {"ok": True}


# Enregistrement des routeurs métier
app.include_router(import_charlemagne.router)
