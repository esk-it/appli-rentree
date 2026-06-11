"""Endpoint de comparaison N vs N-1."""
from __future__ import annotations

from dataclasses import asdict

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from backend.database import db_session
from backend.services.comparaison import comparer_annees

router = APIRouter(prefix="/api/comparaison", tags=["comparaison"])


@router.get("")
def comparer(
    annee_n: str = Query(..., description='Libellé de l\'année N, ex. "2026-2027"'),
    annee_n_minus_1: str = Query(..., description="Libellé de l'année précédente"),
    session: Session = Depends(db_session),
) -> dict:
    """Compare deux snapshots et renvoie entrants / restants / sortants.

    Returns:
        {
            "annee_n_libelle": "...",
            "annee_n_minus_1_libelle": "...",
            "entrants": [EleveResume, ...],
            "restants": [{ eleve_n: EleveResume, changements: [Changement, ...] }, ...],
            "sortants": [EleveResume, ...],
            "totaux": { "entrants": N, "restants": N, "sortants": N }
        }
    """
    try:
        res = comparer_annees(session, annee_n, annee_n_minus_1)
    except ValueError as e:
        raise HTTPException(400, str(e)) from e

    return {
        "annee_n_libelle": res.annee_n_libelle,
        "annee_n_minus_1_libelle": res.annee_n_minus_1_libelle,
        "totaux": {
            "entrants": len(res.entrants),
            "restants": len(res.restants),
            "sortants": len(res.sortants),
        },
        "entrants": [asdict(e) for e in res.entrants],
        "restants": [
            {
                "eleve_n": asdict(r.eleve_n),
                "changements": [asdict(c) for c in r.changements],
            }
            for r in res.restants
        ],
        "sortants": [asdict(e) for e in res.sortants],
    }
