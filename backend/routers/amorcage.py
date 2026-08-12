"""Endpoints d'amorçage — chargement des Personnes depuis KoXo (Lot 9).

Voie unique : `POST /api/amorcage/koxo` avec le fichier en base64.
Le multipart est délibérément évité (bug WebView2 observé au Lot 6).

Le mot de passe éventuellement présent dans le fichier N'EST JAMAIS
persisté — le rapport le signale simplement pour information.
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
from backend.services.amorcage import RapportAmorcage, amorcer_depuis_koxo

router = APIRouter(prefix="/api/amorcage", tags=["amorcage"])


class AmorcageKoxoPayload(BaseModel):
    fichier_base64: str
    nom_fichier: str
    site_id: int
    type_personne: str  # "eleve" | "adulte"
    mode: str = "simulation"


class RapportOut(BaseModel):
    type_personne: str
    site: str
    mode: str
    nb_lignes_lues: int
    nb_creations: int
    nb_deja_presentes: int
    nb_conflits_login: int
    nb_rejets: int
    personnes: list[dict]
    rejets: list[dict]
    conflits: list[dict]
    contient_mots_de_passe: bool
    erreurs: list[str]
    est_bloque: bool


def _to_out(r: RapportAmorcage) -> RapportOut:
    return RapportOut(
        type_personne=r.type_personne,
        site=r.site,
        mode=r.mode,
        nb_lignes_lues=r.nb_lignes_lues,
        nb_creations=r.nb_creations,
        nb_deja_presentes=r.nb_deja_presentes,
        nb_conflits_login=r.nb_conflits_login,
        nb_rejets=r.nb_rejets,
        personnes=[asdict(p) for p in r.personnes],
        rejets=[asdict(lr) for lr in r.rejets],
        conflits=r.conflits,
        contient_mots_de_passe=r.contient_mots_de_passe,
        erreurs=r.erreurs,
        est_bloque=r.est_bloque,
    )


@router.post("/koxo", response_model=RapportOut)
def amorcer_koxo(
    payload: AmorcageKoxoPayload, session: Session = Depends(db_session)
) -> RapportOut:
    """Amorce le référentiel depuis un export KoXo (CSV en base64)."""
    if payload.type_personne not in ("eleve", "adulte"):
        raise HTTPException(400, f"type_personne invalide : {payload.type_personne!r}")
    if payload.mode not in ("simulation", "reel"):
        raise HTTPException(400, f"mode invalide : {payload.mode!r}")

    try:
        contenu = base64.b64decode(payload.fichier_base64)
    except Exception as e:
        raise HTTPException(400, f"Base64 invalide : {e}") from e
    if not contenu:
        raise HTTPException(400, "Fichier vide")

    suffix = Path(payload.nom_fichier or "koxo.csv").suffix or ".csv"
    with NamedTemporaryFile(suffix=suffix, delete=False) as tmp:
        tmp.write(contenu)
        chemin_tmp = Path(tmp.name)

    try:
        rapport = amorcer_depuis_koxo(
            session=session,
            chemin_fichier=chemin_tmp,
            site_id=payload.site_id,
            type_personne=payload.type_personne,
            mode=payload.mode,
        )
    except ValueError as e:
        raise HTTPException(404, str(e))
    finally:
        try:
            chemin_tmp.unlink()
        except OSError:
            pass

    try:
        from backend.services.journal import journaliser

        journaliser(
            session,
            type_operation="amorcage",
            cible=payload.type_personne,
            mode=payload.mode,
            parametres={"site": rapport.site, "fichier": payload.nom_fichier},
            resultat={
                "nb_lignes_lues": rapport.nb_lignes_lues,
                "nb_creations": rapport.nb_creations,
                "nb_deja_presentes": rapport.nb_deja_presentes,
                "nb_conflits_login": rapport.nb_conflits_login,
                "nb_rejets": rapport.nb_rejets,
            },
        )
        session.commit()
    except Exception:  # pragma: no cover — le journal ne doit rien casser
        session.rollback()

    return _to_out(rapport)
