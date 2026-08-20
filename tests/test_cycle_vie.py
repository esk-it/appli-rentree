"""Tests du cycle de vie des CompteCible.

Comble le trou du Lot 12 : le service `suivi.py` savait faire transiter un
compte, mais rien n'en créait. Ces tests vérifient la chaîne complète
`prevu → cree → actif → quarantaine/purge`.
"""
from __future__ import annotations

from datetime import date, timedelta

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


# ---------------------------------------------------------------------------
# Mapping site/type → cibles
# ---------------------------------------------------------------------------


def test_cibles_eleve_ndk():
    from backend.services.cycle_vie import cibles_pour

    c = set(cibles_pour("NDK", "eleve"))
    assert c == {"google", "koxo_ndk", "pmb_ndk", "jpm", "cardstudio"}


def test_cibles_adulte_na_ni_badge_ni_carte():
    from backend.services.cycle_vie import cibles_pour

    c = set(cibles_pour("NDK", "adulte"))
    assert c == {"google", "koxo_ndk", "pmb_ndk"}
    assert "jpm" not in c
    assert "cardstudio" not in c


def test_cibles_su_utilise_ses_propres_serveurs():
    from backend.services.cycle_vie import cibles_pour

    c = set(cibles_pour("SU", "eleve"))
    assert "koxo_su" in c and "pmb_su" in c
    assert "koxo_ndk" not in c


def test_cibles_nde_est_rattache_a_ndk():
    """NDE n'a pas d'infra propre — il utilise les serveurs NDK."""
    from backend.services.cycle_vie import cibles_pour

    c = set(cibles_pour("NDE", "eleve"))
    assert "koxo_ndk" in c and "pmb_ndk" in c


def test_cibles_type_invalide():
    from backend.services.cycle_vie import cibles_pour

    with pytest.raises(ValueError, match="type_personne"):
        cibles_pour("NDK", "prof")


# ---------------------------------------------------------------------------
# Création des « prévus »
# ---------------------------------------------------------------------------


def test_enregistrer_prevus_cree_les_comptes(session, site_factory, personne_factory):
    from backend.models import CompteCible
    from backend.services.cycle_vie import enregistrer_prevus

    site = site_factory("NDK")
    p = personne_factory(site_id=site.id, login="jdupont")

    r = enregistrer_prevus(session, [p.id], ["google", "koxo_ndk"])
    session.commit()

    assert r.nb_crees == 2
    comptes = session.query(CompteCible).filter_by(personne_id=p.id).all()
    assert {c.cible for c in comptes} == {"google", "koxo_ndk"}
    assert all(c.etat == "prevu" for c in comptes)


def test_enregistrer_prevus_renseigne_identifiant_externe(
    session, site_factory, personne_factory
):
    """Google → email, autres cibles → badge."""
    from backend.models import CompteCible
    from backend.services.cycle_vie import enregistrer_prevus

    site = site_factory("NDK")  # domaine lekreisker.fr
    p = personne_factory(
        site_id=site.id, nom="DUPONT", prenom="Jean", login="jdupont",
        id_charlemagne=5824,
    )

    enregistrer_prevus(session, [p.id], ["google", "koxo_ndk"])
    session.commit()

    google = session.query(CompteCible).filter_by(personne_id=p.id, cible="google").one()
    koxo = session.query(CompteCible).filter_by(personne_id=p.id, cible="koxo_ndk").one()
    assert google.identifiant_externe == "jean.dupont@lekreisker.fr"
    assert koxo.identifiant_externe == str(p.badge)


def test_enregistrer_prevus_est_idempotent(session, site_factory, personne_factory):
    from backend.models import CompteCible
    from backend.services.cycle_vie import enregistrer_prevus

    site = site_factory("NDK")
    p = personne_factory(site_id=site.id, login="jdupont")

    enregistrer_prevus(session, [p.id], ["google"])
    session.commit()
    r2 = enregistrer_prevus(session, [p.id], ["google"])
    session.commit()

    assert r2.nb_crees == 0
    assert r2.nb_ignores == 1
    assert session.query(CompteCible).filter_by(personne_id=p.id).count() == 1


