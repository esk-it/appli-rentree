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
from backend.models import AnneeScolaire, EleveSnapshot
from backend.services.exporters.cardstudio import generer_exports_cardstudio
from backend.services.exporters.google import generer_exports_google
from backend.services.exporters.google_adultes import generer_exports_google_adultes
from backend.services.exporters.koxo import generer_exports_koxo
from backend.services.exporters.koxo_adultes import generer_exports_koxo_adultes
from backend.services.exporters.pmb import generer_exports_pmb
from backend.services.exporters.smartair import (
    generer_exports_smartair,
    parser_export_smartair_n_minus_1,
)
from backend.services.exporters.tout import generer_tout

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


class ExportSmartAirPayload(BaseModel):
    annee_n: str = Field(..., description='Libellé de l\'année N, ex. "2026-2027"')
    contenu_smartair_n_minus_1: str | None = Field(
        None,
        description=(
            "Optionnel — contenu CSV d'un précédent export SmartAir. "
            "Permet de préserver les CardId hex et de calculer les Op a/b/m."
        ),
    )


@router.post("/smartair")
def exporter_smartair(
    payload: ExportSmartAirPayload,
    session: Session = Depends(db_session),
) -> dict:
    """Génère le CSV SmartAir pour l'année N.

    Si un export SmartAir N-1 est fourni (en contenu CSV brut), les CardId
    hexa sont préservés et les Op sont calculées (a/b/m).
    """
    card_ids: dict[int, str] | None = None
    badges_n_1: set[int] | None = None
    if payload.contenu_smartair_n_minus_1:
        try:
            card_ids, badges_n_1 = parser_export_smartair_n_minus_1(
                payload.contenu_smartair_n_minus_1
            )
        except Exception as e:
            raise HTTPException(400, f"Export SmartAir N-1 illisible : {e}") from e

    try:
        fichiers = generer_exports_smartair(
            session=session,
            libelle_n=payload.annee_n,
            card_ids_existants=card_ids,
            badges_n_minus_1=badges_n_1,
        )
    except ValueError as e:
        raise HTTPException(400, str(e)) from e

    return {
        "annee_n": payload.annee_n,
        "a_utilise_n_minus_1": bool(payload.contenu_smartair_n_minus_1),
        "fichiers": [asdict(f) for f in fichiers],
    }


class ExportGooglePayload(BaseModel):
    annee_n: str = Field(..., description='Libellé de l\'année N, ex. "2026-2027"')
    annee_n_minus_1: str | None = Field(
        None,
        description=(
            "Optionnel — libellé de l'année précédente. Si fourni, on génère "
            "aussi le fichier Nouveaux (entrants avec MDP)."
        ),
    )


@router.post("/google")
def exporter_google(
    payload: ExportGooglePayload,
    session: Session = Depends(db_session),
) -> dict:
    """Génère les CSV bulk-import Google Workspace pour l'année N."""
    badges_n_1: set[int] | None = None
    if payload.annee_n_minus_1:
        annee_n_1 = (
            session.query(AnneeScolaire)
            .filter_by(libelle=payload.annee_n_minus_1)
            .one_or_none()
        )
        if annee_n_1 is None:
            raise HTTPException(
                400, f"Snapshot N-1 introuvable : {payload.annee_n_minus_1}"
            )
        badges_n_1 = {
            e.num_badge
            for e in session.query(EleveSnapshot).filter_by(
                annee_scolaire_id=annee_n_1.id
            )
            if e.num_badge is not None
        }

    try:
        fichiers = generer_exports_google(
            session=session,
            libelle_n=payload.annee_n,
            badges_n_minus_1=badges_n_1,
        )
    except ValueError as e:
        raise HTTPException(400, str(e)) from e

    return {
        "annee_n": payload.annee_n,
        "annee_n_minus_1": payload.annee_n_minus_1,
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


class ExportKoxoAdultesPayload(BaseModel):
    annee_n: str = Field(...)
    annee_n_minus_1: str | None = Field(None)


@router.post("/koxo-adultes")
def exporter_koxo_adultes(
    payload: ExportKoxoAdultesPayload,
    session: Session = Depends(db_session),
) -> dict:
    """Génère les CSV KoXo adultes (Tous, Nouveaux, Anciens si N-1)."""
    try:
        fichiers = generer_exports_koxo_adultes(
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


class ExportGoogleAdultesPayload(BaseModel):
    annee_n: str = Field(...)
    annee_n_minus_1: str | None = Field(None)


@router.post("/google-adultes")
def exporter_google_adultes(
    payload: ExportGoogleAdultesPayload,
    session: Session = Depends(db_session),
) -> dict:
    """Génère les CSV Google Workspace pour le personnel."""
    try:
        fichiers = generer_exports_google_adultes(
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


class ExportToutPayload(BaseModel):
    annee_n: str = Field(..., description='Libellé de l\'année N')
    annee_n_minus_1: str | None = Field(
        None, description="Libellé année N-1 (active Nouveaux/Anciens)"
    )
    contenu_smartair_n_minus_1: str | None = Field(
        None, description="Contenu CSV SmartAir N-1 (optionnel)"
    )


@router.post("/tout")
def exporter_tout(
    payload: ExportToutPayload,
    session: Session = Depends(db_session),
) -> dict:
    """Lance tous les générateurs et bundle dans un ZIP unique."""
    try:
        res = generer_tout(
            session=session,
            libelle_n=payload.annee_n,
            libelle_n_minus_1=payload.annee_n_minus_1,
            contenu_smartair_n_minus_1=payload.contenu_smartair_n_minus_1,
        )
    except ValueError as e:
        raise HTTPException(400, str(e)) from e

    return asdict(res)
