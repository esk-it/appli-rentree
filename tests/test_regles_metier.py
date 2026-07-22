"""Tests des règles métier — login normalisé, email, homonymes."""
from __future__ import annotations

import random

import pytest

from backend.services.regles_metier import (
    calculer_email,
    calculer_login_base,
    detecter_homonymes_ingestion,
    generer_mot_de_passe,
    normaliser_nom,
    normaliser_pour_email,
)


class TestLoginBase:
    """Cas alignés sur le XLSX historique pour garantir la compat des comptes."""

    @pytest.mark.parametrize(
        "prenom,nom,attendu",
        [
            ("Tifenn", "ARGOUARC'H", "targouarch"),
            ("Nawel", "BACH HAMBA", "nbachhamba"),
            ("Loris", "BEN HAMOU--PEPIN", "lbenhamoup"),  # tronqué à 10
            ("Mia", "BELLEC--ILY", "mbellecily"),
            ("Raphaël", "TROADEC", "rtroadec"),
            ("Léanne", "ABGRALL", "labgrall"),
            ("Alexandre", "DOUGUET", "adouguet"),
            ("Jean", "BARS", "jbars"),
        ],
    )
    def test_cas_du_xlsx_historique(self, prenom, nom, attendu):
        assert calculer_login_base(prenom, nom) == attendu

    def test_prenom_vide(self):
        assert calculer_login_base("", "DUPONT") == "dupont"

    def test_nom_vide(self):
        assert calculer_login_base("Jean", "") == "jean"

    def test_les_deux_vides(self):
        assert calculer_login_base("", "") == ""
        assert calculer_login_base(None, None) == ""

    def test_troncature_par_defaut_10(self):
        assert len(calculer_login_base("Jean", "A" * 30)) == 10

    def test_longueur_max_personnalisable(self):
        assert calculer_login_base("Jean", "ABCDEFGHIJKLMNO", longueur_max=15) == "jabcdefghijklmn"


class TestNormaliserNom:
    def test_accents_retires(self):
        assert normaliser_nom("Éléonore") == "eleonore"

    def test_apostrophes_retirees(self):
        assert normaliser_nom("ARGOUARC'H") == "argouarch"

    def test_tirets_retires(self):
        assert normaliser_nom("BEN-HAMOU") == "benhamou"

    def test_espaces_retires(self):
        assert normaliser_nom("BACH HAMBA") == "bachhamba"

    def test_seulement_a_z(self):
        assert normaliser_nom("Jean42-Marc!D'O") == "jeanmarcdo"


class TestEmail:
    """Format `prenom.nom@domaine` avec normalisation."""

    @pytest.mark.parametrize(
        "prenom,nom,domaine,attendu",
        [
            ("Tifenn", "ARGOUARC'H", "lekreisker.fr", "tifenn.argouarch@lekreisker.fr"),
            ("Nawel", "BACH HAMBA", "lekreisker.fr", "nawel.bach.hamba@lekreisker.fr"),
            (
                "Loris",
                "BEN HAMOU--PEPIN",
                "lekreisker.fr",
                "loris.ben.hamou-pepin@lekreisker.fr",
            ),
            (
                "Mia",
                "BELLEC--ILY",
                "lekreisker.fr",
                "mia.bellec-ily@lekreisker.fr",
            ),
            ("Raphaël", "TROADEC", "ndecleder.fr", "raphael.troadec@ndecleder.fr"),
            ("Léanne", "ABGRALL", "lekreisker.fr", "leanne.abgrall@lekreisker.fr"),
        ],
    )
    def test_cas_du_xlsx_historique(self, prenom, nom, domaine, attendu):
        assert calculer_email(prenom, nom, domaine) == attendu

    def test_domaine_change(self):
        assert calculer_email("Jean", "DUPONT", "test.fr") == "jean.dupont@test.fr"

    def test_prenom_vide(self):
        assert calculer_email("", "DUPONT", "lekreisker.fr") == "dupont@lekreisker.fr"

    def test_les_deux_vides(self):
        assert calculer_email("", "", "lekreisker.fr") == ""


class TestNormaliserPourEmail:
    def test_espaces_deviennent_points(self):
        assert normaliser_pour_email("Bach Hamba") == "bach.hamba"

    def test_doubles_tirets_compactes(self):
        assert normaliser_pour_email("Bellec--Ily") == "bellec-ily"

    def test_apostrophes_retirees(self):
        assert normaliser_pour_email("ARGOUARC'H") == "argouarch"


class TestMotDePasseUtilitaire:
    """Fonction utilitaire — non appelée en prod, mais utile pour tests."""

    def test_format(self):
        rng = random.Random(42)
        mdp = generer_mot_de_passe(rng)
        assert len(mdp) == 8
        assert mdp[0].isupper()
        assert mdp[1:6].islower()
        assert mdp[6:].isdigit()

    def test_reproductibilite_avec_seed(self):
        assert generer_mot_de_passe(random.Random(1)) == generer_mot_de_passe(random.Random(1))

    def test_diversite_sans_seed(self):
        mdps = {generer_mot_de_passe() for _ in range(20)}
        assert len(mdps) >= 15


class TestDetecterHomonymesIngestion:
    """Deux lignes de mêmes nom+prénom (normalisés) dans un même export."""

    def test_pas_de_paire_quand_unique(self):
        lignes = [
            {"nom": "MARTIN", "prenom": "Pierre"},
            {"nom": "DUPONT", "prenom": "Léa"},
        ]
        assert detecter_homonymes_ingestion(lignes) == []

    def test_paire_simple_detectee(self):
        lignes = [
            {"nom": "MARTIN", "prenom": "Pierre", "id_ch": 1},
            {"nom": "DUPONT", "prenom": "Léa", "id_ch": 2},
            {"nom": "MARTIN", "prenom": "Pierre", "id_ch": 3},
        ]
        paires = detecter_homonymes_ingestion(lignes)
        assert len(paires) == 1
        assert paires[0].cle_normalisee == ("MARTIN", "PIERRE")
        assert {l["id_ch"] for l in paires[0].lignes} == {1, 3}

    def test_triplet_donne_un_groupe(self):
        lignes = [
            {"nom": "MARTIN", "prenom": "Léa", "id_ch": 1},
            {"nom": "MARTIN", "prenom": "Léa", "id_ch": 2},
            {"nom": "MARTIN", "prenom": "Léa", "id_ch": 3},
        ]
        paires = detecter_homonymes_ingestion(lignes)
        assert len(paires) == 1
        assert len(paires[0].lignes) == 3

    def test_accents_ignores_dans_la_cle(self):
        """`Léa` et `Lea` sont détectés comme homonymes."""
        lignes = [
            {"nom": "MARTIN", "prenom": "Léa", "id_ch": 1},
            {"nom": "MARTIN", "prenom": "Lea", "id_ch": 2},
        ]
        assert len(detecter_homonymes_ingestion(lignes)) == 1

    def test_casse_ignoree(self):
        lignes = [
            {"nom": "Martin", "prenom": "Léa"},
            {"nom": "MARTIN", "prenom": "léa"},
        ]
        assert len(detecter_homonymes_ingestion(lignes)) == 1

    def test_lignes_sans_nom_ni_prenom_ignorees(self):
        lignes = [
            {"nom": None, "prenom": None},
            {"nom": "", "prenom": ""},
        ]
        assert detecter_homonymes_ingestion(lignes) == []
