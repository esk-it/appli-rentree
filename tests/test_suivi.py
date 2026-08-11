"""Tests du suivi / purge (Lot 12)."""
from __future__ import annotations

from datetime import date, timedelta

import pytest


@pytest.fixture()
def compte_factory(session):
    from backend.models import CompteCible

    def _creer(personne_id, cible="google", etat="actif", **kwargs):
        c = CompteCible(personne_id=personne_id, cible=cible, etat=etat, **kwargs)
        session.add(c)
        session.commit()
        return c

    return _creer


def test_marquer_sortant_google_met_en_quarantaine(session, personne_factory, compte_factory):
    from backend.services.suivi import marquer_sortant

    p = personne_factory(login="test1")
    compte_factory(p.id, cible="google", etat="actif")

    t = marquer_sortant(session, p.id, "google", aujourd_hui=date(2026, 1, 1))
    session.commit()

    assert t.etat_avant == "actif"
    assert t.etat_apres == "quarantaine"
    # 18 mois (~548 jours) plus tard
    assert t.date_prevue_purge == date(2026, 1, 1) + timedelta(days=548)


def test_marquer_sortant_koxo_passe_direct_a_purge(session, personne_factory, compte_factory):
    from backend.services.suivi import marquer_sortant

    p = personne_factory(login="test1")
    compte_factory(p.id, cible="koxo_ndk", etat="actif")

    t = marquer_sortant(session, p.id, "koxo_ndk", aujourd_hui=date(2026, 1, 1))
    session.commit()

    assert t.etat_apres == "purge"
    assert t.date_prevue_purge == date(2026, 1, 1)  # immédiat


def test_marquer_sortant_compte_introuvable(session, personne_factory):
    from backend.services.suivi import marquer_sortant

    p = personne_factory(login="test1")
    with pytest.raises(ValueError, match="introuvable"):
        marquer_sortant(session, p.id, "google")


def test_marquer_sortant_cible_invalide(session, personne_factory):
    from backend.services.suivi import marquer_sortant

    p = personne_factory(login="test1")
    with pytest.raises(ValueError, match="cible"):
        marquer_sortant(session, p.id, "fantome")


def test_comptes_a_purger_liste_les_echus(session, personne_factory, compte_factory):
    from backend.services.suivi import comptes_a_purger

    p1 = personne_factory(login="a")
    p2 = personne_factory(login="b")
    p3 = personne_factory(login="c")

    # Échéance dépassée
    compte_factory(p1.id, cible="google", etat="quarantaine",
                   date_prevue_purge=date(2024, 1, 1))
    # Encore en quarantaine, échéance future
    compte_factory(p2.id, cible="google", etat="quarantaine",
                   date_prevue_purge=date(2099, 1, 1))
    # Actif : pas concerné
    compte_factory(p3.id, cible="google", etat="actif")

    echus = comptes_a_purger(session, aujourd_hui=date(2026, 6, 1))
    ids = {c.personne_id for c in echus}
    assert ids == {p1.id}


def test_stats_suivi_agrege_par_cible_et_etat(session, personne_factory, compte_factory):
    from backend.services.suivi import stats_suivi

    p1 = personne_factory(login="a")
    p2 = personne_factory(login="b")
    p3 = personne_factory(login="c")

    compte_factory(p1.id, cible="google", etat="actif")
    compte_factory(p2.id, cible="google", etat="quarantaine",
                   date_prevue_purge=date(2024, 1, 1))
    compte_factory(p3.id, cible="koxo_ndk", etat="actif")

    s = stats_suivi(session, aujourd_hui=date(2026, 1, 1))
    assert s.par_cible["google"]["actif"] == 1
    assert s.par_cible["google"]["quarantaine"] == 1
    assert s.par_cible["koxo_ndk"]["actif"] == 1
    assert s.total_par_etat["actif"] == 2
    assert s.nb_purges_echues == 1


def test_lister_par_etat(session, personne_factory, compte_factory):
    from backend.services.suivi import lister_par_etat

    p1 = personne_factory(login="a")
    p2 = personne_factory(login="b")
    compte_factory(p1.id, cible="google", etat="quarantaine",
                   date_prevue_purge=date(2024, 1, 1))
    compte_factory(p2.id, cible="google", etat="actif")

    r = lister_par_etat(session, "quarantaine")
    assert len(r) == 1
    assert r[0][1].login == "a"


def test_lister_etat_invalide(session):
    from backend.services.suivi import lister_par_etat
    with pytest.raises(ValueError, match="etat"):
        lister_par_etat(session, "n_importe_quoi")
