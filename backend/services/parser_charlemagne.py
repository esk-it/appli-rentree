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
    "identifiant eleve": "id_charlemagne",
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


MAX_LIGNES_AVANT_ENTETE = 10
"""Jusqu'où chercher la ligne d'en-tête avant d'abandonner."""


def _ligne_entete(df: pd.DataFrame) -> int:
    """Repère la ligne qui porte les libellés de colonnes.

    Charlemagne coiffe certains exports XLSX d'un titre daté — « Le 26 août
    2026 à 09 h 32 » — suivi de lignes vides. Lu tel quel, ce titre devient
    l'en-tête et **aucune** colonne n'est reconnue : l'ingestion refuse le
    fichier entier, ou pire, prend la vraie ligne d'en-tête pour un élève.

    On retient donc la ligne qui fait apparaître le plus de libellés connus.
    Zéro si aucune ne fait mieux que la première — un fichier déjà bien
    formé n'est pas touché.
    """
    meilleure, meilleur_score = 0, -1
    for i in range(min(MAX_LIGNES_AVANT_ENTETE, len(df))):
        score = sum(
            1
            for v in df.iloc[i]
            if pd.notna(v) and _normaliser_libelle(v) in COLONNES_NORMALISEES
        )
        if score > meilleur_score:
            meilleure, meilleur_score = i, score
    return meilleure


def lire_xlsx(chemin: str | Path, feuille: str | int = 0) -> pd.DataFrame:
    """Lit un export Charlemagne au format XLSX.

    Args:
        chemin: chemin du fichier .xlsx ou .xls
        feuille: nom ou index de la feuille à lire (par défaut la première)
    """
    chemin = Path(chemin)
    moteur = "xlrd" if chemin.suffix.lower() == ".xls" else "openpyxl"

    brut = pd.read_excel(chemin, sheet_name=feuille, engine=moteur, header=None)
    entete = _ligne_entete(brut)
    df = pd.read_excel(chemin, sheet_name=feuille, engine=moteur, header=entete)
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
