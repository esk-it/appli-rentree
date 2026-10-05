"""Le relevé des adresses calculées dans l'annuaire Google.

Au 5 octobre 2026, le Référentiel affichait « calculée, pas encore relevée
dans Google » pour 152 adultes et 74 élèves de NDE dont le compte existait
bel et bien à cette adresse. Le relevé lit l'annuaire — sans y rien écrire —
et fait de ces adresses des constats ; ce qui ne concorde pas se propose.
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
    an = annee_factory("2026-2027")
    session.commit()

    def inscrit(nom, prenom, *, type="adulte", site=ndk, **kw):
        p = personne_factory(type=type, nom=nom, prenom=prenom,
                             site_id=site.id if site else None, **kw)
        session.add(Snapshot(personne_id=p.id, annee_scolaire_id=an.id, nom=nom, prenom=prenom,
                             classe="2_1" if type == "eleve" else None,
                             date_ingestion=datetime(2026, 9, 30)))
        session.commit()
        return p

    return {"ndk": ndk, "an": an, "inscrit": inscrit}


def _compte(email, nom, prenom, *, ou="/5. Professeurs", alias=(), suspendu=False,
            id_externe=None, id="g-1"):
    return {"email": email, "alias": list(alias), "ou": ou, "nom": nom, "prenom": prenom,
            "suspendu": suspendu, "id_externe": id_externe, "id": id}


def _relever(session, comptes):
    from backend.services.releve_adresses import relever

    return relever(session, comptes)


# ---------------------------------------------------------------------------
# Ce qui se relève d'office
# ---------------------------------------------------------------------------


def test_une_adresse_calculee_que_google_confirme_devient_un_constat(session, ecole):
    from backend.models import Personne
    from backend.services.releve_adresses import enregistrer

    anne = ecole["inscrit"]("MARTIN", "Anne")
    r = _relever(session, [_compte(f"anne.martin@{DOMAINE}", "MARTIN", "Anne", id="g-77")])

    assert [x.personne_id for x in r.relevees] == [anne.id]
    assert r.a_verifier == [] and r.sans_compte == []
    assert enregistrer(session, r) == 1
    session.expire_all()
    p = session.get(Personne, anne.id)
    assert (p.email_constate, p.google_user_id) == (f"anne.martin@{DOMAINE}", "g-77")


def test_l_ordre_nom_prenom_les_accents_et_les_tirets_ne_comptent_pas(session, ecole):
    """Des centaines de comptes portent le prénom dans le champ du nom."""
    ecole["inscrit"]("LE GALL", "Maelys")
    r = _relever(session, [_compte(f"maelys.le.gall@{DOMAINE}", "Maëlys", "Le-Gall")])
    assert len(r.relevees) == 1


def test_l_adresse_que_la_base_koxo_detient_est_essayee(session, ecole):
    """La règle des particules ne se devine pas : `isabelle.leduff@` ici,
    `le.duff` ailleurs. La base KoXo, elle, le sait."""
    from backend.models import LoginReserve

    isa = ecole["inscrit"]("LE DUFF", "Isabelle")
    session.add(LoginReserve(login="ileduff", badge=isa.badge, site="NDK",
                             source="controle_koxo", email=f"isabelle.leduff@{DOMAINE}"))
    session.commit()
    r = _relever(session, [_compte(f"isabelle.leduff@{DOMAINE}", "LE DUFF", "Isabelle")])
    (x,) = r.relevees
    assert x.adresse_google == f"isabelle.leduff@{DOMAINE}"
    assert x.adresse_affichee == f"isabelle.le.duff@{DOMAINE}"


def test_les_adresses_deja_constatees_ne_sont_pas_touchees(session, ecole):
    ecole["inscrit"]("MARTIN", "Anne", email_constate=f"a.martin@{DOMAINE}")
    r = _relever(session, [_compte(f"anne.martin@{DOMAINE}", "MARTIN", "Anne")])
    assert (r.nb_inscrits, r.nb_deja_constatees, r.relevees) == (1, 1, [])


# ---------------------------------------------------------------------------
# Ce qui se propose, sans rien écrire
# ---------------------------------------------------------------------------


def test_un_alias_au_nom_d_un_autre_se_propose(session, ecole):
    """`victor.guez@` est l'alias du compte de Victor GHEZ : c'est sans doute
    lui, mais une orthographe différente se regarde."""
    ecole["inscrit"]("GUEZ", "Victor", type="eleve")
    r = _relever(session, [_compte(f"victor.ghez@{DOMAINE}", "GHEZ", "Victor",
                                   ou="/2. NDE/NDE2027/6B", alias=[f"victor.guez@{DOMAINE}"])])
    (x,) = r.a_verifier
    assert x.adresse_google == f"victor.ghez@{DOMAINE}" and "Victor GHEZ" in x.motif
    assert r.relevees == []


def test_un_homonyme_meme_d_une_annee_passee_empeche_le_releve(session, ecole, personne_factory):
    """L'ancienne Léa ROUE garde `lea.roue@` : la nouvelle ne le reprend pas."""
    personne_factory(type="eleve", nom="ROUE", prenom="Léa", site_id=ecole["ndk"].id,
                     login="lroue", email_constate=f"lea.roue@{DOMAINE}")
    ecole["inscrit"]("ROUE", "Léa", type="eleve", login="lroue2")
    r = _relever(session, [_compte(f"lea.roue@{DOMAINE}", "ROUE", "Léa", ou="/7. Sortis")])
    (x,) = r.a_verifier
    assert "revendiquée aussi par Léa ROUE" in x.motif


