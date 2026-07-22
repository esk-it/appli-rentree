"""Tests du reset automatique de schéma pré-v0.22.

Depuis v0.22.0, si la base contient des tables de l'ancien schéma
(`eleve_snapshot`, `adulte_snapshot`, `chambre`, `affectation_chambre`),
le démarrage déclenche un wipe complet et recrée les tables du nouveau
schéma.
"""
from __future__ import annotations

import importlib

from sqlalchemy import inspect, text


def test_wipe_declenche_si_ancien_schema(tmp_db_path):
    """Simule la présence d'une table pré-v0.22 → init_db doit la supprimer."""
    import backend.database as database

    # Insère une table pré-v0.22 dans la base fraîche
    with database._engine.begin() as conn:
        conn.execute(text("CREATE TABLE eleve_snapshot (id INTEGER PRIMARY KEY, nom TEXT)"))

    assert "eleve_snapshot" in inspect(database._engine).get_table_names()

    # Simule un redémarrage : appelle init_db
    importlib.reload(database)
    database.init_db()

    tables = set(inspect(database._engine).get_table_names())
    assert "eleve_snapshot" not in tables, "table pré-v0.22 doit être supprimée"
    # Les nouvelles tables sont présentes
    assert {"personne", "snapshot", "compte_cible", "arbitrage", "site", "table_correspondance"}.issubset(tables)


def test_init_db_est_idempotent(tmp_db_path, session):
    """Appeler init_db deux fois ne casse rien."""
    from backend.database import init_db
    from backend.models import Site

    site = Site(
        nom="TEST",
        nom_complet="Test",
        domaine_mail="test.fr",
        prefixe_annee_ou="TEST",
        numero_ordre=99,
    )
    session.add(site)
    session.commit()
    site_id = site.id

    # Second init_db — ne doit rien casser
    init_db()

    # La donnée est toujours là
    from backend.database import get_session
    with get_session() as s:
        s2 = s.query(Site).filter_by(id=site_id).one()
        assert s2.nom == "TEST"


def test_nouveau_schema_a_toutes_les_tables_attendues(tmp_db_path):
    """Vérifie que toutes les nouvelles tables sont bien créées."""
    import backend.database as database

    tables = set(inspect(database._engine).get_table_names())
    attendues = {
        # Nouvelles tables du Lot 1
        "personne",
        "snapshot",
        "compte_cible",
        "arbitrage",
        "site",
        "table_correspondance",
        # Conservées (§2 du prompt)
        "annee_scolaire",
        "etablissement",
        "generation",
        "parametre",
    }
    manquantes = attendues - tables
    assert not manquantes, f"Tables manquantes : {manquantes}"
