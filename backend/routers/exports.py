"""Endpoints de génération des fichiers d'import.

Chaque endpoint cible un système métier (KoXo, PMB, SmartAir, etc.).
Pour l'instant, seul KoXo est implémenté. Les autres suivront.
"""
from __future__ import annotations

from dataclasses import asdict

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from backend.database import db_session
from backend.services.exporters.koxo import generer_exports_koxo

router = APIRouter(prefix="/api/exports", tags=["exports"])


class ExportKoxoPayload(BaseModel):
    annee_n: str = Field(..., description='Libellé de l\'année N, ex. "2026-2027"')
    annee_n_minus_1: str | None = Field(
        None,
        description=(
            "Libellé de l'année N-1 (optionnel). Si fourni, l'export inclut "
            "les fichiers Nouveaux/Anciens calculés via comparaison."
        ),
    )


@router.post("/koxo")
def exporter_koxo(
    payload: ExportKoxoPayload,
    session: Session = Depends(db_session),
) -> dict:
    """Génère les CSV d'import KoXo pour l'année N (et N-1 si fournie).

    Returns:
        {
            "annee_n": "...",
            "annee_n_minus_1": "..." | null,
            "fichiers": [
                { "nom": "KoXo_SU_Eleves_Tous_2026-2027.csv",
                  "contenu": "...CSV...",
                  "nb_lignes": 702,
                  "description": "..." },
                ...
            ]
        }
    """
    try:
        fichiers = generer_exports_koxo(
            session=session,
            libelle_n=payload.annee_n,
            libelle_n_minus_1=payload.annee_n_minus_1,
        )
    except ValueError as e:
        raise HTTPException(400, str(e)) from e

    return {
        "annee_n": payload.annee_n,
        "annee_n_minus_1": payload.annee_n_minus_1,
        "fichiers": [asdict(f) for f in fichiers],
    }
