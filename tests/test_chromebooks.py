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


def test_une_machine_notee_rendue_quitte_les_reclamations():
    """Sans mémoire, la liste resterait identique du premier au dernier jour."""
    from backend.services.chromebooks import analyser_flotte

    appareils = [_appareil("adele.lemordant@lekreisker.fr", serie="A1")]
    profs = [_Prof("LEMORDANT", "Adèle", "Anglais", "sortant")]
    comptes = [_compte("adele.lemordant@lekreisker.fr", "LEMORDANT", "Adèle")]

    avant = analyser_flotte(appareils, profs, comptes)
    assert avant.nb_a_recuperer == 1

    apres = analyser_flotte(
        appareils, profs, comptes,
        suivi={"A1": {"recupere_le": "2026-09-02", "attribue_a": None}},
    )
    assert apres.nb_a_recuperer == 0
    assert [a.serie for a in apres.recuperees] == ["A1"]
    assert [a.serie for a in apres.disponibles] == ["A1"], "rendue donc réattribuable"


def test_une_machine_confiee_equipe_son_nouveau_porteur():
    """Le geste physique précède la console de plusieurs jours."""
    from backend.services.chromebooks import analyser_flotte

    r = analyser_flotte(
        [_appareil("Prof_08", serie="P8")],
        [_Prof("BILLANT", "Pierre", "Maths", "arrivant")],
        [_compte("pierre.billant@lekreisker.fr", "BILLANT", "Pierre")],
        suivi={"P8": {"recupere_le": None,
                      "attribue_a": "pierre.billant@lekreisker.fr"}},
    )
    assert r.a_attribuer == [], "il a sa machine, même si l'étiquette l'ignore"
    assert r.profs[0].attribue == "P8"
    assert [a.serie for a in r.etiquettes_a_mettre_a_jour] == ["P8"]
    assert any("étiquette Google ait suivi" in a for a in r.avertissements)
    assert r.disponibles == [], "une machine confiée n'est plus libre"


def test_une_etiquette_deja_a_jour_ne_rappelle_rien():
    from backend.services.chromebooks import analyser_flotte

    r = analyser_flotte(
        [_appareil("pierre.billant@lekreisker.fr", serie="P8")],
        [_Prof("BILLANT", "Pierre", "Maths", "arrivant")],
        [_compte("pierre.billant@lekreisker.fr", "BILLANT", "Pierre")],
        suivi={"P8": {"recupere_le": None,
                      "attribue_a": "pierre.billant@lekreisker.fr"}},
    )
    assert r.etiquettes_a_mettre_a_jour == []


def test_un_remplacant_a_besoin_dune_machine_comme_un_arrivant():
    """Les lignes à deux noms sont des remplacements : ils enseignent aussi."""
    from backend.services.chromebooks import analyser_flotte

    r = analyser_flotte(
        [_appareil("Prof_08", serie="P8")],
        [_Prof("CLOITRE / FUMAT", "Morgane / Linda", "Breton", "remplace")],
        [],
    )
    assert [p.nom for p in r.a_attribuer] == ["CLOITRE / FUMAT"]
    assert [a.etiquette for a in r.disponibles] == ["Prof_08"]


def test_les_enseignants_sans_compte_sont_listes_pas_seulement_comptes():
    """Savoir combien ne dit pas si c'est normal — il faut voir qui."""
    from backend.services.chromebooks import analyser_flotte

    r = analyser_flotte(
        [],
        [_Prof("COSSE", "Clara", "NSI", "arrivant"),
         _Prof("MORIO", "Erwann", "Lettres", "en_poste")],
        [],
    )
    assert {p.nom for p in r.sans_compte} == {"COSSE", "MORIO"}
    assert {p.code for p in r.sans_compte} == {"arrivant", "en_poste"}
    assert any("Sans compte" in a for a in r.avertissements)


def test_une_machine_confiee_nest_plus_une_discordance():
    """L'étiquette périmée est un rappel, pas une contradiction à trancher."""
    from backend.services.chromebooks import analyser_flotte

    r = analyser_flotte(
        [_appareil("ancien@lekreisker.fr", serie="A",
                   recents=["quelquun.dautre@lekreisker.fr"])],
        [], [],
        suivi={"A": {"recupere_le": None, "attribue_a": "nouveau@lekreisker.fr"}},
    )
    assert r.discordances == []


