"""Où en est la rentrée — l'état de chaque étape du parcours.

Le rail montrait l'ordre des quinze étapes sans jamais dire où l'on en
était : cinq seulement portaient un état, toute la partie Google restait
muette. C'est là qu'on se perd, parce qu'une rentrée se travaille sur
plusieurs jours en fermant l'application entre deux.
"""
from __future__ import annotations

import pytest

from backend.services.parcours import A_FAIRE, FAITE, INCONNU


@pytest.fixture()
def snap_factory(session):
    from backend.models import Snapshot

    def _creer(personne_id, annee_id, classe=None):
        s = Snapshot(personne_id=personne_id, annee_scolaire_id=annee_id,
                     nom="X", prenom="Y", classe=classe)
        session.add(s)
        session.commit()
        return s

    return _creer


@pytest.fixture()
def tc_factory(session):
    from backend.models import TableCorrespondance

    def _creer(site_id, code, definitive, groupe="6a@lekreisker.fr"):
        tc = TableCorrespondance(
            site_id=site_id, classe_charlemagne_long=f"CLASSE {code}",
            classe_code_court=code, ou_pre_rentree="/3. NDK/NDK2027",
            ou_definitive=definitive, groupe_google=groupe,
        )
        session.add(tc)
        session.commit()
        return tc

    return _creer


def _etat(session, annee_id, etape, **kw):
    from backend.services.parcours import avancement

    return avancement(session, annee_id=annee_id, **kw).par_id[etape]


# ---------------------------------------------------------------------------
# Les cinq étapes qu'on croyait aveugles
# ---------------------------------------------------------------------------


def test_la_rotation_se_lit_dans_les_chemins_de_la_table(
    session, site_factory, annee_factory, tc_factory
):
    """`2026-2027` prépare l'arbre `2027` : la seconde moitié du libellé."""
    site = site_factory("NDK")
    annee = annee_factory("2026-2027")
    tc_factory(site.id, "6A", "/3. NDK/NDK2027/6A")

    assert _etat(session, annee.id, "rotation").etat == FAITE


def test_une_table_restee_sur_lannee_passee_est_a_faire(
    session, site_factory, annee_factory, tc_factory
):
    site = site_factory("NDK")
    annee = annee_factory("2026-2027")
    tc_factory(site.id, "6A", "/3. NDK/NDK2026/6A")

    e = _etat(session, annee.id, "rotation")
    assert e.etat == A_FAIRE
    assert "2027" in e.detail


def test_des_constats_sans_base_ne_valent_pas_un_controle(
    session, site_factory, annee_factory
):
    """C'est le défaut réel : 2299 constats relevés, aucun exploitable."""
    from backend.models import LoginReserve

    site_factory("NDK")
    annee = annee_factory("2026-2027")
    session.add(LoginReserve(login="jdupont", badge=100, site=None))
    session.commit()

    e = _etat(session, annee.id, "controle_koxo")
    assert e.etat == A_FAIRE
    assert "sans leur base" in e.detail


def test_des_constats_avec_leur_base_valent_un_controle(
    session, site_factory, annee_factory
):
    from backend.models import LoginReserve

    site_factory("NDK")
    annee = annee_factory("2026-2027")
    session.add(LoginReserve(login="jdupont", badge=100, site="NDK"))
    session.commit()

    e = _etat(session, annee.id, "controle_koxo")
    assert e.etat == FAITE
    assert "NDK" in e.detail


def test_la_synchro_koxo_se_lit_dans_les_constats(
    session, site_factory, annee_factory, personne_factory, snap_factory
):
    """Si chaque élève de l'année figure dans un export contrôlé, KoXo les a."""
    from backend.models import LoginReserve

    site = site_factory("NDK")
    annee = annee_factory("2026-2027")
    p = personne_factory(site_id=site.id, login="jdupont", id_charlemagne=100)
    snap_factory(p.id, annee.id, classe="6A")
    session.add(LoginReserve(login="jdupont", badge=p.badge, site="NDK"))
    session.commit()

    assert _etat(session, annee.id, "synchro_koxo").etat == FAITE


def test_un_eleve_absent_de_koxo_rend_la_synchro_a_faire(
    session, site_factory, annee_factory, personne_factory, snap_factory
):
    from backend.models import LoginReserve

    site = site_factory("NDK")
    annee = annee_factory("2026-2027")
    badges = []
    for idc in (100, 200):
        p = personne_factory(site_id=site.id, login=f"e{idc}", id_charlemagne=idc)
        snap_factory(p.id, annee.id, classe="6A")
        badges.append(p.badge)
    session.add(LoginReserve(login="e100", badge=badges[0], site="NDK"))
    session.commit()

    e = _etat(session, annee.id, "synchro_koxo")
    assert e.etat == A_FAIRE
    assert "1 élève" in e.detail


