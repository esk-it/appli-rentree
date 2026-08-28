"""Tests des groupes Google (appartenances) et de l'OU d'archivage des sortants."""
from __future__ import annotations

import csv
import io
from datetime import date

import pytest


@pytest.fixture()
def snap_factory(session):
    from backend.models import Snapshot

    def _creer(personne_id, annee_id, **kwargs):
        defaults = {"nom": "MARTIN", "prenom": "Jean", "classe": "3B"}
        defaults.update(kwargs)
        s = Snapshot(personne_id=personne_id, annee_scolaire_id=annee_id, **defaults)
        session.add(s)
        session.commit()
        return s

    return _creer


@pytest.fixture()
def tc_factory(session):
    from backend.models import TableCorrespondance

    def _creer(site_id, code_court, groupe_google=None, groupe_profs_google=None):
        tc = TableCorrespondance(
            site_id=site_id,
            classe_charlemagne_long=f"CLASSE {code_court}",
            classe_code_court=code_court,
            groupe_google=groupe_google,
            groupe_profs_google=groupe_profs_google,
            ou_pre_rentree="/3. NDK/NDK2026",
            ou_definitive=f"/3. NDK/NDK2026/{code_court}",
        )
        session.add(tc)
        session.commit()
        return tc

    return _creer


def _lire(contenu: bytes) -> list[dict]:
    if contenu.startswith(b"\xef\xbb\xbf"):
        contenu = contenu[3:]
    return list(csv.DictReader(io.StringIO(contenu.decode("utf-8"))))


# ---------------------------------------------------------------------------
# Groupes Google — élèves
# ---------------------------------------------------------------------------


def test_groupes_format_4_colonnes(
    session, site_factory, annee_factory, personne_factory, snap_factory, tc_factory
):
    from backend.services.exports_google_groupes import (
        COLONNES_GROUPES,
        generer_csv_groupes_google,
    )

    site = site_factory("NDK")
    annee = annee_factory()
    tc_factory(site.id, "3B", groupe_google="3eme-b@lekreisker.fr")
    p = personne_factory(site_id=site.id, nom="DUPONT", prenom="Jean", login="jdupont")
    snap_factory(p.id, annee.id, classe="3B")

    contenu, _ = generer_csv_groupes_google(
        session=session, site_id=site.id, annee_id=annee.id
    )
    rows = _lire(contenu)

    assert list(rows[0].keys()) == COLONNES_GROUPES
    assert rows[0]["Group Email [Required]"] == "3eme-b@lekreisker.fr"
    assert rows[0]["Member Email"] == "jean.dupont@lekreisker.fr"
    assert rows[0]["Member Type"] == "USER"
    assert rows[0]["Member Role"] == "MEMBER"


def test_groupes_eleves_regroupes_par_classe(
    session, site_factory, annee_factory, personne_factory, snap_factory, tc_factory
):
    from backend.services.exports_google_groupes import generer_csv_groupes_google

    site = site_factory("NDK")
    annee = annee_factory()
    tc_factory(site.id, "3B", groupe_google="3eme-b@lekreisker.fr")
    tc_factory(site.id, "4A", groupe_google="4eme-a@lekreisker.fr")

    for i in range(2):
        p = personne_factory(site_id=site.id, login=f"b{i}")
        snap_factory(p.id, annee.id, classe="3B")
    p = personne_factory(site_id=site.id, login="a0")
    snap_factory(p.id, annee.id, classe="4A")

    contenu, r = generer_csv_groupes_google(
        session=session, site_id=site.id, annee_id=annee.id, inclure_profs=False
    )
    rows = _lire(contenu)

    assert r.nb_lignes_eleves == 3
    assert r.nb_groupes_classes == 2
    par_groupe = {}
    for row in rows:
        par_groupe.setdefault(row["Group Email [Required]"], []).append(row["Member Email"])
    assert len(par_groupe["3eme-b@lekreisker.fr"]) == 2
    assert len(par_groupe["4eme-a@lekreisker.fr"]) == 1


def test_groupes_classe_sans_adresse_est_signalee(
    session, site_factory, annee_factory, personne_factory, snap_factory, tc_factory
):
    """Une classe sans groupe_google configuré est listée, pas silencieuse."""
    from backend.services.exports_google_groupes import generer_csv_groupes_google

    site = site_factory("NDK")
    annee = annee_factory()
    tc_factory(site.id, "3B", groupe_google=None)  # pas d'adresse
    p = personne_factory(site_id=site.id, login="jdupont")
    snap_factory(p.id, annee.id, classe="3B")

    contenu, r = generer_csv_groupes_google(
        session=session, site_id=site.id, annee_id=annee.id, inclure_profs=False
    )

    assert r.nb_lignes == 0
    assert r.classes_sans_groupe == ["3B"]