def test_enregistrer_prevus_ne_fait_pas_reculer_un_etat(
    session, site_factory, personne_factory
):
    """Un compte déjà actif n'est pas ramené à `prevu`."""
    from backend.models import CompteCible
    from backend.services.cycle_vie import enregistrer_prevus

    site = site_factory("NDK")
    p = personne_factory(site_id=site.id, login="jdupont")
    session.add(CompteCible(personne_id=p.id, cible="google", etat="actif"))
    session.commit()

    enregistrer_prevus(session, [p.id], ["google"])
    session.commit()

    compte = session.query(CompteCible).filter_by(personne_id=p.id, cible="google").one()
    assert compte.etat == "actif"


def test_enregistrer_prevus_pour_export_nouveaux(
    session, site_factory, annee_factory, personne_factory, snap_factory
):
    """Seuls les nouveaux de l'export sont enregistrés."""
    from backend.models import CompteCible
    from backend.services.cycle_vie import enregistrer_prevus_pour_export

    site = site_factory("NDK")
    an_prec = annee_factory("2024-2025")
    an_cour = annee_factory("2025-2026")

    p_reste = personne_factory(site_id=site.id, login="reste")
    snap_factory(p_reste.id, an_prec.id)
    snap_factory(p_reste.id, an_cour.id)
    p_neuf = personne_factory(site_id=site.id, login="neuf")
    snap_factory(p_neuf.id, an_cour.id)

    r = enregistrer_prevus_pour_export(
        session,
        site_id=site.id,
        type_personne="eleve",
        annee_cible_id=an_cour.id,
        annee_source_id=an_prec.id,
        categorie="nouveaux",
        cible_unique="koxo_ndk",
    )
    session.commit()

    assert r.nb_crees == 1
    comptes = session.query(CompteCible).all()
    assert len(comptes) == 1
    assert comptes[0].personne_id == p_neuf.id


# ---------------------------------------------------------------------------
# Transitions en avant
# ---------------------------------------------------------------------------


def test_confirmer_creation(session, site_factory, personne_factory):
    from backend.models import CompteCible
    from backend.services.cycle_vie import confirmer_creation, enregistrer_prevus

    site = site_factory("NDK")
    p = personne_factory(site_id=site.id, login="jdupont")
    enregistrer_prevus(session, [p.id], ["koxo_ndk"])
    session.commit()

    r = confirmer_creation(session, cible="koxo_ndk")
    session.commit()

    assert r.nb_transitions == 1
    compte = session.query(CompteCible).filter_by(personne_id=p.id).one()
    assert compte.etat == "cree"


def test_confirmer_creation_ne_touche_pas_les_autres_cibles(
    session, site_factory, personne_factory
):
    from backend.models import CompteCible
    from backend.services.cycle_vie import confirmer_creation, enregistrer_prevus

    site = site_factory("NDK")
    p = personne_factory(site_id=site.id, login="jdupont")
    enregistrer_prevus(session, [p.id], ["koxo_ndk", "google"])
    session.commit()

    confirmer_creation(session, cible="koxo_ndk")
    session.commit()

    google = session.query(CompteCible).filter_by(personne_id=p.id, cible="google").one()
    assert google.etat == "prevu"


def test_confirmer_creation_filtre_par_site(
    session, site_factory, personne_factory
):
    from backend.models import CompteCible
    from backend.services.cycle_vie import confirmer_creation, enregistrer_prevus

    ndk = site_factory("NDK")
    su = site_factory("SU")
    p_ndk = personne_factory(site_id=ndk.id, login="ndk1")
    p_su = personne_factory(site_id=su.id, login="su1")
    enregistrer_prevus(session, [p_ndk.id, p_su.id], ["google"])
    session.commit()

    confirmer_creation(session, cible="google", site_id=ndk.id)
    session.commit()

    assert session.query(CompteCible).filter_by(personne_id=p_ndk.id).one().etat == "cree"
    assert session.query(CompteCible).filter_by(personne_id=p_su.id).one().etat == "prevu"


