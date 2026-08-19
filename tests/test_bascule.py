"""Tests de la bascule des OU Google (pré-rentrée → définitive)."""
from __future__ import annotations

import csv
import io

import pytest
from fastapi.testclient import TestClient


@pytest.fixture()
def client(tmp_db_path):
    from backend.main import app

    with TestClient(app) as c:
        yield c


@pytest.fixture()
def snap_factory(session):
    from backend.models import Snapshot

    def _creer(personne_id, annee_id, **kwargs):
        defaults = {"nom": "MARTIN", "prenom": "Jean", "classe": "31"}
        defaults.update(kwargs)
        s = Snapshot(personne_id=personne_id, annee_scolaire_id=annee_id, **defaults)
        session.add(s)
        session.commit()
        return s

    return _creer


@pytest.fixture()
def contexte(session, site_factory, annee_factory, personne_factory, snap_factory):
    """Un site, une année, une classe en table, un élève avec snapshot."""
    from backend.models import TableCorrespondance

    site = site_factory("NDK")
    annee = annee_factory("2026-2027")
    session.add(
        TableCorrespondance(
            site_id=site.id,
            classe_charlemagne_long="TROISIEME 1",
            classe_code_court="31",
            ou_pre_rentree="/3. NDK/NDK2026",
            ou_definitive="/3. NDK/NDK2026/31",
        )
    )
    session.commit()
    p = personne_factory(
        nom="DUPONT", prenom="Jean", login="jdupont", site_id=site.id, classe="31"
    )
    snap_factory(p.id, annee.id, nom="DUPONT", prenom="Jean", classe="31")
    return {"site": site, "annee": annee, "personne": p}


# ---------------------------------------------------------------------------
# Planification
# ---------------------------------------------------------------------------


def test_phase_pre_rentree_vise_lou_dattente(session, contexte):
    from backend.services.bascule import planifier_bascule

    r = planifier_bascule(
        session, annee_id=contexte["annee"].id, phase="pre_rentree"
    )
    assert r.nb_a_deplacer == 1
    m = r.mouvements[0]
    assert m.ou_visee == "/3. NDK/NDK2026"
    assert m.ou_appliquee is None
    assert m.motif == "aucun placement enregistré"
    assert m.email == "jean.dupont@lekreisker.fr"


def test_phase_definitive_vise_lou_de_la_classe(session, contexte):
    from backend.services.bascule import planifier_bascule

    r = planifier_bascule(session, annee_id=contexte["annee"].id, phase="definitive")
    assert r.mouvements[0].ou_visee == "/3. NDK/NDK2026/31"


def test_deja_en_place_nest_pas_redeplace(session, contexte):
    """Le second passage ne repropose pas ce qui a déjà été appliqué."""
    from backend.services.bascule import enregistrer_bascule, planifier_bascule

    r1 = planifier_bascule(
        session, annee_id=contexte["annee"].id, phase="pre_rentree"
    )
    assert enregistrer_bascule(session, r1, mode="reel") == 1

    r2 = planifier_bascule(
        session, annee_id=contexte["annee"].id, phase="pre_rentree"
    )
    assert r2.nb_a_deplacer == 0
    assert r2.nb_deja_en_place == 1
    assert r2.mouvements[0].motif == "déjà placé dans cette OU"


def test_enchainement_des_deux_phases(session, contexte):
    """Pré-rentrée puis bascule : le mouvement dit d'où l'on vient."""
    from backend.services.bascule import enregistrer_bascule, planifier_bascule

    r1 = planifier_bascule(session, annee_id=contexte["annee"].id, phase="pre_rentree")
    enregistrer_bascule(session, r1, mode="reel")

    r2 = planifier_bascule(session, annee_id=contexte["annee"].id, phase="definitive")
    assert r2.nb_a_deplacer == 1
    m = r2.mouvements[0]
    assert m.ou_appliquee == "/3. NDK/NDK2026"
    assert m.ou_visee == "/3. NDK/NDK2026/31"
    assert "depuis /3. NDK/NDK2026" in m.motif


