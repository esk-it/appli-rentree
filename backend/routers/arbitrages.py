"""Endpoint des arbitrages — mémoire des décisions humaines.

- `GET /api/arbitrages/en-attente` : cas non tranchés (à traiter en priorité)
- `GET /api/arbitrages` : tous les arbitrages (audit, y compris tranchés)
- `POST /api/arbitrages/{id}/trancher` : enregistre la décision humaine

Aucun endpoint de suppression : une décision arbitrée reste tracée à vie.
"""
from __future__ import annotations

import json
from datetime import datetime
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session

from backend.database import db_session
from backend.models import Arbitrage
from backend.services.arbitrage import en_attente, trancher

router = APIRouter(prefix="/api/arbitrages", tags=["arbitrages"])


class ArbitrageOut(BaseModel):
    id: int
    type_cas: str
    cle_cas: str
    decision: str | None
    note: str | None
    contexte: dict
    date_creation: datetime
    date_decision: datetime | None
    est_en_attente: bool


class DecisionIn(BaseModel):
    decision: str
    note: str | None = None


def _to_out(arb: Arbitrage) -> ArbitrageOut:
    try:
        ctx = json.loads(arb.contexte_json)
    except (json.JSONDecodeError, TypeError):
        ctx = {}
    return ArbitrageOut(
        id=arb.id,
        type_cas=arb.type_cas,
        cle_cas=arb.cle_cas,
        decision=arb.decision,
        note=arb.note,
        contexte=ctx,
        date_creation=arb.date_creation,
        date_decision=arb.date_decision,
        est_en_attente=arb.est_en_attente,
    )


@router.get("/en-attente", response_model=list[ArbitrageOut])
def lister_en_attente(session: Session = Depends(db_session)) -> list[ArbitrageOut]:
    """Cas ambigus qui attendent une décision humaine."""
    return [_to_out(a) for a in en_attente(session)]


@router.get("", response_model=list[ArbitrageOut])
def lister_tous(
    type_cas: Literal["collision_login", "homonymie_ingestion", "rapprochement", "qualification"] | None = None,
    session: Session = Depends(db_session),
) -> list[ArbitrageOut]:
    """Historique complet — filtrage optionnel par type de cas."""
    q = session.query(Arbitrage).order_by(Arbitrage.date_creation.desc())
    if type_cas is not None:
        q = q.filter(Arbitrage.type_cas == type_cas)
    return [_to_out(a) for a in q.all()]


@router.post("/{arbitrage_id}/trancher", response_model=ArbitrageOut)
def trancher_arbitrage(
    arbitrage_id: int,
    payload: DecisionIn,
    session: Session = Depends(db_session),
) -> ArbitrageOut:
    """Enregistre la décision humaine. Renvoie 409 si déjà tranché."""
    if not payload.decision or not payload.decision.strip():
        raise HTTPException(400, "La décision ne peut pas être vide.")
    try:
        r = trancher(session, arbitrage_id, payload.decision.strip(), payload.note)
    except ValueError as e:
        raise HTTPException(404, str(e))
    if r.deja_tranche:
        raise HTTPException(
            409,
            f"Cet arbitrage a déjà été tranché ({r.arbitrage.decision!r}) — décision immuable.",
        )
    session.commit()
    return _to_out(r.arbitrage)
