"""Ce qui est parti chez qui, et ce qui a bougé depuis.

Lecture seule, sauf la déclaration : pour Sodexo, le programme ne
fabrique pas le fichier — il prend acte de ce que l'utilisateur dit avoir
transmis.
"""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy.orm import Session

from backend.database import db_session
from backend.models import AnneeScolaire
from backend.models.envoi import SYSTEMES_DESTINATAIRES
from backend.services.envois import enregistrer, etat

router = APIRouter(prefix="/api/envois", tags=["envois"])


class MouvementClasseOut(BaseModel):
    classe: str
    nb_actuel: int
    entrants: list[str]
    sortants: list[str]
    arrives_d_ailleurs: list[str]
    nb_changements: int


class EtatEnvoiOut(BaseModel):
    systeme: str
    envoye_le: str | None
    declare: bool
    nom_fichier: str | None
    nb_envoyes: int
    nb_actuels: int
    nb_changements: int
    nb_classes_touchees: int
    classes: list[MouvementClasseOut]


def _annee(session: Session, annee_id: int | None) -> AnneeScolaire:
    if annee_id is not None:
        a = session.get(AnneeScolaire, annee_id)
        if a is None:
            raise HTTPException(404, f"Année {annee_id} inconnue.")
        return a
    a = (
        session.query(AnneeScolaire)
        .order_by(AnneeScolaire.libelle.desc())
        .first()
    )
    if a is None:
        raise HTTPException(404, "Aucune année scolaire dans le référentiel.")
    return a


def _verifier(systeme: str) -> str:
    if systeme not in SYSTEMES_DESTINATAIRES:
        raise HTTPException(
            400,
            f"Système inconnu : {systeme!r}. "
            f"Attendu parmi {', '.join(SYSTEMES_DESTINATAIRES)}.",
        )
    return systeme


def _en_sortie(e) -> EtatEnvoiOut:
    return EtatEnvoiOut(
        systeme=e.systeme,
        envoye_le=e.envoye_le.isoformat() if e.envoye_le else None,
        declare=e.declare,
        nom_fichier=e.nom_fichier,
        nb_envoyes=e.nb_envoyes,
        nb_actuels=e.nb_actuels,
        nb_changements=e.nb_changements,
        nb_classes_touchees=e.nb_classes_touchees,
        classes=[
            MouvementClasseOut(
                classe=c.classe,
                nb_actuel=c.nb_actuel,
                entrants=c.entrants,
                sortants=c.sortants,
                arrives_d_ailleurs=c.arrives_d_ailleurs,
                nb_changements=c.nb_changements,
            )
            for c in e.classes
        ],
    )


@router.get("/{systeme}", response_model=EtatEnvoiOut)
def lire_etat(
    systeme: str,
    annee_id: int | None = Query(None),
    session: Session = Depends(db_session),
) -> EtatEnvoiOut:
    """Le dernier envoi, et classe par classe ce qui a bougé depuis."""
    return _en_sortie(etat(session, _verifier(systeme), _annee(session, annee_id).id))


class DeclarationPayload(BaseModel):
    annee_id: int | None = None
    note: str | None = None


@router.post("/{systeme}/declarer", response_model=EtatEnvoiOut)
def declarer(
    systeme: str,
    payload: DeclarationPayload,
    session: Session = Depends(db_session),
) -> EtatEnvoiOut:
    """Prend acte d'un envoi que le programme n'a pas fabriqué.

    Le CSV de Sodexo naît d'un classeur Google : le programme ne peut pas
    savoir qu'il est parti. Il le tient de l'utilisateur, et le dit —
    l'écran distingue un envoi déclaré d'un fichier produit, parce qu'un
    envoi déclaré vaut ce que vaut la parole de celui qui l'a déclaré.
    """
    annee = _annee(session, payload.annee_id)
    enregistrer(
        session,
        systeme=_verifier(systeme),
        annee_id=annee.id,
        declare=True,
        note=payload.note,
    )
    return _en_sortie(etat(session, systeme, annee.id))
