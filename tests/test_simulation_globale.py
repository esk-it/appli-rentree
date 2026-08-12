"""Tests du moteur de simulation transverse (Lot 7)."""
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


def test_simulation_vide_si_aucune_donnee(session, annee_factory):
    from backend.services.simulation_globale import simuler_globalement

    an1 = annee_factory("2024-2025")
    an2 = annee_factory("2025-2026")

    r = simuler_globalement(session, an1.id, an2.id)

    assert r.lignes == []
    assert r.nb_arbitrages_en_attente == 0
    assert r.est_pret_a_executer is True


def test_simulation_compte_nouveaux(
    session, site_factory, annee_factory, personne_factory, snap_factory
):
    """Un nouveau élève à annee_cible → +1 en KoXo et +1 en Google."""
    from backend.services.simulation_globale import simuler_globalement

    site = site_factory("NDK")
    an_prec = annee_factory("2024-2025")
    an_cour = annee_factory("2025-2026")

    p = personne_factory(site_id=site.id, nom="NEUF", login="neuf")
    snap_factory(p.id, an_cour.id, classe="3B")

    r = simuler_globalement(session, an_prec.id, an_cour.id)

    # Une ligne KoXo + une ligne Google, chacune avec nouveaux=1
    koxo = [l for l in r.lignes if l.cible == "koxo" and l.site_nom == "NDK"]
    google = [l for l in r.lignes if l.cible == "google" and l.site_nom == "NDK"]
    assert len(koxo) == 1 and koxo[0].nouveaux == 1
    assert len(google) == 1 and google[0].nouveaux == 1


def test_simulation_totaux_par_cible(
    session, site_factory, annee_factory, personne_factory, snap_factory
):
    """L'agrégation par cible somme les compteurs de tous les sites/types."""
    from backend.services.simulation_globale import simuler_globalement

    ndk = site_factory("NDK")
    su = site_factory("SU")
    an_prec = annee_factory("2024-2025")
    an_cour = annee_factory("2025-2026")

    # 2 nouveaux NDK
    for i in range(2):
        p = personne_factory(site_id=ndk.id, nom=f"N{i}", login=f"n{i}")
        snap_factory(p.id, an_cour.id, classe="3B")
    # 1 nouveau SU
    p = personne_factory(site_id=su.id, nom="S1", login="s1")
    snap_factory(p.id, an_cour.id, classe="61")

    r = simuler_globalement(session, an_prec.id, an_cour.id)

    assert r.totaux_par_cible["koxo"]["nouveaux"] == 3
    assert r.totaux_par_cible["google"]["nouveaux"] == 3


def test_simulation_compte_sortants(
    session, site_factory, annee_factory, personne_factory, snap_factory
):
    from backend.services.simulation_globale import simuler_globalement

    site = site_factory("NDK")
    an_prec = annee_factory("2024-2025")
    an_cour = annee_factory("2025-2026")

    p = personne_factory(site_id=site.id, nom="SORT", login="sort")
    snap_factory(p.id, an_prec.id, classe="TALE")  # présent seulement à l'ancienne

    r = simuler_globalement(session, an_prec.id, an_cour.id)

    assert r.totaux_par_cible["koxo"]["sortants"] == 1
    assert r.totaux_par_cible["google"]["sortants"] == 1


def test_simulation_compte_modifies(
    session, site_factory, annee_factory, personne_factory, snap_factory
):
    """Un changement de classe → seau modifié → compté dans les 2 cibles."""
    from backend.services.simulation_globale import simuler_globalement

    site = site_factory("NDK")
    an_prec = annee_factory("2024-2025")
    an_cour = annee_factory("2025-2026")

    p = personne_factory(site_id=site.id, nom="MOD", login="mod")
    snap_factory(p.id, an_prec.id, classe="3B")
    snap_factory(p.id, an_cour.id, classe="2NDE")

    r = simuler_globalement(session, an_prec.id, an_cour.id)

    assert r.totaux_par_cible["koxo"]["modifies"] == 1
    assert r.totaux_par_cible["google"]["modifies"] == 1


def test_simulation_arbitrage_bloque_execution(
    session, site_factory, annee_factory, personne_factory, snap_factory
):
    """Un arbitrage en attente empêche l'exécution automatique."""
    from backend.services.arbitrage import creer_ou_reprendre
    from backend.services.simulation_globale import simuler_globalement

    site = site_factory("NDK")
    an_prec = annee_factory("2024-2025")
    an_cour = annee_factory("2025-2026")

    p = personne_factory(site_id=site.id, nom="NEUF", login="neuf")
    snap_factory(p.id, an_cour.id, classe="3B")

    # Crée un arbitrage en attente
    creer_ou_reprendre(
        session,
        type_cas="collision_login",
        cle_cas="test-simu-blocage",
        contexte={},
    )
    session.commit()

    r = simuler_globalement(session, an_prec.id, an_cour.id)

    assert r.nb_arbitrages_en_attente == 1
    assert r.est_pret_a_executer is False
    assert any(b.type == "arbitrage_en_attente" for b in r.blocages)


