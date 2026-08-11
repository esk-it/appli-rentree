"""Tests des statistiques (Lot 13)."""
from __future__ import annotations

import pytest


@pytest.fixture()
def snap_factory(session):
    from backend.models import Snapshot

    def _creer(personne_id, annee_id, **kwargs):
        defaults = {"nom": "MARTIN", "prenom": "Jean", "classe": "3B"}
        defaults.update(kwargs)
        s = Snapshot(personne_id=personne_id, annee_scolaire_id=annee_id, **defaults)
        session.add(s)
        session.commit()
        return s

    return _creer


def test_stats_referentiel_base_vide(session):
    from backend.services.statistiques import stats_referentiel
    r = stats_referentiel(session)
    assert r.nb_personnes_total == 0
    assert r.nb_sites == 0
    assert r.nb_arbitrages_en_attente == 0


def test_stats_referentiel_avec_personnes(session, site_factory, personne_factory):
    from backend.services.statistiques import stats_referentiel

    site_factory("NDK")
    personne_factory(type="eleve", login="e1")
    personne_factory(type="eleve", login="e2")
    personne_factory(type="adulte", login="a1")

    r = stats_referentiel(session)
    assert r.nb_personnes_total == 3
    assert r.nb_eleves_total == 2
    assert r.nb_adultes_total == 1
    assert r.nb_sites == 1


def test_stats_referentiel_compte_arbitrages(session):
    from backend.services.arbitrage import creer_ou_reprendre, trancher
    from backend.services.statistiques import stats_referentiel

    a1 = creer_ou_reprendre(session, type_cas="collision_login", cle_cas="k1", contexte={})
    creer_ou_reprendre(session, type_cas="collision_login", cle_cas="k2", contexte={})
    trancher(session, a1.id, "suffixe:2")
    session.commit()

    r = stats_referentiel(session)
    assert r.nb_arbitrages_en_attente == 1
    assert r.nb_arbitrages_tranches == 1


def test_stats_annee_repartitions(session, site_factory, annee_factory, personne_factory, snap_factory):
    from backend.services.statistiques import stats_annee

    ndk = site_factory("NDK")
    su = site_factory("SU")
    annee = annee_factory("2025-2026")

    for i in range(3):
        p = personne_factory(site_id=ndk.id, login=f"ndk{i}")
        snap_factory(p.id, annee.id, regime="D", niveau="3")
    for i in range(2):
        p = personne_factory(site_id=su.id, login=f"su{i}")
        snap_factory(p.id, annee.id, regime="E", niveau="6")

    s = stats_annee(session, annee.id)

    assert s.nb_personnes == 5
    assert s.nb_eleves == 5
    par_site = {v.label: v.valeur for v in s.par_site}
    assert par_site == {"NDK": 3, "SU": 2}
    par_regime = {v.label: v.valeur for v in s.par_regime}
    assert par_regime == {"D": 3, "E": 2}
    par_niveau = {v.label: v.valeur for v in s.par_niveau}
    assert par_niveau == {"3": 3, "6": 2}


def test_stats_annee_ignore_snapshots_anciens(
    session, site_factory, annee_factory, personne_factory, snap_factory
):
    """Si une personne a 2 snapshots dans une même année, on retient le plus récent."""
    from datetime import datetime, timedelta
    from backend.models import Snapshot
    from backend.services.statistiques import stats_annee

    site = site_factory("NDK")
    annee = annee_factory()
    p = personne_factory(site_id=site.id, login="test1")

    ancien = Snapshot(personne_id=p.id, annee_scolaire_id=annee.id,
                      nom="P", prenom="P", regime="D",
                      date_ingestion=datetime.utcnow() - timedelta(days=10))
    session.add(ancien)
    snap_factory(p.id, annee.id, regime="E")  # dernier

    s = stats_annee(session, annee.id)
    par_regime = {v.label: v.valeur for v in s.par_regime}
    assert par_regime == {"E": 1}  # pas "D"


def test_stats_annee_introuvable(session):
    from backend.services.statistiques import stats_annee
    with pytest.raises(ValueError, match="introuvable"):
        stats_annee(session, 99999)
