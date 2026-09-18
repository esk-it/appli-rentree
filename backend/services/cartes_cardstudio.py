"""Le fichier CardStudio, fabriqué depuis le référentiel.

## Ce qui change par rapport à la version précédente

La version précédente **réclamait un export de Charlemagne** à chaque
utilisation, puis le filtrait. Le raisonnement tenait : quatre des treize
colonnes — `Code niveau`, `Code établissement`, `Photo`, `Date Entrée pour
tri` — n'existaient nulle part dans le référentiel, et un fichier sans le
chemin des photos fait imprimer des badges sans visage.

Mais l'usage réel est : *« voilà les élèves dont je veux les cartes, donne-moi
le fichier »*. Exiger un export à chaque fois, puis faire saisir des numéros
de badge à la main pour désigner des élèves, c'est demander à quelqu'un de
connaître par cœur ce que le programme a sous la main.

Les quatre colonnes manquantes se traitent chacune pour ce qu'elle est :

- **`Photo`** se constate. Le partage est lu, le fichier est trouvé, son
  chemin est écrit. C'est plus sûr que ce que faisait Charlemagne, qui
  reconstruisait le nom sans vérifier qu'il existe.
- **`Code niveau`** et **`Code établissement`** sont des attributs de la
  **classe** — 64 classes, 64 niveaux, aucune ambiguïté sur l'export de
  référence. Ils vivent donc dans la table de correspondance, à côté des
  unités d'organisation, et s'apprennent une fois.
- **`Date Entrée pour tri`** est la date d'entrée réelle dans
  l'établissement, parfois sept ans en arrière. Elle ne se déduit de rien :
  elle s'apprend elle aussi, et se garde.

D'où `apprendre_depuis_export` : un export CardStudio de Charlemagne, passé
**une fois**, enseigne au programme ce qu'il ignorait. Ensuite il n'en a
plus besoin.

## Les chambres

Charlemagne ajoute en fin d'export des lignes `INTERNAT` qui ne portent que
deux valeurs : `Etablissement` vaut `INTERNAT`, `Chambres` porte le nom de
la chambre. Ni badge, ni élève.

C'est une **liste de lieux**, pas une affectation — rien ne dit qui dort où,
et le référentiel ne le sait pas davantage. Mais la liste, elle, est stable :
les soixante-dix-sept chambres de l'internat ne changent pas d'une année sur
l'autre. Elle est donc écrite ici, et reconduite telle quelle.

## Ce qui n'est jamais inventé

Un élève sans photo constatée sort avec `Photo` et `NomFichierPhoto` vides,
et **le rapport le nomme**. Une classe dont les codes ne sont pas connus sort
avec ces colonnes vides, et le rapport la nomme aussi. Remplir au jugé
produirait un fichier qui a l'air complet — et une carte fausse ne se
découvre qu'une fois imprimée.
"""
from __future__ import annotations

import io
import re
import unicodedata
from dataclasses import dataclass, field
from datetime import date
from pathlib import Path

import openpyxl
import pandas as pd
from sqlalchemy.orm import Session

from backend.models import AnneeScolaire, Personne, Snapshot, TableCorrespondance
from backend.services.inventaire_photos import (
    InventaireImpossible,
    chemins_attribues,
)

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

Relevé sur les exports de Charlemagne eux-mêmes : 708 lignes `02-COL` → SU,
798 `03-LY` et 166 `04-LP` → KREISKER.
"""

ETABLISSEMENT_INTERNAT = "INTERNAT"

CHAMBRES = [
    *(f"chambre {etage:02d}-{lit:02d}" for etage in range(2, 22) for lit in (1, 2)),
    *(f"chambre {numero}" for numero in range(22, 59)),
]
"""Les soixante-dix-sept chambres de l'internat.

Relevées sur l'export CardStudio de septembre 2026, à l'identique :
quarante chambres doubles numérotées `02-01` à `21-02`, puis trente-sept
simples de `22` à `58`.

