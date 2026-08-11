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
