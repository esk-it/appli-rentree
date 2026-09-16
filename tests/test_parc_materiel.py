"""Tests du parc : l'état des machines, la réserve de pièces, les prêts.

Ce qui distingue ce module d'un inventaire, c'est qu'une machine morte y
reste utile. Les tests portent donc surtout sur le croisement des organes
et sur le prélèvement, qui écrit des deux côtés.
"""
from __future__ import annotations

from datetime import date, timedelta

import pytest


@pytest.fixture()
def parc(session):
    """Fabrique des machines déjà cassées, en un appel."""
    from backend.services.parc_materiel import changer_etat, declarer_panne

    def _machine(serie, *organes, etat="hs"):
        for organe in organes:
            declarer_panne(session, serie, organe)
        changer_etat(session, serie, etat)
        return serie

    return _machine


# ---------------------------------------------------------------------------
# L'état du parc
# ---------------------------------------------------------------------------


def test_le_parc_se_compte_par_etat(session, parc):
    from backend.services.parc_materiel import changer_etat, etat_du_parc

    changer_etat(session, "SN-STOCK", "en_stock")
    changer_etat(session, "SN-SERVICE", "en_service")
    parc("SN-MORTE", "batterie")

    machines, synthese = etat_du_parc(session)
    assert len(machines) == 3
    assert (synthese.en_stock, synthese.en_service, synthese.hs) == (1, 1, 1)


def test_declarer_une_panne_passe_la_machine_hs(session):
    from backend.services.parc_materiel import declarer_panne, etat_du_parc

    declarer_panne(session, "SN-1", "ecran")
    machines, _ = etat_du_parc(session)
    assert machines[0].etat == "hs"
    assert machines[0].pannes_ouvertes == ["ecran"]


def test_une_panne_peut_se_noter_sans_retirer_du_service(session):
    """Une charnière fendue qui tient encore n'immobilise pas la machine."""
    from backend.services.parc_materiel import declarer_panne, etat_du_parc

    declarer_panne(session, "SN-1", "charniere", passer_hs=False)
    machines, _ = etat_du_parc(session)
    assert machines[0].etat == "en_service"
    assert machines[0].pannes_ouvertes == ["charniere"]


def test_deux_fois_le_meme_organe_est_refuse(session):
    from backend.services.parc_materiel import GesteImpossible, declarer_panne

    declarer_panne(session, "SN-1", "clavier")
    with pytest.raises(GesteImpossible, match="déjà une panne ouverte"):
        declarer_panne(session, "SN-1", "clavier")


def test_organe_hors_liste_refuse(session):
    from backend.services.parc_materiel import GesteImpossible, declarer_panne

    with pytest.raises(GesteImpossible, match="Organe inconnu"):
        declarer_panne(session, "SN-1", "le machin du dessous")


# ---------------------------------------------------------------------------
# L'atelier — la raison d'être du module
# ---------------------------------------------------------------------------


def test_deux_mortes_complementaires_font_une_vivante(session, parc):
    """Le cas qui justifie tout : batterie d'un côté, clavier de l'autre."""
    from backend.services.parc_materiel import analyser_atelier

    parc("SN-BATTERIE", "batterie")
    parc("SN-CLAVIER", "clavier")

    a = analyser_atelier(session)
    assert a.nb_remontables == 1
    r = a.remontages[0]
    # On répare l'une **avec** l'autre : le sens importe peu, le couple non.
    assert {r.serie, *r.donneurs.values()} == {"SN-BATTERIE", "SN-CLAVIER"}
    assert list(r.donneurs) == r.organes_manquants


def test_on_repare_la_moins_abimee(session, parc):
    """Une machine à trois pannes finira donneuse quoi qu'il arrive."""
    from backend.services.parc_materiel import analyser_atelier

    parc("SN-LEGERE", "clavier")
    parc("SN-EPAVE", "ecran", "batterie", "trackpad")

    a = analyser_atelier(session)
    assert [r.serie for r in a.remontages] == ["SN-LEGERE"]
    assert a.remontages[0].donneurs == {"clavier": "SN-EPAVE"}


def test_un_donneur_ne_sert_quune_fois(session, parc):
    """Sacrifier la même machine deux fois donnerait un plan infaisable."""
    from backend.services.parc_materiel import analyser_atelier

    parc("SN-A", "clavier")
    parc("SN-B", "clavier")
    parc("SN-UNIQUE", "ecran")  # seule à porter un clavier intact

    a = analyser_atelier(session)
    assert a.nb_remontables == 1
    bloquees = dict(a.bloquees)
    assert "clavier" in bloquees.get("SN-B", []) or "clavier" in bloquees.get("SN-A", [])


