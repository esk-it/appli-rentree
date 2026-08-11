"""Tests des exports Google Workspace (bulk-import Admin, 40 colonnes)."""
from __future__ import annotations

import csv
import io

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
    """Crée une TableCorrespondance pour lier classe → OU."""
    from backend.models import TableCorrespondance

    def _creer(site_id, code_court, ou_pre_rentree=None, ou_definitive=None):
        tc = TableCorrespondance(
            site_id=site_id,
            classe_charlemagne_long=f"CLASSE {code_court}",
            classe_code_court=code_court,
            ou_pre_rentree=ou_pre_rentree or f"/3. NDK/NDK2026",
            ou_definitive=ou_definitive or f"/3. NDK/NDK2026/{code_court}",
        )
        session.add(tc)
        session.commit()
        return tc

    return _creer


def _lire_csv_google(contenu: bytes) -> list[dict]:
    """Décode un CSV Google (UTF-8 avec BOM)."""
    # Retire le BOM s'il existe
    if contenu.startswith(b"\xef\xbb\xbf"):
        contenu = contenu[3:]
    texte = contenu.decode("utf-8")
    return list(csv.DictReader(io.StringIO(texte)))


# ---------------------------------------------------------------------------
# Format
# ---------------------------------------------------------------------------


def test_export_google_a_40_colonnes_officielles(
    session, site_factory, annee_factory, personne_factory, snap_factory, tc_factory
):
    from backend.services.exports_google import COLONNES_GOOGLE, generer_csv_google

    site = site_factory("NDK")
    annee = annee_factory()
    tc_factory(site.id, "3B")
    p = personne_factory(site_id=site.id, nom="DUPONT", prenom="Jean", login="jdupont")
    snap_factory(p.id, annee.id, classe="3B")

    contenu, _ = generer_csv_google(
        session=session, site_id=site.id, type_personne="eleve",
        categorie="tous", annee_cible_id=annee.id,
    )
    rows = _lire_csv_google(contenu)

    assert len(COLONNES_GOOGLE) == 40
    assert list(rows[0].keys()) == COLONNES_GOOGLE


def test_export_google_bom_utf8_present(session, site_factory, annee_factory, personne_factory, snap_factory):
    """Google Admin exige le BOM UTF-8 pour reconnaître l'encodage."""
    from backend.services.exports_google import generer_csv_google

    site = site_factory("NDK")
    annee = annee_factory()
    p = personne_factory(site_id=site.id, login="test1")
    snap_factory(p.id, annee.id)

    contenu, _ = generer_csv_google(
        session=session, site_id=site.id, type_personne="eleve",
        categorie="tous", annee_cible_id=annee.id,
    )
    assert contenu.startswith(b"\xef\xbb\xbf")


def test_export_google_password_toujours_vide(
    session, site_factory, annee_factory, personne_factory, snap_factory, tc_factory
):
    """Le mot de passe n'est jamais rempli à ce lot — sera injecté au Lot 8b
    via la boucle de retour KoXo, en mémoire uniquement."""
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
    for r in _lire_csv_google(contenu):
        assert r["Password [Required]"] == ""


def test_export_google_email_utilise_domaine_du_site(
    session, site_factory, annee_factory, personne_factory, snap_factory, tc_factory
):
    from backend.services.exports_google import generer_csv_google

    site = site_factory("NDK")  # lekreisker.fr
    annee = annee_factory()
    tc_factory(site.id, "3B")
    p = personne_factory(site_id=site.id, login="jdupont")
    snap_factory(p.id, annee.id, classe="3B")

    contenu, _ = generer_csv_google(
        session=session, site_id=site.id, type_personne="eleve",
        categorie="tous", annee_cible_id=annee.id,
    )
    r = _lire_csv_google(contenu)[0]
    assert r["Email Address [Required]"] == "jdupont@lekreisker.fr"


def test_export_google_employee_id_est_id_charlemagne(
    session, site_factory, annee_factory, personne_factory, snap_factory, tc_factory
):
    """Employee ID = clé stable pour rapprochement bidirectionnel plus tard."""
    from backend.services.exports_google import generer_csv_google

    site = site_factory("NDK")
    annee = annee_factory()
    tc_factory(site.id, "3B")
    p = personne_factory(site_id=site.id, id_charlemagne=5824, login="test1")
    snap_factory(p.id, annee.id, classe="3B")

    contenu, _ = generer_csv_google(
        session=session, site_id=site.id, type_personne="eleve",
        categorie="tous", annee_cible_id=annee.id,
    )
    assert _lire_csv_google(contenu)[0]["Employee ID"] == "5824"


# ---------------------------------------------------------------------------
# OU (Org Unit Path) résolue via TableCorrespondance
# ---------------------------------------------------------------------------


def test_ou_tous_utilise_ou_definitive(
    session, site_factory, annee_factory, personne_factory, snap_factory, tc_factory
):
    from backend.services.exports_google import generer_csv_google

    site = site_factory("NDK")
    annee = annee_factory()
    tc_factory(site.id, "3B", ou_pre_rentree="/3. NDK/NDK2026",
               ou_definitive="/3. NDK/NDK2026/3B")
    p = personne_factory(site_id=site.id, login="test1")
    snap_factory(p.id, annee.id, classe="3B")

    contenu, _ = generer_csv_google(
        session=session, site_id=site.id, type_personne="eleve",
        categorie="tous", annee_cible_id=annee.id,
    )
    assert _lire_csv_google(contenu)[0]["Org Unit Path [Required]"] == "/3. NDK/NDK2026/3B"


