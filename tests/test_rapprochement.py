"""Retrouver une personne quand son nom n'est pas écrit pareil des deux côtés.

Les quatre premiers cas sont réels : ces enseignants passaient pour absents
de Google alors que leur compte existait.
"""
from __future__ import annotations

import pytest


def _compte(email, nom, prenom):
    return {"email": email, "nom": nom, "prenom": prenom}


ANNUAIRE = [
    _compte("rosa.carbonell@lekreisker.fr", "CARBONELL", "Rosa"),
    _compte("carolina.hamon@lekreisker.fr", "HAMON", "Carolina"),
    _compte("jaya.lejalu@lekreisker.fr", "LE JALU", "Jaya"),
    _compte("erwan.morio@lekreisker.fr", "MORIO", "Erwan"),
    _compte("paul.durand@lekreisker.fr", "DURAND", "Paul"),
]


def _index():
    from backend.services.rapprochement import construire_index

    return construire_index(ANNUAIRE)


@pytest.mark.parametrize(
    "nom, prenom, attendu",
    [
        ("CARBONELL-ROMO", "Rosa Maria", "rosa.carbonell@lekreisker.fr"),
        ("HAMON-DIAZ", "Carolina", "carolina.hamon@lekreisker.fr"),
        ("LE JALU", "Jayaparathy", "jaya.lejalu@lekreisker.fr"),
        ("MORIO", "Erwann", "erwan.morio@lekreisker.fr"),
    ],
)
def test_les_quatre_cas_reels_se_resolvent(nom, prenom, attendu):
    from backend.services.rapprochement import rapprocher

    r = rapprocher(nom, prenom, _index())
    assert r.email == attendu
    assert r.approximatif, "l'égalité stricte n'a pas suffi : il faut le dire"
    assert r.methode != "exact"


def test_une_correspondance_exacte_nest_pas_signalee():
    from backend.services.rapprochement import rapprocher

    r = rapprocher("DURAND", "Paul", _index())
    assert r.email == "paul.durand@lekreisker.fr"
    assert r.methode == "exact"
    assert r.approximatif is False


def test_un_inconnu_reste_inconnu():
    from backend.services.rapprochement import rapprocher

    r = rapprocher("TROUVETOU", "Géo", _index())
    assert r.email is None
    assert r.methode == "aucun"


def test_deux_homonymes_ne_sont_jamais_departages():
    """Choisir reviendrait à tirer au sort."""
    from backend.services.rapprochement import construire_index, rapprocher

    index = construire_index([
        _compte("marie.martin@lekreisker.fr", "MARTIN", "Marie"),
        _compte("marie.martin2@lekreisker.fr", "MARTIN", "Marie"),
    ])
    r = rapprocher("MARTIN", "Marie", index)
    assert r.email is None
    assert r.methode == "ambigu"
    assert len(r.candidats) == 2


def test_la_tolerance_orthographique_sarrete_a_une_lettre():
    """Au-delà, ce ne sont plus deux graphies mais deux personnes."""
    from backend.services.rapprochement import construire_index, rapprocher

    index = construire_index([_compte("a@x.fr", "MARTIN", "Paul")])
    assert rapprocher("MARTIH", "Paul", index).email == "a@x.fr", "une lettre"
    assert rapprocher("MARTOH", "Paul", index).email is None, "deux lettres"


def test_un_prefixe_trop_court_ne_rapproche_rien():
    """« Jan » conviendrait à Janick, Janine et Janvier."""
    from backend.services.rapprochement import construire_index, rapprocher

    index = construire_index([_compte("j@x.fr", "MARTIN", "Janick")])
    assert rapprocher("MARTIN", "Jan", index).email is None
    assert rapprocher("MARTIN", "Jani", index).email == "j@x.fr"


def test_ladresse_rattrape_un_nom_ecrit_autrement():
    """L'annuaire sépare `LE JALU`, l'adresse colle `lejalu`."""
    from backend.services.rapprochement import construire_index, rapprocher

    index = construire_index([
        _compte("jaya.lejalu@lekreisker.fr", "LEJALU", "Jaya"),
    ])
    r = rapprocher("LE JALU", "Jaya", index)
    assert r.email == "jaya.lejalu@lekreisker.fr"


@pytest.mark.parametrize(
    "a, b, attendu",
    [
        ("erwan", "erwann", True),
        ("martin", "martih", True),
        ("martin", "matrin", False),
        ("martin", "martin", False),
        ("martin", "mart", False),
        ("", "a", True),
    ],
)
def test_distance_dune_lettre(a, b, attendu):
    from backend.services.rapprochement import distance_un

    assert distance_un(a, b) is attendu


def test_les_composantes_dun_nom_compose():
    from backend.services.rapprochement import parts

    assert parts("CARBONELL-ROMO") == ["carbonell", "romo"]
    assert parts("LE JALU") == ["le", "jalu"]
    assert parts("O'CONNOR") == ["o", "connor"]
    assert parts(None) == []


def test_la_flotte_relie_les_quatre_et_le_dit(monkeypatch):
    """Bout en bout : ils cessent d'être « sans compte », et on sait pourquoi."""
    from dataclasses import dataclass

    from backend.services.chromebooks import analyser_flotte

    @dataclass
    class P:
        nom: str
        prenom: str
        discipline: str = "Espagnol"
        code: str = "en_poste"

    r = analyser_flotte(
        [],
        [P("CARBONELL-ROMO", "Rosa Maria"), P("MORIO", "Erwann"),
         P("DURAND", "Paul")],
        ANNUAIRE,
    )
    assert r.sans_compte == []
    assert {p.nom for p in r.rapproches} == {"CARBONELL-ROMO", "MORIO"}
    assert any("règle plus souple" in a for a in r.avertissements)
