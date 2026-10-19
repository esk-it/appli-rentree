"""Le fichier élèves du portail Sodexo — voir `services/sodexo_fichier.py`.

Lecture seule : l'édition Charlemagne entre, le CSV sort. Rien n'est écrit
en base ; l'envoi se déclare ensuite, comme avant, par « J'ai transmis ».
"""
from __future__ import annotations

import base64

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session

from backend.database import db_session

router = APIRouter(prefix="/api/sodexo", tags=["sodexo"])


class FichierPayload(BaseModel):
    fichier_base64: str
    nom_fichier: str
    annee_id: int | None = None


class ParticulierOut(BaseModel):
    badge: str
    nom: str
    prenom: str
    classe: str
    regime: str
    code: str


class FichierOut(BaseModel):
    nb_lignes_lues: int
    nb_eleves: int
    par_code: dict[str, int]
    particuliers: list[ParticulierOut]
    erreurs: list[str]
    avertissements: list[str]
    absents: list[str]
    inconnus: list[str]
    pret: bool
    nom_fichier: str
    csv_base64: str | None = None
    """Seulement quand rien n'arrête le fichier."""


@router.post("/fichier", response_model=FichierOut)
def fabriquer_fichier(payload: FichierPayload, session: Session = Depends(db_session)):
    """L'édition « Export vers SoHappy » → le CSV à importer, vérifié."""
    from backend.services.configuration import get_param
    from backend.services.sodexo_fichier import (
        PROFILS_ELEVES_DEFAUT,
        FichierSodexoImpossible,
        en_csv,
        fabriquer,
        nom_du_fichier,
    )

    try:
        contenu = base64.b64decode(payload.fichier_base64)
    except Exception as e:
        raise HTTPException(400, f"Base64 invalide : {e}") from None
    if not contenu:
        raise HTTPException(400, "Fichier vide.")
    profils = get_param(session, "sodexo.profils_eleves", PROFILS_ELEVES_DEFAUT)
    if isinstance(profils, str):
        profils = [p.strip() for p in profils.split(",")]
    try:
        r = fabriquer(session, contenu, payload.nom_fichier, profils=profils,
                      annee_id=payload.annee_id)
    except FichierSodexoImpossible as e:
        raise HTTPException(400, str(e)) from None
    return FichierOut(
        nb_lignes_lues=r.nb_lignes_lues,
        nb_eleves=len(r.eleves),
        par_code=r.par_code,
        particuliers=[
            ParticulierOut(badge=e.badge, nom=e.nom, prenom=e.prenom, classe=e.classe,
                           regime=e.regime, code=e.code)
            for e in r.particuliers
        ],
        erreurs=r.erreurs,
        avertissements=r.avertissements,
        absents=r.absents,
        inconnus=r.inconnus,
        pret=r.pret,
        nom_fichier=nom_du_fichier(),
        csv_base64=base64.b64encode(en_csv(r)).decode() if r.pret else None,
    )