# ---------------------------------------------------------------------------
# Groupes Google — profs
# ---------------------------------------------------------------------------


def test_groupes_profs_depuis_classes_prof_principal(
    session, site_factory, annee_factory, personne_factory, snap_factory, tc_factory
):
    from backend.services.exports_google_groupes import generer_csv_groupes_google

    site = site_factory("NDK")
    annee = annee_factory()
    tc_factory(site.id, "3B", groupe_profs_google="profs-3b@lekreisker.fr")
    tc_factory(site.id, "4A", groupe_profs_google="profs-4a@lekreisker.fr")

    prof = personne_factory(
        type="adulte", site_id=site.id, nom="BARS", prenom="Julien", login="jbars"
    )
    snap_factory(prof.id, annee.id, classes_prof_principal="3B;4A")

    contenu, r = generer_csv_groupes_google(
        session=session, site_id=site.id, annee_id=annee.id, inclure_eleves=False
    )
    rows = _lire(contenu)

    assert r.nb_lignes_profs == 2
    groupes = {row["Group Email [Required]"] for row in rows}
    assert groupes == {"profs-3b@lekreisker.fr", "profs-4a@lekreisker.fr"}
    assert all(row["Member Email"] == "julien.bars@lekreisker.fr" for row in rows)


def test_groupes_profs_pas_de_doublon(
    session, site_factory, annee_factory, personne_factory, snap_factory, tc_factory
):
    """Un prof listé deux fois pour la même classe n'apparaît qu'une fois."""
    from backend.services.exports_google_groupes import generer_csv_groupes_google

    site = site_factory("NDK")
    annee = annee_factory()
    tc_factory(site.id, "3B", groupe_profs_google="profs-3b@lekreisker.fr")

    prof = personne_factory(type="adulte", site_id=site.id, login="jbars")
    snap_factory(prof.id, annee.id, classes_prof_principal="3B;3B; 3B ")

    _, r = generer_csv_groupes_google(
        session=session, site_id=site.id, annee_id=annee.id, inclure_eleves=False
    )
    assert r.nb_lignes_profs == 1


def test_groupes_profs_vides_signales(
    session, site_factory, annee_factory, personne_factory, snap_factory, tc_factory
):
    """Un groupe profs configuré sans aucun enseignant est remonté."""
    from backend.services.exports_google_groupes import generer_csv_groupes_google

    site = site_factory("NDK")
    annee = annee_factory()
    tc_factory(site.id, "3B", groupe_profs_google="profs-3b@lekreisker.fr")
    tc_factory(site.id, "4A", groupe_profs_google="profs-4a@lekreisker.fr")

    prof = personne_factory(type="adulte", site_id=site.id, login="jbars")
    snap_factory(prof.id, annee.id, classes_prof_principal="3B")  # rien pour 4A

    _, r = generer_csv_groupes_google(
        session=session, site_id=site.id, annee_id=annee.id, inclure_eleves=False
    )
    assert r.groupes_profs_vides == ["profs-4a@lekreisker.fr"]


def test_groupes_les_deux_familles_ensemble(
    session, site_factory, annee_factory, personne_factory, snap_factory, tc_factory
):
    from backend.services.exports_google_groupes import generer_csv_groupes_google

    site = site_factory("NDK")
    annee = annee_factory()
    tc_factory(
        site.id, "3B",
        groupe_google="3eme-b@lekreisker.fr",
        groupe_profs_google="profs-3b@lekreisker.fr",
    )

    eleve = personne_factory(type="eleve", site_id=site.id, login="eleve1")
    snap_factory(eleve.id, annee.id, classe="3B")
    prof = personne_factory(type="adulte", site_id=site.id, login="prof1")
    snap_factory(prof.id, annee.id, classes_prof_principal="3B")

    _, r = generer_csv_groupes_google(session=session, site_id=site.id, annee_id=annee.id)

    assert r.nb_lignes_eleves == 1
    assert r.nb_lignes_profs == 1
    assert r.nb_lignes == 2


def test_groupes_refuse_les_deux_exclusions(session, site_factory, annee_factory):
    from backend.services.exports_google_groupes import generer_csv_groupes_google

    site = site_factory("NDK")
    annee = annee_factory()
    with pytest.raises(ValueError, match="au moins"):
        generer_csv_groupes_google(
            session=session, site_id=site.id, annee_id=annee.id,
            inclure_eleves=False, inclure_profs=False,
        )


