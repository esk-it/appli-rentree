"""Endpoints du suivi CompteCible (Lot 12)."""
from __future__ import annotations

from datetime import date

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session

from backend.database import db_session
from backend.services.cycle_vie import (
    activer,
    cibles_pour,
    confirmer_creation,
    purger,
    traiter_sortants,
)
from backend.services.suivi import (
    comptes_a_purger,
    lister_par_etat,
    marquer_sortant,
    stats_suivi,
)

router = APIRouter(prefix="/api/suivi", tags=["suivi"])


class StatsOut(BaseModel):
    par_cible: dict[str, dict[str, int]]
    total_par_etat: dict[str, int]
    nb_purges_echues: int


@router.get("/stats", response_model=StatsOut)
def obtenir_stats(session: Session = Depends(db_session)) -> StatsOut:
    s = stats_suivi(session)
    return StatsOut(
        par_cible=s.par_cible,
        total_par_etat=s.total_par_etat,
        nb_purges_echues=s.nb_purges_echues,
    )


class LigneCompteOut(BaseModel):
    id: int
    personne_id: int
    cle_pivot: str
    nom: str
    prenom: str
    login: str
    site_nom: str | None
    cible: str
    etat: str
    identifiant_externe: str | None
    date_prevue_purge: date | None
    note: str | None


@router.get("/liste", response_model=list[LigneCompteOut])
def lister(
    etat: str, cible: str | None = None, session: Session = Depends(db_session)
) -> list[LigneCompteOut]:
    try:
        rows = lister_par_etat(session, etat, cible)
    except ValueError as e:
        raise HTTPException(400, str(e))
    return [
        LigneCompteOut(
            id=c.id,
            personne_id=p.id, cle_pivot=p.cle_pivot,
            nom=p.nom, prenom=p.prenom, login=p.login,
            site_nom=s.nom if s else None,
            cible=c.cible, etat=c.etat,
            identifiant_externe=c.identifiant_externe,
            date_prevue_purge=c.date_prevue_purge, note=c.note,
        )
        for c, p, s in rows
    ]


@router.get("/purges-echues", response_model=list[LigneCompteOut])
def lister_purges(session: Session = Depends(db_session)) -> list[LigneCompteOut]:
    comptes = comptes_a_purger(session)
    resultat = []
    for c in comptes:
        p = c.personne
        resultat.append(LigneCompteOut(
            id=c.id, personne_id=p.id, cle_pivot=p.cle_pivot,
            nom=p.nom, prenom=p.prenom, login=p.login,
            site_nom=p.site.nom if p.site else None,
            cible=c.cible, etat=c.etat,
            identifiant_externe=c.identifiant_externe,
            date_prevue_purge=c.date_prevue_purge, note=c.note,
        ))
    return resultat


class MarquerSortantPayload(BaseModel):
    personne_id: int
    cible: str


@router.post("/marquer-sortant")
def poster_sortant(
    payload: MarquerSortantPayload, session: Session = Depends(db_session)
) -> dict:
    try:
        t = marquer_sortant(session, payload.personne_id, payload.cible)
    except ValueError as e:
        raise HTTPException(400, str(e))
    session.commit()
    return {
        "ok": True,
        "personne_id": t.personne_id, "cible": t.cible,
        "etat_avant": t.etat_avant, "etat_apres": t.etat_apres,
        "date_prevue_purge": t.date_prevue_purge.isoformat() if t.date_prevue_purge else None,
    }


# ---------------------------------------------------------------------------
# Transitions de cycle de vie
# ---------------------------------------------------------------------------


class RapportCycleOut(BaseModel):
    operation: str
    nb_crees: int
    nb_transitions: int
    nb_ignores: int
    details: list[dict]
    erreurs: list[str]


class ConfirmerPayload(BaseModel):
    cible: str
    site_id: int | None = None


@router.post("/confirmer-creation", response_model=RapportCycleOut)
def poster_confirmer_creation(
    payload: ConfirmerPayload, session: Session = Depends(db_session)
) -> RapportCycleOut:
    """Passe les comptes `prevu` à `cree` — après import effectif côté cible."""
    try:
        r = confirmer_creation(session, cible=payload.cible, site_id=payload.site_id)
    except ValueError as e:
        raise HTTPException(400, str(e))
    session.commit()
    return RapportCycleOut(**r.__dict__)


@router.post("/activer", response_model=RapportCycleOut)
def poster_activer(
    payload: ConfirmerPayload, session: Session = Depends(db_session)
) -> RapportCycleOut:
    """Passe les comptes `cree` à `actif`."""
    try:
        r = activer(session, cible=payload.cible, site_id=payload.site_id)
    except ValueError as e:
        raise HTTPException(400, str(e))
    session.commit()
    return RapportCycleOut(**r.__dict__)


class TraiterSortantsPayload(BaseModel):
    annee_source_id: int
    annee_cible_id: int


@router.post("/traiter-sortants", response_model=RapportCycleOut)
def poster_traiter_sortants(
    payload: TraiterSortantsPayload, session: Session = Depends(db_session)
) -> RapportCycleOut:
    """Applique la politique de sortie à tous les sortants de la réconciliation.

    Google → quarantaine +18 mois. Autres cibles → purge immédiate.
    Aucune suppression n'est effectuée côté système tiers : seul l'état du
    référentiel change.
    """
    try:
        r = traiter_sortants(session, payload.annee_source_id, payload.annee_cible_id)
    except ValueError as e:
        raise HTTPException(404, str(e))
    session.commit()
    return RapportCycleOut(**r.__dict__)


class PurgerPayload(BaseModel):
    """Purge des comptes dont l'échéance de quarantaine est dépassée.

    `confirmation` est un garde-fou explicite : le prompt impose une
    « confirmation séparée » pour toute suppression.
    """

    compte_ids: list[int] | None = None
    cible: str | None = None
    confirmation: bool = False


@router.post("/purger", response_model=RapportCycleOut)
def poster_purger(
    payload: PurgerPayload, session: Session = Depends(db_session)
) -> RapportCycleOut:
    """Marque comme purgés les comptes dont la quarantaine est terminée.

    N'effectue **aucune suppression** dans les systèmes tiers : enregistre
    que l'utilisateur l'a faite de son côté. Seuls les comptes en
    quarantaine avec une échéance atteinte sont éligibles.
    """
    if not payload.confirmation:
        raise HTTPException(
            400,
            "Confirmation requise : relis la liste des comptes concernés puis "
            "renvoie `confirmation: true`.",
        )
    try:
        r = purger(session, compte_ids=payload.compte_ids, cible=payload.cible)
    except ValueError as e:
        raise HTTPException(400, str(e))
    session.commit()

    try:
        from backend.services.journal import journaliser

        journaliser(
            session,
            type_operation="cycle_vie",
            cible=payload.cible or "toutes",
            parametres={"nb_demandes": len(payload.compte_ids or [])},
            resultat={"nb_purges": r.nb_transitions, "nb_refuses": len(r.erreurs)},
        )
        session.commit()
    except Exception:  # pragma: no cover — le journal ne doit rien casser
        session.rollback()

    return RapportCycleOut(**r.__dict__)


@router.get("/cibles")
def obtenir_cibles(site_nom: str, type_personne: str) -> dict:
    """Cibles applicables à un couple (site, type de personne)."""
    try:
        return {"cibles": cibles_pour(site_nom, type_personne)}
    except ValueError as e:
        raise HTTPException(400, str(e))
