"""Endpoints du mode API Google Workspace.

Trois étapes distinctes, dans cet ordre :

1. `GET /statut` — la configuration est-elle exploitable ?
2. `POST /plan` — que ferait-on ? (aucun envoi)
3. `POST /executer` — application effective, sur confirmation explicite

Aucun endpoint de suppression : le prompt l'interdit (§7.2). Un sortant est
suspendu et déplacé en OU d'archivage, jamais effacé.
"""
from __future__ import annotations

from typing import Any, Literal

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session

from backend.database import db_session
from backend.services.google_api import (
    ClientGoogle,
    charger_config,
    construire_plan,
    est_disponible,
)

router = APIRouter(prefix="/api/google", tags=["google_api"])


class StatutOut(BaseModel):
    bibliotheques_disponibles: bool
    message_bibliotheques: str
    api_active: bool
    configuration_complete: bool
    problemes: list[str]


@router.get("/statut", response_model=StatutOut)
def obtenir_statut(session: Session = Depends(db_session)) -> StatutOut:
    """Diagnostic de la configuration — ne contacte pas Google."""
    disponible, message = est_disponible()
    config = charger_config(session)
    problemes = config.valider()
    return StatutOut(
        bibliotheques_disponibles=disponible,
        message_bibliotheques=message,
        api_active=config.active,
        configuration_complete=not problemes and disponible,
        problemes=problemes,
    )


@router.post("/tester-connexion")
def tester_connexion(session: Session = Depends(db_session)) -> dict:
    """Vérifie l'authentification auprès de Google — lecture seule."""
    config = charger_config(session)
    try:
        client = ClientGoogle(config)
        return client.tester_connexion()
    except ValueError as e:
        raise HTTPException(400, str(e))
    except Exception as e:
        raise HTTPException(
            502,
            f"Connexion à Google impossible : {type(e).__name__}: {e}",
        )


class PlanPayload(BaseModel):
    site_id: int
    type_personne: Literal["eleve", "adulte"]
    annee_cible_id: int
    annee_source_id: int
    csv_koxo_base64: str | None = None
    """CSV KoXo enrichi — fournit les mots de passe des nouveaux comptes.
    Transite en mémoire, n'est jamais persisté."""

    phase: Literal["pre_rentree", "definitive"] = "pre_rentree"
    """Phase de rentrée visée. Même découpage que la bascule par CSV."""


class OperationOut(BaseModel):
    action: str
    email: str
    libelle: str


class PlanOut(BaseModel):
    phase: str
    nb_total: int
    nb_creations: int
    nb_deplacements: int
    nb_suspensions: int
    nb_bloques: int
    est_executable: bool
    operations: list[OperationOut]
    avertissements: list[str]


def _construire(session: Session, payload: PlanPayload):
    mots_de_passe: dict[str, str] = {}
    if payload.csv_koxo_base64:
        import base64

        from backend.services.exports_google import _extraire_mdp_depuis_csv_koxo

        try:
            contenu = base64.b64decode(payload.csv_koxo_base64)
            mots_de_passe = _extraire_mdp_depuis_csv_koxo(contenu)
        except Exception as e:
            raise HTTPException(400, f"CSV KoXo illisible : {e}")

    try:
        return construire_plan(
            session,
            site_id=payload.site_id,
            type_personne=payload.type_personne,
            annee_cible_id=payload.annee_cible_id,
            annee_source_id=payload.annee_source_id,
            mots_de_passe=mots_de_passe,
            phase=payload.phase,
        )
    except ValueError as e:
        raise HTTPException(400, str(e))


@router.post("/plan", response_model=PlanOut)
def obtenir_plan(
    payload: PlanPayload, session: Session = Depends(db_session)
) -> PlanOut:
    """Calcule les opérations qui seraient appliquées. N'envoie rien."""
    plan = _construire(session, payload)
    return PlanOut(
        phase=plan.phase,
        nb_total=plan.nb_total,
        nb_creations=plan.nb_creations,
        nb_deplacements=plan.nb_deplacements,
        nb_suspensions=plan.nb_suspensions,
        nb_bloques=plan.nb_bloques,
        est_executable=plan.est_executable,
        operations=[
            OperationOut(action=o.action, email=o.email, libelle=o.libelle)
            for o in plan.operations
        ],
        avertissements=plan.avertissements,
    )


class ExecutionPayload(PlanPayload):
    confirmation: bool = False
    """Garde-fou explicite : une exécution ne part jamais par défaut."""


class ExecutionOut(BaseModel):
    nb_reussies: int
    nb_echecs: int
    echecs: list[dict[str, Any]]
    tout_reussi: bool


@router.post("/executer", response_model=ExecutionOut)
def executer(
    payload: ExecutionPayload, session: Session = Depends(db_session)
) -> ExecutionOut:
    """Applique le plan côté Google. Exige une confirmation explicite."""
    if not payload.confirmation:
        raise HTTPException(
            400,
            "Confirmation requise : relis le plan puis renvoie "
            "`confirmation: true` pour appliquer.",
        )

    config = charger_config(session)
    try:
        client = ClientGoogle(config)
    except ValueError as e:
        raise HTTPException(400, str(e))

    plan = _construire(session, payload)
    if not plan.est_executable:
        raise HTTPException(
            409,
            f"{plan.nb_bloques} élève(s) sans OU calculable — complète la Table "
            "de correspondance avant d'exécuter.",
        )
    # `session` transmise : les OU réellement appliquées sont mémorisées, sans
    # quoi le canal CSV reproposerait indéfiniment les mêmes déplacements.
    resultat = client.executer_plan(plan, session=session)

    # Trace l'exécution — sans aucun mot de passe (le journal les filtre).
    try:
        from backend.services.journal import journaliser

        journaliser(
            session,
            type_operation="export",
            cible="google_api",
            mode="reel",
            parametres={
                "site_id": payload.site_id,
                "type_personne": payload.type_personne,
            },
            resultat={
                "nb_reussies": resultat.nb_reussies,
                "nb_echecs": resultat.nb_echecs,
            },
        )
        session.commit()
    except Exception:  # pragma: no cover
        session.rollback()

    return ExecutionOut(
        nb_reussies=resultat.nb_reussies,
        nb_echecs=resultat.nb_echecs,
        echecs=resultat.echecs,
        tout_reussi=resultat.tout_reussi,
    )
