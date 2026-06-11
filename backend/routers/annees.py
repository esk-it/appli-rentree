"""Endpoints autour des années scolaires (snapshots)."""
from __future__ import annotations

from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import func
from sqlalchemy.orm import Session

from backend.database import db_session
from backend.models import AnneeScolaire, EleveSnapshot

router = APIRouter(prefix="/api/annees", tags=["annees"])


class AnneeOut(BaseModel):
    id: int
    libelle: str
    date_creation: datetime
    est_active: bool
    nb_eleves: int


@router.get("", response_model=list[AnneeOut])
def lister_annees(session: Session = Depends(db_session)) -> list[AnneeOut]:
    """Liste les snapshots d'année avec leur effectif total."""
    results = (
        session.query(
            AnneeScolaire,
            func.count(EleveSnapshot.id).label("nb_eleves"),
        )
        .outerjoin(
            EleveSnapshot, EleveSnapshot.annee_scolaire_id == AnneeScolaire.id
        )
        .group_by(AnneeScolaire.id)
        .order_by(AnneeScolaire.date_creation.desc())
        .all()
    )
    return [
        AnneeOut(
            id=a.id,
            libelle=a.libelle,
            date_creation=a.date_creation,
            est_active=a.est_active,
            nb_eleves=int(n),
        )
        for a, n in results
    ]


@router.delete("/{annee_id}")
def supprimer_annee(
    annee_id: int, session: Session = Depends(db_session)
) -> dict:
    """Supprime un snapshot et tous ses élèves (cascade)."""
    annee = session.query(AnneeScolaire).filter_by(id=annee_id).one_or_none()
    if annee is None:
        raise HTTPException(404, f"Année introuvable : {annee_id}")
    libelle = annee.libelle
    session.delete(annee)
    session.commit()
    return {"ok": True, "supprime_id": annee_id, "supprime_libelle": libelle}