def _avec_synchro(etiquette, serie, iso, recents=None):
    a = _appareil(etiquette, serie=serie, recents=recents)
    a["derniere_synchro"] = iso
    return a


def test_une_etiquette_survit_a_la_machine_quelle_decrit():
    """Trois machines au nom d'une enseignante, une seule vivante.

    Les deux autres sont des étiquettes que personne n'a corrigées en les
    rangeant. Les compter comme un dû envoie réclamer un objet que la
    personne n'a pas.
    """
    from backend.services.chromebooks import analyser_flotte

    r = analyser_flotte(
        [_avec_synchro("helene.maurice@lekreisker.fr", "VIVE", "2026-07-05T10:00:00.000Z"),
         _avec_synchro("helene.maurice@lekreisker.fr", "DORT1", "2025-04-03T10:00:00.000Z"),
         _avec_synchro("helene.maurice@lekreisker.fr", "DORT2", "2024-12-26T10:00:00.000Z")],
        [_Prof("MAURICE", "Hélène", "Lettres", "sortant")],
        [_compte("helene.maurice@lekreisker.fr", "MAURICE", "Hélène")],
    )
    assert {a.serie for a in r.dormantes} == {"DORT1", "DORT2"}
    assert any("plus d'un an" in x for x in r.avertissements)
    assert r.nb_a_recuperer == 3, "elles restent listées, mais signalées"


def test_une_machine_jamais_synchronisee_dort():
    from backend.services.chromebooks import analyser_flotte

    r = analyser_flotte([_appareil("x@lekreisker.fr", serie="N")], [], [])
    assert r.appareils[0].dort is True


def test_on_retrouve_une_machine_par_son_numero():
    """Le geste part de l'objet : on lit le numéro inscrit dessous."""
    from backend.services.chromebooks import analyser_flotte, chercher_appareil

    r = analyser_flotte(
        [_appareil("helene.maurice@lekreisker.fr", serie="NXHPXEF0020394916B7611"),
         _appareil("Prof_08", serie="AUTRE")],
        [], [],
    )
    assert [a.serie for a in chercher_appareil(r, "916B76")] == ["NXHPXEF0020394916B7611"]
    assert [a.serie for a in chercher_appareil(r, "prof_08")] == ["AUTRE"]


def test_on_retrouve_une_machine_par_qui_sen_sert_vraiment():
    """L'étiquette peut désigner quelqu'un d'autre : c'est le cas utile."""
    from backend.services.chromebooks import analyser_flotte, chercher_appareil

    r = analyser_flotte(
        [_appareil("ancienne.etiquette@lekreisker.fr", serie="X",
                   recents=["gaelle.bauduin@lekreisker.fr"])],
        [], [],
    )
    assert [a.serie for a in chercher_appareil(r, "bauduin")] == ["X"]


def test_une_requete_trop_courte_ne_ratisse_pas_tout():
    from backend.services.chromebooks import analyser_flotte, chercher_appareil

    r = analyser_flotte([_appareil("x@lekreisker.fr", serie="ABC")], [], [])
    assert chercher_appareil(r, "AB") == []
    assert len(chercher_appareil(r, "ABC")) == 1


def test_le_plus_recemment_vu_vient_en_premier():
    """C'est celui qu'on a le plus de chances d'avoir entre les mains."""
    from backend.services.chromebooks import analyser_flotte, chercher_appareil

    r = analyser_flotte(
        [_avec_synchro("helene.maurice@lekreisker.fr", "VIEUX", "2024-12-26T10:00:00.000Z"),
         _avec_synchro("helene.maurice@lekreisker.fr", "RECENT", "2026-07-05T10:00:00.000Z")],
        [], [],
    )
    assert [a.serie for a in chercher_appareil(r, "maurice")] == ["RECENT", "VIEUX"]


