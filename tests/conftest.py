"""Configuration partagée pour pytest.

Depuis la refonte identité (v0.22.0), les fixtures créent des `Site`,
`Personne`, `Snapshot`, `CompteCible` sur une DB temporaire isolée.
"""
from __future__ import annotations

from collections.abc import Iterator

import pytest


@pytest.fixture()
def tmp_db_path(tmp_path, monkeypatch) -> str:
    """Isole chaque test sur sa propre DB SQLite (jamais de pollution croisée)."""
    monkeypatch.setenv("APPLI_RENTREE_DATA_DIR", str(tmp_path))
    monkeypatch.setattr("sys.frozen", True, raising=False)

    # Force re-import de config et database avec la nouvelle DB
    import importlib
    import sys

    import backend.config
    importlib.reload(backend.config)
    import backend.database
    importlib.reload(backend.database)
    # La nouvelle Base peut contenir des Tables héritées d'une session pytest
    # précédente (les modèles restent référencés depuis sys.modules). On la
    # vide avant de redéclarer, sinon `class X(Base)` explose avec
    # "Table already defined for this MetaData".
    backend.database.Base.metadata.clear()

    # Purge les services et modèles du cache d'imports — ainsi, quand un test
    # importe `backend.services.X`, python réexécute son code contre la
    # nouvelle Base au lieu de servir la version cachée branchée sur
    # l'ancienne. Sans cela, `backend.services.reconciliation` (importé la
    # 1re fois avant le reload) reste attaché à l'ancienne AnneeScolaire.
    for nom in list(sys.modules):
        if nom.startswith("backend.models.") or nom.startswith("backend.services.") or nom == "backend.models":
            del sys.modules[nom]

    # Réimporte les modèles pour qu'ils s'enregistrent contre la nouvelle Base
    import backend.models  # noqa: F401 — forces re-import chain

    backend.database.init_db()
    yield str(tmp_path / "appli_rentree.db")


@pytest.fixture()
def session(tmp_db_path) -> Iterator:
    from backend.database import get_session

    with get_session() as s:
        yield s


@pytest.fixture()
def site_factory(session):
    """Factory pour créer un Site."""
    from backend.models import Site

    compteur = {"n": 0}
    defauts = {
        "NDE": ("Notre-Dame d'Espérance", "ndecleder.fr", "NDE", 2),
        "NDK": ("Notre-Dame du Kreisker", "lekreisker.fr", "NDK", 3),
        "SU": ("Sainte-Ursule", "lekreisker.fr", "SU", 4),
    }

    def _creer(nom: str = "NDK", **overrides):
        compteur["n"] += 1
        d = defauts.get(nom, ("Test", "test.fr", nom, 10 + compteur["n"]))
        s = Site(
            nom=nom,
            nom_complet=overrides.get("nom_complet", d[0]),
            domaine_mail=overrides.get("domaine_mail", d[1]),
            prefixe_annee_ou=overrides.get("prefixe_annee_ou", d[2]),
            numero_ordre=overrides.get("numero_ordre", d[3]),
        )
        session.add(s)
        session.commit()
        return s

    return _creer


@pytest.fixture()
def annee_factory(session):
    from backend.models import AnneeScolaire

    def _creer(libelle: str = "2025-2026"):
        a = AnneeScolaire(libelle=libelle, est_active=True)
        session.add(a)
        session.commit()
        return a

    return _creer


@pytest.fixture()
def personne_factory(session):
    """Factory pour créer une Personne (avec badge auto-calculé)."""
    from backend.models import Personne

    compteur = {"eleve": 0, "adulte": 0}

    def _creer(
        type: str = "eleve",
        id_charlemagne: int | None = None,
        nom: str | None = None,
        prenom: str | None = None,
        login: str | None = None,
        site_id: int | None = None,
        **kwargs,
    ):
        compteur[type] += 1
        if id_charlemagne is None:
            id_charlemagne = 5000 + compteur[type] if type == "eleve" else 100 + compteur[type]
        badge = Personne.calculer_badge(type, id_charlemagne)
        if nom is None:
            nom = f"NOM{compteur[type]:03d}"
        if prenom is None:
            prenom = f"Prenom{compteur[type]:03d}"
        if login is None:
            login = f"{prenom[0].lower()}{nom.lower()}"[:10]
        p = Personne(
            type=type,
            id_charlemagne=id_charlemagne,
            badge=badge,
            login=login,
            nom=nom,
            prenom=prenom,
            site_id=site_id,
            **kwargs,
        )
        session.add(p)
        session.commit()
        return p

    return _creer