def test_simulation_pret_si_aucun_blocage(
    session, site_factory, annee_factory, personne_factory, snap_factory
):
    from backend.services.simulation_globale import simuler_globalement

    site = site_factory("NDK")
    an_prec = annee_factory("2024-2025")
    an_cour = annee_factory("2025-2026")
    p = personne_factory(site_id=site.id, login="test")
    snap_factory(p.id, an_cour.id)

    r = simuler_globalement(session, an_prec.id, an_cour.id)
    assert r.est_pret_a_executer is True


def test_simulation_separe_par_type_personne(
    session, site_factory, annee_factory, personne_factory, snap_factory
):
    from backend.services.simulation_globale import simuler_globalement

    site = site_factory("NDK")
    an_prec = annee_factory("2024-2025")
    an_cour = annee_factory("2025-2026")

    p_e = personne_factory(type="eleve", site_id=site.id, login="e1")
    p_a = personne_factory(type="adulte", site_id=site.id, login="a1")
    snap_factory(p_e.id, an_cour.id)
    snap_factory(p_a.id, an_cour.id)

    r = simuler_globalement(session, an_prec.id, an_cour.id)

    types = {l.type_personne for l in r.lignes}
    assert "eleve" in types and "adulte" in types


def test_simulation_annee_source_introuvable(session, annee_factory):
    from backend.services.simulation_globale import simuler_globalement

    an = annee_factory("2025-2026")
    with pytest.raises(ValueError, match="source introuvable"):
        simuler_globalement(session, 99999, an.id)


def test_simulation_annee_cible_introuvable(session, annee_factory):
    from backend.services.simulation_globale import simuler_globalement

    an = annee_factory("2024-2025")
    with pytest.raises(ValueError, match="cible introuvable"):
        simuler_globalement(session, an.id, 99999)


def test_rapport_texte_lisible(
    session, site_factory, annee_factory, personne_factory, snap_factory
):
    from backend.services.simulation_globale import (
        rendre_rapport_texte,
        simuler_globalement,
    )

    site = site_factory("NDK")
    an_prec = annee_factory("2024-2025")
    an_cour = annee_factory("2025-2026")
    p = personne_factory(site_id=site.id, login="neuf")
    snap_factory(p.id, an_cour.id, classe="3B")

    texte = rendre_rapport_texte(simuler_globalement(session, an_prec.id, an_cour.id))

    assert "RAPPORT DE SIMULATION" in texte
    assert "2024-2025" in texte and "2025-2026" in texte
    assert "PRÊT À EXÉCUTER" in texte
    assert "koxo" in texte and "google" in texte
    assert "aucune écriture" in texte.lower()


def test_rapport_texte_annonce_les_blocages(
    session, site_factory, annee_factory, personne_factory, snap_factory
):
    from backend.services.arbitrage import creer_ou_reprendre
    from backend.services.simulation_globale import (
        rendre_rapport_texte,
        simuler_globalement,
    )

    site = site_factory("NDK")
    an_prec = annee_factory("2024-2025")
    an_cour = annee_factory("2025-2026")
    p = personne_factory(site_id=site.id, login="neuf")
    snap_factory(p.id, an_cour.id, classe="3B")
    creer_ou_reprendre(session, type_cas="collision_login", cle_cas="k", contexte={})
    session.commit()

    texte = rendre_rapport_texte(simuler_globalement(session, an_prec.id, an_cour.id))
    assert "BLOCAGE" in texte
    assert "PRÊT À EXÉCUTER" not in texte


def test_rapport_csv_structure(
    session, site_factory, annee_factory, personne_factory, snap_factory
):
    import csv
    import io

    from backend.services.simulation_globale import (
        rendre_rapport_csv,
        simuler_globalement,
    )

    site = site_factory("NDK")
    an_prec = annee_factory("2024-2025")
    an_cour = annee_factory("2025-2026")
    p = personne_factory(site_id=site.id, login="neuf")
    snap_factory(p.id, an_cour.id, classe="3B")

    csv_texte = rendre_rapport_csv(simuler_globalement(session, an_prec.id, an_cour.id))
    rows = list(csv.DictReader(io.StringIO(csv_texte), delimiter=";"))

    assert len(rows) == 2  # une ligne koxo + une ligne google
    assert rows[0]["site"] == "NDK"
    assert int(rows[0]["nouveaux"]) == 1


def test_simulation_scenario_realiste(
    session, site_factory, annee_factory, personne_factory, snap_factory
):
    """1 nouveau + 1 modifié + 1 sortant = 3 opérations par cible."""
    from backend.services.simulation_globale import simuler_globalement

    site = site_factory("NDK")
    an_prec = annee_factory("2024-2025")
    an_cour = annee_factory("2025-2026")

    # Nouveau
    p_n = personne_factory(site_id=site.id, nom="N", login="n1")
    snap_factory(p_n.id, an_cour.id, classe="3B")
    # Modifié (change de classe)
    p_m = personne_factory(site_id=site.id, nom="M", login="m1")
    snap_factory(p_m.id, an_prec.id, classe="3B")
    snap_factory(p_m.id, an_cour.id, classe="2NDE")
    # Sortant
    p_s = personne_factory(site_id=site.id, nom="S", login="s1")
    snap_factory(p_s.id, an_prec.id, classe="TALE")

    r = simuler_globalement(session, an_prec.id, an_cour.id)

    total_ops = sum(l.total_operations for l in r.lignes if l.cible == "koxo")
    # 1 nouveau + 1 modifié + 1 sortant = 3 ops KoXo
    assert total_ops == 3
