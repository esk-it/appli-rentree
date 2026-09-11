"""Tests des exports JPM/SmartAir et CardStudio (Lot 11).

L'export PMB n'est plus fabriqué ici : PMB veut treize colonnes dont
sept sont absentes du référentiel. Le programme se contente de répartir
le fichier de Charlemagne — voir `test_repartition_pmb.py`.
"""
from __future__ import annotations

import csv
import io

import openpyxl
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


# ---------------------------------------------------------------------------
# JPM / SmartAir
# ---------------------------------------------------------------------------


def test_jpm_differentiel_a_b_m(session, site_factory, annee_factory, personne_factory, snap_factory):
    from backend.services.exports_jpm import COLONNES_JPM, generer_csv_jpm

    site = site_factory("NDK")
    an_prec = annee_factory("2024-2025")
    an_cour = annee_factory("2025-2026")

    # Ajout (dans cible seulement)
    p_a = personne_factory(site_id=site.id, nom="NEUF", login="neuf")
    snap_factory(p_a.id, an_cour.id, classe="3B")
    # Suppression (dans source seulement)
    p_b = personne_factory(site_id=site.id, nom="SORT", login="sort")
    snap_factory(p_b.id, an_prec.id, classe="TALE")
    # Modification (classe change)
    p_m = personne_factory(site_id=site.id, nom="MOD", login="mod")
    snap_factory(p_m.id, an_prec.id, classe="3B")
    snap_factory(p_m.id, an_cour.id, classe="2NDE")
    # Identique (ignoré)
    p_i = personne_factory(site_id=site.id, nom="IDENT", login="ident")
    snap_factory(p_i.id, an_prec.id, classe="4A")
    snap_factory(p_i.id, an_cour.id, classe="4A")

    contenu, rapport = generer_csv_jpm(
        session=session, site_id=site.id,
        annee_cible_id=an_cour.id, annee_source_id=an_prec.id,
    )

    assert rapport.nb_ajouts == 1
    assert rapport.nb_suppressions == 1
    assert rapport.nb_modifications == 1
    assert rapport.nb_total == 3

    rows = list(csv.DictReader(io.StringIO(contenu.decode("utf-8"))))
    ops = {r["Op"] for r in rows}
    assert ops == {"a", "b", "m"}
    # Colonnes techniques constantes présentes
    for r in rows:
        assert r["Technology"] == "P"
        assert r["Grants"] == "FFFFFF"


def test_jpm_ignore_les_adultes(session, site_factory, annee_factory, personne_factory, snap_factory):
    from backend.services.exports_jpm import generer_csv_jpm

    site = site_factory("NDK")
    an_prec = annee_factory("2024-2025")
    an_cour = annee_factory("2025-2026")

    # Un adulte nouveau — ne doit PAS apparaître dans JPM
    p_adulte = personne_factory(type="adulte", site_id=site.id, login="prof1")
    snap_factory(p_adulte.id, an_cour.id, poste_occupe="ENSEIGNEMENT")

    _, rapport = generer_csv_jpm(
        session=session, site_id=site.id,
        annee_cible_id=an_cour.id, annee_source_id=an_prec.id,
    )
    assert rapport.nb_total == 0


# ---------------------------------------------------------------------------
# CardStudio
# ---------------------------------------------------------------------------


def _table(session, site, *codes):
    """Déclare des classes dans la table de correspondance."""
    from backend.models import TableCorrespondance

    for code in codes:
        session.add(TableCorrespondance(
            site_id=site.id,
            classe_charlemagne_long=code,
            classe_code_court=code,
            ou_pre_rentree=f"/{site.nom}",
            ou_definitive=f"/{site.nom}/{code}",
        ))
    session.commit()


def _export(lignes, colonnes=None):
    """Un export CardStudio de Charlemagne, réduit à l'essentiel."""
    colonnes = colonnes or [
        "Etablissement", "Code établissement", "Code niveau", "Code classe",
        "Num Badge", "Code Régime", "Nom et prénom", "Nom", "Prénom",
        "Photo", "Date Entrée pour tri", "NomFichierPhoto", "Chambres",
    ]
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.append(colonnes)
    for l in lignes:
        ws.append([l.get(c, "") for c in colonnes])
    buf = io.BytesIO()
    wb.save(buf)
    return buf.getvalue()


def test_cardstudio_rend_les_13_colonnes(session, site_factory):
    """Le fichier produit a exactement le format que CardStudio attend."""
    from backend.services.exports_cardstudio import (
        COLONNES_CARDSTUDIO, repartir_export_cardstudio,
    )

    site = site_factory("NDK")
    _table(session, site, "3B")
    contenu = _export([{
        "Code classe": "3B", "Num Badge": "12340",
        "Nom": "DUPONT", "Prénom": "Jean", "Nom et prénom": "DUPONT Jean",
    }])

    octets, r = repartir_export_cardstudio(
        session, contenu=contenu, nom_fichier="export.xlsx")

    ws = openpyxl.load_workbook(io.BytesIO(octets)).active
    entete = [c.value for c in next(ws.iter_rows(max_row=1))]
    assert entete == COLONNES_CARDSTUDIO
    assert r.nb_lignes_retenues == 1


