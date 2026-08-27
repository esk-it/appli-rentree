"""Tests d'unicité globale du login (Lot 2).

Le contrôle d'unicité **traverse tous les types et toutes les années**,
y compris les personnes sorties. Un login libéré n'est jamais recyclé.
"""
from __future__ import annotations

from backend.services.regles_metier import (
    login_est_libre,
    proposer_login_pour,
    proposer_suffixe,
)


class TestLoginEstLibre:
    def test_libre_quand_base_vide(self, session):
        assert login_est_libre(session, "jbars")

    def test_pris_apres_creation(self, session, personne_factory):
        personne_factory(login="jbars")
        assert not login_est_libre(session, "jbars")

    def test_login_vide_est_faux(self, session):
        assert not login_est_libre(session, "")

    def test_traverse_les_types(self, session, personne_factory):
        """Un adulte 'jbars' bloque un élève 'jbars' — la doc §3.2 le prescrit."""
        personne_factory(type="adulte", login="jbars")
        assert not login_est_libre(session, "jbars")


class TestProposerSuffixe:
    def test_base_libre_est_retournee_telle_quelle(self, session):
        r = proposer_suffixe(session, "jdupont")
        assert r is not None
        assert r.login_propose == "jdupont"
        assert r.suffixe_utilise == 0
        assert r.a_conflit is False
        assert r.personnes_en_conflit == []

    def test_conflit_donne_suffixe_2(self, session, personne_factory):
        personne_factory(login="jdupont")
        r = proposer_suffixe(session, "jdupont")
        assert r.login_propose == "jdupont1"
        assert r.suffixe_utilise == 1
        assert r.a_conflit is True
        assert len(r.personnes_en_conflit) == 1
        assert r.personnes_en_conflit[0].login == "jdupont"

    def test_conflit_multiple_donne_le_suffixe_suivant(self, session, personne_factory):
        personne_factory(login="jdupont")
        personne_factory(login="jdupont1")
        r = proposer_suffixe(session, "jdupont")
        assert r.login_propose == "jdupont2"
        assert r.suffixe_utilise == 2

    def test_login_libere_pas_recycle(self, session, personne_factory):
        """Prompt §6.2 : 'un login libéré n'est jamais recyclé'.
        Ici on simule un ancien élève encore en base (pas de suppression)."""
        # Personne sortie mais toujours au référentiel (jamais supprimée)
        personne_factory(type="eleve", id_charlemagne=1000, login="jdupont")
        # Un nouvel arrivant du même login veut le prendre
        r = proposer_suffixe(session, "jdupont")
        assert r.login_propose != "jdupont"
        assert r.login_propose == "jdupont1"

    def test_max_suffixes_atteint_renvoie_none(self, session, personne_factory):
        # La base plus les cinq premiers suffixes : plus rien de libre en
        # dessous de la limite d'essais.
        personne_factory(login="short")
        for i in range(1, 6):
            personne_factory(login=f"short{i}")
        r = proposer_suffixe(session, "short", max_essais=5)
        assert r is None

    def test_conflits_listes_pour_arbitrage(self, session, personne_factory):
        """Les personnes qui portent la base sont retournées pour permettre
        à l'utilisateur de trancher (même personne / personne distincte)."""
        p1 = personne_factory(
            type="eleve",
            id_charlemagne=100,
            login="pdupont",
            nom="DUPONT",
            prenom="Pierre",
        )
        p2 = personne_factory(
            type="adulte",
            id_charlemagne=50,
            login="pdupont1",
            nom="DUPONT",
            prenom="Paul",
        )
        r = proposer_suffixe(session, "pdupont")
        assert r.login_propose == "pdupont2"
        # Les deux Pierre/Paul sont listés dans le conflit
        ids = {c.personne_id for c in r.personnes_en_conflit}
        assert ids == {p1.id, p2.id}


