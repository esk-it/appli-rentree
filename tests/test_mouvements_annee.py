"""Changer un élève de classe en cours d'année.

Toute la chaîne de rentrée suppose une campagne, traitée en bloc. La vie
scolaire se fait à l'unité : un changement de classe en octobre, une
inscription en janvier. Le faire à la main dans chaque système revenait à
espérer n'en oublier aucun.
"""
from __future__ import annotations

import pytest

from backend.services.mouvements_annee import (
    MouvementImpossible,
    planifier_changement_de_classe,
)


@pytest.fixture()
def snap_factory(session):
    from backend.models import Snapshot

    def _creer(personne_id, annee_id, classe=None, **kw):
        s = Snapshot(personne_id=personne_id, annee_scolaire_id=annee_id,
                     nom="DUPONT", prenom="Jean", classe=classe, **kw)
        session.add(s)
        session.commit()
        return s

    return _creer


@pytest.fixture()
def tc_factory(session):
    from backend.models import TableCorrespondance

    def _creer(site_id, code, groupe=None):
        tc = TableCorrespondance(
            site_id=site_id, classe_charlemagne_long=f"CLASSE {code}",
            classe_code_court=code,
            ou_pre_rentree="/3. NDK/NDK2027",
            ou_definitive=f"/3. NDK/NDK2027/{code}",
            groupe_google=groupe if groupe is not None else f"{code.lower()}@lekreisker.fr",
        )
        session.add(tc)
        session.commit()
        return tc

    return _creer


@pytest.fixture()
def contexte(session, site_factory, annee_factory, personne_factory,
             snap_factory, tc_factory):
    site = site_factory("NDK")
    annee = annee_factory("2026-2027")
    tc_factory(site.id, "6A")
    tc_factory(site.id, "6B")
    p = personne_factory(site_id=site.id, login="jdupont", id_charlemagne=100,
                         email_constate="jean.dupont@lekreisker.fr")
    snap_factory(p.id, annee.id, classe="6A")
    return site, annee, p


def _place(session, personne, ou):
    from backend.models import CompteCible

    session.add(CompteCible(personne_id=personne.id, cible="google",
                            etat="cree", ou_appliquee=ou))
    session.commit()


# ---------------------------------------------------------------------------
# Le plan
# ---------------------------------------------------------------------------


def test_le_plan_nomme_les_deux_groupes_et_la_nouvelle_ou(session, contexte):
    _, annee, p = contexte
    _place(session, p, "/3. NDK/NDK2027/6A")

    plan = planifier_changement_de_classe(
        session, personne_id=p.id, nouvelle_classe="6B", annee_id=annee.id
    )

    assert plan.classe_avant == "6A"
    assert plan.classe_apres == "6B"
    assert plan.ou_apres == "/3. NDK/NDK2027/6B"
    assert plan.deplacement_utile is True
    assert plan.groupe_quitte == "6a@lekreisker.fr"
    assert plan.groupe_rejoint == "6b@lekreisker.fr"


def test_en_pre_rentree_lou_ne_change_pas(session, contexte):
    """Tout le monde attend dans la même unité : la classe n'y change rien.

    C'est le jour J qui répartit. Déplacer maintenant ferait sortir l'élève
    de l'attente avant les autres.
    """
    _, annee, p = contexte
    _place(session, p, "/3. NDK/NDK2027")

    plan = planifier_changement_de_classe(
        session, personne_id=p.id, nouvelle_classe="6B", annee_id=annee.id
    )

    assert plan.ou_apres == "/3. NDK/NDK2027"
    assert plan.deplacement_utile is False
    # Les groupes, eux, suivent la classe dès maintenant.
    assert plan.groupe_rejoint == "6b@lekreisker.fr"
    assert plan.a_un_effet


def test_le_plan_nomme_ce_qui_reste_manuel(session, contexte):
    """Un écran qui ferait 60 % du travail sans nommer le reste serait pire."""
    _, annee, p = contexte

    plan = planifier_changement_de_classe(
        session, personne_id=p.id, nouvelle_classe="6B", annee_id=annee.id
    )

    systemes = {r.systeme for r in plan.reste_a_faire}
    assert systemes == {"KoXo", "PMB", "JPM"}
    koxo = next(r for r in plan.reste_a_faire if r.systeme == "KoXo")
    assert "jdupont" in koxo.geste and "6B" in koxo.geste


def test_la_simulation_ne_touche_a_rien(session, contexte):
    _, annee, p = contexte

    plan = planifier_changement_de_classe(
        session, personne_id=p.id, nouvelle_classe="6B", annee_id=annee.id
    )

    assert plan.applique is False
    session.refresh(p)
    assert p.classe != "6B"


