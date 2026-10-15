"""La rentrée guidée : l'état de la campagne, et les gestes sur ses étapes.

Toute la logique est dans `services/rentree.py`. Ici, ce que l'écran
demande, et l'accès à Google quand une étape s'y constate — toujours sur
demande, jamais à la navigation.

Une campagne se désigne par le libellé de sa rentrée, « 2027-2028 » :
l'année elle-même n'existe qu'une fois l'export ingéré.
"""
from __future__ import annotations

from dataclasses import asdict
from datetime import date

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session

from backend.database import db_session

router = APIRouter(prefix="/api/rentree", tags=["rentree"])


class MesureOut(BaseModel):
    id: str
    libelle: str
    valeur: int | None
    attendu: str
    bloquante: bool
    detail: str
    source: str
    lu_le: str
    bonne: bool | None


class EtapeOut(BaseModel):
    id: str
    chapitre: str
    titre: str
    rang: int
    statut: str
    validee_le: str | None = None
    note: str | None = None
    reportable: bool = False
    pas_avant: str | None = None
    gestes: list[str] = []
    gestes_le: dict = {}
    avant: dict = {}
    apres: dict = {}


class EtatOut(BaseModel):
    annee: str
    annee_id: int | None
    chapitres: list[dict]
    etapes: list[EtapeOut]
    courante: str | None
    nb_validees: int
    commencee: bool
    """Au moins une étape a été ouverte."""
    s_ouvre_le: str
    """Le jour où la campagne peut commencer (ISO)."""
    trop_tot: bool
    repetition: bool = False
    """Sur une copie de la base : la campagne se commence sans attendre juillet."""


def _mesure_out(m) -> MesureOut:
    return MesureOut(**asdict(m), bonne=m.bonne)


def _etat_out(session: Session, libelle: str | None) -> EtatOut:
    from backend.services.repetition import est_active
    from backend.services.rentree import RentreeImpossible, etat, s_ouvre_le

    try:
        e = etat(session, annee=libelle)
        ouverture = s_ouvre_le(e.annee)
    except RentreeImpossible as ex:
        raise HTTPException(400, str(ex)) from None
    return EtatOut(
        annee=e.annee, annee_id=e.annee_id, chapitres=e.chapitres,
        etapes=[EtapeOut(**asdict(x)) for x in e.etapes], courante=e.courante,
        nb_validees=e.nb_validees,
        commencee=any(x.statut != "a_faire" and x.statut != "fermee" for x in e.etapes),
        s_ouvre_le=ouverture.isoformat(),
        trop_tot=date.today() < ouverture and not est_active(),
        repetition=est_active(),
    )


@router.get("/etat", response_model=EtatOut)
def lire_etat(annee: str | None = None, session: Session = Depends(db_session)):
    """Où en est la campagne — par défaut celle qui se prépare. Lecture locale."""
    return _etat_out(session, annee)


class CommencerPayload(BaseModel):
    libelle: str


@router.post("/commencer", response_model=EtatOut)
def commencer_rentree(payload: CommencerPayload, session: Session = Depends(db_session)):
    """Ouvre la campagne. Ne crée pas l'année : l'ingestion s'en charge.

    En répétition, sur une copie de la base, elle s'ouvre sans attendre
    juillet : c'est tout l'intérêt de répéter.
    """
    from backend.services.repetition import est_active
    from backend.services.rentree import RentreeImpossible, commencer, s_ouvre_le

    try:
        jour = s_ouvre_le(payload.libelle) if est_active() else None
        libelle = commencer(session, payload.libelle, aujourd_hui=jour)
    except RentreeImpossible as e:
        raise HTTPException(400, str(e)) from None
    return _etat_out(session, libelle)


class GestePayload(BaseModel):
    annee: str
    google: bool = False
    """Relire Google pour les mesures qui s'y constatent."""


