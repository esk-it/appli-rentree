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


def test_les_deux_bases_deposees_ensemble_couvrent_l_ecole(
    session, etab, eleve, site_factory, personne_factory
):
    """Ne pas accuser l'autre site ne suffisait pas : il fallait pouvoir le
    juger. Un export par base, déposés ensemble, et les deux répondent."""
    from backend.services.concordance import croiser

    site, an = etab
    su = site_factory("SU")
    ailleurs = personne_factory(
        type="eleve", site_id=su.id, nom="ABGRALL", prenom="Lena",
        login="labgrall", classe="61",
    )
    r = croiser(
        session,
        _fichier(f"{eleve.badge};CAZUC;Axel;2_4",
                 f"{ailleurs.badge};ABGRALL;Lena;61"),
        annee_id=an.id,
        koxo_par_base=[
            [_LigneKoxo(str(eleve.badge), "2_4")],      # base NDK
            [_LigneKoxo(str(ailleurs.badge), "52")],    # base SU, en retard
        ],
    )
    assert r.koxo_sites == ["NDK", "SU"], "les deux bases sont interrogées"
    assert [l.nom for l in r.lignes] == ["ABGRALL"]
    assert r.lignes[0].genres == ["koxo"]
    assert r.lignes[0].koxo == "52"


def test_une_petite_base_ne_disparait_pas_derriere_une_grosse(
    session, etab, eleve, site_factory, personne_factory
):
    """La couverture se calcule fichier par fichier. Sur le tas fusionné,
    le seuil proportionnel effacerait la base la moins peuplée."""
    from backend.services.concordance import croiser

    site, an = etab
    su = site_factory("SU")
    petits = [
        personne_factory(
            type="eleve", site_id=su.id, nom=f"N{i}", prenom="X",
            login=f"x{i}", classe="61",
        )
        for i in range(2)
    ]
    gros = [
        personne_factory(
            type="eleve", site_id=site.id, nom=f"M{i}", prenom="Y",
            login=f"y{i}", classe="2_4",
        )
        for i in range(60)
    ]
    r = croiser(
        session,
        _fichier(*[f"{p.badge};{p.nom};{p.prenom};2_4" for p in gros],
                 *[f"{p.badge};{p.nom};{p.prenom};61" for p in petits]),
        annee_id=an.id,
        koxo_par_base=[
            [_LigneKoxo(str(p.badge), "2_4") for p in gros],
            [_LigneKoxo(str(p.badge), "61") for p in petits],
        ],
    )
    assert r.koxo_sites == ["NDK", "SU"]


# ---------------------------------------------------------------------------
# La lecture des exports déposés
# ---------------------------------------------------------------------------


def _export_koxo(*eleves: tuple[str, str, str, str]) -> str:
    """Un export KoXo en base64, tel que le routeur le reçoit.

    Chaque élève est `(groupe_secondaire, nom, prenom, login, id_unique)`
    aplati en `(groupe, nom, login, id_unique)` — le prénom est déduit.
    """
    import base64

    entete = (
        "Groupe primaire;Groupe secondaire;Titre;Nom;Prénom;Identifiant;"
        "ID unique;Mot de passe;Date de naissance;Email"
    )
    lignes = [entete]
    for groupe, nom, login, ident in eleves:
        lignes.append(
            f"Elèves;{groupe};;{nom};Prenom;{login};{ident};Mdp00001;;"
        )
    texte = "\r\n".join(lignes) + "\r\n"
    return base64.b64encode(texte.encode("cp1252")).decode("ascii")


def test_deux_exports_restent_deux_bases():
    """Elles ne sont pas fusionnées : chacune dit de qui elle parle."""
    from backend.routers.concordance import _lire_les_exports_koxo

    bases, avertis = _lire_les_exports_koxo([
        _export_koxo(("2_4", "CAZUC", "acazuc", "111")),
        _export_koxo(("61", "ABGRALL", "labgrall", "222")),
    ])
    assert [len(b) for b in bases] == [1, 1]
    assert avertis == []