Elles sont écrites ici plutôt que relues d'un export parce qu'elles ne
changent pas — un internat ne se reconstruit pas chaque été. Le jour où il
s'agrandit, cette liste est l'endroit à corriger, et le seul.
"""


class CartesImpossibles(Exception):
    """Le fichier ne peut pas être produit, et le message dit pourquoi."""


@dataclass
class CandidatCarte:
    """Un élève tel qu'il se présente au moment de choisir."""

    personne_id: int
    badge: int | None
    nom: str
    prenom: str
    nom_complet: str
    classe: str
    site: str | None
    regime: str | None
    a_une_photo: bool
    codes_connus: bool
    """Vrai si la classe porte son code niveau et son code établissement."""


@dataclass
class RapportCartes:
    nb_cartes: int = 0
    nb_chambres: int = 0
    sans_photo: list[str] = field(default_factory=list)
    classes_sans_codes: list[str] = field(default_factory=list)
    sans_date_entree: int = 0
    photos_indisponibles: str | None = None
    """Renseigné quand le partage n'a pas pu être lu du tout."""
    nom_fichier_suggere: str = "CardStudio.xlsx"


@dataclass
class RapportApprentissage:
    nb_lignes_lues: int = 0
    classes_apprises: list[str] = field(default_factory=list)
    classes_inconnues: list[str] = field(default_factory=list)
    nb_dates_apprises: int = 0
    nb_photos_memorisees: int = 0
    badges_inconnus: int = 0


# ---------------------------------------------------------------------------
# Choisir
# ---------------------------------------------------------------------------


def _annee_en_cours(session: Session, annee_id: int | None) -> AnneeScolaire:
    if annee_id is not None:
        annee = session.get(AnneeScolaire, annee_id)
        if annee is None:
            raise CartesImpossibles(f"Année scolaire {annee_id} inconnue.")
        return annee
    # `est_active` est vrai sur plusieurs années à la fois : c'est le libellé
    # décroissant qui désigne la plus récente, comme partout ailleurs.
    annee = (
        session.query(AnneeScolaire)
        .order_by(AnneeScolaire.libelle.desc())
        .first()
    )
    if annee is None:
        raise CartesImpossibles("Aucune année scolaire dans le référentiel.")
    return annee


def _derniers_snapshots(session: Session, annee_id: int) -> dict[int, Snapshot]:
    derniers: dict[int, Snapshot] = {}
    for sn in session.query(Snapshot).filter(Snapshot.annee_scolaire_id == annee_id):
        prec = derniers.get(sn.personne_id)
        if prec is None or (
            sn.date_ingestion
            and prec.date_ingestion
            and sn.date_ingestion > prec.date_ingestion
        ):
            derniers[sn.personne_id] = sn
    return derniers


def _codes_par_classe(session: Session) -> dict[str, TableCorrespondance]:
    return {
        (t.classe_code_court or "").strip(): t
        for t in session.query(TableCorrespondance).all()
        if (t.classe_code_court or "").strip()
    }


