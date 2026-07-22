"""Endpoints d'aide au calcul et à la vérification des logins.

Ces endpoints ne créent rien — ils préparent les informations dont l'écran
d'arbitrage (Lot 5) aura besoin pour permettre à l'utilisateur de trancher
sur les collisions de login.
"""
from __future__ import annotations

from dataclasses import asdict

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel
from sqlalchemy.orm import Session

from backend.database import db_session
from backend.services.regles_metier import (
    DEFAUT_LONGUEUR_MAX_LOGIN,
    calculer_login_base,
    login_est_libre,
    proposer_login_pour,
    proposer_suffixe,
)

router = APIRouter(prefix="/api/logins", tags=["logins"])


class VerificationOut(BaseModel):
    login: str
    libre: bool


@router.get("/verifier", response_model=VerificationOut)
def verifier(
    login: str = Query(..., min_length=1),
    session: Session = Depends(db_session),
) -> VerificationOut:
    """True si aucune Personne n'a ce login (référentiel entier, tous types)."""
    return VerificationOut(login=login, libre=login_est_libre(session, login))


class ResumeConflitOut(BaseModel):
    personne_id: int
    cle_pivot: str
    login: str
    nom: str
    prenom: str
    type: str


class PropositionOut(BaseModel):
    login_base: str
    login_propose: str
    suffixe_utilise: int
    a_conflit: bool
    personnes_en_conflit: list[ResumeConflitOut]


@router.get("/proposer", response_model=PropositionOut | None)
def proposer(
    prenom: str = Query(..., min_length=0),
    nom: str = Query(..., min_length=1),
    longueur_max: int = Query(DEFAUT_LONGUEUR_MAX_LOGIN, ge=3, le=30),
    session: Session = Depends(db_session),
) -> PropositionOut | None:
    """Propose un login libre pour (prenom, nom), avec le contexte d'arbitrage."""
    resultat = proposer_login_pour(session, prenom, nom, longueur_max=longueur_max)
    if resultat is None:
        return None
    return PropositionOut(**asdict(resultat))


class LoginBaseOut(BaseModel):
    login_base: str


@router.get("/base", response_model=LoginBaseOut)
def base(
    prenom: str = Query(...),
    nom: str = Query(...),
    longueur_max: int = Query(DEFAUT_LONGUEUR_MAX_LOGIN, ge=3, le=30),
) -> LoginBaseOut:
    """Retourne juste le login canonique sans consultation du référentiel."""
    return LoginBaseOut(login_base=calculer_login_base(prenom, nom, longueur_max))


@router.get("/proposer-depuis-base", response_model=PropositionOut | None)
def proposer_depuis_base(
    login_base: str = Query(..., min_length=1),
    session: Session = Depends(db_session),
) -> PropositionOut | None:
    """Variante : propose un suffixe libre à partir d'un login base déjà calculé."""
    resultat = proposer_suffixe(session, login_base)
    if resultat is None:
        return None
    return PropositionOut(**asdict(resultat))
