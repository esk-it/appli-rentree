"""Endpoint du contrôle avant synchronisation KoXo.

Voie base64, comme l'amorçage : le multipart est délibérément évité
(bug WebView2 observé au Lot 6).

Le contrôle **n'écrit rien**. Il n'a pas de mode simulation/réel parce
qu'il n'a pas de mode réel : il lit un export et raconte ce qu'il voit.
"""
from __future__ import annotations

import base64
from dataclasses import asdict
from pathlib import Path
from tempfile import NamedTemporaryFile

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session

from backend.database import db_session
from backend.services.controle_koxo import RapportControle, controler_export_koxo

router = APIRouter(prefix="/api/koxo", tags=["koxo"])


class ControlePayload(BaseModel):
    fichier_base64: str
    nom_fichier: str
    type_personne: str  # "eleve" | "adulte"
    site_id: int | None = None
    annee_id: int | None = None


class ControleOut(BaseModel):
    fichier: str
    type_personne: str
    nb_lignes: int
    nb_concordants: int
    colonnes_lues: list[str]
    separateur: str
    encodage: str
    date_naissance_renseignee: int
    contient_mots_de_passe: bool
    ecarts: list[dict]
    avertissements: list[str]
    nb_par_genre: dict[str, int]
    est_sain: bool


def _to_out(r: RapportControle) -> ControleOut:
    return ControleOut(
        fichier=r.fichier,
        type_personne=r.type_personne,
        nb_lignes=r.nb_lignes,
        nb_concordants=r.nb_concordants,
        colonnes_lues=r.colonnes_lues,
        separateur=r.separateur,
        encodage=r.encodage,
        date_naissance_renseignee=r.date_naissance_renseignee,
        contient_mots_de_passe=r.contient_mots_de_passe,
        ecarts=[asdict(e) for e in r.ecarts],
        avertissements=r.avertissements,
        nb_par_genre=r.nb_par_genre,
        est_sain=r.est_sain,
    )


@router.post("/controle", response_model=ControleOut)
def controler(
    payload: ControlePayload, session: Session = Depends(db_session)
) -> ControleOut:
    """Confronte un export KoXo au référentiel, sans rien modifier."""
    if payload.type_personne not in ("eleve", "adulte"):
        raise HTTPException(400, f"type_personne invalide : {payload.type_personne!r}")

    try:
        contenu = base64.b64decode(payload.fichier_base64)
    except Exception as e:
        raise HTTPException(400, f"Base64 invalide : {e}") from e
    if not contenu:
        raise HTTPException(400, "Fichier vide")

    suffixe = Path(payload.nom_fichier or "koxo.csv").suffix or ".csv"
    with NamedTemporaryFile(suffix=suffixe, delete=False) as tmp:
        tmp.write(contenu)
        chemin = Path(tmp.name)

    try:
        rapport = controler_export_koxo(
            session,
            chemin,
            type_personne=payload.type_personne,
            site_id=payload.site_id,
            annee_id=payload.annee_id,
        )
    except ValueError as e:
        raise HTTPException(400, str(e)) from None
    finally:
        # Le fichier porte des mots de passe en clair : il ne survit pas à
        # la requête, quoi qu'il arrive.
        try:
            chemin.unlink()
        except OSError:
            pass

    # Le nom du fichier déposé remplace celui du temporaire.
    rapport.fichier = payload.nom_fichier or rapport.fichier
    return _to_out(rapport)