def lister_candidats(
    session: Session,
    *,
    annee_id: int | None = None,
    sites: list[str] | None = None,
    classes: list[str] | None = None,
) -> list[CandidatCarte]:
    """Les élèves parmi lesquels choisir, avec ce qu'il faut savoir d'eux.

    L'état de la photo voyage avec chacun : une carte sans visage est une
    carte à refaire, et c'est **avant** de cocher qu'il faut le voir, pas
    dans un rapport après coup.

    Le partage peut être injoignable — poste hors réseau, partage non monté.
    Ce n'est pas une raison de refuser la liste : on la rend, en disant que
    l'état des photos est inconnu plutôt qu'en le déclarant faux.
    """
    annee = _annee_en_cours(session, annee_id)
    derniers = _derniers_snapshots(session, annee.id)
    codes = _codes_par_classe(session)

    try:
        photos = chemins_attribues(session, annee_id=annee.id)
    except InventaireImpossible:
        photos = {}

    voulus_sites = {s.strip().upper() for s in (sites or []) if s and s.strip()}
    voulus_classes = {c.strip() for c in (classes or []) if c and c.strip()}

    candidats: list[CandidatCarte] = []
    for p in session.query(Personne).filter(Personne.type == "eleve").all():
        sn = derniers.get(p.id)
        if sn is None:
            continue  # pas scolarisé cette année : pas de carte à faire
        classe = (sn.classe or p.classe or "").strip()
        if not classe:
            continue

        correspondance = codes.get(classe)
        site = correspondance.site.nom if correspondance and correspondance.site else None
        if voulus_sites and (site or "").upper() not in voulus_sites:
            continue
        if voulus_classes and classe not in voulus_classes:
            continue

        candidats.append(CandidatCarte(
            personne_id=p.id,
            badge=p.badge,
            nom=p.nom or "",
            prenom=p.prenom or "",
            nom_complet=f"{p.nom or ''} {p.prenom or ''}".strip(),
            classe=classe,
            site=site,
            regime=(sn.regime or p.regime or "").strip() or None,
            a_une_photo=p.id in photos,
            codes_connus=bool(
                correspondance
                and correspondance.code_niveau
                and correspondance.code_etablissement
            ),
        ))

    candidats.sort(key=lambda c: (c.classe, c.nom, c.prenom))
    return candidats


# ---------------------------------------------------------------------------
# Produire
# ---------------------------------------------------------------------------


def _date_pour_tri(valeur: date | None) -> str:
    """`AAAAMMJJ`, la forme que CardStudio trie."""
    return valeur.strftime("%Y%m%d") if valeur else ""


def construire_fichier(
    session: Session,
    *,
    personne_ids: list[int],
    annee_id: int | None = None,
    avec_chambres: bool = False,
    intitule: str = "",
) -> tuple[bytes, RapportCartes]:
    """Le classeur à importer dans CardStudio, pour les élèves désignés.

    Args:
        personne_ids: les élèves cochés. C'est la seule désignation admise —
            un identifiant de référentiel, pas un numéro de badge recopié.
        avec_chambres: ajouter en fin de fichier les lignes de chambre.
        intitule: un mot pour nommer le fichier (« cartes oubliées »).

    Raises:
        CartesImpossibles: aucun élève désigné.
    """
    if not personne_ids:
        raise CartesImpossibles(
            "Aucun élève coché. Le fichier serait vide, et CardStudio "
            "n'accepte qu'un fichier par projet."
        )

    annee = _annee_en_cours(session, annee_id)
    derniers = _derniers_snapshots(session, annee.id)
    codes = _codes_par_classe(session)
    rapport = RapportCartes()

    try:
        photos = chemins_attribues(session, annee_id=annee.id)
    except InventaireImpossible as e:
        photos = {}
        rapport.photos_indisponibles = str(e)

    voulus = list(dict.fromkeys(personne_ids))
    personnes = {
        p.id: p
        for p in session.query(Personne).filter(Personne.id.in_(voulus)).all()
    }

    lignes: list[dict] = []
    classes_sans_codes: set[str] = set()
    for pid in voulus:
        p = personnes.get(pid)
        if p is None:
            continue
        sn = derniers.get(p.id)
        classe = ((sn.classe if sn else None) or p.classe or "").strip()
        correspondance = codes.get(classe)

        code_etablissement = (
            correspondance.code_etablissement if correspondance else None
        ) or ""
        code_niveau = (correspondance.code_niveau if correspondance else None) or ""
        if not code_etablissement or not code_niveau:
            classes_sans_codes.add(classe or "(sans classe)")

        chemin = photos.get(p.id) or ""
        nom_complet = f"{p.nom or ''} {p.prenom or ''}".strip()
        if not chemin:
            rapport.sans_photo.append(f"{nom_complet} — {classe}")

        date_entree = p.date_entree or (sn.date_entree if sn else None)
        if not date_entree:
            rapport.sans_date_entree += 1

        lignes.append({
            "Etablissement": ETABLISSEMENTS.get(code_etablissement, ""),
            "Code établissement": code_etablissement,
            "Code niveau": code_niveau,
            "Code classe": classe,
            "Num Badge": str(p.badge) if p.badge else "",
            "Code Régime": ((sn.regime if sn else None) or p.regime or "").strip(),
            "Nom et prénom": nom_complet,
            "Nom": p.nom or "",
            "Prénom": p.prenom or "",
            "Photo": chemin,
            "Date Entrée pour tri": _date_pour_tri(date_entree),
            # Écrit en valeur, jamais en formule : CardStudio lit le classeur
            # sans passer par Excel, et une formule sans cache lui est vide.
            "NomFichierPhoto": Path(chemin).name if chemin else "",
            "Chambres": "",
        })

    # L'ordre de l'impression : classe puis nom, pour que la pile qui sort de
    # l'imprimante suive la liste qu'on a cochée.
    lignes.sort(key=lambda l: (l["Code classe"], l["Nom et prénom"]))
    rapport.nb_cartes = len(lignes)

    if avec_chambres:
        # En queue, comme Charlemagne les écrit : ce ne sont pas des élèves,
        # elles n'ont pas à s'intercaler dans le tri.
        lignes.extend(
            {
                **{c: "" for c in COLONNES_CARDSTUDIO},
                "Etablissement": ETABLISSEMENT_INTERNAT,
                "Chambres": chambre,
            }
            for chambre in CHAMBRES
        )
        rapport.nb_chambres = len(CHAMBRES)

    rapport.classes_sans_codes = sorted(classes_sans_codes)
    rapport.sans_photo.sort()
    rapport.nom_fichier_suggere = _nommer(intitule, lignes, rapport.nb_cartes)
    return _encoder_xlsx(lignes), rapport