def test_deux_comptes_pour_un_eleve_dans_la_meme_base_sont_signales():
    """Vécu : Lou PERON portait « lperon » et « lperon1 », même ID unique.
    Le second est à supprimer dans KoXo, et rien ne le disait."""
    from backend.routers.concordance import _lire_les_exports_koxo

    bases, avertis = _lire_les_exports_koxo([
        _export_koxo(
            ("T_G4B", "PERON", "lperon", "87500"),
            ("T_G4B", "PERON", "lperon1", "87500"),
        ),
    ])
    assert len(bases[0]) == 1, "la seconde ligne n'est pas comptée deux fois"
    assert len(avertis) == 1
    assert "même base" in avertis[0]
    assert "lperon et lperon1" in avertis[0]


def test_un_eleve_present_dans_deux_bases_reste_dans_les_deux():
    """Deux bases, deux comptes, et aucun n'est jeté à la lecture.

    La lecture ne connaît pas le site de l'élève : elle ne peut pas savoir
    lequel des deux fait foi. Garder « le premier lu » faisait dépendre la
    réponse de l'ordre de dépôt — et comme on dépose NDK avant SU, un
    élève de SU inscrit en DAO au lycée était jugé sur son compte DAO.
    """
    from backend.routers.concordance import _lire_les_exports_koxo

    bases, avertis = _lire_les_exports_koxo([
        _export_koxo(("DAO", "SCHOLAR", "ascholar", "333")),
        _export_koxo(("31", "SCHOLAR", "ascholar", "333")),
    ])
    assert [len(b) for b in bases] == [1, 1]
    assert avertis == [], "ce n'est pas un doublon : ce sont deux serveurs"


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



# ---------------------------------------------------------------------------
# Les accès secondaires : la DAO
# ---------------------------------------------------------------------------


def _eleves(personne_factory, site, prefixe, classe, n):
    return [
        personne_factory(
            type="eleve", site_id=site.id, nom=f"{prefixe}{i}", prenom="X",
            login=f"{prefixe.lower()}{i}", classe=classe,
        )
        for i in range(n)
    ]


def test_un_eleve_de_su_en_dao_n_est_pas_mal_range(
    session, etab, site_factory, personne_factory
):
    """Le cas vécu, à la lettre.

    Des élèves de SU suivent la DAO en 3PM au lycée. Il a fallu leur
    ouvrir un compte sur le KoXo de NDK, rangé dans le groupe « DAO ». La
    Concordance lisait NDK en premier, trouvait « DAO » là où la base de
    SU dit « 31 », et accusait dix-neuf élèves d'être mal rangés.

    Chacun se compare à la base de son propre établissement.
    """
    from backend.services.concordance import croiser

    ndk, an = etab
    su = site_factory("SU")
    lyceens = _eleves(personne_factory, ndk, "LY", "3_PM", 30)
    collegiens = _eleves(personne_factory, su, "CO", "31", 10)
    dao = personne_factory(
        type="eleve", site_id=su.id, nom="SCHOLAR", prenom="Axel",
        login="ascholar", classe="31",
    )

    r = croiser(
        session,
        _fichier(
            *[f"{p.badge};{p.nom};{p.prenom};3_PM" for p in lyceens],
            f"{dao.badge};SCHOLAR;Axel;31",
            *[f"{p.badge};{p.nom};{p.prenom};31" for p in collegiens],
        ),
        annee_id=an.id,
        koxo_par_base=[
            # Serveur NDK — déposé en premier, avec le compte DAO.
            [_LigneKoxo(str(p.badge), "3_PM") for p in lyceens]
            + [_LigneKoxo(str(dao.badge), "DAO")],
            # Serveur SU — le compte principal, dans sa classe.
            [_LigneKoxo(str(dao.badge), "31")]
            + [_LigneKoxo(str(p.badge), "31") for p in collegiens],
        ],
    )

    assert not [l for l in r.lignes if l.nom == "SCHOLAR"], (
        "le compte DAO de NDK n'est pas sa classe"
    )
    assert r.koxo_sites == ["NDK", "SU"]
    assert r.acces_secondaires == ["SCHOLAR Axel (SU) : base NDK, groupe DAO"]


