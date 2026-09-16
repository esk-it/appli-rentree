"""Endpoints du parc : états, pannes, prélèvements, accessoires.

Lecture d'un côté, gestes de l'autre. `GET /atelier` propose un plan de
remontage et n'écrit rien ; c'est `POST /prelever` qui l'applique, une
pièce à la fois — on ne lance pas un atelier entier d'un bouton, parce que
c'est le tournevis qui décide si la pièce entre vraiment.
"""
from __future__ import annotations

from dataclasses import asdict
from datetime import date

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session

from backend.database import db_session
from backend.models.parc_materiel import (
    ETATS_ACCESSOIRE,
    ETATS_MACHINE,
    ORGANES,
    TYPES_ACCESSOIRE,
)
from backend.services.parc_materiel import (
    GesteImpossible,
    analyser_atelier,
    changer_etat,
    declarer_panne,
    enregistrer_accessoire,
    etat_du_parc,
    etat_du_stock,
    preter,
    prelever,
    rendre,
    resoudre_panne,
)

router = APIRouter(prefix="/api/parc", tags=["parc"])


def _geste(action):
    """Traduit un refus métier en 400, avec son message tel quel."""
    try:
        return action()
    except GesteImpossible as e:
        raise HTTPException(400, str(e)) from None


# ---------------------------------------------------------------------------
# Vocabulaire — l'interface ne réinvente pas les listes
# ---------------------------------------------------------------------------


class VocabulaireOut(BaseModel):
    etats_machine: list[str]
    organes: list[str]
    etats_accessoire: list[str]
    types_accessoire: list[str]


@router.get("/vocabulaire", response_model=VocabulaireOut)
def vocabulaire() -> VocabulaireOut:
    """Les listes fermées, servies au front pour qu'il n'en invente pas."""
    return VocabulaireOut(
        etats_machine=list(ETATS_MACHINE),
        organes=list(ORGANES),
        etats_accessoire=list(ETATS_ACCESSOIRE),
        types_accessoire=list(TYPES_ACCESSOIRE),
    )


# ---------------------------------------------------------------------------
# Machines
# ---------------------------------------------------------------------------


class MachineOut(BaseModel):
    serie: str
    etat: str
    etat_depuis: date | None
    attribue_a: str | None
    attribue_le: date | None
    note: str | None
    pannes_ouvertes: list[str]


class ParcOut(BaseModel):
    machines: list[MachineOut]
    en_service: int
    en_stock: int
    hs: int
    reforme: int


@router.get("/machines", response_model=ParcOut)
def lister_machines(session: Session = Depends(db_session)) -> ParcOut:
    machines, synthese = etat_du_parc(session)
    return ParcOut(
        machines=[MachineOut(**asdict(m)) for m in machines],
        **asdict(synthese),
    )


class EtatPayload(BaseModel):
    etat: str
    note: str | None = None


@router.post("/machines/{serie}/etat", response_model=MachineOut)
def poser_etat(
    serie: str, payload: EtatPayload, session: Session = Depends(db_session)
) -> MachineOut:
    _geste(lambda: changer_etat(session, serie, payload.etat, note=payload.note))
    machines, _ = etat_du_parc(session)
    return MachineOut(**asdict(next(m for m in machines if m.serie == serie)))


class PannePayload(BaseModel):
    organe: str
    note: str | None = None
    passer_hs: bool = True
    """À faux, on consigne le défaut sans retirer la machine du service."""


class PanneOut(BaseModel):
    id: int
    serie: str
    organe: str
    constatee_le: date | None
    note: str | None
    resolue_le: date | None
    resolution: str | None
    prelevee_pour: str | None


@router.post("/machines/{serie}/panne", response_model=PanneOut)
def poser_panne(
    serie: str, payload: PannePayload, session: Session = Depends(db_session)
) -> PanneOut:
    p = _geste(
        lambda: declarer_panne(
            session,
            serie,
            payload.organe,
            note=payload.note,
            passer_hs=payload.passer_hs,
        )
    )
    return PanneOut(**{c: getattr(p, c) for c in PanneOut.model_fields})


@router.get("/machines/{serie}/pannes", response_model=list[PanneOut])
def lister_pannes(
    serie: str, session: Session = Depends(db_session)
) -> list[PanneOut]:
    """Toutes les pannes de la machine, ouvertes comme refermées.

    L'historique compte autant que l'état : savoir qu'un écran a déjà été
    remplacé une fois change le regard qu'on porte sur la machine.
    """
    from backend.models import PanneChromebook

    lignes = (
        session.query(PanneChromebook)
        .filter_by(serie=serie)
        .order_by(PanneChromebook.constatee_le.desc(), PanneChromebook.id.desc())
        .all()
    )
    return [PanneOut(**{c: getattr(p, c) for c in PanneOut.model_fields}) for p in lignes]


