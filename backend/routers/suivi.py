"""Endpoints du suivi CompteCible (Lot 12)."""
from __future__ import annotations

from datetime import date

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session

from backend.database import db_session
from backend.services.suivi import (
    comptes_a_purger,
    lister_par_etat,
    marquer_sortant,
    stats_suivi,
)

router = APIRouter(prefix="/api/suivi", tags=["suivi"])


class StatsOut(BaseModel):
    par_cible: dict[str, dict[str, int]]
    total_par_etat: dict[str, int]
    nb_purges_echues: int


@router.get("/stats", response_model=StatsOut)
def obtenir_stats(session: Session = Depends(db_session)) -> StatsOut:
    s = stats_suivi(session)
    return StatsOut(
        par_cible=s.par_cible,
        total_par_etat=s.total_par_etat,
        nb_purges_echues=s.nb_purges_echues,
    )


class LigneCompteOut(BaseModel):
    id: int
    personne_id: int
    cle_pivot: str
    nom: str
    prenom: str
    login: str
    site_nom: str | None
    cible: str
    etat: str
    identifiant_externe: str | None
    date_prevue_purge: date | None
    note: str | None


@router.get("/liste", response_model=list[LigneCompteOut])
def lister(
    etat: str, cible: str | None = None, session: Session = Depends(db_session)
) -> list[LigneCompteOut]:
    try:
        rows = lister_par_etat(session, etat, cible)
    except ValueError as e:
        raise HTTPException(400, str(e))
    return [
        LigneCompteOut(
            id=c.id,
            personne_id=p.id, cle_pivot=p.cle_pivot,
            nom=p.nom, prenom=p.prenom, login=p.login,
            site_nom=s.nom if s else None,
            cible=c.cible, etat=c.etat,
            identifiant_externe=c.identifiant_externe,
            date_prevue_purge=c.date_prevue_purge, note=c.note,
        )
        for c, p, s in rows
    ]


@router.get("/purges-echues", response_model=list[LigneCompteOut])
def lister_purges(session: Session = Depends(db_session)) -> list[LigneCompteOut]:
    comptes = comptes_a_purger(session)
    resultat = []
    for c in comptes:
        p = c.personne
        resultat.append(LigneCompteOut(
            id=c.id, personne_id=p.id, cle_pivot=p.cle_pivot,
            nom=p.nom, prenom=p.prenom, login=p.login,
            site_nom=p.site.nom if p.site else None,
            cible=c.cible, etat=c.etat,
            identifiant_externe=c.identifiant_externe,
            date_prevue_purge=c.date_prevue_purge, note=c.note,
        ))
    return resultat


class MarquerSortantPayload(BaseModel):
    personne_id: int
    cible: str


@router.post("/marquer-sortant")
def poster_sortant(
    payload: MarquerSortantPayload, session: Session = Depends(db_session)
) -> dict:
    try:
        t = marquer_sortant(session, payload.personne_id, payload.cible)
    except ValueError as e:
        raise HTTPException(400, str(e))
    session.commit()
    return {
        "ok": True,
        "personne_id": t.personne_id, "cible": t.cible,
        "etat_avant": t.etat_avant, "etat_apres": t.etat_apres,
        "date_prevue_purge": t.date_prevue_purge.isoformat() if t.date_prevue_purge else None,
    }
