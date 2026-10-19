"""Le fichier élèves du portail Sodexo, fabriqué par le programme.

## Pourquoi le programme le fait désormais (19 octobre 2026)

Le fichier naissait d'un classeur Google : on y collait l'édition
Charlemagne « Liste des élèves - Export vers SoHappy » dans l'onglet
Import, l'onglet Export la remettait en forme, et un script en faisait un
CSV. Lu de près, le circuit ne transmettait jamais les réductions :

- le script demande le CSV à Google en collant le numéro de l'onglet sans
  `&gid=` — Google rend alors le **premier** onglet, Import, et non Export ;
- l'Import porte le régime de Charlemagne (D, E, P) dans « Code Régime »,
  et les codes particuliers (10P, 10POGEC…) dans une autre colonne,
  « PassageS » : le portail ne les a jamais reçus. Au 19 octobre, 14 élèves
  partaient en D ou en E au lieu de 10P ou 10POGEC ;
- l'onglet Export sautait en plus 22 lignes de l'Import.

Johann ne voulait pas toucher à un classeur qu'il n'a pas fait : le
programme reprend la règle, et la vérifie.

## La règle

**Code Régime = PassageS s'il est rempli, sinon le régime de Charlemagne.**
C'est la formule de l'onglet Export, la seule de tout le classeur.

## Ce que le portail en fait

MONEWEB Gestion, ligne « Import comptes par badge – CLASSIFICATION 1 –
Elèves » : les colonnes sont repérées par leur **en-tête** ; il lit
`Num Badge` (la clé du compte), `Nom`, `Prénom` et `Code Régime`, qui
devient à la fois l'élément de classification et le **profil de gestion**
— lequel porte la subvention (« Subvention 10% sur formule ogec »). Un
code qui n'existe pas comme profil ne trouve rien : le fichier s'arrête
donc ici plutôt qu'au portail. Ajout et modification, jamais suppression.

Le fichier garde les neuf colonnes de l'onglet Export, dans son ordre, et
la forme exacte du dernier CSV accepté : UTF-8 sans BOM, point-virgule,
fins de ligne LF.
"""
from __future__ import annotations

import csv
import io
import re
import unicodedata
from collections import Counter
from dataclasses import dataclass, field
from datetime import date

from sqlalchemy.orm import Session


class FichierSodexoImpossible(ValueError):
    """L'édition ne peut pas être lue — le message dit pourquoi."""


PROFILS_ELEVES_DEFAUT = ["D", "E", "P", "10P", "10POGEC", "33P", "50P", "GRATUITE"]
"""Les profils de gestion élèves du portail, relevés le 19 octobre 2026."""

COLONNES_SORTIE = [
    "Code établissement", "Code niveau", "Code classe", "Num Badge", "Code Régime",
    "Nom et prénom", "Nom", "Prénom", "Photo",
]


def _plat(texte) -> str:
    decompose = unicodedata.normalize("NFD", str(texte or "").strip().lower())
    return re.sub(r"\s+", " ", "".join(c for c in decompose if unicodedata.category(c) != "Mn"))


# L'en-tête de l'édition, aplati, vers le nom qu'on lui donne ici. « Code
# Régime » y figure deux fois : on garde la première valeur non vide.
COLONNES_EDITION = {
    "code etablissement": "etablissement",
    "code niveau": "niveau",
    "code classe": "classe",
    "num badge": "badge",
    "nom et prenom": "nom_prenom",
    "nom": "nom",
    "prenom": "prenom",
    "photo": "photo",
    "code regime": "regime",
    "passages": "passage",
}
REQUISES = ("badge", "nom", "prenom", "regime")


@dataclass
class EleveSodexo:
    ligne: int
    """Ligne de l'édition, pour retrouver l'élève dans Charlemagne."""
    badge: str
    nom: str
    prenom: str
    regime: str
    """Le régime de Charlemagne : D, E, P."""
    passage: str = ""
    """Le code particulier de Charlemagne, s'il y en a un : 10P, 10POGEC…"""
    etablissement: str = ""
    niveau: str = ""
    classe: str = ""
    nom_prenom: str = ""
    photo: str = ""

    @property
    def code(self) -> str:
        """Ce que le portail recevra : le code particulier d'abord."""
        return self.passage or self.regime


@dataclass
class RapportSodexo:
    nb_lignes_lues: int
    eleves: list[EleveSodexo] = field(default_factory=list)
    erreurs: list[str] = field(default_factory=list)
    """Ce qui arrête la fabrication : le portail importerait mal."""
    avertissements: list[str] = field(default_factory=list)
    absents: list[str] = field(default_factory=list)
    """Inscrits cette année, sur un site du fichier, que l'édition ne porte pas."""
    inconnus: list[str] = field(default_factory=list)
    """Badges de l'édition que le référentiel ne connaît pas."""

    @property
    def par_code(self) -> dict[str, int]:
        return dict(Counter(e.code for e in self.eleves).most_common())

    @property
    def particuliers(self) -> list[EleveSodexo]:
        """Ceux dont le code n'est pas le régime : les réductions, la gratuité."""
        return sorted((e for e in self.eleves if e.passage),
                      key=lambda e: (e.passage, e.classe, e.nom, e.prenom))

    @property
    def pret(self) -> bool:
        return not self.erreurs and bool(self.eleves)


