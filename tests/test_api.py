"""Tests d'intégration via FastAPI TestClient."""
from __future__ import annotations

import pytest
from fastapi.testclient import TestClient


@pytest.fixture()
def client(tmp_db_path):
    """Client FastAPI sur la DB temporaire."""
    # Re-import après que tmp_db_path ait reload la DB
    import importlib
    import backend.main

    importlib.reload(backend.main)
    return TestClient(backend.main.app)


class TestHealthEtBase:
    def test_health(self, client):
        r = client.get("/api/health")
        assert r.status_code == 200
        assert r.json() == {"ok": True, "version": client.app.version}

    def test_annees_vide_au_demarrage(self, client):
        r = client.get("/api/annees")
        assert r.status_code == 200
        assert r.json() == []

    def test_etablissements_vide_au_demarrage(self, client):
        r = client.get("/api/etablissements")
        assert r.status_code == 200
        assert r.json() == []


class TestParametres:
    def test_lister_renvoie_les_defauts(self, client):
        r = client.get("/api/parametres")
        assert r.status_code == 200
        liste = r.json()
        cles = {p["cle"] for p in liste}
        assert "email.domaine" in cles
        # Valeur par défaut
        email = next(p for p in liste if p["cle"] == "email.domaine")
        assert email["valeur"] == "lekreisker.fr"

    def test_mettre_a_jour_change_la_valeur(self, client):
        r = client.put(
            "/api/parametres/email.domaine",
            json={"valeur": "nouveau-domaine.fr"},
        )
        assert r.status_code == 200
        # Vérifie
        liste = client.get("/api/parametres").json()
        email = next(p for p in liste if p["cle"] == "email.domaine")
        assert email["valeur"] == "nouveau-domaine.fr"

    def test_parametre_inconnu_renvoie_404(self, client):
        r = client.put(
            "/api/parametres/inconnu", json={"valeur": "x"}
        )
        assert r.status_code == 404


class TestRecherche:
    def test_terme_vide_renvoie_422(self, client):
        # min_length=1 → FastAPI lève 422
        r = client.get("/api/recherche?q=")
        assert r.status_code == 422

    def test_aucun_resultat_renvoie_listes_vides(self, client):
        r = client.get("/api/recherche?q=INEXISTANT")
        assert r.status_code == 200
        body = r.json()
        assert body["nb_eleves"] == 0
        assert body["nb_adultes"] == 0
