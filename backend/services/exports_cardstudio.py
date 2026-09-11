"""L'export CardStudio : découper le fichier de Charlemagne, pas le fabriquer.

## Pourquoi le programme ne fabrique pas ce fichier

CardStudio veut treize colonnes :

    Etablissement ; Code établissement ; Code niveau ; Code classe ;
    Num Badge ; Code Régime ; Nom et prénom ; Nom ; Prénom ; Photo ;
    Date Entrée pour tri ; NomFichierPhoto ; Chambres

Quatre d'entre elles — `Code niveau`, `Code établissement`, `Photo` et
`Date Entrée pour tri` — ne sont **nulle part** dans le référentiel. Mesuré
sur la base de la rentrée 2026-2027 : zéro valeur sur 2132 snapshots, pour
les quatre. Le numéro de chambre n'y est pas davantage.

La version précédente les produisait quand même, en laissant `Photo` vide
et en devinant le reste. CardStudio ouvrait le fichier sans une seule
photographie. Un export qui rend un fichier inutilisable est pire que pas
d'export : on croit avoir avancé.

Charlemagne, lui, sait écrire ce fichier — c'est un export dédié, qui porte
le chemin réseau complet de chaque portrait. C'est de là qu'il doit venir.

## Ce que le programme apporte, et que Charlemagne ne sait pas

**Choisir.** CardStudio n'accepte qu'un seul fichier par projet : une fois
importé, on ne peut plus rien y ajouter. Il faut donc pouvoir décider, avant
d'importer, qui entre — un site, une classe, une poignée d'élèves, ou tout
le monde. Charlemagne sort le fichier entier, et rien d'autre.

La table de correspondance sait que « 35 » est au collège et « T_STMG2 » au
lycée : c'est elle qui rend le filtre par site possible.

**Compléter ce que l'export omet.** Selon le profil choisi dans Charlemagne,
l'export sort dix colonnes ou treize. Les trois qui peuvent manquer se
déduisent :

- `NomFichierPhoto` est le nom de fichier contenu dans `Photo`. On l'écrit
  **en valeur**, jamais en formule : CardStudio lit le classeur sans passer
  par Excel, et une formule sans valeur en cache lui apparaît vide.
- `Etablissement` se déduit de `Code établissement` (voir `ETABLISSEMENTS`).

## Les chambres, et ce qu'on ne peut pas en faire

Charlemagne ajoute à la fin de l'export des lignes `INTERNAT` — soixante-dix-sept
sur celui de septembre 2026. **Elles ne portent que deux valeurs** :
`Etablissement` vaut `INTERNAT`, `Chambres` vaut « chambre 02-01 ». Ni numéro
de badge, ni nom, ni classe.

C'est donc une **liste de chambres**, pas une affectation. Rien dans ce
fichier ne dit quel élève occupe quelle chambre, et le référentiel ne le
sait pas davantage. On ne peut pas remplir la colonne `Chambres` par élève :
la donnée n'existe nulle part.

La case à cocher fait donc la seule chose honnête — reconduire ces lignes
telles quelles, en fin de fichier, pour retrouver exactement ce que
Charlemagne produit. Décochée, elles sont écartées : ce sont des lignes sans
personne, qui n'ont pas à peupler un projet de badges.

## Ce que la répartition ne touche pas

Rien du contenu. Chaque ligne est réémise **telle quelle** — mêmes valeurs,
même ordre de colonnes. Le seul geste est de choisir qui entre, et de
remplir ce qui manquait. C'est ce qui rend le résultat vérifiable.

## Les lignes rendues à part

- **Écartées** : code classe absent de la table de correspondance. Elles ne
  sont dans aucun fichier, et il faut le savoir — sans quoi un élève
  disparaît sans bruit.
- **Inconnues du référentiel** : présentes dans Charlemagne, jamais
  ingérées. Le fichier les emporte quand même, mais le rapport les signale.
"""
from __future__ import annotations

import io
import re
import unicodedata
from dataclasses import dataclass, field
from pathlib import Path

import openpyxl
import pandas as pd
from sqlalchemy.orm import Session

from backend.models import Personne, TableCorrespondance

