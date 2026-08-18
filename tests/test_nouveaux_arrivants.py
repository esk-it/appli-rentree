"""Tests de la liste des nouveaux arrivants."""
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


def _lire_csv(contenu: bytes) -> list[dict]:
    if contenu.startswith(b"\xef\xbb\xbf"):
        contenu = contenu[3:]
    return list(csv.DictReader(io.StringIO(contenu.decode("utf-8")), delimiter=";"))


# ---------------------------------------------------------------------------
# Classement
# ---------------------------------------------------------------------------


def test_signaux_concordants_donnent_nouveau(
    session, site_factory, annee_factory, personne_factory, snap_factory
):
    """Ni compte, ni classe l'an dernier : nouvel arrivant net."""
    from backend.services.nouveaux_arrivants import lister_nouveaux_arrivants

    site = site_factory("NDK")
    annee = annee_factory("2026-2027")
    p = personne_factory(nom="LE GALL", prenom="Maël", login="mlegall", site_id=site.id)
    snap_factory(p.id, annee.id, nom="LE GALL", prenom="Maël", classe="61",
                 classe_precedente=None)

    r = lister_nouveaux_arrivants(session, annee_id=annee.id)
    assert r.nb_total == 1
    assert r.nb_nouveaux == 1
    a = r.arrivants[0]
    assert a.statut == "nouveau"
    assert a.classe == "61"
    assert a.login == "mlegall"
    assert a.email == "mael.le.gall@lekreisker.fr"


def test_eleve_qui_poursuit_avec_compte_est_absent(
    session, site_factory, annee_factory, personne_factory, snap_factory
):
    from backend.services.nouveaux_arrivants import lister_nouveaux_arrivants

    site = site_factory("NDK")
    annee = annee_factory("2026-2027")
    p = personne_factory(
        nom="DANIELOU", prenom="Ambre", login="adanielou", site_id=site.id,
        email_constate="ambre.danielou@lekreisker.fr",
    )
    snap_factory(p.id, annee.id, classe="32", classe_precedente="31")

    r = lister_nouveaux_arrivants(session, annee_id=annee.id)
    assert r.nb_total == 0


def test_sans_compte_mais_avec_classe_precedente_est_a_verifier(
    session, site_factory, annee_factory, personne_factory, snap_factory
):
    """Cas réel : Anna KERVELLA, 2_2 → 1_G3, sans adresse."""
    from backend.services.nouveaux_arrivants import lister_nouveaux_arrivants

    site = site_factory("NDK")
    annee = annee_factory("2026-2027")
    p = personne_factory(nom="KERVELLA", prenom="Anna", login="akervella", site_id=site.id)
    snap_factory(p.id, annee.id, classe="1_G3", classe_precedente="2_2")

    r = lister_nouveaux_arrivants(session, annee_id=annee.id)
    assert r.nb_a_verifier == 1
    a = r.arrivants[0]
    assert a.statut == "a_verifier"
    assert "2_2" in a.motif


def test_avec_compte_mais_sans_classe_precedente_est_a_verifier(
    session, site_factory, annee_factory, personne_factory, snap_factory
):
    """Cas réel : Lyana LE JEUNE, compte existant, aucune classe l'an dernier."""
    from backend.services.nouveaux_arrivants import lister_nouveaux_arrivants

    site = site_factory("NDK")
    annee = annee_factory("2026-2027")
    p = personne_factory(
        nom="LE JEUNE", prenom="Lyana", login="llejeune", site_id=site.id,
        email_constate="lyana.lejeune@lekreisker.fr",
    )
    snap_factory(p.id, annee.id, classe="54", classe_precedente=None)

    r = lister_nouveaux_arrivants(session, annee_id=annee.id)
    assert r.nb_a_verifier == 1
    assert r.arrivants[0].statut == "a_verifier"
    # L'adresse constatée est conservée, pas recalculée
    assert r.arrivants[0].email == "lyana.lejeune@lekreisker.fr"


def test_exclure_les_a_verifier(
    session, site_factory, annee_factory, personne_factory, snap_factory
):
    from backend.services.nouveaux_arrivants import lister_nouveaux_arrivants

    site = site_factory("NDK")
    annee = annee_factory("2026-2027")
    net = personne_factory(nom="NEUF", prenom="Jean", login="jneuf", site_id=site.id)
    snap_factory(net.id, annee.id, nom="NEUF", classe="61", classe_precedente=None)
    douteux = personne_factory(nom="KERVELLA", prenom="Anna", login="akervella", site_id=site.id)
    snap_factory(douteux.id, annee.id, nom="KERVELLA", classe="1_G3", classe_precedente="2_2")

    r = lister_nouveaux_arrivants(session, annee_id=annee.id, inclure_a_verifier=False)
    assert r.nb_total == 1
    assert r.arrivants[0].nom == "NEUF"


def test_annee_source_tranche_quand_elle_existe(
    session, site_factory, annee_factory, personne_factory, snap_factory
):
    """Avec une année de référence, la présence l'an dernier fait foi.

    Un élève sans compte mais déjà présent l'an dernier n'est pas un
    arrivant : c'est un compte à créer, mais pas une entrée à valider.
    """
    from backend.services.nouveaux_arrivants import lister_nouveaux_arrivants

    site = site_factory("NDK")
    prec = annee_factory("2025-2026")
    cour = annee_factory("2026-2027")

    ancien = personne_factory(nom="KERVELLA", prenom="Anna", login="akervella", site_id=site.id)
    snap_factory(ancien.id, prec.id, nom="KERVELLA", classe="2_2")
    snap_factory(ancien.id, cour.id, nom="KERVELLA", classe="1_G3", classe_precedente="2_2")

    entrant = personne_factory(nom="NEUF", prenom="Jean", login="jneuf", site_id=site.id)
    snap_factory(entrant.id, cour.id, nom="NEUF", classe="61", classe_precedente=None)

    r = lister_nouveaux_arrivants(
        session, annee_id=cour.id, annee_source_id=prec.id
    )
    assert r.annee_source_libelle == "2025-2026"
    assert r.nb_total == 1
    assert r.arrivants[0].nom == "NEUF"


