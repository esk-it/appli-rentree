"""Configuration de la base SQLite + sessions SQLAlchemy.

Mode synchrone choisi pour la simplicité — pour un single-user et ~1700 élèves
× 5 années de snapshots, c'est largement suffisant. On reverra pour de l'async
le jour où ce sera utile.

Localisation du fichier .db :
- En dev : `<projet>/data/appli_rentree.db`
- En prod (frozen PyInstaller) : `%APPDATA%/appli-rentree/appli_rentree.db`

Voir backend/config.py pour la résolution exacte.
"""
from __future__ import annotations

from contextlib import contextmanager
from typing import Iterator

from sqlalchemy import create_engine
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker

from backend.config import CHEMIN_DB


class Base(DeclarativeBase):
    """Base déclarative partagée par tous les modèles."""

    pass


_engine = create_engine(
    f"sqlite:///{CHEMIN_DB}",
    echo=False,
    future=True,
    connect_args={"check_same_thread": False},  # sinon FastAPI râle en multi-thread
)

_SessionLocal = sessionmaker(
    bind=_engine,
    autocommit=False,
    autoflush=False,
    future=True,
)


def init_db() -> None:
    """Crée les tables manquantes au démarrage de l'app.

    SQLAlchemy ne touche pas aux tables existantes (DDL idempotent).
    Pour des migrations plus complexes plus tard, on passera à Alembic.
    """
    # Imports nécessaires pour que les modèles s'enregistrent dans Base.metadata
    from backend.models import (  # noqa: F401
        adulte_snapshot,
        annee_scolaire,
        eleve_snapshot,
        etablissement,
        parametre,
    )

    Base.metadata.create_all(bind=_engine)


@contextmanager
def get_session() -> Iterator[Session]:
    """Context manager pour usage hors-endpoints (tests, scripts)."""
    session = _SessionLocal()
    try:
        yield session
    finally:
        session.close()


def db_session() -> Iterator[Session]:
    """Dépendance FastAPI — injecte une session ouverte le temps d'un endpoint."""
    session = _SessionLocal()
    try:
        yield session
    finally:
        session.close()
