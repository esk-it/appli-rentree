"""Tests de l'atelier des cartes — le fichier CardStudio depuis le référentiel.

Ce que ces tests protègent avant tout : **rien ne s'invente**. Une photo
absente reste une case vide et un nom dans le rapport ; une classe dont les
codes sont inconnus laisse ses colonnes vides et se signale. Un fichier qui
a l'air complet mais ne l'est pas produit des cartes fausses, et une carte
fausse ne se découvre qu'imprimée.
"""
from __future__ import annotations

import io
import json
from datetime import date

import openpyxl
import pytest


@pytest.fixture()
def snap_factory(session):
    from backend.models import Snapshot

    def _creer(personne_id, annee_id, **kwargs):
        defauts = {"nom": "MARTIN", "prenom": "Jean", "classe": "3B"}
        defauts.update(kwargs)
        s = Snapshot(personne_id=personne_id, annee_scolaire_id=annee_id, **defauts)
        session.add(s)
        session.commit()
        return s

    return _creer


@pytest.fixture()
def classe_factory(session):
    """Une classe dans la table de correspondance, codes CardStudio compris."""
    from backend.models import TableCorrespondance

    def _creer(site, code_court, *, niveau=None, etablissement=None, long=None):
        t = TableCorrespondance(
            site_id=site.id,
            classe_charlemagne_long=long or code_court,
            classe_code_court=code_court,
            ou_pre_rentree=f"/{site.nom}",
            ou_definitive=f"/{site.nom}/{code_court}",
            code_niveau=niveau,
            code_etablissement=etablissement,
        )
        session.add(t)
        session.commit()
        return t

    return _creer


def _lignes(octets: bytes) -> list[dict]:
    ws = openpyxl.load_workbook(io.BytesIO(octets)).active
    lignes = list(ws.values)
    entete = [str(c) for c in lignes[0]]
    return [dict(zip(entete, l)) for l in lignes[1:]]


# ---------------------------------------------------------------------------
# Les chambres
# ---------------------------------------------------------------------------


def test_les_chambres_sont_les_soixante_dix_sept_de_l_internat():
    """La liste est figée, et sa forme aussi : doubles puis simples."""
    from backend.services.cartes_cardstudio import CHAMBRES

    assert len(CHAMBRES) == 77
    assert CHAMBRES[0] == "chambre 02-01"
    assert CHAMBRES[39] == "chambre 21-02"
    assert CHAMBRES[40] == "chambre 22"
    assert CHAMBRES[-1] == "chambre 58"
    assert len(set(CHAMBRES)) == 77


def test_les_chambres_sont_reconduites_en_fin_de_fichier(
    session, site_factory, annee_factory, personne_factory, snap_factory, classe_factory
):
    """Cochée, la case remplit vraiment la colonne — c'était le défaut.

    Les lignes de chambre ne portent que deux valeurs, comme Charlemagne les
    écrit : l'établissement `INTERNAT` et le nom de la chambre. Elles vont en
    queue : ce ne sont pas des élèves, elles n'ont pas à s'intercaler.
    """
    from backend.services.cartes_cardstudio import CHAMBRES, construire_fichier

    site = site_factory("NDK")
    annee = annee_factory("2026-2027")
    classe_factory(site, "2_1", niveau="1-2NDES-LY", etablissement="03-LY")
    p = personne_factory(site_id=site.id, nom="DUPONT", prenom="Léa")
    snap_factory(p.id, annee.id, classe="2_1")

    octets, rapport = construire_fichier(
        session, personne_ids=[p.id], annee_id=annee.id, avec_chambres=True
    )
    lignes = _lignes(octets)

    assert rapport.nb_cartes == 1
    assert rapport.nb_chambres == 77
    assert len(lignes) == 78
    assert lignes[0]["Nom"] == "DUPONT"
    chambres = [l["Chambres"] for l in lignes[1:]]
    assert chambres == CHAMBRES
    assert {l["Etablissement"] for l in lignes[1:]} == {"INTERNAT"}
    assert all(not l["Num Badge"] for l in lignes[1:])


def test_sans_la_case_aucune_ligne_de_chambre(
    session, site_factory, annee_factory, personne_factory, snap_factory, classe_factory
):
    from backend.services.cartes_cardstudio import construire_fichier

    site = site_factory("NDK")
    annee = annee_factory("2026-2027")
    classe_factory(site, "2_1", niveau="1-2NDES-LY", etablissement="03-LY")
    p = personne_factory(site_id=site.id)
    snap_factory(p.id, annee.id, classe="2_1")

    octets, rapport = construire_fichier(
        session, personne_ids=[p.id], annee_id=annee.id, avec_chambres=False
    )
    assert rapport.nb_chambres == 0
    assert len(_lignes(octets)) == 1


