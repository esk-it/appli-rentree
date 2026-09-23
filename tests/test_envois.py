# -*- coding: utf-8 -*-
"""Ce qui est parti chez qui, et ce qui a bougé depuis.

La question qui revient chaque semaine : « qu'est-ce qui a changé depuis
la dernière fois que j'ai envoyé ? » Sans réponse, on renvoie tout le
monde — ce qui refait des comptes qui existent et réimprime des cartes
déjà faites.

Ce que ces tests protègent : un envoi garde **ce qu'il contenait**, et la
comparaison distingue un élève qui arrive d'un élève qui a simplement
changé de classe. Les confondre ferait créer un second compte à
quelqu'un qui en a déjà un.
"""
from __future__ import annotations

import pytest

# Les imports de modèles et de services restent **dans** les tests : le
# conftest purge le cache d'imports entre deux tests pour rebâtir la base,
# et un nom capturé au chargement du module désignerait l'ancienne classe.


@pytest.fixture()
def eleve(session, personne_factory):
    from backend.models import Snapshot

    n = {"i": 0}

    def _creer(annee_id, classe, nom=None):
        n["i"] += 1
        p = personne_factory(
            type="eleve",
            id_charlemagne=7000 + n["i"],
            nom=nom or f"NOM{n['i']}",
            prenom="Test",
            login=f"e{n['i']}",
        )
        session.add(
            Snapshot(
                personne_id=p.id, annee_scolaire_id=annee_id,
                nom=p.nom, prenom=p.prenom, classe=classe,
            )
        )
        p.classe = classe
        session.commit()
        return p

    return _creer


def test_sans_envoi_precedent_tout_le_monde_est_entrant(session, annee_factory, eleve):
    """C'est exact, et c'est ce que le premier envoi contiendra."""
    from backend.services.envois import etat
    an = annee_factory("2026-2027")
    eleve(an.id, "61")
    eleve(an.id, "62")

    e = etat(session, "sodexo", an.id)
    assert e.jamais_envoye
    assert e.nb_actuels == 2
    assert e.nb_changements == 2
    assert {c.classe for c in e.classes} == {"61", "62"}
    assert all(len(c.entrants) == 1 for c in e.classes)


def test_apres_un_envoi_plus_rien_n_a_bouge(session, annee_factory, eleve):
    from backend.services.envois import enregistrer, etat
    an = annee_factory("2026-2027")
    eleve(an.id, "61")
    eleve(an.id, "62")

    enregistrer(session, systeme="sodexo", annee_id=an.id, declare=True)
    e = etat(session, "sodexo", an.id)

    assert not e.jamais_envoye
    assert e.declare is True
    assert e.nb_envoyes == 2
    assert e.nb_changements == 0
    assert e.nb_classes_touchees == 0


def test_un_nouvel_eleve_est_un_entrant(session, annee_factory, eleve):
    from backend.services.envois import enregistrer, etat
    an = annee_factory("2026-2027")
    eleve(an.id, "61")
    enregistrer(session, systeme="sodexo", annee_id=an.id, declare=True)

    eleve(an.id, "61", nom="ARRIVE")
    e = etat(session, "sodexo", an.id)

    c = next(x for x in e.classes if x.classe == "61")
    assert c.entrants == ["Test ARRIVE"]
    assert c.sortants == []
    assert e.nb_changements == 1


def test_un_changement_de_classe_n_est_pas_une_arrivee(
    session, annee_factory, eleve
):
    """La distinction qui compte.

    Chez le destinataire, un entrant se crée et un déplacé se corrige.
    Les confondre fait un second compte à quelqu'un qui en a déjà un.
    """
    from backend.services.envois import enregistrer, etat
    from backend.models import Snapshot

    an = annee_factory("2026-2027")
    p = eleve(an.id, "61", nom="BOUGE")
    enregistrer(session, systeme="sodexo", annee_id=an.id, declare=True)

    session.add(
        Snapshot(
            personne_id=p.id, annee_scolaire_id=an.id,
            nom=p.nom, prenom=p.prenom, classe="62",
        )
    )
    session.commit()

    e = etat(session, "sodexo", an.id)
    partie = next(x for x in e.classes if x.classe == "61")
    arrivee = next(x for x in e.classes if x.classe == "62")

    assert partie.sortants == ["Test BOUGE"]
    assert arrivee.arrives_d_ailleurs == ["Test BOUGE"], "ce n'est pas un entrant"
    assert arrivee.entrants == []


def test_un_eleve_qui_disparait_est_un_sortant(session, annee_factory, eleve):
    from backend.services.envois import enregistrer, etat
    from backend.models import Snapshot

    an = annee_factory("2026-2027")
    p = eleve(an.id, "61", nom="PARTI")
    eleve(an.id, "61")
    enregistrer(session, systeme="sodexo", annee_id=an.id, declare=True)

    session.query(Snapshot).filter(Snapshot.personne_id == p.id).delete()
    session.commit()

    e = etat(session, "sodexo", an.id)
    c = next(x for x in e.classes if x.classe == "61")
    assert c.sortants == ["Test PARTI"]
    assert c.nb_actuel == 1


