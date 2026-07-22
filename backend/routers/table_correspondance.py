"""Endpoints CRUD de la table de correspondance classe → OU/groupe Google.

C'est la configuration métier centrale. Éditable dans l'interface, elle
sera enrichie/importée automatiquement au Lot 6. Ce routeur expose ce
qu'il faut pour l'écran d'édition manuel.
"""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from backend.database import db_session
from backend.models import Site, TableCorrespondance

router = APIRouter(prefix="/api/table-correspondance", tags=["table_correspondance"])


class LigneOut(BaseModel):
    id: int
    site_id: int
    site_nom: str
    classe_charlemagne_long: str
    classe_code_court: str
    groupe_google: str | None
    ou_pre_rentree: str
    ou_definitive: str
    groupe_profs_google: str | None


class LignePayload(BaseModel):
    site_id: int
    classe_charlemagne_long: str = Field(..., min_length=1, max_length=100)
    classe_code_court: str = Field(..., min_length=1, max_length=30)
    groupe_google: str | None = None
    ou_pre_rentree: str = Field(..., min_length=1, max_length=200)
    ou_definitive: str = Field(..., min_length=1, max_length=200)
    groupe_profs_google: str | None = None


def _serialiser(l: TableCorrespondance, sites_par_id: dict[int, Site]) -> LigneOut:
    return LigneOut(
        id=l.id,
        site_id=l.site_id,
        site_nom=sites_par_id[l.site_id].nom if l.site_id in sites_par_id else "?",
        classe_charlemagne_long=l.classe_charlemagne_long,
        classe_code_court=l.classe_code_court,
        groupe_google=l.groupe_google,
        ou_pre_rentree=l.ou_pre_rentree,
        ou_definitive=l.ou_definitive,
        groupe_profs_google=l.groupe_profs_google,
    )


@router.get("", response_model=list[LigneOut])
def lister(
    site: str | None = None, session: Session = Depends(db_session)
) -> list[LigneOut]:
    sites_par_id = {s.id: s for s in session.query(Site).all()}
    q = session.query(TableCorrespondance)
    if site:
        s_obj = next((v for v in sites_par_id.values() if v.nom == site), None)
        if not s_obj:
            return []
        q = q.filter_by(site_id=s_obj.id)
    q = q.order_by(TableCorrespondance.site_id, TableCorrespondance.classe_code_court)
    return [_serialiser(l, sites_par_id) for l in q.all()]


@router.post("", response_model=LigneOut)
def creer(
    payload: LignePayload, session: Session = Depends(db_session)
) -> LigneOut:
    sites_par_id = {s.id: s for s in session.query(Site).all()}
    if payload.site_id not in sites_par_id:
        raise HTTPException(400, f"Site {payload.site_id} introuvable")
    if (
        session.query(TableCorrespondance)
        .filter_by(site_id=payload.site_id, classe_code_court=payload.classe_code_court)
        .one_or_none()
    ):
        raise HTTPException(
            409,
            f"Ligne déjà présente : site={payload.site_id} classe={payload.classe_code_court}",
        )
    l = TableCorrespondance(**payload.model_dump())
    session.add(l)
    session.commit()
    session.refresh(l)
    return _serialiser(l, sites_par_id)


@router.put("/{ligne_id}", response_model=LigneOut)
def modifier(
    ligne_id: int, payload: LignePayload, session: Session = Depends(db_session)
) -> LigneOut:
    l = session.query(TableCorrespondance).filter_by(id=ligne_id).one_or_none()
    if l is None:
        raise HTTPException(404, "Ligne introuvable")
    for k, v in payload.model_dump().items():
        setattr(l, k, v)
    session.commit()
    session.refresh(l)
    sites_par_id = {s.id: s for s in session.query(Site).all()}
    return _serialiser(l, sites_par_id)


@router.delete("/{ligne_id}")
def supprimer(ligne_id: int, session: Session = Depends(db_session)) -> dict:
    l = session.query(TableCorrespondance).filter_by(id=ligne_id).one_or_none()
    if l is None:
        raise HTTPException(404, "Ligne introuvable")
    session.delete(l)
    session.commit()
    return {"ok": True, "supprime": ligne_id}