# ---------------------------------------------------------------------------
# L'application
# ---------------------------------------------------------------------------


def test_le_referentiel_bouge_avant_google(session, contexte):
    """Sans lui, la bascule du jour J ramènerait l'élève en 6A."""
    from backend.models import Snapshot

    _, annee, p = contexte

    plan = planifier_changement_de_classe(
        session, personne_id=p.id, nouvelle_classe="6B", annee_id=annee.id,
        mode="reel",
    )
    session.commit()

    assert plan.applique is True
    session.refresh(p)
    assert p.classe == "6B"

    dernier = (
        session.query(Snapshot)
        .filter_by(personne_id=p.id, annee_scolaire_id=annee.id)
        .order_by(Snapshot.id.desc())
        .first()
    )
    assert dernier.classe == "6B"
    assert dernier.classe_precedente == "6A", "d'où il vient reste lisible"


def test_lancienne_photographie_nest_pas_effacee(session, contexte):
    """Les photographies s'ajoutent : l'historique de l'année reste entier."""
    from backend.models import Snapshot

    _, annee, p = contexte
    planifier_changement_de_classe(
        session, personne_id=p.id, nouvelle_classe="6B", annee_id=annee.id,
        mode="reel",
    )
    session.commit()

    classes = [
        s.classe
        for s in session.query(Snapshot)
        .filter_by(personne_id=p.id, annee_scolaire_id=annee.id)
        .order_by(Snapshot.id)
    ]
    assert classes == ["6A", "6B"]


# ---------------------------------------------------------------------------
# Les refus
# ---------------------------------------------------------------------------


def test_une_classe_absente_de_la_table_est_refusee(session, contexte):
    """Ni son OU ni son groupe ne sont connus : rien ne se devine."""
    _, annee, p = contexte

    with pytest.raises(MouvementImpossible, match="pas déclarée dans la Table"):
        planifier_changement_de_classe(
            session, personne_id=p.id, nouvelle_classe="6Z", annee_id=annee.id
        )


def test_un_eleve_sans_photographie_est_refuse(
    session, site_factory, annee_factory, personne_factory, tc_factory
):
    site = site_factory("NDK")
    annee = annee_factory("2026-2027")
    tc_factory(site.id, "6B")
    p = personne_factory(site_id=site.id, login="sansphoto", id_charlemagne=900)

    with pytest.raises(MouvementImpossible, match="photographie"):
        planifier_changement_de_classe(
            session, personne_id=p.id, nouvelle_classe="6B", annee_id=annee.id
        )


def test_la_meme_classe_est_refusee(session, contexte):
    _, annee, p = contexte

    with pytest.raises(MouvementImpossible, match="déjà en 6A"):
        planifier_changement_de_classe(
            session, personne_id=p.id, nouvelle_classe="6A", annee_id=annee.id
        )


def test_une_personne_inconnue_est_refusee(session, contexte):
    _, annee, _ = contexte

    with pytest.raises(MouvementImpossible, match="Personne introuvable"):
        planifier_changement_de_classe(
            session, personne_id=99999, nouvelle_classe="6B", annee_id=annee.id
        )


# ---------------------------------------------------------------------------
# Les avertissements
# ---------------------------------------------------------------------------


def test_une_classe_sans_groupe_est_signalee(
    session, site_factory, annee_factory, personne_factory, snap_factory,
    tc_factory
):
    site = site_factory("NDK")
    annee = annee_factory("2026-2027")
    tc_factory(site.id, "6A")
    tc_factory(site.id, "6B", groupe="")
    p = personne_factory(site_id=site.id, login="jdupont", id_charlemagne=100,
                         email_constate="jean.dupont@lekreisker.fr")
    snap_factory(p.id, annee.id, classe="6A")

    plan = planifier_changement_de_classe(
        session, personne_id=p.id, nouvelle_classe="6B", annee_id=annee.id
    )
    assert any("aucune adresse de groupe" in a for a in plan.avertissements)


def test_un_compte_jamais_place_est_signale(session, contexte):
    """Le programme ne sait pas d'où il part : autant le dire."""
    _, annee, p = contexte

    plan = planifier_changement_de_classe(
        session, personne_id=p.id, nouvelle_classe="6B", annee_id=annee.id
    )
    assert any("jamais placé" in a for a in plan.avertissements)


# ---------------------------------------------------------------------------
# La reprise
# ---------------------------------------------------------------------------