COLONNES_CARDSTUDIO = [
    "Etablissement", "Code établissement", "Code niveau", "Code classe",
    "Num Badge", "Code Régime", "Nom et prénom", "Nom", "Prénom",
    "Photo", "Date Entrée pour tri", "NomFichierPhoto", "Chambres",
]

ETABLISSEMENTS = {
    "02-COL": "SU",
    "03-LY": "KREISKER",
    "04-LP": "KREISKER",
}
"""Libellé attendu par CardStudio pour chaque code d'établissement.

Relevé sur les exports de Charlemagne eux-mêmes. Quand le fichier porte
déjà la colonne `Etablissement`, c'est elle qui fait foi : cette table ne
sert qu'à la reconstituer quand elle manque.
"""

ETABLISSEMENT_INTERNAT = "INTERNAT"
"""Valeur que Charlemagne met dans `Etablissement` sur les lignes de chambre."""

EXTENSIONS = {".htm", ".html", ".xlsx", ".xls"}


class ExportImpossible(Exception):
    """Le fichier fourni n'est pas un export CardStudio exploitable."""


@dataclass
class LigneEcartee:
    badge: str
    nom: str
    classe: str
    motif: str


@dataclass
class RapportExportCardStudio:
    nb_lignes_lues: int = 0
    nb_lignes_retenues: int = 0
    colonnes_completees: list[str] = field(default_factory=list)
    ecartees: list[LigneEcartee] = field(default_factory=list)
    inconnus_referentiel: list[str] = field(default_factory=list)
    chambres_reportees: int = 0
    sites_rencontres: list[str] = field(default_factory=list)
    classes_rencontrees: list[str] = field(default_factory=list)
    nom_fichier_suggere: str = "CardStudio.xlsx"


def _plier(libelle: str) -> str:
    """Réduit un libellé de colonne à ses lettres, sans accent ni casse."""
    s = unicodedata.normalize("NFD", str(libelle or ""))
    s = "".join(c for c in s if unicodedata.category(c) != "Mn")
    return "".join(c for c in s.upper() if c.isalnum())


def _texte(v) -> str:
    """Rend une cellule en texte, sans le `.0` que pandas colle aux entiers."""
    if v is None or (isinstance(v, float) and v != v):
        return ""
    if isinstance(v, float) and v.is_integer():
        return str(int(v))
    return str(v).strip()


def _lire(contenu: bytes, nom_fichier: str) -> pd.DataFrame:
    """Lit l'export en conservant les libellés d'origine.

    Le parseur d'ingestion normalise les noms de colonnes ; ici il faut les
    garder tels quels, puisqu'ils ressortent dans le fichier produit.
    """
    suffixe = Path(nom_fichier or "").suffix.lower()
    if suffixe not in EXTENSIONS:
        raise ExportImpossible(
            f"Extension non reconnue : {suffixe or '(aucune)'}. "
            f"Attendu : {', '.join(sorted(EXTENSIONS))}."
        )
    tampon = io.BytesIO(contenu)
    try:
        if suffixe in (".htm", ".html"):
            # Charlemagne exporte en cp1252 ; lu en UTF-8, le fichier casse
            # sur le premier accent.
            tables = pd.read_html(tampon, encoding="cp1252")
            if not tables:
                raise ExportImpossible("Aucun tableau dans ce fichier HTM.")
            df = max(tables, key=len)
        else:
            df = pd.read_excel(tampon, engine="xlrd" if suffixe == ".xls" else None)
    except ExportImpossible:
        raise
    except Exception as e:  # pragma: no cover - dépend du fichier fourni
        raise ExportImpossible(f"Lecture impossible : {e}") from None
    return df.dropna(how="all")


def _reperer_colonnes(df: pd.DataFrame) -> dict[str, str]:
    """Associe chaque colonne attendue à celle du fichier, accents mis à part."""
    presentes = {_plier(c): c for c in df.columns}
    reperes = {}
    for attendue in COLONNES_CARDSTUDIO:
        trouvee = presentes.get(_plier(attendue))
        if trouvee is not None:
            reperes[attendue] = trouvee
    obligatoires = ["Num Badge", "Code classe", "Nom", "Prénom"]
    manquantes = [c for c in obligatoires if c not in reperes]
    if manquantes:
        raise ExportImpossible(
            "Ce fichier n'a pas l'air d'un export CardStudio : il manque "
            + ", ".join(f"« {c} »" for c in manquantes)
            + f". Colonnes trouvées : {', '.join(str(c) for c in df.columns)}."
        )
    return reperes