@pytest.mark.parametrize(
    "compte, motif",
    [
        (dict(suspendu=True), "suspendu"),
        (dict(ou="/7. Sortis/Comptes à supprimer au 31-12-2027"), "rangé chez les sortis"),
        (dict(id_externe="999"), "autre numéro Charlemagne (999)"),
    ],
)
def test_un_compte_suspendu_sorti_ou_numerote_autrement_se_propose(session, ecole, compte, motif):
    ecole["inscrit"]("MARTIN", "Anne", id_charlemagne=120)
    r = _relever(session, [_compte(f"anne.martin@{DOMAINE}", "MARTIN", "Anne", **compte)])
    (x,) = r.a_verifier
    assert motif in x.motif and x.adresse_google == f"anne.martin@{DOMAINE}"


def test_sans_site_un_seul_compte_a_son_nom_se_propose(session, ecole):
    ecole["inscrit"]("LAZENNEC", "Annie", site=None)
    r = _relever(session, [_compte(f"annie.lazennec@{DOMAINE}", "LAZENNEC", "Annie",
                                   ou="/6. Personnel/AESH")])
    (x,) = r.a_verifier
    assert x.adresse_affichee is None and x.adresse_google == f"annie.lazennec@{DOMAINE}"


def test_sans_compte_a_son_nom_l_adresse_reste_calculee(session, ecole):
    ecole["inscrit"]("CHARLOU-CREPIN", "Marie")
    r = _relever(session, [_compte(f"autre@{DOMAINE}", "AUTRE", "Personne")])
    assert [x.nom for x in r.sans_compte] == ["CHARLOU-CREPIN"]


# ---------------------------------------------------------------------------
# Retenir une proposition
# ---------------------------------------------------------------------------


def test_retenir_garde_l_adresse_principale_et_refuse_ce_qui_est_pris(session, ecole):
    from backend.models import Personne
    from backend.services.releve_adresses import retenir

    victor = ecole["inscrit"]("GUEZ", "Victor", type="eleve")
    loris = ecole["inscrit"]("TOUX", "Loris", type="eleve")
    ecole["inscrit"]("TOUX", "Lorys", type="eleve", login="ltoux2", email_constate=f"lorys.toux@{DOMAINE}")
    comptes = {
        f"victor.guez@{DOMAINE}": {"email": f"victor.ghez@{DOMAINE}", "id": "g-9"},
        f"lorys.toux@{DOMAINE}": {"email": f"lorys.toux@{DOMAINE}", "id": "g-8"},
    }
    r = retenir(session, comptes, {victor.id: f"victor.guez@{DOMAINE}",
                                   loris.id: f"lorys.toux@{DOMAINE}"})

    assert [(x.retenue, x.adresse) for x in r] == [
        (True, f"victor.ghez@{DOMAINE}"), (False, f"lorys.toux@{DOMAINE}"),
    ]
    assert "déjà l'adresse de Lorys TOUX" in r[1].motif
    session.expire_all()
    assert session.get(Personne, victor.id).email_constate == f"victor.ghez@{DOMAINE}"
    assert session.get(Personne, loris.id).email_constate is None