class ResolutionPayload(BaseModel):
    resolution: str = "reparee"


@router.post("/pannes/{panne_id}/resoudre", response_model=PanneOut)
def fermer_panne(
    panne_id: int, payload: ResolutionPayload, session: Session = Depends(db_session)
) -> PanneOut:
    p = _geste(lambda: resoudre_panne(session, panne_id, payload.resolution))
    return PanneOut(**{c: getattr(p, c) for c in PanneOut.model_fields})


# ---------------------------------------------------------------------------
# L'atelier
# ---------------------------------------------------------------------------


class RemontageOut(BaseModel):
    serie: str
    organes_manquants: list[str]
    donneurs: dict[str, str]


class AtelierOut(BaseModel):
    machines_hs: list[MachineOut]
    remontages: list[RemontageOut]
    organes_disponibles: dict[str, int]
    bloquees: list[tuple[str, list[str]]]
    nb_remontables: int


@router.get("/atelier", response_model=AtelierOut)
def atelier(session: Session = Depends(db_session)) -> AtelierOut:
    """Ce que la réserve de pièces permet de remonter. N'écrit rien."""
    a = analyser_atelier(session)
    return AtelierOut(
        machines_hs=[MachineOut(**asdict(m)) for m in a.machines_hs],
        remontages=[RemontageOut(**asdict(r)) for r in a.remontages],
        organes_disponibles=a.organes_disponibles,
        bloquees=a.bloquees,
        nb_remontables=a.nb_remontables,
    )


class PrelevementPayload(BaseModel):
    depuis: str
    vers: str
    organe: str
    note: str | None = None


@router.post("/prelever")
def poser_prelevement(
    payload: PrelevementPayload, session: Session = Depends(db_session)
) -> dict:
    """Prend un organe sur une machine pour en réparer une autre."""
    resolue, creee = _geste(
        lambda: prelever(
            session,
            depuis=payload.depuis,
            vers=payload.vers,
            organe=payload.organe,
            note=payload.note,
        )
    )
    machines, _ = etat_du_parc(session)
    par_serie = {m.serie: m for m in machines}
    return {
        "organe": payload.organe,
        "receveuse": MachineOut(**asdict(par_serie[payload.vers])).model_dump(),
        "donneuse": MachineOut(**asdict(par_serie[payload.depuis])).model_dump(),
    }


# ---------------------------------------------------------------------------
# Accessoires
# ---------------------------------------------------------------------------


class AccessoireOut(BaseModel):
    serie: str
    type: str
    etat: str
    note: str | None
    prete_a: str | None
    prete_le: date | None
    retour_prevu_le: date | None
    pret_id: int | None
    en_retard: bool


class StockOut(BaseModel):
    accessoires: list[AccessoireOut]
    par_type: dict[str, dict[str, int]]
    nb_en_retard: int


def _stock_vers_out(stock) -> StockOut:
    return StockOut(
        accessoires=[
            AccessoireOut(**asdict(a), en_retard=a.en_retard) for a in stock.accessoires
        ],
        par_type=stock.par_type,
        nb_en_retard=len(stock.en_retard),
    )


@router.get("/accessoires", response_model=StockOut)
def lister_accessoires(session: Session = Depends(db_session)) -> StockOut:
    return _stock_vers_out(etat_du_stock(session))


class NouvelAccessoirePayload(BaseModel):
    serie: str
    type: str = "chargeur"
    note: str | None = None


@router.post("/accessoires", response_model=StockOut)
def ajouter_accessoire(
    payload: NouvelAccessoirePayload, session: Session = Depends(db_session)
) -> StockOut:
    _geste(
        lambda: enregistrer_accessoire(
            session, payload.serie, type_accessoire=payload.type, note=payload.note
        )
    )
    return _stock_vers_out(etat_du_stock(session))


class PretPayload(BaseModel):
    a_qui: str
    retour_prevu_le: date | None = None
    note: str | None = None


@router.post("/accessoires/{serie}/preter", response_model=StockOut)
def sortir_accessoire(
    serie: str, payload: PretPayload, session: Session = Depends(db_session)
) -> StockOut:
    _geste(
        lambda: preter(
            session,
            serie,
            a_qui=payload.a_qui,
            retour_prevu_le=payload.retour_prevu_le,
            note=payload.note,
        )
    )
    return _stock_vers_out(etat_du_stock(session))


class RetourPayload(BaseModel):
    etat: str = "en_stock"
    """L'objet peut revenir cassé : le retour dit dans quel état."""


@router.post("/accessoires/{serie}/rendre", response_model=StockOut)
def rentrer_accessoire(
    serie: str, payload: RetourPayload, session: Session = Depends(db_session)
) -> StockOut:
    _geste(lambda: rendre(session, serie, etat=payload.etat))
    return _stock_vers_out(etat_du_stock(session))
