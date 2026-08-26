"""Tests du parser Charlemagne — mappings de colonnes contre régression.

Le parser doit tolérer les variantes de libellé rencontrées dans les vrais
exports (« Identifiant Élève », « Num Badge », etc.) et normaliser sans
perte de sens.
"""
from __future__ import annotations

from pathlib import Path


def _ecrire_htm(chemin: Path, entetes: list[str], lignes: list[list[str]]) -> None:
    """Crée un mini export HTM Charlemagne-like (encodage cp1252)."""
    ths = "".join(f"<th>{h}</th>" for h in entetes)
    rows = ""
    for l in lignes:
        rows += "<tr>" + "".join(f"<td>{c}</td>" for c in l) + "</tr>"
    html = f"""<html><body><table>
        <tr>{ths}</tr>
        {rows}
    </table></body></html>"""
    chemin.write_text(html, encoding="cp1252")


def test_mapping_identifiant_eleve(tmp_path):
    """`Identifiant Élève` doit être normalisé en `id_charlemagne`.

    Régression : le vrai export « Export Gestion de bases » utilise cette
    variante, qui manquait dans le mapping et bloquait toute ingestion.
    """
    from backend.services.parser_charlemagne import lire_htm

    fic = tmp_path / "export.htm"
    _ecrire_htm(
        fic,
        ["Num Badge", "Identifiant Élève", "Nom", "Prénom", "Code Classe prec.",
         "Code classe", "Code Classe an prochain", "Email", "Code Régime"],
        [["68240", "5824", "DANIELOU", "Ambre", "2_2", "1_G2", "", "ambre.danielou@lekreisker.fr", "D"]],
    )

    df = lire_htm(fic)

    assert "id_charlemagne" in df.columns
    assert df.loc[0, "id_charlemagne"] == 5824
    assert df.loc[0, "num_badge"] == 68240
    assert df.loc[0, "nom"] == "DANIELOU"
    assert df.loc[0, "code_classe"] == "1_G2"
    assert df.loc[0, "code_classe_precedente"] == "2_2"


def test_mapping_id_court(tmp_path):
    """La variante courte « ID » (utilisée en interne) reste supportée."""
    from backend.services.parser_charlemagne import lire_htm

    fic = tmp_path / "e.htm"
    _ecrire_htm(fic, ["Nom", "Prénom", "ID"], [["MARTIN", "Jean", "42"]])

    df = lire_htm(fic)
    assert df.loc[0, "id_charlemagne"] == 42


def test_mapping_identifiant_adultes(tmp_path):
    """« Identifiant » (export adultes) est aussi mappé vers id_charlemagne."""
    from backend.services.parser_charlemagne import lire_htm

    fic = tmp_path / "a.htm"
    _ecrire_htm(fic, ["Identifiant", "Nom", "Prénom"], [["313", "BARS", "John"]])

    df = lire_htm(fic)
    assert df.loc[0, "id_charlemagne"] == 313


# ---------------------------------------------------------------------------
# En-tête précédé d'un titre
# ---------------------------------------------------------------------------


def _classeur_avec_titre(tmp_path, lignes_avant_entete):
    """Reproduit la forme d'un export XLSX coiffé d'un titre daté."""
    import openpyxl

    wb = openpyxl.Workbook()
    ws = wb.active
    if lignes_avant_entete:
        ws.append(["Le 26 août 2026 à 09 h 32"])
        for _ in range(lignes_avant_entete - 1):
            ws.append([])
    ws.append([
        "Num Badge", "Identifiant Elève", "Nom", "Prénom",
        "Code Classe prec.", "Code classe", "Code Régime", "Email",
    ])
    ws.append([
        "18810", "881", "ZWOLINSKI", "Julie", None, "3T", "D", None,
    ])
    ws.append([
        "18390", "839", "MARC", "Calie", "6B", "5L", "DP3",
        "calie.marc@lekreisker.fr",
    ])
    chemin = tmp_path / "export.xlsx"
    wb.save(chemin)
    return chemin


def test_un_titre_date_ne_passe_pas_pour_len_tete(tmp_path):
    """Charlemagne coiffe ses exports XLSX d'un titre, puis de lignes vides.

    Lu tel quel, ce titre devient l'en-tête : aucune colonne n'est reconnue
    et l'ingestion refuse le fichier — ou prend la vraie ligne d'en-tête
    pour un élève.
    """
    from backend.services.parser_charlemagne import lire_xlsx

    df = lire_xlsx(_classeur_avec_titre(tmp_path, lignes_avant_entete=3))
    assert list(df.columns)[:4] == ["num_badge", "id_charlemagne", "nom", "prenom"]
    assert len(df) == 2, "la ligne d'en-tête n'est pas comptée comme un élève"
    assert df.iloc[0]["nom"] == "ZWOLINSKI"


def test_un_classeur_sans_titre_est_lu_comme_avant(tmp_path):
    """La recherche d'en-tête ne doit pas déplacer ce qui est déjà correct."""
    from backend.services.parser_charlemagne import lire_xlsx

    df = lire_xlsx(_classeur_avec_titre(tmp_path, lignes_avant_entete=0))
    assert list(df.columns)[:4] == ["num_badge", "id_charlemagne", "nom", "prenom"]
    assert len(df) == 2


def test_len_tete_nest_pas_cherchee_indefiniment(tmp_path):
    """Au-delà de quelques lignes, mieux vaut échouer que fouiller le fichier."""
    import openpyxl

    from backend.services.parser_charlemagne import (
        MAX_LIGNES_AVANT_ENTETE,
        lire_xlsx,
    )

    wb = openpyxl.Workbook()
    ws = wb.active
    for _ in range(MAX_LIGNES_AVANT_ENTETE + 2):
        ws.append(["blabla"])
    ws.append(["Num Badge", "Nom", "Prénom"])
    ws.append(["18810", "ZWOLINSKI", "Julie"])
    chemin = tmp_path / "trop_loin.xlsx"
    wb.save(chemin)

    df = lire_xlsx(chemin)
    assert "num_badge" not in df.columns
