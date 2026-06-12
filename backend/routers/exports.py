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
from backend.services.exporters.cardstudio import generer_exports_cardstudio
from backend.services.exporters.koxo import generer_exports_koxo
from backend.services.exporters.pmb import generer_exports_pmb

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


class ExportPmbPayload(BaseModel):
    annee_n: str = Field(..., description='Libellé de l\'année N, ex. "2026-2027"')


@router.post("/pmb")
def exporter_pmb(
    payload: ExportPmbPayload,
    session: Session = Depends(db_session),
) -> dict:
    """Génère les CSV d'import PMB (une par instance : SU et NDK).

    PMB ne gère pas vraiment de Nouveaux/Anciens — on importe juste l'état
    complet. L'archivage des anciens emprunteurs reste manuel côté PMB.
    """
    try:
        fichiers = generer_exports_pmb(session=session, libelle_n=payload.annee_n)
    except ValueError as e:
        raise HTTPException(400, str(e)) from e

    return {
        "annee_n": payload.annee_n,
        "fichiers": [asdict(f) for f in fichiers],
    }


class ExportCardStudioPayload(BaseModel):
    annee_n: str = Field(..., description='Libellé de l\'année N, ex. "2026-2027"')


@router.post("/cardstudio")
def exporter_cardstudio(
    payload: ExportCardStudioPayload,
    session: Session = Depends(db_session),
) -> dict:
    """Génère les XLSX d'import CardStudio (un par groupe : KREISKER, SU…)."""
    try:
        fichiers = generer_exports_cardstudio(
            session=session, libelle_n=payload.annee_n
        )
    except ValueError as e:
        raise HTTPException(400, str(e)) from e

    return {
        "annee_n": payload.annee_n,
        "fichiers": [asdict(f) for f in fichiers],
    }
