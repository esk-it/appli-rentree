"""Tests des règles métier (login KoXo, email, mot de passe).

Cas alignés sur le XLSX historique de l'ESK pour garantir qu'on ne
casse pas la compat des comptes existants.
"""
from __future__ import annotations

import random

import pytest

from backend.services.regles_metier import (
    email_lekreisker,
    generer_mot_de_passe,
    groupe_primaire_koxo,
    login_koxo,
    normaliser_pour_email,
    normaliser_pour_login,
)


class TestLoginKoxo:
    """Vérifie l'algorithme de login : première lettre prénom + nom (max 10)."""

    @pytest.mark.parametrize(
        "prenom,nom,attendu",
        [
            ("Tifenn", "ARGOUARC'H", "targouarch"),  # apostrophe retirée
            ("Nawel", "BACH HAMBA", "nbachhamba"),  # espace retiré
            ("Loris", "BEN HAMOU--PEPIN", "lbenhamoup"),  # tronqué à 10
            ("Mia", "BELLEC--ILY", "mbellecily"),  # double tiret compacté
            ("Raphaël", "TROADEC", "rtroadec"),  # accent retiré
            ("Léanne", "ABGRALL", "labgrall"),  # accent retiré
            ("Alexandre", "DOUGUET", "adouguet"),  # cas simple
        ],
    )
    def test_cas_du_xlsx_historique(self, prenom, nom, attendu):
        assert login_koxo(prenom, nom) == attendu

    def test_prenom_vide_donne_juste_le_nom(self):
        assert login_koxo("", "DUPONT") == "dupont"

    def test_nom_tres_long_est_tronque(self):
        assert len(login_koxo("Jean", "ABCDEFGHIJKLMNOPQRSTUVWXYZ")) == 10

    def test_caracteres_speciaux_supprimes(self):
        # Anciennement des bugs sur les chars non-ASCII
        assert "?" not in login_koxo("Jérémie", "MAR&IN-LE/CLERC")


class TestEmailLekreisker:
    """Vérifie le format email standard."""

    @pytest.mark.parametrize(
        "prenom,nom,attendu",
        [
            ("Tifenn", "ARGOUARC'H", "tifenn.argouarch@lekreisker.fr"),
            ("Nawel", "BACH HAMBA", "nawel.bach.hamba@lekreisker.fr"),
            ("Loris", "BEN HAMOU--PEPIN", "loris.ben.hamou-pepin@lekreisker.fr"),
            ("Mia", "BELLEC--ILY", "mia.bellec-ily@lekreisker.fr"),
            ("Raphaël", "TROADEC", "raphael.troadec@lekreisker.fr"),
            ("Léanne", "ABGRALL", "leanne.abgrall@lekreisker.fr"),
        ],
    )
    def test_cas_du_xlsx_historique(self, prenom, nom, attendu):
        assert email_lekreisker(prenom, nom) == attendu

    def test_domaine_custom(self):
        assert email_lekreisker("Jean", "DUPONT", domaine="autre.fr") == (
            "jean.dupont@autre.fr"
        )

    def test_prenom_vide(self):
        assert email_lekreisker("", "DUPONT") == "dupont@lekreisker.fr"


class TestMotDePasse:
    def test_format_par_defaut(self):
        rng = random.Random(42)
        mdp = generer_mot_de_passe(rng)
        assert len(mdp) == 8  # 6 lettres + 2 chiffres
        # Première lettre en majuscule
        assert mdp[0].isupper()
        # Le reste : 5 lettres minuscules + 2 chiffres
        assert mdp[1:6].islower()
        assert mdp[6:].isdigit()

    def test_reproductibilite_avec_seed(self):
        """Même seed = même MDP, pour faciliter le débogage."""
        rng1 = random.Random(42)
        rng2 = random.Random(42)
        assert generer_mot_de_passe(rng1) == generer_mot_de_passe(rng2)

    def test_diversite_sans_seed(self):
        """Sans seed, on doit avoir des MDP variés."""
        mdps = {generer_mot_de_passe() for _ in range(20)}
        assert len(mdps) >= 15  # forte diversité attendue


class TestGroupePrimaire:
    def test_eleve(self):
        assert groupe_primaire_koxo(est_adulte=False) == "Elèves"

    def test_adulte(self):
        assert groupe_primaire_koxo(est_adulte=True) == "Professeurs"


class TestNormalisation:
    def test_login_ne_garde_que_az(self):
        assert normaliser_pour_login("Jean-Marc D'O") == "jeanmarcdo"

    def test_email_respecte_separateurs(self):
        # Espaces → points par défaut
        assert normaliser_pour_email("Bach Hamba") == "bach.hamba"
        # Tirets doubles → simples
        assert normaliser_pour_email("Bellec--Ily") == "bellec-ily"
