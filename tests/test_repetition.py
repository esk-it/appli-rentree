"""La répétition : la rentrée jouée sur une copie de la base, Google en lecture seule.

Demandé par Johann le 15 octobre 2026 : « attendre le 01/07/2027 pour
pouvoir essayer c'est chaud ». Ce qui compte ici, c'est ce qui ne doit
jamais arriver : écrire dans la vraie base, ou dans Google.
"""
from __future__ import annotations

import pytest


@pytest.fixture()
def base(tmp_db_path):
    from backend.database import init_db
    from backend.services import repetition

    init_db()
    yield
    repetition.jeter()


def _sites() -> list[str]:
    from backend import database
    from backend.models import Site

    s = database._SessionLocal()
    try:
        return sorted(x.nom for x in s.query(Site))
    finally:
        s.close()


def _ajouter_site(nom: str) -> None:
    from backend import database
    from backend.models import Site

    s = database._SessionLocal()
    try:
        s.add(Site(nom=nom, nom_complet=nom, domaine_mail="essai.fr", prefixe_annee_ou=nom,
                   numero_ordre=len(_sites()) + 1))
        s.commit()
    finally:
        s.close()


def test_la_repetition_travaille_sur_une_copie(base):
    from backend.services import repetition

    _ajouter_site("NDK")
    e = repetition.commencer()
    assert e.active and e.copie_existe and e.copiee_le
    _ajouter_site("SU")
    assert _sites() == ["NDK", "SU"]

    repetition.quitter()
    assert _sites() == ["NDK"], "la vraie base n'a pas bougé"

    repetition.commencer()
    assert _sites() == ["NDK", "SU"], "la copie se reprend où on l'a laissée"
    repetition.commencer(neuve=True)
    assert _sites() == ["NDK"], "une copie neuve repart de la vraie base"

    repetition.jeter()
    assert not repetition.est_active() and not repetition.etat().copie_existe
    assert _sites() == ["NDK"]


def test_google_n_est_que_lu_pendant_la_repetition(base):
    from googleapiclient.http import HttpMockSequence, HttpRequest

    from backend.services import repetition

    def requete(methode):
        http = HttpMockSequence([({"status": "200"}, "{}")])
        return HttpRequest(http, lambda reponse, contenu: contenu,
                           "https://admin.googleapis.com/admin/directory/v1/users",
                           method=methode)

    assert requete("POST").execute() is not None, "hors répétition, rien n'est bloqué"
    repetition.commencer()
    assert requete("GET").execute() is not None, "les lectures passent"
    for methode in ("POST", "PUT", "PATCH", "DELETE"):
        with pytest.raises(repetition.EcritureGoogleEnRepetition, match="rien n'est envoyé"):
            requete(methode).execute()


def test_la_rentree_se_commence_sans_attendre_en_repetition(base):
    from fastapi.testclient import TestClient

    from backend.main import app

    with TestClient(app) as client:
        assert client.post("/api/rentree/commencer", json={"libelle": "2099-2100"}).status_code == 400

        assert client.post("/api/repetition/commencer", json={}).json()["active"]
        e = client.get("/api/rentree/etat", params={"annee": "2099-2100"}).json()
        assert e["repetition"] and not e["trop_tot"]
        e = client.post("/api/rentree/commencer", json={"libelle": "2099-2100"}).json()
        assert e["commencee"] and e["courante"] == "mise_en_place"

        assert not client.post("/api/repetition/quitter", json={}).json()["active"]
        e = client.get("/api/rentree/etat", params={"annee": "2099-2100"}).json()
        assert not e["commencee"] and e["trop_tot"], "la vraie base n'a pas de campagne"
