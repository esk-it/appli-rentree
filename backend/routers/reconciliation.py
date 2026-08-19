"""Endpoint de réconciliation.

Compare deux années scolaires et renvoie le classement en 5 seaux.
Lecture pure — aucune écriture, pas de mode `reel`/`simulation` à distinguer.
"""
from __future__ import annotations

from dataclasses import asdict
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy.orm import Session

from backend.database import db_session
from backend.services.reconciliation import RapportReconciliation, reconcilier

router = APIRouter(prefix="/api/reconciliation", tags=["reconciliation"])


class ChangementOut(BaseModel):
    champ: str
    avant: str | None
    apres: str | None


class EntreeOut(BaseModel):
    personne_id: int
    cle_pivot: str
    type: str
    nom: str
    prenom: str
    login: str
    site_id: int | None
    classe_source: str | None
    classe_cible: str | None
    motif: str
    changements: list[ChangementOut] = []


class RapportOut(BaseModel):
    annee_source_id: int
    annee_source_libelle: str
    annee_cible_id: int
    annee_cible_libelle: str
    type_personne: str | None
    compteurs: dict[str, int]
    avertissements: list[str]
    nouveaux: list[EntreeOut]
    identiques: list[EntreeOut]
    modifies: list[EntreeOut]
    sortants: list[EntreeOut]
    ambigus: list[EntreeOut]


def _to_out(rapport: RapportReconciliation) -> RapportOut:
    def entree(e):
        return EntreeOut(**asdict(e))

    return RapportOut(
        annee_source_id=rapport.annee_source_id,
        annee_source_libelle=rapport.annee_source_libelle,
        annee_cible_id=rapport.annee_cible_id,
        annee_cible_libelle=rapport.annee_cible_libelle,
        type_personne=rapport.type_personne,
        compteurs=rapport.compteurs,
        avertissements=rapport.avertissements,
        nouveaux=[entree(e) for e in rapport.nouveaux],
        identiques=[entree(e) for e in rapport.identiques],
        modifies=[entree(e) for e in rapport.modifies],
        sortants=[entree(e) for e in rapport.sortants],
        ambigus=[entree(e) for e in rapport.ambigus],
    )


@router.get("", response_model=RapportOut)
def obtenir_reconciliation(
    annee_source_id: int = Query(..., description="ID de l'année servant de référentiel"),
    annee_cible_id: int = Query(..., description="ID de l'année à évaluer"),
    type_personne: Literal["eleve", "adulte"] | None = Query(
        None, description="Filtre optionnel : eleve | adulte"
    ),
    session: Session = Depends(db_session),
) -> RapportOut:
    """Réconciliation d'une année cible par rapport à une année source."""
    try:
        rapport = reconcilier(
            session=session,
            annee_source_id=annee_source_id,
            annee_cible_id=annee_cible_id,
            type_personne=type_personne,
        )
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    return _to_out(rapport)
