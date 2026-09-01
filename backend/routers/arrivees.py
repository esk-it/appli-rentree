"""Faire entrer quelqu'un en cours d'année.

Quatre gestes, séparés parce qu'entre le deuxième et le troisième il y a
un geste humain — l'import du CSV dans la console Google.

    proposer   → ce que deviendrait cette personne, sans rien écrire
    enregistrer→ elle entre au référentiel
    compte     → le CSV d'une ligne, mot de passe au coffre
    groupe     → une fois le compte créé, il rejoint sa classe

Le versement au coffre impose que celui-ci soit ouvert : la clé vit dans
le routeur du coffre, jamais ici.
"""
from __future__ import annotations

import base64
from dataclasses import asdict

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session

from backend.database import db_session
from backend.models import Personne
from backend.services.arrivees import (
    ArriveeImpossible,
    ajouter_au_groupe,
    enregistrer_arrivee,
    fabriquer_compte_google,
    inscrire_au_tableau_chromebooks,
    proposer_arrivee,
)

router = APIRouter(prefix="/api/arrivees", tags=["arrivees"])


class ProposerPayload(BaseModel):
    site_id: int
    type_personne: str
    nom: str
    prenom: str
    annee_id: int
    classe: str | None = None
    id_charlemagne: int | None = None


class PropositionOut(BaseModel):
    nom: str
    prenom: str
    site_nom: str
    type_personne: str
    classe: str | None
    login_propose: str
    email_propose: str
    badge: int | None
    ou_pre_rentree: str | None
    ou_definitive: str | None
    groupe_google: str | None
    personne_existante_id: int | None
    avertissements: list[str]


@router.post("/proposer", response_model=PropositionOut)
def proposer(
    payload: ProposerPayload, session: Session = Depends(db_session)
) -> PropositionOut:
    """Ce que deviendrait cette personne. N'écrit rien."""
    try:
        p = proposer_arrivee(
            session,
            site_id=payload.site_id,
            type_personne=payload.type_personne,
            nom=payload.nom,
            prenom=payload.prenom,
            annee_id=payload.annee_id,
            classe=payload.classe,
            id_charlemagne=payload.id_charlemagne,
        )
    except ArriveeImpossible as e:
        raise HTTPException(400, str(e)) from None
    return PropositionOut(**asdict(p))


class EnregistrerPayload(ProposerPayload):
    mode: str = "simulation"


class EnregistrementOut(BaseModel):
    personne_id: int
    login: str
    email: str | None
    badge: int | None
    mode: str


@router.post("/enregistrer", response_model=EnregistrementOut)
def enregistrer(
    payload: EnregistrerPayload, session: Session = Depends(db_session)
) -> EnregistrementOut:
    """Fait entrer la personne au référentiel. Rien dans Google encore."""
    if payload.mode not in ("simulation", "reel"):
        raise HTTPException(400, f"mode invalide : {payload.mode!r}")
    try:
        prop = proposer_arrivee(
            session,
            site_id=payload.site_id,
            type_personne=payload.type_personne,
            nom=payload.nom,
            prenom=payload.prenom,
            annee_id=payload.annee_id,
            classe=payload.classe,
            id_charlemagne=payload.id_charlemagne,
        )
        personne = enregistrer_arrivee(
            session, prop,
            site_id=payload.site_id,
            annee_id=payload.annee_id,
            id_charlemagne=payload.id_charlemagne,
            mode=payload.mode,
        )
    except ArriveeImpossible as e:
        raise HTTPException(400, str(e)) from None
    return EnregistrementOut(
        personne_id=personne.id, login=personne.login or "",
        email=personne.email, badge=personne.badge, mode=payload.mode,
    )


class ComptePayload(BaseModel):
    personne_id: int
    ou: str
    """L'unité d'organisation où la console rangera le compte à sa
    création — celle de pré-rentrée ou celle de la classe, au choix."""
    mode: str = "simulation"


class CompteOut(BaseModel):
    email: str
    ou_visee: str
    nom_fichier: str
    avertissements: list[str]
    csv_base64: str


@router.post("/compte-google", response_model=CompteOut)
def compte_google(
    payload: ComptePayload, session: Session = Depends(db_session)
) -> CompteOut:
    """Le CSV d'une ligne à importer dans la console, mot de passe compris.

    Le coffre doit être ouvert : générer un mot de passe et le ranger sont
    le même geste.
    """
    from backend.routers.coffre import _cle_courante

    cle = _cle_courante()
    personne = session.query(Personne).filter_by(id=payload.personne_id).one_or_none()
    if personne is None:
        raise HTTPException(404, f"Personne introuvable : {payload.personne_id}")
    try:
        contenu, rapport = fabriquer_compte_google(
            session, cle, personne, ou=payload.ou, mode=payload.mode,
        )
    except ArriveeImpossible as e:
        raise HTTPException(409, str(e)) from None
    except ValueError as e:
        raise HTTPException(400, str(e)) from None
    return CompteOut(
        email=rapport.email, ou_visee=rapport.ou_visee,
        nom_fichier=rapport.nom_fichier,
        avertissements=rapport.avertissements,
        csv_base64=base64.b64encode(contenu).decode(),
    )


class GroupePayload(BaseModel):
    personne_id: int
    groupe: str


class GroupeOut(BaseModel):
    message: str


@router.post("/groupe", response_model=GroupeOut)
def rejoindre_groupe(
    payload: GroupePayload, session: Session = Depends(db_session)
) -> GroupeOut:
    """Fait entrer l'arrivant dans le groupe de sa classe.

    À faire **après** l'import du CSV : ajouter un membre qui n'existe pas
    encore échoue.
    """
    from backend.services.google_api import ClientGoogle, charger_config

    personne = session.query(Personne).filter_by(id=payload.personne_id).one_or_none()
    if personne is None:
        raise HTTPException(404, f"Personne introuvable : {payload.personne_id}")
    try:
        client = ClientGoogle(charger_config(session))
    except ValueError as e:
        raise HTTPException(400, str(e)) from None
    try:
        message = ajouter_au_groupe(session, personne, client, payload.groupe)
    except ArriveeImpossible as e:
        raise HTTPException(400, str(e)) from None
    except Exception as e:
        raise HTTPException(502, f"Google a refusé : {type(e).__name__}: {e}")
    return GroupeOut(message=message)


class ChromebookPayload(BaseModel):
    personne_id: int
    annee_id: int
    discipline: str | None = None
    mode: str = "reel"


@router.post("/tableau-chromebooks", response_model=GroupeOut)
def tableau_chromebooks(
    payload: ChromebookPayload, session: Session = Depends(db_session)
) -> GroupeOut:
    """Fait apparaître un adulte dans l'écran Chromebooks.

    Cet écran lit le tableau des enseignants, importé une fois l'an : une
    AESH qui prend son poste en novembre n'y figure pas, et c'est
    précisément le moment où elle a besoin d'une machine.
    """
    personne = session.query(Personne).filter_by(id=payload.personne_id).one_or_none()
    if personne is None:
        raise HTTPException(404, f"Personne introuvable : {payload.personne_id}")
    try:
        message = inscrire_au_tableau_chromebooks(
            session, personne, annee_id=payload.annee_id,
            discipline=payload.discipline, mode=payload.mode,
        )
    except ArriveeImpossible as e:
        raise HTTPException(400, str(e)) from None
    return GroupeOut(message=message)
