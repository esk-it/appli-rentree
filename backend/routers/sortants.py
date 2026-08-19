"""Endpoints du suivi des sortants."""
from __future__ import annotations

from datetime import date

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy.orm import Session

from backend.database import db_session
from backend.services.sortants import lister_sortants

router = APIRouter(prefix="/api/sortants", tags=["sortants"])


class SortantOut(BaseModel):
    personne_id: int
    cle_pivot: str
    nom: str
    prenom: str
    email: str | None
    site: str | None
    derniere_classe: str | None
    etat: str
    date_prevue_purge: date | None
    ou_attendue: str | None
    note: str | None
    echeance_depassee: bool
    verification: str
    ou_reelle: str | None
    suspendu_reellement: bool | None
    detail_verification: str | None


class RapportOut(BaseModel):
    nb_total: int
    nb_echeance_depassee: int
    nb_conformes: int
    nb_ecarts: int
    sortants: list[SortantOut]


def _en_sortie(r) -> RapportOut:
    return RapportOut(
        nb_total=r.nb_total,
        nb_echeance_depassee=r.nb_echeance_depassee,
        nb_conformes=r.nb_conformes,
        nb_ecarts=r.nb_ecarts,
        sortants=[
            SortantOut(**{**vars(s), "echeance_depassee": s.echeance_depassee})
            for s in r.sortants
        ],
    )


@router.get("", response_model=RapportOut)
def lister(
    site_id: int | None = Query(None),
    seulement_echus: bool = Query(False, description="Seuls ceux dont la purge est due"),
    session: Session = Depends(db_session),
) -> RapportOut:
    """Les comptes en sortie, tels que le programme les connaît."""
    return _en_sortie(
        lister_sortants(session, site_id=site_id, seulement_echus=seulement_echus)
    )


class VerificationOut(BaseModel):
    job_id: str
    nb_a_verifier: int


@router.post("/verifier", response_model=VerificationOut)
def verifier(
    site_id: int | None = Query(None), session: Session = Depends(db_session)
) -> VerificationOut:
    """Confronte chaque compte à son état réel dans Google.

    Ne modifie rien, ni chez Google ni en base : relève les écarts. La
    correction reste une action délibérée.

    Réutilise le suivi d'exécution — une vérification sur plusieurs
    centaines de comptes est aussi longue qu'un déplacement, et mérite le
    même avancement lisible.
    """
    from backend.services.google_api import ClientGoogle, charger_config
    from backend.services.jobs_google import creer_job, lancer_en_tache_de_fond
    from backend.services.sortants import CONFORME, comparer_au_constat

    rapport = lister_sortants(session, site_id=site_id)
    a_verifier = [s for s in rapport.sortants if s.email]
    if not a_verifier:
        raise HTTPException(400, "Aucun sortant avec une adresse à vérifier.")

    config = charger_config(session)
    try:
        client = ClientGoogle(config)
    except ValueError as e:
        raise HTTPException(400, str(e)) from None

    # Le job manipule des « opérations » : on lui en fabrique de lecture.
    class _Lecture:
        def __init__(self, sortant):
            self.action = "verifier"
            self.email = sortant.email
            self.libelle = f"Vérifier {sortant.email}"
            self.personne_id = None  # rien à mémoriser : c'est une lecture
            self.ou_visee = None
            self.sortant = sortant

    lectures = [_Lecture(s) for s in a_verifier]
    job = creer_job(
        phase="verification",
        libelle=f"Vérification de {len(lectures)} compte(s) sortant(s)",
        operations=lectures,
    )

    # Un écart n'est pas une panne : il devient l'échec de l'étape, ce qui
    # le fait remonter en tête de liste avec son motif — exactement le
    # comportement voulu pour une vérification.
    def verifier_un(lecture) -> None:
        constat = client.lire_utilisateur(lecture.email)
        comparer_au_constat(lecture.sortant, constat)
        if lecture.sortant.verification != CONFORME:
            raise RuntimeError(lecture.sortant.detail_verification or "écart constaté")

    lancer_en_tache_de_fond(job, lectures, appliquer=verifier_un)
    return VerificationOut(job_id=job.id, nb_a_verifier=len(lectures))
