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