# ---------------------------------------------------------------------------
# Lire l'édition
# ---------------------------------------------------------------------------


def _cellules(contenu: bytes, nom_fichier: str) -> list[list[str]]:
    """Les lignes de l'édition, en texte — xlsx, xls ou csv."""
    extension = (nom_fichier or "").lower().rsplit(".", 1)[-1]
    if extension in ("xlsx", "xlsm", "xls"):
        import pandas as pd

        try:
            tableau = pd.read_excel(
                io.BytesIO(contenu), header=None, dtype=str,
                engine="xlrd" if extension == "xls" else None,
            )
        except Exception as e:
            raise FichierSodexoImpossible(f"Le classeur ne se lit pas : {e}") from None
        return [["" if v is None or str(v) == "nan" else str(v) for v in ligne]
                for ligne in tableau.itertuples(index=False)]
    for encodage in ("utf-8-sig", "cp1252"):
        try:
            texte = contenu.decode(encodage)
            break
        except UnicodeDecodeError:
            continue
    else:
        raise FichierSodexoImpossible("Le fichier n'est ni en UTF-8 ni en cp1252.")
    premiere = texte.split("\n", 1)[0]
    separateur = ";" if premiere.count(";") >= premiere.count(",") else ","
    return [ligne for ligne in csv.reader(io.StringIO(texte), delimiter=separateur)]


def _badge(valeur: str) -> str:
    """« 99880 », « 99880.0 » → « 99880 » ; le reste tel quel, pour le signaler."""
    v = (valeur or "").strip()
    if re.fullmatch(r"\d+\.0+", v):
        v = v.split(".")[0]
    return v


def lire_edition(contenu: bytes, nom_fichier: str) -> tuple[list[EleveSodexo], int]:
    """Les élèves de l'édition « Liste des élèves - Export vers SoHappy »."""
    lignes = _cellules(contenu, nom_fichier)
    for i, ligne in enumerate(lignes[:15]):
        plats = [_plat(c) for c in ligne]
        if "num badge" in plats and "code regime" in plats:
            entete, debut = plats, i + 1
            break
    else:
        raise FichierSodexoImpossible(
            "Ce fichier n'est pas l'édition « Liste des élèves - Export vers SoHappy » : "
            "aucune ligne d'en-tête ne porte « Num Badge » et « Code Régime »."
        )
    positions: dict[str, list[int]] = {}
    for k, nom in enumerate(entete):
        if nom in COLONNES_EDITION:
            positions.setdefault(COLONNES_EDITION[nom], []).append(k)
    manquent = [c for c in REQUISES if c not in positions]
    if manquent:
        raise FichierSodexoImpossible(f"Colonnes absentes de l'édition : {', '.join(manquent)}.")

    def valeur(ligne: list[str], cle: str) -> str:
        for k in positions.get(cle, []):
            if k < len(ligne) and str(ligne[k]).strip():
                return str(ligne[k]).strip()
        return ""

    eleves = []
    for numero, ligne in enumerate(lignes[debut:], start=debut + 1):
        if not any(str(c).strip() for c in ligne):
            continue
        eleves.append(EleveSodexo(
            ligne=numero, badge=_badge(valeur(ligne, "badge")),
            nom=valeur(ligne, "nom"), prenom=valeur(ligne, "prenom"),
            regime=valeur(ligne, "regime"), passage=valeur(ligne, "passage"),
            etablissement=valeur(ligne, "etablissement"), niveau=valeur(ligne, "niveau"),
            classe=valeur(ligne, "classe"), nom_prenom=valeur(ligne, "nom_prenom"),
            photo=valeur(ligne, "photo"),
        ))
    return eleves, len(lignes) - debut


# ---------------------------------------------------------------------------
# Vérifier et fabriquer
# ---------------------------------------------------------------------------


def _qui(e: EleveSodexo) -> str:
    return f"{e.prenom} {e.nom} ({e.classe or '?'}, badge {e.badge or '—'})"


