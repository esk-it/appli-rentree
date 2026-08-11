"""Application FastAPI — point d'entrée du backend.

Lancée comme sidecar par Tauri (binaire bundlé via PyInstaller), ou directement
en dev via `start_backend.ps1` / `uvicorn backend.main:app --reload --port 8020`.
"""
from __future__ import annotations

import logging
import os
import traceback
from contextlib import asynccontextmanager
from logging.handlers import RotatingFileHandler

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from backend.config import RACINE_DONNEES
from backend.database import init_db
from backend.routers import (
    amorcage,
    annees,
    arbitrages,
    etablissements,
    exports,
    ingestion,
    logins,
    parametres,
    personnes,
    reconciliation,
    simulation,
    sites,
    table_correspondance,
)


# ---------------------------------------------------------------------------
# Logging fichier — indispensable pour diagnostiquer le sidecar en prod (pas
# de console visible). Le fichier est écrit à côté de la base SQLite.
# ---------------------------------------------------------------------------

CHEMIN_LOG = RACINE_DONNEES / "backend.log"


def _configurer_logs() -> logging.Logger:
    logger = logging.getLogger("appli_rentree")
    if logger.handlers:  # déjà configuré (tests, reload)
        return logger
    logger.setLevel(logging.INFO)

    formatteur = logging.Formatter(
        "%(asctime)s [%(levelname)s] %(name)s: %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )

    # Fichier avec rotation (5 x 500 Ko)
    try:
        handler_fichier = RotatingFileHandler(
            CHEMIN_LOG, maxBytes=500_000, backupCount=5, encoding="utf-8"
        )
        handler_fichier.setFormatter(formatteur)
        logger.addHandler(handler_fichier)
    except OSError:
        pass  # si le fichier est verrouillé, on tombe juste sur la console

    # Console (utile en dev + visible dans Tauri console si l'utilisateur en a une)
    handler_console = logging.StreamHandler()
    handler_console.setFormatter(formatteur)
    logger.addHandler(handler_console)

    return logger


log = _configurer_logs()


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Hook de démarrage / arrêt FastAPI."""
    log.info("Démarrage backend v%s — data dir = %s", app.version, RACINE_DONNEES)
    init_db()
    log.info("init_db OK — prêt à servir")
    yield
    log.info("Arrêt backend")


app = FastAPI(
    title="Appli Rentrée — Backend",
    description=(
        "Backend de l'application de préparation de la rentrée scolaire de "
        "l'Ensemble Scolaire du Kreisker (ESK). Sert le frontend Tauri/Svelte."
    ),
    version="0.32.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ---------------------------------------------------------------------------
# Middlewares de trace : chaque requête entrante est loggée, et toute
# exception non catchée par un endpoint est capturée avec stack trace.
# ---------------------------------------------------------------------------


@app.middleware("http")
async def middleware_trace(request: Request, call_next):
    """Trace les requêtes + capture les exceptions non gérées."""
    try:
        log.info("→ %s %s", request.method, request.url.path)
        response = await call_next(request)
        log.info("← %s %s [%d]", request.method, request.url.path, response.status_code)
        return response
    except Exception as e:
        tb = traceback.format_exc()
        log.error(
            "✗ %s %s a levé une exception : %s\n%s",
            request.method,
            request.url.path,
            e,
            tb,
        )
        log.info("← %s %s [500]", request.method, request.url.path)
        return JSONResponse(
            status_code=500,
            content={"detail": f"Erreur interne : {type(e).__name__}: {e}"},
        )


@app.get("/api/health")
def health() -> dict:
    """Sonde de vie du backend (utilisée par Tauri au démarrage)."""
    return {"ok": True, "version": app.version}


@app.get("/api/logs")
def dernieres_logs(n: int = 200) -> dict:
    """Retourne les N dernières lignes du fichier backend.log.

    Utile en debug quand aucune console n'est visible côté utilisateur.
    Accessible aussi directement dans le navigateur : http://127.0.0.1:8020/api/logs
    """
    n = max(1, min(n, 2000))
    if not CHEMIN_LOG.exists():
        return {"lignes": [], "chemin": str(CHEMIN_LOG), "avertissement": "pas encore de log"}
    try:
        with open(CHEMIN_LOG, encoding="utf-8", errors="replace") as f:
            lignes = f.readlines()
    except OSError as e:
        return {"lignes": [], "erreur": str(e)}
    return {"chemin": str(CHEMIN_LOG), "lignes": [l.rstrip() for l in lignes[-n:]]}


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


# Routeurs métier — Lot 1 : identité + config
app.include_router(personnes.router)
app.include_router(sites.router)
app.include_router(table_correspondance.router)
app.include_router(annees.router)
app.include_router(etablissements.router)
app.include_router(parametres.router)
app.include_router(logins.router)
app.include_router(ingestion.router)
app.include_router(reconciliation.router)
app.include_router(arbitrages.router)
app.include_router(amorcage.router)
app.include_router(exports.router)
app.include_router(simulation.router)