def test_cardstudio_deduit_le_nom_de_photo_en_valeur(session, site_factory):
    """`NomFichierPhoto` se tire de `Photo`, et jamais sous forme de formule.

    CardStudio lit le classeur sans passer par Excel : une formule sans
    valeur en cache lui apparaît vide, et le badge sort sans visage.
    """
    from backend.services.exports_cardstudio import (
        COLONNES_CARDSTUDIO, repartir_export_cardstudio,
    )

    site = site_factory("NDK")
    _table(session, site, "3B")
    chemin = r"\\SERVEUR\Photos\2026-2027\DUPONT Jean.jpg"
    contenu = _export([{
        "Code classe": "3B", "Num Badge": "12340", "Nom": "DUPONT",
        "Prénom": "Jean", "Photo": chemin, "NomFichierPhoto": "=MID(J2,1,9)",
    }])

    octets, r = repartir_export_cardstudio(
        session, contenu=contenu, nom_fichier="export.xlsx")

    ligne = list(openpyxl.load_workbook(io.BytesIO(octets)).active
                 .iter_rows(min_row=2, values_only=True))[0]
    i = COLONNES_CARDSTUDIO.index("NomFichierPhoto")
    assert ligne[i] == "DUPONT Jean.jpg"
    assert COLONNES_CARDSTUDIO.index("Photo") is not None
    assert ligne[COLONNES_CARDSTUDIO.index("Photo")] == chemin
    assert "NomFichierPhoto" in r.colonnes_completees


def test_cardstudio_filtres_se_cumulent(session, site_factory):
    """Site, classe et badge se combinent — chacun vide ne filtre rien."""
    from backend.services.exports_cardstudio import repartir_export_cardstudio

    ndk = site_factory("NDK")
    su = site_factory("SU")
    _table(session, ndk, "2_1", "2_2")
    _table(session, su, "31")
    contenu = _export([
        {"Code classe": "2_1", "Num Badge": "1", "Nom": "A", "Prénom": "a"},
        {"Code classe": "2_2", "Num Badge": "2", "Nom": "B", "Prénom": "b"},
        {"Code classe": "31", "Num Badge": "3", "Nom": "C", "Prénom": "c"},
    ])

    def compte(**kw):
        _, r = repartir_export_cardstudio(
            session, contenu=contenu, nom_fichier="e.xlsx", **kw)
        return r.nb_lignes_retenues

    assert compte() == 3
    assert compte(sites=["NDK"]) == 2
    assert compte(sites=["SU"]) == 1
    assert compte(classes=["2_1"]) == 1
    assert compte(badges=["3"]) == 1
    assert compte(sites=["NDK"], classes=["2_1"]) == 1
    # Les filtres se cumulent : une classe de SU dans le site NDK ne rend rien.
    assert compte(sites=["NDK"], classes=["31"]) == 0


def test_cardstudio_ecarte_les_classes_hors_table(session, site_factory):
    """Une classe inconnue ne tombe dans aucun fichier — mais se signale.

    Sans ce relevé, l'élève disparaît sans bruit et personne ne s'aperçoit
    qu'il n'aura pas de badge.
    """
    from backend.services.exports_cardstudio import repartir_export_cardstudio

    site = site_factory("NDK")
    _table(session, site, "2_1")
    contenu = _export([
        {"Code classe": "2_1", "Num Badge": "1", "Nom": "A", "Prénom": "a"},
        {"Code classe": "ZZZ", "Num Badge": "9", "Nom": "Z", "Prénom": "z"},
    ])

    _, r = repartir_export_cardstudio(
        session, contenu=contenu, nom_fichier="e.xlsx")

    assert r.nb_lignes_retenues == 1
    assert [e.badge for e in r.ecartees] == ["9"]
    assert "table de correspondance" in r.ecartees[0].motif


def test_cardstudio_lignes_de_chambre(session, site_factory):
    """Les lignes `INTERNAT` ne désignent personne : elles sortent du lot.

    Charlemagne les ajoute en fin d'export avec un seul nom de chambre, sans
    badge ni élève. Les laisser passer donnerait un badge vierge par chambre.
    """
    from backend.services.exports_cardstudio import (
        COLONNES_CARDSTUDIO, repartir_export_cardstudio,
    )

    site = site_factory("NDK")
    _table(session, site, "2_1")
    contenu = _export([
        {"Code classe": "2_1", "Num Badge": "1", "Nom": "A", "Prénom": "a"},
        {"Etablissement": "INTERNAT", "Chambres": "chambre 02-01"},
    ])

    _, sans = repartir_export_cardstudio(
        session, contenu=contenu, nom_fichier="e.xlsx", avec_chambres=False)
    octets, avec = repartir_export_cardstudio(
        session, contenu=contenu, nom_fichier="e.xlsx", avec_chambres=True)

    assert sans.nb_lignes_retenues == 1
    assert sans.chambres_reportees == 0
    assert avec.nb_lignes_retenues == 1      # l'élève, pas la chambre
    assert avec.chambres_reportees == 1

    lignes = list(openpyxl.load_workbook(io.BytesIO(octets)).active
                  .iter_rows(min_row=2, values_only=True))
    assert len(lignes) == 2
    i_ch = COLONNES_CARDSTUDIO.index("Chambres")
    assert lignes[-1][i_ch] == "chambre 02-01"


def test_cardstudio_refuse_un_fichier_etranger(session, site_factory):
    """Un fichier qui n'est pas cet export se dit tout de suite."""
    from backend.services.exports_cardstudio import (
        ExportImpossible, repartir_export_cardstudio,
    )

    site_factory("NDK")
    contenu = _export([{"Autre": "x"}], colonnes=["Autre"])
    with pytest.raises(ExportImpossible, match="Num Badge"):
        repartir_export_cardstudio(session, contenu=contenu, nom_fichier="e.xlsx")

    with pytest.raises(ExportImpossible, match="Extension"):
        repartir_export_cardstudio(session, contenu=b"x", nom_fichier="e.txt")