def test_groupes_site_introuvable(session, annee_factory):
    from backend.services.exports_google_groupes import generer_csv_groupes_google

    annee = annee_factory()
    with pytest.raises(ValueError, match="Site introuvable"):
        generer_csv_groupes_google(session=session, site_id=99999, annee_id=annee.id)


# ---------------------------------------------------------------------------
# OU d'archivage des sortants
# ---------------------------------------------------------------------------


def test_ou_sortants_contient_lecheance(session):
    """L'échéance réelle figure dans le nom de l'OU, au jour près.

    Auparavant elle était arrondie au 31 décembre de l'année d'expiration,
    ce qui étirait la conservation bien au-delà des 18 mois de la règle :
    un départ d'août tombait au 31 décembre suivant, soit 29 mois.
    """
    from backend.services.exports_google import calculer_ou_sortants

    ou = calculer_ou_sortants(session, aujourd_hui=date(2026, 1, 1))
    assert ou == "/7. Sortis/Comptes à supprimer au 01-07-2027"


def test_ou_sortants_propre_au_site(session, site_factory):
    """NDE range ses partants dans son OU à elle, sans date.

    Cet usage précède le programme ; lui imposer la convention datée
    obligerait à déplacer l'existant sans rien y gagner.
    """
    from backend.services.exports_google import calculer_ou_sortants

    nde = site_factory("NDE")
    nde.ou_sortants = "/2. NDE/Sortie"
    session.commit()

    assert calculer_ou_sortants(session, site=nde) == "/2. NDE/Sortie"
    # Un site sans convention propre garde le dossier daté
    ndk = site_factory("NDK")
    assert calculer_ou_sortants(session, site=ndk).startswith("/7. Sortis/Comptes")


def test_ou_sortants_respecte_le_parametre(session):
    from backend.services.configuration import set_param
    from backend.services.exports_google import calculer_ou_sortants

    set_param(session, "google.ou_sortants", "/9. Archives")
    session.commit()

    ou = calculer_ou_sortants(session, aujourd_hui=date(2026, 1, 1))
    assert ou.startswith("/9. Archives/")


def test_export_anciens_utilise_lou_de_sortie(
    session, site_factory, annee_factory, personne_factory, snap_factory, tc_factory
):
    """Les sortants partent tous dans l'OU d'archivage, pas dans leur OU de classe."""
    from backend.services.exports_google import generer_csv_google

    site = site_factory("NDK")
    an_prec = annee_factory("2024-2025")
    an_cour = annee_factory("2025-2026")
    tc_factory(site.id, "TALE")

    p = personne_factory(site_id=site.id, nom="SORT", login="sort")
    snap_factory(p.id, an_prec.id, classe="TALE")  # absent de l'année cible

    contenu, _ = generer_csv_google(
        session=session, site_id=site.id, type_personne="eleve",
        categorie="anciens", annee_cible_id=an_cour.id, annee_source_id=an_prec.id,
    )
    rows = _lire(contenu)

    assert len(rows) == 1
    assert rows[0]["Org Unit Path [Required]"].startswith("/7. Sortis/")


def test_export_anciens_adultes_aussi_archives(
    session, site_factory, annee_factory, personne_factory, snap_factory
):
    """Un adulte sortant ne reste pas à la racine du site."""
    from backend.services.exports_google import generer_csv_google

    site = site_factory("NDK")
    an_prec = annee_factory("2024-2025")
    an_cour = annee_factory("2025-2026")

    p = personne_factory(type="adulte", site_id=site.id, login="prof1")
    snap_factory(p.id, an_prec.id, poste_occupe="ENSEIGNEMENT")

    contenu, _ = generer_csv_google(
        session=session, site_id=site.id, type_personne="adulte",
        categorie="anciens", annee_cible_id=an_cour.id, annee_source_id=an_prec.id,
    )
    rows = _lire(contenu)

    assert rows[0]["Org Unit Path [Required]"].startswith("/7. Sortis/")


def test_export_tous_nest_pas_affecte(
    session, site_factory, annee_factory, personne_factory, snap_factory, tc_factory
):
    """La catégorie `tous` continue d'utiliser l'OU définitive de la classe."""
    from backend.services.exports_google import generer_csv_google

    site = site_factory("NDK")
    annee = annee_factory()
    tc_factory(site.id, "3B")
    p = personne_factory(site_id=site.id, login="test1")
    snap_factory(p.id, annee.id, classe="3B")

    contenu, _ = generer_csv_google(
        session=session, site_id=site.id, type_personne="eleve",
        categorie="tous", annee_cible_id=annee.id,
    )
    rows = _lire(contenu)
    assert rows[0]["Org Unit Path [Required]"] == "/3. NDK/NDK2026/3B"



