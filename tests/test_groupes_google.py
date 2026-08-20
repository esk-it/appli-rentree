"""Tests de la synchronisation des groupes de classe."""
from __future__ import annotations

import pytest


@pytest.fixture()
def contexte(session, site_factory, annee_factory, personne_factory):
    """Une classe avec son groupe, deux élèves inscrits."""
    from backend.models import Snapshot, TableCorrespondance

    site = site_factory("NDK")
    annee = annee_factory("2026-2027")
    session.add(
        TableCorrespondance(
            site_id=site.id, classe_charlemagne_long="SECONDE 1",
            classe_code_court="2_1", groupe_google="2nde-1@lekreisker.fr",
            ou_pre_rentree="/3. NDK/NDK2027", ou_definitive="/3. NDK/NDK2027/2_1",
        )
    )
    session.commit()

    def _eleve(nom, prenom, login, classe="2_1"):
        p = personne_factory(
            nom=nom, prenom=prenom, login=login, site_id=site.id,
            email_constate=f"{prenom.lower()}.{nom.lower()}@lekreisker.fr",
        )
        session.add(Snapshot(personne_id=p.id, annee_scolaire_id=annee.id,
                             nom=nom, prenom=prenom, classe=classe))
        session.commit()
        return p

    return {"site": site, "annee": annee, "eleve": _eleve}


def test_ajoute_les_manquants(session, contexte):
    from backend.services.groupes_google import calculer_diff_groupes

    contexte["eleve"]("DUPONT", "Jean", "jdupont")
    r = calculer_diff_groupes(session, {}, annee_id=contexte["annee"].id)
    assert r.nb_a_ajouter == 1
    assert r.diffs[0].a_ajouter == ["jean.dupont@lekreisker.fr"]


def test_retire_ceux_qui_ne_sont_plus_de_la_classe(session, contexte):
    """C'est ce que le CSV ne sait pas faire : un groupe garde ses anciens."""
    from backend.services.groupes_google import calculer_diff_groupes

    contexte["eleve"]("DUPONT", "Jean", "jdupont")
    parti = contexte["eleve"]("PARTI", "Luc", "lparti", classe="AUTRE")

    r = calculer_diff_groupes(
        session,
        {"2nde-1@lekreisker.fr": ["jean.dupont@lekreisker.fr", parti.email_constate]},
        annee_id=contexte["annee"].id,
    )
    assert r.nb_a_ajouter == 0
    assert r.diffs[0].a_retirer == ["luc.parti@lekreisker.fr"]
    assert r.diffs[0].deja_membres == 1


def test_un_membre_inconnu_nest_jamais_retire(session, contexte):
    """Un professeur ou une adresse de service : on ignore pourquoi il est là."""
    from backend.services.groupes_google import calculer_diff_groupes

    contexte["eleve"]("DUPONT", "Jean", "jdupont")
    r = calculer_diff_groupes(
        session,
        {"2nde-1@lekreisker.fr": ["jean.dupont@lekreisker.fr", "vie.scolaire@lekreisker.fr"]},
        annee_id=contexte["annee"].id,
    )
    assert r.diffs[0].a_retirer == []
    assert r.diffs[0].inconnus == ["vie.scolaire@lekreisker.fr"]
    assert any("laissés en place" in a for a in r.avertissements)


def test_groupe_deja_conforme(session, contexte):
    from backend.services.groupes_google import calculer_diff_groupes

    contexte["eleve"]("DUPONT", "Jean", "jdupont")
    r = calculer_diff_groupes(
        session,
        {"2nde-1@lekreisker.fr": ["jean.dupont@lekreisker.fr"]},
        annee_id=contexte["annee"].id,
    )
    assert r.nb_a_ajouter == 0 and r.nb_a_retirer == 0
    assert r.diffs[0].nb_mouvements == 0


