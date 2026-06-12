"""Endpoint d'accès à l'historique des générations."""
from __future__ import annotations

from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy.orm import Session

from backend.database import db_session
from backend.models import Generation

router = APIRouter(prefix="/api/historique", tags=["historique"])


class GenerationOut(BaseModel):
    id: int
    date_creation: datetime
    cible: str
    annee_n: str
    annee_n_minus_1: str | None
    nb_fichiers: int
    nb_lignes_total: int
    notes: str | None


@router.get("", response_model=list[GenerationOut])
def lister_historique(
    limite: int = Query(100, ge=1, le=500),
    cible: str | None = Query(None, description="Filtre optionnel par cible"),
    session: Session = Depends(db_session),
) -> list[GenerationOut]:
    """Liste les générations passées (les plus récentes en premier)."""
    q = session.query(Generation).order_by(Generation.date_creation.desc())
    if cible:
        q = q.filter_by(cible=cible)
    items = q.limit(limite).all()
    return [
        GenerationOut(
            id=g.id,
            date_creation=g.date_creation,
            cible=g.cible,
            annee_n=g.annee_n,
            annee_n_minus_1=g.annee_n_minus_1,
            nb_fichiers=g.nb_fichiers,
            nb_lignes_total=g.nb_lignes_total,
            notes=g.notes,
        )
        for g in items
    ]


@router.delete("/{id_generation}")
def supprimer_generation(
    id_generation: int, session: Session = Depends(db_session)
) -> dict:
    g = session.query(Generation).filter_by(id=id_generation).one_or_none()
    if g is None:
        raise HTTPException(404, "Génération introuvable")
    session.delete(g)
    session.commit()
    return {"ok": True, "supprime": id_generation}
