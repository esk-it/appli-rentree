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
        login_reserve,
        parametre,
        personne,
        secret_conserve,
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


def _detecter_tables_avec_drift() -> dict[str, list[str]]:
    """Repère les tables dont le schéma réel diverge du modèle.

    Deux formes de divergence détectées :

    1. **Nullabilité** — une colonne existe des deux côtés mais avec un
       `nullable` différent (ex. `arbitrage.decision` passé de NOT NULL à
       nullable en v0.26.0).
    2. **Colonne obsolète bloquante** — une colonne NOT NULL sans valeur
       par défaut existe en base mais plus dans le modèle. `create_all`
       ne la supprime jamais, et tout INSERT échouerait puisque le modèle
       ne la renseigne plus.

    Ne gère PAS les changements de type — trop rare, et mieux vaut échouer
    bruyamment que convertir en silence.

    Retourne `{nom_table: [descriptions des drifts]}` — clef seulement si
    au moins un drift.
    """
    inspector = inspect(_engine)
    tables_reelles = set(inspector.get_table_names())
    drifts: dict[str, list[str]] = {}

    for table in Base.metadata.tables.values():
        if table.name not in tables_reelles:
            continue
        cols_reelles = {c["name"]: c for c in inspector.get_columns(table.name)}
        cols_modele = {col.name for col in table.columns}
        anomalies: list[str] = []

        for col in table.columns:
            real = cols_reelles.get(col.name)
            if real is None:
                continue  # géré par _migrer_colonnes_manquantes
            nullable_reel = bool(real.get("nullable", True))
            if nullable_reel != col.nullable:
                anomalies.append(
                    f"{col.name}: nullable modèle={col.nullable} vs base={nullable_reel}"
                )

        for nom, real in cols_reelles.items():
            if nom in cols_modele:
                continue
            bloquante = not real.get("nullable", True) and real.get("default") is None
            if bloquante:
                anomalies.append(f"{nom}: colonne obsolète NOT NULL sans défaut")

        if anomalies:
            drifts[table.name] = anomalies
    return drifts


def _table_est_vide(nom_table: str) -> bool:
    with _engine.begin() as conn:
        n = conn.execute(text(f"SELECT COUNT(*) FROM {nom_table}")).scalar_one()
    return int(n or 0) == 0


def _recreer_tables_vides_avec_drift() -> list[str]:
    """Drop puis re-crée les tables dont le schéma diffère du modèle actuel.

    Seulement si la table est **vide** — pour éviter toute perte de données
    non-intentionnelle. Sur une table non vide, log un warning et laisse
    l'anomalie en place ; l'utilisateur devra intervenir manuellement.

    Retourne la liste des tables effectivement recréées.
    """
    drifts = _detecter_tables_avec_drift()
    recreees: list[str] = []
    for nom_table, anomalies in drifts.items():
        if not _table_est_vide(nom_table):
            print(
                f"[DB] {nom_table} a un drift ({', '.join(anomalies)}) mais contient "
                "des données — non touchée. Wipe manuel requis pour corriger."
            )
            continue
        print(
            f"[DB] {nom_table} vide avec drift ({', '.join(anomalies)}) — DROP + recréation."
        )
        table_obj = Base.metadata.tables[nom_table]
        with _engine.begin() as conn:
            conn.execute(text(f"DROP TABLE {nom_table}"))
        # create_all limité à cette table (les autres restent intactes)
        table_obj.create(bind=_engine)
        recreees.append(nom_table)
    return recreees


def _reconstruire_login_reserve() -> bool:
    """Rebâtit `login_reserve` quand sa clé d'unicité ignore encore le site.

    La table a d'abord été unique sur `(login, badge)`. Un professeur
    existant dans les deux bases KoXo n'y tenait donc qu'une ligne : lire le
    second export écrasait le site du premier, et l'export ne retrouvait
    plus le constat de la base qu'il visait.

    SQLite ne sait pas modifier une contrainte en place. La table est
    reconstruite plutôt que migrée, ce qui est sans dommage : **c'est un
    cache**, entièrement redéduit d'un passage au Contrôle KoXo. Les
    identifiants eux-mêmes vivent sur `Personne`, et ne sont pas touchés.
    """
    inspector = inspect(_engine)
    if "login_reserve" not in set(inspector.get_table_names()):
        return False

    contraintes = inspector.get_unique_constraints("login_reserve")
    a_jour = any(
        "site" in (c.get("column_names") or []) for c in contraintes
    )
    if a_jour:
        return False

    table = Base.metadata.tables["login_reserve"]
    table.drop(bind=_engine, checkfirst=True)
    table.create(bind=_engine)
    return True


def init_db() -> None:
    """Crée les tables manquantes au démarrage.

    Quatre passes successives :
    1. Wipe complet si un schéma pré-v0.22 est détecté (tables obsolètes).
    2. `create_all()` pour les tables inexistantes.
    3. `_migrer_colonnes_manquantes` : ADD COLUMN pour les colonnes ajoutées
       depuis la dernière version (drift additif — ex. `date_decision`).
    4. `_recreer_tables_vides_avec_drift` : DROP + recréation ciblée pour les
       tables **vides** dont une colonne a changé de nullabilité (drift
       structurel — ex. `arbitrage.decision` passé de NOT NULL à nullable
       en v0.26.0).

    Sur une table non vide avec drift structurel, log un warning et laisse
    en place (l'utilisateur doit trancher).
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
    for sql in alters:
        print(f"[DB] Migration auto : {sql}")

    recreees = _recreer_tables_vides_avec_drift()
    for t in recreees:
        print(f"[DB] Table {t} recréée après drift structurel")

    if _reconstruire_login_reserve():
        print(
            "[DB] Table login_reserve reconstruite : les constats sont "
            "désormais tenus par base. Repasse tes exports KoXo au Contrôle "
            "en désignant leur site."
        )


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