def test_classe_sans_adresse_de_groupe_est_signalee(
    session, contexte, site_factory
):
    """Inventer une adresse serait pire que de ne rien faire."""
    from backend.models import TableCorrespondance
    from backend.services.groupes_google import calculer_diff_groupes

    session.add(
        TableCorrespondance(
            site_id=contexte["site"].id, classe_charlemagne_long="SECONDE 2",
            classe_code_court="2_2", groupe_google=None,
            ou_pre_rentree="/3. NDK/NDK2027", ou_definitive="/3. NDK/NDK2027/2_2",
        )
    )
    session.commit()
    contexte["eleve"]("AUTRE", "Ana", "aautre", classe="2_2")

    r = calculer_diff_groupes(session, {}, annee_id=contexte["annee"].id)
    assert "2_2" in r.classes_sans_groupe
    assert any("aucune adresse de groupe" in a for a in r.avertissements)


def test_adresse_calculee_quand_rien_nest_constate(
    session, contexte, personne_factory
):
    from backend.models import Snapshot
    from backend.services.groupes_google import calculer_diff_groupes

    p = personne_factory(
        nom="SANSMAIL", prenom="Zoe", login="zsansmail",
        site_id=contexte["site"].id, email_constate=None,
    )
    session.add(Snapshot(personne_id=p.id, annee_scolaire_id=contexte["annee"].id,
                         nom="SANSMAIL", prenom="Zoe", classe="2_1"))
    session.commit()

    r = calculer_diff_groupes(session, {}, annee_id=contexte["annee"].id)
    assert "zoe.sansmail@lekreisker.fr" in r.diffs[0].a_ajouter


def test_annee_introuvable(session, contexte):
    from backend.services.groupes_google import calculer_diff_groupes

    with pytest.raises(ValueError, match="introuvable"):
        calculer_diff_groupes(session, {}, annee_id=99999)


def test_groupe_absent_de_google_retient_ses_ajouts(session, contexte):
    """Un groupe vide se remplit ; un groupe absent, non.

    Les confondre ferait planifier des ajouts qui échouent un par un, sans
    que rien ne l'ait annoncé — le défaut même que ce module doit éviter.
    """
    from backend.services.groupes_google import calculer_diff_groupes

    contexte["eleve"]("DUPONT", "Jean", "jdupont")
    r = calculer_diff_groupes(
        session, {"2nde-1@lekreisker.fr": None}, annee_id=contexte["annee"].id
    )

    assert r.nb_a_ajouter == 0, "rien ne doit être tenté dans un groupe absent"
    assert r.nb_retenus == 1
    assert r.groupes_absents == ["2nde-1@lekreisker.fr"]
    assert r.diffs[0].existe is False
    assert r.diffs[0].retenus == ["jean.dupont@lekreisker.fr"]
    assert any("n'existent pas dans Google" in a for a in r.avertissements)


def test_groupe_vide_se_remplit_normalement(session, contexte):
    """Le pendant du test précédent : `[]` n'est pas `None`."""
    from backend.services.groupes_google import calculer_diff_groupes

    contexte["eleve"]("DUPONT", "Jean", "jdupont")
    r = calculer_diff_groupes(
        session, {"2nde-1@lekreisker.fr": []}, annee_id=contexte["annee"].id
    )

    assert r.nb_a_ajouter == 1
    assert r.nb_retenus == 0
    assert r.groupes_absents == []
    assert r.diffs[0].existe is True


def test_site_entier_sans_eleve_est_signale(
    session, contexte, site_factory
):
    """Une classe vide est banale ; un site entier vide signale un export manquant."""
    from backend.models import TableCorrespondance
    from backend.services.groupes_google import calculer_diff_groupes

    autre = site_factory("NDE")
    session.add(
        TableCorrespondance(
            site_id=autre.id, classe_charlemagne_long="SIXIEME VERTE",
            classe_code_court="6V", groupe_google="6eme-verte@ndecleder.fr",
            ou_pre_rentree="/2 NDE/NDE2027", ou_definitive="/2 NDE/NDE2027/6V",
        )
    )
    session.commit()
    contexte["eleve"]("DUPONT", "Jean", "jdupont")  # NDK seulement

    r = calculer_diff_groupes(session, {}, annee_id=contexte["annee"].id)

    assert r.sites_sans_eleve == ["NDE"]
    assert "NDK" not in r.sites_sans_eleve
    assert any("Aucun élève pour l'année préparée" in a for a in r.avertissements)


