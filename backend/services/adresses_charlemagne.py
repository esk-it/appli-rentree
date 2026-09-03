"""Renvoyer à Charlemagne les adresses qu'il ne connaît pas.

## Pourquoi ce sens-là

Charlemagne est la source pour l'état civil, la classe et le badge. Il ne
l'est pas pour l'adresse de messagerie : les comptes se créent ici, après
l'export de rentrée. Sa colonne `Email` reste donc vide pour toute la
promotion entrante — à la rentrée 2026, trois cent soixante-neuf élèves,
c'est-à-dire les sixièmes et les secondes au complet.

Le reste de l'établissement s'appuie sur cette colonne : c'est elle que
Charlemagne réexporte vers PMB, vers SoHappy, vers les listes de diffusion.
Une colonne vide se propage partout.

## La règle : ne proposer que des faits

Une adresse du référentiel a trois origines possibles — **constatée** (lue
dans Google), **attribuée** (une homonymie tranchée), ou **calculée**
(`prenom.nom@domaine`, une hypothèse). Sur les trois cent soixante-neuf
lignes à remplir, trois cent soixante et une venaient d'un calcul.

Pousser un calcul dans Charlemagne propagerait l'erreur au lieu de la
corriger. Chaque adresse proposée est donc **confrontée à l'annuaire
Google** avant d'entrer dans le fichier. Sans liste de comptes, rien n'est
proposé : les lignes partent en « à vérifier » plutôt qu'en fichier
d'import.

## Ce que la confrontation distingue

| Constat | Ce que ça veut dire |
|---|---|
| `a_remplir` | Charlemagne n'a rien, et l'adresse existe dans Google |
| `a_verifier` | Charlemagne n'a rien, et l'adresse n'a pas pu être confirmée |
| `a_corriger` | Charlemagne porte une adresse d'école **qui n'existe pas** |
| `alias_dans_charlemagne` | Charlemagne porte un alias du bon compte — ça marche |
| `referentiel_a_tort` | Google donne raison à Charlemagne : c'est ici qu'il faut corriger |
| `adresse_personnelle` | Le champ contient une adresse de famille, pas le compte |
| `conflit` | Les deux adresses existent mais désignent deux comptes |
| `hors_referentiel` | L'élève est dans Charlemagne, jamais ingéré ici |

Les adresses personnelles ne sont **pas** mises dans le fichier d'import.
Écraser l'adresse d'une famille par le compte de l'élève est peut-être ce
qu'on veut, mais c'est une décision, pas une évidence — et elle est sans
retour.
"""
from __future__ import annotations

import csv
import io
from dataclasses import dataclass, field, replace

from sqlalchemy.orm import Session

from backend.models import Personne, Site
from backend.services.csv_charlemagne import (
    BOM_UTF8,
    champs as decouper,
    decoder,
    lignes_du_fichier,
    lire,
)
from backend.services.repartition_pmb import RepartitionImpossible

COLONNES_RETOUR = ("Num Badge", "Type", "Nom", "Prénom", "Email")
"""Ce que l'import de Charlemagne attend, dans cet ordre.

`Type` doit être en **deuxième colonne** : c'est ainsi que Charlemagne le
lit, et le fichier est refusé s'il est ailleurs. Les deux colonnes
d'identité ne servent qu'à relire le fichier avant de l'importer — c'est le
badge qui apparie.
"""

TYPES_CHARLEMAGNE = {"eleve": "ELEVE", "adulte": "ADULTE"}
"""Le vocabulaire de Charlemagne, qui n'est pas celui du référentiel."""

COLONNES_REQUISES = ("Num Badge", "Email")


@dataclass
class Constat:
    """Une ligne de Charlemagne, ce qu'on en sait, et ce qu'il faut en faire."""

    badge: str
    nom: str
    prenom: str
    classe: str
    adresse_charlemagne: str
    adresse_referentiel: str
    type_personne: str
    """`ELEVE` ou `ADULTE`, dans le vocabulaire de Charlemagne."""
    origine: str
    """`constatee`, `attribuee`, `calculee` ou `aucune`."""
    detail: str = ""