def test_la_bascule_se_lit_dans_les_ou_memorisees(
    session, site_factory, annee_factory, personne_factory, snap_factory
):
    """Le programme mémorise ce qu'il applique : Google n'est pas nécessaire."""
    from backend.models import CompteCible

    site = site_factory("NDK")
    annee = annee_factory("2026-2027")
    p = personne_factory(site_id=site.id, login="jdupont", id_charlemagne=100)
    snap_factory(p.id, annee.id, classe="6A")
    session.add(CompteCible(personne_id=p.id, cible="google", etat="cree",
                            ou_appliquee="/3. NDK/NDK2027"))
    session.commit()

    assert _etat(session, annee.id, "bascule").etat == FAITE


def test_une_bascule_partielle_reste_a_faire(
    session, site_factory, annee_factory, personne_factory, snap_factory
):
    from backend.models import CompteCible

    site = site_factory("NDK")
    annee = annee_factory("2026-2027")
    places, total = 0, 3
    for i in range(total):
        p = personne_factory(site_id=site.id, login=f"e{i}",
                             id_charlemagne=100 + i)
        snap_factory(p.id, annee.id, classe="6A")
        if places < 1:
            session.add(CompteCible(personne_id=p.id, cible="google",
                                    etat="cree", ou_appliquee="/3. NDK/NDK2027"))
            places += 1
    session.commit()

    e = _etat(session, annee.id, "bascule")
    assert e.etat == A_FAIRE
    assert "2 élève" in e.detail


# ---------------------------------------------------------------------------
# Ce qui ne se lit que dans Google
# ---------------------------------------------------------------------------


def test_les_etapes_google_valent_inconnu_par_defaut(
    session, site_factory, annee_factory
):
    """Le module n'appelle jamais Google : il ne peut pas conclure seul."""
    from backend.services.parcours import ETAPES_GOOGLE

    site_factory("NDK")
    annee = annee_factory("2026-2027")

    for etape in ETAPES_GOOGLE:
        e = _etat(session, annee.id, etape)
        assert e.etat == INCONNU, etape
        assert e.source == "google"
        assert e.detail, "un état sans phrase ne vaut rien"


def test_un_etat_google_fourni_est_repris(session, site_factory, annee_factory):
    site_factory("NDK")
    annee = annee_factory("2026-2027")

    e = _etat(session, annee.id, "adresses", etats_google={
        "adresses": (FAITE, "Aucune divergence résolvable."),
    })
    assert e.etat == FAITE
    assert e.detail == "Aucune divergence résolvable."


def test_inconnu_nest_pas_a_faire(session, site_factory, annee_factory):
    """Une case vide faute d'avoir regardé mentirait autant qu'une case fausse."""
    from backend.services.parcours import avancement

    site_factory("NDK")
    annee = annee_factory("2026-2027")
    r = avancement(session, annee_id=annee.id)

    assert r.nb_inconnues >= 5
    assert all(e.detail for e in r.etapes)


# ---------------------------------------------------------------------------
# Les étapes de préparation, qui marchaient déjà
# ---------------------------------------------------------------------------


def test_sans_rien_tout_est_a_faire(session, annee_factory):
    from backend.services.parcours import avancement

    annee = annee_factory("2026-2027")
    r = avancement(session, annee_id=annee.id)
    par_id = r.par_id

    assert par_id["sites"].etat == A_FAIRE
    assert par_id["table"].etat == A_FAIRE
    assert par_id["amorcage"].etat == A_FAIRE
    assert par_id["ingestion"].etat == A_FAIRE


def test_une_table_sans_adresse_de_groupe_est_faite_mais_le_dit(
    session, site_factory, annee_factory, tc_factory
):
    site = site_factory("NDK")
    annee = annee_factory("2026-2027")
    tc_factory(site.id, "6A", "/3. NDK/NDK2027/6A", groupe=None)

    e = _etat(session, annee.id, "table")
    assert e.etat == FAITE
    assert "sans adresse de groupe" in e.detail


def test_une_annee_inconnue_est_refusee(session):
    from backend.services.parcours import avancement

    with pytest.raises(ValueError, match="introuvable"):
        avancement(session, annee_id=9999)


# ---------------------------------------------------------------------------
# Les endpoints
# ---------------------------------------------------------------------------


