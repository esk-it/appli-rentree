"""Endpoints de l'atelier des cartes — CardStudio.

Le fichier se fabrique depuis le référentiel : aucun export de Charlemagne
n'est demandé pour produire des cartes. L'apprentissage, lui, en lit un —
une fois, pour les trois choses que le référentiel ne peut pas connaître.
"""
from __future__ import annotations

import base64
import binascii

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session

from backend.database import db_session
from backend.services.cartes_cardstudio import (
    CHAMBRES,
    CartesImpossibles,
    apprendre_depuis_export,
    construire_fichier,
    lister_candidats,
)

router = APIRouter(prefix="/api/cartes", tags=["cartes"])


class CandidatOut(BaseModel):
    personne_id: int
    badge: int | None
    nom: str
    prenom: str
    nom_complet: str
    classe: str
    site: str | None
    regime: str | None
    a_une_photo: bool
    codes_connus: bool


class CandidatsReponse(BaseModel):
    candidats: list[CandidatOut]
    nb_chambres: int
    """Combien de lignes de chambre la case à cocher ajoutera."""


@router.get("/candidats", response_model=CandidatsReponse)
def candidats(
    annee_id: int | None = None, session: Session = Depends(db_session)
) -> CandidatsReponse:
    """Tous les élèves de l'année, avec l'état de leur photo.

    La liste part entière : le filtrage par site et par classe se fait dans
    l'écran, où cocher et décocher doit être instantané. Un aller-retour par
    changement de filtre rendrait le choix pénible, et c'est précisément ce
    qu'on cherche à réparer.
    """
    try:
        trouves = lister_candidats(session, annee_id=annee_id)
    except CartesImpossibles as e:
        raise HTTPException(400, str(e))
    return CandidatsReponse(
        candidats=[CandidatOut(**vars(c)) for c in trouves],
        nb_chambres=len(CHAMBRES),
    )


class FichierPayload(BaseModel):
    personne_ids: list[int]
    annee_id: int | None = None
    avec_chambres: bool = False
    intitule: str = ""


class FichierReponse(BaseModel):
    nom_fichier: str
    contenu_base64: str
    nb_cartes: int
    nb_chambres: int
    sans_photo: list[str]
    classes_sans_codes: list[str]
    sans_date_entree: int
    photos_indisponibles: str | None


@router.post("/fichier", response_model=FichierReponse)
def fichier(
    payload: FichierPayload, session: Session = Depends(db_session)
) -> FichierReponse:
    """Le classeur à importer dans CardStudio, pour les élèves cochés."""
    try:
        contenu, rapport = construire_fichier(
            session,
            personne_ids=payload.personne_ids,
            annee_id=payload.annee_id,
            avec_chambres=payload.avec_chambres,
            intitule=payload.intitule,
        )
    except CartesImpossibles as e:
        raise HTTPException(400, str(e))
    return FichierReponse(
        nom_fichier=rapport.nom_fichier_suggere,
        contenu_base64=base64.b64encode(contenu).decode("ascii"),
        nb_cartes=rapport.nb_cartes,
        nb_chambres=rapport.nb_chambres,
        sans_photo=rapport.sans_photo,
        classes_sans_codes=rapport.classes_sans_codes,
        sans_date_entree=rapport.sans_date_entree,
        photos_indisponibles=rapport.photos_indisponibles,
    )


class ApprentissagePayload(BaseModel):
    contenu_base64: str
    nom_fichier: str


class ApprentissageReponse(BaseModel):
    nb_lignes_lues: int
    classes_apprises: list[str]
    classes_inconnues: list[str]
    nb_dates_apprises: int
    nb_photos_memorisees: int
    badges_inconnus: int


@router.post("/apprendre", response_model=ApprentissageReponse)
def apprendre(
    payload: ApprentissagePayload, session: Session = Depends(db_session)
) -> ApprentissageReponse:
    """Enseigne les codes de classe et les dates d'entrée depuis un export.

    Opération d'installation, pas d'usage courant : une fois faite, le
    programme n'a plus besoin de Charlemagne pour fabriquer des cartes.
    """
    try:
        brut = base64.b64decode(payload.contenu_base64)
    except (ValueError, binascii.Error):
        raise HTTPException(400, "Contenu illisible : base64 invalide.")
    try:
        rapport = apprendre_depuis_export(
            session, contenu=brut, nom_fichier=payload.nom_fichier
        )
    except CartesImpossibles as e:
        raise HTTPException(400, str(e))
    return ApprentissageReponse(**vars(rapport))