def test_reingestion_ne_duplique_pas_la_ligne(
    session, site_factory, annee_factory, personne_factory, snap_factory
):
    """Deux snapshots la même année : une seule ligne sur la liste imprimée."""
    from backend.services.nouveaux_arrivants import lister_nouveaux_arrivants

    site = site_factory("NDK")
    annee = annee_factory("2026-2027")
    p = personne_factory(nom="NEUF", prenom="Jean", login="jneuf", site_id=site.id)
    snap_factory(p.id, annee.id, classe="61", classe_precedente=None)
    snap_factory(p.id, annee.id, classe="62", classe_precedente=None)

    r = lister_nouveaux_arrivants(session, annee_id=annee.id)
    assert r.nb_total == 1


def test_filtres_site_et_type(
    session, site_factory, annee_factory, personne_factory, snap_factory
):
    from backend.services.nouveaux_arrivants import lister_nouveaux_arrivants

    ndk = site_factory("NDK")
    su = site_factory("SU")
    annee = annee_factory("2026-2027")

    a = personne_factory(nom="A", prenom="Jean", login="ja", site_id=ndk.id)
    snap_factory(a.id, annee.id, classe="61", classe_precedente=None)
    b = personne_factory(nom="B", prenom="Marie", login="mb", site_id=su.id)
    snap_factory(b.id, annee.id, classe="61", classe_precedente=None)
    c = personne_factory(type="adulte", nom="C", prenom="Luc", login="lc", site_id=ndk.id)
    snap_factory(c.id, annee.id, classe=None, classe_precedente=None)

    assert lister_nouveaux_arrivants(session, annee_id=annee.id).nb_total == 3
    assert lister_nouveaux_arrivants(session, annee_id=annee.id, site_id=ndk.id).nb_total == 2
    r = lister_nouveaux_arrivants(session, annee_id=annee.id, type_personne="eleve")
    assert r.nb_total == 2


def test_annee_introuvable(session):
    from backend.services.nouveaux_arrivants import lister_nouveaux_arrivants

    with pytest.raises(ValueError, match="introuvable"):
        lister_nouveaux_arrivants(session, annee_id=99999)


# ---------------------------------------------------------------------------
# CSV
# ---------------------------------------------------------------------------


def test_csv_lisible_par_excel(
    session, site_factory, annee_factory, personne_factory, snap_factory
):
    """Point-virgule + BOM : Excel FR ouvre en colonnes, accents intacts."""
    from backend.services.nouveaux_arrivants import (
        generer_csv_nouveaux,
        lister_nouveaux_arrivants,
    )

    site = site_factory("NDK")
    annee = annee_factory("2026-2027")
    p = personne_factory(nom="LE GALL", prenom="Maël", login="mlegall", site_id=site.id)
    snap_factory(p.id, annee.id, nom="LE GALL", prenom="Maël", classe="61",
                 regime="D", classe_precedente=None)

    contenu = generer_csv_nouveaux(lister_nouveaux_arrivants(session, annee_id=annee.id))
    assert contenu.startswith(b"\xef\xbb\xbf")

    rows = _lire_csv(contenu)
    assert len(rows) == 1
    r = rows[0]
    assert r["Prénom"] == "Maël"
    assert r["Nom"] == "LE GALL"
    assert r["Classe"] == "61"
    assert r["Régime"] == "D"
    assert r["Identifiant"] == "mlegall"
    assert r["Adresse mail"] == "mael.le.gall@lekreisker.fr"
    assert r["Statut"] == "Nouveau"


def test_csv_vide_garde_ses_entetes(session, annee_factory):
    from backend.services.nouveaux_arrivants import (
        COLONNES_CSV,
        generer_csv_nouveaux,
        lister_nouveaux_arrivants,
    )

    annee = annee_factory("2026-2027")
    contenu = generer_csv_nouveaux(lister_nouveaux_arrivants(session, annee_id=annee.id))
    rows = _lire_csv(contenu)
    assert rows == []
    assert COLONNES_CSV[0].encode("utf-8") in contenu


# ---------------------------------------------------------------------------
# API
# ---------------------------------------------------------------------------


def test_api_liste_et_csv(
    client, session, site_factory, annee_factory, personne_factory, snap_factory
):
    import base64

    site = site_factory("NDK")
    annee = annee_factory("2026-2027")
    p = personne_factory(nom="NEUF", prenom="Jean", login="jneuf", site_id=site.id)
    snap_factory(p.id, annee.id, classe="61", classe_precedente=None)

    r = client.get(f"/api/nouveaux?annee_id={annee.id}")
    assert r.status_code == 200
    corps = r.json()
    assert corps["nb_nouveaux"] == 1
    assert corps["arrivants"][0]["login"] == "jneuf"

    r2 = client.get(f"/api/nouveaux/csv?annee_id={annee.id}")
    assert r2.status_code == 200
    assert r2.json()["nom_fichier"] == "Nouveaux_arrivants_2026-2027.csv"
    contenu = base64.b64decode(r2.json()["contenu_base64"])
    assert b"jneuf" in contenu


def test_api_annee_inconnue(client):
    assert client.get("/api/nouveaux?annee_id=99999").status_code == 404


def test_api_type_invalide(client, annee_factory):
    annee = annee_factory("2026-2027")
    r = client.get(f"/api/nouveaux?annee_id={annee.id}&type=chien")
    assert r.status_code == 400
