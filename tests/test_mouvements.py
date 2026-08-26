"""Qui entre, qui sort, qui reste — pour une année donnée.

Deux populations, deux sources : les élèves se déduisent des
photographies annuelles, les adultes se lisent dans le tableau des
professeurs. Et ce que la source ne permet pas d'établir doit être dit,
jamais deviné : sans année précédente, tout le monde paraîtrait entrant.
"""
from __future__ import annotations

import pytest

from backend.models import MouvementProf, Personne, Snapshot


@pytest.fixture
def monde(session, annee_factory):
    """Deux années d'élèves, et de quoi ajouter des adultes."""

    def _faire():
        a1 = annee_factory("2025-2026")
        a2 = annee_factory("2026-2027")
        return a1, a2

    return _faire


def _eleve(session, nom, prenom, badge, login=None):
    p = Personne(
        type="eleve", nom=nom, prenom=prenom, badge=badge,
        login=login or (prenom[0] + nom).lower(), id_charlemagne=badge,
    )
    session.add(p)
    session.commit()
    return p


def _adulte(session, nom, prenom, badge):
    p = Personne(
        type="adulte", nom=nom, prenom=prenom, badge=badge,
        login=(prenom[0] + nom).lower(), id_charlemagne=badge,
    )
    session.add(p)
    session.commit()
    return p


def _inscrire(session, personne, annee, classe):
    session.add(Snapshot(
        personne_id=personne.id, annee_scolaire_id=annee.id,
        nom=personne.nom, prenom=personne.prenom, classe=classe,
    ))
    session.commit()


def test_un_eleve_present_les_deux_annees_reste(session, monde):
    from backend.services.mouvements import mouvements_annee

    a1, a2 = monde()
    p = _eleve(session, "MARTIN", "Paul", 20100)
    _inscrire(session, p, a1, "45")
    _inscrire(session, p, a2, "32")

    r = mouvements_annee(session, annee_id=a2.id, type_personne="eleve")
    assert [(l.nom, l.mouvement) for l in r.lignes] == [("MARTIN", "present")]
    assert r.lignes[0].detail == "45 → 32", "la transition se lit d'un coup d'œil"


def test_un_eleve_absent_de_lannee_precedente_entre(session, monde):
    from backend.services.mouvements import mouvements_annee

    a1, a2 = monde()
    ancien = _eleve(session, "ANCIEN", "Anne", 20100)
    _inscrire(session, ancien, a1, "45")
    _inscrire(session, ancien, a2, "32")
    nouveau = _eleve(session, "NOUVEAU", "Noe", 20200)
    _inscrire(session, nouveau, a2, "65")

    r = mouvements_annee(session, annee_id=a2.id, type_personne="eleve")
    entrants = [l for l in r.lignes if l.mouvement == "entrant"]
    assert [l.nom for l in entrants] == ["NOUVEAU"]
    assert entrants[0].detail == "entre en 65"


def test_un_eleve_absent_de_lannee_suivante_sort(session, monde):
    from backend.services.mouvements import mouvements_annee

    a1, a2 = monde()
    parti = _eleve(session, "PARTI", "Pia", 20100)
    _inscrire(session, parti, a1, "T_G1")
    reste = _eleve(session, "RESTE", "Rex", 20200)
    _inscrire(session, reste, a1, "45")
    _inscrire(session, reste, a2, "32")

    r = mouvements_annee(session, annee_id=a1.id, type_personne="eleve")
    sortants = [l for l in r.lignes if l.mouvement == "sortant"]
    assert [l.nom for l in sortants] == ["PARTI"]
    assert sortants[0].detail == "quitte la T_G1"


def test_sans_annee_precedente_les_entrants_ne_sont_pas_devines(
    session, annee_factory
):
    """La mauvaise réponse serait spectaculaire : tout le monde entrant."""
    from backend.services.mouvements import mouvements_annee

    a = annee_factory("2026-2027")
    p = _eleve(session, "MARTIN", "Paul", 20100)
    _inscrire(session, p, a, "32")

    r = mouvements_annee(session, annee_id=a.id, type_personne="eleve")
    assert r.entrants_connus is False
    assert not [l for l in r.lignes if l.mouvement == "entrant"]
    assert "paraîtraient tous nouveaux" in r.raisons["entrant"]
    assert [l.mouvement for l in r.lignes] == ["present"]


def test_sans_annee_suivante_les_sortants_ne_sont_pas_devines(
    session, annee_factory
):
    from backend.services.mouvements import mouvements_annee

    a = annee_factory("2026-2027")
    p = _eleve(session, "MARTIN", "Paul", 20100)
    _inscrire(session, p, a, "32")

    r = mouvements_annee(session, annee_id=a.id, type_personne="eleve")
    assert r.sortants_connus is False
    assert "reste ouverte" in r.raisons["sortant"]


def test_la_derniere_annee_ne_fabrique_pas_de_sortants(session, monde):
    """Personne ne « sort » de l'année qu'on prépare : rien ne le dit encore."""
    from backend.services.mouvements import mouvements_annee

    a1, a2 = monde()
    p = _eleve(session, "MARTIN", "Paul", 20100)
    _inscrire(session, p, a1, "45")
    _inscrire(session, p, a2, "32")
    q = _eleve(session, "SEUL", "Sam", 20200)
    _inscrire(session, q, a2, "65")

    r = mouvements_annee(session, annee_id=a2.id, type_personne="eleve")
    assert r.nb_par_mouvement["sortant"] == 0
    assert r.sortants_connus is False


# ---------------------------------------------------------------------------
# Adultes
# ---------------------------------------------------------------------------


def _ligne_prof(session, annee, nom, prenom, code, **extra):
    m = MouvementProf(
        annee_scolaire_id=annee.id, nom=nom, prenom=prenom, code=code, **extra
    )
    session.add(m)
    session.commit()
    return m