def test_classe_hors_table_bloque(
    session, site_factory, annee_factory, personne_factory, snap_factory
):
    """Jamais d'OU par défaut : on s'arrête et on l'explique."""
    from backend.services.bascule import planifier_bascule

    site = site_factory("NDK")
    annee = annee_factory("2026-2027")
    p = personne_factory(nom="X", prenom="Y", login="xy", site_id=site.id)
    snap_factory(p.id, annee.id, classe="4Z")

    r = planifier_bascule(session, annee_id=annee.id, phase="definitive")
    assert r.nb_bloques == 1
    assert r.est_applicable is False
    assert "'4Z'" in r.mouvements[0].motif
    assert r.mouvements[0].ou_visee is None


def test_ou_non_renseignee_bloque(
    session, site_factory, annee_factory, personne_factory, snap_factory
):
    from backend.models import TableCorrespondance
    from backend.services.bascule import planifier_bascule

    site = site_factory("NDK")
    annee = annee_factory("2026-2027")
    session.add(
        TableCorrespondance(
            site_id=site.id, classe_charlemagne_long="T", classe_code_court="31",
            ou_pre_rentree="", ou_definitive="/3. NDK/NDK2026/31",
        )
    )
    session.commit()
    p = personne_factory(nom="X", prenom="Y", login="xy", site_id=site.id)
    snap_factory(p.id, annee.id, classe="31")

    r = planifier_bascule(session, annee_id=annee.id, phase="pre_rentree")
    assert r.nb_bloques == 1
    assert "OU de pré-rentrée non renseignée" in r.mouvements[0].motif
    # ... mais la phase définitive, elle, passe
    assert planifier_bascule(session, annee_id=annee.id, phase="definitive").nb_bloques == 0


def test_filtre_par_site(
    session, site_factory, annee_factory, personne_factory, snap_factory
):
    from backend.models import TableCorrespondance
    from backend.services.bascule import planifier_bascule

    ndk = site_factory("NDK")
    su = site_factory("SU")
    annee = annee_factory("2026-2027")
    for s in (ndk, su):
        session.add(
            TableCorrespondance(
                site_id=s.id, classe_charlemagne_long="T", classe_code_court="31",
                ou_pre_rentree=f"/{s.nom}/2026", ou_definitive=f"/{s.nom}/2026/31",
            )
        )
    session.commit()
    for i, s in enumerate((ndk, su)):
        p = personne_factory(nom=f"N{i}", prenom="P", login=f"l{i}", site_id=s.id)
        snap_factory(p.id, annee.id, classe="31")

    tous = planifier_bascule(session, annee_id=annee.id, phase="definitive")
    assert tous.nb_total == 2
    assert tous.sites == ["NDK", "SU"]

    un = planifier_bascule(session, annee_id=annee.id, phase="definitive", site_id=ndk.id)
    assert un.nb_total == 1
    assert un.sites == ["NDK"]


def test_adultes_exclus(session, contexte, personne_factory, snap_factory):
    """L'OU d'un adulte ne se déduit pas d'une classe — on ne devine pas."""
    from backend.services.bascule import planifier_bascule

    a = personne_factory(
        type="adulte", nom="PROF", prenom="Luc", login="lprof",
        site_id=contexte["site"].id,
    )
    snap_factory(a.id, contexte["annee"].id, classe=None)

    r = planifier_bascule(session, annee_id=contexte["annee"].id, phase="definitive")
    assert all(m.cle_pivot.startswith("E") for m in r.mouvements)
    assert r.nb_total == 1


def test_reingestion_ne_duplique_pas(session, contexte, snap_factory):
    from backend.services.bascule import planifier_bascule

    snap_factory(contexte["personne"].id, contexte["annee"].id, classe="31")
    r = planifier_bascule(session, annee_id=contexte["annee"].id, phase="definitive")
    assert r.nb_total == 1


def test_phase_invalide(session, contexte):
    from backend.services.bascule import planifier_bascule

    with pytest.raises(ValueError, match="phase invalide"):
        planifier_bascule(session, annee_id=contexte["annee"].id, phase="plus_tard")


def test_annee_introuvable(session):
    from backend.services.bascule import planifier_bascule

    with pytest.raises(ValueError, match="introuvable"):
        planifier_bascule(session, annee_id=99999, phase="definitive")


# ---------------------------------------------------------------------------
# Enregistrement
# ---------------------------------------------------------------------------


def test_simulation_nenregistre_rien(session, contexte):
    from backend.models import CompteCible
    from backend.services.bascule import enregistrer_bascule, planifier_bascule

    r = planifier_bascule(session, annee_id=contexte["annee"].id, phase="pre_rentree")
    enregistrer_bascule(session, r, mode="simulation")
    assert session.query(CompteCible).count() == 0


