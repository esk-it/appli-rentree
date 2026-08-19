"""Endpoints de la bascule des OU Google."""
from __future__ import annotations

import base64

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy.orm import Session

from backend.database import db_session
from backend.services.bascule import (
    LIBELLE_PHASE,
    enregistrer_bascule,
    generer_csv_bascule,
    planifier_bascule,
)

router = APIRouter(prefix="/api/bascule", tags=["bascule"])


class MouvementOut(BaseModel):
    personne_id: int
    cle_pivot: str
    nom: str
    prenom: str
    classe: str | None
    site: str
    email: str | None
    ou_appliquee: str | None
    ou_visee: str | None
    statut: str
    motif: str


class RapportOut(BaseModel):
    phase: str
    phase_libelle: str
    annee_libelle: str
    sites: list[str]
    nb_total: int
    nb_a_deplacer: int
    nb_deja_en_place: int
    nb_bloques: int
    est_applicable: bool
    mouvements: list[MouvementOut]


def _planifier(session, annee_id, phase, site_id):
    try:
        return planifier_bascule(
            session, annee_id=annee_id, phase=phase, site_id=site_id
        )
    except ValueError as e:
        code = 400 if "phase" in str(e) else 404
        raise HTTPException(code, str(e)) from None


def _en_sortie(r) -> RapportOut:
    return RapportOut(
        phase=r.phase,
        phase_libelle=LIBELLE_PHASE[r.phase],
        annee_libelle=r.annee_libelle,
        sites=r.sites,
        nb_total=r.nb_total,
        nb_a_deplacer=r.nb_a_deplacer,
        nb_deja_en_place=r.nb_deja_en_place,
        nb_bloques=r.nb_bloques,
        est_applicable=r.est_applicable,
        mouvements=[MouvementOut(**vars(m)) for m in r.mouvements],
    )


@router.get("", response_model=RapportOut)
def planifier(
    annee_id: int = Query(..., description="Année dont on prépare la rentrée"),
    phase: str = Query(..., description="`pre_rentree` ou `definitive`"),
    site_id: int | None = Query(None, description="Un site, ou tous si absent"),
    session: Session = Depends(db_session),
) -> RapportOut:
    """Ce que la bascule ferait — ne modifie rien."""
    return _en_sortie(_planifier(session, annee_id, phase, site_id))


class FichierOut(BaseModel):
    nom_fichier: str
    contenu_base64: str
    nb_lignes: int


@router.get("/csv", response_model=FichierOut)
def telecharger_csv(
    annee_id: int = Query(...),
    phase: str = Query(...),
    site_id: int | None = Query(None),
    session: Session = Depends(db_session),
) -> FichierOut:
    """CSV de mise à jour d'OU pour la console Google Admin."""
    r = _planifier(session, annee_id, phase, site_id)
    contenu = generer_csv_bascule(r)
    portee = "_".join(r.sites) if len(r.sites) <= 3 else "tous"
    suffixe = "pre-rentree" if r.phase == "pre_rentree" else "definitive"
    return FichierOut(
        nom_fichier=f"Google_OU_{suffixe}_{portee}_{r.annee_libelle}.csv",
        contenu_base64=base64.b64encode(contenu).decode("ascii"),
        nb_lignes=r.nb_a_deplacer,
    )


class ConfirmationPayload(BaseModel):
    annee_id: int
    phase: str
    site_id: int | None = None
    mode: str = "simulation"


class ConfirmationOut(BaseModel):
    nb_enregistres: int
    mode: str
    message: str


@router.post("/confirmer", response_model=ConfirmationOut)
def confirmer(
    payload: ConfirmationPayload, session: Session = Depends(db_session)
) -> ConfirmationOut:
    """Enregistre que la bascule a été appliquée côté Google.

    À appeler **après** l'import du CSV dans la console Admin. Le programme
    n'agit pas sur Google : il prend acte, pour savoir ensuite qui reste à
    déplacer.
    """
    if payload.mode not in ("simulation", "reel"):
        raise HTTPException(400, f"mode invalide : {payload.mode!r}")
    r = _planifier(session, payload.annee_id, payload.phase, payload.site_id)
    if not r.est_applicable:
        raise HTTPException(
            409,
            f"{r.nb_bloques} élève(s) sans OU calculable — complète la Table de "
            "correspondance avant de confirmer.",
        )
    n = enregistrer_bascule(session, r, mode=payload.mode)
    return ConfirmationOut(
        nb_enregistres=n,
        mode=payload.mode,
        message=(
            f"{n} déplacement(s) enregistré(s)"
            if payload.mode == "reel"
            else f"{n} déplacement(s) seraient enregistrés"
        ),
    )
