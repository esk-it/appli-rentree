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
from backend.services.exports_cardstudio import generer_xlsx_cardstudio
from backend.services.exports_google import (
    generer_csv_google,
    generer_csv_google_avec_mdp,
)
from backend.services.exports_jpm import generer_csv_jpm
from backend.services.exports_koxo import generer_csv_koxo
from backend.services.exports_pmb import generer_csv_pmb

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


# ---------------------------------------------------------------------------
# Lot 8b — Boucle retour KoXo → Google (MDP en mémoire uniquement)
# ---------------------------------------------------------------------------


class ExportGoogleAvecMdpPayload(BaseModel):
    """Le CSV KoXo enrichi (avec MDP) est envoyé en base64 dans le corps JSON.

    Les MDP transitent en mémoire côté serveur uniquement — jamais persistés."""

    csv_koxo_base64: str
    site_id: int
    type_personne: Literal["eleve", "adulte"]
    categorie: Literal["tous", "nouveaux", "anciens"]
    annee_cible_id: int
    annee_source_id: int | None = None


class ExportGoogleAvecMdpReponse(BaseModel):
    site_nom: str
    type_personne: str
    categorie: str
    nb_lignes: int
    nb_lignes_avec_mdp: int
    nb_sans_ou: int
    nb_mdp_orphelins: int
    nom_fichier: str
    contenu_base64: str


@router.post("/google-avec-mdp", response_model=ExportGoogleAvecMdpReponse)
def exporter_google_avec_mdp(
    payload: ExportGoogleAvecMdpPayload, session: Session = Depends(db_session)
) -> ExportGoogleAvecMdpReponse:
    """Enrichit un CSV Google avec les MDP extraits d'un CSV KoXo."""
    try:
        contenu_koxo = base64.b64decode(payload.csv_koxo_base64)
    except Exception as e:
        raise HTTPException(400, f"Base64 CSV KoXo invalide : {e}") from e
    if not contenu_koxo:
        raise HTTPException(400, "CSV KoXo vide")

    try:
        contenu, rapport = generer_csv_google_avec_mdp(
            session=session,
            csv_koxo_bytes=contenu_koxo,
            site_id=payload.site_id,
            type_personne=payload.type_personne,
            categorie=payload.categorie,
            annee_cible_id=payload.annee_cible_id,
            annee_source_id=payload.annee_source_id,
        )
    except ValueError as e:
        raise HTTPException(400, str(e))

    return ExportGoogleAvecMdpReponse(
        site_nom=rapport.site_nom,
        type_personne=rapport.type_personne,
        categorie=rapport.categorie,
        nb_lignes=rapport.nb_lignes,
        nb_lignes_avec_mdp=rapport.nb_lignes_avec_mdp,
        nb_sans_ou=rapport.nb_sans_ou,
        nb_mdp_orphelins=rapport.nb_mdp_orphelins,
        nom_fichier=rapport.nom_fichier_suggere,
        contenu_base64=base64.b64encode(contenu).decode("ascii"),
    )


# ---------------------------------------------------------------------------
# Lot 11a — PMB
# ---------------------------------------------------------------------------


class ExportPmbPayload(BaseModel):
    site_id: int
    type_personne: Literal["eleve", "adulte"]
    categorie: Literal["tous", "nouveaux", "anciens"]
    annee_cible_id: int
    annee_source_id: int | None = None


class ExportPmbReponse(BaseModel):
    site_nom: str
    type_personne: str
    categorie: str
    nb_lignes: int
    nom_fichier: str
    contenu_base64: str


@router.post("/pmb", response_model=ExportPmbReponse)
def exporter_pmb(payload: ExportPmbPayload, session: Session = Depends(db_session)) -> ExportPmbReponse:
    try:
        contenu, rapport = generer_csv_pmb(
            session=session, site_id=payload.site_id, type_personne=payload.type_personne,
            categorie=payload.categorie, annee_cible_id=payload.annee_cible_id,
            annee_source_id=payload.annee_source_id,
        )
    except ValueError as e:
        raise HTTPException(400, str(e))
    return ExportPmbReponse(
        site_nom=rapport.site_nom, type_personne=rapport.type_personne,
        categorie=rapport.categorie, nb_lignes=rapport.nb_lignes,
        nom_fichier=rapport.nom_fichier_suggere,
        contenu_base64=base64.b64encode(contenu).decode("ascii"),
    )


# ---------------------------------------------------------------------------
# Lot 11b — JPM / SmartAir (différentiel a/b/m)
# ---------------------------------------------------------------------------


class ExportJpmPayload(BaseModel):
    site_id: int
    annee_cible_id: int
    annee_source_id: int


class ExportJpmReponse(BaseModel):
    site_nom: str
    nb_ajouts: int
    nb_suppressions: int
    nb_modifications: int
    nb_total: int
    nom_fichier: str
    contenu_base64: str


@router.post("/jpm", response_model=ExportJpmReponse)
def exporter_jpm(payload: ExportJpmPayload, session: Session = Depends(db_session)) -> ExportJpmReponse:
    try:
        contenu, rapport = generer_csv_jpm(
            session=session, site_id=payload.site_id,
            annee_cible_id=payload.annee_cible_id,
            annee_source_id=payload.annee_source_id,
        )
    except ValueError as e:
        raise HTTPException(400, str(e))
    return ExportJpmReponse(
        site_nom=rapport.site_nom,
        nb_ajouts=rapport.nb_ajouts, nb_suppressions=rapport.nb_suppressions,
        nb_modifications=rapport.nb_modifications, nb_total=rapport.nb_total,
        nom_fichier=rapport.nom_fichier_suggere,
        contenu_base64=base64.b64encode(contenu).decode("ascii"),
    )


# ---------------------------------------------------------------------------
# Lot 11c — CardStudio (XLSX badges)
# ---------------------------------------------------------------------------


class ExportCardStudioPayload(BaseModel):
    site_id: int
    categorie: Literal["tous", "nouveaux"]
    annee_cible_id: int
    annee_source_id: int | None = None


class ExportCardStudioReponse(BaseModel):
    site_nom: str
    nb_lignes: int
    nom_fichier: str
    contenu_base64: str


@router.post("/cardstudio", response_model=ExportCardStudioReponse)
def exporter_cardstudio(payload: ExportCardStudioPayload, session: Session = Depends(db_session)) -> ExportCardStudioReponse:
    try:
        contenu, rapport = generer_xlsx_cardstudio(
            session=session, site_id=payload.site_id,
            categorie=payload.categorie, annee_cible_id=payload.annee_cible_id,
            annee_source_id=payload.annee_source_id,
        )
    except ValueError as e:
        raise HTTPException(400, str(e))
    return ExportCardStudioReponse(
        site_nom=rapport.site_nom, nb_lignes=rapport.nb_lignes,
        nom_fichier=rapport.nom_fichier_suggere,
        contenu_base64=base64.b64encode(contenu).decode("ascii"),
    )
