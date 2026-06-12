"""Endpoints d'analytique sur les snapshots d'année.

Renvoie des comptages structurés (par niveau, classe, régime, établissement)
exploitables pour des graphiques côté UI.
"""
from __future__ import annotations

from collections import Counter

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy.orm import Session

from backend.database import db_session
from backend.models import AnneeScolaire, EleveSnapshot, Etablissement

router = APIRouter(prefix="/api/statistiques", tags=["statistiques"])


class Decompte(BaseModel):
    cle: str
    valeur: int


class StatistiquesAnnee(BaseModel):
    annee_libelle: str
    total: int
    par_etablissement: list[Decompte]
    par_niveau: list[Decompte]
    par_classe: list[Decompte]
    par_regime: list[Decompte]
    nouveaux: int  # flag Charlemagne
    classes_distinctes: int


@router.get("", response_model=StatistiquesAnnee)
def statistiques_annee(
    annee: str = Query(..., description="Libellé d'année, ex. 2025-2026"),
    session: Session = Depends(db_session),
) -> StatistiquesAnnee:
    """Renvoie des décomptes structurés pour l'année donnée."""
    a = session.query(AnneeScolaire).filter_by(libelle=annee).one_or_none()
    if a is None:
        raise HTTPException(404, f"Année introuvable : {annee}")

    etabs = {e.id: e for e in session.query(Etablissement).all()}
    eleves = (
        session.query(EleveSnapshot).filter_by(annee_scolaire_id=a.id).all()
    )

    par_etab: Counter[str] = Counter()
    par_niveau: Counter[str] = Counter()
    par_classe: Counter[str] = Counter()
    par_regime: Counter[str] = Counter()
    nouveaux = 0

    for e in eleves:
        etab = etabs.get(e.etablissement_id)
        if etab:
            par_etab[etab.code_court] += 1
        if e.code_niveau:
            par_niveau[e.code_niveau] += 1
        if e.code_classe:
            par_classe[e.code_classe] += 1
        if e.code_regime:
            par_regime[e.code_regime] += 1
        if e.est_nouveau_charlemagne:
            nouveaux += 1

    def vers_decomptes(c: Counter, *, tri_par_valeur: bool = True) -> list[Decompte]:
        items = c.most_common() if tri_par_valeur else sorted(c.items())
        return [Decompte(cle=k, valeur=v) for k, v in items]

    return StatistiquesAnnee(
        annee_libelle=a.libelle,
        total=len(eleves),
        par_etablissement=vers_decomptes(par_etab),
        par_niveau=vers_decomptes(par_niveau, tri_par_valeur=False),
        par_classe=vers_decomptes(par_classe, tri_par_valeur=False),
        par_regime=vers_decomptes(par_regime),
        nouveaux=nouveaux,
        classes_distinctes=len(par_classe),
    )
