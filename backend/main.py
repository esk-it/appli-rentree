"""Application FastAPI — point d'entrée du backend.

Lancée comme sidecar par Tauri (binaire bundlé via PyInstaller), ou directement
en dev via `start_backend.ps1` / `uvicorn backend.main:app --reload --port 8020`.
"""
from __future__ import annotations

import os
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from backend.database import init_db
from backend.routers import annees, comparaison, etablissements, exports, import_charlemagne


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Hook de démarrage / arrêt FastAPI.

    Au démarrage : crée les tables SQLite manquantes (idempotent).
    """
    init_db()
    yield


app = FastAPI(
    title="Appli Rentrée — Backend",
    description=(
        "Backend de l'application de préparation de la rentrée scolaire de "
        "l'Ensemble Scolaire du Kreisker (ESK). Sert le frontend Tauri/Svelte."
    ),
    version="0.8.0",
    lifespan=lifespan,
)

# CORS : en dev le frontend Svelte tourne sur Vite (5173), en prod il est servi
# par Tauri via le scheme tauri://. Dans tous les cas, le backend tourne sur
# 127.0.0.1:8020 et n'est pas exposé sur le réseau, donc on ouvre largement.
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


# Routeurs métier
app.include_router(import_charlemagne.router)
app.include_router(annees.router)
app.include_router(etablissements.router)
app.include_router(comparaison.router)
app.include_router(exports.router)