# ---------------------------------------------------------------------------
# Choisir des personnes, pas des numéros de badge
# ---------------------------------------------------------------------------


def test_on_designe_des_personnes_et_le_fichier_les_suit(
    session, site_factory, annee_factory, personne_factory, snap_factory, classe_factory
):
    """Trois élèves dans la base, deux cochés : deux cartes."""
    from backend.services.cartes_cardstudio import construire_fichier

    site = site_factory("NDK")
    annee = annee_factory("2026-2027")
    classe_factory(site, "2_1", niveau="1-2NDES-LY", etablissement="03-LY")
    gardes = []
    for nom in ("ABALAIN", "BIHAN", "CORRE"):
        p = personne_factory(site_id=site.id, nom=nom, prenom="Test")
        snap_factory(p.id, annee.id, classe="2_1", regime="D")
        gardes.append(p)

    octets, rapport = construire_fichier(
        session, personne_ids=[gardes[0].id, gardes[2].id], annee_id=annee.id
    )
    lignes = _lignes(octets)

    assert rapport.nb_cartes == 2
    assert [l["Nom"] for l in lignes] == ["ABALAIN", "CORRE"]


def test_un_fichier_vide_est_refuse(session, annee_factory):
    """CardStudio n'accepte qu'un fichier par projet : un vide le gâche."""
    from backend.services.cartes_cardstudio import CartesImpossibles, construire_fichier

    annee = annee_factory("2026-2027")
    with pytest.raises(CartesImpossibles, match="Aucun élève coché"):
        construire_fichier(session, personne_ids=[], annee_id=annee.id)


def test_les_candidats_portent_l_etat_de_leur_photo(
    session, site_factory, annee_factory, personne_factory, snap_factory,
    classe_factory, tmp_path, monkeypatch
):
    """C'est avant de cocher qu'on doit voir qui n'a pas de visage."""
    from backend.models import Parametre
    from backend.services.cartes_cardstudio import lister_candidats

    site = site_factory("NDK")
    annee = annee_factory("2026-2027")
    classe_factory(site, "2_1", niveau="1-2NDES-LY", etablissement="03-LY")
    avec = personne_factory(site_id=site.id, nom="AVEC", prenom="Photo")
    sans = personne_factory(site_id=site.id, nom="SANS", prenom="Photo")
    snap_factory(avec.id, annee.id, classe="2_1")
    snap_factory(sans.id, annee.id, classe="2_1")

    (tmp_path / "AVEC Photo.jpg").write_bytes(b"x")
    session.add(Parametre(
        cle="chemin_dossier_photos", valeur_json=json.dumps(str(tmp_path))
    ))
    session.commit()

    par_nom = {c.nom: c for c in lister_candidats(session, annee_id=annee.id)}
    assert par_nom["AVEC"].a_une_photo is True
    assert par_nom["SANS"].a_une_photo is False
    assert par_nom["AVEC"].site == "NDK"
    assert par_nom["AVEC"].codes_connus is True


def test_un_partage_injoignable_ne_fait_pas_disparaitre_la_liste(
    session, site_factory, annee_factory, personne_factory, snap_factory, classe_factory
):
    """Poste hors réseau : on rend la liste, photos inconnues, pas d'erreur."""
    from backend.services.cartes_cardstudio import lister_candidats

    site = site_factory("NDK")
    annee = annee_factory("2026-2027")
    classe_factory(site, "2_1")
    p = personne_factory(site_id=site.id, nom="SEUL")
    snap_factory(p.id, annee.id, classe="2_1")

    candidats = lister_candidats(session, annee_id=annee.id)
    assert [c.nom for c in candidats] == ["SEUL"]
    assert candidats[0].a_une_photo is False


# ---------------------------------------------------------------------------
# Ce qui manque se dit, et ne s'invente pas
# ---------------------------------------------------------------------------


