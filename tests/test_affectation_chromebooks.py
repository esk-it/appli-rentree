"""Tests de l'affectation d'un Chromebook à quelqu'un.

Ce que ces tests protègent : **l'état suit l'affectation**. Une machine
`en_stock` attribuée à un prof est un état que rien ne contredit et que
personne ne remarque — jusqu'au jour où on la cherche dans l'armoire.
"""
from __future__ import annotations

from datetime import date

import pytest


def test_affecter_met_la_machine_en_service(session):
    from backend.services.parc_materiel import affecter, etat_du_parc

    affecter(session, "5CD1234ABC", a="Mme MARTIN")

    machines, synthese = etat_du_parc(session)
    m = next(m for m in machines if m.serie == "5CD1234ABC")
    assert m.attribue_a == "Mme MARTIN"
    assert m.attribue_le == date.today()
    assert m.etat == "en_service"
    assert synthese.en_service == 1


def test_reprendre_rend_la_machine_au_stock(session):
    from backend.services.parc_materiel import affecter, etat_du_parc

    affecter(session, "5CD1234ABC", a="Mme MARTIN")
    affecter(session, "5CD1234ABC", a=None)

    machines, synthese = etat_du_parc(session)
    m = next(m for m in machines if m.serie == "5CD1234ABC")
    assert m.attribue_a is None
    assert m.attribue_le is None
    assert m.etat == "en_stock"
    assert synthese.en_stock == 1


def test_reprendre_une_machine_hs_ne_la_repare_pas(session):
    """On la récupère du prof ; elle reste HS, et l'atelier décidera."""
    from backend.services.parc_materiel import affecter, changer_etat, etat_du_parc

    affecter(session, "5CD1234ABC", a="M. BERNARD")
    changer_etat(session, "5CD1234ABC", "hs")
    affecter(session, "5CD1234ABC", a=None)

    machines, _ = etat_du_parc(session)
    m = next(m for m in machines if m.serie == "5CD1234ABC")
    assert m.attribue_a is None
    assert m.etat == "hs"


def test_une_date_ancienne_est_conservee(session):
    """Confiée en septembre, saisie en novembre : c'est septembre qui compte."""
    from backend.services.parc_materiel import affecter, etat_du_parc

    affecter(session, "5CD1234ABC", a="Mme PETIT", depuis=date(2026, 9, 1))

    machines, _ = etat_du_parc(session)
    m = next(m for m in machines if m.serie == "5CD1234ABC")
    assert m.attribue_le == date(2026, 9, 1)


def test_un_porteur_vide_vaut_une_reprise(session):
    """Le champ laissé blanc ne doit pas créer un porteur nommé « »."""
    from backend.services.parc_materiel import affecter, etat_du_parc

    affecter(session, "5CD1234ABC", a="Mme PETIT")
    affecter(session, "5CD1234ABC", a="   ")

    machines, _ = etat_du_parc(session)
    m = next(m for m in machines if m.serie == "5CD1234ABC")
    assert m.attribue_a is None
    assert m.etat == "en_stock"


def test_une_serie_vide_est_refusee(session):
    from backend.services.parc_materiel import GesteImpossible, affecter

    with pytest.raises(GesteImpossible, match="numéro de série"):
        affecter(session, "  ", a="Mme MARTIN")


def test_affecter_cree_la_machine_si_elle_est_inconnue(session):
    """L'inventaire se fait en affectant : exiger une création préalable
    obligerait à saisir chaque machine deux fois."""
    from backend.services.parc_materiel import affecter, etat_du_parc

    machines_avant, _ = etat_du_parc(session)
    assert machines_avant == []

    affecter(session, "NEUVE001", a="M. ROBERT")

    machines, _ = etat_du_parc(session)
    assert [m.serie for m in machines] == ["NEUVE001"]
