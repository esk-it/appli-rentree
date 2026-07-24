"""Tests du service de réconciliation — les 5 seaux (nouveau/identique/modifie/sortant/ambigu)."""
from __future__ import annotations

import pytest


# ---------------------------------------------------------------------------
# Fixture snapshot minimal
# ---------------------------------------------------------------------------


@pytest.fixture()
def snapshot_factory(session):
    """Crée un Snapshot pour (personne, année) avec des valeurs par défaut."""
    from backend.models import Snapshot

    def _creer(
        personne_id: int,
        annee_scolaire_id: int,
        nom: str = "MARTIN",
        prenom: str = "Jean",
        classe: str | None = "3B",
        **kwargs,
    ):
        snap = Snapshot(
            personne_id=personne_id,
            annee_scolaire_id=annee_scolaire_id,
            nom=nom,
            prenom=prenom,
            classe=classe,
            **kwargs,
        )
        session.add(snap)
        session.commit()
        return snap

    return _creer


# ---------------------------------------------------------------------------
# Cas de base : 5 seaux
# ---------------------------------------------------------------------------


def test_seau_nouveau(session, site_factory, personne_factory, annee_factory, snapshot_factory):
    """Une personne présente uniquement dans l'année cible → seau `nouveau`."""
    from backend.services.reconciliation import reconcilier

    site_factory("NDK")
    an_prec = annee_factory("2024-2025")
    an_cour = annee_factory("2025-2026")

    p = personne_factory(nom="MARTIN", prenom="Jean")
    snapshot_factory(p.id, an_cour.id, nom="MARTIN", prenom="Jean", classe="3B")

    r = reconcilier(session, an_prec.id, an_cour.id)

    assert r.compteurs == {"nouveau": 1, "identique": 0, "modifie": 0, "sortant": 0, "ambigu": 0}
    assert r.nouveaux[0].nom == "MARTIN"
    assert r.nouveaux[0].classe_cible == "3B"
    assert r.nouveaux[0].motif == "nouveau dans l'export cible"


def test_seau_identique(session, site_factory, personne_factory, annee_factory, snapshot_factory):
    """Même personne, mêmes valeurs constatées → seau `identique`, hash inchangé."""
    from backend.services.reconciliation import reconcilier

    site_factory("NDK")
    an_prec = annee_factory("2024-2025")
    an_cour = annee_factory("2025-2026")

    p = personne_factory(nom="DUPONT", prenom="Marie")
    # Mêmes champs aux deux années
    snapshot_factory(p.id, an_prec.id, nom="DUPONT", prenom="Marie", classe="4A")
    snapshot_factory(p.id, an_cour.id, nom="DUPONT", prenom="Marie", classe="4A")

    r = reconcilier(session, an_prec.id, an_cour.id)

    assert r.compteurs["identique"] == 1
    assert r.compteurs["modifie"] == 0
    assert r.identiques[0].motif == "aucun changement"
    assert r.identiques[0].changements == []


def test_seau_modifie_avec_diff(
    session, site_factory, personne_factory, annee_factory, snapshot_factory
):
    """Passage de classe → seau `modifie` avec la diff explicite."""
    from backend.services.reconciliation import reconcilier

    site_factory("NDK")
    an_prec = annee_factory("2024-2025")
    an_cour = annee_factory("2025-2026")

    p = personne_factory(nom="DURAND", prenom="Pierre")
    snapshot_factory(p.id, an_prec.id, classe="3B")
    snapshot_factory(p.id, an_cour.id, classe="2NDE1")

    r = reconcilier(session, an_prec.id, an_cour.id)

    assert r.compteurs["modifie"] == 1
    e = r.modifies[0]
    assert e.classe_source == "3B"
    assert e.classe_cible == "2NDE1"
    assert e.motif == "classe 3B → 2NDE1"
    assert len(e.changements) == 1
    assert e.changements[0].champ == "classe"
    assert e.changements[0].avant == "3B"
    assert e.changements[0].apres == "2NDE1"