def test_ou_nouveaux_utilise_ou_pre_rentree(
    session, site_factory, annee_factory, personne_factory, snap_factory, tc_factory
):
    """Les nouveaux comptes partent en OU pré-rentrée le temps de la validation."""
    from backend.services.exports_google import generer_csv_google

    site = site_factory("NDK")
    an_prec = annee_factory("2024-2025")
    an_cour = annee_factory("2025-2026")
    tc_factory(site.id, "6A", ou_pre_rentree="/3. NDK/NDK2026",
               ou_definitive="/3. NDK/NDK2026/6A")

    p_nouveau = personne_factory(site_id=site.id, login="neuf")
    snap_factory(p_nouveau.id, an_cour.id, classe="6A")

    contenu, _ = generer_csv_google(
        session=session, site_id=site.id, type_personne="eleve",
        categorie="nouveaux", annee_cible_id=an_cour.id, annee_source_id=an_prec.id,
    )
    r = _lire_csv_google(contenu)[0]
    assert r["Org Unit Path [Required]"] == "/3. NDK/NDK2026"
    assert r["Change Password at Next Sign-In"] == "True"


def test_ou_adultes_utilise_racine_site(
    session, site_factory, annee_factory, personne_factory, snap_factory
):
    from backend.services.exports_google import generer_csv_google

    site = site_factory("NDK")  # numero_ordre=3
    annee = annee_factory()
    p = personne_factory(type="adulte", site_id=site.id, login="prof1")
    snap_factory(p.id, annee.id, poste_occupe="ENSEIGNEMENT")

    contenu, _ = generer_csv_google(
        session=session, site_id=site.id, type_personne="adulte",
        categorie="tous", annee_cible_id=annee.id,
    )
    assert _lire_csv_google(contenu)[0]["Org Unit Path [Required]"] == "/3. NDK"


def test_ou_absente_signalee_dans_rapport(
    session, site_factory, annee_factory, personne_factory, snap_factory
):
    """Classe absente de TableCorrespondance → OU vide + comptée dans nb_sans_ou."""
    from backend.services.exports_google import generer_csv_google

    site = site_factory("NDK")
    annee = annee_factory()
    p = personne_factory(site_id=site.id, login="test1")
    snap_factory(p.id, annee.id, classe="XX_INCONNUE")  # pas de TableCorrespondance

    contenu, rapport = generer_csv_google(
        session=session, site_id=site.id, type_personne="eleve",
        categorie="tous", annee_cible_id=annee.id,
    )
    assert rapport.nb_lignes == 1
    assert rapport.nb_sans_ou == 1
    assert _lire_csv_google(contenu)[0]["Org Unit Path [Required]"] == ""


# ---------------------------------------------------------------------------
# Employee Type
# ---------------------------------------------------------------------------


def test_employee_type_student_pour_eleve(
    session, site_factory, annee_factory, personne_factory, snap_factory, tc_factory
):
    from backend.services.exports_google import generer_csv_google

    site = site_factory("NDK")
    annee = annee_factory()
    tc_factory(site.id, "3B")
    p = personne_factory(type="eleve", site_id=site.id, login="e1")
    snap_factory(p.id, annee.id, classe="3B")

    contenu, _ = generer_csv_google(
        session=session, site_id=site.id, type_personne="eleve",
        categorie="tous", annee_cible_id=annee.id,
    )
    assert _lire_csv_google(contenu)[0]["Employee Type"] == "Student"


def test_employee_type_staff_pour_adulte(
    session, site_factory, annee_factory, personne_factory, snap_factory
):
    from backend.services.exports_google import generer_csv_google

    site = site_factory("NDK")
    annee = annee_factory()
    p = personne_factory(type="adulte", site_id=site.id, login="a1")
    snap_factory(p.id, annee.id, poste_occupe="ENSEIGNEMENT")

    contenu, _ = generer_csv_google(
        session=session, site_id=site.id, type_personne="adulte",
        categorie="tous", annee_cible_id=annee.id,
    )
    assert _lire_csv_google(contenu)[0]["Employee Type"] == "Staff"


# ---------------------------------------------------------------------------
# Validation params (mêmes que KoXo)
# ---------------------------------------------------------------------------


def test_google_nouveaux_sans_annee_source(session, site_factory, annee_factory):
    from backend.services.exports_google import generer_csv_google

    site = site_factory("NDK")
    annee = annee_factory()
    with pytest.raises(ValueError, match="annee_source_id"):
        generer_csv_google(session=session, site_id=site.id, type_personne="eleve",
                           categorie="nouveaux", annee_cible_id=annee.id)


def test_google_categorie_invalide(session, site_factory, annee_factory):
    from backend.services.exports_google import generer_csv_google

    site = site_factory("NDK")
    annee = annee_factory()
    with pytest.raises(ValueError, match="categorie"):
        generer_csv_google(session=session, site_id=site.id, type_personne="eleve",
                           categorie="autre", annee_cible_id=annee.id)


def test_google_nom_fichier_suggere(session, site_factory, annee_factory):
    from backend.services.exports_google import generer_csv_google

    site = site_factory("NDK")
    annee = annee_factory()
    _, rapport = generer_csv_google(
        session=session, site_id=site.id, type_personne="eleve",
        categorie="nouveaux", annee_cible_id=annee.id, annee_source_id=annee.id,
    )
    assert rapport.nom_fichier_suggere == "Google_NDK_eleves_nouveaux.csv"