def test_celui_qui_a_rendu_en_juin_et_qui_revient_est_a_reequiper():
    """Ni arrivant ni partant : rien ne le signalait, et il n'a plus rien.

    Le cas réel : un enseignant qui ignore s'il sera reconduit rend sa
    machine avant l'été, puis revient en septembre.
    """
    from backend.services.chromebooks import analyser_flotte

    r = analyser_flotte(
        [_appareil("nicole.lanconneur@lekreisker.fr", serie="R1")],
        [_Prof("LANCONNEUR", "Nicole", "Anglais", "en_poste")],
        [_compte("nicole.lanconneur@lekreisker.fr", "LANCONNEUR", "Nicole")],
        suivi={"R1": {"recupere_le": "2026-06-30", "attribue_a": None,
                      "recupere_de": "nicole.lanconneur@lekreisker.fr"}},
    )
    assert [p.nom for p in r.a_attribuer] == ["LANCONNEUR"]
    assert r.a_attribuer[0].raison == "revenu"
    assert any("revenus" in a for a in r.avertissements)


def test_un_titulaire_qui_na_jamais_eu_de_machine_nen_attend_pas():
    """Les signaler tous noierait les cas qui comptent."""
    from backend.services.chromebooks import analyser_flotte

    r = analyser_flotte(
        [],
        [_Prof("SANSMACHINE", "Paul", "Maths", "en_poste")],
        [_compte("paul.sansmachine@lekreisker.fr", "SANSMACHINE", "Paul")],
    )
    assert r.a_attribuer == []
    assert len(r.profs) == 1, "il reste au tableau, simplement sans alerte"


def test_les_raisons_dattendre_une_machine_sont_distinguees():
    from backend.services.chromebooks import analyser_flotte

    r = analyser_flotte(
        [_appareil("revenu@lekreisker.fr", serie="R")],
        [_Prof("NOUVEAU", "Alice", "SVT", "arrivant"),
         _Prof("REMPLACE / X", "Bob / Y", "Breton", "remplace"),
         _Prof("REVENU", "Carla", "Anglais", "en_poste")],
        [_compte("alice.nouveau@lekreisker.fr", "NOUVEAU", "Alice"),
         _compte("revenu@lekreisker.fr", "REVENU", "Carla")],
        suivi={"R": {"recupere_le": "2026-06-30", "attribue_a": None,
                     "recupere_de": "revenu@lekreisker.fr"}},
    )
    raisons = {p.nom: p.raison for p in r.a_attribuer}
    assert raisons == {
        "NOUVEAU": "arrivant",
        "REMPLACE / X": "remplace",
        "REVENU": "revenu",
    }


def test_un_revenu_deja_reequipe_disparait_de_la_liste():
    from backend.services.chromebooks import analyser_flotte

    r = analyser_flotte(
        [_appareil("nicole.lanconneur@lekreisker.fr", serie="R1"),
         _appareil("Prof_08", serie="P8")],
        [_Prof("LANCONNEUR", "Nicole", "Anglais", "en_poste")],
        [_compte("nicole.lanconneur@lekreisker.fr", "LANCONNEUR", "Nicole")],
        suivi={
            "R1": {"recupere_le": "2026-06-30", "attribue_a": None,
                   "recupere_de": "nicole.lanconneur@lekreisker.fr"},
            "P8": {"recupere_le": None,
                   "attribue_a": "nicole.lanconneur@lekreisker.fr"},
        },
    )
    assert r.a_attribuer == []


def test_chaque_appareil_sait_ce_quon_attend_de_lui():
    """La vue du parc colore l'action attendue, pas la santé technique."""
    from backend.services.chromebooks import analyser_flotte

    r = analyser_flotte(
        [_appareil("adele.lemordant@lekreisker.fr", serie="ATTENDU"),
         _appareil("Prof_08", serie="LIBRE"),
         _appareil("qui.reste@lekreisker.fr", serie="TRANQUILLE")],
        [_Prof("LEMORDANT", "Adèle", "Anglais", "sortant"),
         _Prof("RESTE", "Qui", "Maths", "en_poste")],
        [_compte("adele.lemordant@lekreisker.fr", "LEMORDANT", "Adèle"),
         _compte("qui.reste@lekreisker.fr", "RESTE", "Qui")],
    )
    par_serie = {a.serie: a for a in r.appareils}

    assert par_serie["ATTENDU"].a_recuperer is True
    assert par_serie["LIBRE"].libre is True
    assert par_serie["TRANQUILLE"].a_recuperer is False
    assert par_serie["TRANQUILLE"].libre is False, "rien à signaler"