def test_une_classe_sans_changement_se_distingue_des_autres(
    session, annee_factory, eleve
):
    """C'est l'économie du dispositif : on ne rouvre que ce qui bouge."""
    from backend.services.envois import enregistrer, etat
    an = annee_factory("2026-2027")
    eleve(an.id, "61")
    eleve(an.id, "62")
    enregistrer(session, systeme="sodexo", annee_id=an.id, declare=True)
    eleve(an.id, "62", nom="NEUF")

    e = etat(session, "sodexo", an.id)
    calme = next(x for x in e.classes if x.classe == "61")
    agitee = next(x for x in e.classes if x.classe == "62")

    assert calme.nb_changements == 0
    assert agitee.nb_changements == 1
    assert e.nb_classes_touchees == 1


def test_chaque_systeme_a_son_propre_dernier_envoi(session, annee_factory, eleve):
    """Sodexo et CardStudio ne partent pas le même jour."""
    from backend.services.envois import dernier, enregistrer, etat
    an = annee_factory("2026-2027")
    eleve(an.id, "61")
    enregistrer(session, systeme="sodexo", annee_id=an.id, declare=True)

    assert dernier(session, "sodexo", an.id) is not None
    assert dernier(session, "cardstudio", an.id) is None
    assert etat(session, "cardstudio", an.id).jamais_envoye


def test_le_dernier_envoi_est_le_plus_recent(session, annee_factory, eleve):
    from backend.services.envois import dernier, enregistrer, etat
    an = annee_factory("2026-2027")
    eleve(an.id, "61")
    premier = enregistrer(session, systeme="sodexo", annee_id=an.id, declare=True)
    eleve(an.id, "61", nom="DEUXIEME")
    second = enregistrer(session, systeme="sodexo", annee_id=an.id, declare=True)

    assert dernier(session, "sodexo", an.id).id == second.id
    assert second.nb_lignes == 2 and premier.nb_lignes == 1
    assert etat(session, "sodexo", an.id).nb_changements == 0


def test_un_envoi_produit_garde_le_nom_du_fichier(session, annee_factory, eleve):
    """Un fichier produit se distingue d'un envoi déclaré.

    Le second vaut ce que vaut la parole de celui qui l'a déclaré, et
    l'écran doit pouvoir le dire.
    """
    from backend.services.envois import enregistrer, etat
    an = annee_factory("2026-2027")
    eleve(an.id, "61")
    enregistrer(
        session, systeme="cardstudio", annee_id=an.id,
        nom_fichier="CardStudio_36_cartes.xlsx",
    )

    e = etat(session, "cardstudio", an.id)
    assert e.declare is False
    assert e.nom_fichier == "CardStudio_36_cartes.xlsx"


def test_un_envoi_partiel_ne_retient_que_ses_lignes(session, annee_factory, eleve):
    """Un fichier de trente-six cartes n'a pas transmis mille huit cents
    élèves : ce qu'il contenait est ce qu'on lui compare."""
    from backend.services.envois import enregistrer, etat
    an = annee_factory("2026-2027")
    a = eleve(an.id, "61")
    eleve(an.id, "62")

    enregistrer(
        session, systeme="cardstudio", annee_id=an.id, lignes={a.id: "61"},
    )

    e = etat(session, "cardstudio", an.id)
    assert e.nb_envoyes == 1
    # L'autre n'a jamais eu de carte : c'est un entrant, pas un oubli.
    autre = next(x for x in e.classes if x.classe == "62")
    assert len(autre.entrants) == 1


def test_les_lignes_suivent_la_suppression_de_leur_envoi(
    session, annee_factory, eleve
):
    from backend.services.envois import enregistrer
    from backend.models import Envoi, LigneEnvoi
    an = annee_factory("2026-2027")
    eleve(an.id, "61")
    e = enregistrer(session, systeme="sodexo", annee_id=an.id, declare=True)

    session.delete(e)
    session.commit()
    assert session.query(LigneEnvoi).count() == 0
    assert session.query(Envoi).count() == 0


def test_un_envoi_ne_voit_que_son_annee(session, annee_factory, eleve):
    from backend.services.envois import dernier, enregistrer, etat
    passee = annee_factory("2025-2026")
    an = annee_factory("2026-2027")
    eleve(passee.id, "61")
    eleve(an.id, "62")

    enregistrer(session, systeme="sodexo", annee_id=an.id, declare=True)
    assert dernier(session, "sodexo", passee.id) is None
    assert [c.classe for c in etat(session, "sodexo", an.id).classes] == ["62"]
