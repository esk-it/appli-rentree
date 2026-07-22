"""Règles métier — génération et unicité du login, calcul d'email.

## Login

Forme : `initiale du prénom + nom`. Normalisation :

- suppression des accents (unidecode) ;
- suppression des apostrophes, espaces et traits d'union ;
- passage en minuscules ;
- troncature à `longueur_max` caractères (défaut 10).

**Un login attribué à une `Personne` est figé à vie**, y compris son suffixe
d'homonymie. Un login libéré n'est jamais recyclé — la `Personne` partie
existe toujours en base, avec son login toujours réservé.

## Homonymes — détection en deux temps

Cf. `docs/gestion-rentree-logique.md` §7.2. Une comparaison brute des noms
peut *masquer* les homonymes lorsqu'un départ et une arrivée se produisent
sur le même cycle. On ne s'y fie donc pas.

1. **À l'ingestion** — deux lignes de mêmes nom+prénom dans le même export.
   → `detecter_homonymes_ingestion(lignes)`.
2. **À l'attribution du login** — le login calculé existe déjà dans le
   référentiel. → `proposer_suffixe(session, login_base)`.

Un arbitrage humain (Lot 5) tranche : mêmes personnes / personnes distinctes.
La décision est mémorisée dans `Arbitrage` et jamais redemandée.

## Mot de passe

**Pas d'autorité côté programme** — KoXo génère à la création, on transporte
en mémoire pour Google, on oublie. Rien n'est persisté (§7.3 de la doc).
La fonction `generer_mot_de_passe` est conservée comme utilitaire (tests,
prévisualisation) mais **n'est pas appelée en production**.
"""
from __future__ import annotations

import random
import re
from dataclasses import dataclass

from sqlalchemy.orm import Session
from unidecode import unidecode

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

DEFAUT_LONGUEUR_MAX_LOGIN = 10
DEFAUT_MAX_SUFFIXES = 99

# ---------------------------------------------------------------------------
# Normalisation
# ---------------------------------------------------------------------------


def normaliser_nom(texte: str | None) -> str:
    """Ne garde que `[a-z]` : accents/apostrophes/tirets/espaces retirés, minuscules."""
    if not texte:
        return ""
    s = unidecode(str(texte)).lower()
    return re.sub(r"[^a-z]", "", s)


def normaliser_pour_email(
    texte: str | None, separateur_espaces: str = "."
) -> str:
    """Variante email : minuscules, sans accents, sans apostrophes.

    - espaces → `separateur_espaces` (typiquement `.`)
    - doubles tirets `--` → tiret simple `-`
    - tirets simples conservés
    - `[a-z0-9.-]` seuls autorisés
    """
    if not texte:
        return ""
    s = unidecode(str(texte)).lower()
    s = s.replace("'", "")
    s = re.sub(r"-{2,}", "-", s)
    s = re.sub(r"\s+", separateur_espaces, s.strip())
    return re.sub(r"[^a-z0-9.\-]", "", s)


# ---------------------------------------------------------------------------
# Login
# ---------------------------------------------------------------------------


def calculer_login_base(
    prenom: str | None,
    nom: str | None,
    longueur_max: int = DEFAUT_LONGUEUR_MAX_LOGIN,
) -> str:
    """Login canonique : première lettre prénom + nom normalisé, tronqué.

    Si prénom absent → nom seul tronqué.
    Si nom absent → prénom seul tronqué.
    """
    p = normaliser_nom(prenom)
    n = normaliser_nom(nom)
    if not p and not n:
        return ""
    if not p:
        return n[:longueur_max]
    if not n:
        return p[:longueur_max]
    return (p[0] + n)[:longueur_max]


def login_est_libre(session: Session, login: str) -> bool:
    """True si aucune `Personne` n'a ce login au référentiel.

    L'interrogation traverse tous les types (élève/adulte), toutes les années,
    y compris les personnes sorties — un login libéré n'est pas recyclé.
    """
    from backend.models import Personne

    if not login:
        return False
    existante = session.query(Personne).filter_by(login=login).first()
    return existante is None


@dataclass
class PropositionLogin:
    """Résultat d'une proposition de login."""

    login_base: str
    """Login normalisé sans suffixe (`jdupont`)."""

    login_propose: str
    """Login effectivement libre au moment de la proposition (`jdupont2` p. ex.)."""

    suffixe_utilise: int
    """0 si aucun suffixe (base libre), sinon numéro utilisé (2, 3, …)."""

    a_conflit: bool
    """True si le base n'était pas libre — utile pour déclencher un arbitrage."""

    personnes_en_conflit: list["ResumePersonneConflit"]
    """Les personnes qui portent le login base ou ses variantes proches."""


@dataclass
class ResumePersonneConflit:
    """Résumé d'une personne qui bloque un login."""

    personne_id: int
    cle_pivot: str
    login: str
    nom: str
    prenom: str
    type: str


def _resumer_personne_pour_conflit(p) -> ResumePersonneConflit:
    return ResumePersonneConflit(
        personne_id=p.id,
        cle_pivot=p.cle_pivot,
        login=p.login,
        nom=p.nom,
        prenom=p.prenom,
        type=p.type,
    )