def test_la_synthese_du_parc_compte_ce_qui_est_la():
    """Cinq cents appareils vus seulement à travers quatre listes d'actions
    restent invisibles le reste de l'année."""
    from backend.services.chromebooks import analyser_flotte

    r = analyser_flotte(
        [_avec_synchro("a@x.fr", "A", "2026-08-01T10:00:00.000Z"),
         _avec_synchro("b@x.fr", "B", "2024-01-01T10:00:00.000Z"),
         _appareil("c@x.fr", serie="C", statut="DEPROVISIONED")],
        [], [],
    )
    p = r.parc

    assert p.total == 3
    assert p.actifs == 2
    assert p.desactives == 1
    assert p.dormants == 1, "B n'a pas synchronisé depuis plus d'un an"
    assert p.par_modele[0] == ("Acer Spin 511", 3)
    assert dict(p.par_ou)["/1. Chromebooks/1. Personnel éducatif"] == 3


def test_le_journal_raconte_le_trajet_dune_machine():
    """Une machine confiée quitte les listes d'actions — et le champ de vision.

    Le cas vécu : la machine de Maryvonne L'HER confiée à Pierre BILLANT.
    Trois semaines plus tard, c'est la seule question qu'on se pose.
    """
    from backend.services.chromebooks import analyser_flotte

    r = analyser_flotte(
        [_appareil("maryvonne.lher@lekreisker.fr", serie="M1")],
        [],
        [_compte("maryvonne.lher@lekreisker.fr", "L'HER", "Maryvonne"),
         _compte("pierre.billant@lekreisker.fr", "BILLANT", "Pierre")],
        suivi={"M1": {"recupere_le": "2026-08-21",
                      "recupere_de": "maryvonne.lher@lekreisker.fr",
                      "attribue_a": "pierre.billant@lekreisker.fr",
                      "attribue_le": "2026-08-24"}},
    )

    assert len(r.historique) == 1
    m = r.historique[0]
    assert m.rendu_par_nom == "Maryvonne L'HER"
    assert m.confie_a_nom == "Pierre BILLANT"
    assert m.rendu_le == "2026-08-21"
    assert m.confie_le == "2026-08-24"


def test_le_journal_va_du_plus_recent_au_plus_ancien():
    from backend.services.chromebooks import analyser_flotte

    r = analyser_flotte(
        [_appareil("a@x.fr", serie="VIEUX"), _appareil("b@x.fr", serie="RECENT")],
        [], [],
        suivi={
            "VIEUX": {"recupere_le": "2026-08-01", "recupere_de": "a@x.fr",
                      "attribue_a": None, "attribue_le": None},
            "RECENT": {"recupere_le": "2026-08-24", "recupere_de": "b@x.fr",
                       "attribue_a": None, "attribue_le": None},
        },
    )
    assert [m.serie for m in r.historique] == ["RECENT", "VIEUX"]


def test_une_machine_sans_geste_note_nentre_pas_au_journal():
    """Le journal raconte ce qu'on a fait, pas ce que Google contient."""
    from backend.services.chromebooks import analyser_flotte

    r = analyser_flotte([_appareil("a@x.fr", serie="A")], [], [])
    assert r.historique == []


def test_une_adresse_inconnue_reste_lisible_au_journal():
    """Sans compte correspondant, l'adresse tient lieu de nom."""
    from backend.services.chromebooks import analyser_flotte

    r = analyser_flotte(
        [_appareil("x@x.fr", serie="A")], [], [],
        suivi={"A": {"recupere_le": "2026-08-24", "recupere_de": "parti@x.fr",
                     "attribue_a": None, "attribue_le": None}},
    )
    assert r.historique[0].rendu_par == "parti@x.fr"
    assert r.historique[0].rendu_par_nom is None


def test_une_machine_desactivee_dit_pourquoi_elle_nest_pas_reattribuable():
    """Le cas vécu : rendue, mais elle n'apparaissait nulle part ensuite.

    Google désactive un appareil retiré du parc et son étiquette lui
    survit. Ne rien dire laisse chercher pourquoi il a disparu.
    """
    from backend.services.chromebooks import analyser_flotte

    r = analyser_flotte(
        [_appareil("yanna.lachoua-martial@lekreisker.fr", serie="MORTE",
                   statut="DEPROVISIONED")],
        [], [],
        suivi={"MORTE": {"recupere_le": "2026-08-24",
                         "recupere_de": "yanna.lachoua-martial@lekreisker.fr",
                         "attribue_a": None, "attribue_le": None}},
    )
    machine = r.appareils[0]

    assert machine.libre is False
    assert "désactivée" in machine.motif_indisponible
    assert r.historique[0].motif_indisponible == machine.motif_indisponible


