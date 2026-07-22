"""Tests d'intégration via FastAPI TestClient (Lot 1 + 2)."""
from __future__ import annotations

import pytest
from fastapi.testclient import TestClient


@pytest.fixture()
def client(tmp_db_path):
    """Client FastAPI sur la DB temporaire — pas de reload de backend.main
    pour éviter les duplications SQLAlchemy (les modèles sont déjà rechargés
    par le fixture tmp_db_path)."""
    from backend.main import app

    with TestClient(app) as c:
        yield c


class TestHealth:
    def test_version_courante(self, client):
        r = client.get("/api/health")
        assert r.status_code == 200
        assert r.json()["ok"] is True
        assert r.json()["version"].startswith("0.")


class TestRacine:
    """Les collections de base sont accessibles et vides au démarrage."""

    def test_sites_vide(self, client):
        r = client.get("/api/sites")
        assert r.status_code == 200
        assert r.json() == []

    def test_personnes_vide(self, client):
        r = client.get("/api/personnes")
        assert r.status_code == 200
        assert r.json() == []

    def test_table_correspondance_vide(self, client):
        r = client.get("/api/table-correspondance")
        assert r.status_code == 200
        assert r.json() == []

    def test_annees_vide(self, client):
        r = client.get("/api/annees")
        assert r.status_code == 200
        assert r.json() == []


class TestSitesCRUD:
    def test_creer_lister_modifier_supprimer(self, client):
        # Créer
        payload = {
            "nom": "NDE",
            "nom_complet": "Notre-Dame d'Espérance",
            "domaine_mail": "ndecleder.fr",
            "prefixe_annee_ou": "NDE",
            "numero_ordre": 2,
        }
        r = client.post("/api/sites", json=payload)
        assert r.status_code == 200
        site_id = r.json()["id"]
        assert r.json()["prefixe_racine_ou"] == "/2. NDE"

        # Lister
        r = client.get("/api/sites")
        assert len(r.json()) == 1
        assert r.json()[0]["domaine_mail"] == "ndecleder.fr"

        # Doublon interdit
        r2 = client.post("/api/sites", json=payload)
        assert r2.status_code == 409

        # Modifier
        r = client.put(
            f"/api/sites/{site_id}",
            json={**payload, "nom_complet": "NDE modifié"},
        )
        assert r.status_code == 200
        assert r.json()["nom_complet"] == "NDE modifié"

        # Supprimer
        r = client.delete(f"/api/sites/{site_id}")
        assert r.status_code == 200

        r = client.get("/api/sites")
        assert r.json() == []


class TestTableCorrespondance:
    def test_bloque_si_site_inconnu(self, client):
        r = client.post(
            "/api/table-correspondance",
            json={
                "site_id": 999,
                "classe_charlemagne_long": "TROISIEME FUSHIA",
                "classe_code_court": "3F",
                "ou_pre_rentree": "/2. NDE/NDE2026",
                "ou_definitive": "/2. NDE/NDE2026/3F",
            },
        )
        assert r.status_code == 400

    def test_creation_normale(self, client):
        # Crée un site d'abord
        site = client.post(
            "/api/sites",
            json={
                "nom": "NDE",
                "nom_complet": "NDE",
                "domaine_mail": "ndecleder.fr",
                "prefixe_annee_ou": "NDE",
                "numero_ordre": 2,
            },
        ).json()

        r = client.post(
            "/api/table-correspondance",
            json={
                "site_id": site["id"],
                "classe_charlemagne_long": "TROISIEME FUSHIA",
                "classe_code_court": "3F",
                "groupe_google": "3eme-fuschia@ndecleder.fr",
                "ou_pre_rentree": "/2. NDE/NDE2026",
                "ou_definitive": "/2. NDE/NDE2026/3F",
            },
        )
        assert r.status_code == 200
        assert r.json()["site_nom"] == "NDE"

    def test_doublon_bloque(self, client):
        site = client.post(
            "/api/sites",
            json={
                "nom": "NDE",
                "nom_complet": "NDE",
                "domaine_mail": "ndecleder.fr",
                "prefixe_annee_ou": "NDE",
                "numero_ordre": 2,
            },
        ).json()
        payload = {
            "site_id": site["id"],
            "classe_charlemagne_long": "TROISIEME FUSHIA",
            "classe_code_court": "3F",
            "ou_pre_rentree": "/2. NDE/NDE2026",
            "ou_definitive": "/2. NDE/NDE2026/3F",
        }
        client.post("/api/table-correspondance", json=payload)
        r = client.post("/api/table-correspondance", json=payload)
        assert r.status_code == 409


class TestPersonnes:
    def test_cle_pivot_invalide(self, client):
        r = client.get("/api/personnes/par-cle-pivot/X999")
        assert r.status_code == 400

    def test_cle_pivot_non_numerique(self, client):
        r = client.get("/api/personnes/par-cle-pivot/Eabc")
        assert r.status_code == 400

    def test_cle_pivot_introuvable(self, client):
        r = client.get("/api/personnes/par-cle-pivot/E9999")
        assert r.status_code == 404


class TestParametres:
    def test_lister_renvoie_les_defauts(self, client):
        r = client.get("/api/parametres")
        assert r.status_code == 200
        liste = r.json()
        assert len(liste) > 0
        cles = {p["cle"] for p in liste}
        assert "email.domaine" in cles