def test_groupes_a_creer_porte_de_quoi_les_creer(session, contexte):
    """`2_1` ne dit rien dans la console Google : le nom vient du libellé long."""
    from backend.services.groupes_google import (
        calculer_diff_groupes,
        groupes_a_creer,
    )

    contexte["eleve"]("DUPONT", "Jean", "jdupont")
    r = calculer_diff_groupes(
        session, {"2nde-1@lekreisker.fr": None}, annee_id=contexte["annee"].id
    )
    creations = groupes_a_creer(session, r)

    assert len(creations) == 1
    c = creations[0]
    assert c.adresse == "2nde-1@lekreisker.fr"
    assert c.nom == "SECONDE 1 (NDK)"
    assert "2026-2027" in c.description
    assert c.nb_membres_attendus == 1, "les ajouts retenus reprendront après création"


def test_aucun_groupe_a_creer_quand_tout_existe(session, contexte):
    from backend.services.groupes_google import (
        calculer_diff_groupes,
        groupes_a_creer,
    )

    contexte["eleve"]("DUPONT", "Jean", "jdupont")
    r = calculer_diff_groupes(
        session, {"2nde-1@lekreisker.fr": []}, annee_id=contexte["annee"].id
    )
    assert groupes_a_creer(session, r) == []


def test_libelle_partage_est_desambigue_par_le_code(session, contexte):
    """`term-g5a` et `term-g5b` portent le même libellé long dans la Table.

    Leur donner le même nom rendrait la console Google illisible, alors que
    ce sont deux listes distinctes.
    """
    from backend.models import TableCorrespondance
    from backend.services.groupes_google import (
        calculer_diff_groupes,
        groupes_a_creer,
    )

    site = contexte["site"]
    for court, adresse in (("T_G5A", "term-g5a@lekreisker.fr"),
                           ("T_G5B", "term-g5b@lekreisker.fr")):
        session.add(
            TableCorrespondance(
                site_id=site.id, classe_charlemagne_long="TERMINALE G5",
                classe_code_court=court, groupe_google=adresse,
                ou_pre_rentree="/3. NDK/NDK2027",
                ou_definitive=f"/3. NDK/NDK2027/{court}",
            )
        )
    session.commit()

    r = calculer_diff_groupes(
        session,
        {"term-g5a@lekreisker.fr": None, "term-g5b@lekreisker.fr": None,
         "2nde-1@lekreisker.fr": []},
        annee_id=contexte["annee"].id,
    )
    noms = {c.adresse: c.nom for c in groupes_a_creer(session, r)}

    assert noms["term-g5a@lekreisker.fr"] == "TERMINALE G5 (NDK) — T_G5A"
    assert noms["term-g5b@lekreisker.fr"] == "TERMINALE G5 (NDK) — T_G5B"
    assert len(set(noms.values())) == 2


def test_les_groupes_utiles_passent_devant(session, contexte):
    """Celui dont l'absence coûte quelque chose aujourd'hui vient en premier."""
    from backend.models import TableCorrespondance
    from backend.services.groupes_google import (
        calculer_diff_groupes,
        groupes_a_creer,
    )

    session.add(
        TableCorrespondance(
            site_id=contexte["site"].id, classe_charlemagne_long="SECONDE 9",
            classe_code_court="2_9", groupe_google="2nde-9@lekreisker.fr",
            ou_pre_rentree="/3. NDK/NDK2027", ou_definitive="/3. NDK/NDK2027/2_9",
        )
    )
    session.commit()
    contexte["eleve"]("DUPONT", "Jean", "jdupont")  # classe 2_1

    r = calculer_diff_groupes(
        session,
        {"2nde-1@lekreisker.fr": None, "2nde-9@lekreisker.fr": None},
        annee_id=contexte["annee"].id,
    )
    creations = groupes_a_creer(session, r)

    assert creations[0].adresse == "2nde-1@lekreisker.fr"
    assert creations[0].nb_membres_attendus == 1
    assert creations[1].nb_membres_attendus == 0