def _nommer(intitule: str, lignes: list[dict], nb_cartes: int) -> str:
    """Un nom de fichier qui dit ce qu'il contient."""
    morceaux = ["CardStudio"]
    if intitule.strip():
        morceaux.append(intitule.strip())
    else:
        classes = {l["Code classe"] for l in lignes if l["Code classe"]}
        if 0 < len(classes) <= 3:
            morceaux.append("_".join(sorted(classes)))
        else:
            morceaux.append(f"{nb_cartes}cartes")
    nom = "_".join(morceaux)
    return re.sub(r"[^A-Za-z0-9_\-]+", "_", nom) + ".xlsx"


def _encoder_xlsx(lignes: list[dict]) -> bytes:
    """Écrit le classeur. Tout en texte : CardStudio lit des chaînes."""
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


# ---------------------------------------------------------------------------
# Apprendre — une fois, puis plus jamais
# ---------------------------------------------------------------------------

EXTENSIONS_EXPORT = {".htm", ".html", ".xlsx", ".xls"}


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


def _lire_export(contenu: bytes, nom_fichier: str) -> pd.DataFrame:
    suffixe = Path(nom_fichier or "").suffix.lower()
    if suffixe not in EXTENSIONS_EXPORT:
        raise CartesImpossibles(
            f"Extension non reconnue : {suffixe or '(aucune)'}. "
            f"Attendu : {', '.join(sorted(EXTENSIONS_EXPORT))}."
        )
    tampon = io.BytesIO(contenu)
    try:
        if suffixe in (".htm", ".html"):
            # Charlemagne exporte en cp1252 ; lu en UTF-8, le fichier casse
            # sur le premier accent.
            tables = pd.read_html(tampon, encoding="cp1252")
            if not tables:
                raise CartesImpossibles("Aucun tableau dans ce fichier HTM.")
            df = max(tables, key=len)
        else:
            df = pd.read_excel(tampon, engine="xlrd" if suffixe == ".xls" else None)
    except CartesImpossibles:
        raise
    except Exception as e:  # pragma: no cover - dépend du fichier fourni
        raise CartesImpossibles(f"Lecture impossible : {e}") from None
    return df.dropna(how="all")