def test_une_machine_hors_du_parc_du_personnel_le_dit_aussi():
    from backend.services.chromebooks import analyser_flotte

    r = analyser_flotte(
        [_appareil("K-B5-13-08", serie="ELEVE", ou="/1. Chromebooks/2. Elèves")],
        [], [],
    )
    assert "hors du parc du personnel" in r.appareils[0].motif_indisponible


def test_une_machine_disponible_na_pas_de_motif():
    from backend.services.chromebooks import analyser_flotte

    r = analyser_flotte([_appareil("Prof_08", serie="LIBRE")], [], [])
    assert r.appareils[0].libre is True
    assert r.appareils[0].motif_indisponible is None


def test_la_note_suit_la_machine_jusquau_journal():
    """Le programme ne peut pas déduire ce qu'on décide : il offre de l'écrire."""
    from backend.services.chromebooks import analyser_flotte

    r = analyser_flotte(
        [_appareil("x@x.fr", serie="A", statut="DEPROVISIONED")], [], [],
        suivi={"A": {"recupere_le": "2026-08-24", "recupere_de": "x@x.fr",
                     "attribue_a": None, "attribue_le": None,
                     "note": "Rendue au fournisseur, hors garantie"}},
    )
    assert r.appareils[0].note == "Rendue au fournisseur, hors garantie"
    assert r.historique[0].note == "Rendue au fournisseur, hors garantie"


def test_une_machine_dit_ce_que_chaque_source_pense_delle():
    """Trois noms pour une machine : autocollant, étiquette, connexions.

    Le cas réel : étiquette julien.martial, connexions
    samuel.ouchia-lebars. Aucun des deux n'est faux — ils datent
    d'époques différentes, et c'est cela qu'il faut montrer.
    """
    from backend.services.chromebooks import analyser_flotte

    r = analyser_flotte(
        [_appareil("julien.martial@lekreisker.fr", serie="ECHANGEE",
                   recents=["samuel.ouchia-lebars@lekreisker.fr"])],
        [_Prof("MARTIAL", "Julien", "Maths", "en_poste")],
        [_compte("julien.martial@lekreisker.fr", "MARTIAL", "Julien")],
    )
    a = r.appareils[0]

    assert a.porteur == "julien.martial@lekreisker.fr"
    assert a.derniers_utilisateurs == ["samuel.ouchia-lebars@lekreisker.fr"]
    assert a.porteur_en_poste is True
    assert a.porteur_code == "en_poste"


def test_une_etiquette_portee_par_plusieurs_machines_est_comptee():
    """Trois machines pour une même enseignante : des étiquettes jamais
    corrigées, et le nombre le dit avant qu'on aille les chercher."""
    from backend.services.chromebooks import analyser_flotte

    r = analyser_flotte(
        [_appareil("helene.maurice@lekreisker.fr", serie="A"),
         _appareil("helene.maurice@lekreisker.fr", serie="B"),
         _appareil("helene.maurice@lekreisker.fr", serie="C"),
         _appareil("seule@lekreisker.fr", serie="D")],
        [], [],
    )
    par_serie = {a.serie: a for a in r.appareils}

    assert par_serie["A"].homonymes_etiquette == 2
    assert par_serie["D"].homonymes_etiquette == 0


def test_le_porteur_sortant_est_signale_comme_tel():
    from backend.services.chromebooks import analyser_flotte

    r = analyser_flotte(
        [_appareil("adele.lemordant@lekreisker.fr", serie="A")],
        [_Prof("LEMORDANT", "Adèle", "Anglais", "sortant")],
        [_compte("adele.lemordant@lekreisker.fr", "LEMORDANT", "Adèle")],
    )
    assert r.appareils[0].porteur_en_poste is False
    assert r.appareils[0].porteur_code == "sortant"


