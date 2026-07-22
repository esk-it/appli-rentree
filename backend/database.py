"""Configuration de la base SQLite + sessions SQLAlchemy.

Mode synchrone choisi pour la simplicité — pour un single-user et ~1700
personnes × 5 années de snapshots, c'est largement suffisant.

Localisation du fichier .db :
- En dev : `<projet>/data/appli_rentree.db`
- En prod (frozen PyInstaller) : `%APPDATA%/appli-rentree/appli_rentree.db`

Voir backend/config.py pour la résolution exacte.

## Reset de schéma

Depuis la refonte identité (v0.22.0), le schéma est incompatible avec les
anciens `EleveSnapshot` / `AdulteSnapshot` / `Chambre`. Au démarrage, si
la base contient une trace d'une ancienne version, on **wipe complet et
recrée**. C'est une décision explicite (pas de compatibilité rétrograde).
"""
from __future__ import annotations

from contextlib import contextmanager
from typing import Iterator

from sqlalchemy import create_engine, inspect, text
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker

from backend.config import CHEMIN_DB


class Base(DeclarativeBase):
    """Base déclarative partagée par tous les modèles."""

    pass


_engine = create_engine(
    f"sqlite:///{CHEMIN_DB}",
    echo=False,
    future=True,
    connect_args={"check_same_thread": False},
)

_SessionLocal = sessionmaker(
    bind=_engine,
    autocommit=False,
    autoflush=False,
    future=True,
)


# Tables du schéma pré-v0.22 qui n'existent plus. Leur présence dans la
# base courante déclenche un wipe complet.
_TABLES_ANCIEN_SCHEMA = {
    "eleve_snapshot",
    "adulte_snapshot",
    "chambre",
    "affectation_chambre",
}


def _detecter_ancien_schema() -> set[str]:
    """Retourne l'ensemble des tables obsolètes présentes en base."""
    try:
        inspector = inspect(_engine)
        existantes = set(inspector.get_table_names())
    except Exception:
        return set()
    return existantes & _TABLES_ANCIEN_SCHEMA


def _wipe_complet() -> None:
    """Supprime toutes les tables — SQLAlchemy et pré-v0.22."""
    # Import des modèles pour peupler Base.metadata avant le drop
    from backend.models import (  # noqa: F401
        annee_scolaire,
        arbitrage,
        compte_cible,
        etablissement,
        generation,
        parametre,
        personne,
        site,
        snapshot,
        table_correspondance,
    )
    Base.metadata.drop_all(bind=_engine)
    # Puis les anciennes tables non gérées par Base
    with _engine.begin() as conn:
        for t in _TABLES_ANCIEN_SCHEMA:
            conn.execute(text(f"DROP TABLE IF EXISTS {t}"))


def init_db() -> None:
    """Crée les tables manquantes au démarrage. Wipe complet si vieux schéma détecté."""
    # Imports pour enregistrer les modèles dans Base.metadata
    from backend.models import (  # noqa: F401
        annee_scolaire,
        arbitrage,
        compte_cible,
        etablissement,
        generation,
        parametre,
        personne,
        site,
        snapshot,
        table_correspondance,
    )

    tables_obsoletes = _detecter_ancien_schema()
    if tables_obsoletes:
        print(
            f"[DB] Schéma pré-v0.22 détecté (tables obsolètes : {sorted(tables_obsoletes)}). "
            "Reset complet."
        )
        _wipe_complet()

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