def test_une_classe_sans_codes_laisse_les_colonnes_vides_et_se_signale(
    session, site_factory, annee_factory, personne_factory, snap_factory, classe_factory
):
    """Deviner `03-LY` mettrait un lycéen au collège sur sa carte."""
    from backend.services.cartes_cardstudio import construire_fichier

    site = site_factory("NDK")
    annee = annee_factory("2026-2027")
    classe_factory(site, "2_9")            # ni niveau ni établissement
    p = personne_factory(site_id=site.id, nom="INCONNUE")
    snap_factory(p.id, annee.id, classe="2_9")

    octets, rapport = construire_fichier(
        session, personne_ids=[p.id], annee_id=annee.id
    )
    ligne = _lignes(octets)[0]

    assert ligne["Code niveau"] in (None, "")
    assert ligne["Code établissement"] in (None, "")
    assert ligne["Etablissement"] in (None, "")
    assert rapport.classes_sans_codes == ["2_9"]


def test_un_eleve_sans_photo_est_nomme(
    session, site_factory, annee_factory, personne_factory, snap_factory, classe_factory
):
    from backend.services.cartes_cardstudio import construire_fichier

    site = site_factory("NDK")
    annee = annee_factory("2026-2027")
    classe_factory(site, "2_1", niveau="1-2NDES-LY", etablissement="03-LY")
    p = personne_factory(site_id=site.id, nom="NUL", prenom="Visage")
    snap_factory(p.id, annee.id, classe="2_1")

    octets, rapport = construire_fichier(
        session, personne_ids=[p.id], annee_id=annee.id
    )
    ligne = _lignes(octets)[0]

    assert ligne["Photo"] in (None, "")
    assert ligne["NomFichierPhoto"] in (None, "")
    assert rapport.sans_photo == ["NUL Visage — 2_1"]


def test_l_etablissement_se_deduit_du_code(
    session, site_factory, annee_factory, personne_factory, snap_factory, classe_factory
):
    """`04-LP` et `03-LY` sont deux établissements, un seul site : KREISKER."""
    from backend.services.cartes_cardstudio import construire_fichier

    site = site_factory("NDK")
    annee = annee_factory("2026-2027")
    classe_factory(site, "1_BPAGORA", niveau="2-1ERES-LP", etablissement="04-LP")
    p = personne_factory(site_id=site.id, nom="PRO")
    snap_factory(p.id, annee.id, classe="1_BPAGORA")

    octets, _ = construire_fichier(session, personne_ids=[p.id], annee_id=annee.id)
    ligne = _lignes(octets)[0]
    assert ligne["Etablissement"] == "KREISKER"
    assert ligne["Code établissement"] == "04-LP"
    assert ligne["Code niveau"] == "2-1ERES-LP"


def test_la_date_d_entree_sort_au_format_de_tri(
    session, site_factory, annee_factory, personne_factory, snap_factory, classe_factory
):
    from backend.services.cartes_cardstudio import construire_fichier

    site = site_factory("NDK")
    annee = annee_factory("2026-2027")
    classe_factory(site, "2_1", niveau="1-2NDES-LY", etablissement="03-LY")
    p = personne_factory(site_id=site.id, date_entree=date(2023, 9, 4))
    snap_factory(p.id, annee.id, classe="2_1")

    octets, rapport = construire_fichier(
        session, personne_ids=[p.id], annee_id=annee.id
    )
    assert _lignes(octets)[0]["Date Entrée pour tri"] == "20230904"
    assert rapport.sans_date_entree == 0


# ---------------------------------------------------------------------------
# Apprendre depuis un export — l'opération d'installation
# ---------------------------------------------------------------------------


def _export(lignes, colonnes=None) -> bytes:
    """Un export CardStudio de Charlemagne, réduit à l'essentiel."""
    from backend.services.cartes_cardstudio import COLONNES_CARDSTUDIO

    wb = openpyxl.Workbook()
    ws = wb.active
    ws.append(colonnes or COLONNES_CARDSTUDIO)
    for l in lignes:
        ws.append([l.get(c, "") for c in (colonnes or COLONNES_CARDSTUDIO)])
    buf = io.BytesIO()
    wb.save(buf)
    return buf.getvalue()


