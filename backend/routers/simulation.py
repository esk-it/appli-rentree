"""Endpoint du moteur de simulation transverse (Lot 7)."""
from __future__ import annotations

from dataclasses import asdict

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy.orm import Session

from backend.database import db_session
from backend.services.simulation_globale import (
    RapportSimulation,
    rendre_rapport_csv,
    rendre_rapport_texte,
    simuler_globalement,
)

router = APIRouter(prefix="/api/simulation", tags=["simulation"])


class LigneOut(BaseModel):
    site_id: int
    site_nom: str
    type_personne: str
    cible: str
    nouveaux: int
    identiques: int
    modifies: int
    sortants: int
    total_operations: int


class BlocageOut(BaseModel):
    type: str
    description: str
    valeur: str | None = None


class RapportOut(BaseModel):
    annee_source_id: int
    annee_source_libelle: str
    annee_cible_id: int
    annee_cible_libelle: str
    lignes: list[LigneOut]
    blocages: list[BlocageOut]
    nb_arbitrages_en_attente: int
    totaux_par_cible: dict[str, dict[str, int]]
    est_pret_a_executer: bool


def _to_out(r: RapportSimulation) -> RapportOut:
    return RapportOut(
        annee_source_id=r.annee_source_id,
        annee_source_libelle=r.annee_source_libelle,
        annee_cible_id=r.annee_cible_id,
        annee_cible_libelle=r.annee_cible_libelle,
        lignes=[
            LigneOut(
                site_id=l.site_id,
                site_nom=l.site_nom,
                type_personne=l.type_personne,
                cible=l.cible,
                nouveaux=l.nouveaux,
                identiques=l.identiques,
                modifies=l.modifies,
                sortants=l.sortants,
                total_operations=l.total_operations,
            )
            for l in r.lignes
        ],
        blocages=[BlocageOut(**asdict(b)) for b in r.blocages],
        nb_arbitrages_en_attente=r.nb_arbitrages_en_attente,
        totaux_par_cible=r.totaux_par_cible,
        est_pret_a_executer=r.est_pret_a_executer,
    )


@router.get("", response_model=RapportOut)
def obtenir_simulation(
    annee_source_id: int = Query(...),
    annee_cible_id: int = Query(...),
    session: Session = Depends(db_session),
) -> RapportOut:
    """Rapport transverse : ce que le programme ferait par cible/site/type."""
    try:
        rapport = simuler_globalement(session, annee_source_id, annee_cible_id)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    return _to_out(rapport)


class RapportExportOut(BaseModel):
    format: str
    nom_fichier: str
    contenu_base64: str


@router.get("/export", response_model=RapportExportOut)
def exporter_simulation(
    annee_source_id: int = Query(...),
    annee_cible_id: int = Query(...),
    format: str = Query("texte", pattern="^(texte|csv)$"),
    session: Session = Depends(db_session),
) -> RapportExportOut:
    """Rapport de simulation archivable — texte lisible ou CSV pour tableur."""
    import base64

    try:
        rapport = simuler_globalement(session, annee_source_id, annee_cible_id)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))

    if format == "csv":
        contenu = rendre_rapport_csv(rapport)
        extension = "csv"
    else:
        contenu = rendre_rapport_texte(rapport)
        extension = "txt"

    nom = (
        f"Simulation_{rapport.annee_source_libelle}_vers_"
        f"{rapport.annee_cible_libelle}.{extension}"
    )
    return RapportExportOut(
        format=format,
        nom_fichier=nom,
        contenu_base64=base64.b64encode(contenu.encode("utf-8")).decode("ascii"),
    )