def test_enregistrement_cree_le_compte_absent(session, contexte):
    """Un élève amorcé sans passer par un export « nouveaux » existe pourtant."""
    from backend.models import CompteCible
    from backend.services.bascule import enregistrer_bascule, planifier_bascule

    r = planifier_bascule(session, annee_id=contexte["annee"].id, phase="pre_rentree")
    enregistrer_bascule(session, r, mode="reel")

    c = session.query(CompteCible).filter_by(cible="google").one()
    assert c.etat == "actif"
    assert c.ou_appliquee == "/3. NDK/NDK2026"
    assert c.identifiant_externe == "jean.dupont@lekreisker.fr"


# ---------------------------------------------------------------------------
# CSV
# ---------------------------------------------------------------------------


def test_csv_ne_contient_que_les_deplacements(session, contexte):
    from backend.services.bascule import (
        enregistrer_bascule,
        generer_csv_bascule,
        planifier_bascule,
    )
    from backend.services.exports_google import COLONNES_GOOGLE

    r = planifier_bascule(session, annee_id=contexte["annee"].id, phase="pre_rentree")
    contenu = generer_csv_bascule(r)
    assert contenu.startswith(b"\xef\xbb\xbf")
    rows = list(csv.DictReader(io.StringIO(contenu[3:].decode("utf-8"))))
    assert list(rows[0].keys()) == COLONNES_GOOGLE
    assert rows[0]["Email Address [Required]"] == "jean.dupont@lekreisker.fr"
    assert rows[0]["Org Unit Path [Required]"] == "/3. NDK/NDK2026"
    assert rows[0]["Password [Required]"] == ""  # mise à jour, pas création
    assert rows[0]["Employee ID"] == str(contexte["personne"].id_charlemagne)

    # Une fois appliqué, le CSV suivant est vide de lignes
    enregistrer_bascule(session, r, mode="reel")
    r2 = planifier_bascule(session, annee_id=contexte["annee"].id, phase="pre_rentree")
    rows2 = list(csv.DictReader(io.StringIO(generer_csv_bascule(r2)[3:].decode("utf-8"))))
    assert rows2 == []


# ---------------------------------------------------------------------------
# API
# ---------------------------------------------------------------------------


def test_api_planifier_et_csv(client, session, contexte):
    an = contexte["annee"].id
    r = client.get(f"/api/bascule?annee_id={an}&phase=pre_rentree")
    assert r.status_code == 200
    corps = r.json()
    assert corps["nb_a_deplacer"] == 1
    assert corps["phase_libelle"] == "placement en OU de pré-rentrée"
    assert corps["est_applicable"] is True

    r2 = client.get(f"/api/bascule/csv?annee_id={an}&phase=definitive")
    assert r2.status_code == 200
    assert "definitive" in r2.json()["nom_fichier"]


def test_api_confirmer(client, session, contexte):
    an = contexte["annee"].id
    r = client.post(
        "/api/bascule/confirmer",
        json={"annee_id": an, "phase": "pre_rentree", "mode": "reel"},
    )
    assert r.status_code == 200
    assert r.json()["nb_enregistres"] == 1

    # Idempotent : plus rien à enregistrer
    r2 = client.post(
        "/api/bascule/confirmer",
        json={"annee_id": an, "phase": "pre_rentree", "mode": "reel"},
    )
    assert r2.json()["nb_enregistres"] == 0


def test_api_confirmer_refuse_si_bloquants(
    client, session, site_factory, annee_factory, personne_factory, snap_factory
):
    site = site_factory("NDK")
    annee = annee_factory("2026-2027")
    p = personne_factory(nom="X", prenom="Y", login="xy", site_id=site.id)
    snap_factory(p.id, annee.id, classe="4Z")

    r = client.post(
        "/api/bascule/confirmer",
        json={"annee_id": annee.id, "phase": "definitive", "mode": "reel"},
    )
    assert r.status_code == 409
    assert "Table de correspondance" in r.json()["detail"]


def test_api_phase_invalide(client, contexte):
    r = client.get(f"/api/bascule?annee_id={contexte['annee'].id}&phase=nimporte")
    assert r.status_code == 400


def test_api_annee_inconnue(client):
    assert client.get("/api/bascule?annee_id=99999&phase=definitive").status_code == 404