def _sites_par_classe(session: Session) -> dict[str, str]:
    """Code classe → nom du site, d'après la table de correspondance."""
    par_classe = {}
    for t in session.query(TableCorrespondance).all():
        code = (t.classe_code_court or "").strip()
        if code and t.site is not None:
            par_classe[code] = t.site.nom
    return par_classe


def _badges_connus(session: Session) -> set[str]:
    return {
        str(b)
        for (b,) in session.query(Personne.badge).filter(Personne.badge.isnot(None))
    }


def repartir_export_cardstudio(
    session: Session,
    *,
    contenu: bytes,
    nom_fichier: str,
    sites: list[str] | None = None,
    classes: list[str] | None = None,
    badges: list[str] | None = None,
    avec_chambres: bool = False,
) -> tuple[bytes, RapportExportCardStudio]:
    """Filtre l'export CardStudio de Charlemagne et rend un XLSX prêt à importer.

    Args:
        contenu: l'export tel que Charlemagne l'a écrit.
        nom_fichier: son nom, dont on tire l'extension.
        sites: noms de sites à garder (`["NDK"]`, `["NDK", "SU"]`). Vide = tous.
        classes: codes classe à garder. Vide = toutes.
        badges: numéros de badge à garder. Vide = tous.
        avec_chambres: reconduire en fin de fichier les lignes `INTERNAT` de
            Charlemagne — une liste de chambres, sans élève attaché.

    Les trois filtres se cumulent. Un élève doit satisfaire chacun de ceux
    qui sont renseignés.

    Raises:
        ExportImpossible: fichier illisible ou colonnes absentes.
    """
    df = _lire(contenu, nom_fichier)
    reperes = _reperer_colonnes(df)
    rapport = RapportExportCardStudio(nb_lignes_lues=len(df))

    col = lambda ligne, nom: _texte(ligne[reperes[nom]]) if nom in reperes else ""
    par_classe = _sites_par_classe(session)
    connus = _badges_connus(session)

    voulus_sites = {s.strip().upper() for s in (sites or []) if s and s.strip()}
    voulus_classes = {c.strip() for c in (classes or []) if c and c.strip()}
    voulus_badges = {_texte(b) for b in (badges or []) if _texte(b)}

    # Les lignes de chambre, mises de côté. Elles ne désignent personne : on
    # les reconduit à l'identique si la case est cochée, sans chercher à les
    # rattacher à un élève — rien ne le permet.
    lignes_chambres: list[dict] = []
    for _, ligne in df.iterrows():
        if col(ligne, "Etablissement").upper() == ETABLISSEMENT_INTERNAT:
            chambre = col(ligne, "Chambres")
            if chambre:
                lignes_chambres.append({
                    **{c: "" for c in COLONNES_CARDSTUDIO},
                    "Etablissement": ETABLISSEMENT_INTERNAT,
                    "Chambres": chambre,
                })

    retenues: list[dict] = []
    vus_sites: set[str] = set()
    vus_classes: set[str] = set()
    completees: set[str] = set()

    for _, ligne in df.iterrows():
        badge = col(ligne, "Num Badge")
        classe = col(ligne, "Code classe")
        nom_complet = col(ligne, "Nom et prénom") or (
            f"{col(ligne, 'Nom')} {col(ligne, 'Prénom')}".strip()
        )
        if not badge:
            continue
        if col(ligne, "Etablissement").upper() == ETABLISSEMENT_INTERNAT:
            continue            # doublon de chambre, replié plus haut

        site = par_classe.get(classe)
        if site is None:
            rapport.ecartees.append(LigneEcartee(
                badge=badge, nom=nom_complet, classe=classe,
                motif="code classe absent de la table de correspondance",
            ))
            continue
        vus_sites.add(site)
        vus_classes.add(classe)

        if voulus_sites and site.upper() not in voulus_sites:
            continue
        if voulus_classes and classe not in voulus_classes:
            continue
        if voulus_badges and badge not in voulus_badges:
            continue

        if badge not in connus:
            rapport.inconnus_referentiel.append(f"{nom_complet} ({badge})")

        chemin_photo = col(ligne, "Photo")
        nom_photo = col(ligne, "NomFichierPhoto")
        if not nom_photo and chemin_photo:
            nom_photo = chemin_photo.rsplit("\\", 1)[-1]
            completees.add("NomFichierPhoto")
        elif nom_photo.startswith("="):
            # Charlemagne écrit parfois une formule ; CardStudio n'en fait rien.
            nom_photo = chemin_photo.rsplit("\\", 1)[-1] if chemin_photo else ""
            completees.add("NomFichierPhoto")

        etablissement = col(ligne, "Etablissement")
        if not etablissement:
            etablissement = ETABLISSEMENTS.get(col(ligne, "Code établissement"), "")
            if etablissement:
                completees.add("Etablissement")

        retenues.append({
            "Etablissement": etablissement,
            "Code établissement": col(ligne, "Code établissement"),
            "Code niveau": col(ligne, "Code niveau"),
            "Code classe": classe,
            "Num Badge": badge,
            "Code Régime": col(ligne, "Code Régime"),
            "Nom et prénom": nom_complet,
            "Nom": col(ligne, "Nom"),
            "Prénom": col(ligne, "Prénom"),
            "Photo": chemin_photo,
            "Date Entrée pour tri": col(ligne, "Date Entrée pour tri"),
            "NomFichierPhoto": nom_photo,
            "Chambres": "",
        })

    # L'ordre de l'impression : classe puis nom, pour que la pile qui sort
    # de l'imprimante suive la liste que l'on coche.
    retenues.sort(key=lambda l: (l["Code classe"], l["Nom et prénom"]))

    # Compté avant les chambres : le rapport annonce des élèves, et une
    # ligne de chambre n'en est pas un.
    rapport.nb_lignes_retenues = len(retenues)

    if avec_chambres:
        # En queue, comme Charlemagne les écrit : ce ne sont pas des élèves,
        # elles n'ont pas à s'intercaler dans le tri.
        retenues.extend(lignes_chambres)
        rapport.chambres_reportees = len(lignes_chambres)
    rapport.colonnes_completees = sorted(completees)
    rapport.sites_rencontres = sorted(vus_sites)
    rapport.classes_rencontrees = sorted(vus_classes)
    rapport.nom_fichier_suggere = _nommer(voulus_sites, voulus_classes, voulus_badges)

    return _encoder_xlsx(retenues), rapport


