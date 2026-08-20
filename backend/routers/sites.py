"""Endpoints CRUD des sites (NDE, NDK, SU).

Un site est un référentiel : nom, domaine mail Google Workspace, préfixe
d'arborescence OU. Rarement modifié après amorçage, mais éditable.
"""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from backend.database import db_session
from backend.models import Site

router = APIRouter(prefix="/api/sites", tags=["sites"])


class SiteOut(BaseModel):
    id: int
    nom: str
    nom_complet: str
    domaine_mail: str
    ou_sortants: str | None = None
    prefixe_annee_ou: str
    numero_ordre: int
    prefixe_racine_ou: str


class SitePayload(BaseModel):
    nom: str = Field(..., min_length=1, max_length=20)
    nom_complet: str = Field(..., min_length=1, max_length=150)
    domaine_mail: str = Field(..., min_length=3, max_length=100)
    ou_sortants: str | None = Field(None, max_length=200)
    prefixe_annee_ou: str = Field(..., min_length=1, max_length=20)
    numero_ordre: int = Field(..., ge=1)


def _serialiser(s: Site) -> SiteOut:
    return SiteOut(
        id=s.id,
        nom=s.nom,
        nom_complet=s.nom_complet,
        domaine_mail=s.domaine_mail,
        ou_sortants=s.ou_sortants,
        prefixe_annee_ou=s.prefixe_annee_ou,
        numero_ordre=s.numero_ordre,
        prefixe_racine_ou=s.prefixe_racine_ou(),
    )


@router.get("", response_model=list[SiteOut])
def lister_sites(session: Session = Depends(db_session)) -> list[SiteOut]:
    return [_serialiser(s) for s in session.query(Site).order_by(Site.numero_ordre).all()]


@router.post("", response_model=SiteOut)
def creer_site(
    payload: SitePayload, session: Session = Depends(db_session)
) -> SiteOut:
    if session.query(Site).filter_by(nom=payload.nom).one_or_none():
        raise HTTPException(409, f"Un site {payload.nom} existe déjà")
    s = Site(
        nom=payload.nom,
        nom_complet=payload.nom_complet,
        domaine_mail=payload.domaine_mail,
        ou_sortants=payload.ou_sortants,
        prefixe_annee_ou=payload.prefixe_annee_ou,
        numero_ordre=payload.numero_ordre,
    )
    session.add(s)
    session.commit()
    session.refresh(s)
    return _serialiser(s)


@router.put("/{site_id}", response_model=SiteOut)
def modifier_site(
    site_id: int, payload: SitePayload, session: Session = Depends(db_session)
) -> SiteOut:
    s = session.query(Site).filter_by(id=site_id).one_or_none()
    if s is None:
        raise HTTPException(404, "Site introuvable")
    s.nom = payload.nom
    s.nom_complet = payload.nom_complet
    s.domaine_mail = payload.domaine_mail
    s.ou_sortants = payload.ou_sortants
    s.prefixe_annee_ou = payload.prefixe_annee_ou
    s.numero_ordre = payload.numero_ordre
    session.commit()
    session.refresh(s)
    return _serialiser(s)


@router.delete("/{site_id}")
def supprimer_site(site_id: int, session: Session = Depends(db_session)) -> dict:
    s = session.query(Site).filter_by(id=site_id).one_or_none()
    if s is None:
        raise HTTPException(404, "Site introuvable")
    session.delete(s)
    session.commit()
    return {"ok": True, "supprime": site_id}
