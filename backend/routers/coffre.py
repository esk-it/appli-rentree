"""Le coffre à mots de passe — ouverture, recherche, versement.

## La clé ne traverse jamais le réseau

Le mot de passe maître est envoyé une fois, à l'ouverture. La clé qui en
dérive reste **dans le processus**, dans une variable de module, et n'est
jamais rendue à l'interface : celle-ci ne sait que si le coffre est ouvert
ou fermé.

C'est tenable parce que le sidecar est local, mono-utilisateur, et lié à la
fenêtre qui l'a lancé. Une application multi-utilisateurs demanderait autre
chose.

## Le verrouillage automatique

Un coffre ouvert et oublié est un coffre ouvert. Toute inactivité de quinze
minutes le referme ; chaque usage repousse l'échéance. Fermer la fenêtre le
referme aussi, la clé n'étant qu'en mémoire.
"""
from __future__ import annotations

import base64
import time
from dataclasses import asdict

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session

from backend.database import db_session
from backend.services.coffre import (
    CoffreDejaInitialise,
    CoffreVerrouille,
    chercher,
    est_initialise,
    initialiser,
    ouvrir,
    verser_export_koxo,
)

router = APIRouter(prefix="/api/coffre", tags=["coffre"])

DUREE_OUVERTURE = 15 * 60
"""Secondes d'inactivité avant refermeture. Un coffre oublié ouvert n'en
est plus un."""

_CLE: bytes | None = None
_EXPIRE_A: float = 0.0


def _cle_courante() -> bytes:
    """La clé si le coffre est ouvert, et repousse l'échéance."""
    global _CLE, _EXPIRE_A
    if _CLE is None or time.monotonic() > _EXPIRE_A:
        _CLE = None
        raise HTTPException(
            401,
            "Le coffre est fermé. Saisis le mot de passe maître pour "
            "l'ouvrir.",
        )
    _EXPIRE_A = time.monotonic() + DUREE_OUVERTURE
    return _CLE


def _ouvrir_en_memoire(cle: bytes) -> None:
    global _CLE, _EXPIRE_A
    _CLE = cle
    _EXPIRE_A = time.monotonic() + DUREE_OUVERTURE


def verrouiller_maintenant() -> None:
    """Referme le coffre. Appelable depuis les tests et l'arrêt du backend."""
    global _CLE, _EXPIRE_A
    _CLE = None
    _EXPIRE_A = 0.0


class MotDePassePayload(BaseModel):
    mot_de_passe: str


class EtatOut(BaseModel):
    initialise: bool
    ouvert: bool
    expire_dans: int = 0
    """Secondes restantes avant refermeture automatique."""
    nb_secrets: int = 0


@router.get("/etat", response_model=EtatOut)
def etat(session: Session = Depends(db_session)) -> EtatOut:
    """Ce que l'interface a le droit de savoir : ouvert ou fermé."""
    from backend.models import SecretConserve

    ouvert = _CLE is not None and time.monotonic() <= _EXPIRE_A
    return EtatOut(
        initialise=est_initialise(session),
        ouvert=ouvert,
        expire_dans=max(0, int(_EXPIRE_A - time.monotonic())) if ouvert else 0,
        nb_secrets=session.query(SecretConserve).count(),
    )


@router.post("/initialiser", response_model=EtatOut)
def initialiser_coffre(
    payload: MotDePassePayload, session: Session = Depends(db_session)
) -> EtatOut:
    """Crée le mot de passe maître. Une seule fois, sans reprise possible."""
    try:
        cle = initialiser(session, payload.mot_de_passe)
    except CoffreDejaInitialise as e:
        raise HTTPException(409, str(e)) from None
    except CoffreVerrouille as e:
        raise HTTPException(400, str(e)) from None
    session.commit()
    _ouvrir_en_memoire(cle)
    return etat(session)


@router.post("/ouvrir", response_model=EtatOut)
def ouvrir_coffre(
    payload: MotDePassePayload, session: Session = Depends(db_session)
) -> EtatOut:
    try:
        cle = ouvrir(session, payload.mot_de_passe)
    except CoffreVerrouille as e:
        raise HTTPException(401, str(e)) from None
    _ouvrir_en_memoire(cle)
    return etat(session)


@router.post("/verrouiller", response_model=EtatOut)
def verrouiller(session: Session = Depends(db_session)) -> EtatOut:
    verrouiller_maintenant()
    return etat(session)


class SecretOut(BaseModel):
    personne_id: int
    nom: str
    prenom: str
    login: str | None
    classe: str | None
    cible: str
    site: str | None
    origine: str
    mot_de_passe: str


@router.get("/chercher", response_model=list[SecretOut])
def chercher_secret(
    q: str, session: Session = Depends(db_session)
) -> list[SecretOut]:
    """Retrouve des mots de passe par nom, prénom ou identifiant.

    Une requête vide ne rend rien : un champ laissé vide ne doit pas
    déballer le coffre entier.
    """
    cle = _cle_courante()
    try:
        return [SecretOut(**asdict(s)) for s in chercher(session, cle, q)]
    except CoffreVerrouille as e:
        raise HTTPException(409, str(e)) from None


class VersementPayload(BaseModel):
    fichier_base64: str
    site: str | None = None


class VersementOut(BaseModel):
    site: str | None
    nb_lignes: int
    nb_deposes: int
    nb_sans_correspondance: int
    nb_sans_mot_de_passe: int
    resume: str


@router.post("/verser", response_model=VersementOut)
def verser(
    payload: VersementPayload, session: Session = Depends(db_session)
) -> VersementOut:
    """Range dans le coffre les mots de passe d'un export KoXo."""
    cle = _cle_courante()
    try:
        contenu = base64.b64decode(payload.fichier_base64)
    except Exception as e:
        raise HTTPException(400, f"Base64 invalide : {e}") from e
    if not contenu:
        raise HTTPException(400, "Fichier vide")

    r = verser_export_koxo(session, cle, contenu, site=payload.site)
    session.commit()
    return VersementOut(**{**asdict(r), "resume": r.resume})