def test_une_classe_sans_adresse_de_groupe_est_nommee(
    session, site_factory, annee_factory, personne_factory, snap_factory,
    tc_factory,
):
    """Ses élèves n'entreront dans aucune liste, et rien ne le dit ailleurs.

    Un groupe déclaré mais absent de Google se voit — les ajouts échouent.
    Une classe qui ne déclare aucun groupe ne se voit nulle part : le calcul
    la saute en silence. Deux classes de NDK étaient dans ce cas, soit
    soixante et un élèves.
    """
    from backend.services.groupes_google import calculer_diff_groupes

    site = site_factory("NDK")
    annee = annee_factory("2026-2027")
    tc_factory(site.id, "1_ST2S1", groupe_google=None)
    tc_factory(site.id, "1_STL", groupe_google="1ere-stl@lekreisker.fr")

    for classe in ("1_ST2S1", "1_STL"):
        p = personne_factory(site_id=site.id, login=f"eleve{classe}")
        snap_factory(p.id, annee.id, classe=classe)

    r = calculer_diff_groupes(
        session, {"1ere-stl@lekreisker.fr": []}, annee_id=annee.id,
    )
    assert "1_ST2S1" in r.classes_sans_groupe
    assert "1_STL" not in r.classes_sans_groupe


def test_un_site_sans_eleve_charge_ne_perd_pas_ses_membres(
    session, site_factory, annee_factory, personne_factory, snap_factory,
    tc_factory,
):
    """L'écran l'annonçait déjà ; rien ne le faisait.

    NDE n'était pas encore ingéré au moment de préparer NDK et SU. Ses
    groupes montraient des sortants, et la synchronisation les aurait
    retirés — sur la foi d'un export Charlemagne pas encore lu. Un site
    vide n'est pas un site qui s'est vidé.
    """
    from backend.services.groupes_google import calculer_diff_groupes

    ndk = site_factory("NDK")
    nde = site_factory("NDE")
    annee = annee_factory("2026-2027")
    tc_factory(ndk.id, "6A", groupe_google="6eme-a@lekreisker.fr")
    tc_factory(nde.id, "6V", groupe_google="6eme-verte@lekreisker.fr")

    # NDK est chargé, NDE ne l'est pas.
    p = personne_factory(site_id=ndk.id, login="present",
                         email_constate="present@lekreisker.fr")
    snap_factory(p.id, annee.id, classe="6A")
    # Une élève de NDE, connue du référentiel mais sans photographie 2026-2027.
    personne_factory(site_id=nde.id, login="nde1",
                     email_constate="eleve.nde@lekreisker.fr")

    r = calculer_diff_groupes(session, {
        "6eme-a@lekreisker.fr": [],
        "6eme-verte@lekreisker.fr": ["eleve.nde@lekreisker.fr"],
    }, annee_id=annee.id)

    assert r.sites_sans_eleve == ["NDE"]
    nde_diff = next(d for d in r.diffs if d.site == "NDE")
    assert nde_diff.a_retirer == [], "aucun retrait sur un site non chargé"
    assert nde_diff.retraits_suspendus == ["eleve.nde@lekreisker.fr"]
    assert any("suspendus" in a for a in r.avertissements)


def test_un_site_charge_retire_normalement(
    session, site_factory, annee_factory, personne_factory, snap_factory,
    tc_factory,
):
    """La suspension ne doit valoir que pour un site entièrement absent."""
    from backend.services.groupes_google import calculer_diff_groupes

    ndk = site_factory("NDK")
    annee = annee_factory("2026-2027")
    tc_factory(ndk.id, "6A", groupe_google="6eme-a@lekreisker.fr")

    reste = personne_factory(site_id=ndk.id, login="reste",
                             email_constate="reste@lekreisker.fr")
    snap_factory(reste.id, annee.id, classe="6A")
    personne_factory(site_id=ndk.id, login="parti",
                     email_constate="parti@lekreisker.fr")

    r = calculer_diff_groupes(session, {
        "6eme-a@lekreisker.fr": ["reste@lekreisker.fr", "parti@lekreisker.fr"],
    }, annee_id=annee.id)

    assert r.sites_sans_eleve == []
    d = r.diffs[0]
    assert d.a_retirer == ["parti@lekreisker.fr"]
    assert d.retraits_suspendus == []
