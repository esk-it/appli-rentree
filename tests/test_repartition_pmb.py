"""Répartir l'export PMB de Charlemagne entre les instances PMB.

Le fichier de Charlemagne porte les trois sites en vrac ; PMB a une
instance par établissement. Importé entier dans celle du lycée, il y fait
entrer les classes du collège — c'est arrivé, et la documentaliste a vu
ses effectifs doubler.
"""
from __future__ import annotations

import pytest

ENTETE = (
    "Num Badge;Nom;Prénom;Adresse 1;Adresse 2;CP;Ville;"
    "Tél. domicile (avec LR);Année de naissance;Code classe;Sexe;Email;Prof. Princ."
)


def _ligne(badge, nom, prenom, classe, **kw):
    return ";".join([
        str(badge), nom, prenom,
        kw.get("adresse", "1 rue du Test"), "", "29250", "ST POL DE LEON", "",
        kw.get("naissance", "2010"), classe, kw.get("sexe", "F"),
        kw.get("email", ""), kw.get("pp", "Mme TEST Anne"),
    ])


def _fichier(*lignes, entete=ENTETE, bom=True, encodage="utf-8"):
    texte = "\r\n".join([entete, *lignes]) + "\r\n"
    brut = texte.encode(encodage)
    return (b"\xef\xbb\xbf" + brut) if bom and encodage == "utf-8" else brut


@pytest.fixture()
def tc_factory(session):
    from backend.models import TableCorrespondance

    def _creer(site_id, code):
        t = TableCorrespondance(
            site_id=site_id,
            classe_charlemagne_long=f"CLASSE {code}",
            classe_code_court=code,
            ou_pre_rentree="/attente",
            ou_definitive=f"/{code}",
            groupe_google=f"{code.lower()}@lekreisker.fr",
        )
        session.add(t)
        session.commit()
        return t

    return _creer


@pytest.fixture()
def deux_instances(session, site_factory, tc_factory):
    """Un lycée et un collège, chacun avec deux classes dans la table."""
    ndk = site_factory("NDK")
    su = site_factory("SU")
    tc_factory(ndk.id, "2_1")
    tc_factory(ndk.id, "T_STMG2")
    tc_factory(su.id, "35")
    tc_factory(su.id, "61")
    return ndk, su


# ---------------------------------------------------------------------------
# Le partage
# ---------------------------------------------------------------------------


def test_chaque_classe_part_dans_l_instance_de_son_site(session, deux_instances):
    """C'est le seul savoir que Charlemagne n'a pas : qui héberge « 35 »."""
    from backend.services.repartition_pmb import repartir_export_pmb

    contenu = _fichier(
        _ligne(11, "DUPONT", "Alice", "2_1"),
        _ligne(22, "MARTIN", "Bob", "35"),
        _ligne(33, "DURAND", "Chloé", "T_STMG2"),
    )
    r = repartir_export_pmb(session, contenu, annee_libelle="2026-2027")

    par_site = {p.site_nom: p for p in r.paquets}
    assert par_site["NDK"].nb_eleves == 2
    assert par_site["SU"].nb_eleves == 1
    assert par_site["NDK"].classes == ["2_1", "T_STMG2"]
    assert par_site["NDK"].nom_fichier == "PMB_NDK_2026-2027.csv"


def test_rien_ne_se_perd_entre_le_fichier_lu_et_les_fichiers_rendus(
    session, deux_instances
):
    """La somme des fichiers vaut l'entrée, aux écartées près — c'est ce qui
    rend le résultat vérifiable d'un coup d'œil."""
    from backend.services.repartition_pmb import repartir_export_pmb

    contenu = _fichier(
        _ligne(11, "DUPONT", "Alice", "2_1"),
        _ligne(22, "MARTIN", "Bob", "35"),
        _ligne(33, "SANS", "Classe", ""),
    )
    r = repartir_export_pmb(session, contenu, annee_libelle="2026-2027")
    assert r.nb_lignes_lues == 3
    assert r.nb_reparties + len(r.ecartees) == r.nb_lignes_lues


def test_une_classe_hors_table_est_ecartee_et_nommee(session, deux_instances):
    """Sans cette liste, l'élève disparaîtrait sans bruit."""
    from backend.services.repartition_pmb import repartir_export_pmb

    contenu = _fichier(_ligne(89040, "DENIEL", "Enzo", ""))
    r = repartir_export_pmb(session, contenu, annee_libelle="2026-2027")

    assert r.paquets == []
    assert not r.tout_est_place
    (e,) = r.ecartees
    assert (e.badge, e.nom, e.prenom) == ("89040", "DENIEL", "Enzo")
    assert "aucune classe" in e.motif


def test_le_motif_nomme_la_classe_inconnue(session, deux_instances):
    from backend.services.repartition_pmb import repartir_export_pmb

    r = repartir_export_pmb(
        session, _fichier(_ligne(44, "X", "Y", "9_Z")), annee_libelle="2026-2027"
    )
    assert "9_Z" in r.ecartees[0].motif


# ---------------------------------------------------------------------------
# Ce que la répartition ne touche pas
# ---------------------------------------------------------------------------


