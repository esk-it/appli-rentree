"""Renvoyer à Charlemagne les adresses qu'il ne connaît pas.

Charlemagne est la source pour l'état civil et la classe ; il ne l'est pas
pour l'adresse, qui se crée ici après son export. Sa colonne reste donc
vide pour toute la promotion entrante — 369 élèves à la rentrée 2026.

Le risque, en la remplissant, est de pousser une **hypothèse** : sur ces
369, 361 adresses venaient d'un calcul `prenom.nom@domaine` et non d'une
lecture de Google. Chaque proposition est donc confrontée à l'annuaire.
"""
from __future__ import annotations

import csv
import io

import pytest

ENTETE = "Num Badge;Nom;Prénom;Code classe;Email"


def _fichier(*lignes, entete=ENTETE):
    return (b"\xef\xbb\xbf"
            + ("\r\n".join([entete, *lignes]) + "\r\n").encode("utf-8"))


def _ligne(badge, nom, prenom, classe, email=""):
    return ";".join([str(badge), nom, prenom, classe, email])


def _compte(email, *alias):
    return {"email": email, "alias": list(alias), "nom": "X", "prenom": "Y",
            "ou": "/NDK", "suspendu": False, "id_externe": None}


@pytest.fixture()
def ndk(session, site_factory):
    return site_factory("NDK")


@pytest.fixture()
def eleve(session, ndk, personne_factory):
    """Une élève dont l'adresse se calcule : `alice.dupont@lekreisker.fr`."""
    return personne_factory(
        type="eleve", site_id=ndk.id, nom="DUPONT", prenom="Alice",
        login="adupont",
    )


# ---------------------------------------------------------------------------
# Le cas central : remplir un vide, mais seulement si Google confirme
# ---------------------------------------------------------------------------


def test_un_vide_se_remplit_quand_google_connait_l_adresse(session, eleve):
    from backend.services.adresses_charlemagne import confronter_adresses

    r = confronter_adresses(
        session, _fichier(_ligne(eleve.badge, "DUPONT", "Alice", "2_1")),
        comptes_google=[_compte("alice.dupont@lekreisker.fr")],
        annee_libelle="2026-2027",
    )
    assert [c.badge for c in r.a_remplir] == [str(eleve.badge)]
    assert r.a_remplir[0].adresse_referentiel == "alice.dupont@lekreisker.fr"
    assert r.a_remplir[0].origine == "calculee"
    assert r.nb_a_importer == 1


def test_une_adresse_calculee_absente_de_google_n_est_pas_proposee(
    session, eleve
):
    """C'est tout l'enjeu : la pousser propagerait l'erreur au lieu de la
    corriger."""
    from backend.services.adresses_charlemagne import confronter_adresses

    r = confronter_adresses(
        session, _fichier(_ligne(eleve.badge, "DUPONT", "Alice", "2_1")),
        comptes_google=[_compte("quelquun.dautre@lekreisker.fr")],
    )
    assert r.a_remplir == []
    assert len(r.a_verifier) == 1
    assert "n'a pas été trouvée dans Google" in r.a_verifier[0].detail
    assert r.csv_a_importer == b""


def test_sans_liste_google_rien_n_est_propose(session, eleve):
    """Un fichier d'import fait de suppositions ne vaut pas mieux qu'aucun."""
    from backend.services.adresses_charlemagne import confronter_adresses

    r = confronter_adresses(
        session, _fichier(_ligne(eleve.badge, "DUPONT", "Alice", "2_1"))
    )
    assert not r.google_consulte
    assert r.a_remplir == []
    assert len(r.a_verifier) == 1
    assert r.rien_a_faire


def test_une_adresse_deja_juste_ne_fait_rien(session, eleve):
    from backend.services.adresses_charlemagne import confronter_adresses

    r = confronter_adresses(
        session,
        _fichier(_ligne(eleve.badge, "DUPONT", "Alice", "2_1",
                        "alice.dupont@lekreisker.fr")),
        comptes_google=[_compte("alice.dupont@lekreisker.fr")],
    )
    assert r.nb_deja_bonnes == 1
    assert r.rien_a_faire


# ---------------------------------------------------------------------------
# Alias, renommages et vraies erreurs — ce qui les sépare
# ---------------------------------------------------------------------------


def test_une_adresse_d_ecole_inexistante_est_a_corriger(session, eleve):
    """Vécu : Charlemagne portait `louise.cadiou1@`, le compte est `…2@`."""
    from backend.services.adresses_charlemagne import confronter_adresses

    r = confronter_adresses(
        session,
        _fichier(_ligne(eleve.badge, "DUPONT", "Alice", "2_1",
                        "alice.dupont1@lekreisker.fr")),
        comptes_google=[_compte("alice.dupont@lekreisker.fr")],
    )
    (c,) = r.a_corriger
    assert "n'existe pas dans Google" in c.detail
    assert c.adresse_referentiel == "alice.dupont@lekreisker.fr"


