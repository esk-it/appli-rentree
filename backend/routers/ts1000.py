"""Endpoint du différentiel TS1000.

Un seul appel : on dépose l'export de la centrale, on reçoit le relevé et
les quatre fichiers prêts. Ils sont rendus ensemble parce qu'ils se lisent
ensemble — décider d'importer les suppressions suppose d'avoir vu combien
de déplacements les accompagnent.
"""
from __future__ import annotations

import base64
import binascii

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session

from backend.database import db_session
from backend.services.differentiel_ts1000 import (
    DifferentielImpossible,
    calculer_differentiel,
    controler_cardid,
    ecrire_classeur,
)

router = APIRouter(prefix="/api/ts1000", tags=["ts1000"])


class DifferentielPayload(BaseModel):
    contenu_base64: str
    nom_fichier: str = "Users.xls"
    annee_id: int


class MouvementOut(BaseModel):
    op: str
    badge: str
    nom: str
    groupe_actuel: str | None
    groupe_vise: str | None
    motif: str
    a_une_carte: bool


class LotOut(BaseModel):
    id: str
    libelle: str
    nb: int
    nom_fichier: str
    contenu_base64: str
    mouvements: list[MouvementOut]


class DifferentielOut(BaseModel):
    nb_lignes_lues: int
    nb_inscrits: int
    nb_total: int
    lots: list[LotOut]
    proteges: list[MouvementOut]
    indetermines: list[MouvementOut]
    groupes_internat: list[str]
    avertissements: list[str]
    cardid_perdus: list[str]
    """Vide en fonctionnement normal. Non vide, ne rien importer : une carte
    encodée cesserait d'ouvrir."""


def _sortie(m) -> MouvementOut:
    return MouvementOut(
        op=m.op,
        badge=m.badge,
        nom=m.nom,
        groupe_actuel=m.groupe_actuel,
        groupe_vise=m.groupe_vise,
        motif=m.motif,
        a_une_carte=m.a_une_carte,
    )


@router.post("/differentiel", response_model=DifferentielOut)
def differentiel(
    payload: DifferentielPayload, session: Session = Depends(db_session)
) -> DifferentielOut:
    """Ce qu'il faudrait porter dans TS1000. N'écrit rien nulle part."""
    try:
        contenu = base64.b64decode(payload.contenu_base64)
    except (binascii.Error, ValueError) as e:
        raise HTTPException(400, f"Fichier illisible : {e}") from None

    try:
        r = calculer_differentiel(session, contenu, annee_id=payload.annee_id)
    except DifferentielImpossible as e:
        raise HTTPException(400, str(e)) from None

    # L'ordre des lots est celui dans lequel on les importe : créer avant de
    # déplacer, déplacer avant de supprimer. Une suppression jouée d'abord
    # effacerait un badge qu'un déplacement allait sauver.
    familles = [
        ("creations", "Créations", r.creations),
        ("deplacements", "Déplacements de classe", r.deplacements),
        ("internat", "Passages à l'internat", r.internat),
        ("suppressions", "Suppressions", r.suppressions),
    ]

    lots: list[LotOut] = []
    perdus: list[str] = []
    for i, (identifiant, libelle, mouvements) in enumerate(familles, start=1):
        if not mouvements:
            continue
        perdus += controler_cardid(r.colonnes, mouvements)
        lots.append(
            LotOut(
                id=identifiant,
                libelle=libelle,
                nb=len(mouvements),
                nom_fichier=f"TS1000_{i}_{identifiant}.xlsx",
                contenu_base64=base64.b64encode(
                    ecrire_classeur(r.colonnes, mouvements)
                ).decode("ascii"),
                mouvements=[_sortie(m) for m in mouvements],
            )
        )

    avertissements = list(r.avertissements)
    if perdus:
        avertissements.insert(
            0,
            f"{len(perdus)} ligne(s) perdraient leur CardId — "
            "ne rien importer : les cartes cesseraient d'ouvrir.",
        )

    return DifferentielOut(
        nb_lignes_lues=r.nb_lignes_lues,
        nb_inscrits=r.nb_inscrits,
        nb_total=r.nb_total,
        lots=lots,
        proteges=[_sortie(m) for m in r.proteges],
        indetermines=[_sortie(m) for m in r.indetermines],
        groupes_internat=r.groupes_internat,
        avertissements=avertissements,
        cardid_perdus=sorted(set(perdus)),
    )
