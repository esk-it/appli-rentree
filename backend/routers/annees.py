"""Endpoints autour des années scolaires.

Depuis la refonte (v0.22.0), les snapshots portent une identité `Personne`
et ne sont plus séparés élèves/adultes — le compteur est unifié.
"""
from __future__ import annotations

from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import func
from sqlalchemy.orm import Session

from backend.database import db_session
from backend.models import AnneeScolaire, Personne, Snapshot

router = APIRouter(prefix="/api/annees", tags=["annees"])


class AnneeOut(BaseModel):
    id: int
    libelle: str
    date_creation: datetime
    est_active: bool
    nb_snapshots: int
    nb_personnes_distinctes: int


@router.get("", response_model=list[AnneeOut])
def lister_annees(session: Session = Depends(db_session)) -> list[AnneeOut]:
    """Liste les années avec effectifs (snapshots et personnes distinctes)."""
    results = (
        session.query(
            AnneeScolaire,
            func.count(Snapshot.id).label("nb_snapshots"),
            func.count(func.distinct(Snapshot.personne_id)).label("nb_personnes"),
        )
        .outerjoin(Snapshot, Snapshot.annee_scolaire_id == AnneeScolaire.id)
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
            nb_snapshots=int(n_snap),
            nb_personnes_distinctes=int(n_pers),
        )
        for a, n_snap, n_pers in results
    ]


@router.delete("/{annee_id}")
def supprimer_annee(
    annee_id: int, session: Session = Depends(db_session)
) -> dict:
    """Supprime une année scolaire. Les snapshots sont détachés (personnes
    conservées, snapshots supprimés en cascade via FK)."""
    annee = session.query(AnneeScolaire).filter_by(id=annee_id).one_or_none()
    if annee is None:
        raise HTTPException(404, f"Année introuvable : {annee_id}")
    libelle = annee.libelle
    # Suppression manuelle des snapshots (pas de cascade automatique définie)
    session.query(Snapshot).filter_by(annee_scolaire_id=annee_id).delete()
    session.delete(annee)
    session.commit()
    return {"ok": True, "supprime_id": annee_id, "supprime_libelle": libelle}