@pytest.fixture()
def client(tmp_db_path):
    from fastapi.testclient import TestClient

    from backend.main import app

    with TestClient(app) as c:
        yield c


def test_lendpoint_local_nappelle_pas_google(
    session, client, site_factory, annee_factory, tc_factory
):
    """Il est rejoué à chaque navigation : il doit rester gratuit."""
    from backend.services.parcours import ETAPES_GOOGLE

    site = site_factory("NDK")
    annee = annee_factory("2026-2027")
    tc_factory(site.id, "6A", "/3. NDK/NDK2027/6A")

    r = client.get("/api/parcours/avancement", params={"annee_id": annee.id})
    assert r.status_code == 200, r.text
    par_id = {e["id"]: e for e in r.json()["etapes"]}

    assert par_id["rotation"]["etat"] == FAITE
    for etape in ETAPES_GOOGLE:
        assert par_id[etape]["etat"] == INCONNU
        assert par_id[etape]["source"] == "google"


def test_lendpoint_local_refuse_une_annee_inconnue(client):
    r = client.get("/api/parcours/avancement", params={"annee_id": 9999})
    assert r.status_code == 400
    assert "introuvable" in r.json()["detail"].lower()


def test_une_lecture_google_en_echec_nemporte_pas_les_autres(session, contexte_nd):
    """Celle qui tombe laisse ses étapes à `inconnu`, avec la raison.

    L'interprétation est séparée de la lecture réseau : c'est elle qui
    porte les décisions, et elle s'éprouve sans Google.
    """
    from backend.routers.parcours import etats_google_depuis

    annee = contexte_nd
    etats = etats_google_depuis(
        session, annee_id=annee.id, comptes=None, diff=None,
        erreurs={"adresses": "Lecture des comptes impossible : réseau"},
    )

    assert etats["adresses"][0] == INCONNU
    assert "réseau" in etats["adresses"][1]
    assert etats["vider"][0] == INCONNU


def test_des_groupes_complets_font_une_etape_faite(session, contexte_nd):
    from backend.routers.parcours import etats_google_depuis

    class _Diff:
        nb_a_ajouter = 0
        groupes_absents: list = []

    etats = etats_google_depuis(session, annee_id=contexte_nd.id, diff=_Diff())
    assert etats["groupes"][0] == FAITE
    assert etats["arborescence"][0] == FAITE


def test_des_groupes_absents_de_google_bloquent_larborescence(
    session, contexte_nd
):
    from backend.routers.parcours import etats_google_depuis

    class _Diff:
        nb_a_ajouter = 12
        groupes_absents = ["6eme-a@lekreisker.fr"]

    etats = etats_google_depuis(session, annee_id=contexte_nd.id, diff=_Diff())
    assert etats["groupes"][0] == A_FAIRE
    assert etats["arborescence"][0] == A_FAIRE
    assert "1 groupe" in etats["arborescence"][1]


def test_un_eleve_sans_compte_google_rend_letape_comptes_a_faire(
    session, site_factory, annee_factory, personne_factory, snap_factory
):
    from backend.routers.parcours import etats_google_depuis

    site = site_factory("NDK")
    annee = annee_factory("2026-2027")
    p = personne_factory(site_id=site.id, login="jdupont", id_charlemagne=100,
                         email_constate="jean.dupont@lekreisker.fr")
    snap_factory(p.id, annee.id, classe="6A")

    etats = etats_google_depuis(session, annee_id=annee.id, comptes=[])
    assert etats["comptes"][0] == A_FAIRE
    assert "1 élève" in etats["comptes"][1]


def test_un_alias_suffit_a_reconnaitre_un_compte(
    session, site_factory, annee_factory, personne_factory, snap_factory
):
    """Un compte répond à ses alias : l'étape ne doit pas les ignorer."""
    from backend.routers.parcours import etats_google_depuis

    site = site_factory("NDK")
    annee = annee_factory("2026-2027")
    p = personne_factory(site_id=site.id, login="jdupont", id_charlemagne=100,
                         email_constate="j.dupont@lekreisker.fr")
    snap_factory(p.id, annee.id, classe="6A")

    etats = etats_google_depuis(session, annee_id=annee.id, comptes=[{
        "email": "jean.dupont@lekreisker.fr",
        "alias": ["j.dupont@lekreisker.fr"],
        "ou": "/3. NDK/NDK2027", "nom": "DUPONT", "prenom": "Jean",
    }])
    assert etats["comptes"][0] == FAITE


@pytest.fixture()
def contexte_nd(session, site_factory, annee_factory):
    site_factory("NDK")
    return annee_factory("2026-2027")