def test_seau_modifie_multichamps(
    session, personne_factory, annee_factory, snapshot_factory
):
    """Plusieurs champs changent → motif agrégé, liste complète des changements."""
    from backend.services.reconciliation import reconcilier

    an_prec = annee_factory("2024-2025")
    an_cour = annee_factory("2025-2026")

    p = personne_factory(nom="DUPONT", prenom="Sophie")
    snapshot_factory(p.id, an_prec.id, classe="3B", regime="D", niveau="3")
    snapshot_factory(p.id, an_cour.id, classe="2NDE1", regime="E", niveau="2NDE")

    r = reconcilier(session, an_prec.id, an_cour.id)

    e = r.modifies[0]
    champs_changes = {c.champ for c in e.changements}
    assert champs_changes == {"classe", "regime", "niveau"}
    assert e.motif.startswith("changements : ")


def test_seau_sortant(session, personne_factory, annee_factory, snapshot_factory):
    """Personne présente à l'année source, absente de la cible → `sortant`."""
    from backend.services.reconciliation import reconcilier

    an_prec = annee_factory("2024-2025")
    an_cour = annee_factory("2025-2026")

    p = personne_factory(nom="LEBLANC", prenom="Alice")
    snapshot_factory(p.id, an_prec.id, classe="TALE")  # dernière année

    r = reconcilier(session, an_prec.id, an_cour.id)

    assert r.compteurs["sortant"] == 1
    assert r.sortants[0].nom == "LEBLANC"
    assert r.sortants[0].classe_source == "TALE"
    assert r.sortants[0].classe_cible is None


def test_seau_ambigu_vide_par_defaut(
    session, personne_factory, annee_factory, snapshot_factory
):
    """Le seau ambigu reste vide tant que le Lot 5 (arbitrage) n'est pas branché."""
    from backend.services.reconciliation import reconcilier

    an_prec = annee_factory("2024-2025")
    an_cour = annee_factory("2025-2026")
    p = personne_factory()
    snapshot_factory(p.id, an_cour.id)

    r = reconcilier(session, an_prec.id, an_cour.id)
    assert r.ambigus == []


# ---------------------------------------------------------------------------
# Cas mixtes
# ---------------------------------------------------------------------------


def test_scenario_mixte(session, site_factory, personne_factory, annee_factory, snapshot_factory):
    """Un scénario réaliste : 1 nouveau, 1 identique, 1 modifié, 1 sortant."""
    from backend.services.reconciliation import reconcilier

    site_factory("NDK")
    an_prec = annee_factory("2024-2025")
    an_cour = annee_factory("2025-2026")

    # Identique
    p_id = personne_factory(nom="IDENT", prenom="Ident", id_charlemagne=1000)
    snapshot_factory(p_id.id, an_prec.id, nom="IDENT", prenom="Ident", classe="3A")
    snapshot_factory(p_id.id, an_cour.id, nom="IDENT", prenom="Ident", classe="3A")

    # Modifié (changement de classe)
    p_mod = personne_factory(nom="MODIF", prenom="Modif", id_charlemagne=2000)
    snapshot_factory(p_mod.id, an_prec.id, classe="3A")
    snapshot_factory(p_mod.id, an_cour.id, classe="2NDE1")

    # Sortant (uniquement source)
    p_out = personne_factory(nom="SORT", prenom="Sort", id_charlemagne=3000)
    snapshot_factory(p_out.id, an_prec.id, classe="TALE")

    # Nouveau (uniquement cible)
    p_new = personne_factory(nom="NEUF", prenom="Neuf", id_charlemagne=4000)
    snapshot_factory(p_new.id, an_cour.id, classe="6A")

    r = reconcilier(session, an_prec.id, an_cour.id)

    assert r.compteurs == {
        "nouveau": 1,
        "identique": 1,
        "modifie": 1,
        "sortant": 1,
        "ambigu": 0,
    }
    assert r.nouveaux[0].nom == "NEUF"
    assert r.identiques[0].nom == "IDENT"
    assert r.modifies[0].nom == "MODIF"
    assert r.sortants[0].nom == "SORT"


# ---------------------------------------------------------------------------
# Filtres et cas limites
# ---------------------------------------------------------------------------