def _date_depuis_tri(brut: str) -> date | None:
    """`20260901` → une date. Tout le reste → rien, sans bruit."""
    chiffres = re.sub(r"\D", "", brut or "")
    if len(chiffres) != 8:
        return None
    try:
        return date(int(chiffres[:4]), int(chiffres[4:6]), int(chiffres[6:8]))
    except ValueError:
        return None


def apprendre_depuis_export(
    session: Session, *, contenu: bytes, nom_fichier: str
) -> RapportApprentissage:
    """Enseigne au programme ce que seul Charlemagne savait.

    Trois choses, et le fichier n'est plus nécessaire ensuite :

    - le **code niveau** et le **code établissement** de chaque classe,
      rangés dans la table de correspondance ;
    - la **date d'entrée** de chaque élève, rangée au référentiel ;
    - le **chemin de photo** constaté, qui sert à repérer les orphelines
      après un changement de nom.

    Rien n'est écrasé par du vide : un export partiel ne doit pas effacer ce
    qu'un export complet avait appris.

    Raises:
        CartesImpossibles: fichier illisible ou colonnes absentes.
    """
    df = _lire_export(contenu, nom_fichier)
    presentes = {_plier(c): c for c in df.columns}
    reperes = {
        attendue: presentes[_plier(attendue)]
        for attendue in COLONNES_CARDSTUDIO
        if _plier(attendue) in presentes
    }
    manquantes = [c for c in ("Code classe", "Num Badge") if c not in reperes]
    if manquantes:
        raise CartesImpossibles(
            "Ce fichier n'a pas l'air d'un export CardStudio : il manque "
            + ", ".join(f"« {c} »" for c in manquantes)
            + f". Colonnes trouvées : {', '.join(str(c) for c in df.columns)}."
        )

    col = lambda ligne, nom: _texte(ligne[reperes[nom]]) if nom in reperes else ""
    correspondances = _codes_par_classe(session)
    par_badge = {
        p.badge: p
        for p in session.query(Personne).filter(Personne.badge.isnot(None)).all()
    }

    rapport = RapportApprentissage(nb_lignes_lues=len(df))
    apprises: set[str] = set()
    inconnues: set[str] = set()

    for _, ligne in df.iterrows():
        if col(ligne, "Etablissement").upper() == ETABLISSEMENT_INTERNAT:
            continue  # une chambre n'enseigne rien
        classe = col(ligne, "Code classe")
        badge = col(ligne, "Num Badge")
        if not badge:
            continue

        niveau = col(ligne, "Code niveau")
        etablissement = col(ligne, "Code établissement")
        correspondance = correspondances.get(classe)
        if correspondance is None:
            if classe:
                inconnues.add(classe)
        elif niveau or etablissement:
            if niveau and correspondance.code_niveau != niveau:
                correspondance.code_niveau = niveau
                apprises.add(classe)
            if etablissement and correspondance.code_etablissement != etablissement:
                correspondance.code_etablissement = etablissement
                apprises.add(classe)

        personne = par_badge.get(int(badge)) if badge.isdigit() else None
        if personne is None:
            rapport.badges_inconnus += 1
            continue

        entree = _date_depuis_tri(col(ligne, "Date Entrée pour tri"))
        if entree and personne.date_entree != entree:
            personne.date_entree = entree
            rapport.nb_dates_apprises += 1

        chemin = col(ligne, "Photo")
        if chemin and personne.chemin_photo_constate != chemin:
            personne.chemin_photo_constate = chemin
            rapport.nb_photos_memorisees += 1

    session.commit()
    rapport.classes_apprises = sorted(apprises)
    rapport.classes_inconnues = sorted(inconnues)
    return rapport