def test_une_etiquette_qui_ne_designe_personne_ne_conclut_rien():
    """Un code d'emplacement n'est pas une adresse : rien à en déduire."""
    from backend.services.chromebooks import analyser_flotte

    r = analyser_flotte(
        [_appareil("K-B5-13-08", serie="A", ou="/1. Chromebooks/2. Elèves")],
        [], [],
    )
    assert r.appareils[0].porteur is None
    assert r.appareils[0].porteur_en_poste is None
    assert r.appareils[0].homonymes_etiquette == 0


def test_une_absence_explique_quun_autre_se_serve_de_la_machine():
    """Le cas réel : Julien en congé formation, Samuel sur sa machine.

    Les trois faits étaient affichés ; c'est leur rapprochement qui dit la
    chose, et c'est ce rapprochement qu'on ne devrait pas avoir à faire.
    """
    from backend.services.chromebooks import analyser_flotte

    r = analyser_flotte(
        [_appareil("julien.martial@lekreisker.fr", serie="A",
                   recents=["samuel.ouchia-lebars@lekreisker.fr"])],
        [_Prof("MARTIAL", "Julien", "Maths", "formation")],
        [_compte("julien.martial@lekreisker.fr", "MARTIAL", "Julien")],
    )
    lecture = " ".join(r.appareils[0].lecture)

    assert "congé formation" in lecture
    assert "samuel.ouchia-lebars@lekreisker.fr" in lecture
    assert "Rien d'anormal" in lecture


def test_un_partant_qui_sen_sert_encore_est_annonce_comme_tel():
    from backend.services.chromebooks import analyser_flotte

    from datetime import datetime, timedelta

    hier = (datetime.utcnow() - timedelta(days=1)).isoformat() + "Z"
    r = analyser_flotte(
        [_avec_synchro("adele.lemordant@lekreisker.fr", "A", hier,
                       recents=["adele.lemordant@lekreisker.fr"])],
        [_Prof("LEMORDANT", "Adèle", "Anglais", "sortant")],
        [_compte("adele.lemordant@lekreisker.fr", "LEMORDANT", "Adèle")],
    )
    assert "quitte l'établissement" in " ".join(r.appareils[0].lecture)


def test_une_etiquette_contredite_sans_raison_reste_une_supposition():
    """Un changement de mains ne laisse pas de trace : on ne l'affirme pas."""
    from backend.services.chromebooks import analyser_flotte

    r = analyser_flotte(
        [_appareil("ancien@lekreisker.fr", serie="A",
                   recents=["nouveau@lekreisker.fr"])],
        [], [],
    )
    lecture = " ".join(r.appareils[0].lecture)
    assert "sans doute" in lecture
    assert "réétiquetée" in lecture


def test_une_machine_desactivee_le_dit_avant_tout_le_reste():
    from backend.services.chromebooks import analyser_flotte

    r = analyser_flotte(
        [_appareil("yanna@lekreisker.fr", serie="A", statut="DEPROVISIONED")],
        [], [],
    )
    lecture = r.appareils[0].lecture
    assert "désactivé" in lecture[0]
    assert any("étiquette" in p for p in lecture)


def test_plusieurs_machines_au_meme_nom_dont_une_qui_dort():
    from backend.services.chromebooks import analyser_flotte

    r = analyser_flotte(
        [_avec_synchro("helene.maurice@lekreisker.fr", "VIVE", "2026-07-05T10:00:00.000Z"),
         _avec_synchro("helene.maurice@lekreisker.fr", "DORT", "2024-12-26T10:00:00.000Z")],
        [], [],
    )
    par_serie = {a.serie: a for a in r.appareils}
    assert "2 machines portent cette étiquette" in " ".join(par_serie["DORT"].lecture)
    assert not any("machines portent" in p for p in par_serie["VIVE"].lecture)


def test_reprise_alors_que_la_personne_est_toujours_la():
    from backend.services.chromebooks import analyser_flotte

    r = analyser_flotte(
        [_appareil("nicole.lanconneur@lekreisker.fr", serie="A")],
        [_Prof("LANCONNEUR", "Nicole", "Anglais", "en_poste")],
        [_compte("nicole.lanconneur@lekreisker.fr", "LANCONNEUR", "Nicole")],
        suivi={"A": {"recupere_le": "2026-08-24", "attribue_a": None,
                     "recupere_de": "nicole.lanconneur@lekreisker.fr"}},
    )
    assert "toujours au tableau" in " ".join(r.appareils[0].lecture)


