"""Tests de l'inventaire des photos.

La question posée est toujours nominative — « donne-moi la liste, avec nom,
prénom et classe » — parce qu'elle sert à relancer les professeurs
principaux. Les tests portent donc sur ce que le relevé nomme, et sur ce
qu'il ne déclare pas manquant à tort.
"""
from __future__ import annotations

import json

import pytest


@pytest.fixture()
def contexte(session, site_factory, annee_factory, personne_factory, tmp_path):
    from backend.models import Parametre, Snapshot

    site = site_factory("NDK")
    annee = annee_factory("2026-2027")
    session.add(
        Parametre(
            cle="chemin_dossier_photos", valeur_json=json.dumps(str(tmp_path))
        )
    )
    session.commit()

    def _eleve(nom, prenom, classe="2_5", **kw):
        p = personne_factory(nom=nom, prenom=prenom, site_id=site.id, **kw)
        session.add(
            Snapshot(
                personne_id=p.id,
                annee_scolaire_id=annee.id,
                nom=nom,
                prenom=prenom,
                classe=classe,
            )
        )
        session.commit()
        return p

    return {"site": site, "annee": annee, "eleve": _eleve, "dossier": tmp_path}


def _relever(session, contexte):
    from backend.services.inventaire_photos import relever

    return relever(session, annee_id=contexte["annee"].id)


def test_une_photo_presente_se_voit(session, contexte):
    contexte["eleve"]("DUPONT", "Jean")
    (contexte["dossier"] / "DUPONT Jean.jpg").write_bytes(b"x")

    r = _relever(session, contexte)
    assert (r.nb_eleves, r.nb_avec, r.nb_sans) == (1, 1, 0)
    assert r.taux == 1.0


def test_une_photo_absente_est_nommee_avec_sa_classe(session, contexte):
    contexte["eleve"]("SANSPHOTO", "Zoe", classe="1_G3")

    r = _relever(session, contexte)
    assert r.nb_sans == 1
    m = r.manquantes[0]
    assert (m.nom, m.prenom, m.classe, m.site) == ("SANSPHOTO", "Zoe", "1_G3", "NDK")
    assert m.chemin_attendu.endswith("SANSPHOTO Zoe.jpg")


def test_les_variantes_de_nommage_sont_acceptees(session, contexte):
    """Déclarer manquante une photo qui est là ferait relancer pour rien."""
    contexte["eleve"]("AVEC", "Souligne")
    contexte["eleve"]("AVEC", "Inverse")
    (contexte["dossier"] / "AVEC_Souligne.png").write_bytes(b"x")
    (contexte["dossier"] / "Inverse AVEC.jpeg").write_bytes(b"x")

    r = _relever(session, contexte)
    assert r.nb_sans == 0


def test_la_casse_du_fichier_nempeche_pas_de_trouver(session, contexte):
    contexte["eleve"]("DUPONT", "Jean")
    (contexte["dossier"] / "dupont jean.JPG").write_bytes(b"x")

    assert _relever(session, contexte).nb_sans == 0


def test_le_compte_par_classe_sert_a_relancer(session, contexte):
    contexte["eleve"]("A", "Un", classe="2_5")
    contexte["eleve"]("B", "Deux", classe="2_5")
    contexte["eleve"]("C", "Trois", classe="1_G3")
    (contexte["dossier"] / "A Un.jpg").write_bytes(b"x")

    r = _relever(session, contexte)
    assert r.par_classe["2_5"] == {"avec": 1, "sans": 1}
    assert r.par_classe["1_G3"] == {"avec": 0, "sans": 1}
    # Les classes les plus incomplètes d'abord : c'est l'ordre des relances.
    assert r.classes_incompletes == ["1_G3", "2_5"]


def test_un_eleve_sans_classe_nentre_pas_dans_le_compte(session, contexte):
    """Sans classe, on ne sait pas à qui le réclamer."""
    contexte["eleve"]("HORS", "Classe", classe="")

    r = _relever(session, contexte)
    assert r.nb_eleves == 0


