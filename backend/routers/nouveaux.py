"""Endpoints de la liste des nouveaux arrivants.

Liste de relecture humaine : on la lit à l'écran, on l'imprime, ou on
l'ouvre dans Excel pour la faire valider par un collègue. Rien à voir
avec les exports de `/api/exports`, qui alimentent des systèmes cibles.
"""
from __future__ import annotations

import base64
from datetime import date

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy.orm import Session

from backend.database import db_session
from backend.services.nouveaux_arrivants import (
    generer_csv_nouveaux,
    lister_nouveaux_arrivants,
)

router = APIRouter(prefix="/api/nouveaux", tags=["nouveaux"])


class ArrivantOut(BaseModel):
    personne_id: int
    cle_pivot: str
    type: str
    badge: int
    nom: str
    prenom: str
    classe: str | None
    niveau: str | None
    site: str | None
    regime: str | None
    login: str
    email: str | None
    date_entree: date | None
    classe_precedente: str | None
    statut: str
    motif: str


class RapportOut(BaseModel):
    annee_libelle: str
    annee_source_libelle: str | None
    nb_total: int
    nb_nouveaux: int
    nb_a_verifier: int
    arrivants: list[ArrivantOut]


def _construire(
    session: Session,
    annee_id: int,
    site_id: int | None,
    type_personne: str | None,
    annee_source_id: int | None,
    inclure_a_verifier: bool,
):
    if type_personne is not None and type_personne not in ("eleve", "adulte"):
        raise HTTPException(400, f"type invalide : {type_personne!r}")
    try:
        return lister_nouveaux_arrivants(
            session,
            annee_id=annee_id,
            site_id=site_id,
            type_personne=type_personne,
            annee_source_id=annee_source_id,
            inclure_a_verifier=inclure_a_verifier,
        )
    except ValueError as e:
        raise HTTPException(404, str(e)) from None


@router.get("", response_model=RapportOut)
def lister(
    annee_id: int = Query(..., description="Année de rentrée à préparer"),
    site_id: int | None = Query(None),
    type: str | None = Query(None, description="`eleve` ou `adulte`"),
    annee_source_id: int | None = Query(
        None, description="Année de référence, si elle a été ingérée"
    ),
    inclure_a_verifier: bool = Query(True),
    session: Session = Depends(db_session),
) -> RapportOut:
    """Les personnes pour lesquelles un compte reste à créer."""
    r = _construire(
        session, annee_id, site_id, type, annee_source_id, inclure_a_verifier
    )
    return RapportOut(
        annee_libelle=r.annee_libelle,
        annee_source_libelle=r.annee_source_libelle,
        nb_total=r.nb_total,
        nb_nouveaux=r.nb_nouveaux,
        nb_a_verifier=r.nb_a_verifier,
        arrivants=[ArrivantOut(**vars(a)) for a in r.arrivants],
    )


class FichierOut(BaseModel):
    nom_fichier: str
    contenu_base64: str
    nb_lignes: int


@router.get("/csv", response_model=FichierOut)
def telecharger_csv(
    annee_id: int = Query(...),
    site_id: int | None = Query(None),
    type: str | None = Query(None),
    annee_source_id: int | None = Query(None),
    inclure_a_verifier: bool = Query(True),
    session: Session = Depends(db_session),
) -> FichierOut:
    """Même liste, au format tableur (`;` + BOM, ouvrable dans Excel)."""
    r = _construire(
        session, annee_id, site_id, type, annee_source_id, inclure_a_verifier
    )
    contenu = generer_csv_nouveaux(r)
    suffixe = r.annee_libelle.replace("/", "-")
    return FichierOut(
        nom_fichier=f"Nouveaux_arrivants_{suffixe}.csv",
        contenu_base64=base64.b64encode(contenu).decode("ascii"),
        nb_lignes=r.nb_total,
    )