def _contexte(session: Session, annee: str, etape_id: str, google: bool):
    from backend.routers.coffre import cle_si_ouverte
    from backend.services.google_api import ClientGoogle, charger_config
    from backend.services.rentree import MESURES_GOOGLE, PAR_ID, contexte

    if etape_id not in PAR_ID:
        raise HTTPException(404, f"Étape inconnue : {etape_id}")
    ctx = contexte(session, annee, cle_coffre=cle_si_ouverte())
    besoin = MESURES_GOOGLE & set(PAR_ID[etape_id].mesures)
    if google and besoin and ctx.annee is not None:
        try:
            client = ClientGoogle(charger_config(session))
        except ValueError as e:
            raise HTTPException(400, str(e)) from None
        try:
            ctx.comptes_google = client.lister_utilisateurs()
            if "unites_manquantes" in besoin:
                ctx.ou_google = client.lister_ou()
        except Exception as e:
            raise HTTPException(502, f"Lecture Google impossible : {type(e).__name__}: {e}")
    return ctx


class OuvertureOut(BaseModel):
    etape: EtapeOut
    mesures: list[MesureOut]


@router.post("/etapes/{etape_id}/ouvrir", response_model=OuvertureOut)
def ouvrir_etape(etape_id: str, payload: GestePayload, session: Session = Depends(db_session)):
    """Ouvre l'étape et rend ses mesures du moment. Google seulement si demandé."""
    from backend.services.rentree import RentreeImpossible, ouvrir

    ctx = _contexte(session, payload.annee, etape_id, payload.google)
    try:
        mesures = ouvrir(session, ctx, etape_id)
    except RentreeImpossible as e:
        raise HTTPException(409, str(e)) from None
    etat = _etat_out(session, payload.annee)
    return OuvertureOut(
        etape=next(x for x in etat.etapes if x.id == etape_id),
        mesures=[_mesure_out(m) for m in mesures],
    )


class DeclarationPayload(BaseModel):
    annee: str
    geste: str
    fait: bool = True


@router.post("/etapes/{etape_id}/gestes", response_model=list[str])
def declarer(etape_id: str, payload: DeclarationPayload, session: Session = Depends(db_session)):
    """Un geste fait hors du programme — « c'est importé dans KoXo NDK »."""
    from backend.services.rentree import RentreeImpossible, declarer_geste

    try:
        return declarer_geste(session, payload.annee, etape_id, payload.geste, fait=payload.fait)
    except RentreeImpossible as e:
        raise HTTPException(409, str(e)) from None


class ValidationPayload(BaseModel):
    annee: str
    forcer: bool = False
    note: str | None = None
    google: bool = True
    """Une étape qui se constate dans Google se valide sur une lecture fraîche."""


@router.post("/etapes/{etape_id}/valider", response_model=EtatOut)
def valider_etape(etape_id: str, payload: ValidationPayload, session: Session = Depends(db_session)):
    """Valide l'étape sur ce qui est constaté maintenant ; refuse et dit pourquoi."""
    from backend.services.rentree import RentreeImpossible, valider

    ctx = _contexte(session, payload.annee, etape_id, payload.google)
    try:
        valider(session, ctx, etape_id, forcer=payload.forcer, note=payload.note)
    except RentreeImpossible as e:
        raise HTTPException(409, str(e)) from None
    return _etat_out(session, payload.annee)


class NotePayload(BaseModel):
    annee: str
    note: str | None = None


@router.post("/etapes/{etape_id}/reporter", response_model=EtatOut)
def reporter_etape(etape_id: str, payload: NotePayload, session: Session = Depends(db_session)):
    from backend.services.rentree import RentreeImpossible, reporter

    try:
        reporter(session, payload.annee, etape_id, note=payload.note)
    except RentreeImpossible as e:
        raise HTTPException(409, str(e)) from None
    return _etat_out(session, payload.annee)


@router.post("/etapes/{etape_id}/rouvrir", response_model=EtatOut)
def rouvrir_etape(etape_id: str, payload: NotePayload, session: Session = Depends(db_session)):
    from backend.services.rentree import RentreeImpossible, rouvrir

    try:
        rouvrir(session, payload.annee, etape_id)
    except RentreeImpossible as e:
        raise HTTPException(409, str(e)) from None
    return _etat_out(session, payload.annee)
