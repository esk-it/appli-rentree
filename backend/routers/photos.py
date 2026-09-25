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
import threading
import time
from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import FileResponse
from pydantic import BaseModel
from sqlalchemy.orm import Session

from backend.database import db_session
from backend.models import AnneeScolaire, Parametre, Personne, Snapshot

router = APIRouter(prefix="/api/photos", tags=["photos"])


def _dossier_pour(session: Session, personne: Personne) -> str | None:
    """Le dossier où chercher la photo de cette personne.

    La règle vit dans `inventaire_photos.dossier_de` : celui de son site
    s'il en a un, sinon le dossier commun de sa population. Les avatars,
    l'inventaire et les cartes la lisent au même endroit — sans quoi le
    trombinoscope montrerait un visage que l'inventaire dit absent.

    Pas de repli d'une population sur l'autre : le dossier des élèves ne
    contient pas les adultes, et y chercher ne ferait que des 404 plus
    lents.
    """
    from backend.services.inventaire_photos import dossier_de

    return dossier_de(session, personne)


def _lire_parametre(session: Session, cle: str) -> str | None:
    p = session.query(Parametre).filter_by(cle=cle).one_or_none()
    if p is None:
        return None
    try:
        return json.loads(p.valeur_json) or None
    except (json.JSONDecodeError, TypeError):
        return None


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
    pistes: list[str]


class InventaireOut(BaseModel):
    dossier: str
    dossiers_injoignables: dict[str, int] = {}
    type_personne: str
    nb_eleves: int
    nb_avec: int
    nb_sans: int
    nb_a_verifier: int
    taux: float
    par_classe: dict[str, dict[str, int]]
    classes_incompletes: list[str]
    manquantes: list[EleveSansPhotoOut]


@router.get("/inventaire", response_model=InventaireOut)
def inventaire(
    annee_id: int,
    type_personne: str = "eleve",
    session: Session = Depends(db_session),
) -> InventaireOut:
    """Le relevé complet du partage. Lecture seule.

    Un listage par dossier, puis tout se compare en mémoire : quelques
    millièmes sur le partage réel depuis la v0.186 (huit secondes avant,
    quand chaque fichier se vérifiait par un aller-retour réseau). L'accueil
    ne le lance pas pour autant de lui-même : un partage injoignable, lui,
    reste lent à le dire.
    """
    from backend.services.inventaire_photos import InventaireImpossible, relever

    try:
        r = relever(session, annee_id=annee_id, type_personne=type_personne)
    except InventaireImpossible as e:
        raise HTTPException(400, str(e)) from None

    return InventaireOut(
        dossier=r.dossier,
        dossiers_injoignables=r.dossiers_injoignables,
        type_personne=r.type_personne,
        nb_eleves=r.nb_eleves,
        nb_avec=r.nb_avec,
        nb_sans=r.nb_sans,
        nb_a_verifier=r.nb_a_verifier,
        taux=r.taux,
        par_classe=r.par_classe,
        classes_incompletes=r.classes_incompletes,
        manquantes=[EleveSansPhotoOut(**vars(e)) for e in r.manquantes],
    )


@router.get("/inventaire/classeur")
def classeur_manquantes(
    annee_id: int,
    type_personne: str = "eleve",
    session: Session = Depends(db_session),
):
    """La liste des manquantes, triée par classe — celle qu'on distribue."""
    from fastapi.responses import Response

    from backend.services.inventaire_photos import (
        InventaireImpossible,
        classeur,
        relever,
    )

    try:
        r = relever(session, annee_id=annee_id, type_personne=type_personne)
    except InventaireImpossible as e:
        raise HTTPException(400, str(e)) from None

    return Response(
        content=classeur(r),
        media_type=(
            "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
        ),
        headers={
            "content-disposition": (
                f'attachment; filename="Photos_manquantes_{type_personne}s.xlsx"'
            )
        },
    )


CACHE_PHOTO = {"Cache-Control": "private, max-age=3600"}
"""Une heure. Chaque vignette du Référentiel relisait sa photo sur le partage
réseau à chaque passage — quinze lectures SMB pour afficher une liste qu'on
venait de quitter. Une photo change rarement ; une heure de retard sur une
photo retouchée ne gêne personne."""

