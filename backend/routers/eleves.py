"""Endpoints d'accès aux EleveSnapshot persistés."""
from __future__ import annotations

from datetime import date

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy.orm import Session

from backend.database import db_session
from backend.models import AnneeScolaire, EleveSnapshot, Etablissement
from backend.services.regles_metier import email_lekreisker, login_koxo

router = APIRouter(prefix="/api/eleves", tags=["eleves"])


class EleveOut(BaseModel):
    id: int
    num_badge: int | None
    nom: str
    prenom: str
    etablissement_code: str
    etablissement_nom: str
    code_classe: str | None
    code_niveau: str | None
    code_regime: str | None
    est_nouveau_charlemagne: bool
    date_entree: date | None
    # Champs dérivés (utiles dans la liste / le détail)
    login_koxo: str
    email: str


@router.get("", response_model=list[EleveOut])
def lister_eleves(
    annee: str = Query(..., description="Libellé d'année, ex. 2025-2026"),
    session: Session = Depends(db_session),
) -> list[EleveOut]:
    """Liste tous les élèves d'un snapshot, avec champs dérivés (login/email)."""
    a = session.query(AnneeScolaire).filter_by(libelle=annee).one_or_none()
    if a is None:
        raise HTTPException(404, f"Année introuvable : {annee}")

    etabs = {e.id: e for e in session.query(Etablissement).all()}
    eleves = (
        session.query(EleveSnapshot)
        .filter_by(annee_scolaire_id=a.id)
        .order_by(EleveSnapshot.nom, EleveSnapshot.prenom)
        .all()
    )

    return [
        EleveOut(
            id=e.id,
            num_badge=e.num_badge,
            nom=e.nom,
            prenom=e.prenom,
            etablissement_code=etabs[e.etablissement_id].code_court
            if e.etablissement_id in etabs
            else "?",
            etablissement_nom=etabs[e.etablissement_id].nom_long
            if e.etablissement_id in etabs
            else "?",
            code_classe=e.code_classe,
            code_niveau=e.code_niveau,
            code_regime=e.code_regime,
            est_nouveau_charlemagne=e.est_nouveau_charlemagne,
            date_entree=e.date_entree,
            login_koxo=login_koxo(e.prenom or "", e.nom or ""),
            email=email_lekreisker(e.prenom or "", e.nom or ""),
        )
        for e in eleves
    ]