def test_le_mouvement_des_adultes_vient_du_tableau(session, monde):
    from backend.services.mouvements import mouvements_annee

    _, a2 = monde()
    _adulte(session, "ALDRIN", "Thierry", 651)
    _ligne_prof(session, a2, "ALDRIN", "Thierry", "sortant", libelle="Profs sortants")
    _ligne_prof(session, a2, "BILLANT", "Pierre", "arrivant")
    _ligne_prof(session, a2, "SERIO", "Philippe", "en_poste")

    r = mouvements_annee(session, annee_id=a2.id, type_personne="adulte")
    assert r.source == "tableau des professeurs"
    par_nom = {l.nom: l for l in r.lignes}
    assert par_nom["ALDRIN"].mouvement == "sortant"
    assert par_nom["BILLANT"].mouvement == "entrant"
    assert par_nom["SERIO"].mouvement == "present"


def test_un_arrivant_sans_compte_est_montre_et_le_dit(session, monde):
    """C'est une information — ce qui reste à faire pour lui — pas une anomalie."""
    from backend.services.mouvements import mouvements_annee

    _, a2 = monde()
    _ligne_prof(session, a2, "BILLANT", "Pierre", "arrivant")

    r = mouvements_annee(session, annee_id=a2.id, type_personne="adulte")
    assert r.lignes[0].personne_id is None
    assert r.lignes[0].detail == "arrivant sans compte au référentiel"


def test_un_adulte_du_tableau_est_relie_a_son_compte(session, monde):
    from backend.services.mouvements import mouvements_annee

    _, a2 = monde()
    p = _adulte(session, "ALDRIN", "Thierry", 651)
    _ligne_prof(session, a2, "ALDRIN", "Thierry", "sortant")

    r = mouvements_annee(session, annee_id=a2.id, type_personne="adulte")
    assert r.lignes[0].personne_id == p.id
    assert r.lignes[0].login == "taldrin"
    assert r.lignes[0].cle_pivot == p.cle_pivot


def test_un_remplacement_dit_qui_est_remplace(session, monde):
    from backend.services.mouvements import mouvements_annee

    _, a2 = monde()
    _ligne_prof(session, a2, "FUMAT", "Linda", "remplace",
                remplace_nom="CLOITRE", remplace_prenom="Morgane")

    r = mouvements_annee(session, annee_id=a2.id, type_personne="adulte")
    assert r.lignes[0].detail == "remplace Morgane CLOITRE"
    assert r.lignes[0].mouvement == "present", "un remplaçant est là, il n'entre pas"


def test_sans_tableau_le_mouvement_des_adultes_est_inconnu(session, monde):
    """Les adultes n'ont pas de photographie annuelle : rien à déduire."""
    from backend.services.mouvements import mouvements_annee

    _, a2 = monde()
    _adulte(session, "ALDRIN", "Thierry", 651)

    r = mouvements_annee(session, annee_id=a2.id, type_personne="adulte")
    assert r.lignes == []
    assert r.entrants_connus is False and r.sortants_connus is False
    assert "Aucun tableau des professeurs" in r.raisons["entrant"]


def test_les_adultes_ne_sont_pas_deduits_des_snapshots(session, monde):
    """Le piège : un adulte sans snapshot n'est pas un sortant."""
    from backend.services.mouvements import mouvements_annee

    a1, a2 = monde()
    _adulte(session, "ALDRIN", "Thierry", 651)
    _ligne_prof(session, a2, "ALDRIN", "Thierry", "en_poste")

    r = mouvements_annee(session, annee_id=a2.id, type_personne="adulte")
    assert r.nb_par_mouvement["sortant"] == 0


# ---------------------------------------------------------------------------
# Bornes
# ---------------------------------------------------------------------------


def test_le_filtre_de_site_sapplique(session, monde):
    from backend.models import Site
    from backend.services.mouvements import mouvements_annee

    a1, a2 = monde()
    site = Site(
        nom="NDK", nom_complet="Kreisker", domaine_mail="lekreisker.fr",
        prefixe_annee_ou="NDK", numero_ordre=3,
    )
    session.add(site)
    session.commit()

    ici = _eleve(session, "ICI", "Ida", 20100)
    ici.site_id = site.id
    ailleurs = _eleve(session, "AILLEURS", "Ali", 20200)
    session.commit()
    _inscrire(session, ici, a2, "32")
    _inscrire(session, ailleurs, a2, "33")

    r = mouvements_annee(session, annee_id=a2.id, type_personne="eleve", site="NDK")
    assert [l.nom for l in r.lignes] == ["ICI"]


def test_un_type_invalide_est_refuse(session, monde):
    from backend.services.mouvements import mouvements_annee

    _, a2 = monde()
    with pytest.raises(ValueError, match="type_personne"):
        mouvements_annee(session, annee_id=a2.id, type_personne="chromebook")


def test_une_annee_inconnue_est_refusee(session, monde):
    from backend.services.mouvements import mouvements_annee

    monde()
    with pytest.raises(ValueError, match="introuvable"):
        mouvements_annee(session, annee_id=9999, type_personne="eleve")


def test_les_lignes_sont_triees_par_nom(session, monde):
    from backend.services.mouvements import mouvements_annee

    _, a2 = monde()
    for nom, prenom, badge in [("ZOLA", "Zoe", 20300), ("ABEL", "Ava", 20100),
                               ("MOREL", "Max", 20200)]:
        p = _eleve(session, nom, prenom, badge)
        _inscrire(session, p, a2, "32")

    r = mouvements_annee(session, annee_id=a2.id, type_personne="eleve")
    assert [l.nom for l in r.lignes] == ["ABEL", "MOREL", "ZOLA"]
