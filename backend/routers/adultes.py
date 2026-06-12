"""Endpoints pour les adultes/personnel : ingestion et listing."""
from __future__ import annotations

from datetime import date

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from backend.config import DOSSIER_INPUT
from backend.database import db_session
from backend.models import AdulteSnapshot, AnneeScolaire, Etablissement
from backend.services.ingestion_adultes import ingerer_export_adultes
from backend.services.regles_metier import email_lekreisker, login_koxo

router = APIRouter(prefix="/api/adultes", tags=["adultes"])


class IngererAdultesPayload(BaseModel):
    nom_fichier: str = Field(..., description="Nom du fichier dans data/input/")
    libelle_annee: str = Field(..., description='Ex: "2025-2026"')
    remplacer_si_existe: bool = Field(False)


@router.post("/ingerer")
def ingerer_adultes(
    payload: IngererAdultesPayload,
    session: Session = Depends(db_session),
) -> dict:
    """Ingère un export Charlemagne adultes comme snapshot."""
    chemin = DOSSIER_INPUT / payload.nom_fichier
    if not chemin.exists():
        raise HTTPException(404, f"Fichier introuvable : {payload.nom_fichier}")
    try:
        return ingerer_export_adultes(
            session=session,
            chemin_fichier=chemin,
            libelle_annee=payload.libelle_annee,
            remplacer_si_existe=payload.remplacer_si_existe,
        )
    except ValueError as e:
        raise HTTPException(400, str(e)) from e
    except Exception as e:
        session.rollback()
        raise HTTPException(500, f"Échec ingestion adultes : {e}") from e


class AdulteOut(BaseModel):
    id: int
    num_personnel: int | None
    civilite: str | None
    nom: str
    prenom: str
    fonction: str | None
    matieres: str | None
    email_personnel: str | None
    etablissement_code: str | None
    est_nouveau_charlemagne: bool
    date_naissance: date | None
    login_koxo: str
    email_calcule: str


@router.get("", response_model=list[AdulteOut])
def lister_adultes(
    annee: str,
    session: Session = Depends(db_session),
) -> list[AdulteOut]:
    """Liste tous les adultes d'un snapshot avec champs dérivés."""
    a = session.query(AnneeScolaire).filter_by(libelle=annee).one_or_none()
    if a is None:
        raise HTTPException(404, f"Année introuvable : {annee}")

    etabs = {e.id: e for e in session.query(Etablissement).all()}
    adultes = (
        session.query(AdulteSnapshot)
        .filter_by(annee_scolaire_id=a.id)
        .order_by(AdulteSnapshot.nom, AdulteSnapshot.prenom)
        .all()
    )

    return [
        AdulteOut(
            id=ad.id,
            num_personnel=ad.num_personnel,
            civilite=ad.civilite,
            nom=ad.nom,
            prenom=ad.prenom,
            fonction=ad.fonction,
            matieres=ad.matieres,
            email_personnel=ad.email_personnel,
            etablissement_code=etabs[ad.etablissement_id].code_court
            if ad.etablissement_id and ad.etablissement_id in etabs
            else None,
            est_nouveau_charlemagne=ad.est_nouveau_charlemagne,
            date_naissance=ad.date_naissance,
            login_koxo=login_koxo(ad.prenom or "", ad.nom or ""),
            email_calcule=email_lekreisker(ad.prenom or "", ad.nom or ""),
        )
        for ad in adultes
    ]
