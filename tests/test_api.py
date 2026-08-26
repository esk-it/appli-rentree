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


# ---------------------------------------------------------------------------
# PATCH /api/personnes/{id}/email
# ---------------------------------------------------------------------------


def test_patch_email_fige_l_adresse(client, session, site_factory, personne_factory):
    site = site_factory("NDK")
    p = personne_factory(nom="GUILLOU", prenom="Hugo", login="hguillou", site_id=site.id)

    r = client.patch(
        f"/api/personnes/{p.id}/email",
        json={"email": "  Hugo.Guillou2@LEKREISKER.fr "},
    )
    assert r.status_code == 200
    corps = r.json()
    assert corps["email"] == "hugo.guillou2@lekreisker.fr"  # normalisée
    assert corps["email_est_constate"] is True


def test_patch_email_vide_retablit_le_calcul(
    client, session, site_factory, personne_factory
):
    site = site_factory("NDK")
    p = personne_factory(
        nom="GUILLOU", prenom="Hugo", login="hguillou", site_id=site.id,
        email_constate="autre@lekreisker.fr",
    )

    r = client.patch(f"/api/personnes/{p.id}/email", json={"email": ""})
    assert r.status_code == 200
    assert r.json()["email"] == "hugo.guillou@lekreisker.fr"
    assert r.json()["email_est_constate"] is False


def test_patch_email_refuse_une_adresse_deja_prise(
    client, session, site_factory, personne_factory
):
    site = site_factory("NDK")
    personne_factory(
        nom="GUILLOU", prenom="Hugo", login="hguillou", site_id=site.id,
        email_constate="hugo.guillou@lekreisker.fr",
    )
    p2 = personne_factory(nom="GUILLOU", prenom="Hugo", login="hguillou2", site_id=site.id)

    r = client.patch(
        f"/api/personnes/{p2.id}/email", json={"email": "hugo.guillou@lekreisker.fr"}
    )
    assert r.status_code == 409
    assert "déjà l'adresse" in r.json()["detail"]


def test_patch_email_refuse_une_adresse_malformee(
    client, session, site_factory, personne_factory
):
    site = site_factory("NDK")
    p = personne_factory(site_id=site.id, login="test1")
    assert client.patch(f"/api/personnes/{p.id}/email", json={"email": "sansarobase"}).status_code == 400


def test_patch_email_personne_inconnue(client):
    r = client.patch("/api/personnes/999999/email", json={"email": "a@b.fr"})
    assert r.status_code == 404


def test_fiche_rend_le_parcours_multi_annees(client, session, site_factory,
                                             annee_factory, personne_factory):
    """L'écran n'affichait que la classe de l'année préparée.

    Savoir d'où vient un élève — quelle classe l'an dernier — est ce qui
    permet de juger un cas douteux sans ouvrir Charlemagne à côté.
    """
    from backend.models import CompteCible, Snapshot

    site = site_factory("NDK")
    a1 = annee_factory("2025-2026")
    a2 = annee_factory("2026-2027")
    p = personne_factory(nom="ABIVEN", prenom="Maël", login="mabiven1",
                         site_id=site.id)
    session.add(Snapshot(personne_id=p.id, annee_scolaire_id=a1.id,
                         nom="ABIVEN", prenom="Maël", classe="1_G1", regime="D"))
    session.add(Snapshot(personne_id=p.id, annee_scolaire_id=a2.id,
                         nom="ABIVEN", prenom="Maël", classe="T_G1A", regime="D"))
    session.add(CompteCible(personne_id=p.id, cible="google", etat="actif",
                            ou_appliquee="/3. NDK/NDK2026/1_G1"))
    session.commit()

    d = client.get(f"/api/personnes/{p.id}/fiche").json()

    assert d["personne"]["nom"] == "ABIVEN"
    assert [(a["annee"], a["classe"]) for a in d["parcours"]] == [
        ("2026-2027", "T_G1A"),
        ("2025-2026", "1_G1"),
    ], "de la plus récente à la plus ancienne"
    assert d["parcours"][0]["regime"] == "D"
    assert d["comptes"][0]["ou_appliquee"] == "/3. NDK/NDK2026/1_G1"


def test_fiche_dune_personne_sans_annee(client, session, personne_factory):
    """Un adulte n'a pas de snapshot : la fiche le dit plutôt que d'échouer."""
    p = personne_factory(nom="DUPONT", prenom="Jean", login="jdupont")
    session.commit()

    d = client.get(f"/api/personnes/{p.id}/fiche").json()
    assert d["parcours"] == []
    assert d["comptes"] == []


def test_fiche_ne_garde_quun_snapshot_par_annee(client, session, annee_factory,
                                                personne_factory):
    """Un export rejoué crée un second snapshot : on garde le plus récent."""
    from datetime import datetime, timedelta

    from backend.models import Snapshot

    annee = annee_factory("2026-2027")
    p = personne_factory(nom="X", prenom="Y", login="xy")
    ancien = datetime.utcnow() - timedelta(days=2)
    session.add(Snapshot(personne_id=p.id, annee_scolaire_id=annee.id,
                         nom="X", prenom="Y", classe="ANCIENNE",
                         date_ingestion=ancien))
    session.add(Snapshot(personne_id=p.id, annee_scolaire_id=annee.id,
                         nom="X", prenom="Y", classe="RECENTE"))
    session.commit()

    d = client.get(f"/api/personnes/{p.id}/fiche").json()
    assert [a["classe"] for a in d["parcours"]] == ["RECENTE"]


def test_fiche_personne_inexistante(client):
    assert client.get("/api/personnes/999999/fiche").status_code == 404


def test_la_version_annoncee_suit_celle_de_lapplication():
    """Elle était écrite en dur : l'écran a annoncé 0.75.1 huit versions durant.

    Au point de faire douter du mécanisme de mise à jour, qui lui
    fonctionnait — les publications étaient bien sur GitHub.
    """
    import json
    from pathlib import Path

    from backend.main import app

    conf = json.loads(
        (Path(__file__).resolve().parent.parent / "src-tauri" / "tauri.conf.json")
        .read_text(encoding="utf-8")
    )
    assert app.version == conf["version"]
