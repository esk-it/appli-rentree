"""Reprise sur indisponibilité passagère de Google.

Un relevé de 2700 comptes qui abandonne sur un 503 est une perte sèche :
l'erreur ne vient pas de nous et disparaît d'elle-même. Une erreur qui
tient à la requête, elle, doit remonter tout de suite.
"""
from __future__ import annotations

import pytest


class _Reponse:
    def __init__(self, status):
        self.status = status


class _ErreurGoogle(Exception):
    def __init__(self, status):
        super().__init__(f"HTTP {status}")
        self.resp = _Reponse(status)


@pytest.mark.parametrize("code", [403, 429, 500, 502, 503, 504])
def test_rejoue_les_indisponibilites(code):
    from backend.services.google_api import reessayer

    essais = {"n": 0}

    def appel():
        essais["n"] += 1
        if essais["n"] < 3:
            raise _ErreurGoogle(code)
        return "ok"

    assert reessayer(appel, pause=lambda _: None) == "ok"
    assert essais["n"] == 3


@pytest.mark.parametrize("code", [400, 401, 404, 409, 412])
def test_ne_rejoue_pas_une_erreur_de_requete(code):
    """Une OU absente ou un droit manquant : réessayer retarde le diagnostic."""
    from backend.services.google_api import reessayer

    essais = {"n": 0}

    def appel():
        essais["n"] += 1
        raise _ErreurGoogle(code)

    with pytest.raises(_ErreurGoogle):
        reessayer(appel, pause=lambda _: None)
    assert essais["n"] == 1, "un seul essai pour une erreur définitive"


def test_abandonne_apres_le_dernier_essai():
    from backend.services.google_api import reessayer

    essais = {"n": 0}

    def appel():
        essais["n"] += 1
        raise _ErreurGoogle(503)

    with pytest.raises(_ErreurGoogle):
        reessayer(appel, tentatives=4, pause=lambda _: None)
    assert essais["n"] == 4


def test_une_erreur_sans_statut_remonte_telle_quelle():
    """Une panne réseau n'a pas de code HTTP : on ne la classe pas passagère."""
    from backend.services.google_api import reessayer

    essais = {"n": 0}

    def appel():
        essais["n"] += 1
        raise OSError("connexion perdue")

    with pytest.raises(OSError):
        reessayer(appel, pause=lambda _: None)
    assert essais["n"] == 1


def test_attente_croissante():
    """Marteler un service indisponible l'aide rarement à se rétablir."""
    from backend.services.google_api import reessayer

    attentes = []

    def appel():
        raise _ErreurGoogle(503)

    with pytest.raises(_ErreurGoogle):
        reessayer(appel, tentatives=4, pause=attentes.append)
    assert attentes == [2.0, 4.0, 8.0]
