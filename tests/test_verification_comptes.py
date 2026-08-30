"""Vérifier qu'un import a produit ce qu'on croit.

Un import de masse répond « 238 créations réussies » et s'arrête là. Il ne
dit pas dans quelle unité d'organisation les comptes ont atterri, ni s'ils
sont actifs, ni si Google réclamera un changement de mot de passe. Ces
trois-là décident pourtant si l'élève pourra se connecter le jour J.
"""
from __future__ import annotations

import pytest


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

    def _creer(site_id, code, pre, definitive):
        tc = TableCorrespondance(
            site_id=site_id, classe_charlemagne_long=f"CLASSE {code}",
            classe_code_court=code, ou_pre_rentree=pre, ou_definitive=definitive,
        )
        session.add(tc)
        session.commit()
        return tc

    return _creer


def _google(ou, *, suspendu=False, changement=False):
    return {
        "email": "jean.dupont@lekreisker.fr", "ou": ou, "suspendu": suspendu,
        "changement_mdp_exige": changement, "nom": "DUPONT", "prenom": "Jean",
        "date_creation": "2026-08-30T17:40:45.000Z", "derniere_connexion": None,
    }


@pytest.fixture()
def contexte(session, site_factory, annee_factory, personne_factory,
             snap_factory, tc_factory):
    site = site_factory("NDK")
    annee = annee_factory("2026-2027")
    tc_factory(site.id, "6A", "/3. NDK/NDK2027", "/3. NDK/NDK2027/6A")
    p = personne_factory(site_id=site.id, login="jdupont",
                         email_constate="jean.dupont@lekreisker.fr")
    snap_factory(p.id, annee.id, classe="6A")
    return site, annee, p


def test_un_compte_dans_lou_dattente_est_conforme(session, contexte):
    """Entre la pré-rentrée et le jour J, l'OU d'attente est la bonne."""
    from backend.services.verification_comptes import verifier_comptes

    _, annee, _ = contexte
    r = verifier_comptes(session, {
        "jean.dupont@lekreisker.fr": _google("/3. NDK/NDK2027"),
    }, annee_id=annee.id)

    c = r.comptes[0]
    assert c.trouve and c.est_conforme
    assert c.ou_reconnue == "pre_rentree"
    assert c.classe == "6A"
    assert r.tout_va_bien


def test_un_compte_dans_lou_de_sa_classe_est_conforme_aussi(session, contexte):
    """Le jour J, c'est l'autre qui est juste : on ne tranche pas."""
    from backend.services.verification_comptes import verifier_comptes

    _, annee, _ = contexte
    r = verifier_comptes(session, {
        "jean.dupont@lekreisker.fr": _google("/3. NDK/NDK2027/6A"),
    }, annee_id=annee.id)

    assert r.comptes[0].ou_reconnue == "definitive"
    assert r.comptes[0].est_conforme


def test_une_ou_inattendue_est_signalee(session, contexte):
    from backend.services.verification_comptes import verifier_comptes

    _, annee, _ = contexte
    r = verifier_comptes(session, {
        "jean.dupont@lekreisker.fr": _google("/3. NDK/NDK2026/2_1"),
    }, annee_id=annee.id)

    c = r.comptes[0]
    assert c.ou_reconnue is None
    assert any("inattendue" in a for a in c.anomalies)
    assert not r.tout_va_bien


def test_un_changement_de_mdp_exige_est_une_anomalie(session, contexte):
    """C'est le réglage qui ferait diverger Google de l'annuaire."""
    from backend.services.verification_comptes import verifier_comptes

    _, annee, _ = contexte
    r = verifier_comptes(session, {
        "jean.dupont@lekreisker.fr": _google("/3. NDK/NDK2027", changement=True),
    }, annee_id=annee.id)

    assert any("changement de mot de passe" in a
               for a in r.comptes[0].anomalies)


def test_un_compte_suspendu_est_une_anomalie(session, contexte):
    from backend.services.verification_comptes import verifier_comptes

    _, annee, _ = contexte
    r = verifier_comptes(session, {
        "jean.dupont@lekreisker.fr": _google("/3. NDK/NDK2027", suspendu=True),
    }, annee_id=annee.id)

    assert "compte suspendu" in r.comptes[0].anomalies


def test_une_adresse_sans_compte_google_est_le_cas_redoute(session, contexte):
    """C'est le résultat qu'on cherche, pas une erreur d'appel."""
    from backend.services.verification_comptes import verifier_comptes

    _, annee, _ = contexte
    r = verifier_comptes(
        session, {"jean.dupont@lekreisker.fr": None}, annee_id=annee.id
    )

    c = r.comptes[0]
    assert c.trouve is False
    assert r.nb_introuvables == 1
    assert any("aucun compte Google" in a for a in c.anomalies)