def test_dossier_non_regle_et_dossier_absent_se_disent_differemment(
    session, site_factory, annee_factory, tmp_path
):
    """Les deux se corrigent différemment : un réglage, ou un partage à monter."""
    from backend.models import Parametre
    from backend.services.inventaire_photos import InventaireImpossible, relever

    site_factory("NDK")
    annee = annee_factory("2026-2027")

    with pytest.raises(InventaireImpossible, match="Paramètres"):
        relever(session, annee_id=annee.id)

    session.add(
        Parametre(
            cle="chemin_dossier_photos",
            valeur_json=json.dumps(str(tmp_path / "nulle-part")),
        )
    )
    session.commit()
    with pytest.raises(InventaireImpossible, match="partage réseau"):
        relever(session, annee_id=annee.id)


def test_le_classeur_porte_les_colonnes_quon_distribue(session, contexte):
    import io

    import openpyxl

    from backend.services.inventaire_photos import classeur

    contexte["eleve"]("SANSPHOTO", "Zoe", classe="1_G3")
    r = _relever(session, contexte)

    feuille = openpyxl.load_workbook(io.BytesIO(classeur(r))).active
    lignes = list(feuille.iter_rows(values_only=True))
    assert lignes[0][:4] == ("Classe", "Nom", "Prénom", "Site")
    assert lignes[1][:3] == ("1_G3", "SANSPHOTO", "Zoe")


# ---------------------------------------------------------------------------
# Les adultes : un autre dossier, une autre maille
# ---------------------------------------------------------------------------


def test_les_adultes_ont_leur_propre_dossier(session, contexte, personne_factory, tmp_path):
    """Chercher un professeur parmi les photos d'élèves ne ferait que des
    absences fausses : les deux arborescences ne se recoupent pas."""
    from backend.models import Parametre, Snapshot
    from backend.services.inventaire_photos import relever

    dossier_adultes = tmp_path / "Enseignants"
    dossier_adultes.mkdir()
    session.add(
        Parametre(
            cle="chemin_dossier_photos_adultes",
            valeur_json=json.dumps(str(dossier_adultes)),
        )
    )
    prof = personne_factory(
        type="adulte", nom="ABIVEN", prenom="Ingrid", site_id=contexte["site"].id
    )
    session.add(
        Snapshot(
            personne_id=prof.id, annee_scolaire_id=contexte["annee"].id,
            nom="ABIVEN", prenom="Ingrid",
        )
    )
    session.commit()
    (dossier_adultes / "ABIVEN Ingrid.jpg").write_bytes(b"x")

    r = relever(session, annee_id=contexte["annee"].id, type_personne="adulte")
    assert (r.nb_eleves, r.nb_avec, r.nb_sans) == (1, 1, 0)
    # La maille d'un adulte est son site, pas une classe qu'il n'a pas.
    assert list(r.par_classe) == ["NDK"]


def test_un_adulte_sans_annee_nentre_pas_dans_le_compte(session, contexte, personne_factory, tmp_path):
    """Sinon la liste des relances serait pleine de gens partis."""
    from backend.models import Parametre
    from backend.services.inventaire_photos import relever

    dossier_adultes = tmp_path / "Enseignants"
    dossier_adultes.mkdir()
    session.add(
        Parametre(
            cle="chemin_dossier_photos_adultes",
            valeur_json=json.dumps(str(dossier_adultes)),
        )
    )
    personne_factory(type="adulte", nom="PARTI", prenom="Depuis", site_id=contexte["site"].id)
    session.commit()

    r = relever(session, annee_id=contexte["annee"].id, type_personne="adulte")
    assert r.nb_eleves == 0


def test_le_dossier_adultes_manquant_se_dit_pour_les_adultes(session, contexte):
    from backend.services.inventaire_photos import InventaireImpossible, relever

    with pytest.raises(InventaireImpossible, match="photos adultes"):
        relever(session, annee_id=contexte["annee"].id, type_personne="adulte")


# ---------------------------------------------------------------------------
# Les homonymes : la classe entre parenthèses
# ---------------------------------------------------------------------------


