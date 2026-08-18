"""Tests du modèle Personne — clé pivot, badge, email calculé, unicité."""
from __future__ import annotations

import pytest
from sqlalchemy.exc import IntegrityError

from backend.models import Personne


class TestFormuleBadge:
    """La formule badge est le socle de l'interop KoXo / JPM / CardStudio.

    Vérifiée sur 1820/1820 lignes de l'export historique dans la doc.
    """

    def test_eleve_id_1(self):
        assert Personne.calculer_badge("eleve", 1) == 10010

    def test_eleve_id_5292_donne_62920(self):
        """Exemple documenté dans gestion-rentree-logique.md §4.1."""
        assert Personne.calculer_badge("eleve", 5292) == 62920

    def test_eleve_id_7544(self):
        assert Personne.calculer_badge("eleve", 7544) == 85440

    def test_eleve_id_zero(self):
        assert Personne.calculer_badge("eleve", 0) == 10000

    def test_adulte_pas_de_formule(self):
        """Adulte : numérotation propre reprise telle quelle."""
        assert Personne.calculer_badge("adulte", 60) == 60
        assert Personne.calculer_badge("adulte", 313) == 313


class TestClePivot:
    def test_eleve_donne_prefixe_E(self, session, personne_factory):
        p = personne_factory(type="eleve", id_charlemagne=5292)
        assert p.cle_pivot == "E5292"

    def test_adulte_donne_prefixe_A(self, session, personne_factory):
        p = personne_factory(type="adulte", id_charlemagne=60)
        assert p.cle_pivot == "A60"


class TestUnicite:
    """Prompt §5 : deux espaces d'ID Charlemagne se télescopent — un E60 et un
    A60 doivent coexister sans conflit."""

    def test_meme_id_types_differents_coexistent(
        self, session, personne_factory
    ):
        eleve = personne_factory(type="eleve", id_charlemagne=60, login="eleve60")
        adulte = personne_factory(type="adulte", id_charlemagne=60, login="adulte60")
        # Deux entités distinctes
        assert eleve.id != adulte.id
        assert eleve.cle_pivot == "E60"
        assert adulte.cle_pivot == "A60"

    def test_meme_type_meme_id_est_bloque(
        self, session, personne_factory
    ):
        personne_factory(type="eleve", id_charlemagne=1234, login="premier")
        with pytest.raises(IntegrityError):
            personne_factory(
                type="eleve", id_charlemagne=1234, login="second"
            )

    def test_login_unique_globalement(self, session, personne_factory):
        """L'unicité du login traverse les types — cas 'jbars' collision élève/adulte."""
        personne_factory(type="adulte", id_charlemagne=1, login="jbars")
        with pytest.raises(IntegrityError):
            personne_factory(
                type="eleve", id_charlemagne=99, login="jbars"
            )


class TestEmailCalcule:
    """Email = `prenom.nom@site.domaine_mail` — surtout pas `login@domaine`.

    Le login est `initiale+nom` (`jdupont`), l'adresse est `jean.dupont`.
    Les confondre produirait des adresses inexistantes dans tous les exports.
    """

    def test_ndk_donne_lekreisker(self, session, site_factory, personne_factory):
        ndk = site_factory("NDK")
        p = personne_factory(
            nom="DUPONT", prenom="Jean", login="jdupont", site_id=ndk.id
        )
        # Recharge avec la relation site chargée
        session.refresh(p)
        assert p.email == "jean.dupont@lekreisker.fr"

    def test_nde_donne_ndecleder(self, session, site_factory, personne_factory):
        nde = site_factory("NDE")
        p = personne_factory(
            nom="MARTIN", prenom="Marie", login="mmartin", site_id=nde.id
        )
        session.refresh(p)
        assert p.email == "marie.martin@ndecleder.fr"

    def test_accents_et_apostrophes_normalises(
        self, session, site_factory, personne_factory
    ):
        ndk = site_factory("NDK")
        p = personne_factory(
            nom="L'HÉLIAS", prenom="Gwenaëlle", login="glhelias", site_id=ndk.id
        )
        session.refresh(p)
        assert p.email == "gwenaelle.lhelias@lekreisker.fr"

    def test_sans_site_donne_none(self, session, personne_factory):
        p = personne_factory(login="orphelin", site_id=None)
        assert p.email is None


class TestEmailConstate:
    """Une adresse constatée fait autorité et n'est jamais recalculée.

    Sur l'export réel, une formule ne retrouve que ~93 % des adresses en
    place : noms composés tronqués, séparateurs incohérents, prénoms
    orthographiés autrement dans Charlemagne. Recalculer casserait les
    comptes concernés.
    """

    def test_constate_prime_sur_le_calcul(
        self, session, site_factory, personne_factory
    ):
        ndk = site_factory("NDK")
        p = personne_factory(
            nom="HENOCQ KERAUTRET",
            prenom="Sarah",
            login="shenocqker",
            site_id=ndk.id,
            email_constate="sarah.henocq@lekreisker.fr",
        )
        session.refresh(p)
        # Le calcul donnerait sarah.henocq.kerautret — le compte réel est autre
        assert p.email == "sarah.henocq@lekreisker.fr"
        assert p.email_est_constate is True

    def test_calcule_sans_constat(self, session, site_factory, personne_factory):
        ndk = site_factory("NDK")
        p = personne_factory(nom="NEUF", prenom="Jean", login="jneuf", site_id=ndk.id)
        session.refresh(p)
        assert p.email == "jean.neuf@lekreisker.fr"
        assert p.email_est_constate is False

    def test_constate_sans_site_reste_disponible(self, session, personne_factory):
        """Une adresse constatée n'a pas besoin du site : elle est complète."""
        p = personne_factory(
            login="sanssite", site_id=None, email_constate="a.b@lekreisker.fr"
        )
        assert p.email == "a.b@lekreisker.fr"


class TestSitePrefixeRacineOU:
    def test_format_racine(self, session, site_factory):
        nde = site_factory("NDE")
        assert nde.prefixe_racine_ou() == "/2. NDE"
        ndk = site_factory("NDK")
        assert ndk.prefixe_racine_ou() == "/3. NDK"
        su = site_factory("SU")
        assert su.prefixe_racine_ou() == "/4. SU"
