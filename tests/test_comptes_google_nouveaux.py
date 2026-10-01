"""Les inscrits sans compte Google, et leur création en un clic.

Un élève qui arrive : Johann recopie son identifiant et son mot de passe
KoXo dans Charlemagne, ingère l'export enrichi — et le programme crée le
compte Google qu'il créait jusqu'ici à la main dans la console.
"""
from __future__ import annotations

from datetime import datetime

import pytest

DOMAINE = "lekreisker.fr"
OU_ATTENTE = "/3. NDK/NDK2027"
OU_CLASSE = "/3. NDK/NDK2027/2_1"
GROUPE = "2nde-1@lekreisker.fr"


@pytest.fixture()
def ecole(session, site_factory, annee_factory, personne_factory):
    from backend.models import Snapshot, TableCorrespondance

    ndk = site_factory("NDK")
    ndk.base_koxo = "NDK"
    an = annee_factory("2026-2027")
    session.add(TableCorrespondance(
        site_id=ndk.id, classe_charlemagne_long="2NDE 1", classe_code_court="2_1",
        ou_pre_rentree=OU_ATTENTE, ou_definitive=OU_CLASSE, groupe_google=GROUPE,
    ))
    session.commit()

    def eleve(nom, prenom, id_ch, **kw):
        p = personne_factory(nom=nom, prenom=prenom, id_charlemagne=id_ch, site_id=ndk.id,
                             classe="2_1", **kw)
        session.add(Snapshot(personne_id=p.id, annee_scolaire_id=an.id, nom=nom, prenom=prenom,
                             classe="2_1", date_ingestion=datetime(2026, 9, 30)))
        session.commit()
        return p

    return {"site": ndk, "an": an, "eleve": eleve}


@pytest.fixture()
def cle(session):
    from backend.services.coffre import initialiser

    return initialiser(session, "maitre-essai-longue-phrase")


def _deposer(session, cle, p, mdp, cible="charlemagne", site=None, identifiant=None):
    from backend.services.coffre import deposer

    deposer(session, cle, personne_id=p.id, mot_de_passe=mdp, cible=cible, site=site,
            origine=cible, identifiant=identifiant)
    session.commit()


def _compte(email, ou=OU_CLASSE, nom="AUTRE", prenom="Camarade", alias=(), id_externe=None):
    return {"email": email, "alias": list(alias), "ou": ou, "nom": nom, "prenom": prenom,
            "id_externe": id_externe}


# ---------------------------------------------------------------------------
# Le relevé
# ---------------------------------------------------------------------------


def test_un_inscrit_sans_compte_est_a_creer_dans_l_unite_de_ses_camarades(session, ecole, cle):
    from backend.services.comptes_google_nouveaux import relever

    lea = ecole["eleve"]("ROUE", "Léa", 8761)
    _deposer(session, cle, lea, "Abcdef12")
    r = relever(session, [_compte("camarade@lekreisker.fr")])

    (c,) = r.a_creer
    assert (c.personne_id, c.adresse) == (lea.id, f"lea.roue@{DOMAINE}")
    assert (c.ou, c.groupe, c.origine_mot_de_passe, c.bloque) == (OU_CLASSE, GROUPE, "charlemagne", None)
    assert (r.nb_inscrits, r.nb_avec_compte) == (1, 0)


def test_l_unite_de_pre_rentree_quand_les_camarades_y_attendent(session, ecole, cle):
    from backend.services.comptes_google_nouveaux import relever

    _deposer(session, cle, ecole["eleve"]("ROUE", "Léa", 8761), "Abcdef12")
    r = relever(session, [_compte("camarade@lekreisker.fr", ou=OU_ATTENTE)])
    assert r.a_creer[0].ou == OU_ATTENTE


def test_un_compte_par_adresse_alias_ou_numero_n_est_pas_a_creer(session, ecole):
    from backend.services.comptes_google_nouveaux import relever

    ecole["eleve"]("ROUE", "Léa", 8761)
    ecole["eleve"]("DUIGOU", "Raphaël", 8762)
    ecole["eleve"]("TANGUY", "Alix", 8763)
    r = relever(session, [
        _compte(f"lea.roue@{DOMAINE}"),
        _compte(f"r.duigou@{DOMAINE}", alias=[f"raphael.duigou@{DOMAINE}"]),
        _compte(f"alix.t@{DOMAINE}", id_externe="8763"),
    ])
    assert r.a_creer == [] and r.a_rattacher == []
    assert r.nb_avec_compte == 3


def test_un_compte_au_meme_nom_sous_une_autre_adresse_est_a_rattacher(session, ecole, cle):
    """Créé à la main sous une autre orthographe : le doubler serait pire."""
    from backend.services.comptes_google_nouveaux import relever

    lea = ecole["eleve"]("ROUE", "Léa", 8761)
    _deposer(session, cle, lea, "Abcdef12")
    r = relever(session, [_compte(f"lea.roue2@{DOMAINE}", nom="Roué", prenom="Léa")])
    assert r.a_creer == []
    (a,) = r.a_rattacher
    assert a.adresses_google == [f"lea.roue2@{DOMAINE}"]


def test_un_homonyme_qui_appartient_a_une_autre_fiche_n_empeche_rien(session, ecole, cle):
    from backend.services.comptes_google_nouveaux import relever

    ecole["eleve"]("LE GALL", "Yann", 8770, email_constate=f"yann.le-gall@{DOMAINE}", login="ylegall")
    nouveau = ecole["eleve"]("LE GALL", "Yann", 8771, login="ylegall2",
                             email_attribuee=f"yann.le-gall2@{DOMAINE}")
    _deposer(session, cle, nouveau, "Abcdef12")
    r = relever(session, [_compte(f"yann.le-gall@{DOMAINE}", nom="LE GALL", prenom="Yann")])
    assert [c.personne_id for c in r.a_creer] == [nouveau.id]
    assert r.a_rattacher == []