def test_une_machine_reparee_nest_pas_redemontee(session, parc):
    from backend.services.parc_materiel import analyser_atelier

    parc("SN-A", "batterie")
    parc("SN-B", "clavier")
    parc("SN-C", "ecran")

    a = analyser_atelier(session)
    reparees = {r.serie for r in a.remontages}
    donneurs = {d for r in a.remontages for d in r.donneurs.values()}
    assert not (reparees & donneurs), "une machine réparée sert de donneuse"


def test_organe_introuvable_bloque_et_se_dit(session, parc):
    from backend.services.parc_materiel import analyser_atelier

    parc("SN-SEULE", "carte_mere")

    a = analyser_atelier(session)
    assert a.nb_remontables == 0
    assert a.bloquees == [("SN-SEULE", ["carte_mere"])]


def test_autre_ne_se_croise_pas(session, parc):
    """Deux « autre » ne font pas une pièce : on ne promet pas l'impossible.

    La machine reste utile comme donneuse — ce qu'on refuse, c'est de la
    déclarer remontable alors qu'on ne sait même pas ce qui lui manque.
    """
    from backend.services.parc_materiel import analyser_atelier

    parc("SN-FLOU", "autre")
    parc("SN-AUSSI-FLOUE", "autre")

    a = analyser_atelier(session)
    assert a.nb_remontables == 0
    assert dict(a.bloquees) == {"SN-AUSSI-FLOUE": ["autre"], "SN-FLOU": ["autre"]}
    # Et l'organe ne figure pas dans la réserve : il n'est pas une pièce.
    assert "autre" not in a.organes_disponibles


def test_les_organes_disponibles_se_comptent(session, parc):
    from backend.services.parc_materiel import analyser_atelier

    parc("SN-A", "batterie")
    parc("SN-B", "batterie")

    a = analyser_atelier(session)
    # Deux machines HS, aucune n'a de clavier mort : deux claviers en réserve.
    assert a.organes_disponibles["clavier"] == 2
    assert "batterie" not in a.organes_disponibles


# ---------------------------------------------------------------------------
# Le prélèvement — deux écritures, un geste
# ---------------------------------------------------------------------------


def test_prelever_repare_lune_et_ampute_lautre(session, parc):
    from backend.services.parc_materiel import etat_du_parc, prelever

    parc("SN-RECEVEUSE", "clavier")
    parc("SN-DONNEUSE", "ecran")

    prelever(session, depuis="SN-DONNEUSE", vers="SN-RECEVEUSE", organe="clavier")

    par_serie = {m.serie: m for m in etat_du_parc(session)[0]}
    # La receveuse n'a plus rien d'ouvert, donc elle remarche.
    assert par_serie["SN-RECEVEUSE"].pannes_ouvertes == []
    assert par_serie["SN-RECEVEUSE"].etat == "en_stock"
    # La donneuse a perdu son clavier, et on sait où il est parti.
    assert sorted(par_serie["SN-DONNEUSE"].pannes_ouvertes) == ["clavier", "ecran"]


def test_le_prelevement_dit_ou_lorgane_est_parti(session, parc):
    from backend.models import PanneChromebook
    from backend.services.parc_materiel import prelever

    parc("SN-RECEVEUSE", "batterie")
    parc("SN-DONNEUSE", "ecran")
    prelever(session, depuis="SN-DONNEUSE", vers="SN-RECEVEUSE", organe="batterie")

    creee = (
        session.query(PanneChromebook)
        .filter_by(serie="SN-DONNEUSE", organe="batterie")
        .one()
    )
    assert creee.prelevee_pour == "SN-RECEVEUSE"

    resolue = (
        session.query(PanneChromebook)
        .filter_by(serie="SN-RECEVEUSE", organe="batterie")
        .one()
    )
    assert resolue.resolution == "piece_prelevee"
    assert resolue.resolue_le is not None


def test_une_receveuse_encore_cassee_reste_hs(session, parc):
    from backend.services.parc_materiel import etat_du_parc, prelever

    parc("SN-RECEVEUSE", "clavier", "ecran")
    parc("SN-DONNEUSE", "batterie")
    prelever(session, depuis="SN-DONNEUSE", vers="SN-RECEVEUSE", organe="clavier")

    par_serie = {m.serie: m for m in etat_du_parc(session)[0]}
    assert par_serie["SN-RECEVEUSE"].pannes_ouvertes == ["ecran"]
    assert par_serie["SN-RECEVEUSE"].etat == "hs"