def test_les_treize_colonnes_ressortent_intactes(session, deux_instances):
    """Le programme ne sait pas produire ces colonnes ; il ne doit surtout
    pas les réécrire."""
    import csv
    import io

    from backend.services.repartition_pmb import repartir_export_pmb

    ligne = _ligne(
        11, "VANDE SOMPELE", "Cécile", "2_1",
        adresse="7, lieu-dit Coz-Castel", email="c.v@lekreisker.fr",
        pp="Mme MARTINEZ RUIZ Raquel, M. RAMEAU François-Xavier",
    )
    r = repartir_export_pmb(session, _fichier(ligne), annee_libelle="2026-2027")

    sortie = r.paquets[0].contenu_csv.decode("utf-8-sig")
    lues = list(csv.reader(io.StringIO(sortie), delimiter=";"))
    assert lues[0] == ENTETE.split(";")
    assert lues[1] == ligne.split(";")


def test_le_fichier_rendu_a_le_bom_et_des_crlf(session, deux_instances):
    """C'est ce que Charlemagne produit et ce que PMB avale sans broncher."""
    from backend.services.repartition_pmb import repartir_export_pmb

    r = repartir_export_pmb(
        session, _fichier(_ligne(11, "A", "B", "2_1")), annee_libelle="2026-2027"
    )
    brut = r.paquets[0].contenu_csv
    assert brut.startswith(b"\xef\xbb\xbf")
    assert brut.endswith(b"\r\n")
    assert b"\n" not in brut.replace(b"\r\n", b"")


def test_l_ordre_des_lignes_est_celui_du_fichier_d_origine(session, deux_instances):
    from backend.services.repartition_pmb import repartir_export_pmb

    contenu = _fichier(
        _ligne(3, "TROIS", "C", "2_1"),
        _ligne(1, "UN", "A", "2_1"),
        _ligne(2, "DEUX", "B", "2_1"),
    )
    r = repartir_export_pmb(session, contenu, annee_libelle="2026-2027")
    sortie = r.paquets[0].contenu_csv.decode("utf-8-sig")
    assert [l.split(";")[1] for l in sortie.strip().split("\r\n")[1:]] == [
        "TROIS", "UN", "DEUX",
    ]


def test_un_export_windows_1252_est_lu_aussi(session, deux_instances):
    """Charlemagne écrit tantôt en UTF-8, tantôt dans l'encodage Windows."""
    from backend.services.repartition_pmb import repartir_export_pmb

    contenu = _fichier(
        _ligne(11, "LE GOFF", "Maëlys", "2_1"), encodage="cp1252", bom=False
    )
    r = repartir_export_pmb(session, contenu, annee_libelle="2026-2027")
    assert "Maëlys" in r.paquets[0].contenu_csv.decode("utf-8-sig")


# ---------------------------------------------------------------------------
# Ce que le référentiel apporte en plus
# ---------------------------------------------------------------------------


def test_un_eleve_inconnu_du_referentiel_est_signale_sans_etre_ecarte(
    session, deux_instances, personne_factory
):
    """Il ira bien dans PMB — mais il n'a ni compte Google ni compte KoXo,
    et aucun autre écran ne le montre : le bilan ne voit que ce qui a été
    ingéré."""
    from backend.services.repartition_pmb import repartir_export_pmb

    ndk, _ = deux_instances
    connu = personne_factory(type="eleve", site_id=ndk.id, nom="CONNU", prenom="Anna")

    contenu = _fichier(
        _ligne(connu.badge, "CONNU", "Anna", "2_1"),
        _ligne(99760, "BOIAN", "Rébecca", "35"),
    )
    r = repartir_export_pmb(session, contenu, annee_libelle="2026-2027")

    assert r.nb_reparties == 2, "l'inconnu part quand même dans son instance"
    (i,) = r.inconnus_du_referentiel
    assert (i.badge, i.nom) == ("99760", "BOIAN")


def test_une_ligne_ecartee_n_est_pas_comptee_comme_inconnue(
    session, deux_instances
):
    """Elle n'est dans aucun fichier : la signaler deux fois ferait croire
    à deux problèmes là où il n'y en a qu'un."""
    from backend.services.repartition_pmb import repartir_export_pmb

    r = repartir_export_pmb(
        session, _fichier(_ligne(99999, "X", "Y", "")), annee_libelle="2026-2027"
    )
    assert len(r.ecartees) == 1
    assert r.inconnus_du_referentiel == []


# ---------------------------------------------------------------------------
# Les refus
# ---------------------------------------------------------------------------


def test_un_fichier_qui_n_est_pas_l_export_pmb_est_refuse(session, deux_instances):
    """Mieux vaut refuser que rendre deux fichiers vides : c'est la leçon
    des étiquettes NDE."""
    from backend.services.repartition_pmb import (
        RepartitionImpossible,
        repartir_export_pmb,
    )

    with pytest.raises(RepartitionImpossible) as e:
        repartir_export_pmb(
            session,
            _fichier(_ligne(11, "A", "B", "2_1"), entete="login;nom;prenom;classe"),
            annee_libelle="2026-2027",
        )
    assert "Num Badge" in str(e.value) and "Code classe" in str(e.value)


def test_un_fichier_vide_est_refuse(session, deux_instances):
    from backend.services.repartition_pmb import (
        RepartitionImpossible,
        repartir_export_pmb,
    )

    with pytest.raises(RepartitionImpossible):
        repartir_export_pmb(session, b"", annee_libelle="2026-2027")


def test_une_ligne_au_mauvais_nombre_de_colonnes_est_ecartee(
    session, deux_instances
):
    from backend.services.repartition_pmb import repartir_export_pmb

    contenu = _fichier(
        _ligne(11, "BON", "Format", "2_1"),
        "12;TRONQUE;Ligne;2_1",
    )
    r = repartir_export_pmb(session, contenu, annee_libelle="2026-2027")
    assert r.nb_reparties == 1
    assert "4 colonnes au lieu de 13" in r.ecartees[0].motif
