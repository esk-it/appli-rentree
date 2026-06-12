"""Configuration partagée pour pytest.

Fixtures :
- `tmp_db_path` : crée un fichier SQLite temporaire isolé par test
- `session` : ouvre une session SQLAlchemy sur cette DB temporaire
- `eleve_factory` : helper pour créer un EleveSnapshot rapidement
- `etablissement_factory` : helper pour créer un Etablissement
- `annee_factory` : helper pour créer une AnneeScolaire
"""
from __future__ import annotations

import os
from collections.abc import Iterator

import pytest


@pytest.fixture()
def tmp_db_path(tmp_path, monkeypatch) -> str:
    """Isole chaque test sur sa propre DB SQLite (jamais de pollution croisée)."""
    db_file = tmp_path / "test.db"
    monkeypatch.setenv("APPLI_RENTREE_DATA_DIR", str(tmp_path))
    # On force aussi sys.frozen pour que la config aille chercher l'env
    # Note : on ne touche pas sys.frozen mais on importe config après pour
    # qu'il lise APPLI_RENTREE_DATA_DIR — mais en réalité config.py lit ça
    # uniquement si frozen. Trick : monkeypatch sys.frozen avant import.
    monkeypatch.setattr("sys.frozen", True, raising=False)

    # Force re-import de config et database avec la nouvelle DB
    import importlib

    import backend.config
    importlib.reload(backend.config)
    import backend.database
    importlib.reload(backend.database)
    # Réimporte les modèles pour qu'ils s'enregistrent contre la nouvelle Base
    import backend.models
    importlib.reload(backend.models)
    import backend.models.etablissement as m_etab
    importlib.reload(m_etab)
    import backend.models.annee_scolaire as m_annee
    importlib.reload(m_annee)
    import backend.models.eleve_snapshot as m_eleve
    importlib.reload(m_eleve)
    import backend.models.adulte_snapshot as m_adulte
    importlib.reload(m_adulte)
    import backend.models.parametre as m_param
    importlib.reload(m_param)
    import backend.models.generation as m_gen
    importlib.reload(m_gen)
    import backend.models.chambre as m_chambre
    importlib.reload(m_chambre)

    backend.database.init_db()
    yield str(db_file)


@pytest.fixture()
def session(tmp_db_path) -> Iterator:
    from backend.database import get_session

    with get_session() as s:
        yield s


@pytest.fixture()
def etablissement_factory(session):
    """Factory pour créer rapidement un Etablissement."""
    from backend.models import Etablissement

    compteur = {"n": 0}

    def _creer(
        code_charlemagne: str = "02-COL",
        code_court: str = "SU",
        nom_long: str = "Collège Sainte-Ursule",
        type: str = "college",
    ):
        compteur["n"] += 1
        e = Etablissement(
            code_charlemagne=code_charlemagne,
            code_court=code_court,
            nom_long=nom_long,
            type=type,
        )
        session.add(e)
        session.commit()
        return e

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
def eleve_factory(session):
    from backend.models import EleveSnapshot

    compteur = {"n": 0}

    # Sentinel pour distinguer "non spécifié" de "explicitement None"
    _NON_SPECIFIE = object()

    def _creer(
        annee_id: int,
        etablissement_id: int,
        nom: str | None = None,
        prenom: str | None = None,
        num_badge=_NON_SPECIFIE,
        code_classe: str | None = "31",
        code_niveau: str | None = "3EMES",
        code_regime: str | None = "D",
        est_nouveau_charlemagne: bool = False,
    ):
        compteur["n"] += 1
        # Si num_badge n'est pas passé, on en génère un. Si None est passé, on
        # respecte (pour tester le fallback nom+prenom).
        badge = (
            10000 + compteur["n"]
            if num_badge is _NON_SPECIFIE
            else num_badge
        )
        e = EleveSnapshot(
            annee_scolaire_id=annee_id,
            etablissement_id=etablissement_id,
            nom=nom or f"NOM{compteur['n']:03d}",
            prenom=prenom or f"Prenom{compteur['n']:03d}",
            num_badge=badge,
            code_classe=code_classe,
            code_niveau=code_niveau,
            code_regime=code_regime,
            est_nouveau_charlemagne=est_nouveau_charlemagne,
        )
        session.add(e)
        session.commit()
        return e

    return _creer