def test_un_alias_du_bon_compte_n_est_pas_une_erreur(session, eleve):
    """Google garde l'ancienne adresse en alias après un renommage : le
    courrier arrive, et proposer de la « corriger » serait du bruit."""
    from backend.services.adresses_charlemagne import confronter_adresses

    r = confronter_adresses(
        session,
        _fichier(_ligne(eleve.badge, "DUPONT", "Alice", "2_1",
                        "alice.dupont.ancienne@lekreisker.fr")),
        comptes_google=[
            _compte("alice.dupont@lekreisker.fr",
                    "alice.dupont.ancienne@lekreisker.fr")
        ],
    )
    assert r.a_corriger == []
    (c,) = r.alias_dans_charlemagne
    assert "le courrier arrive" in c.detail
    assert r.rien_a_faire


def test_quand_charlemagne_a_le_compte_principal_c_est_ici_qu_on_corrige(
    session, ndk, personne_factory
):
    """Vécu : REFLOCH — le référentiel avait constaté `colleen.refloch@`,
    devenue alias après le renommage en `myo.refloch@`."""
    from backend.services.adresses_charlemagne import confronter_adresses

    p = personne_factory(
        type="eleve", site_id=ndk.id, nom="REFLOCH", prenom="Myo",
        login="mrefloch", email_constate="colleen.refloch@lekreisker.fr",
    )
    r = confronter_adresses(
        session,
        _fichier(_ligne(p.badge, "REFLOCH", "Myo", "2_6",
                        "myo.refloch@lekreisker.fr")),
        comptes_google=[
            _compte("myo.refloch@lekreisker.fr", "colleen.refloch@lekreisker.fr")
        ],
    )
    assert r.a_corriger == []
    (c,) = r.referentiel_a_tort
    assert "pas dans Charlemagne" in c.detail
    assert r.rien_a_faire, "on n'écrit pas dans Charlemagne ce qu'il a déjà juste"


def test_deux_comptes_distincts_sont_un_conflit(session, eleve):
    """Ni l'un ni l'autre ne peut être choisi sans savoir lequel l'élève
    utilise — c'est le cas des deux Hugo GUILLOU."""
    from backend.services.adresses_charlemagne import confronter_adresses

    r = confronter_adresses(
        session,
        _fichier(_ligne(eleve.badge, "DUPONT", "Alice", "2_1",
                        "a.dupont@lekreisker.fr")),
        comptes_google=[_compte("a.dupont@lekreisker.fr"),
                        _compte("alice.dupont@lekreisker.fr")],
    )
    (c,) = r.conflit
    assert "deux comptes distincts" in c.detail
    assert r.rien_a_faire


# ---------------------------------------------------------------------------
# L'adresse de la famille
# ---------------------------------------------------------------------------


def test_une_adresse_personnelle_est_signalee_sans_etre_ecrasee(session, eleve):
    """46 lignes en portaient une. L'écraser est peut-être ce qu'on veut,
    mais c'est une décision, et elle est sans retour."""
    from backend.services.adresses_charlemagne import confronter_adresses

    r = confronter_adresses(
        session,
        _fichier(_ligne(eleve.badge, "DUPONT", "Alice", "2_1",
                        "famille.dupont@gmail.com")),
        comptes_google=[_compte("alice.dupont@lekreisker.fr")],
    )
    (c,) = r.adresse_personnelle
    assert c.adresse_charlemagne == "famille.dupont@gmail.com"
    assert r.rien_a_faire
    assert r.csv_a_importer == b""


# ---------------------------------------------------------------------------
# Le fichier rendu
# ---------------------------------------------------------------------------


def test_le_fichier_porte_le_badge_et_l_adresse(session, eleve):
    from backend.services.adresses_charlemagne import (
        COLONNES_RETOUR,
        confronter_adresses,
    )

    r = confronter_adresses(
        session, _fichier(_ligne(eleve.badge, "DUPONT", "Alice", "2_1")),
        comptes_google=[_compte("alice.dupont@lekreisker.fr")],
        annee_libelle="2026-2027",
    )
    texte = r.csv_a_importer.decode("utf-8-sig")
    lues = list(csv.reader(io.StringIO(texte), delimiter=";"))
    assert lues[0] == list(COLONNES_RETOUR)
    assert lues[1] == [str(eleve.badge), "ELEVE", "DUPONT", "Alice",
                       "alice.dupont@lekreisker.fr"]
    assert r.csv_a_importer.startswith(b"\xef\xbb\xbf")
    assert r.nom_fichier == "Charlemagne_adresses_2026-2027.csv"


