"""Endpoints pour la gestion des chambres d'internat et des affectations."""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from backend.database import db_session
from backend.models import AffectationChambre, AnneeScolaire, Chambre, EleveSnapshot

router = APIRouter(prefix="/api/chambres", tags=["chambres"])


# ---------------------------------------------------------------------------
# Chambres (CRUD)
# ---------------------------------------------------------------------------


class ChambreOut(BaseModel):
    id: int
    numero: str
    batiment: str | None
    etage: str | None
    capacite_max: int
    notes: str | None
    nb_occupants: int = 0


class ChambrePayload(BaseModel):
    numero: str = Field(..., min_length=1)
    batiment: str | None = None
    etage: str | None = None
    capacite_max: int = 1
    notes: str | None = None


@router.get("", response_model=list[ChambreOut])
def lister_chambres(
    annee: str | None = None,
    session: Session = Depends(db_session),
) -> list[ChambreOut]:
    """Liste les chambres. Si `annee` fourni, ajoute le nb_occupants pour cette année."""
    chambres = session.query(Chambre).order_by(Chambre.numero).all()
    occupants_par_chambre: dict[int, int] = {}
    if annee:
        a = session.query(AnneeScolaire).filter_by(libelle=annee).one_or_none()
        if a is not None:
            ids_snapshots = [
                e.id
                for e in session.query(EleveSnapshot.id).filter_by(
                    annee_scolaire_id=a.id
                )
            ]
            for aff in (
                session.query(AffectationChambre)
                .filter(AffectationChambre.eleve_snapshot_id.in_(ids_snapshots))
                .all()
            ):
                occupants_par_chambre[aff.chambre_id] = (
                    occupants_par_chambre.get(aff.chambre_id, 0) + 1
                )
    return [
        ChambreOut(
            id=c.id,
            numero=c.numero,
            batiment=c.batiment,
            etage=c.etage,
            capacite_max=c.capacite_max,
            notes=c.notes,
            nb_occupants=occupants_par_chambre.get(c.id, 0),
        )
        for c in chambres
    ]


@router.post("", response_model=ChambreOut)
def creer_chambre(
    payload: ChambrePayload, session: Session = Depends(db_session)
) -> ChambreOut:
    if session.query(Chambre).filter_by(numero=payload.numero).one_or_none():
        raise HTTPException(409, f"Une chambre {payload.numero} existe déjà")
    c = Chambre(
        numero=payload.numero,
        batiment=payload.batiment,
        etage=payload.etage,
        capacite_max=payload.capacite_max,
        notes=payload.notes,
    )
    session.add(c)
    session.commit()
    session.refresh(c)
    return ChambreOut(
        id=c.id,
        numero=c.numero,
        batiment=c.batiment,
        etage=c.etage,
        capacite_max=c.capacite_max,
        notes=c.notes,
    )


@router.put("/{chambre_id}", response_model=ChambreOut)
def modifier_chambre(
    chambre_id: int,
    payload: ChambrePayload,
    session: Session = Depends(db_session),
) -> ChambreOut:
    c = session.query(Chambre).filter_by(id=chambre_id).one_or_none()
    if c is None:
        raise HTTPException(404, "Chambre introuvable")
    c.numero = payload.numero
    c.batiment = payload.batiment
    c.etage = payload.etage
    c.capacite_max = payload.capacite_max
    c.notes = payload.notes
    session.commit()
    session.refresh(c)
    return ChambreOut(
        id=c.id,
        numero=c.numero,
        batiment=c.batiment,
        etage=c.etage,
        capacite_max=c.capacite_max,
        notes=c.notes,
    )


@router.delete("/{chambre_id}")
def supprimer_chambre(
    chambre_id: int, session: Session = Depends(db_session)
) -> dict:
    c = session.query(Chambre).filter_by(id=chambre_id).one_or_none()
    if c is None:
        raise HTTPException(404, "Chambre introuvable")
    # Supprime les affectations liées
    session.query(AffectationChambre).filter_by(chambre_id=chambre_id).delete()
    session.delete(c)
    session.commit()
    return {"ok": True}


# ---------------------------------------------------------------------------
# Affectations
# ---------------------------------------------------------------------------


class AffectationPayload(BaseModel):
    eleve_snapshot_id: int
    chambre_id: int | None  # None = désaffecter


class AffectationOut(BaseModel):
    eleve_snapshot_id: int
    chambre_id: int | None
    chambre_numero: str | None


@router.put("/affectations", response_model=AffectationOut)
def affecter(
    payload: AffectationPayload, session: Session = Depends(db_session)
) -> AffectationOut:
    """Affecte un élève à une chambre, ou le désaffecte si chambre_id=None."""
    e = (
        session.query(EleveSnapshot)
        .filter_by(id=payload.eleve_snapshot_id)
        .one_or_none()
    )
    if e is None:
        raise HTTPException(404, "Élève snapshot introuvable")

    # Supprime affectation existante
    session.query(AffectationChambre).filter_by(
        eleve_snapshot_id=payload.eleve_snapshot_id
    ).delete()
    chambre_numero = None
    if payload.chambre_id is not None:
        c = session.query(Chambre).filter_by(id=payload.chambre_id).one_or_none()
        if c is None:
            raise HTTPException(404, "Chambre introuvable")
        session.add(
            AffectationChambre(
                chambre_id=payload.chambre_id,
                eleve_snapshot_id=payload.eleve_snapshot_id,
            )
        )
        chambre_numero = c.numero
    session.commit()
    return AffectationOut(
        eleve_snapshot_id=payload.eleve_snapshot_id,
        chambre_id=payload.chambre_id,
        chambre_numero=chambre_numero,
    )


@router.get("/affectations")
def lister_affectations(
    annee: str, session: Session = Depends(db_session)
) -> dict:
    """Retourne un dict eleve_snapshot_id → chambre_id pour une année."""
    a = session.query(AnneeScolaire).filter_by(libelle=annee).one_or_none()
    if a is None:
        raise HTTPException(404, "Année introuvable")
    ids = {
        e.id
        for e in session.query(EleveSnapshot.id).filter_by(annee_scolaire_id=a.id)
    }
    affectations = (
        session.query(AffectationChambre)
        .filter(AffectationChambre.eleve_snapshot_id.in_(ids))
        .all()
    )
    chambres = {c.id: c for c in session.query(Chambre).all()}
    return {
        str(aff.eleve_snapshot_id): {
            "chambre_id": aff.chambre_id,
            "chambre_numero": chambres[aff.chambre_id].numero
            if aff.chambre_id in chambres
            else None,
        }
        for aff in affectations
    }