def test_apprendre_remplit_les_codes_de_classe_et_les_dates(
    session, site_factory, annee_factory, personne_factory, snap_factory, classe_factory
):
    """Un export passé une fois, et Charlemagne n'est plus nécessaire."""
    from backend.services.cartes_cardstudio import (
        apprendre_depuis_export, construire_fichier,
    )

    site = site_factory("NDK")
    annee = annee_factory("2026-2027")
    classe_factory(site, "2_1")            # codes inconnus au départ
    p = personne_factory(site_id=site.id, nom="TANGUY", prenom="Alix")
    snap_factory(p.id, annee.id, classe="2_1")

    contenu = _export([{
        "Code établissement": "03-LY",
        "Code niveau": "1-2NDES-LY",
        "Code classe": "2_1",
        "Num Badge": str(p.badge),
        "Photo": r"\\ESK-APP01\Photos\TANGUY Alix.jpg",
        "Date Entrée pour tri": "20260901",
    }])
    rapport = apprendre_depuis_export(
        session, contenu=contenu, nom_fichier="export.xlsx"
    )

    assert rapport.classes_apprises == ["2_1"]
    assert rapport.nb_dates_apprises == 1
    assert rapport.nb_photos_memorisees == 1

    octets, suite = construire_fichier(
        session, personne_ids=[p.id], annee_id=annee.id
    )
    ligne = _lignes(octets)[0]
    assert ligne["Code niveau"] == "1-2NDES-LY"
    assert ligne["Date Entrée pour tri"] == "20260901"
    assert suite.classes_sans_codes == []


def test_apprendre_n_efface_jamais_avec_du_vide(
    session, site_factory, annee_factory, personne_factory, classe_factory
):
    """Un export partiel ne doit pas défaire ce qu'un export complet a appris."""
    from backend.services.cartes_cardstudio import apprendre_depuis_export

    site = site_factory("NDK")
    annee_factory("2026-2027")
    t = classe_factory(site, "2_1", niveau="1-2NDES-LY", etablissement="03-LY")
    p = personne_factory(site_id=site.id, date_entree=date(2022, 9, 1))

    contenu = _export(
        [{"Code classe": "2_1", "Num Badge": str(p.badge)}],
        colonnes=["Code classe", "Num Badge"],
    )
    apprendre_depuis_export(session, contenu=contenu, nom_fichier="partiel.xlsx")

    assert t.code_niveau == "1-2NDES-LY"
    assert p.date_entree == date(2022, 9, 1)


def test_apprendre_ignore_les_lignes_de_chambre(
    session, site_factory, annee_factory, personne_factory, classe_factory
):
    """Une chambre n'a ni badge ni classe : elle n'enseigne rien."""
    from backend.services.cartes_cardstudio import apprendre_depuis_export

    site = site_factory("NDK")
    annee_factory("2026-2027")
    classe_factory(site, "2_1")
    contenu = _export([
        {"Etablissement": "INTERNAT", "Chambres": "chambre 02-01"},
    ])
    rapport = apprendre_depuis_export(
        session, contenu=contenu, nom_fichier="e.xlsx"
    )
    assert rapport.classes_apprises == []
    assert rapport.badges_inconnus == 0


def test_apprendre_signale_les_classes_hors_table(
    session, site_factory, annee_factory, personne_factory, classe_factory
):
    """Une classe absente de la table ne s'y crée pas toute seule."""
    from backend.services.cartes_cardstudio import apprendre_depuis_export

    site = site_factory("NDK")
    annee_factory("2026-2027")
    classe_factory(site, "2_1")
    p = personne_factory(site_id=site.id)
    contenu = _export([{
        "Code classe": "9_9", "Code niveau": "X", "Code établissement": "03-LY",
        "Num Badge": str(p.badge),
    }])
    rapport = apprendre_depuis_export(
        session, contenu=contenu, nom_fichier="e.xlsx"
    )
    assert rapport.classes_inconnues == ["9_9"]


def test_apprendre_refuse_un_fichier_qui_n_en_est_pas(session):
    from backend.services.cartes_cardstudio import CartesImpossibles, apprendre_depuis_export

    contenu = _export([{"Truc": "1"}], colonnes=["Truc"])
    with pytest.raises(CartesImpossibles, match="n'a pas l'air d'un export"):
        apprendre_depuis_export(session, contenu=contenu, nom_fichier="e.xlsx")


# ---------------------------------------------------------------------------
# Le dossier des photos, vu de deux côtés
# ---------------------------------------------------------------------------


LECTURE = r"\ESK-APP01\Charlemagne\Alcuin\Photos\Eleves\KREISKER\2026-2027"
CARDSTUDIO = r"\ESK-APP01\Alcuin$\Photos\Eleves\KREISKER\2026-2027"


