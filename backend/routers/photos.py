"""Endpoint de lecture des photos élèves (Lot 14a).

Sert une photo depuis le partage réseau `\\\\ESK-APP01\\...` (chemin
configuré dans les Paramètres, clef `chemin_dossier_photos`). Le fichier
est identifié par le nom stocké dans le snapshot le plus récent de
l'élève.

Si le partage est inaccessible ou le fichier manquant → 404, le frontend
tombe alors sur l'avatar initiales.
"""
from __future__ import annotations

import json
from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import FileResponse
from pydantic import BaseModel
from sqlalchemy.orm import Session

from backend.database import db_session
from backend.models import Parametre, Personne, Snapshot

router = APIRouter(prefix="/api/photos", tags=["photos"])


def _lire_chemin_dossier_photos(session: Session) -> str | None:
    p = session.query(Parametre).filter_by(cle="chemin_dossier_photos").one_or_none()
    if p is None:
        return None
    try:
        return json.loads(p.valeur_json)
    except (json.JSONDecodeError, TypeError):
        return None


# ---------------------------------------------------------------------------
# L'inventaire — qui a sa photo, et qui ne l'a pas
# ---------------------------------------------------------------------------


class EleveSansPhotoOut(BaseModel):
    personne_id: int
    nom: str
    prenom: str
    classe: str
    site: str | None
    badge: int | None
    chemin_attendu: str | None


class InventaireOut(BaseModel):
    dossier: str
    nb_eleves: int
    nb_avec: int
    nb_sans: int
    taux: float
    par_classe: dict[str, dict[str, int]]
    classes_incompletes: list[str]
    manquantes: list[EleveSansPhotoOut]


@router.get("/inventaire", response_model=InventaireOut)
def inventaire(annee_id: int, session: Session = Depends(db_session)) -> InventaireOut:
    """Le relevé complet du partage. Lecture seule, et volontairement lente.

    Un accès par élève sur un partage réseau : c'est le sujet de l'écran, on
    l'attend. C'est pour cela que l'accueil ne le lance pas de lui-même.
    """
    from backend.services.inventaire_photos import InventaireImpossible, relever

    try:
        r = relever(session, annee_id=annee_id)
    except InventaireImpossible as e:
        raise HTTPException(400, str(e)) from None

    return InventaireOut(
        dossier=r.dossier,
        nb_eleves=r.nb_eleves,
        nb_avec=r.nb_avec,
        nb_sans=r.nb_sans,
        taux=r.taux,
        par_classe=r.par_classe,
        classes_incompletes=r.classes_incompletes,
        manquantes=[EleveSansPhotoOut(**vars(e)) for e in r.manquantes],
    )


@router.get("/inventaire/classeur")
def classeur_manquantes(annee_id: int, session: Session = Depends(db_session)):
    """La liste des manquantes, triée par classe — celle qu'on distribue."""
    from fastapi.responses import Response

    from backend.services.inventaire_photos import (
        InventaireImpossible,
        classeur,
        relever,
    )

    try:
        r = relever(session, annee_id=annee_id)
    except InventaireImpossible as e:
        raise HTTPException(400, str(e)) from None

    return Response(
        content=classeur(r),
        media_type=(
            "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
        ),
        headers={
            "content-disposition": 'attachment; filename="Photos_manquantes.xlsx"'
        },
    )


@router.get("/{personne_id}")
def obtenir_photo(personne_id: int, session: Session = Depends(db_session)):
    """Renvoie l'image de la personne. 404 si absente ou dossier non configuré."""
    dossier = _lire_chemin_dossier_photos(session)
    if not dossier:
        raise HTTPException(404, "Paramètre `chemin_dossier_photos` non configuré")

    personne = session.query(Personne).filter_by(id=personne_id).one_or_none()
    if personne is None:
        raise HTTPException(404, "Personne introuvable")

    # Utilise chemin_photo_constate en priorité (fixé à l'ingestion),
    # sinon fallback sur le nom du dernier snapshot.
    nom_fichier = personne.chemin_photo_constate
    if not nom_fichier:
        snap = (
            session.query(Snapshot)
            .filter_by(personne_id=personne_id)
            .order_by(Snapshot.date_ingestion.desc())
            .first()
        )
        if snap:
            nom_fichier = snap.chemin_photo

    # Fallback ultime : convention historique "NOM Prénom.jpg"
    if not nom_fichier:
        nom_fichier = f"{personne.nom} {personne.prenom}.jpg"

    chemin_complet = Path(dossier) / nom_fichier
    if not chemin_complet.exists() or not chemin_complet.is_file():
        raise HTTPException(404, f"Photo introuvable : {nom_fichier}")

    # FileResponse gère le mime type automatiquement
    return FileResponse(chemin_complet)
