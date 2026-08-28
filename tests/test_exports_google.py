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
    p = personne_factory(site_id=site.id, nom="DUPONT", prenom="Jean", login="jdupont")
    snap_factory(p.id, annee.id, classe="3B")

    contenu, _ = generer_csv_google(
        session=session, site_id=site.id, type_personne="eleve",
        categorie="tous", annee_cible_id=annee.id,
    )
    r = _lire_csv_google(contenu)[0]
    # `prenom.nom`, pas `login@` : le login `jdupont` ne fait pas l'adresse
    assert r["Email Address [Required]"] == "jean.dupont@lekreisker.fr"


def test_export_google_reprend_l_adresse_constatee(
    session, site_factory, annee_factory, personne_factory, snap_factory, tc_factory
):
    """Un compte existant garde son adresse, même hors convention.

    Sinon l'export créerait un doublon à côté du compte déjà en service.
    """
    from backend.services.exports_google import generer_csv_google

    site = site_factory("NDK")
    annee = annee_factory()
    tc_factory(site.id, "3B")
    p = personne_factory(
        site_id=site.id,
        nom="HENOCQ KERAUTRET",
        prenom="Sarah",
        login="shenocqker",
        email_constate="sarah.henocq@lekreisker.fr",
    )
    snap_factory(p.id, annee.id, classe="3B")

    contenu, _ = generer_csv_google(
        session=session, site_id=site.id, type_personne="eleve",
        categorie="tous", annee_cible_id=annee.id,
    )
    r = _lire_csv_google(contenu)[0]
    assert r["Email Address [Required]"] == "sarah.henocq@lekreisker.fr"


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
    # KoXo est l'autorité du mot de passe : le faire personnaliser à la
    # première connexion le ferait diverger de l'annuaire et de la fiche
    # imprimée, sans moyen de les raccorder ensuite.
    assert r["Change Password at Next Sign-In"] == "False"


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


def test_export_nouveaux_previent_que_le_mot_de_passe_manque(
    session, site_factory, annee_factory, personne_factory
):
    """Un CSV de créations sans mot de passe est refusé par Google.

    Le fichier paraît complet : sans avertissement, l'échec ne se découvre
    qu'à l'import, une fois le fichier transmis.
    """
    from backend.models import Snapshot, TableCorrespondance
    from backend.services.exports_google import generer_csv_google

    site = site_factory("NDK")
    source = annee_factory("2025-2026")
    cible = annee_factory("2026-2027")
    session.add(
        TableCorrespondance(
            site_id=site.id, classe_charlemagne_long="SECONDE 1",
            classe_code_court="2_1", ou_pre_rentree="/3. NDK/NDK2027",
            ou_definitive="/3. NDK/NDK2027/2_1",
        )
    )
    p = personne_factory(nom="DUPONT", prenom="Jean", login="jdupont", site_id=site.id)
    session.add(Snapshot(personne_id=p.id, annee_scolaire_id=cible.id,
                         nom="DUPONT", prenom="Jean", classe="2_1"))
    session.commit()

    _, r = generer_csv_google(
        session=session, site_id=site.id, type_personne="eleve",
        categorie="nouveaux", annee_cible_id=cible.id, annee_source_id=source.id,
    )

    assert r.nb_lignes == 1
    assert any("Password" in a and "KoXo" in a for a in r.avertissements)


def test_export_tous_ne_previent_pas_du_mot_de_passe(
    session, site_factory, annee_factory, personne_factory
):
    """L'avertissement ne vaut que pour des créations."""
    from backend.models import Snapshot, TableCorrespondance
    from backend.services.exports_google import generer_csv_google

    site = site_factory("NDK")
    cible = annee_factory("2026-2027")
    session.add(
        TableCorrespondance(
            site_id=site.id, classe_charlemagne_long="SECONDE 1",
            classe_code_court="2_1", ou_pre_rentree="/3. NDK/NDK2027",
            ou_definitive="/3. NDK/NDK2027/2_1",
        )
    )
    p = personne_factory(nom="DUPONT", prenom="Jean", login="jdupont", site_id=site.id)
    session.add(Snapshot(personne_id=p.id, annee_scolaire_id=cible.id,
                         nom="DUPONT", prenom="Jean", classe="2_1"))
    session.commit()

    _, r = generer_csv_google(
        session=session, site_id=site.id, type_personne="eleve",
        categorie="tous", annee_cible_id=cible.id,
    )

    assert not any("Password" in a for a in r.avertissements)


def test_aucun_export_ne_force_le_changement_de_mot_de_passe(
    session, site_factory, annee_factory, personne_factory, snap_factory,
    tc_factory,
):
    """Sur les trois catégories, et pour les deux populations.

    Le mot de passe vient de KoXo, qui l'imprime sur la fiche remise à
    l'élève. Google n'en reçoit qu'une copie ; le faire changer à la
    première connexion romprait l'unique mot de passe que l'élève connaît.
    """
    from backend.services.exports_google import generer_csv_google

    site = site_factory("NDK")
    an_prec = annee_factory("2025-2026")
    an_cour = annee_factory("2026-2027")
    tc_factory(site.id, "6A", ou_pre_rentree="/3. NDK/NDK2027",
               ou_definitive="/3. NDK/NDK2027/6A")

    ancien = personne_factory(site_id=site.id, login="ancien")
    snap_factory(ancien.id, an_prec.id, classe="6A")
    snap_factory(ancien.id, an_cour.id, classe="6A")
    neuf = personne_factory(site_id=site.id, login="neuf")
    snap_factory(neuf.id, an_cour.id, classe="6A")
    parti = personne_factory(site_id=site.id, login="parti")
    snap_factory(parti.id, an_prec.id, classe="6A")

    for categorie in ("tous", "nouveaux", "anciens"):
        contenu, _ = generer_csv_google(
            session=session, site_id=site.id, type_personne="eleve",
            categorie=categorie, annee_cible_id=an_cour.id,
            annee_source_id=an_prec.id,
        )
        lignes = _lire_csv_google(contenu)
        assert lignes, f"aucune ligne pour {categorie}"
        for l in lignes:
            assert l["Change Password at Next Sign-In"] == "False", categorie


def test_le_payload_api_ne_force_pas_non_plus():
    """Les deux canaux doivent dire la même chose à Google."""
    from backend.services.google_api import payload_creation_utilisateur

    p = payload_creation_utilisateur(
        email="jean.dupont@lekreisker.fr", prenom="Jean", nom="DUPONT",
        mot_de_passe="Xxxxxx11", org_unit_path="/3. NDK/NDK2027",
    )
    assert p["changePasswordAtNextLogin"] is False