def test_une_machine_endormie_ne_pretend_pas_servir_encore():
    """La liste des derniers utilisateurs est un historique, pas un présent.

    Sur une machine sans synchronisation depuis deux ans, « s'en servait
    encore récemment » est faux — et contredirait la phrase sur son sommeil.
    """
    from datetime import datetime, timedelta

    from backend.services.chromebooks import analyser_flotte

    hier = (datetime.utcnow() - timedelta(days=1)).isoformat() + "Z"
    r = analyser_flotte(
        [_avec_synchro("helene.maurice@lekreisker.fr", "DORT",
                       "2024-12-26T10:00:00.000Z",
                       recents=["helene.maurice@lekreisker.fr"]),
         _avec_synchro("helene.maurice@lekreisker.fr", "VIVE", hier,
                       recents=["helene.maurice@lekreisker.fr"])],
        [_Prof("MAURICE", "Hélène", "Lettres", "sortant")],
        [_compte("helene.maurice@lekreisker.fr", "MAURICE", "Hélène")],
    )
    par_serie = {a.serie: " ".join(a.lecture) for a in r.appareils}

    assert "réclamer" not in par_serie["DORT"], "elle dort : on ne peut pas l'affirmer"
    assert "ne donne plus signe de vie" in par_serie["DORT"]
    assert "réclamer" in par_serie["VIVE"], "celle-ci, si"


def test_le_compte_explique_ce_que_le_tableau_ignore():
    """Le cas réel : une AESH, absente du tableau des enseignants.

    Regarder le seul tableau des profs, c'était regarder par la mauvaise
    fenêtre : le compte Google existe pour tout le monde, et l'unité où il
    est rangé dit à quel titre la personne est là.
    """
    from backend.services.chromebooks import analyser_flotte

    r = analyser_flotte(
        [_appareil("marine.le-jeune@lekreisker.fr", serie="A",
                   recents=["marine.le-jeune@lekreisker.fr"])],
        [],
        [{"email": "marine.le-jeune@lekreisker.fr", "nom": "LE JEUNE",
          "prenom": "Marine", "ou": "/6. Personnel/AESH", "suspendu": False,
          "derniere_connexion": "2026-06-18T08:00:00.000Z"}],
    )
    a = r.appareils[0]
    lecture = " ".join(a.lecture)

    assert a.porteur_ou == "/6. Personnel/AESH"
    assert a.porteur_suspendu is False
    assert "ne figure pas au tableau des enseignants" in lecture
    assert "/6. Personnel/AESH" in lecture
    assert "2026-06-18" in lecture


def test_un_compte_disparu_libere_la_machine():
    """L'autre cas réel : la personne n'a plus de compte du tout."""
    from backend.services.chromebooks import analyser_flotte

    r = analyser_flotte(
        [_appareil("gaelle.bauduin@lekreisker.fr", serie="A",
                   recents=["johan.lemer@lekreisker.fr"])],
        [], [_compte("johan.lemer@lekreisker.fr", "LEMER", "Johan")],
    )
    a = r.appareils[0]

    assert a.porteur_compte_existe is False
    assert "n'existe plus dans Google" in " ".join(a.lecture)
    assert "peut être réattribuée" in " ".join(a.lecture)


def test_un_compte_suspendu_explique_le_retour():
    from backend.services.chromebooks import analyser_flotte

    r = analyser_flotte(
        [_appareil("parti@lekreisker.fr", serie="A")],
        [],
        [{"email": "parti@lekreisker.fr", "nom": "PARTI", "prenom": "Jean",
          "ou": "/5. Professeurs", "suspendu": True}],
    )
    assert "suspendu" in " ".join(r.appareils[0].lecture)


def test_un_compte_deja_range_en_sortie_le_dit():
    from backend.services.chromebooks import analyser_flotte

    r = analyser_flotte(
        [_appareil("ancien@lekreisker.fr", serie="A")],
        [],
        [{"email": "ancien@lekreisker.fr", "nom": "ANCIEN", "prenom": "Paul",
          "ou": "/7. Sortis/Profs sortis", "suspendu": False}],
    )
    assert "déjà traitée comme sortie" in " ".join(r.appareils[0].lecture)


