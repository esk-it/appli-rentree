"""Tests de la mise en conformité de l'arborescence Google."""
from __future__ import annotations

import pytest


@pytest.fixture()
def table(session, site_factory):
    """Deux sites, quelques classes visant l'arbre 2027."""
    from backend.models import TableCorrespondance

    ndk = site_factory("NDK")
    nde = site_factory("NDE")
    session.add_all([
        TableCorrespondance(
            site_id=ndk.id, classe_charlemagne_long="S1", classe_code_court="2_1",
            ou_pre_rentree="/3. NDK/NDK2027", ou_definitive="/3. NDK/NDK2027/2_1",
        ),
        TableCorrespondance(
            site_id=ndk.id, classe_charlemagne_long="S9", classe_code_court="2_9",
            ou_pre_rentree="/3. NDK/NDK2027", ou_definitive="/3. NDK/NDK2027/2_9",
        ),
        TableCorrespondance(
            site_id=nde.id, classe_charlemagne_long="3F", classe_code_court="3F",
            ou_pre_rentree="/2. NDE/NDE2027", ou_definitive="/2. NDE/NDE2027/3F",
        ),
    ])
    session.commit()


def test_renommage_emporte_les_classes(session, table):
    """Recycler un arbre évite de recréer ses dizaines de classes."""
    from backend.services.ou_google import analyser_conformite

    existantes = [
        "/3. NDK", "/3. NDK/NDK2025", "/3. NDK/NDK2025/2_1", "/3. NDK/NDK2025/T_G1A",
        "/2. NDE",
    ]
    r = analyser_conformite(
        session, existantes, annee_source="2025", annee_cible="2027"
    )
    assert len(r.renommages) == 1
    assert r.renommages[0].ancien == "/3. NDK/NDK2025"
    assert r.renommages[0].nouveau == "/3. NDK/NDK2027"
    assert r.renommages[0].nb_sous_ou == 2
    # 2_1 suit son parent : plus rien à créer pour elle
    assert "/3. NDK/NDK2027/2_1" in r.deja_conformes
    assert "/3. NDK/NDK2027/2_1" not in r.a_creer


def test_les_classes_nouvelles_restent_a_creer(session, table):
    """Un arbre recyclé ne connaît que les classes de son année d'origine."""
    from backend.services.ou_google import analyser_conformite

    existantes = ["/3. NDK", "/3. NDK/NDK2025", "/3. NDK/NDK2025/2_1", "/2. NDE"]
    r = analyser_conformite(
        session, existantes, annee_source="2025", annee_cible="2027"
    )
    assert "/3. NDK/NDK2027/2_9" in r.a_creer


def test_site_sans_arbre_a_recycler(session, table):
    """NDE n'a pas d'arbre 2025 : tout son arbre 2027 est à créer."""
    from backend.services.ou_google import analyser_conformite

    existantes = ["/3. NDK", "/3. NDK/NDK2025", "/2. NDE"]
    r = analyser_conformite(
        session, existantes, annee_source="2025", annee_cible="2027"
    )
    assert "/2. NDE/NDE2027" in r.a_creer
    assert "/2. NDE/NDE2027/3F" in r.a_creer


def test_le_parent_est_cree_avant_son_enfant(session, table):
    """Google refuse une OU dont le parent n'existe pas."""
    from backend.services.ou_google import analyser_conformite

    r = analyser_conformite(session, ["/3. NDK", "/2. NDE"], autoriser_renommage=False)
    positions = {c: i for i, c in enumerate(r.a_creer)}
    assert positions["/2. NDE/NDE2027"] < positions["/2. NDE/NDE2027/3F"]
    assert positions["/3. NDK/NDK2027"] < positions["/3. NDK/NDK2027/2_1"]


def test_parent_intermediaire_absent_est_ajoute(session, table):
    """La Table ne déclare que les classes ; l'arbre d'année doit suivre."""
    from backend.services.ou_google import analyser_conformite

    r = analyser_conformite(session, [], autoriser_renommage=False)
    assert "/3. NDK" in r.a_creer
    assert "/3. NDK/NDK2027" in r.a_creer


def test_sans_renommage_tout_est_cree(session, table):
    from backend.services.ou_google import analyser_conformite

    existantes = ["/3. NDK", "/3. NDK/NDK2025", "/3. NDK/NDK2025/2_1", "/2. NDE"]
    r = analyser_conformite(session, existantes, autoriser_renommage=False)
    assert r.renommages == []
    assert "/3. NDK/NDK2027/2_1" in r.a_creer


def test_arbre_cible_deja_present_nest_pas_fusionne(session, table):
    """Renommer sur un arbre existant mêlerait deux promotions."""
    from backend.services.ou_google import analyser_conformite

    existantes = [
        "/3. NDK", "/3. NDK/NDK2025", "/3. NDK/NDK2027", "/2. NDE",
    ]
    r = analyser_conformite(
        session, existantes, annee_source="2025", annee_cible="2027"
    )
    assert r.renommages == []
    assert any("existe déjà" in a for a in r.avertissements)


def test_conformite_totale(session, table):
    from backend.services.ou_google import analyser_conformite

    existantes = [
        "/3. NDK", "/3. NDK/NDK2027", "/3. NDK/NDK2027/2_1", "/3. NDK/NDK2027/2_9",
        "/2. NDE", "/2. NDE/NDE2027", "/2. NDE/NDE2027/3F",
    ]
    r = analyser_conformite(session, existantes, autoriser_renommage=False)
    assert r.est_conforme is True
    assert r.nb_a_creer == 0


def test_table_vide_est_signalee(session, site_factory):
    from backend.services.ou_google import analyser_conformite

    site_factory("NDK")
    r = analyser_conformite(session, ["/3. NDK"])
    assert r.a_creer == []
    assert any("aucune OU" in a for a in r.avertissements)