def proposer_suffixe(
    session: Session,
    login_base: str,
    max_essais: int = DEFAUT_MAX_SUFFIXES,
) -> PropositionLogin | None:
    """Retourne un login libre, avec métadonnées d'arbitrage.

    Essaie `login_base`, puis `login_base2`, `login_base3`, … jusqu'à trouver
    un libre. Renvoie `None` si aucun trouvé au bout de `max_essais`.

    Le champ `personnes_en_conflit` contient les `Personne` qui portent
    déjà `login_base` (pour matérialiser l'arbitrage humain — mêmes personnes
    ou personnes distinctes).
    """
    from backend.models import Personne

    if not login_base:
        return None

    conflits = (
        session.query(Personne)
        .filter(Personne.login.like(f"{login_base}%"))
        .all()
    )
    logins_pris = {p.login for p in conflits}

    for suffixe in range(1, max_essais + 1):
        candidat = login_base if suffixe == 1 else f"{login_base}{suffixe}"
        if candidat not in logins_pris:
            return PropositionLogin(
                login_base=login_base,
                login_propose=candidat,
                suffixe_utilise=0 if suffixe == 1 else suffixe,
                a_conflit=(suffixe > 1),
                personnes_en_conflit=[
                    _resumer_personne_pour_conflit(p)
                    for p in conflits
                    if p.login == login_base or (p.login.startswith(login_base) and p.login[len(login_base):].isdigit())
                ],
            )
    return None


def proposer_login_pour(
    session: Session,
    prenom: str,
    nom: str,
    longueur_max: int = DEFAUT_LONGUEUR_MAX_LOGIN,
) -> PropositionLogin | None:
    """Combine `calculer_login_base` + `proposer_suffixe`."""
    base = calculer_login_base(prenom, nom, longueur_max)
    if not base:
        return None
    return proposer_suffixe(session, base)


# ---------------------------------------------------------------------------
# Email
# ---------------------------------------------------------------------------


def calculer_email(
    prenom: str | None,
    nom: str | None,
    domaine: str,
) -> str:
    """Email canonique `prenom.nom@domaine`.

    - accents retirés, minuscules
    - apostrophes retirées
    - espaces → points, tirets doubles → tiret simple
    """
    p = normaliser_pour_email(prenom)
    n = normaliser_pour_email(nom)
    if not p and not n:
        return ""
    if p and n:
        return f"{p}.{n}@{domaine}"
    return f"{p or n}@{domaine}"


# ---------------------------------------------------------------------------
# Homonymes — détection à l'ingestion
# ---------------------------------------------------------------------------


@dataclass
class PaireHomonyme:
    """Une paire de lignes d'export qui se ressemblent en (nom, prenom)."""

    cle_normalisee: tuple[str, str]
    lignes: list[dict]


def _cle_homonyme(nom: str | None, prenom: str | None) -> tuple[str, str]:
    """Clé de comparaison pour détecter les homonymies :
    accents retirés + upper + trim, sur nom ET prénom."""
    n = unidecode(str(nom or "")).upper().strip()
    p = unidecode(str(prenom or "")).upper().strip()
    return (n, p)


def detecter_homonymes_ingestion(
    lignes: list[dict],
    champ_nom: str = "nom",
    champ_prenom: str = "prenom",
) -> list[PaireHomonyme]:
    """Détecte les groupes de lignes qui partagent (nom, prénom) normalisés.

    Détection intra-export : deux lignes du même fichier Charlemagne qui
    portent les mêmes nom et prénom (accents ignorés). Chaque groupe de
    ≥ 2 lignes est retourné comme `PaireHomonyme` (le nom "paire" est
    pratique, mais un triplet donnera un seul PaireHomonyme avec 3 lignes).
    """
    par_cle: dict[tuple[str, str], list[dict]] = {}
    for l in lignes:
        cle = _cle_homonyme(l.get(champ_nom), l.get(champ_prenom))
        if not cle[0] and not cle[1]:
            continue
        par_cle.setdefault(cle, []).append(l)
    return [
        PaireHomonyme(cle_normalisee=cle, lignes=grp)
        for cle, grp in par_cle.items()
        if len(grp) >= 2
    ]


# ---------------------------------------------------------------------------
# Mot de passe — utilitaire (non utilisé en production)
# ---------------------------------------------------------------------------

_CONSONNES = "bcdfgjklmnpqrstvwxz"
_VOYELLES = "aeiou"


def generer_mot_de_passe(rng: random.Random | None = None) -> str:
    """Format historique `Sateku68` — 6 lettres alternées + 2 chiffres.

    KoXo est l'autorité du mot de passe en production ; cette fonction sert
    aux tests et à d'éventuelles prévisualisations d'écrans (arbitrage,
    amorçage). Elle n'est pas appelée dans la chaîne d'exécution réelle.
    """
    r = rng or random.Random()
    debut_consonne = r.choice([True, False])
    lettres: list[str] = []
    for i in range(6):
        if (i % 2 == 0) == debut_consonne:
            lettres.append(r.choice(_CONSONNES))
        else:
            lettres.append(r.choice(_VOYELLES))
    lettres[0] = lettres[0].upper()
    return "".join(lettres) + f"{r.randint(0, 99):02d}"