def test_une_adresse_que_google_ne_connait_plus_n_est_pas_retenue(session, ecole):
    from backend.services.releve_adresses import retenir

    anne = ecole["inscrit"]("MARTIN", "Anne")
    (x,) = retenir(session, {f"anne.martin@{DOMAINE}": None}, {anne.id: f"anne.martin@{DOMAINE}"})
    assert not x.retenue and "n'existe plus" in x.motif


def test_le_journal_dit_qui_sans_les_adresses(session, ecole):
    from backend.models import Generation
    from backend.services.releve_adresses import enregistrer

    ecole["inscrit"]("MARTIN", "Anne")
    enregistrer(session, _relever(session, [_compte(f"anne.martin@{DOMAINE}", "MARTIN", "Anne")]))
    (g,) = session.query(Generation).filter_by(type_operation="identifiant", cible="google").all()
    trace = f"{g.parametres_json} {g.resultat_json} {g.notes}"
    assert "anne.martin" not in trace and "MARTIN" not in trace


# ---------------------------------------------------------------------------
# Le point d'entrée
# ---------------------------------------------------------------------------


class _Annuaire:
    def __init__(self, comptes):
        self.comptes = comptes

    def lister_utilisateurs(self, prefixe_ou=None):
        return list(self.comptes)


def test_le_point_d_entree_lit_google_et_enregistre(session, ecole, monkeypatch, tmp_db_path):
    from fastapi.testclient import TestClient

    from backend.main import app
    from backend.models import Personne

    anne = ecole["inscrit"]("MARTIN", "Anne")
    ecole["inscrit"]("GUEZ", "Victor", type="eleve")
    annuaire = _Annuaire([
        _compte(f"anne.martin@{DOMAINE}", "MARTIN", "Anne"),
        _compte(f"victor.ghez@{DOMAINE}", "GHEZ", "Victor", alias=[f"victor.guez@{DOMAINE}"]),
    ])
    monkeypatch.setattr("backend.routers.google_api.ClientGoogle", lambda config: annuaire)

    with TestClient(app) as client:
        r = client.post("/api/google/adresses/relever", json={})
    assert r.status_code == 200, r.text
    corps = r.json()
    assert (corps["nb_enregistrees"], len(corps["a_verifier"])) == (1, 1)
    assert "google_id" not in corps["relevees"][0]
    session.expire_all()
    assert session.get(Personne, anne.id).email_constate == f"anne.martin@{DOMAINE}"


class _AnnuaireComplet(_Annuaire):
    def lister_membres(self, groupe):
        return []


def test_la_coherence_releve_les_adresses_au_passage(session, ecole, monkeypatch, tmp_db_path):
    """Elle lit l'annuaire en entier pour croiser les classes : les adresses
    qu'il confirme s'enregistrent sans autre geste."""
    import base64

    from fastapi.testclient import TestClient

    from backend.main import app
    from backend.models import Personne

    lea = ecole["inscrit"]("ROUE", "Léa", type="eleve")
    annuaire = _AnnuaireComplet([_compte(f"lea.roue@{DOMAINE}", "ROUE", "Léa", ou="/3. NDK/NDK2027/2_1")])
    monkeypatch.setattr("backend.routers.concordance.ClientGoogle", lambda config: annuaire)
    fichier = f"﻿Num Badge;Nom;Prénom;Code classe\r\n{lea.badge};ROUE;Léa;2_1\r\n".encode("utf-8")

    with TestClient(app) as client:
        r = client.post("/api/concordance", json={
            "fichier_base64": base64.b64encode(fichier).decode(), "annee_id": ecole["an"].id,
        })
    assert r.status_code == 200, r.text
    assert r.json()["adresses_relevees"] == 1
    session.expire_all()
    assert session.get(Personne, lea.id).email_constate == f"lea.roue@{DOMAINE}"