def test_deux_homonymes_trouvent_chacune_sa_photo(session, contexte):
    """Deux SAOUT Marie ne peuvent pas partager un fichier.

    La vie scolaire ajoute alors la classe entre parenthèses. Sans les
    chercher, les deux sont déclarées sans photo alors qu'elles en ont
    chacune une.
    """
    contexte["eleve"]("SAOUT", "Marie", classe="44", login="msaout")
    contexte["eleve"]("SAOUT", "Marie", classe="BTS_2", login="msaout2")
    (contexte["dossier"] / "SAOUT Marie (44).JPG").write_bytes(b"x")
    (contexte["dossier"] / "SAOUT Marie (BTS2).JPG").write_bytes(b"x")

    r = _relever(session, contexte)
    assert (r.nb_eleves, r.nb_avec, r.nb_sans) == (2, 2, 0)


def test_un_suffixe_non_deductible_est_signale_pas_devine(session, contexte):
    """`(TMCV1)` ne se déduit pas de `T_BPMCV1`.

    Attribuer au jugé mettrait le visage d'une élève sur la carte de son
    homonyme. On nomme le fichier et on laisse trancher.
    """
    contexte["eleve"]("BELLEC", "Manon", classe="21", login="mbellec")
    contexte["eleve"]("BELLEC", "Manon", classe="T_BPMCV1", login="mbellec2")
    (contexte["dossier"] / "BELLEC Manon (21).JPG").write_bytes(b"x")
    (contexte["dossier"] / "BELLEC Manon (TMCV1).JPG").write_bytes(b"x")

    r = _relever(session, contexte)
    assert r.nb_avec == 1
    assert r.nb_sans == 1
    assert r.nb_a_verifier == 1
    manquante = r.manquantes[0]
    assert manquante.classe == "T_BPMCV1"
    assert manquante.pistes == ["bellec manon (tmcv1).jpg"]


def test_une_photo_exacte_lemporte_sur_une_parenthesee(session, contexte):
    """Le fichier sans parenthèse désigne la personne sans ambiguïté."""
    contexte["eleve"]("SEULE", "Anne", classe="2_5")
    (contexte["dossier"] / "SEULE Anne.jpg").write_bytes(b"x")
    (contexte["dossier"] / "SEULE Anne (autre).jpg").write_bytes(b"x")

    r = _relever(session, contexte)
    assert r.nb_sans == 0


def test_sans_parenthese_aucune_piste_nest_inventee(session, contexte):
    contexte["eleve"]("ABSENTE", "Zoe", classe="2_5")

    r = _relever(session, contexte)
    assert r.manquantes[0].pistes == []
    assert r.nb_a_verifier == 0


def test_un_fichier_revendique_par_deux_nest_a_personne(session, contexte):
    """`BELLEC Manon.jpg` existe à côté des deux fichiers parenthésés.

    Les deux Manon s'en réclamaient, et chacune était comptée « avec
    photo » — sur la même image. C'est exactement ce que la parenthèse
    existe pour éviter : on rend le fichier au doute.
    """
    contexte["eleve"]("BELLEC", "Manon", classe="BTS_1", login="mbellec")
    contexte["eleve"]("BELLEC", "Manon", classe="1_ST2S1", login="mbellec2")
    (contexte["dossier"] / "BELLEC Manon.jpg").write_bytes(b"x")
    (contexte["dossier"] / "BELLEC Manon (21).JPG").write_bytes(b"x")
    (contexte["dossier"] / "BELLEC Manon (TMCV1).JPG").write_bytes(b"x")

    r = _relever(session, contexte)
    assert r.nb_avec == 0
    assert r.nb_sans == 2
    assert r.nb_a_verifier == 2
    # Les trois fichiers leur sont proposés, le disputé compris : retirer
    # un fichier du compte sans le montrer laisserait croire qu'il n'existe
    # pas. C'est à elle de trancher, pas au programme.
    for e in r.manquantes:
        assert e.pistes == [
            "bellec manon (21).jpg",
            "bellec manon (tmcv1).jpg",
            "bellec manon.jpg",
        ]


def test_la_parenthese_lemporte_sur_le_nom_nu(session, contexte):
    """Le fichier parenthésé désigne quelqu'un exprès ; le nom nu, non."""
    contexte["eleve"]("SAOUT", "Marie", classe="44", login="msaout")
    (contexte["dossier"] / "SAOUT Marie.jpg").write_bytes(b"x")
    (contexte["dossier"] / "SAOUT Marie (44).JPG").write_bytes(b"x")

    r = _relever(session, contexte)
    assert r.nb_sans == 0