def test_rejouer_un_mouvement_deja_ecrit_reste_possible(session, contexte):
    """Google peut échouer après que le référentiel a bougé.

    Refuser la reprise pour la raison même qui prouve que la première
    moitié a réussi laisserait l'élève à moitié déplacé, sans recours.
    """
    _, annee, p = contexte
    planifier_changement_de_classe(
        session, personne_id=p.id, nouvelle_classe="6B", annee_id=annee.id,
        mode="reel",
    )
    session.commit()

    plan = planifier_changement_de_classe(
        session, personne_id=p.id, nouvelle_classe="6B", annee_id=annee.id,
        reprise=True,
    )
    assert plan.classe_avant == "6A", "l'origine se lit dans la photographie précédente"
    assert plan.classe_apres == "6B"
    assert plan.groupe_quitte == "6a@lekreisker.fr"
    assert plan.groupe_rejoint == "6b@lekreisker.fr"


def test_une_reprise_ne_reecrit_pas_le_referentiel(session, contexte):
    from backend.models import Snapshot

    _, annee, p = contexte
    planifier_changement_de_classe(
        session, personne_id=p.id, nouvelle_classe="6B", annee_id=annee.id,
        mode="reel",
    )
    session.commit()
    avant = session.query(Snapshot).filter_by(
        personne_id=p.id, annee_scolaire_id=annee.id
    ).count()

    plan = planifier_changement_de_classe(
        session, personne_id=p.id, nouvelle_classe="6B", annee_id=annee.id,
        mode="reel", reprise=True,
    )
    session.commit()

    apres = session.query(Snapshot).filter_by(
        personne_id=p.id, annee_scolaire_id=annee.id
    ).count()
    assert apres == avant, "aucune photographie ajoutée"
    assert any("déjà ce changement" in a for a in plan.avertissements)


def test_sans_reprise_le_refus_tient(session, contexte):
    _, annee, p = contexte
    planifier_changement_de_classe(
        session, personne_id=p.id, nouvelle_classe="6B", annee_id=annee.id,
        mode="reel",
    )
    session.commit()

    with pytest.raises(MouvementImpossible, match="déjà en 6B"):
        planifier_changement_de_classe(
            session, personne_id=p.id, nouvelle_classe="6B", annee_id=annee.id
        )


# ---------------------------------------------------------------------------
# L'endpoint
# ---------------------------------------------------------------------------


@pytest.fixture()
def client(tmp_db_path):
    from fastapi.testclient import TestClient

    from backend.main import app

    with TestClient(app) as c:
        yield c


class _GoogleFactice:
    """Consigne ce qu'on lui demande ; échoue sur ce qu'on lui dit d'échouer.

    `appartenances` dit dans quels groupes l'élève se trouve **vraiment** :
    c'est de là que se déduisent les retraits, et non de sa classe passée.
    """

    def __init__(self, echoue=(), appartenances=()):
        self.echoue = set(echoue)
        self.appartenances = list(appartenances)
        self.deplacements, self.retraits, self.ajouts = [], [], []

    def lister_groupes_de(self, email):
        if "lister_groupes" in self.echoue:
            raise RuntimeError("lecture des groupes refusée")
        return list(self.appartenances)

    def appliquer_operation(self, op):
        if "deplacer" in self.echoue:
            raise RuntimeError("unité d'organisation inconnue")
        self.deplacements.append((op.email, op.ou_visee))

    def retirer_membre(self, groupe, email):
        if "retirer" in self.echoue:
            raise RuntimeError("membre absent du groupe")
        self.retraits.append((groupe, email))

    def ajouter_membre(self, groupe, email):
        if "ajouter" in self.echoue:
            raise RuntimeError("groupe introuvable")
        self.ajouts.append((groupe, email))


@pytest.fixture()
def google():
    """Le client est fourni au service, pas construit par lui : aucun
    monkeypatch n'est nécessaire pour l'éprouver."""
    return _GoogleFactice()


def test_lendpoint_simule_sans_toucher_a_google(session, client, contexte, google):
    _, annee, p = contexte
    _place(session, p, "/3. NDK/NDK2027/6A")

    r = client.post("/api/mouvements/changer-classe", json={
        "personne_id": p.id, "nouvelle_classe": "6B", "annee_id": annee.id,
    })
    assert r.status_code == 200, r.text
    corps = r.json()
    assert corps["applique"] is False
    assert corps["operations"] == []
    assert google.deplacements == [] and google.ajouts == []