def fabriquer(
    session: Session | None,
    contenu: bytes,
    nom_fichier: str,
    *,
    profils: list[str] | None = None,
    annee_id: int | None = None,
) -> RapportSodexo:
    """Lit l'édition, applique la règle, et dit ce qui ne passerait pas."""
    lus, nb_lignes = lire_edition(contenu, nom_fichier)
    rapport = RapportSodexo(nb_lignes_lues=nb_lignes)
    connus = {p.strip() for p in (profils or PROFILS_ELEVES_DEFAUT) if p.strip()}

    par_badge: dict[str, EleveSodexo] = {}
    doublons_identiques = 0
    for e in lus:
        if not e.badge:
            rapport.erreurs.append(f"Ligne {e.ligne} sans badge — {_qui(e)} : le portail ne saurait pas quel compte créer.")
            continue
        if not e.badge.isdigit():
            rapport.erreurs.append(f"Ligne {e.ligne} : badge « {e.badge} » qui n'est pas un numéro — {_qui(e)}.")
            continue
        if not e.code:
            rapport.erreurs.append(f"Ligne {e.ligne} sans régime — {_qui(e)}.")
            continue
        if e.code not in connus:
            rapport.erreurs.append(
                f"{_qui(e)} : le code « {e.code} » n'existe pas comme profil de gestion "
                "dans le portail. Corrige-le dans Charlemagne, ou ajoute le profil aux "
                "Paramètres s'il vient d'être créé chez Sodexo."
            )
            continue
        deja = par_badge.get(e.badge)
        if deja is None:
            par_badge[e.badge] = e
        elif (deja.nom, deja.prenom, deja.code, deja.classe) == (e.nom, e.prenom, e.code, e.classe):
            doublons_identiques += 1
        else:
            rapport.erreurs.append(
                f"Le badge {e.badge} porte deux élèves différents : {_qui(deja)} et {_qui(e)}."
            )
    rapport.eleves = sorted(par_badge.values(), key=lambda e: e.ligne)
    if doublons_identiques:
        rapport.avertissements.append(
            f"{doublons_identiques} ligne(s) en double dans l'édition, à l'identique : "
            "gardées une seule fois."
        )
    if session is not None:
        _recouper(session, rapport, annee_id)
    return rapport


def _recouper(session: Session, rapport: RapportSodexo, annee_id: int | None) -> None:
    """Le référentiel en regard : personne d'inscrit ne doit manquer.

    Les sites servis sont ceux des élèves du fichier — NDK et SU ; NDE a
    son propre service et ne figure pas dans l'édition.
    """
    from backend.models import AnneeScolaire, Personne, Site, Snapshot

    annee = (session.get(AnneeScolaire, annee_id) if annee_id else
             session.query(AnneeScolaire).order_by(AnneeScolaire.libelle.desc()).first())
    if annee is None:
        return
    badges = {int(e.badge) for e in rapport.eleves}
    par_badge = {p.badge: p for p in session.query(Personne).filter(Personne.badge.in_(badges or {0}))}
    rapport.inconnus = [_qui(e) for e in rapport.eleves if int(e.badge) not in par_badge]
    sites = {p.site_id for p in par_badge.values() if p.site_id}
    if not sites:
        return
    noms_sites = {s.id: s.nom for s in session.query(Site)}
    inscrits = (
        session.query(Personne)
        .join(Snapshot, Snapshot.personne_id == Personne.id)
        .filter(Snapshot.annee_scolaire_id == annee.id, Personne.type == "eleve",
                Personne.site_id.in_(sites))
        .distinct()
        .all()
    )
    rapport.absents = sorted(
        f"{p.prenom} {p.nom} ({noms_sites.get(p.site_id, '?')}, {p.classe or '?'})"
        for p in inscrits if p.badge not in badges
    )
    if rapport.absents:
        rapport.avertissements.append(
            f"{len(rapport.absents)} élève(s) inscrit(s) en {annee.libelle} à "
            f"{', '.join(sorted(noms_sites[s] for s in sites))} ne sont pas dans l'édition : "
            "ils n'auront pas de compte au self."
        )
    if rapport.inconnus:
        rapport.avertissements.append(
            f"{len(rapport.inconnus)} badge(s) de l'édition inconnu(s) du référentiel : "
            "un export Charlemagne plus récent que le dernier ingéré, sans doute."
        )


def _propre(v: str) -> str:
    """Un point-virgule ou un saut de ligne dans un nom décalerait les colonnes."""
    return re.sub(r"[;\r\n]+", " ", v or "").strip()


def en_csv(rapport: RapportSodexo) -> bytes:
    """Le fichier à importer, à la forme exacte de ce que le portail accepte."""
    lignes = [";".join(COLONNES_SORTIE)]
    for e in rapport.eleves:
        lignes.append(";".join(_propre(v) for v in (
            e.etablissement, e.niveau, e.classe, e.badge, e.code,
            e.nom_prenom or f"{e.nom} {e.prenom}", e.nom, e.prenom, e.photo,
        )))
    return "\n".join(lignes).encode("utf-8")


def nom_du_fichier(jour: date | None = None) -> str:
    return f"Sodexo_eleves_{(jour or date.today()).isoformat()}.csv"