def test_l_ordre_de_depot_ne_change_rien(
    session, etab, site_factory, personne_factory
):
    """SU d'abord ou NDK d'abord : la même réponse.

    Une Concordance dont le verdict dépend de l'ordre dans lequel on a
    choisi les fichiers ne vérifie rien.
    """
    from backend.services.concordance import croiser

    ndk, an = etab
    su = site_factory("SU")
    lyceen = personne_factory(
        type="eleve", site_id=ndk.id, nom="LY", prenom="X", login="ly", classe="3_PM",
    )
    dao = personne_factory(
        type="eleve", site_id=su.id, nom="SCHOLAR", prenom="Axel",
        login="ascholar", classe="31",
    )
    base_ndk = [_LigneKoxo(str(lyceen.badge), "3_PM"), _LigneKoxo(str(dao.badge), "DAO")]
    base_su = [_LigneKoxo(str(dao.badge), "31")]
    source = _fichier(f"{lyceen.badge};LY;X;3_PM", f"{dao.badge};SCHOLAR;Axel;31")

    un = croiser(session, source, annee_id=an.id, koxo_par_base=[base_ndk, base_su])
    deux = croiser(session, source, annee_id=an.id, koxo_par_base=[base_su, base_ndk])

    assert [l.nom for l in un.lignes] == [l.nom for l in deux.lignes] == []
    assert un.acces_secondaires == deux.acces_secondaires


def test_un_vrai_ecart_sur_la_base_de_son_site_reste_signale(
    session, etab, site_factory, personne_factory
):
    """Le correctif ne doit rien taire d'autre.

    Un élève de SU dont la base de SU dit une autre classe est en écart,
    DAO ou pas.
    """
    from backend.services.concordance import croiser

    ndk, an = etab
    su = site_factory("SU")
    lyceen = personne_factory(
        type="eleve", site_id=ndk.id, nom="LY", prenom="X", login="ly", classe="3_PM",
    )
    dao = personne_factory(
        type="eleve", site_id=su.id, nom="SCHOLAR", prenom="Axel",
        login="ascholar", classe="31",
    )
    r = croiser(
        session,
        _fichier(f"{lyceen.badge};LY;X;3_PM", f"{dao.badge};SCHOLAR;Axel;31"),
        annee_id=an.id,
        koxo_par_base=[
            [_LigneKoxo(str(lyceen.badge), "3_PM"), _LigneKoxo(str(dao.badge), "DAO")],
            [_LigneKoxo(str(dao.badge), "42")],  # SU se trompe de classe
        ],
    )
    ligne = next(l for l in r.lignes if l.nom == "SCHOLAR")
    assert ligne.genres == ["koxo"]
    assert ligne.koxo == "42", "c'est la base de SU qui parle, pas le groupe DAO"


def test_absent_de_la_base_de_son_site_meme_present_ailleurs(
    session, etab, site_factory, personne_factory
):
    """Un compte DAO ne remplace pas le compte de l'établissement.

    Sans compte sur le serveur de SU, un élève de SU ne se connecte pas au
    collège — même s'il se connecte très bien au lycée.
    """
    from backend.services.concordance import croiser

    ndk, an = etab
    su = site_factory("SU")
    lyceen = personne_factory(
        type="eleve", site_id=ndk.id, nom="LY", prenom="X", login="ly", classe="3_PM",
    )
    dao = personne_factory(
        type="eleve", site_id=su.id, nom="SCHOLAR", prenom="Axel",
        login="ascholar", classe="31",
    )
    autre = personne_factory(
        type="eleve", site_id=su.id, nom="AUTRE", prenom="Y", login="autre", classe="31",
    )
    r = croiser(
        session,
        _fichier(
            f"{lyceen.badge};LY;X;3_PM",
            f"{dao.badge};SCHOLAR;Axel;31",
            f"{autre.badge};AUTRE;Y;31",
        ),
        annee_id=an.id,
        koxo_par_base=[
            [_LigneKoxo(str(lyceen.badge), "3_PM"), _LigneKoxo(str(dao.badge), "DAO")],
            [_LigneKoxo(str(autre.badge), "31")],  # SCHOLAR absent de SU
        ],
    )
    ligne = next(l for l in r.lignes if l.nom == "SCHOLAR")
    assert ligne.genres == ["absent_koxo"]