CACHE_ABSENCE = {"Cache-Control": "private, max-age=600"}
"""Dix minutes pour une photo absente : sinon chaque défilement redemande au
partage les mêmes centaines de photos qu'il n'a pas."""


DUREE_ATTRIBUTIONS = 120.0
"""Deux minutes. Un relevé du partage coûte un dixième de seconde ; une page
du Référentiel demande quarante vignettes."""

_attributions: dict[str, tuple[tuple, float, dict[int, str]]] = {}
"""Par population : (ce qui a servi au relevé, quand, le relevé)."""
_verrou_attributions = threading.Lock()


def _photo_attribuee(session: Session, personne: Personne) -> Path | None:
    """Le fichier que l'inventaire attribue à cette personne cette année.

    Les vignettes cherchaient `NOM Prénom.jpg` à l'orthographe près. Une
    photo nommée avant qu'un accent soit corrigé dans Charlemagne
    (`ROUÉ Léa.jpg` pour ROUE Léa), ou marquée de sa classe (`SAOUT Marie
    (44).jpg`), restait sans visage dans le Référentiel alors que
    l'inventaire et les cartes la trouvaient. Elles lisent donc la même
    attribution — celle qui refuse aussi un fichier que deux personnes se
    disputent.

    Le relevé est gardé deux minutes, sous verrou : quarante vignettes qui
    arrivent ensemble n'en déclenchent qu'un. Il est refait aussitôt si un
    dossier change — régler celui de NDE doit montrer ses photos tout de
    suite, pas dans deux minutes.
    """
    from backend.models import Site
    from backend.services.inventaire_photos import (
        InventaireImpossible,
        chemins_attribues,
        dossier_photos,
    )

    annee = session.query(AnneeScolaire).order_by(AnneeScolaire.libelle.desc()).first()
    if annee is None:
        return None
    cle = (
        annee.id,
        dossier_photos(session, type_personne=personne.type),
        tuple(sorted(
            (s.id, s.dossier_photos_eleves or "", s.dossier_photos_adultes or "")
            for s in session.query(Site)
        )),
    )
    with _verrou_attributions:
        garde = _attributions.get(personne.type)
        if (
            garde is None
            or garde[0] != cle
            or time.monotonic() - garde[1] > DUREE_ATTRIBUTIONS
        ):
            try:
                attribues = chemins_attribues(
                    session, annee_id=annee.id, type_personne=personne.type
                )
            except InventaireImpossible:
                attribues = {}
            garde = _attributions[personne.type] = (cle, time.monotonic(), attribues)
    chemin = garde[2].get(personne.id)
    return Path(chemin) if chemin else None


@router.get("/{personne_id}")
def obtenir_photo(personne_id: int, session: Session = Depends(db_session)):
    """Renvoie l'image de la personne. 404 si absente ou dossier non configuré."""
    personne = session.query(Personne).filter_by(id=personne_id).one_or_none()
    if personne is None:
        raise HTTPException(404, "Personne introuvable", headers=CACHE_ABSENCE)

    # Ce que l'inventaire a trouvé d'abord : c'est la même photo que celle
    # des cartes et du trombinoscope. Les chemins mémorisés ne servent
    # qu'aux personnes hors de l'année — un ancien élève qu'on consulte.
    attribuee = _photo_attribuee(session, personne)
    if attribuee is not None and attribuee.is_file():
        return FileResponse(attribuee, headers=CACHE_PHOTO)

    dossier = _dossier_pour(session, personne)
    if not dossier:
        raise HTTPException(
            404,
            "Aucun dossier de photos réglé pour "
            + ("les adultes" if personne.type == "adulte" else "les élèves"),
            headers=CACHE_ABSENCE,
        )

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
        raise HTTPException(
            404, f"Photo introuvable : {nom_fichier}", headers=CACHE_ABSENCE
        )

    # FileResponse gère le mime type automatiquement
    return FileResponse(chemin_complet, headers=CACHE_PHOTO)
