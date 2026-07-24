"""Lecture des exports KoXo (CSV).

Le format standard :

    badge | Groupe primaire | Groupe secondaire | Titre | Nom | Prénom |
    Identifiant | ID unique | Mot de passe | Date de naissance | Email

Séparateur : virgule (parfois point-virgule selon la config du serveur).
Encodage : utf-8 ou cp1252. On tente les deux.

Deux populations dans les exports :
- **Élèves** : `Groupe primaire = "Elèves"` (avec ou sans accent grave).
  `Groupe secondaire` = code classe Charlemagne (`31`, `1_G2`…).
- **Adultes / profs** : `Groupe primaire = "Professeurs"` ou autre.
  `Groupe secondaire` = matière ou service.

**Le mot de passe est présent dans le fichier mais n'est JAMAIS persisté**
(cf. §7.1 du prompt : « le mot de passe n'est jamais persisté »). Le parser
lit la colonne pour ne pas casser le mapping, mais le service d'amorçage
ignore cette valeur.
"""
from __future__ import annotations

from pathlib import Path

import pandas as pd
from unidecode import unidecode


# Mapping libellé KoXo → nom de colonne normalisé.
COLONNES_KOXO = {
    "badge": "num_badge",
    "id unique": "num_badge",
    "groupe primaire": "groupe_primaire",
    "groupe secondaire": "groupe_secondaire",
    "titre": "titre",
    "nom": "nom",
    "prenom": "prenom",
    "identifiant": "login",
    "mot de passe": "_mot_de_passe_ignore",
    "email": "email",
    "date de naissance": "date_naissance",
}


def _normaliser_libelle(libelle: str) -> str:
    if libelle is None:
        return ""
    return unidecode(str(libelle)).strip().lower()


def lire_csv_koxo(chemin: str | Path) -> pd.DataFrame:
    """Lit un export KoXo au format CSV (virgule ou point-virgule)."""
    chemin = Path(chemin)

    # Tente utf-8 puis cp1252, chaque fois avec , puis ; comme séparateur
    df = None
    dernier_erreur = None
    for encodage in ("utf-8", "cp1252"):
        for sep in (",", ";"):
            try:
                df = pd.read_csv(chemin, sep=sep, encoding=encodage, dtype=str)
                # Une lecture avec le mauvais séparateur donne 1 colonne — on filtre
                if len(df.columns) >= 4:
                    return _normaliser_colonnes(df)
            except (UnicodeDecodeError, pd.errors.ParserError) as e:
                dernier_erreur = e
                continue

    raise ValueError(
        f"Impossible de lire {chemin} (utf-8/cp1252 × ,/; testés) : {dernier_erreur}"
    )


def _normaliser_colonnes(df: pd.DataFrame) -> pd.DataFrame:
    """Renomme les colonnes selon COLONNES_KOXO puis dédoublonne.

    Un export KoXo contient deux colonnes équivalentes pour le badge
    (`badge` et `ID unique`). Après normalisation les deux visent
    `num_badge` — on garde la première non vide.
    """
    nouvelles = {}
    for col in df.columns:
        cle = _normaliser_libelle(col)
        nouvelles[col] = COLONNES_KOXO.get(cle, cle.replace(" ", "_"))
    df = df.rename(columns=nouvelles)

    # Dédoublonne : si deux colonnes ont le même nom, fusionne en gardant
    # la première valeur non nulle (row-wise), puis drop les colonnes en trop.
    if df.columns.duplicated().any():
        fusionne = {}
        for nom in df.columns.unique():
            sous_df = df.loc[:, df.columns == nom]
            if sous_df.shape[1] == 1:
                fusionne[nom] = sous_df.iloc[:, 0]
            else:
                # bfill horizontal : première valeur non-null de chaque row
                fusionne[nom] = sous_df.bfill(axis=1).iloc[:, 0]
        df = pd.DataFrame(fusionne)

    # Nettoyage : trim, string vide → NaN
    for col in df.columns:
        serie = df[col]
        if serie.dtype == object:
            df[col] = serie.astype(str).str.strip().replace({"": None, "nan": None})

    # num_badge : entier
    if "num_badge" in df.columns:
        df["num_badge"] = pd.to_numeric(df["num_badge"], errors="coerce").astype("Int64")

    # Retire les lignes sans identifiant utile (nom vide → probablement en-tête dupliqué)
    if "nom" in df.columns:
        df = df.dropna(subset=["nom"]).reset_index(drop=True)

    return df


def deduire_id_charlemagne(num_badge: int | None, type_personne: str) -> int | None:
    """Formule inverse `badge → id_charlemagne`.

    - Élève : `id = (badge - 10000) / 10`
    - Adulte : `id = badge` (numérotation directe)

    Vérifiée sur 1820/1820 lignes de l'export historique.
    """
    if num_badge is None:
        return None
    if type_personne == "eleve":
        candidat = (int(num_badge) - 10000) / 10
        if candidat < 0 or candidat != int(candidat):
            return None
        return int(candidat)
    return int(num_badge)
