"""Endpoints pour consulter les établissements enregistrés en base."""
from __future__ import annotations

from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy.orm import Session

from backend.database import db_session
from backend.models import Etablissement

router = APIRouter(prefix="/api/etablissements", tags=["etablissements"])


class EtablissementOut(BaseModel):
    id: int
    code_charlemagne: str
    code_court: str
    nom_long: str
    type: str


@router.get("", response_model=list[EtablissementOut])
def lister_etablissements(
    session: Session = Depends(db_session),
) -> list[EtablissementOut]:
    """Liste tous les établissements connus (créés à partir des imports)."""
    etabs = (
        session.query(Etablissement).order_by(Etablissement.code_court).all()
    )
    return [
        EtablissementOut(
            id=e.id,
            code_charlemagne=e.code_charlemagne,
            code_court=e.code_court,
            nom_long=e.nom_long,
            type=e.type,
        )
        for e in etabs
    ]
