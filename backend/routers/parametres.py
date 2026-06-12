"""Endpoints de gestion des paramètres."""
from __future__ import annotations

from dataclasses import asdict
from typing import Any

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session

from backend.database import db_session
from backend.services.configuration import (
    CATALOGUE,
    CATALOGUE_PAR_CLE,
    get_tous_parametres,
    set_param,
)

router = APIRouter(prefix="/api/parametres", tags=["parametres"])


class ParametreOut(BaseModel):
    cle: str
    libelle: str
    description: str
    type: str
    defaut: Any
    valeur: Any
    categorie: str


@router.get("", response_model=list[ParametreOut])
def lister_parametres(session: Session = Depends(db_session)) -> list[ParametreOut]:
    """Liste tous les paramètres du catalogue avec leur valeur courante."""
    valeurs = get_tous_parametres(session)
    return [
        ParametreOut(
            cle=p.cle,
            libelle=p.libelle,
            description=p.description,
            type=p.type,
            defaut=p.defaut,
            valeur=valeurs.get(p.cle, p.defaut),
            categorie=p.categorie,
        )
        for p in CATALOGUE
    ]


class MajParametrePayload(BaseModel):
    valeur: Any


@router.put("/{cle:path}")
def maj_parametre(
    cle: str,
    payload: MajParametrePayload,
    session: Session = Depends(db_session),
) -> dict:
    """Met à jour la valeur d'un paramètre."""
    if cle not in CATALOGUE_PAR_CLE:
        raise HTTPException(404, f"Paramètre inconnu : {cle}")
    # Validation basique du type
    definition = CATALOGUE_PAR_CLE[cle]
    if definition.type == "int":
        try:
            payload.valeur = int(payload.valeur)
        except (TypeError, ValueError):
            raise HTTPException(400, f"Entier attendu pour {cle}")
    elif definition.type == "bool":
        if not isinstance(payload.valeur, bool):
            payload.valeur = bool(payload.valeur)

    set_param(session, cle, payload.valeur)
    session.commit()
    return {"ok": True, "cle": cle, "valeur": payload.valeur}