class TestProposerLoginPour:
    """Wrapper qui combine `calculer_login_base` + `proposer_suffixe`."""

    def test_normalisation_et_proposition(self, session):
        r = proposer_login_pour(session, "Léa", "MARTIN")
        assert r.login_base == "lmartin"
        assert r.login_propose == "lmartin"
        assert r.suffixe_utilise == 0

    def test_conflit_apres_creation(self, session, personne_factory):
        personne_factory(login="lmartin")
        r = proposer_login_pour(session, "Léa", "MARTIN")
        assert r.login_propose == "lmartin1"

    def test_pas_de_nom_ni_prenom_renvoie_none(self, session):
        assert proposer_login_pour(session, "", "") is None


class TestScenariosPromptRefonte:
    """Reproduction des scénarios critiques du prompt de refonte."""

    def test_collision_eleve_adulte_jbars(self, session, personne_factory):
        """§3.2 des docs : Jean BARS prof recruté alors qu'un élève Julien BARS
        existe déjà — les deux 'jbars' ne doivent PAS entrer en collision."""
        # L'élève arrive en premier
        eleve = personne_factory(
            type="eleve",
            id_charlemagne=100,
            nom="BARS",
            prenom="Julien",
            login="jbars",
        )
        # Le prof arrive après
        r = proposer_login_pour(session, "Jean", "BARS")
        assert r.login_propose == "jbars1"
        assert r.a_conflit is True
        # L'élève est bien listé comme conflictant
        assert eleve.id in {c.personne_id for c in r.personnes_en_conflit}

    def test_homonyme_masque_par_depart_simultane(
        self, session, personne_factory
    ):
        """§3.2 + §7.2 : Pierre DUPONT part en juin, un autre Pierre DUPONT arrive
        en septembre. Le nouveau ne doit pas hériter du compte de l'ancien.

        Ici : l'ancien reste au référentiel (jamais supprimé), donc le nouveau
        obtient un suffixe distinct."""
        ancien = personne_factory(
            type="eleve",
            id_charlemagne=100,
            nom="DUPONT",
            prenom="Pierre",
            login="pdupont",
        )
        # Le nouveau Pierre DUPONT (id_ch différent) demande un login
        r = proposer_login_pour(session, "Pierre", "DUPONT")
        # Doit obtenir un suffixe — pas le login de l'ancien
        assert r.login_propose == "pdupont1"
        assert r.login_propose != ancien.login

    def test_suffixe_reste_fige_apres_creation(self, session, personne_factory):
        """§6.2 : 'pdupont1' reste 'pdupont1' même après le départ de 'pdupont'.

        L'ancien reste en base ; même si on ré-interroge, le suffixe attribué
        au nouveau ne bouge pas — c'est le rôle du figeage : le login est
        stocké dans Personne.login, jamais recalculé."""
        p1 = personne_factory(login="pdupont", nom="DUPONT", prenom="Pierre")
        p2 = personne_factory(login="pdupont1", nom="DUPONT", prenom="Paul")

        # Simulate : p1 "part" — dans notre modèle, la Personne reste en base.
        # Le login de p2 reste inchangé — c'est le rôle du champ figé.
        session.refresh(p2)
        assert p2.login == "pdupont1"

        # Une nouvelle personne "Pierre DUPONT" arrive : elle ne récupère
        # PAS pdupont (encore pris par p1 en base) ni pdupont1 (pris par p2)
        r = proposer_login_pour(session, "Pierre", "DUPONT")
        assert r.login_propose == "pdupont2"

    def test_changement_de_nom_ne_touche_pas_le_login(
        self, session, personne_factory
    ):
        """Prompt §12 : 'la personne reste la même, aucun compte n'est
        détruit ni recréé'. Ici on simule qu'une Personne existante voit son
        nom changer (au Lot 3 ce sera piloté par l'ingestion) — le login
        reste identique parce qu'il est stocké, pas recalculé."""
        p = personne_factory(nom="MARTIN", prenom="Léa", login="lmartin")
        # Changement de nom via mariage / correction état civil
        p.nom = "MARTIN-LE GALL"
        session.commit()
        session.refresh(p)
        assert p.login == "lmartin"  # inchangé
        # Une nouvelle Léa MARTIN qui arriverait est bien détectée en collision
        # sur le login (elle aurait aussi calculé "lmartin")
        r = proposer_login_pour(session, "Léa", "MARTIN")
        assert r.login_propose == "lmartin1"
