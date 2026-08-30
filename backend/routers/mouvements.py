"""Les mouvements d'un seul élève, en cours d'année.

Le référentiel bouge d'abord, Google suit. L'inverse laisserait la bascule
du jour J et la composition des groupes ramener l'élève dans son ancienne
classe, chacune de son côté.

Chaque opération Google rend compte séparément : si l'une échoue, les
autres ont eu lieu et on sait laquelle reprendre. La reprise se demande
explicitement — elle accepte alors que le référentiel porte déjà le
changement, ce qui est précisément le cas après un échec à mi-chemin.
"""
from __future__ import annotations

from dataclasses import asdict

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session

from backend.database import db_session
from backend.services.mouvements_annee import (
    MouvementImpossible,
    planifier_changement_de_classe,
)

router = APIRouter(prefix="/api/mouvements", tags=["mouvements"])


class ChangementClassePayload(BaseModel):
    personne_id: int
    nouvelle_classe: str
    annee_id: int
    mode: str = "simulation"
    reprise: bool = False
    appliquer_google: bool = True
    """À faux, seul le référentiel bouge — utile quand on veut d'abord
    corriger KoXo à la main et laisser Google pour ensuite."""


class OperationOut(BaseModel):
    libelle: str
    reussie: bool
    message: str | None = None


class ResteAFaireOut(BaseModel):
    systeme: str
    geste: str


class MouvementOut(BaseModel):
    personne_id: int
    cle_pivot: str
    nom: str
    prenom: str
    email: str | None
    classe_avant: str | None
    classe_apres: str | None
    ou_avant: str | None
    ou_apres: str | None
    deplacement_utile: bool
    groupe_quitte: str | None
    groupe_rejoint: str | None
    reste_a_faire: list[ResteAFaireOut]
    avertissements: list[str]
    applique: bool
    operations: list[OperationOut] = []


def _client_ou_rien(session: Session):
    """Le client Google, ou la raison pour laquelle on n'en a pas."""
    from backend.services.google_api import ClientGoogle, charger_config

    try:
        return ClientGoogle(charger_config(session)), None
    except Exception as e:  # noqa: BLE001
        return None, f"Google n'est pas interrogeable : {e}"


@router.post("/changer-classe", response_model=MouvementOut)
def changer_de_classe(
    payload: ChangementClassePayload, session: Session = Depends(db_session)
) -> MouvementOut:
    """Fait passer un élève dans une autre classe, partout où c'est possible."""
    if payload.mode not in ("simulation", "reel"):
        raise HTTPException(400, f"mode invalide : {payload.mode!r}")

    try:
        plan = planifier_changement_de_classe(
            session,
            personne_id=payload.personne_id,
            nouvelle_classe=payload.nouvelle_classe,
            annee_id=payload.annee_id,
            mode=payload.mode,
            reprise=payload.reprise,
        )
    except MouvementImpossible as e:
        raise HTTPException(409, str(e)) from None
    except ValueError as e:
        raise HTTPException(400, str(e)) from None

    operations: list[OperationOut] = []
    if payload.mode == "reel":
        if payload.appliquer_google:
            from backend.services.mouvements_annee import appliquer_dans_google

            client, raison = _client_ou_rien(session)
            if client is None:
                operations = [
                    OperationOut(libelle="Joindre Google", reussie=False,
                                 message=raison)
                ]
            else:
                operations = [
                    OperationOut(**asdict(o))
                    for o in appliquer_dans_google(session, plan, client)
                ]

        from backend.services.journal import journaliser

        journaliser(
            session,
            type_operation="mouvement",
            cible="eleve",
            mode="reel",
            parametres={
                "personne_id": plan.personne_id,
                "classe_avant": plan.classe_avant,
                "classe_apres": plan.classe_apres,
                "reprise": payload.reprise,
            },
            resultat={
                "ou_apres": plan.ou_apres,
                "operations_reussies": sum(1 for o in operations if o.reussie),
                "operations_echouees": sum(1 for o in operations if not o.reussie),
            },
        )
        session.commit()
    else:
        session.rollback()

    sortie = asdict(plan)
    sortie["reste_a_faire"] = [ResteAFaireOut(**r) for r in sortie["reste_a_faire"]]
    return MouvementOut(**sortie, operations=operations)