def test_activer(session, site_factory, personne_factory):
    from backend.models import CompteCible
    from backend.services.cycle_vie import activer, confirmer_creation, enregistrer_prevus

    site = site_factory("NDK")
    p = personne_factory(site_id=site.id, login="jdupont")
    enregistrer_prevus(session, [p.id], ["google"])
    confirmer_creation(session, cible="google")
    session.commit()

    r = activer(session, cible="google")
    session.commit()

    assert r.nb_transitions == 1
    assert session.query(CompteCible).filter_by(personne_id=p.id).one().etat == "actif"


def test_activer_ignore_les_prevus(session, site_factory, personne_factory):
    """Un compte encore `prevu` ne saute pas directement à `actif`."""
    from backend.models import CompteCible
    from backend.services.cycle_vie import activer, enregistrer_prevus

    site = site_factory("NDK")
    p = personne_factory(site_id=site.id, login="jdupont")
    enregistrer_prevus(session, [p.id], ["google"])
    session.commit()

    r = activer(session, cible="google")
    session.commit()

    assert r.nb_transitions == 0
    assert session.query(CompteCible).filter_by(personne_id=p.id).one().etat == "prevu"


def test_cible_invalide_leve_valueerror(session):
    from backend.services.cycle_vie import activer, confirmer_creation

    with pytest.raises(ValueError, match="cible"):
        confirmer_creation(session, cible="fantome")
    with pytest.raises(ValueError, match="cible"):
        activer(session, cible="fantome")


# ---------------------------------------------------------------------------
# Sortants — politique de sortie automatique
# ---------------------------------------------------------------------------


def test_traiter_sortants_applique_la_politique(
    session, site_factory, annee_factory, personne_factory, snap_factory
):
    """Google → quarantaine +18 mois ; KoXo → purge immédiate."""
    from backend.models import CompteCible
    from backend.services.cycle_vie import enregistrer_prevus, traiter_sortants

    site = site_factory("NDK")
    an_prec = annee_factory("2024-2025")
    an_cour = annee_factory("2025-2026")

    p_sortant = personne_factory(site_id=site.id, nom="SORT", login="sort")
    snap_factory(p_sortant.id, an_prec.id, classe="TALE")  # absent de l'année cible
    enregistrer_prevus(session, [p_sortant.id], ["google", "koxo_ndk"])
    session.commit()

    r = traiter_sortants(
        session, an_prec.id, an_cour.id, aujourd_hui=date(2026, 1, 1)
    )
    session.commit()

    assert r.nb_transitions == 2

    google = session.query(CompteCible).filter_by(
        personne_id=p_sortant.id, cible="google"
    ).one()
    koxo = session.query(CompteCible).filter_by(
        personne_id=p_sortant.id, cible="koxo_ndk"
    ).one()

    assert google.etat == "quarantaine"
    assert google.date_prevue_purge == date(2027, 7, 1)  # 18 mois calendaires
    assert koxo.etat == "purge"
    assert koxo.date_prevue_purge == date(2026, 1, 1)


def test_traiter_sortants_epargne_les_maintenus(
    session, site_factory, annee_factory, personne_factory, snap_factory
):
    from backend.models import CompteCible
    from backend.services.cycle_vie import enregistrer_prevus, traiter_sortants

    site = site_factory("NDK")
    an_prec = annee_factory("2024-2025")
    an_cour = annee_factory("2025-2026")

    p_reste = personne_factory(site_id=site.id, nom="RESTE", login="reste")
    snap_factory(p_reste.id, an_prec.id, classe="3B")
    snap_factory(p_reste.id, an_cour.id, classe="2NDE")
    enregistrer_prevus(session, [p_reste.id], ["google"])
    session.commit()

    r = traiter_sortants(session, an_prec.id, an_cour.id)
    session.commit()

    assert r.nb_transitions == 0
    assert session.query(CompteCible).filter_by(personne_id=p_reste.id).one().etat == "prevu"


