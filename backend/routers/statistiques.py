"""Endpoints des statistiques (Lot 13)."""
from __future__ import annotations

from dataclasses import asdict

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session

from backend.database import db_session
from backend.services.statistiques import stats_annee, stats_referentiel

router = APIRouter(prefix="/api/statistiques", tags=["statistiques"])


class StatValeurOut(BaseModel):
    label: str
    valeur: int


class ReferentielOut(BaseModel):
    nb_personnes_total: int
    nb_eleves_total: int
    nb_adultes_total: int
    nb_sites: int
    nb_annees_scolaires: int
    nb_arbitrages_en_attente: int
    nb_arbitrages_tranches: int


class AnneeOut(BaseModel):
    annee_id: int
    annee_libelle: str
    nb_personnes: int
    nb_eleves: int
    nb_adultes: int
    par_site: list[StatValeurOut]
    par_regime: list[StatValeurOut]
    par_niveau: list[StatValeurOut]
    par_etablissement_charlemagne: list[StatValeurOut]


@router.get("/referentiel", response_model=ReferentielOut)
def obtenir_referentiel(session: Session = Depends(db_session)) -> ReferentielOut:
    return ReferentielOut(**asdict(stats_referentiel(session)))


@router.get("/annee/{annee_id}", response_model=AnneeOut)
def obtenir_annee(annee_id: int, session: Session = Depends(db_session)) -> AnneeOut:
    try:
        s = stats_annee(session, annee_id)
    except ValueError as e:
        raise HTTPException(404, str(e))
    return AnneeOut(**asdict(s))