def test_sans_mot_de_passe_au_coffre_la_creation_est_bloquee(session, ecole):
    from backend.services.comptes_google_nouveaux import relever

    ecole["eleve"]("ROUE", "Léa", 8761)
    (c,) = relever(session, []).a_creer
    assert c.bloque and "MDP Réseau Péda" in c.bloque


# ---------------------------------------------------------------------------
# La création
# ---------------------------------------------------------------------------


class FauxGoogle:
    def __init__(self, comptes=(), refus=None):
        self.comptes = list(comptes)
        self.creations = []
        self.membres = []
        self.refus = refus

    def lister_utilisateurs(self, prefixe_ou=None):
        return list(self.comptes)

    def creer_utilisateur(self, payload):
        if self.refus:
            raise RuntimeError(self.refus)
        self.creations.append(payload)
        return {"id": "g-123", "primaryEmail": payload["primaryEmail"]}

    def ajouter_membre(self, groupe, email):
        self.membres.append((groupe, email))


def test_la_creation_porte_le_mot_de_passe_de_koxo_avant_celui_de_charlemagne(session, ecole, cle):
    """KoXo fait foi : c'est son mot de passe que l'élève connaît."""
    from backend.models import CompteCible, Personne
    from backend.services.comptes_google_nouveaux import creer

    lea = ecole["eleve"]("ROUE", "Léa", 8761)
    _deposer(session, cle, lea, "Charlem1")
    _deposer(session, cle, lea, "Koxo1234", cible="koxo", site="NDK")
    google = FauxGoogle([_compte("camarade@lekreisker.fr")])

    (r,) = creer(session, google, cle, [lea.id])

    assert (r.statut, r.ou, r.groupe_ok) == ("cree", OU_CLASSE, True)
    (payload,) = google.creations
    assert payload["primaryEmail"] == f"lea.roue@{DOMAINE}"
    assert payload["password"] == "Koxo1234"
    assert payload["orgUnitPath"] == OU_CLASSE
    assert payload["changePasswordAtNextLogin"] is False
    assert google.membres == [(GROUPE, f"lea.roue@{DOMAINE}")]
    session.expire_all()
    assert session.get(Personne, lea.id).email_constate == f"lea.roue@{DOMAINE}"
    compte = session.query(CompteCible).filter_by(personne_id=lea.id, cible="google").one()
    assert (compte.etat, compte.ou_appliquee, compte.identifiant_externe) == ("cree", OU_CLASSE, "g-123")


def test_un_compte_que_google_a_deja_n_est_pas_ecrase(session, ecole, cle):
    from backend.services.comptes_google_nouveaux import creer

    lea = ecole["eleve"]("ROUE", "Léa", 8761)
    _deposer(session, cle, lea, "Abcdef12")
    google = FauxGoogle(refus="HttpError 409: Entity already exists.")

    (r,) = creer(session, google, cle, [lea.id])
    assert r.statut == "existait" and "rien n'a été écrasé" in r.message


def test_un_compte_apparu_entre_l_apercu_et_le_clic_n_est_pas_cree(session, ecole, cle):
    from backend.services.comptes_google_nouveaux import creer

    lea = ecole["eleve"]("ROUE", "Léa", 8761)
    _deposer(session, cle, lea, "Abcdef12")
    google = FauxGoogle([_compte(f"lea.roue@{DOMAINE}")])

    (r,) = creer(session, google, cle, [lea.id])
    assert r.statut == "ignore" and google.creations == []


def test_le_journal_ne_garde_ni_mot_de_passe_ni_nom(session, ecole, cle):
    from backend.models import Generation
    from backend.services.comptes_google_nouveaux import creer

    lea = ecole["eleve"]("ROUE", "Léa", 8761)
    _deposer(session, cle, lea, "Secret99")
    creer(session, FauxGoogle(), cle, [lea.id])

    (g,) = session.query(Generation).filter_by(type_operation="cycle_vie", cible="google").all()
    trace = f"{g.parametres_json} {g.resultat_json} {g.notes}"
    assert "Secret99" not in trace and "ROUE" not in trace


# ---------------------------------------------------------------------------
# Les étiquettes, depuis le coffre
# ---------------------------------------------------------------------------


def test_les_etiquettes_des_nouveaux_viennent_du_coffre(session, ecole, cle):
    from backend.services.comptes_google_nouveaux import etiquettes

    lea = ecole["eleve"]("ROUE", "Léa", 8761)
    sans = ecole["eleve"]("DUIGOU", "Raphaël", 8762)
    _deposer(session, cle, lea, "Abcdef12", identifiant="lroue2")

    planches, sans_mdp = etiquettes(session, cle, [lea.id, sans.id])
    ((site, html),) = planches
    page = html.decode("utf-8")
    assert site == "NDK" and "Abcdef12" in page and "lroue2" in page
    assert sans_mdp == ["Raphaël DUIGOU"]


# ---------------------------------------------------------------------------
# Les points d'entrée
# ---------------------------------------------------------------------------


@pytest.fixture()
def client(tmp_db_path):
    from fastapi.testclient import TestClient

    from backend.main import app

    with TestClient(app) as c:
        yield c


def test_rien_ne_se_cree_sans_confirmation_ni_coffre_ouvert(client):
    r = client.post("/api/google/nouveaux-sans-compte/creer", json={"personne_ids": [1]})
    assert r.status_code == 400
    r = client.post(
        "/api/google/nouveaux-sans-compte/creer", json={"personne_ids": [1], "confirmation": True}
    )
    assert r.status_code == 401, "coffre fermé : pas de mot de passe, pas de compte"