def test_sans_reglage_le_chemin_des_photos_ne_bouge_pas(session):
    """Le cas de tout le monde : un seul nom de partage, rien à traduire."""
    from backend.services.cartes_cardstudio import _vu_par_cardstudio

    chemin = LECTURE + r"\MARTIN Jean.jpg"
    assert _vu_par_cardstudio(session, chemin) == chemin


def test_le_fichier_porte_le_chemin_que_cardstudio_sait_ouvrir(session):
    r"""Le même dossier, l'autre nom de partage.

    L'application lit les images par `Charlemagne\Alcuin` ; CardStudio les
    ouvre sous un autre compte, par `Alcuin$`. Écrire notre chemin dans le
    fichier donnait un classeur complet et pas une seule image.
    """
    from backend.services.cartes_cardstudio import _vu_par_cardstudio
    from backend.services.configuration import set_param

    set_param(session, "chemin_dossier_photos", LECTURE)
    set_param(session, "chemin_photos_cardstudio", CARDSTUDIO)
    session.commit()  # `set_param` ne commit pas : le routeur s'en charge

    assert (
        _vu_par_cardstudio(session, LECTURE + r"\MARTIN Jean.jpg")
        == CARDSTUDIO + r"\MARTIN Jean.jpg"
    )


def test_un_chemin_venu_d_ailleurs_est_laisse_tel_quel(session):
    """Photo d'adulte, chemin mémorisé d'un ancien export : on ne recolle
    pas deux racines au hasard sous prétexte qu'un réglage existe."""
    from backend.services.cartes_cardstudio import _vu_par_cardstudio
    from backend.services.configuration import set_param

    set_param(session, "chemin_dossier_photos", LECTURE)
    set_param(session, "chemin_photos_cardstudio", CARDSTUDIO)
    session.commit()  # `set_param` ne commit pas : le routeur s'en charge

    etranger = r"\AUTRE-SERVEUR\Photos\Enseignants\DUPONT Marie.jpg"
    assert _vu_par_cardstudio(session, etranger) == etranger


def test_apprendre_retient_le_dossier_que_cardstudio_ecrit(
    session, site_factory, annee_factory, personne_factory, classe_factory
):
    """Un export prouve par quel chemin CardStudio a su ouvrir les images.

    C'est la seule occasion de l'apprendre, et elle rend le réglage
    inutile : un import suffit.
    """
    from backend.services.cartes_cardstudio import apprendre_depuis_export
    from backend.services.configuration import get_param, set_param

    site = site_factory("NDK")
    annee_factory("2026-2027")
    classe_factory(site, "2_1", niveau="1-2NDES-LY", etablissement="03-LY")
    p = personne_factory(site_id=site.id, nom="MARTIN", prenom="Jean")
    set_param(session, "chemin_dossier_photos", LECTURE)
    session.commit()

    rapport = apprendre_depuis_export(
        session,
        contenu=_export([
            {
                "Code classe": "2_1",
                "Num Badge": str(p.badge),
                "Photo": CARDSTUDIO + r"\MARTIN Jean.jpg",
            },
            {
                "Code classe": "2_1",
                "Num Badge": str(p.badge),
                "Photo": CARDSTUDIO + r"\AUTRE Eleve.jpg",
            },
        ]),
        nom_fichier="export.xlsx",
    )

    assert rapport.racine_photos_apprise == CARDSTUDIO
    assert get_param(session, "chemin_photos_cardstudio") == CARDSTUDIO


def test_apprendre_ne_retient_rien_quand_le_dossier_est_le_notre(
    session, site_factory, annee_factory, personne_factory, classe_factory
):
    """Un seul nom de partage : pas de réglage à poser, pas de bruit."""
    from backend.services.cartes_cardstudio import apprendre_depuis_export
    from backend.services.configuration import get_param, set_param

    site = site_factory("NDK")
    annee_factory("2026-2027")
    classe_factory(site, "2_1", niveau="1-2NDES-LY", etablissement="03-LY")
    p = personne_factory(site_id=site.id, nom="MARTIN", prenom="Jean")
    set_param(session, "chemin_dossier_photos", LECTURE)
    session.commit()

    rapport = apprendre_depuis_export(
        session,
        contenu=_export([
            {
                "Code classe": "2_1",
                "Num Badge": str(p.badge),
                "Photo": LECTURE + r"\MARTIN Jean.jpg",
            }
        ]),
        nom_fichier="export.xlsx",
    )

    assert rapport.racine_photos_apprise is None
    assert not (get_param(session, "chemin_photos_cardstudio") or "")
