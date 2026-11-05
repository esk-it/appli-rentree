"""L'état du référentiel : de quand date ce que le programme sait.

L'écran « Mettre à jour le référentiel » (5 novembre 2026) l'affiche avant
tout import : un élève arrivé depuis le dernier export n'existe encore ni
aux cartes, ni chez Sodexo, ni pour Google.
"""
from __future__ import annotations

from datetime import datetime

import pytest


@pytest.fixture()
def client(tmp_db_path):
    from fastapi.testclient import TestClient

    from backend.main import app

    with TestClient(app) as c:
        yield c


def test_sans_annee_rien_a_dire(client):
    r = client.get("/api/ingestion/etat").json()
    assert r == {"annee_id": None, "annee": None, "populations": []}


def test_la_date_du_dernier_export_par_population(client):
    from backend.database import _SessionLocal
    from backend.models import AnneeScolaire, Personne, Snapshot

    s = _SessionLocal()
    vieille = AnneeScolaire(libelle="2025-2026")
    an = AnneeScolaire(libelle="2026-2027")
    s.add_all([vieille, an]); s.flush()
    for i, (type_, jour) in enumerate([("eleve", 12), ("eleve", 5), ("adulte", 1)], 1):
        p = Personne(type=type_, id_charlemagne=90000 + i, badge=Personne.calculer_badge(type_, 90000 + i),
                     login=f"essai{i}", nom="FICTIF", prenom=f"P{i}")
        s.add(p); s.flush()
        s.add(Snapshot(personne_id=p.id, annee_scolaire_id=an.id, nom=p.nom, prenom=p.prenom,
                       date_ingestion=datetime(2026, 10, jour, 9)))
    # Une ingestion de l'an passé ne date pas l'année en cours.
    s.add(Snapshot(personne_id=p.id, annee_scolaire_id=vieille.id, nom=p.nom, prenom=p.prenom,
                   date_ingestion=datetime(2026, 10, 30, 9)))
    s.commit(); s.close()

    r = client.get("/api/ingestion/etat").json()
    assert r["annee"] == "2026-2027"
    assert r["populations"] == [
        {"type_personne": "eleve", "inscrits": 2, "dernier_export": "2026-10-12"},
        {"type_personne": "adulte", "inscrits": 1, "dernier_export": "2026-10-01"},
    ]