def test_prelever_un_organe_deja_mort_est_refuse(session, parc):
    from backend.services.parc_materiel import GesteImpossible, prelever

    parc("SN-RECEVEUSE", "clavier")
    parc("SN-DONNEUSE", "clavier")

    with pytest.raises(GesteImpossible, match="rien à en tirer"):
        prelever(session, depuis="SN-DONNEUSE", vers="SN-RECEVEUSE", organe="clavier")


def test_prelever_sans_panne_a_reparer_est_refuse(session, parc):
    from backend.services.parc_materiel import GesteImpossible, prelever

    parc("SN-RECEVEUSE", "clavier")
    parc("SN-DONNEUSE", "ecran")

    with pytest.raises(GesteImpossible, match="rien à y remplacer"):
        prelever(session, depuis="SN-DONNEUSE", vers="SN-RECEVEUSE", organe="batterie")


def test_une_machine_ne_se_preleve_pas_sur_elle_meme(session, parc):
    from backend.services.parc_materiel import GesteImpossible, prelever

    parc("SN-A", "clavier")
    with pytest.raises(GesteImpossible, match="elle-même"):
        prelever(session, depuis="SN-A", vers="SN-A", organe="clavier")


def test_reparer_pour_de_vrai_remet_en_stock(session, parc):
    from backend.models import PanneChromebook
    from backend.services.parc_materiel import etat_du_parc, resoudre_panne

    parc("SN-A", "batterie")
    panne = session.query(PanneChromebook).filter_by(serie="SN-A").one()
    resoudre_panne(session, panne.id, "reparee")

    machines, _ = etat_du_parc(session)
    assert machines[0].etat == "en_stock"
    assert machines[0].pannes_ouvertes == []


# ---------------------------------------------------------------------------
# Accessoires et prêts
# ---------------------------------------------------------------------------


def test_un_pret_sort_laccessoire_du_stock(session):
    from backend.services.parc_materiel import (
        enregistrer_accessoire,
        etat_du_stock,
        preter,
    )

    enregistrer_accessoire(session, "CHG-001")
    enregistrer_accessoire(session, "CHG-002")
    preter(session, "CHG-001", a_qui="DUPONT Jean")

    stock = etat_du_stock(session)
    assert stock.par_type["chargeur"] == {"prete": 1, "en_stock": 1}
    dehors = next(a for a in stock.accessoires if a.serie == "CHG-001")
    assert dehors.prete_a == "DUPONT Jean"


def test_un_retard_se_voit(session):
    from backend.services.parc_materiel import (
        enregistrer_accessoire,
        etat_du_stock,
        preter,
    )

    enregistrer_accessoire(session, "CHG-001")
    enregistrer_accessoire(session, "CHG-002")
    preter(session, "CHG-001", a_qui="Tardif", retour_prevu_le=date.today() - timedelta(days=3))
    preter(session, "CHG-002", a_qui="À l'heure", retour_prevu_le=date.today() + timedelta(days=3))

    en_retard = etat_du_stock(session).en_retard
    assert [a.serie for a in en_retard] == ["CHG-001"]


def test_preter_deux_fois_le_meme_est_refuse(session):
    from backend.services.parc_materiel import (
        GesteImpossible,
        enregistrer_accessoire,
        preter,
    )

    enregistrer_accessoire(session, "CHG-001")
    preter(session, "CHG-001", a_qui="Premier")
    with pytest.raises(GesteImpossible, match="chez Premier"):
        preter(session, "CHG-001", a_qui="Second")


def test_un_accessoire_peut_revenir_casse(session):
    from backend.services.parc_materiel import (
        enregistrer_accessoire,
        etat_du_stock,
        preter,
        rendre,
    )

    enregistrer_accessoire(session, "CHG-001")
    preter(session, "CHG-001", a_qui="Quelqu'un")
    rendre(session, "CHG-001", etat="hs")

    stock = etat_du_stock(session)
    assert stock.par_type["chargeur"] == {"hs": 1}
    assert stock.accessoires[0].prete_a is None


def test_preter_un_accessoire_hs_est_refuse(session):
    from backend.services.parc_materiel import (
        GesteImpossible,
        enregistrer_accessoire,
        preter,
        rendre,
    )

    enregistrer_accessoire(session, "CHG-001")
    preter(session, "CHG-001", a_qui="Quelqu'un")
    rendre(session, "CHG-001", etat="hs")
    with pytest.raises(GesteImpossible, match="hs"):
        preter(session, "CHG-001", a_qui="Un autre")


def test_un_numero_de_serie_ne_sert_quune_fois(session):
    from backend.services.parc_materiel import GesteImpossible, enregistrer_accessoire

    enregistrer_accessoire(session, "CHG-001")
    with pytest.raises(GesteImpossible, match="déjà enregistré"):
        enregistrer_accessoire(session, "CHG-001")
