"""Le mot de passe KoXo et Google : lire l'audit, imposer sur clic.

KoXo est LE mot de passe (Johann, 13 octobre 2026). Google ne se vérifie
pas ; on lit qui y a changé un mot de passe, et on lui impose celui de KoXo
pour les comptes choisis — « seulement sur mon clic ».
"""
from __future__ import annotations

from datetime import datetime

import pytest

DOMAINE = "lekreisker.fr"


@pytest.fixture()
def ecole(session, site_factory, annee_factory, personne_factory):
    from backend.models import Snapshot

    ndk = site_factory("NDK", domaine_mail=DOMAINE)
    ndk.base_koxo = "NDK"
    nde = site_factory("NDE", domaine_mail=DOMAINE)
    an = annee_factory("2026-2027")
    session.commit()

    def eleve(nom, prenom, site=ndk, type="eleve", **kw):
        p = personne_factory(type=type, nom=nom, prenom=prenom, site_id=site.id, classe="2_1", **kw)
        session.add(Snapshot(personne_id=p.id, annee_scolaire_id=an.id, nom=nom, prenom=prenom,
                             classe="2_1", date_ingestion=datetime(2026, 10, 12)))
        session.commit()
        return p

    return {"ndk": ndk, "nde": nde, "an": an, "eleve": eleve}


@pytest.fixture()
def cle(session):
    from backend.services.coffre import initialiser

    return initialiser(session, "maitre-essai-longue-phrase")


def _deposer(session, cle, p, mdp, *, cible, site=None, quand=None):
    from backend.services.coffre import deposer

    s = deposer(session, cle, personne_id=p.id, mot_de_passe=mdp, cible=cible, site=site,
                origine="genere" if cible == "google" else cible)
    if quand:
        s.date_maj = quand
    session.commit()


class FauxGoogle:
    def __init__(self, refus=None):
        self.imposes: list[tuple[str, str]] = []
        self.refus = refus

    def imposer_mot_de_passe(self, email, mot_de_passe):
        if self.refus:
            raise RuntimeError(self.refus)
        self.imposes.append((email, mot_de_passe))


# ---------------------------------------------------------------------------
# Lire l'audit
# ---------------------------------------------------------------------------


def test_le_dernier_changement_de_chaque_eleve_et_qui_l_a_fait(session, ecole):
    from backend.services.mots_de_passe_google import changements

    lea = ecole["eleve"]("ROUE", "Léa", email_constate=f"lea.roue@{DOMAINE}")
    tom = ecole["eleve"]("BIHAN", "Tom", email_constate=f"tom.bihan@{DOMAINE}")
    evenements = [
        {"email": f"lea.roue@{DOMAINE}", "quand": "2026-09-02T08:00:00Z",
         "par": f"johann.deniel@{DOMAINE}", "par_l_utilisateur": False},
        {"email": f"lea.roue@{DOMAINE}", "quand": "2026-10-01T10:00:00Z",
         "par": f"lea.roue@{DOMAINE}", "par_l_utilisateur": True},
        {"email": f"tom.bihan@{DOMAINE}", "quand": "2026-09-20T10:00:00Z",
         "par": f"johann.deniel@{DOMAINE}", "par_l_utilisateur": False},
        {"email": f"prof@{DOMAINE}", "quand": "2026-09-20T10:00:00Z",
         "par": f"prof@{DOMAINE}", "par_l_utilisateur": True},
    ]
    r = changements(session, evenements, depuis="2026-08-01")

    assert (r.nb_evenements, r.nb_hors_eleves) == (4, 1)
    par_nom = {c.nom: c for c in r.changements}
    assert (par_nom["ROUE"].par_l_eleve, par_nom["ROUE"].nb_changements) == (True, 2)
    assert par_nom["ROUE"].quand == "2026-10-01T10:00:00Z"
    assert par_nom["BIHAN"].par_l_eleve is False and par_nom["BIHAN"].personne_id == tom.id
    assert lea.id in {c.personne_id for c in r.changements}


# ---------------------------------------------------------------------------
# Imposer, sur clic
# ---------------------------------------------------------------------------


