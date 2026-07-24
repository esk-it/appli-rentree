"""Service d'arbitrage — la mémoire des décisions humaines.

Un **arbitrage** matérialise un cas que le programme refuse de trancher :
collision de login entre nouveaux, homonymie détectée, rapprochement à valider
lors de l'amorçage. Il est créé « en attente » par l'ingestion (ou l'amorçage),
présenté à l'utilisateur via l'écran dédié, tranché, et la décision est
**mémorisée définitivement** — jamais redemandée l'année suivante.

## Idempotence

`creer_ou_reprendre` s'appuie sur `Arbitrage.cle_cas` (unique) pour ne pas
dupliquer un cas déjà connu. La `cle_cas` doit être **déterministe** :
mêmes entrées → même clé.

## Cle_cas — conventions

Le service ne l'impose pas mais les callers respectent :

- collision_login : `collision_login:<login_base>:<cle_pivot_nouveau>`
- homonymie      : `homonymie_ingestion:<nom_norm>:<prenom_norm>:<ids_pivot_tries>`
- rapprochement  : `rapprochement:<cible>:<identifiant_ext>`
- qualification  : `qualification:<cible>:<identifiant_ext>`

Le §3.5 du prompt insiste : **jamais d'heuristique**. Ce service persiste,
ne décide pas.
"""
from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import datetime
from typing import Any

from sqlalchemy.orm import Session

from backend.models import Arbitrage

# Types de cas connus, dupliqués depuis le modèle pour éviter un import
# circulaire (les callers utilisent ces constantes plutôt qu'un magic string).
TYPES_CAS_VALIDES = (
    "collision_login",
    "homonymie_ingestion",
    "rapprochement",
    "qualification",
)


@dataclass
class ArbitrageTranche:
    """Résultat d'un tranchage : renvoie l'objet et un booléen `deja_tranche`
    qui permet au caller de savoir si sa décision a réellement pris effet
    (False = un autre utilisateur a tranché entre-temps, ou l'arbitrage
    était déjà résolu et on renvoie l'existant sans modification)."""

    arbitrage: Arbitrage
    deja_tranche: bool


def creer_ou_reprendre(
    session: Session,
    *,
    type_cas: str,
    cle_cas: str,
    contexte: dict[str, Any],
    note: str | None = None,
) -> Arbitrage:
    """Persiste un cas ambigu **en attente**, sans doublon.

    Si un `Arbitrage` avec la même `cle_cas` existe déjà :
    - qu'il soit tranché ou non, on le renvoie tel quel — la clé pivot fait foi.
    - le `contexte_json` peut être mis à jour (utile si le contexte a évolué).

    Sinon crée un nouvel enregistrement `date_decision = None`.
    Le caller doit committer la session.
    """
    if type_cas not in TYPES_CAS_VALIDES:
        raise ValueError(f"type_cas doit être {TYPES_CAS_VALIDES}, reçu : {type_cas!r}")

    existant = session.query(Arbitrage).filter_by(cle_cas=cle_cas).one_or_none()
    if existant is not None:
        # Rafraîchit le contexte — utile si des infos ont changé
        existant.contexte_json = json.dumps(contexte, ensure_ascii=False, default=str)
        return existant

    arbitrage = Arbitrage(
        type_cas=type_cas,
        cle_cas=cle_cas,
        contexte_json=json.dumps(contexte, ensure_ascii=False, default=str),
        decision=None,
        date_decision=None,
        note=note,
    )
    session.add(arbitrage)
    session.flush()
    return arbitrage


def trancher(
    session: Session,
    arbitrage_id: int,
    decision: str,
    note: str | None = None,
) -> ArbitrageTranche:
    """Enregistre la décision humaine sur un arbitrage.

    Si l'arbitrage est déjà tranché, on renvoie `deja_tranche=True` sans
    écraser la décision précédente — la mémoire est immuable, une décision
    passée ne se corrige que par nouvelle création (cas rare, hors périmètre).
    """
    arb = session.query(Arbitrage).filter_by(id=arbitrage_id).one_or_none()
    if arb is None:
        raise ValueError(f"Arbitrage introuvable : {arbitrage_id}")

    if arb.date_decision is not None:
        return ArbitrageTranche(arbitrage=arb, deja_tranche=True)

    arb.decision = decision
    arb.date_decision = datetime.utcnow()
    if note is not None:
        arb.note = note
    session.flush()
    return ArbitrageTranche(arbitrage=arb, deja_tranche=False)


def en_attente(session: Session) -> list[Arbitrage]:
    """Retourne tous les arbitrages non tranchés, du plus ancien au plus récent."""
    return (
        session.query(Arbitrage)
        .filter(Arbitrage.date_decision.is_(None))
        .order_by(Arbitrage.date_creation.asc())
        .all()
    )


def deja_tranche(session: Session, cle_cas: str) -> Arbitrage | None:
    """Renvoie l'arbitrage correspondant à `cle_cas` s'il a déjà été tranché,
    None sinon. Utile à l'ingestion pour éviter de redemander une décision
    connue."""
    arb = session.query(Arbitrage).filter_by(cle_cas=cle_cas).one_or_none()
    if arb is None or arb.date_decision is None:
        return None
    return arb


# ---------------------------------------------------------------------------
# Fabriques de cle_cas — un seul endroit pour la convention
# ---------------------------------------------------------------------------


def cle_collision_login(login_base: str, cle_pivot_nouveau: str) -> str:
    return f"collision_login:{login_base}:{cle_pivot_nouveau}"


def cle_homonymie_ingestion(
    nom_normalise: str, prenom_normalise: str, cles_pivot: list[str]
) -> str:
    """Clé stable même si l'ordre des IDs varie d'un export à l'autre."""
    tries = ",".join(sorted(cles_pivot))
    return f"homonymie_ingestion:{nom_normalise}:{prenom_normalise}:{tries}"


def cle_rapprochement(cible: str, identifiant_ext: str) -> str:
    return f"rapprochement:{cible}:{identifiant_ext}"


def cle_qualification(cible: str, identifiant_ext: str) -> str:
    return f"qualification:{cible}:{identifiant_ext}"