def test_traiter_sortants_ne_repousse_pas_une_echeance(
    session, site_factory, annee_factory, personne_factory, snap_factory
):
    """Un compte déjà en quarantaine garde sa date de purge d'origine."""
    from backend.models import CompteCible
    from backend.services.cycle_vie import traiter_sortants

    site = site_factory("NDK")
    an_prec = annee_factory("2024-2025")
    an_cour = annee_factory("2025-2026")

    p = personne_factory(site_id=site.id, nom="SORT", login="sort")
    snap_factory(p.id, an_prec.id, classe="TALE")
    echeance = date(2026, 6, 1)
    session.add(CompteCible(
        personne_id=p.id, cible="google", etat="quarantaine",
        date_prevue_purge=echeance,
    ))
    session.commit()

    r = traiter_sortants(session, an_prec.id, an_cour.id, aujourd_hui=date(2026, 1, 1))
    session.commit()

    assert r.nb_ignores == 1
    assert r.nb_transitions == 0
    compte = session.query(CompteCible).filter_by(personne_id=p.id).one()
    assert compte.date_prevue_purge == echeance  # inchangée


def test_traiter_sortants_couvre_eleves_et_adultes(
    session, site_factory, annee_factory, personne_factory, snap_factory
):
    from backend.services.cycle_vie import enregistrer_prevus, traiter_sortants

    site = site_factory("NDK")
    an_prec = annee_factory("2024-2025")
    an_cour = annee_factory("2025-2026")

    p_e = personne_factory(type="eleve", site_id=site.id, login="e1")
    p_a = personne_factory(type="adulte", site_id=site.id, login="a1")
    snap_factory(p_e.id, an_prec.id)
    snap_factory(p_a.id, an_prec.id)
    enregistrer_prevus(session, [p_e.id, p_a.id], ["google"])
    session.commit()

    r = traiter_sortants(session, an_prec.id, an_cour.id)
    session.commit()

    assert r.nb_transitions == 2


def test_traiter_sortants_sans_compte_ne_plante_pas(
    session, site_factory, annee_factory, personne_factory, snap_factory
):
    """Une personne sortante sans CompteCible n'est simplement pas traitée."""
    from backend.services.cycle_vie import traiter_sortants

    site = site_factory("NDK")
    an_prec = annee_factory("2024-2025")
    an_cour = annee_factory("2025-2026")

    p = personne_factory(site_id=site.id, login="sort")
    snap_factory(p.id, an_prec.id)

    r = traiter_sortants(session, an_prec.id, an_cour.id)
    session.commit()

    assert r.nb_transitions == 0
    assert r.erreurs == []


# ---------------------------------------------------------------------------
# Le suivi devient enfin peuplé
# ---------------------------------------------------------------------------


def test_purger_marque_les_echeances_atteintes(
    session, site_factory, personne_factory
):
    from backend.models import CompteCible
    from backend.services.cycle_vie import purger

    site = site_factory("NDK")
    p = personne_factory(site_id=site.id, login="sorti")
    session.add(CompteCible(
        personne_id=p.id, cible="google", etat="quarantaine",
        date_prevue_purge=date(2024, 1, 1),
    ))
    session.commit()

    r = purger(session, aujourd_hui=date(2026, 1, 1))
    session.commit()

    assert r.nb_transitions == 1
    assert session.query(CompteCible).one().etat == "purge"


def test_purger_refuse_une_echeance_future(session, site_factory, personne_factory):
    """Un compte encore en quarantaine active n'est pas purgeable."""
    from backend.models import CompteCible
    from backend.services.cycle_vie import purger

    site = site_factory("NDK")
    p = personne_factory(site_id=site.id, login="encore")
    session.add(CompteCible(
        personne_id=p.id, cible="google", etat="quarantaine",
        date_prevue_purge=date(2099, 1, 1),
    ))
    session.commit()

    r = purger(session, aujourd_hui=date(2026, 1, 1))
    session.commit()

    assert r.nb_transitions == 0
    assert session.query(CompteCible).one().etat == "quarantaine"


