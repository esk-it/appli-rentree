"""Tests de l'algorithme de comparaison N vs N-1."""
from __future__ import annotations

import pytest

from backend.services.comparaison import comparer_annees


@pytest.fixture()
def setup_deux_snapshots(session, etablissement_factory, annee_factory, eleve_factory):
    """Crée 2 snapshots avec des mouvements précis."""
    etab = etablissement_factory()
    n1 = annee_factory("N-1")
    n = annee_factory("N")

    # 5 élèves en N-1
    for i in range(5):
        eleve_factory(
            annee_id=n1.id,
            etablissement_id=etab.id,
            num_badge=1000 + i,
            nom=f"NOM{i:02d}",
            code_classe="3A",
        )

    # En N : on garde les 3 premiers (avec changement de classe pour 2)
    # Prénoms identiques aux N-1 pour ne pas créer de faux changement
    eleve_factory(annee_id=n.id, etablissement_id=etab.id, num_badge=1000, nom="NOM00", prenom="Prenom001", code_classe="3A")  # inchangé
    eleve_factory(annee_id=n.id, etablissement_id=etab.id, num_badge=1001, nom="NOM01", prenom="Prenom002", code_classe="3B")  # classe change
    eleve_factory(annee_id=n.id, etablissement_id=etab.id, num_badge=1002, nom="NOM02", prenom="Prenom003", code_classe="4A", code_regime="P")  # classe + régime
    # 1003 et 1004 supprimés (sortants)

    # 2 nouveaux entrants en N
    eleve_factory(annee_id=n.id, etablissement_id=etab.id, num_badge=2000, nom="NEW00")
    eleve_factory(annee_id=n.id, etablissement_id=etab.id, num_badge=2001, nom="NEW01")

    return {"etab": etab, "n1": n1, "n": n}


def test_compte_correct_entrants_restants_sortants(setup_deux_snapshots, session):
    res = comparer_annees(session, "N", "N-1")
    assert len(res.entrants) == 2
    assert len(res.restants) == 3
    assert len(res.sortants) == 2


def test_les_changements_sont_detectes(setup_deux_snapshots, session):
    res = comparer_annees(session, "N", "N-1")

    # NOM01 : classe change 3A → 3B
    restant_01 = next(r for r in res.restants if r.eleve_n.num_badge == 1001)
    champs_changes = {c.champ for c in restant_01.changements}
    assert "classe" in champs_changes

    # NOM02 : classe ET régime changent
    restant_02 = next(r for r in res.restants if r.eleve_n.num_badge == 1002)
    champs_changes_02 = {c.champ for c in restant_02.changements}
    assert "classe" in champs_changes_02
    assert "regime" in champs_changes_02

    # NOM00 : pas de changement
    restant_00 = next(r for r in res.restants if r.eleve_n.num_badge == 1000)
    assert restant_00.changements == []


def test_match_fallback_sur_nomprenom_quand_pas_de_badge(
    session, etablissement_factory, annee_factory, eleve_factory
):
    etab = etablissement_factory()
    n1 = annee_factory("N-1")
    n = annee_factory("N")
    eleve_factory(annee_id=n1.id, etablissement_id=etab.id, num_badge=None, nom="DUPONT", prenom="Jean")
    eleve_factory(annee_id=n.id, etablissement_id=etab.id, num_badge=None, nom="DUPONT", prenom="Jean", code_classe="4B")

    res = comparer_annees(session, "N", "N-1")
    assert len(res.restants) == 1
    assert len(res.entrants) == 0
    assert len(res.sortants) == 0


def test_lever_erreur_si_annees_identiques(setup_deux_snapshots, session):
    with pytest.raises(ValueError, match="différentes"):
        comparer_annees(session, "N", "N")


def test_lever_erreur_si_snapshot_inexistant(session, annee_factory):
    annee_factory("EXISTE")
    with pytest.raises(ValueError, match="introuvable"):
        comparer_annees(session, "INEXISTANT", "EXISTE")