def test_le_deplacement_puis_lechange_des_groupes(session, contexte):
    """On déplace, on rejoint, puis on quitte ce qu'on occupait à tort."""
    from backend.services.mouvements_annee import appliquer_dans_google

    google = _GoogleFactice(appartenances=["6a@lekreisker.fr"])

    _, annee, p = contexte
    _place(session, p, "/3. NDK/NDK2027/6A")
    plan = planifier_changement_de_classe(
        session, personne_id=p.id, nouvelle_classe="6B", annee_id=annee.id,
        mode="reel",
    )
    ops = appliquer_dans_google(session, plan, google)
    session.commit()

    assert all(o.reussie for o in ops)
    assert google.deplacements == [
        ("jean.dupont@lekreisker.fr", "/3. NDK/NDK2027/6B")
    ]
    assert google.retraits == [("6a@lekreisker.fr", "jean.dupont@lekreisker.fr")]
    assert google.ajouts == [("6b@lekreisker.fr", "jean.dupont@lekreisker.fr")]


def test_on_quitte_le_groupe_ou_lon_est_pas_celui_quon_suppose(
    session, contexte, tc_factory
):
    """Le 4 septembre 2026, les quarante-neuf alignements ont tous rendu
    « Resource Not Found: memberKey » : on retirait l'élève de la classe
    qu'il avait quittée en juin, alors qu'il fallait le sortir de celle où
    il avait été mis par erreur. Chacun restait dans deux groupes."""
    from backend.services.mouvements_annee import appliquer_dans_google

    site, annee, p = contexte
    tc_factory(site.id, "6C")
    # Il n'est plus en 6A — on l'a rangé par erreur en 6C.
    google = _GoogleFactice(appartenances=["6c@lekreisker.fr"])
    _place(session, p, "/3. NDK/NDK2027/6A")
    plan = planifier_changement_de_classe(
        session, personne_id=p.id, nouvelle_classe="6B", annee_id=annee.id,
        mode="reel",
    )
    ops = appliquer_dans_google(session, plan, google)

    assert all(o.reussie for o in ops)
    assert google.retraits == [("6c@lekreisker.fr", "jean.dupont@lekreisker.fr")], (
        "on sort du groupe réellement occupé"
    )
    assert google.ajouts == [("6b@lekreisker.fr", "jean.dupont@lekreisker.fr")]


def test_un_groupe_hors_table_nest_jamais_touche(session, contexte, tc_factory):
    """Listes de service, groupes de professeurs : ils ne se déduisent
    d'aucune classe, et les toucher retirerait un accès qu'on ignore."""
    from backend.services.mouvements_annee import appliquer_dans_google

    site, annee, p = contexte
    tc_factory(site.id, "6C")
    google = _GoogleFactice(
        appartenances=["6c@lekreisker.fr", "tous-les-eleves@lekreisker.fr"]
    )
    _place(session, p, "/3. NDK/NDK2027/6A")
    plan = planifier_changement_de_classe(
        session, personne_id=p.id, nouvelle_classe="6B", annee_id=annee.id,
        mode="reel",
    )
    appliquer_dans_google(session, plan, google)

    quittes = {g for g, _ in google.retraits}
    assert quittes == {"6c@lekreisker.fr"}
    assert "tous-les-eleves@lekreisker.fr" not in quittes


def test_le_groupe_rejoint_nest_pas_retire_dans_la_foulee(session, contexte):
    """On rejoint avant de quitter : sans exclusion explicite, le groupe
    qu'on vient d'obtenir figurerait parmi ceux qu'on occupe."""
    from backend.services.mouvements_annee import appliquer_dans_google

    google = _GoogleFactice(appartenances=["6b@lekreisker.fr"])
    _, annee, p = contexte
    _place(session, p, "/3. NDK/NDK2027/6A")
    plan = planifier_changement_de_classe(
        session, personne_id=p.id, nouvelle_classe="6B", annee_id=annee.id,
        mode="reel",
    )
    appliquer_dans_google(session, plan, google)

    assert google.retraits == []


def test_une_lecture_de_groupes_refusee_se_dit_sans_tout_arreter(session, contexte):
    """Le déplacement et l'ajout ont eu lieu : les taire pour un échec de
    lecture ferait croire que rien n'a bougé."""
    from backend.services.mouvements_annee import appliquer_dans_google

    google = _GoogleFactice(echoue={"lister_groupes"})
    _, annee, p = contexte
    _place(session, p, "/3. NDK/NDK2027/6A")
    plan = planifier_changement_de_classe(
        session, personne_id=p.id, nouvelle_classe="6B", annee_id=annee.id,
        mode="reel",
    )
    ops = appliquer_dans_google(session, plan, google)

    assert all(o.reussie for o in ops)
    assert google.ajouts, "l'ajout a bien eu lieu"
    assert any("groupe d'une autre classe" in a for a in plan.avertissements)