@dataclass
class RapportAdresses:
    nb_lignes_lues: int = 0
    nb_deja_bonnes: int = 0
    google_consulte: bool = False

    a_remplir: list[Constat] = field(default_factory=list)
    a_verifier: list[Constat] = field(default_factory=list)
    a_corriger: list[Constat] = field(default_factory=list)
    alias_dans_charlemagne: list[Constat] = field(default_factory=list)
    referentiel_a_tort: list[Constat] = field(default_factory=list)
    adresse_personnelle: list[Constat] = field(default_factory=list)
    conflit: list[Constat] = field(default_factory=list)
    hors_referentiel: list[Constat] = field(default_factory=list)
    sans_adresse_nulle_part: list[Constat] = field(default_factory=list)

    csv_a_importer: bytes = b""
    nom_fichier: str = ""

    @property
    def nb_a_importer(self) -> int:
        return len(self.a_remplir) + len(self.a_corriger)

    @property
    def rien_a_faire(self) -> bool:
        return self.nb_a_importer == 0


def confronter_adresses(
    session: Session,
    contenu: bytes,
    *,
    comptes_google: list[dict] | None = None,
    annee_libelle: str = "",
) -> RapportAdresses:
    """Confronte la colonne `Email` de Charlemagne au référentiel et à Google.

    Args:
        contenu: l'export de Charlemagne portant les colonnes `Num Badge`
            et `Email` — celui du CDI convient.
        comptes_google: retour de `ClientGoogle.lister_utilisateurs`. Sans
            lui, aucune adresse n'est proposée : le fichier d'import serait
            un fichier de suppositions.

    Raises:
        RepartitionImpossible: fichier vide, ou dépourvu des deux colonnes.
    """
    lignes = lignes_du_fichier(decoder(contenu))
    if not lignes:
        raise RepartitionImpossible("Le fichier est vide.")

    entete = decouper(lignes[0])
    manquantes = [c for c in COLONNES_REQUISES if c not in entete]
    if manquantes:
        raise RepartitionImpossible(
            "Ce fichier ne porte pas les colonnes attendues : il y manque "
            + " et ".join(f"« {c} »" for c in manquantes)
            + ". L'en-tête lu commence par : "
            + ", ".join(entete[:4] or ["(rien)"])
            + "."
        )

    i_badge, i_mail = entete.index("Num Badge"), entete.index("Email")
    i_nom = entete.index("Nom") if "Nom" in entete else None
    i_prenom = entete.index("Prénom") if "Prénom" in entete else None
    i_classe = entete.index("Code classe") if "Code classe" in entete else None

    par_badge = {
        str(p.badge): p for p in session.query(Personne).all() if p.badge is not None
    }
    domaines = _domaines_ecole(session)
    principal_de = _principal_par_adresse(comptes_google)

    r = RapportAdresses(google_consulte=comptes_google is not None)

    for brute in lignes[1:]:
        if not brute.strip():
            continue
        cellules = decouper(brute)
        if len(cellules) <= max(i_badge, i_mail):
            continue
        r.nb_lignes_lues += 1

        badge = lire(cellules, i_badge)
        charle = lire(cellules, i_mail)
        p = par_badge.get(badge)
        modele = Constat(
            badge=badge, nom=lire(cellules, i_nom), prenom=lire(cellules, i_prenom),
            classe=lire(cellules, i_classe), adresse_charlemagne=charle,
            adresse_referentiel=(p.email or "") if p is not None else "",
            type_personne=TYPES_CHARLEMAGNE.get(
                p.type if p is not None else "", "ELEVE"
            ),
            origine=_origine(p),
        )

        if p is None:
            r.hors_referentiel.append(
                _avec(modele, "jamais ingéré ici — le programme ne lui connaît "
                              "pas d'adresse")
            )
            continue

        _classer(
            r, modele, charle, (p.email or "").strip(),
            principal_de, domaines, r.google_consulte,
        )

    _composer_fichier(r, annee_libelle)
    return r


def _avec(modele: Constat, detail: str) -> Constat:
    """Le même constat, avec le motif qui explique où il est rangé."""
    return replace(modele, detail=detail)


