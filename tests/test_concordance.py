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


def test_koxo_apparie_par_badge_jamais_par_nom(
    session, etab, eleve, personne_factory
):
    """Le programme écrit toujours le badge dans l'ID unique de KoXo ;
    c'est la seule clé qui ne bouge pas. Une ligne dont le nom colle mais
    dont l'ID diffère ne compte pas comme une correspondance."""
    from backend.services.concordance import croiser

    site, an = etab
    autre = personne_factory(
        type="eleve", site_id=site.id, nom="MARTIN", prenom="Lou",
        login="lmartin", classe="2_4",
    )
    r = croiser(
        session,
        _fichier(f"{eleve.badge};CAZUC;Axel;2_4", f"{autre.badge};MARTIN;Lou;2_4"),
        annee_id=an.id,
        # Le premier apparie (l'export parle donc bien de NDK) ; le second
        # porte le bon nom mais un ID unique étranger.
        lignes_koxo=[_LigneKoxo(str(autre.badge), "2_4"),
                     _LigneKoxo("999999", "2_4")],
    )
    (l,) = r.lignes
    assert l.nom == "CAZUC"
    assert l.koxo is None
    assert "absent_koxo" in l.genres


def test_un_export_koxo_ne_parle_que_de_sa_base(
    session, etab, eleve, site_factory, personne_factory
):
    """KoXo a **une base par établissement**, et on ne peut en exporter
    qu'une. Déposer celui de NDK faisait passer les six cent quatre-vingt-
    neuf élèves de SU pour absents de KoXo — un écart par élève, sur une
    base qui n'était même pas interrogée."""
    from backend.services.concordance import croiser

    site, an = etab
    su = site_factory("SU")
    ailleurs = personne_factory(
        type="eleve", site_id=su.id, nom="ABGRALL", prenom="Lena",
        login="labgrall", classe="2_4",
    )
    r = croiser(
        session,
        _fichier(f"{eleve.badge};CAZUC;Axel;2_4",
                 f"{ailleurs.badge};ABGRALL;Lena;2_4"),
        annee_id=an.id,
        lignes_koxo=[_LigneKoxo(str(eleve.badge), "2_4")],   # export NDK seul
    )
    assert r.koxo_sites == ["NDK"]
    assert r.lignes == [], "l'élève de SU n'est pas accusé d'absence"
    assert r.nb_accord == 2


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


# ---------------------------------------------------------------------------
# Les formats que Charlemagne produit
# ---------------------------------------------------------------------------


def _html(*lignes):
    """Ce que Charlemagne appelle un `.htm` : une table HTML, en cp1252.

    L'en-tête est en `<th>`, comme dans ses vrais exports — c'est ce qui
    permet à pandas de le reconnaître comme tel plutôt que de numéroter les
    colonnes.
    """
    entete = ("<tr><th>Num Badge</th><th>Identifiant Elève</th><th>Nom</th>"
              "<th>Prénom</th><th>Code classe</th></tr>")
    corps = "".join(
        "<tr>" + "".join(f"<td>{c}</td>" for c in l) + "</tr>" for l in lignes
    )
    return f"<HTML><body><table>{entete}{corps}</table></body></HTML>".encode("cp1252")


def test_l_export_html_de_charlemagne_est_lu(session, etab, eleve):
    """L'écran l'acceptait, le service répondait « l'en-tête lu commence par
    : <HTML> » — un message juste sur un fichier parfaitement valide."""
    from backend.services.concordance import croiser

    _, an = etab
    r = croiser(
        session, _html([eleve.badge, eleve.id_charlemagne, "CAZUC", "Axel", "2_5"]),
        annee_id=an.id,
    )
    assert r.nb_lignes_lues == 1
    (l,) = r.lignes
    assert (l.charlemagne, l.referentiel) == ("2_5", "2_4")
    assert "referentiel" in l.genres


def test_un_html_sans_les_colonnes_est_refuse_clairement(session, etab):
    from backend.services.concordance import ConcordanceImpossible, croiser

    _, an = etab
    mauvais = b"<HTML><table><tr><td>login</td></tr><tr><td>x</td></tr></table></HTML>"
    with pytest.raises(ConcordanceImpossible) as e:
        croiser(session, mauvais, annee_id=an.id)
    assert "Num Badge" in str(e.value)


def test_le_format_se_reconnait_au_contenu_pas_a_l_extension(session, etab, eleve):
    """Un `.htm` renommé reste du HTML, et c'est la première chose qu'on
    fait avec un export qu'on range."""
    from backend.services.concordance import croiser

    _, an = etab
    avec_bom = b"\xef\xbb\xbf" + _html(
        [eleve.badge, eleve.id_charlemagne, "CAZUC", "Axel", "2_4"]
    ).decode("cp1252").encode("utf-8")
    r = croiser(session, avec_bom, annee_id=an.id)
    assert r.nb_lignes_lues == 1
