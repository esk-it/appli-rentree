"""Rapprochement de la flotte Chromebook et des enseignants."""
from __future__ import annotations

from dataclasses import dataclass


@dataclass
class _Prof:
    nom: str
    prenom: str
    discipline: str = "Maths"
    code: str = "en_poste"


def _appareil(etiquette, serie="S1", ou="/1. Chromebooks/1. Personnel éducatif",
              recents=None, statut="ACTIVE"):
    return {
        "serie": serie, "modele": "Acer Spin 511", "ou": ou, "statut": statut,
        "etiquette": etiquette, "utilisateur_annote": "admin.chrome@lekreisker.fr",
        "emplacement": "", "derniers_utilisateurs": recents or [],
        "derniere_synchro": None,
    }


def _compte(email, nom, prenom):
    return {"email": email, "nom": nom, "prenom": prenom,
            "ou": "/5. Professeurs", "suspendu": False}


def test_letiquette_designe_le_porteur_pas_lutilisateur_annote():
    """`annotatedUser` porte partout le même compte technique : il ne dit rien."""
    from backend.services.chromebooks import analyser_flotte

    r = analyser_flotte(
        [_appareil("sandrine.jaouanet@lekreisker.fr")],
        [_Prof("JAOUANET", "Sandrine")],
        [_compte("sandrine.jaouanet@lekreisker.fr", "JAOUANET", "Sandrine")],
    )
    assert r.appareils[0].porteur == "sandrine.jaouanet@lekreisker.fr"
    assert r.profs[0].appareils[0].serie == "S1"


def test_un_partant_qui_detient_une_machine_est_a_relancer():
    from backend.services.chromebooks import analyser_flotte

    r = analyser_flotte(
        [_appareil("adele.lemordant@lekreisker.fr", serie="A1"),
         _appareil("adele.lemordant@lekreisker.fr", serie="A2")],
        [_Prof("LEMORDANT", "Adèle", "Anglais", "sortant")],
        [_compte("adele.lemordant@lekreisker.fr", "LEMORDANT", "Adèle")],
    )
    assert len(r.a_recuperer) == 1
    assert r.nb_a_recuperer == 2, "deux machines chez la même personne"


def test_un_arrivant_sans_machine_est_a_equiper():
    from backend.services.chromebooks import analyser_flotte

    r = analyser_flotte(
        [_appareil("Prof_08", serie="P8")],
        [_Prof("BILLANT", "Pierre", "Maths", "arrivant")],
        [_compte("pierre.billant@lekreisker.fr", "BILLANT", "Pierre")],
    )
    assert [p.nom for p in r.a_attribuer] == ["BILLANT"]
    assert [a.etiquette for a in r.disponibles] == ["Prof_08"]


def test_un_arrivant_deja_equipe_nest_pas_signale():
    from backend.services.chromebooks import analyser_flotte

    r = analyser_flotte(
        [_appareil("pierre.billant@lekreisker.fr")],
        [_Prof("BILLANT", "Pierre", "Maths", "arrivant")],
        [_compte("pierre.billant@lekreisker.fr", "BILLANT", "Pierre")],
    )
    assert r.a_attribuer == []


def test_le_parc_de_pret_se_reconnait_a_son_etiquette():
    from backend.services.chromebooks import analyser_flotte

    r = analyser_flotte(
        [_appareil("Prof_08", serie="A"), _appareil("Stagiaire 9", serie="B"),
         _appareil("Maintenance 2", serie="C"), _appareil("VS Ste Ursule", serie="D"),
         _appareil("K-B5-13-08", serie="E", ou="/1. Chromebooks/2. Elèves")],
        [], [],
    )
    assert sorted(a.serie for a in r.disponibles) == ["A", "B", "C", "D"], (
        "le code d'emplacement d'un appareil élève n'est pas un rôle"
    )


def test_une_machine_au_nom_dun_compte_disparu_est_libre():
    from backend.services.chromebooks import analyser_flotte

    r = analyser_flotte(
        [_appareil("parti.depuis.longtemps@lekreisker.fr", serie="X")],
        [], [_compte("quelquun.dautre@lekreisker.fr", "AUTRE", "Quelqu'un")],
    )
    assert [a.serie for a in r.orphelins] == ["X"]
    assert [a.serie for a in r.disponibles] == ["X"]


def test_une_machine_desactivee_nest_pas_proposee():
    from backend.services.chromebooks import analyser_flotte

    r = analyser_flotte(
        [_appareil("Prof_08", serie="HS", statut="DEPROVISIONED")], [], [],
    )
    assert r.disponibles == []


def test_letiquette_dementie_par_les_connexions_est_montree_pas_tranchee():
    """Deux machines échangées se voient exactement là.

    Le cas réel : Julien détient la machine étiquetée Samuel, et
    réciproquement. Corriger d'office reviendrait à décider lequel des deux
    a raison.
    """
    from backend.services.chromebooks import analyser_flotte

    r = analyser_flotte(
        [
            _appareil("julien.martial@lekreisker.fr", serie="J",
                      recents=["samuel.ouchia-lebars@lekreisker.fr"]),
            _appareil("samuel.ouchia-lebars@lekreisker.fr", serie="S",
                      recents=["julien.martial@lekreisker.fr"]),
        ],
        [], [],
    )
    assert len(r.discordances) == 2
    assert {d.appareil.serie for d in r.discordances} == {"J", "S"}
    assert any("démentent" in a for a in r.avertissements)


def test_une_machine_jamais_utilisee_nest_pas_une_discordance():
    """Sans connexion enregistrée, il n'y a rien à contredire."""
    from backend.services.chromebooks import analyser_flotte

    r = analyser_flotte(
        [_appareil("neuve@lekreisker.fr", recents=[])], [], [],
    )
    assert r.discordances == []


def test_un_homonyme_ne_donne_lieu_a_aucun_rattachement():
    """Deux comptes pour un même nom : choisir serait arbitraire."""
    from backend.services.chromebooks import analyser_flotte

    r = analyser_flotte(
        [_appareil("marie.martin@lekreisker.fr")],
        [_Prof("MARTIN", "Marie")],
        [_compte("marie.martin@lekreisker.fr", "MARTIN", "Marie"),
         _compte("marie.martin2@lekreisker.fr", "MARTIN", "Marie")],
    )
    assert r.profs[0].email is None
    assert r.profs[0].appareils == []
    assert any("pas de compte Google retrouvé" in a for a in r.avertissements)


def test_le_rapprochement_ignore_accents_et_casse():
    from backend.services.chromebooks import analyser_flotte

    r = analyser_flotte(
        [_appareil("helene.maurice@lekreisker.fr")],
        [_Prof("MAURICE", "Hélène", "Lettres", "sortant")],
        [_compte("helene.maurice@lekreisker.fr", "Maurice", "Helene")],
    )
    assert len(r.a_recuperer) == 1