def test_un_enseignant_connu_du_tableau_ne_declenche_pas_la_regle_du_compte():
    """La règle ne comble qu'un silence : elle ne double pas ce qu'on sait."""
    from backend.services.chromebooks import analyser_flotte

    r = analyser_flotte(
        [_appareil("connu@lekreisker.fr", serie="A")],
        [_Prof("CONNU", "Paul", "Maths", "en_poste")],
        [{"email": "connu@lekreisker.fr", "nom": "CONNU", "prenom": "Paul",
          "ou": "/5. Professeurs", "suspendu": False}],
    )
    assert not any("ne figure pas au tableau" in p for p in r.appareils[0].lecture)


def _compte_ou(email, nom, prenom, ou="/5. Professeurs", suspendu=False, vu=None):
    return {"email": email, "nom": nom, "prenom": prenom, "ou": ou,
            "suspendu": suspendu, "derniere_connexion": vu}


def test_un_retour_que_rien_nexplique_est_nomme_comme_tel():
    """Le cas réel : Nicole LANCONNEUR, en poste, compte actif, une machine.

    Tous les signaux contredisent un retour. Une phrase prudente
    n'aiderait personne ; nommer l'absence d'explication, si.
    """
    from backend.services.chromebooks import analyser_flotte

    r = analyser_flotte(
        [_avec_synchro("nicole.lanconneur@lekreisker.fr", "A",
                       "2026-07-03T10:00:00.000Z")],
        [_Prof("LANCONNEUR", "Nicole", "Histoire-Géographie", "en_poste")],
        [_compte_ou("nicole.lanconneur@lekreisker.fr", "LANCONNEUR", "Nicole",
                    vu="2026-08-18T09:00:00.000Z")],
        suivi={"A": {"recupere_le": "2026-08-24",
                     "recupere_de": "nicole.lanconneur@lekreisker.fr",
                     "attribue_a": None, "attribue_le": None}},
    )
    lecture = " ".join(r.appareils[0].lecture)

    assert "Rien n'explique ce retour" in lecture
    assert "2026-08-18" in lecture, "la dernière connexion étaye le constat"
    assert "2026-07-03" in lecture, "et la dernière utilisation de la machine"
    assert "Demande-lui" in lecture


def test_un_porteur_qui_en_a_une_autre_change_la_conclusion():
    """Deux machines, dont celle qu'on rend : c'est un ancien appareil."""
    from backend.services.chromebooks import analyser_flotte

    r = analyser_flotte(
        [_avec_synchro("nicole.lanconneur@lekreisker.fr", "ANCIENNE",
                       "2026-07-03T10:00:00.000Z"),
         _avec_synchro("nicole.lanconneur@lekreisker.fr", "COURANTE",
                       "2026-08-20T10:00:00.000Z")],
        [_Prof("LANCONNEUR", "Nicole", "Histoire-Géographie", "en_poste")],
        [_compte_ou("nicole.lanconneur@lekreisker.fr", "LANCONNEUR", "Nicole")],
        suivi={"ANCIENNE": {"recupere_le": "2026-08-24",
                            "recupere_de": "nicole.lanconneur@lekreisker.fr",
                            "attribue_a": None, "attribue_le": None}},
    )
    ancienne = next(a for a in r.appareils if a.serie == "ANCIENNE")

    assert ancienne.autres_machines_actives == 1
    lecture = " ".join(ancienne.lecture)
    assert "ancien appareil" in lecture
    assert "ne manque donc à personne" in lecture
    assert "Rien n'explique" not in lecture


def test_une_machine_endormie_reprise_a_quelquun_de_present():
    from backend.services.chromebooks import analyser_flotte

    r = analyser_flotte(
        [_avec_synchro("x@lekreisker.fr", "A", "2023-01-01T10:00:00.000Z")],
        [_Prof("X", "Paul", "Maths", "en_poste")],
        [_compte_ou("x@lekreisker.fr", "X", "Paul")],
        suivi={"A": {"recupere_le": "2026-08-24", "recupere_de": "x@lekreisker.fr",
                     "attribue_a": None, "attribue_le": None}},
    )
    lecture = " ".join(r.appareils[0].lecture)
    assert "ne donne plus signe de vie" in lecture
    assert "Rien n'explique" not in lecture
