"""Deux personnes ne se gênent que si elles partagent un annuaire.

L'établissement tient un serveur KoXo par domaine Active Directory, pas un
par site : NDK et SU ont chacun le leur, NDE n'en a aucun. L'arrivée de NDE
levait cinquante-six collisions d'identifiant dont aucune n'était réelle —
ses élèves étaient comparés à ceux de deux annuaires où ils n'ont pas de
compte.
"""
from __future__ import annotations

import pytest


@pytest.fixture()
def trois_sites(session, site_factory):
    """NDK et SU ont leur serveur, NDE n'en a pas."""
    ndk = site_factory("NDK")
    su = site_factory("SU")
    nde = site_factory("NDE")
    ndk.base_koxo = "NDK"
    su.base_koxo = "SU"
    nde.base_koxo = None
    session.commit()
    return ndk, su, nde


def test_un_eleve_est_dans_lannuaire_de_son_site(session, trois_sites):
    from backend.services.regles_metier import bases_koxo

    ndk, su, _ = trois_sites
    assert bases_koxo(session, type_personne="eleve", site_id=ndk.id) == {"NDK"}
    assert bases_koxo(session, type_personne="eleve", site_id=su.id) == {"SU"}


def test_un_eleve_de_nde_nest_dans_aucun(session, trois_sites):
    """C'est tout le sujet : NDE n'a pas de KoXo."""
    from backend.services.regles_metier import bases_koxo

    _, _, nde = trois_sites
    assert bases_koxo(session, type_personne="eleve", site_id=nde.id) == set()


def test_un_adulte_est_dans_tous_les_annuaires(session, trois_sites):
    """Les professeurs enseignent des deux côtés : leurs comptes aussi."""
    from backend.services.regles_metier import bases_koxo

    ndk, _, _ = trois_sites
    assert bases_koxo(session, type_personne="adulte", site_id=ndk.id) == {"NDK", "SU"}
    assert bases_koxo(session, type_personne="adulte", site_id=None) == {"NDK", "SU"}


def test_un_site_inconnu_suppose_le_pire(session, trois_sites):
    """Se taire ferait passer une vraie collision : on ne parie pas."""
    from backend.services.regles_metier import bases_koxo

    assert bases_koxo(session, type_personne="eleve", site_id=None) == {"NDK", "SU"}


# ---------------------------------------------------------------------------
# Le filtrage des conflits
# ---------------------------------------------------------------------------


def test_un_eleve_nde_ne_percute_personne(session, trois_sites, personne_factory):
    from backend.services.regles_metier import collision_reelle, proposer_suffixe

    ndk, _, nde = trois_sites
    personne_factory(site_id=ndk.id, nom="MARC", prenom="Clara", login="cmarc")

    p = proposer_suffixe(session, "cmarc")
    assert p.a_conflit, "le référentiel voit bien l'identifiant pris"
    assert collision_reelle(
        session, type_personne="eleve", site_id=nde.id,
        personnes_en_conflit=p.personnes_en_conflit,
    ) == [], "mais ils ne partagent aucun annuaire"


def test_deux_eleves_du_meme_site_se_percutent(session, trois_sites,
                                               personne_factory):
    from backend.services.regles_metier import collision_reelle, proposer_suffixe

    ndk, _, _ = trois_sites
    personne_factory(site_id=ndk.id, nom="MARC", prenom="Clara", login="cmarc")

    p = proposer_suffixe(session, "cmarc")
    assert collision_reelle(
        session, type_personne="eleve", site_id=ndk.id,
        personnes_en_conflit=p.personnes_en_conflit,
    )


def test_deux_eleves_de_sites_differents_ne_se_percutent_pas(
    session, trois_sites, personne_factory
):
    """Lou-Ann BERNARD à SU et Liam BERNARD à NDK : deux annuaires, deux
    comptes, aucun conflit."""
    from backend.services.regles_metier import collision_reelle, proposer_suffixe

    ndk, su, _ = trois_sites
    personne_factory(site_id=ndk.id, nom="BERNARD", prenom="Liam", login="lbernard")

    p = proposer_suffixe(session, "lbernard")
    assert collision_reelle(
        session, type_personne="eleve", site_id=su.id,
        personnes_en_conflit=p.personnes_en_conflit,
    ) == []


def test_un_adulte_percute_un_eleve_du_meme_annuaire(session, trois_sites,
                                                     personne_factory):
    """Dans un annuaire, l'identifiant est unique pour tout le monde — les
    groupes primaires n'y changent rien."""
    from backend.services.regles_metier import collision_reelle, proposer_suffixe

    ndk, _, _ = trois_sites
    personne_factory(site_id=ndk.id, nom="CUEFF", prenom="Clémence", login="ccueff")

    p = proposer_suffixe(session, "ccueff")
    assert collision_reelle(
        session, type_personne="adulte", site_id=None,
        personnes_en_conflit=p.personnes_en_conflit,
    )


def test_un_adulte_ne_percute_pas_un_eleve_de_nde(session, trois_sites,
                                                  personne_factory):
    from backend.services.regles_metier import collision_reelle, proposer_suffixe

    _, _, nde = trois_sites
    personne_factory(site_id=nde.id, nom="MARC", prenom="Calie", login="cmarc")

    p = proposer_suffixe(session, "cmarc")
    assert collision_reelle(
        session, type_personne="adulte", site_id=None,
        personnes_en_conflit=p.personnes_en_conflit,
    ) == []


def test_sans_configuration_chaque_site_est_son_propre_annuaire(
    session, site_factory
):
    """Le repli : une base migrée ne doit pas cesser de voir les collisions.

    Tant qu'aucun site ne déclare son serveur, on garde l'ancienne lecture.
    Ne plus rien signaler serait bien pire que d'en signaler trop.
    """
    from backend.services.regles_metier import bases_koxo

    ndk = site_factory("NDK")
    site_factory("SU")
    assert bases_koxo(session, type_personne="eleve", site_id=ndk.id) == {"NDK"}
    assert bases_koxo(session, type_personne="adulte", site_id=None) == {"NDK", "SU"}


def test_une_seule_declaration_suffit_a_activer_la_regle(session, site_factory):
    """Dès qu'un site déclare, les autres sont lus à la lettre — un site
    sans serveur déclaré n'en a pas, et c'est bien ce qu'on veut dire."""
    from backend.services.regles_metier import bases_koxo

    ndk = site_factory("NDK")
    nde = site_factory("NDE")
    ndk.base_koxo = "NDK"
    session.commit()

    assert bases_koxo(session, type_personne="eleve", site_id=ndk.id) == {"NDK"}
    assert bases_koxo(session, type_personne="eleve", site_id=nde.id) == set()
