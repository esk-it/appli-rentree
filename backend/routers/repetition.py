"""La répétition : basculer le programme sur une copie de la base, et revenir.

Voir `services/repetition.py`. Ces gestes ne touchent jamais la vraie
base : commencer sur une copie, quitter pour retrouver la vraie, jeter la
copie. À ne pas confondre avec `/api/simulation`, le rapport transverse de
ce que les exports feraient.
"""
from __future__ import annotations

from dataclasses import asdict

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

router = APIRouter(prefix="/api/repetition", tags=["repetition"])


class EtatOut(BaseModel):
    active: bool
    copie_existe: bool
    copiee_le: str | None = None


class CommencerPayload(BaseModel):
    neuve: bool = False
    """Une copie neuve de la vraie base, plutôt que reprendre la précédente."""


@router.get("", response_model=EtatOut)
def lire():
    from backend.services.repetition import etat

    return EtatOut(**asdict(etat()))


@router.post("/commencer", response_model=EtatOut)
def commencer(payload: CommencerPayload):
    from backend.services.repetition import commencer as _commencer

    try:
        return EtatOut(**asdict(_commencer(neuve=payload.neuve)))
    except Exception as e:  # copie impossible : disque plein, base verrouillée
        raise HTTPException(500, f"Répétition impossible : {type(e).__name__}: {e}") from None


@router.post("/quitter", response_model=EtatOut)
def quitter():
    from backend.services.repetition import quitter as _quitter

    return EtatOut(**asdict(_quitter()))


@router.post("/jeter", response_model=EtatOut)
def jeter():
    from backend.services.repetition import jeter as _jeter

    return EtatOut(**asdict(_jeter()))