def _classer(
    r: RapportAdresses,
    modele: Constat,
    charle: str,
    ref: str,
    principal_de: dict[str, str],
    domaines: set[str],
    google_consulte: bool,
) -> None:
    """Range une ligne dans le constat qui la décrit.

    L'ordre des questions compte : « Charlemagne a-t-il quelque chose ? »
    avant « est-ce la bonne chose ? », et « est-ce une adresse d'école ? »
    avant toute comparaison — une adresse de famille ne se compare pas au
    compte de l'élève.
    """
    if not charle:
        if not ref:
            r.sans_adresse_nulle_part.append(
                _avec(modele, "ni Charlemagne ni le référentiel n'ont d'adresse")
            )
        elif not google_consulte:
            r.a_verifier.append(_avec(modele, "Google n'a pas été interrogé"))
        elif ref.lower() in principal_de:
            r.a_remplir.append(modele)
        else:
            r.a_verifier.append(
                _avec(modele, f"« {ref} » n'a pas été trouvée dans Google")
            )
        return

    if not _est_du_domaine(charle, domaines):
        r.adresse_personnelle.append(
            _avec(modele, "adresse de famille dans le champ — remplacer est "
                          "une décision, pas une évidence")
        )
        return

    if ref and charle.lower() == ref.lower():
        r.nb_deja_bonnes += 1
        return

    if not google_consulte:
        r.a_verifier.append(_avec(modele, "Google n'a pas été interrogé"))
        return

    p_charle = principal_de.get(charle.lower())
    p_ref = principal_de.get(ref.lower()) if ref else None
    ref_affichee = ref or "(rien)"

    if p_charle is None:
        suite = f" ; le compte est « {ref} »" if p_ref else ""
        r.a_corriger.append(
            _avec(modele, f"« {charle} » n'existe pas dans Google{suite}")
        )
    elif p_ref is None:
        r.referentiel_a_tort.append(
            _avec(modele, f"Google connaît « {charle} » et pas "
                          f"« {ref_affichee} » : c'est ici qu'il faut "
                          "corriger, pas dans Charlemagne")
        )
    elif p_charle != p_ref:
        r.conflit.append(
            _avec(modele, f"deux comptes distincts : « {p_charle} » et "
                          f"« {p_ref} »")
        )
    elif charle.lower() == p_charle:
        r.referentiel_a_tort.append(
            _avec(modele, "Charlemagne porte le compte principal ; le "
                          f"référentiel en garde l'alias « {ref} ». C'est ici "
                          "qu'il faut corriger, pas dans Charlemagne")
        )
    else:
        r.alias_dans_charlemagne.append(
            _avec(modele, f"alias du compte « {p_charle} » — le courrier arrive")
        )


def _composer_fichier(r: RapportAdresses, annee_libelle: str) -> None:
    """Le CSV à réimporter : les vides à remplir, et les fausses à corriger.

    Ni les adresses personnelles ni les alias n'y entrent. Les premières
    parce qu'écraser une adresse de famille est une décision ; les seconds
    parce qu'ils fonctionnent, et qu'un import qui ne change rien d'utile
    est un import qu'on relit pour rien.
    """
    lignes = [*r.a_remplir, *r.a_corriger]
    if not lignes:
        return
    buf = io.StringIO(newline="")
    w = csv.writer(buf, delimiter=";", quoting=csv.QUOTE_MINIMAL, lineterminator="\r\n")
    w.writerow(COLONNES_RETOUR)
    for c in lignes:
        w.writerow([c.badge, c.type_personne, c.nom, c.prenom,
                    c.adresse_referentiel])
    r.csv_a_importer = BOM_UTF8 + buf.getvalue().encode("utf-8")
    suffixe = f"_{annee_libelle}" if annee_libelle else ""
    r.nom_fichier = f"Charlemagne_adresses{suffixe}.csv"


# ---------------------------------------------------------------------------
# Ce qu'on interroge
# ---------------------------------------------------------------------------


def _origine(p: Personne | None) -> str:
    if p is None:
        return "aucune"
    if p.email_constate:
        return "constatee"
    if p.email_attribuee:
        return "attribuee"
    return "calculee" if p.email else "aucune"


def _domaines_ecole(session: Session) -> set[str]:
    return {
        (s.domaine_mail or "").strip().lower()
        for s in session.query(Site).all()
        if (s.domaine_mail or "").strip()
    }


def _est_du_domaine(adresse: str, domaines: set[str]) -> bool:
    return adresse.rsplit("@", 1)[-1].strip().lower() in domaines


def _principal_par_adresse(comptes: list[dict] | None) -> dict[str, str]:
    """Toute adresse connue de Google — compte ou alias — vers son principal.

    C'est ce qui distingue « Charlemagne se trompe » de « Charlemagne porte
    un alias » : sans cette table, un renommage de compte (Google garde
    l'ancienne adresse en alias) passerait pour une erreur à corriger.
    """
    par_adresse: dict[str, str] = {}
    for u in comptes or []:
        principal = (u.get("email") or "").strip().lower()
        if not principal:
            continue
        par_adresse[principal] = principal
        for alias in u.get("alias") or []:
            a = (alias or "").strip().lower()
            if a:
                par_adresse.setdefault(a, principal)
    return par_adresse