def test_le_mot_de_passe_koxo_part_chez_google(session, ecole, cle):
    from backend.services.mots_de_passe_google import imposer

    lea = ecole["eleve"]("ROUE", "Léa", email_constate=f"lea.roue@{DOMAINE}")
    _deposer(session, cle, lea, "Koxo1234", cible="koxo", site="NDK")
    _deposer(session, cle, lea, "Charl567", cible="charlemagne")
    google = FauxGoogle()

    (r,) = imposer(session, google, cle, [lea.id])
    assert r.statut == "impose" and r.releve_koxo is not None
    assert google.imposes == [(f"lea.roue@{DOMAINE}", "Koxo1234")]


def test_a_nde_c_est_le_mot_de_passe_fabrique(session, ecole, cle):
    from backend.services.mots_de_passe_google import imposer

    rose = ecole["eleve"]("KERDONCUFF", "Rose", site=ecole["nde"],
                          email_constate=f"rose.kerdoncuff@{DOMAINE}")
    _deposer(session, cle, rose, "Gene1234", cible="google", site="NDE")
    google = FauxGoogle()
    (r,) = imposer(session, google, cle, [rose.id])
    assert r.statut == "impose" and google.imposes == [(f"rose.kerdoncuff@{DOMAINE}", "Gene1234")]


@pytest.mark.parametrize("cas, attendu", [
    ("adulte", "Réservé aux élèves"),
    ("adresse_calculee", "Adresse calculée"),
    ("sans_koxo", "Aucun relevé KoXo"),
    ("contredit", "contredit"),
])
def test_ce_que_l_imposition_refuse(session, ecole, cle, cas, attendu):
    from backend.services.mots_de_passe_google import imposer

    p = ecole["eleve"](
        "ROUE", "Léa", type="adulte" if cas == "adulte" else "eleve",
        email_constate=None if cas == "adresse_calculee" else f"lea.roue@{DOMAINE}",
    )
    if cas != "sans_koxo":
        _deposer(session, cle, p, "Ancien11", cible="koxo", site="NDK", quand=datetime(2026, 8, 31))
    _deposer(session, cle, p, "Collège2", cible="charlemagne", quand=datetime(2026, 10, 12))
    google = FauxGoogle()

    (r,) = imposer(session, google, cle, [p.id])
    assert r.statut == "refuse" and attendu in r.message
    assert google.imposes == []


def test_un_refus_de_google_n_arrete_pas_les_suivants_et_le_journal_se_tait(session, ecole, cle):
    from backend.models import Generation
    from backend.services.mots_de_passe_google import imposer

    lea = ecole["eleve"]("ROUE", "Léa", email_constate=f"lea.roue@{DOMAINE}")
    _deposer(session, cle, lea, "Koxo1234", cible="koxo", site="NDK")
    (r,) = imposer(session, FauxGoogle(refus="HttpError 403"), cle, [lea.id])
    assert r.statut == "echec" and "403" in r.message

    (g,) = session.query(Generation).filter_by(type_operation="identifiant", cible="google").all()
    trace = f"{g.parametres_json} {g.resultat_json} {g.notes}"
    assert "Koxo1234" not in trace and "ROUE" not in trace


# ---------------------------------------------------------------------------
# Les points d'entrée
# ---------------------------------------------------------------------------


@pytest.fixture()
def client(tmp_db_path):
    from fastapi.testclient import TestClient

    from backend.main import app

    with TestClient(app) as c:
        yield c


def test_rien_ne_s_impose_sans_confirmation_ni_coffre_ouvert(client):
    r = client.post("/api/google/mots-de-passe/imposer", json={"personne_ids": [1]})
    assert r.status_code == 400
    client.post("/api/coffre/verrouiller")
    r = client.post("/api/google/mots-de-passe/imposer",
                    json={"personne_ids": [1], "confirmation": True})
    assert r.status_code == 401


def test_sans_le_droit_d_audit_la_reponse_dit_comment_l_ajouter(client, monkeypatch):
    import importlib

    google_api = importlib.import_module("backend.services.google_api")

    class SansAudit:
        def changements_de_mot_de_passe(self, depuis):
            raise google_api.DroitManquant(f"ajoute {google_api.SCOPE_AUDIT}")

    monkeypatch.setattr("backend.routers.google_api.ClientGoogle", lambda config: SansAudit())
    r = client.get("/api/google/mots-de-passe/changements", params={"depuis": "2026-08-01"})
    assert r.status_code == 403
    assert "admin.reports.audit.readonly" in r.json()["detail"]
