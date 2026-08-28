"""Créer les groupes Google manquants — le geste qui débloque une classe.

Une adresse de groupe déclarée dans la Table mais absente de Google fait
échouer les ajouts un par un, sans que rien ne l'annonce. L'écran de
conformité propose donc de créer ce qui manque.

Le bouton renvoyait une erreur 500 : l'opération construite pour le suivi
n'avait pas d'`action`, et le job échouait avant même d'appeler Google.
Aucun test ne passait par cet endpoint — celui-ci le fait.
"""
from __future__ import annotations

import pytest
from fastapi.testclient import TestClient


@pytest.fixture()
def client(tmp_db_path):
    from backend.main import app

    with TestClient(app) as c:
        yield c


class _ClientFactice:
    """Un Google qui accepte tout et retient ce qu'on lui a demandé."""

    def __init__(self):
        self.crees: list[tuple[str, str, str]] = []

    def creer_groupe(self, adresse, nom, description=""):
        self.crees.append((adresse, nom, description))


@pytest.fixture()
def google_factice(monkeypatch):
    """Remplace le diff et le client : aucun appel réseau."""
    from dataclasses import dataclass, field

    from backend.services.groupes_google import GroupeACreer

    faux = _ClientFactice()

    @dataclass
    class _Rapport:
        diffs: list = field(default_factory=list)
        nb_retenus: int = 0
        groupes_absents: list = field(default_factory=list)

    def _faux_diff(session, annee_id, site_id):
        return faux, _Rapport()

    def _faux_a_creer(session, rapport):
        return [
            GroupeACreer(
                adresse="6eme-bleue@lekreisker.fr",
                nom="6e bleue",
                description="Classe de 6e bleue",
                classe="6B", site="NDK", nb_membres_attendus=24,
            ),
            GroupeACreer(
                adresse="6eme-verte@lekreisker.fr",
                nom="6e verte",
                description="",
                classe="6V", site="NDK", nb_membres_attendus=0,
            ),
        ]

    monkeypatch.setattr("backend.routers.google_api._diff_groupes", _faux_diff)
    monkeypatch.setattr(
        "backend.services.groupes_google.groupes_a_creer", _faux_a_creer
    )
    return faux


def _attendre(job_id, tours=200):
    """Le job tourne dans un thread : on attend qu'il ait fini."""
    import time

    from backend.services.jobs_google import obtenir_job

    for _ in range(tours):
        job = obtenir_job(job_id)
        if job is not None and job.est_termine:
            return job
        time.sleep(0.01)
    raise AssertionError("le job ne s'est pas terminé")


def test_creer_les_groupes_manquants_aboutit(client, google_factice):
    """Le cas réel : dix-huit groupes à créer, et un 500 à la place."""
    r = client.post("/api/google/groupes/creer", json={
        "annee_id": 1, "confirmation": True,
    })
    assert r.status_code == 200, r.text
    job = r.json()
    assert job["total"] == 2

    fini = _attendre(job["id"])
    assert fini.nb_reussies == 2, fini
    assert [c[0] for c in google_factice.crees] == [
        "6eme-bleue@lekreisker.fr", "6eme-verte@lekreisker.fr",
    ]


def test_chaque_etape_porte_son_action(client, google_factice):
    """C'est l'attribut manquant qui faisait tomber l'endpoint."""
    r = client.post("/api/google/groupes/creer", json={
        "annee_id": 1, "confirmation": True,
    })
    assert r.status_code == 200, r.text
    for etape in r.json()["etapes"]:
        assert etape["action"] == "creer_groupe"


def test_seulement_utiles_ecarte_les_classes_sans_effectif(
    client, google_factice
):
    """Une classe sans élève cette année n'a pas besoin de sa liste."""
    r = client.post("/api/google/groupes/creer", json={
        "annee_id": 1, "confirmation": True, "seulement_utiles": True,
    })
    assert r.status_code == 200, r.text
    assert r.json()["total"] == 1

    _attendre(r.json()["id"])
    assert [c[0] for c in google_factice.crees] == ["6eme-bleue@lekreisker.fr"]


def test_sans_confirmation_rien_nest_cree(client, google_factice):
    r = client.post("/api/google/groupes/creer", json={"annee_id": 1})
    assert r.status_code == 400
    assert google_factice.crees == []
