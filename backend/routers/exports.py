"""Endpoints d'exports vers les cibles (KoXo, Google, PMB, JPM…).

Pour l'instant : KoXo uniquement (Lot 8a). Google et suivants viennent après.

Deux modes de retour possibles :
- `Response(content=..., media_type="text/csv")` : téléchargement direct
- JSON avec le contenu en base64 : pour le frontend qui affiche puis propose
  le download (choix Tauri pour éviter les popups navigateur).
"""
from __future__ import annotations

import base64
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session

from backend.database import db_session
from backend.services.exports_google import generer_csv_google
from backend.services.exports_koxo import generer_csv_koxo

router = APIRouter(prefix="/api/exports", tags=["exports"])


class ExportKoxoPayload(BaseModel):
    site_id: int
    type_personne: Literal["eleve", "adulte"]
    categorie: Literal["tous", "nouveaux", "anciens"]
    annee_cible_id: int
    annee_source_id: int | None = None


class ExportKoxoReponse(BaseModel):
    site_nom: str
    type_personne: str
    categorie: str
    nb_lignes: int
    nom_fichier: str
    contenu_base64: str
    """Contenu CSV encodé cp1252 puis base64 — le frontend décode et déclenche
    le téléchargement."""


@router.post("/koxo", response_model=ExportKoxoReponse)
def exporter_koxo(
    payload: ExportKoxoPayload, session: Session = Depends(db_session)
) -> ExportKoxoReponse:
    """Génère un CSV KoXo (Tous / Nouveaux / Anciens) pour un site donné."""
    try:
        contenu, rapport = generer_csv_koxo(
            session=session,
            site_id=payload.site_id,
            type_personne=payload.type_personne,
            categorie=payload.categorie,
            annee_cible_id=payload.annee_cible_id,
            annee_source_id=payload.annee_source_id,
        )
    except ValueError as e:
        raise HTTPException(400, str(e))

    return ExportKoxoReponse(
        site_nom=rapport.site_nom,
        type_personne=rapport.type_personne,
        categorie=rapport.categorie,
        nb_lignes=rapport.nb_lignes,
        nom_fichier=rapport.nom_fichier_suggere,
        contenu_base64=base64.b64encode(contenu).decode("ascii"),
    )


# ---------------------------------------------------------------------------
# Google Workspace (Lot 10a)
# ---------------------------------------------------------------------------


class ExportGooglePayload(BaseModel):
    site_id: int
    type_personne: Literal["eleve", "adulte"]
    categorie: Literal["tous", "nouveaux", "anciens"]
    annee_cible_id: int
    annee_source_id: int | None = None


class ExportGoogleReponse(BaseModel):
    site_nom: str
    type_personne: str
    categorie: str
    nb_lignes: int
    nb_sans_ou: int
    nom_fichier: str
    contenu_base64: str


@router.post("/google", response_model=ExportGoogleReponse)
def exporter_google(
    payload: ExportGooglePayload, session: Session = Depends(db_session)
) -> ExportGoogleReponse:
    """Génère un CSV Google Admin bulk-import."""
    try:
        contenu, rapport = generer_csv_google(
            session=session,
            site_id=payload.site_id,
            type_personne=payload.type_personne,
            categorie=payload.categorie,
            annee_cible_id=payload.annee_cible_id,
            annee_source_id=payload.annee_source_id,
        )
    except ValueError as e:
        raise HTTPException(400, str(e))

    return ExportGoogleReponse(
        site_nom=rapport.site_nom,
        type_personne=rapport.type_personne,
        categorie=rapport.categorie,
        nb_lignes=rapport.nb_lignes,
        nb_sans_ou=rapport.nb_sans_ou,
        nom_fichier=rapport.nom_fichier_suggere,
        contenu_base64=base64.b64encode(contenu).decode("ascii"),
    )
