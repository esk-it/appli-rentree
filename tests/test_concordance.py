"""Quatre sources pour une seule classe, mises côte à côte.

À la rentrée 2026, quarante-quatre élèves avaient changé de classe dans
Charlemagne après le premier import. Le référentiel a suivi à la
ré-ingestion ; Google et KoXo, jamais. Personne ne l'a vu pendant deux
semaines : aucun écran ne montrait les quatre valeurs ensemble.
"""
from __future__ import annotations

import pytest

ENTETE = "Num Badge;Nom;Prénom;Code classe"


def _fichier(*lignes, entete=ENTETE):
    return (b"\xef\xbb\xbf"
            + ("\r\n".join([entete, *lignes]) + "\r\n").encode("utf-8"))


def _compte(email, ou, *alias):
    return {"email": email, "alias": list(alias), "ou": ou,
            "nom": "X", "prenom": "Y", "suspendu": False, "id_externe": None}


class _LigneKoxo:
    def __init__(self, id_unique, groupe_secondaire):
        self.id_unique = id_unique
        self.groupe_secondaire = groupe_secondaire


@pytest.fixture()
def etab(session, site_factory, annee_factory):
    from backend.models import TableCorrespondance

    site = site_factory("NDK")
    an = annee_factory("2026-2027")
    for code in ("2_4", "2_5", "2_6"):
        session.add(TableCorrespondance(
            site_id=site.id, classe_charlemagne_long=f"SECONDE {code}",
            classe_code_court=code,
            ou_pre_rentree="/NDK/NDK2027",
            ou_definitive=f"/NDK/NDK2027/{code}",
            groupe_google=f"2nde-{code[-1]}@lekreisker.fr",
        ))
    session.commit()
    return site, an


@pytest.fixture()
def eleve(session, etab, personne_factory):
    site, an = etab
    return personne_factory(
        type="eleve", site_id=site.id, nom="CAZUC", prenom="Axel",
        login="acazuc", classe="2_4", email_constate="axel.cazuc@lekreisker.fr",
    )


# ---------------------------------------------------------------------------
# Le cas vécu
# ---------------------------------------------------------------------------


def test_google_en_retard_sur_charlemagne_est_signale(session, etab, eleve):
    """CAZUC Axel : Charlemagne et le référentiel disent 2_4, Google 2_6."""
    from backend.services.concordance import croiser

    _, an = etab
    r = croiser(
        session, _fichier(f"{eleve.badge};CAZUC;Axel;2_4"), annee_id=an.id,
        comptes_google=[_compte("axel.cazuc@lekreisker.fr", "/NDK/NDK2027/2_6")],
        membres_par_groupe={"2nde-6@lekreisker.fr": ["axel.cazuc@lekreisker.fr"],
                            "2nde-4@lekreisker.fr": []},
    )
    (l,) = r.lignes
    assert l.charlemagne == "2_4"
    assert l.referentiel == "2_4"
    assert l.google_classe == "2_6"
    assert "google" in l.genres and "groupe" in l.genres
    assert "referentiel" not in l.genres
    assert l.propose == "2_4", "Charlemagne fait foi par défaut"


def test_tout_le_monde_d_accord_ne_sort_pas(session, etab, eleve):
    from backend.services.concordance import croiser

    _, an = etab
    r = croiser(
        session, _fichier(f"{eleve.badge};CAZUC;Axel;2_4"), annee_id=an.id,
        comptes_google=[_compte("axel.cazuc@lekreisker.fr", "/NDK/NDK2027/2_4")],
        membres_par_groupe={"2nde-4@lekreisker.fr": ["axel.cazuc@lekreisker.fr"]},
    )
    assert r.lignes == []
    assert r.nb_accord == 1


def test_le_referentiel_en_retard_est_signale(session, etab, eleve):
    from backend.services.concordance import croiser

    _, an = etab
    r = croiser(session, _fichier(f"{eleve.badge};CAZUC;Axel;2_5"), annee_id=an.id)
    (l,) = r.lignes
    assert "referentiel" in l.genres
    assert (l.charlemagne, l.referentiel) == ("2_5", "2_4")


# ---------------------------------------------------------------------------
# Une source qu'on n'interroge pas se tait
# ---------------------------------------------------------------------------


def test_sans_google_la_colonne_reste_vide_plutot_que_fausse(session, etab, eleve):
    """Sans cette règle, ne pas interroger Google ferait passer toute
    l'école pour désynchronisée."""
    from backend.services.concordance import croiser

    _, an = etab
    r = croiser(session, _fichier(f"{eleve.badge};CAZUC;Axel;2_4"), annee_id=an.id)
    assert not r.google_consulte
    assert r.lignes == [] and r.nb_accord == 1