def test_filtre_type_personne(
    session, personne_factory, annee_factory, snapshot_factory
):
    """Le filtre type_personne ne renvoie que les élèves ou les adultes."""
    from backend.services.reconciliation import reconcilier

    an_prec = annee_factory("2024-2025")
    an_cour = annee_factory("2025-2026")

    eleve = personne_factory(type="eleve", nom="ELEVE", prenom="E")
    adulte = personne_factory(type="adulte", nom="ADULTE", prenom="A")
    snapshot_factory(eleve.id, an_cour.id)
    snapshot_factory(adulte.id, an_cour.id)

    r_eleves = reconcilier(session, an_prec.id, an_cour.id, type_personne="eleve")
    r_adultes = reconcilier(session, an_prec.id, an_cour.id, type_personne="adulte")

    assert r_eleves.compteurs["nouveau"] == 1
    assert r_eleves.nouveaux[0].type == "eleve"
    assert r_adultes.compteurs["nouveau"] == 1
    assert r_adultes.nouveaux[0].type == "adulte"


def test_type_personne_invalide_leve_valueerror(session, annee_factory):
    from backend.services.reconciliation import reconcilier

    an1 = annee_factory("2024-2025")
    an2 = annee_factory("2025-2026")

    with pytest.raises(ValueError, match="type_personne"):
        reconcilier(session, an1.id, an2.id, type_personne="prof")


def test_annee_source_introuvable(session, annee_factory):
    from backend.services.reconciliation import reconcilier

    an = annee_factory("2025-2026")
    with pytest.raises(ValueError, match="source introuvable"):
        reconcilier(session, 99999, an.id)


def test_annee_cible_introuvable(session, annee_factory):
    from backend.services.reconciliation import reconcilier

    an = annee_factory("2024-2025")
    with pytest.raises(ValueError, match="cible introuvable"):
        reconcilier(session, an.id, 99999)


def test_annees_vides_donne_rapport_vide(session, annee_factory):
    """Deux années sans snapshot : tous les seaux sont vides."""
    from backend.services.reconciliation import reconcilier

    an1 = annee_factory("2024-2025")
    an2 = annee_factory("2025-2026")

    r = reconcilier(session, an1.id, an2.id)

    assert r.compteurs == {"nouveau": 0, "identique": 0, "modifie": 0, "sortant": 0, "ambigu": 0}


def test_multi_snapshots_retient_le_dernier(
    session, personne_factory, annee_factory, snapshot_factory
):
    """Si une année a plusieurs ingestions, seul le dernier snapshot compte."""
    from datetime import datetime, timedelta

    from backend.models import Snapshot
    from backend.services.reconciliation import reconcilier

    an_prec = annee_factory("2024-2025")
    an_cour = annee_factory("2025-2026")

    p = personne_factory(nom="MULTI", prenom="Snap")
    snapshot_factory(p.id, an_prec.id, classe="3B")

    # Deux snapshots dans an_cour : le plus récent est "2NDE1"
    ancien = Snapshot(
        personne_id=p.id,
        annee_scolaire_id=an_cour.id,
        nom="MULTI",
        prenom="Snap",
        classe="OBSOLETE",
        date_ingestion=datetime.utcnow() - timedelta(days=10),
    )
    session.add(ancien)
    session.commit()
    snapshot_factory(p.id, an_cour.id, classe="2NDE1")  # date_ingestion = utcnow (plus récent)

    r = reconcilier(session, an_prec.id, an_cour.id)

    assert r.compteurs["modifie"] == 1
    assert r.modifies[0].classe_cible == "2NDE1"
    assert r.modifies[0].classe_source == "3B"


def test_reconciliation_est_idempotente(
    session, personne_factory, annee_factory, snapshot_factory
):
    """Deux appels successifs sur les mêmes données donnent le même rapport."""
    from backend.services.reconciliation import reconcilier

    an_prec = annee_factory("2024-2025")
    an_cour = annee_factory("2025-2026")

    p = personne_factory(nom="STABLE", prenom="Stable")
    snapshot_factory(p.id, an_prec.id, classe="3A")
    snapshot_factory(p.id, an_cour.id, classe="3A")

    r1 = reconcilier(session, an_prec.id, an_cour.id)
    r2 = reconcilier(session, an_prec.id, an_cour.id)

    assert r1.compteurs == r2.compteurs
    assert [e.personne_id for e in r1.identiques] == [e.personne_id for e in r2.identiques]