def test_purger_refuse_un_compte_actif(session, site_factory, personne_factory):
    from backend.models import CompteCible
    from backend.services.cycle_vie import purger

    site = site_factory("NDK")
    p = personne_factory(site_id=site.id, login="actif")
    session.add(CompteCible(personne_id=p.id, cible="google", etat="actif"))
    session.commit()

    r = purger(session, aujourd_hui=date(2026, 1, 1))
    session.commit()

    assert r.nb_transitions == 0
    assert session.query(CompteCible).one().etat == "actif"


def test_purger_selection_precise(session, site_factory, personne_factory):
    """On peut ne purger qu'une partie du lot éligible."""
    from backend.models import CompteCible
    from backend.services.cycle_vie import purger

    site = site_factory("NDK")
    comptes = []
    for i in range(3):
        p = personne_factory(site_id=site.id, login=f"s{i}")
        c = CompteCible(
            personne_id=p.id, cible="google", etat="quarantaine",
            date_prevue_purge=date(2024, 1, 1),
        )
        session.add(c)
        comptes.append(c)
    session.commit()

    r = purger(session, compte_ids=[comptes[0].id], aujourd_hui=date(2026, 1, 1))
    session.commit()

    assert r.nb_transitions == 1
    etats = sorted(c.etat for c in session.query(CompteCible).all())
    assert etats == ["purge", "quarantaine", "quarantaine"]


def test_purger_signale_une_demande_non_eligible(
    session, site_factory, personne_factory
):
    """Demander la purge d'un compte non éligible remonte une erreur explicite."""
    from backend.models import CompteCible
    from backend.services.cycle_vie import purger

    site = site_factory("NDK")
    p = personne_factory(site_id=site.id, login="futur")
    c = CompteCible(
        personne_id=p.id, cible="google", etat="quarantaine",
        date_prevue_purge=date(2099, 1, 1),
    )
    session.add(c)
    session.commit()

    r = purger(session, compte_ids=[c.id], aujourd_hui=date(2026, 1, 1))
    session.commit()

    assert r.nb_transitions == 0
    assert len(r.erreurs) == 1
    assert "non éligible" in r.erreurs[0]


def test_purger_filtre_par_cible(session, site_factory, personne_factory):
    from backend.models import CompteCible
    from backend.services.cycle_vie import purger

    site = site_factory("NDK")
    p = personne_factory(site_id=site.id, login="multi")
    for cible in ("google", "koxo_ndk"):
        session.add(CompteCible(
            personne_id=p.id, cible=cible, etat="quarantaine",
            date_prevue_purge=date(2024, 1, 1),
        ))
    session.commit()

    r = purger(session, cible="google", aujourd_hui=date(2026, 1, 1))
    session.commit()

    assert r.nb_transitions == 1
    google = session.query(CompteCible).filter_by(cible="google").one()
    koxo = session.query(CompteCible).filter_by(cible="koxo_ndk").one()
    assert google.etat == "purge"
    assert koxo.etat == "quarantaine"


def test_purger_cible_invalide(session):
    from backend.services.cycle_vie import purger

    with pytest.raises(ValueError, match="cible"):
        purger(session, cible="fantome")


def test_stats_suivi_reflete_les_comptes_crees(
    session, site_factory, personne_factory
):
    """Vérifie la correction du trou : l'écran Suivi n'est plus vide."""
    from backend.services.cycle_vie import enregistrer_prevus
    from backend.services.suivi import stats_suivi

    site = site_factory("NDK")
    p = personne_factory(site_id=site.id, login="jdupont")
    enregistrer_prevus(session, [p.id], ["google", "koxo_ndk"])
    session.commit()

    s = stats_suivi(session)
    assert s.total_par_etat["prevu"] == 2
    assert s.par_cible["google"]["prevu"] == 1
    assert s.par_cible["koxo_ndk"]["prevu"] == 1