def test_le_rapport_dit_toujours_que_le_mdp_nest_pas_verifiable(
    session, contexte
):
    """Ne pas laisser croire qu'un compte « conforme » a le bon mot de passe."""
    from backend.services.verification_comptes import verifier_comptes

    _, annee, _ = contexte
    r = verifier_comptes(session, {
        "jean.dupont@lekreisker.fr": _google("/3. NDK/NDK2027"),
    }, annee_id=annee.id)

    assert any("ne se vérifie pas" in a for a in r.avertissements)


def test_lechantillon_prend_les_entrants_dabord(
    session, site_factory, annee_factory, personne_factory, snap_factory
):
    """Un compte ancien n'apprend rien sur l'import du jour."""
    from backend.services.verification_comptes import choisir_echantillon

    site = site_factory("NDK")
    annee = annee_factory("2026-2027")
    ancien = personne_factory(site_id=site.id, login="ancien",
                              email_constate="ancien@lekreisker.fr")
    snap_factory(ancien.id, annee.id, classe="6A")
    for i in range(3):
        neuf = personne_factory(site_id=site.id, login=f"neuf{i}")
        snap_factory(neuf.id, annee.id, classe="6A")

    adresses = choisir_echantillon(session, annee_id=annee.id, par_site=2)
    assert len(adresses) == 2
    assert "ancien@lekreisker.fr" not in adresses


def test_lechantillon_couvre_chaque_site(
    session, site_factory, annee_factory, personne_factory, snap_factory
):
    from backend.services.verification_comptes import choisir_echantillon

    annee = annee_factory("2026-2027")
    for nom in ("NDK", "SU"):
        site = site_factory(nom)
        for i in range(2):
            p = personne_factory(site_id=site.id, login=f"{nom}{i}".lower())
            snap_factory(p.id, annee.id, classe="6A")

    assert len(choisir_echantillon(session, annee_id=annee.id, par_site=1)) == 2


def test_un_echantillon_vide_ne_leve_pas(
    session, site_factory, annee_factory
):
    """Aucun élève chargé : la question n'a pas de réponse, pas d'exception."""
    from backend.services.verification_comptes import choisir_echantillon

    site_factory("NDK")
    annee = annee_factory("2026-2027")
    assert choisir_echantillon(session, annee_id=annee.id) == []


# ---------------------------------------------------------------------------
# L'endpoint
# ---------------------------------------------------------------------------


class _ClientFactice:
    """Un Google qui répond ce qu'on lui a dit de répondre."""

    def __init__(self, reponses):
        self.reponses = reponses
        self.demandees = []

    def lire_utilisateurs(self, adresses):
        self.demandees = list(adresses)
        return {a: self.reponses.get(a) for a in adresses}


def test_lendpoint_verifie_les_adresses_donnees(
    session, contexte, monkeypatch, tmp_db_path
):
    from fastapi.testclient import TestClient

    from backend.main import app

    _, annee, _ = contexte
    faux = _ClientFactice({
        "jean.dupont@lekreisker.fr": _google("/3. NDK/NDK2027"),
    })
    monkeypatch.setattr(
        "backend.routers.google_api.ClientGoogle", lambda config: faux
    )

    with TestClient(app) as client:
        r = client.post("/api/google/verifier-comptes", json={
            "annee_id": annee.id,
            "adresses": ["jean.dupont@lekreisker.fr"],
        })
    assert r.status_code == 200, r.text
    corps = r.json()
    assert corps["nb_verifies"] == 1
    assert corps["tout_va_bien"] is True
    assert faux.demandees == ["jean.dupont@lekreisker.fr"]


def test_lendpoint_choisit_un_echantillon_sans_adresses(
    session, contexte, monkeypatch, tmp_db_path
):
    """C'est le geste attendu : « vérifie-m'en deux et dis-moi »."""
    from fastapi.testclient import TestClient

    from backend.main import app

    _, annee, _ = contexte
    faux = _ClientFactice({
        "jean.dupont@lekreisker.fr": _google("/3. NDK/NDK2027"),
    })
    monkeypatch.setattr(
        "backend.routers.google_api.ClientGoogle", lambda config: faux
    )

    with TestClient(app) as client:
        r = client.post("/api/google/verifier-comptes",
                        json={"annee_id": annee.id})
    assert r.status_code == 200, r.text
    assert faux.demandees, "le programme a choisi lui-même"


def test_lendpoint_refuse_quand_il_ny_a_rien_a_verifier(
    session, site_factory, annee_factory, monkeypatch, tmp_db_path
):
    from fastapi.testclient import TestClient

    from backend.main import app

    site_factory("NDK")
    annee = annee_factory("2026-2027")
    monkeypatch.setattr(
        "backend.routers.google_api.ClientGoogle",
        lambda config: _ClientFactice({}),
    )

    with TestClient(app) as client:
        r = client.post("/api/google/verifier-comptes",
                        json={"annee_id": annee.id})
    assert r.status_code == 400
    assert "aucun élève" in r.json()["detail"].lower()
