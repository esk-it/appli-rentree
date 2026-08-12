"""Endpoints du journal des opérations."""
from __future__ import annotations

from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy.orm import Session

from backend.database import db_session
from backend.models import Generation
from backend.services.journal import comparer_avec_precedent, lister

router = APIRouter(prefix="/api/journal", tags=["journal"])


class GenerationOut(BaseModel):
    id: int
    date_creation: datetime
    type_operation: str
    cible: str | None
    mode: str | None
    annee_libelle: str | None
    annee_source_libelle: str | None
    parametres: dict
    resultat: dict
    notes: str | None


def _to_out(g: Generation) -> GenerationOut:
    return GenerationOut(
        id=g.id,
        date_creation=g.date_creation,
        type_operation=g.type_operation,
        cible=g.cible,
        mode=g.mode,
        annee_libelle=g.annee_libelle,
        annee_source_libelle=g.annee_source_libelle,
        parametres=g.parametres,
        resultat=g.resultat,
        notes=g.notes,
    )


@router.get("", response_model=list[GenerationOut])
def lister_journal(
    type_operation: str | None = None,
    cible: str | None = None,
    annee_libelle: str | None = None,
    limite: int = Query(100, ge=1, le=1000),
    session: Session = Depends(db_session),
) -> list[GenerationOut]:
    """Historique des opérations, du plus récent au plus ancien."""
    return [
        _to_out(g)
        for g in lister(
            session,
            type_operation=type_operation,
            cible=cible,
            annee_libelle=annee_libelle,
            limite=limite,
        )
    ]


class EcartOut(BaseModel):
    compteur: str
    valeur_courante: int
    valeur_precedente: int
    ecart: int
    ecart_relatif: float | None
    est_aberrant: bool


class ComparaisonOut(BaseModel):
    trouvee: bool
    reference_id: int | None = None
    reference_date: str | None = None
    reference_annee: str | None = None
    ecarts: list[EcartOut] = []
    nb_aberrations: int = 0


@router.get("/{generation_id}/comparaison", response_model=ComparaisonOut)
def comparer(
    generation_id: int, session: Session = Depends(db_session)
) -> ComparaisonOut:
    """Compare une opération journalisée à la même opération d'une autre année."""
    g = session.query(Generation).filter_by(id=generation_id).one_or_none()
    if g is None:
        raise HTTPException(404, f"Generation introuvable : {generation_id}")

    c = comparer_avec_precedent(
        session,
        type_operation=g.type_operation,
        cible=g.cible,
        annee_libelle=g.annee_libelle,
        resultat_courant=g.resultat,
    )
    return ComparaisonOut(
        trouvee=c.trouvee,
        reference_id=c.reference_id,
        reference_date=c.reference_date,
        reference_annee=c.reference_annee,
        ecarts=[
            EcartOut(
                compteur=e.compteur,
                valeur_courante=e.valeur_courante,
                valeur_precedente=e.valeur_precedente,
                ecart=e.ecart,
                ecart_relatif=e.ecart_relatif,
                est_aberrant=e.est_aberrant,
            )
            for e in c.ecarts
        ],
        nb_aberrations=len(c.aberrations),
    )
