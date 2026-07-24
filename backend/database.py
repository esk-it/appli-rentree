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


def _migrer_colonnes_manquantes() -> list[str]:
    """Ajoute automatiquement les colonnes manquantes aux tables existantes.

    Cible le drift entre le modèle courant et une base créée par une version
    antérieure. Uniquement des `ALTER TABLE ADD COLUMN` sur des colonnes
    nullable ou avec DEFAULT constant (contrainte SQLite pour ADD COLUMN
    sans downtime).

    Ne touche pas aux colonnes retirées ni aux types changés — pour ça, un
    wipe reste nécessaire. Retourne la liste des ALTER effectivement joués.
    """
    inspector = inspect(_engine)
    tables_reelles = set(inspector.get_table_names())
    alters_effectues: list[str] = []

    for table in Base.metadata.tables.values():
        if table.name not in tables_reelles:
            continue  # sera créée par create_all
        cols_reelles = {c["name"] for c in inspector.get_columns(table.name)}
        for col in table.columns:
            if col.name in cols_reelles:
                continue

            col_type_sql = col.type.compile(dialect=_engine.dialect)
            clauses = [col.name, col_type_sql]

            has_default = col.default is not None and getattr(col.default, "arg", None) is not None
            constant_default = (
                has_default and not callable(col.default.arg)
            )

            if not col.nullable:
                if not constant_default:
                    # ADD COLUMN NOT NULL sans DEFAULT constant → impossible en SQLite
                    # sur table non vide. On skippe et on log — l'utilisateur devra
                    # wiper manuellement si sa table contient des rows.
                    print(
                        f"[DB] Impossible d'ajouter {table.name}.{col.name} "
                        "(NOT NULL sans DEFAULT constant) — skip"
                    )
                    continue
                clauses.append("NOT NULL")

            if constant_default:
                v = col.default.arg
                if isinstance(v, bool):
                    clauses.append(f"DEFAULT {1 if v else 0}")
                elif isinstance(v, (int, float)):
                    clauses.append(f"DEFAULT {v}")
                else:
                    clauses.append(f"DEFAULT '{str(v).replace(chr(39), chr(39)*2)}'")

            sql = f"ALTER TABLE {table.name} ADD COLUMN {' '.join(clauses)}"
            with _engine.begin() as conn:
                conn.execute(text(sql))
            alters_effectues.append(sql)

    return alters_effectues


def init_db() -> None:
    """Crée les tables manquantes au démarrage.

    Trois passes successives :
    1. Wipe complet si un schéma pré-v0.22 est détecté (tables obsolètes).
    2. `create_all()` pour les tables inexistantes.
    3. Migration légère : ajoute les colonnes manquantes aux tables existantes
       (drift entre le modèle courant et une base créée par une version
       antérieure — ex. `arbitrage.date_decision` ajoutée en v0.26.0).
    """
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

    alters = _migrer_colonnes_manquantes()
    if alters:
        for sql in alters:
            print(f"[DB] Migration auto : {sql}")


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