def _nommer(sites: set[str], classes: set[str], badges: set[str]) -> str:
    """Un nom de fichier qui dit ce qu'il contient."""
    morceaux = ["CardStudio"]
    if sites:
        morceaux.append("_".join(sorted(sites)))
    if classes:
        morceaux.append("_".join(sorted(classes)) if len(classes) <= 3
                        else f"{len(classes)}classes")
    if badges:
        morceaux.append(f"{len(badges)}eleves")
    if len(morceaux) == 1:
        morceaux.append("complet")
    nom = "_".join(morceaux)
    return re.sub(r"[^A-Za-z0-9_\-]+", "_", nom) + ".xlsx"


def _encoder_xlsx(lignes: list[dict]) -> bytes:
    """Écrit le classeur. Tout en texte : CardStudio lit des chaînes.

    Le classeur porte une feuille unique, et pas la moindre formule — la
    valeur est dans la cellule, point. C'est ce que CardStudio sait lire,
    lui qui ouvre le fichier sans passer par Excel.
    """
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = "Feuil1"
    ws.append(COLONNES_CARDSTUDIO)
    for l in lignes:
        ws.append([l.get(c, "") for c in COLONNES_CARDSTUDIO])
    for cellule in ws[1]:
        cellule.font = openpyxl.styles.Font(bold=True)
    buf = io.BytesIO()
    wb.save(buf)
    return buf.getvalue()