def test_une_base_ne_sert_qu_un_etablissement(
    session, etab, site_factory, personne_factory
):
    """Beaucoup de DAO ne font pas du serveur de NDK un serveur de SU.

    Si la base de NDK passait pour couvrir SU, chaque élève de SU absent
    du serveur de NDK serait accusé d'absence — alors qu'on n'a simplement
    pas déposé la base de SU.
    """
    from backend.services.concordance import croiser

    ndk, an = etab
    su = site_factory("SU")
    lyceens = _eleves(personne_factory, ndk, "LY", "3_PM", 40)
    # Plus d'un vingtième du site dominant : l'ancien seuil cédait.
    daos = _eleves(personne_factory, su, "DAO", "31", 15)
    sans_dao = personne_factory(
        type="eleve", site_id=su.id, nom="SANSDAO", prenom="Z", login="sansdao", classe="31",
    )
    r = croiser(
        session,
        _fichier(
            *[f"{p.badge};{p.nom};{p.prenom};3_PM" for p in lyceens],
            *[f"{p.badge};{p.nom};{p.prenom};31" for p in daos],
            f"{sans_dao.badge};SANSDAO;Z;31",
        ),
        annee_id=an.id,
        koxo_par_base=[
            [_LigneKoxo(str(p.badge), "3_PM") for p in lyceens]
            + [_LigneKoxo(str(p.badge), "DAO") for p in daos],
        ],  # la base de SU n'a pas été déposée
    )
    assert r.koxo_sites == ["NDK"]
    assert r.lignes == [], "SU n'a pas été interrogé : personne n'y est accusé"
    assert len(r.acces_secondaires) == 15



# ---------------------------------------------------------------------------
# Le constat range aussi ceux qui sont d'accord
# ---------------------------------------------------------------------------


def test_un_croisement_range_les_accords_et_pas_seulement_les_ecarts(
    session, etab, site_factory, personne_factory
):
    """Le rapport ne montre que les écarts ; le constat doit tout ranger.

    Vécu : mille huit cents élèves croisés, vingt-trois verdicts rangés,
    dont vingt-et-un écarts. Seules les lignes en écart passaient au
    rangement — l'écran Cohérence en concluait que presque tout clochait,
    et la colonne « Cohérent » du référentiel ne passait jamais au vert.

    Ce test passe par la vraie Concordance, pas par un faux rapport : c'est
    le faux rapport, qui contenait tout le monde, qui avait masqué la faute.
    """
    from backend.services.coherence import enregistrer, verdicts_par_personne
    from backend.services.concordance import croiser

    ndk, an = etab
    daccord = [
        personne_factory(
            type="eleve", site_id=ndk.id, nom=f"OK{i}", prenom="X",
            login=f"ok{i}", classe="2_4",
        )
        for i in range(5)
    ]
    en_retard = personne_factory(
        type="eleve", site_id=ndk.id, nom="RETARD", prenom="Y",
        login="retard", classe="2_4",
    )

    r = croiser(
        session,
        _fichier(
            *[f"{p.badge};{p.nom};{p.prenom};2_4" for p in daccord],
            f"{en_retard.badge};RETARD;Y;2_4",
        ),
        annee_id=an.id,
        koxo_par_base=[
            [_LigneKoxo(str(p.badge), "2_4") for p in daccord]
            + [_LigneKoxo(str(en_retard.badge), "2_3")],
        ],
    )
    assert r.nb_accord == 5 and len(r.lignes) == 1

    enregistrer(session, r)
    verdicts = verdicts_par_personne(session)

    assert all(verdicts[p.id]["etat"] == "coherent" for p in daccord), (
        "un élève d'accord est un verdict « cohérent », pas une absence de verdict"
    )
    assert verdicts[en_retard.id]["etat"] == "ecarts"
    assert len(verdicts) == 6
