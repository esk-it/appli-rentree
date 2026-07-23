"""Lecture des exports Charlemagne.

Charlemagne peut exporter au format HTM (table HTML) ou XLSX. Ce module gère
les deux. Il retourne un DataFrame pandas avec des noms de colonnes normalisés
(en snake_case, sans accents), pour faciliter le traitement en aval.

L'encodage des HTM Charlemagne est cp1252 (Windows-1252).
"""
from __future__ import annotations

from pathlib import Path

import pandas as pd
from unidecode import unidecode


# Mapping libellé Charlemagne → nom de colonne normalisé.
# Si Charlemagne ajoute/renomme une colonne, on adapte ici uniquement.
COLONNES_NORMALISEES = {
    # -- Communs / élèves (export HTM et export "Gestion de bases") --
    "nom etablissement": "nom_etablissement",
    "code etablissement": "code_etablissement",
    "etablissement": "code_etablissement_court",  # BadgesESK utilise "Etablissement" = "KREISKER"
    "code niveau": "code_niveau",
    "code classe": "code_classe",
    "code classe prec.": "code_classe_precedente",
    "code classe prec": "code_classe_precedente",
    "code classe an prochain": "code_classe_an_prochain",
    "num badge": "num_badge",
    "badge": "num_badge",
    "id": "id_charlemagne",
    "code regime": "code_regime",
    "regime": "code_regime",
    "nom et prenom": "nom_et_prenom",
    "nom": "nom",
    "prenom": "prenom",
    "email": "email",
    "photo": "photo_chemin",
    "nouvel eleve": "nouvel_eleve",
    "date entree pour tri": "date_entree",
    "nomfichierphoto": "nom_fichier_photo",
    "chambres": "chambre",
    # -- Adultes (export "Import Adultes Charlemagne N") --
    "identifiant": "id_charlemagne",
    "poste occupe": "poste_occupe",
    "liste des matieres": "matieres",
    "liste des classes (prof principal)": "classes_prof_principal",
    "date de naissance": "date_naissance",
    "civilite": "civilite",
    "adresse 1": "adresse_1",
    "adresse 2": "adresse_2",
    "code postal": "code_postal",
    "ville": "ville",
    "tel. domicile (avec lr)": "telephone",
    "tel. domicile": "telephone",
    "telephone": "telephone",
    "email professionnel": "email_professionnel",
    "email personnel": "email_personnel",
}


def _normaliser_libelle(libelle: str) -> str:
    """Convertit un libellé brut Charlemagne en clé normalisée.

    "Établissement" → "etablissement", "Date Entrée pour tri" → "date entree pour tri".
    """
    if libelle is None:
        return ""
    return unidecode(str(libelle)).strip().lower()


def lire_htm(chemin: str | Path) -> pd.DataFrame:
    """Lit un export Charlemagne au format HTM (table HTML).

    Returns:
        DataFrame avec colonnes normalisées (snake_case, sans accents).
        Les colonnes non reconnues sont conservées sous leur libellé normalisé.
    """
    chemin = Path(chemin)
    # Charlemagne exporte en cp1252 (Windows-1252).
    tables = pd.read_html(chemin, encoding="cp1252")
    if not tables:
        raise ValueError(f"Aucun tableau trouvé dans {chemin}")
    # Charlemagne met tout dans une seule grande table.
    df = max(tables, key=len)
    return _normaliser_colonnes(df)


def lire_xlsx(chemin: str | Path, feuille: str | int = 0) -> pd.DataFrame:
    """Lit un export Charlemagne au format XLSX.

    Args:
        chemin: chemin du fichier .xlsx ou .xls
        feuille: nom ou index de la feuille à lire (par défaut la première)
    """
    chemin = Path(chemin)
    if chemin.suffix.lower() == ".xls":
        df = pd.read_excel(chemin, sheet_name=feuille, engine="xlrd")
    else:
        df = pd.read_excel(chemin, sheet_name=feuille, engine="openpyxl")
    return _normaliser_colonnes(df)


def _normaliser_colonnes(df: pd.DataFrame) -> pd.DataFrame:
    """Renomme les colonnes selon le mapping COLONNES_NORMALISEES."""
    nouvelles_colonnes = {}
    for col in df.columns:
        cle = _normaliser_libelle(col)
        nouvelles_colonnes[col] = COLONNES_NORMALISEES.get(cle, cle.replace(" ", "_"))
    df = df.rename(columns=nouvelles_colonnes)

    # Conversions de types utiles
    if "num_badge" in df.columns:
        df["num_badge"] = pd.to_numeric(df["num_badge"], errors="coerce").astype("Int64")
    if "id_charlemagne" in df.columns:
        df["id_charlemagne"] = pd.to_numeric(
            df["id_charlemagne"], errors="coerce"
        ).astype("Int64")
    if "date_entree" in df.columns:
        # Format YYYYMMDD → date
        df["date_entree"] = pd.to_datetime(
            df["date_entree"].astype(str).str.replace(r"\.0$", "", regex=True),
            format="%Y%m%d",
            errors="coerce",
        )
    if "date_naissance" in df.columns:
        df["date_naissance"] = pd.to_datetime(
            df["date_naissance"], errors="coerce"
        )
    if "nouvel_eleve" in df.columns:
        # "O" → True, vide / NaN → False
        df["nouvel_eleve"] = df["nouvel_eleve"].fillna("").astype(str).str.strip() == "O"

    # Supprimer les lignes vides (artefacts de parsing, lignes d'en-tête dupliquées)
    cle_identite = "nom" if "nom" in df.columns else df.columns[0]
    df = df.dropna(subset=[cle_identite]).reset_index(drop=True)

    return df