def test_un_echec_de_groupe_nannule_pas_le_deplacement(session, contexte):
    """Chaque opération rend compte seule : on sait laquelle reprendre."""
    from backend.services.mouvements_annee import appliquer_dans_google

    faux = _GoogleFactice(echoue={"ajouter"})
    _, annee, p = contexte
    _place(session, p, "/3. NDK/NDK2027/6A")
    plan = planifier_changement_de_classe(
        session, personne_id=p.id, nouvelle_classe="6B", annee_id=annee.id,
        mode="reel",
    )
    ops = {o.libelle.split()[0]: o for o in appliquer_dans_google(session, plan, faux)}

    assert ops["Déplacer"].reussie is True
    assert ops["Ajouter"].reussie is False
    assert "groupe introuvable" in ops["Ajouter"].message
    assert faux.deplacements, "le déplacement a bien eu lieu"


def test_lou_appliquee_est_memorisee(session, contexte, google):
    """Sans cette trace, la bascule reproposerait le déplacement."""
    from backend.models import CompteCible
    from backend.services.mouvements_annee import appliquer_dans_google

    _, annee, p = contexte
    _place(session, p, "/3. NDK/NDK2027/6A")
    plan = planifier_changement_de_classe(
        session, personne_id=p.id, nouvelle_classe="6B", annee_id=annee.id,
        mode="reel",
    )
    appliquer_dans_google(session, plan, google)
    session.commit()

    compte = session.query(CompteCible).filter_by(
        personne_id=p.id, cible="google"
    ).one()
    assert compte.ou_appliquee == "/3. NDK/NDK2027/6B"


def test_un_deplacement_rate_ne_memorise_rien(session, contexte):
    """Mémoriser une OU qu'on n'a pas obtenue ferait mentir la bascule."""
    from backend.models import CompteCible
    from backend.services.mouvements_annee import appliquer_dans_google

    faux = _GoogleFactice(echoue={"deplacer"})
    _, annee, p = contexte
    _place(session, p, "/3. NDK/NDK2027/6A")
    plan = planifier_changement_de_classe(
        session, personne_id=p.id, nouvelle_classe="6B", annee_id=annee.id,
        mode="reel",
    )
    appliquer_dans_google(session, plan, faux)
    session.commit()

    compte = session.query(CompteCible).filter_by(
        personne_id=p.id, cible="google"
    ).one()
    assert compte.ou_appliquee == "/3. NDK/NDK2027/6A"


def test_sans_adresse_rien_nest_tente(session, site_factory, annee_factory,
                                      personne_factory, snap_factory,
                                      tc_factory, google):
    from backend.services.mouvements_annee import appliquer_dans_google

    site = site_factory("NDK")
    annee = annee_factory("2026-2027")
    tc_factory(site.id, "6A")
    tc_factory(site.id, "6B")
    # Sans site ni adresse constatée, le programme ne devine pas de domaine.
    p = personne_factory(site_id=None, login="sansmail", id_charlemagne=777)
    snap_factory(p.id, annee.id, classe="6A")

    plan = planifier_changement_de_classe(
        session, personne_id=p.id, nouvelle_classe="6B", annee_id=annee.id
    )
    assert appliquer_dans_google(session, plan, google) == []
    assert google.deplacements == []


def test_lendpoint_refuse_une_classe_hors_table_avec_409(
    session, client, contexte, google
):
    _, annee, p = contexte

    r = client.post("/api/mouvements/changer-classe", json={
        "personne_id": p.id, "nouvelle_classe": "6Z", "annee_id": annee.id,
    })
    assert r.status_code == 409
    assert "Table" in r.json()["detail"]


def test_on_peut_ne_bouger_que_le_referentiel(session, client, contexte, google):
    """Pour corriger KoXo à la main d'abord, et laisser Google pour après."""
    _, annee, p = contexte
    _place(session, p, "/3. NDK/NDK2027/6A")

    r = client.post("/api/mouvements/changer-classe", json={
        "personne_id": p.id, "nouvelle_classe": "6B", "annee_id": annee.id,
        "mode": "reel", "appliquer_google": False,
    })
    assert r.status_code == 200, r.text
    assert r.json()["operations"] == []
    assert google.deplacements == []
    session.refresh(p)
    assert p.classe == "6B"