def test_sans_koxo_aucun_ecart_koxo(session, etab, eleve):
    from backend.services.concordance import croiser

    _, an = etab
    r = croiser(
        session, _fichier(f"{eleve.badge};CAZUC;Axel;2_4"), annee_id=an.id,
        comptes_google=[_compte("axel.cazuc@lekreisker.fr", "/NDK/NDK2027/2_4")],
        membres_par_groupe={"2nde-4@lekreisker.fr": ["axel.cazuc@lekreisker.fr"]},
    )
    assert not r.koxo_fourni
    assert "koxo" not in r.par_genre()


def test_koxo_en_retard_est_signale(session, etab, eleve):
    from backend.services.concordance import croiser

    _, an = etab
    r = croiser(
        session, _fichier(f"{eleve.badge};CAZUC;Axel;2_4"), annee_id=an.id,
        lignes_koxo=[_LigneKoxo(str(eleve.badge), "2_6")],
    )
    (l,) = r.lignes
    assert l.koxo == "2_6"
    assert "koxo" in l.genres


def test_koxo_apparie_par_badge_jamais_par_nom(session, etab, eleve):
    """Le programme écrit toujours le badge dans l'ID unique de KoXo ;
    c'est la seule clé qui ne bouge pas."""
    from backend.services.concordance import croiser

    _, an = etab
    r = croiser(
        session, _fichier(f"{eleve.badge};CAZUC;Axel;2_4"), annee_id=an.id,
        lignes_koxo=[_LigneKoxo("999999", "2_4")],
    )
    (l,) = r.lignes
    assert l.koxo is None
    assert "absent_koxo" in l.genres


# ---------------------------------------------------------------------------
# Les bords
# ---------------------------------------------------------------------------


def test_une_unite_d_attente_n_est_pas_un_desaccord_de_classe(session, etab, eleve):
    """Un compte pas encore basculé n'est pas rangé dans la mauvaise
    classe : il n'est encore dans aucune."""
    from backend.services.concordance import croiser

    _, an = etab
    r = croiser(
        session, _fichier(f"{eleve.badge};CAZUC;Axel;2_4"), annee_id=an.id,
        comptes_google=[_compte("axel.cazuc@lekreisker.fr", "/NDK/NDK2027")],
    )
    (l,) = r.lignes
    assert "hors_arbre_de_classe" in l.genres
    assert "google" not in l.genres


def test_un_eleve_absent_du_referentiel_est_signale(session, etab):
    from backend.services.concordance import croiser

    _, an = etab
    r = croiser(session, _fichier("99760;BOIAN;Rébecca;2_4"), annee_id=an.id)
    (l,) = r.lignes
    assert l.personne_id is None
    assert "absent_referentiel" in l.genres


def test_une_ligne_sans_classe_est_ignoree(session, etab, eleve):
    """Sans classe chez Charlemagne, l'élève n'est pas inscrit cette
    année : c'est un sortant, et il se traite ailleurs."""
    from backend.services.concordance import croiser

    _, an = etab
    r = croiser(session, _fichier(f"{eleve.badge};CAZUC;Axel;"), annee_id=an.id)
    assert r.nb_lignes_lues == 0
    assert r.lignes == []


def test_les_classes_concernees_sont_celles_d_arrivee(session, etab, eleve):
    """C'est la liste que la bascule et la synchro des groupes attendent."""
    from backend.services.concordance import croiser

    _, an = etab
    r = croiser(
        session, _fichier(f"{eleve.badge};CAZUC;Axel;2_5"), annee_id=an.id,
        comptes_google=[_compte("axel.cazuc@lekreisker.fr", "/NDK/NDK2027/2_6")],
    )
    assert r.classes_concernees == ["2_5"]


def test_un_fichier_sans_les_colonnes_est_refuse(session, etab):
    from backend.services.concordance import ConcordanceImpossible, croiser

    _, an = etab
    with pytest.raises(ConcordanceImpossible) as e:
        croiser(session, _fichier("a;b", entete="login;nom"), annee_id=an.id)
    assert "Num Badge" in str(e.value)


def test_une_annee_inconnue_est_refusee(session, etab):
    from backend.services.concordance import ConcordanceImpossible, croiser

    with pytest.raises(ConcordanceImpossible, match="Année introuvable"):
        croiser(session, _fichier("1;A;B;2_4"), annee_id=9999)


def test_l_alias_google_apparie_le_compte(session, etab, eleve):
    """Un renommage laisse l'ancienne adresse en alias ; le compte est le
    même, et le manquer ferait croire à un élève sans compte."""
    from backend.services.concordance import croiser

    _, an = etab
    r = croiser(
        session, _fichier(f"{eleve.badge};CAZUC;Axel;2_4"), annee_id=an.id,
        comptes_google=[_compte("nouveau.axel@lekreisker.fr", "/NDK/NDK2027/2_4",
                                "axel.cazuc@lekreisker.fr")],
        membres_par_groupe={"2nde-4@lekreisker.fr": ["axel.cazuc@lekreisker.fr"]},
    )
    assert r.lignes == [], "l'alias suffit à retrouver le compte"
    assert r.nb_accord == 1