def test_le_type_est_en_deuxieme_colonne(session, eleve):
    """Charlemagne le lit à cette place, et refuse le fichier s'il est
    ailleurs."""
    import csv
    import io as _io

    from backend.services.adresses_charlemagne import (
        COLONNES_RETOUR,
        confronter_adresses,
    )

    assert COLONNES_RETOUR[1] == "Type"
    r = confronter_adresses(
        session, _fichier(_ligne(eleve.badge, "DUPONT", "Alice", "2_1")),
        comptes_google=[_compte("alice.dupont@lekreisker.fr")],
    )
    lues = list(csv.reader(_io.StringIO(r.csv_a_importer.decode("utf-8-sig")),
                           delimiter=";"))
    assert lues[0][1] == "Type"
    assert lues[1][1] == "ELEVE"


def test_un_adulte_porte_ADULTE(session, ndk, personne_factory):
    """Le vocabulaire de Charlemagne n'est pas celui du référentiel."""
    import csv
    import io as _io

    from backend.services.adresses_charlemagne import confronter_adresses

    p = personne_factory(
        type="adulte", site_id=ndk.id, nom="MARTIN", prenom="Jean",
        login="jmartin",
    )
    r = confronter_adresses(
        session, _fichier(_ligne(p.badge, "MARTIN", "Jean", "")),
        comptes_google=[_compte("jean.martin@lekreisker.fr")],
    )
    lues = list(csv.reader(_io.StringIO(r.csv_a_importer.decode("utf-8-sig")),
                           delimiter=";"))
    assert lues[1][1] == "ADULTE"


def test_aucun_fichier_quand_il_n_y_a_rien_a_importer(session, eleve):
    """Deux fichiers vides enregistrés puis ouverts, c'est la leçon des
    étiquettes NDE : mieux vaut ne rien rendre du tout."""
    from backend.services.adresses_charlemagne import confronter_adresses

    r = confronter_adresses(
        session,
        _fichier(_ligne(eleve.badge, "DUPONT", "Alice", "2_1",
                        "alice.dupont@lekreisker.fr")),
        comptes_google=[_compte("alice.dupont@lekreisker.fr")],
    )
    assert r.csv_a_importer == b""
    assert r.nom_fichier == ""


# ---------------------------------------------------------------------------
# Les bords
# ---------------------------------------------------------------------------


def test_un_eleve_inconnu_du_referentiel_est_signale(session, ndk):
    from backend.services.adresses_charlemagne import confronter_adresses

    r = confronter_adresses(
        session, _fichier(_ligne(99760, "BOIAN", "Rébecca", "35")),
        comptes_google=[],
    )
    (c,) = r.hors_referentiel
    assert (c.badge, c.nom) == ("99760", "BOIAN")
    assert r.rien_a_faire


def test_un_eleve_sans_adresse_nulle_part_est_signale(
    session, personne_factory
):
    """Sans site, le programme ne devine pas de domaine — et ne doit pas."""
    from backend.services.adresses_charlemagne import confronter_adresses

    p = personne_factory(type="eleve", site_id=None, nom="X", prenom="Y")
    r = confronter_adresses(
        session, _fichier(_ligne(p.badge, "X", "Y", "2_1")), comptes_google=[]
    )
    assert len(r.sans_adresse_nulle_part) == 1
    assert r.a_verifier == []


def test_un_fichier_sans_colonne_email_est_refuse(session, ndk):
    from backend.services.adresses_charlemagne import confronter_adresses
    from backend.services.repartition_pmb import RepartitionImpossible

    with pytest.raises(RepartitionImpossible) as e:
        confronter_adresses(
            session, _fichier("11;A;B;2_1", entete="Num Badge;Nom;Prénom;Code classe")
        )
    assert "Email" in str(e.value)


def test_un_fichier_vide_est_refuse(session, ndk):
    from backend.services.adresses_charlemagne import confronter_adresses
    from backend.services.repartition_pmb import RepartitionImpossible

    with pytest.raises(RepartitionImpossible):
        confronter_adresses(session, b"")


def test_l_export_pmb_de_charlemagne_convient_tel_quel(session, eleve):
    """C'est le fichier que le CDI sort déjà : autant s'en servir plutôt que
    d'en demander un autre."""
    from backend.services.adresses_charlemagne import confronter_adresses

    entete = (
        "Num Badge;Nom;Prénom;Adresse 1;Adresse 2;CP;Ville;"
        "Tél. domicile (avec LR);Année de naissance;Code classe;Sexe;Email;"
        "Prof. Princ."
    )
    ligne = f"{eleve.badge};DUPONT;Alice;1 rue X;;29250;ST POL;;2010;2_1;F;;Mme T A"
    r = confronter_adresses(
        session, _fichier(ligne, entete=entete),
        comptes_google=[_compte("alice.dupont@lekreisker.fr")],
    )
    assert len(r.a_remplir) == 1
    assert r.a_remplir[0].classe == "2_1"
