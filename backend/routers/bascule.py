"""Endpoints de la bascule des OU Google."""
from __future__ import annotations

import base64

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy.orm import Session

from backend.database import db_session
from backend.services.bascule import (
    LIBELLE_PHASE,
    enregistrer_bascule,
    generer_csv_bascule,
    planifier_bascule,
)

router = APIRouter(prefix="/api/bascule", tags=["bascule"])


class MouvementOut(BaseModel):
    personne_id: int
    cle_pivot: str
    nom: str
    prenom: str
    classe: str | None
    site: str
    email: str | None
    ou_appliquee: str | None
    ou_visee: str | None
    statut: str
    motif: str


class RapportOut(BaseModel):
    phase: str
    phase_libelle: str
    annee_libelle: str
    sites: list[str]
    nb_total: int
    nb_a_deplacer: int
    nb_deja_en_place: int
    nb_bloques: int
    est_applicable: bool
    mouvements: list[MouvementOut]


def _planifier(session, annee_id, phase, site_id):
    try:
        return planifier_bascule(
            session, annee_id=annee_id, phase=phase, site_id=site_id
        )
    except ValueError as e:
        code = 400 if "phase" in str(e) else 404
        raise HTTPException(code, str(e)) from None


def _en_sortie(r) -> RapportOut:
    return RapportOut(
        phase=r.phase,
        phase_libelle=LIBELLE_PHASE[r.phase],
        annee_libelle=r.annee_libelle,
        sites=r.sites,
        nb_total=r.nb_total,
        nb_a_deplacer=r.nb_a_deplacer,
        nb_deja_en_place=r.nb_deja_en_place,
        nb_bloques=r.nb_bloques,
        est_applicable=r.est_applicable,
        mouvements=[MouvementOut(**vars(m)) for m in r.mouvements],
    )


@router.get("", response_model=RapportOut)
def planifier(
    annee_id: int = Query(..., description="Année dont on prépare la rentrée"),
    phase: str = Query(..., description="`pre_rentree` ou `definitive`"),
    site_id: int | None = Query(None, description="Un site, ou tous si absent"),
    session: Session = Depends(db_session),
) -> RapportOut:
    """Ce que la bascule ferait — ne modifie rien."""
    return _en_sortie(_planifier(session, annee_id, phase, site_id))


class FichierOut(BaseModel):
    nom_fichier: str
    contenu_base64: str
    nb_lignes: int


@router.get("/csv", response_model=FichierOut)
def telecharger_csv(
    annee_id: int = Query(...),
    phase: str = Query(...),
    site_id: int | None = Query(None),
    session: Session = Depends(db_session),
) -> FichierOut:
    """CSV de mise à jour d'OU pour la console Google Admin."""
    r = _planifier(session, annee_id, phase, site_id)
    contenu = generer_csv_bascule(r)
    portee = "_".join(r.sites) if len(r.sites) <= 3 else "tous"
    suffixe = "pre-rentree" if r.phase == "pre_rentree" else "definitive"
    return FichierOut(
        nom_fichier=f"Google_OU_{suffixe}_{portee}_{r.annee_libelle}.csv",
        contenu_base64=base64.b64encode(contenu).decode("ascii"),
        nb_lignes=r.nb_a_deplacer,
    )


class ConfirmationPayload(BaseModel):
    annee_id: int
    phase: str
    site_id: int | None = None
    mode: str = "simulation"


class ConfirmationOut(BaseModel):
    nb_enregistres: int
    mode: str
    message: str


@router.post("/confirmer", response_model=ConfirmationOut)
def confirmer(
    payload: ConfirmationPayload, session: Session = Depends(db_session)
) -> ConfirmationOut:
    """Enregistre que la bascule a été appliquée côté Google.

    À appeler **après** l'import du CSV dans la console Admin. Le programme
    n'agit pas sur Google : il prend acte, pour savoir ensuite qui reste à
    déplacer.
    """
    if payload.mode not in ("simulation", "reel"):
        raise HTTPException(400, f"mode invalide : {payload.mode!r}")
    r = _planifier(session, payload.annee_id, payload.phase, payload.site_id)
    if not r.est_applicable:
        raise HTTPException(
            409,
            f"{r.nb_bloques} élève(s) sans OU calculable — complète la Table de "
            "correspondance avant de confirmer.",
        )
    n = enregistrer_bascule(session, r, mode=payload.mode)
    return ConfirmationOut(
        nb_enregistres=n,
        mode=payload.mode,
        message=(
            f"{n} déplacement(s) enregistré(s)"
            if payload.mode == "reel"
            else f"{n} déplacement(s) seraient enregistrés"
        ),
    )


# ---------------------------------------------------------------------------
# Relevé de l'état réel — remplacer « ? » par ce que Google contient
# ---------------------------------------------------------------------------


class ReleveOut(BaseModel):
    job_id: str
    nb_a_relever: int


@router.post("/relever", response_model=ReleveOut)
def relever_ou_reelles(
    annee_id: int = Query(...),
    site_id: int | None = Query(None),
    session: Session = Depends(db_session),
) -> ReleveOut:
    """Lit l'OU actuelle de chaque élève dans Google et la mémorise.

    Sans cela, le programme ne connaît que les OU qu'il a lui-même
    demandées : pour un compte créé avant lui, ou déplacé à la main, il
    n'a rien à afficher comme point de départ — d'où les « ? ».

    Lecture seule côté Google. En base, seule la dernière OU connue est
    mise à jour : aucun état de compte n'est touché.
    """
    from backend.services.google_api import (
        ClientGoogle,
        charger_config,
        enregistrer_ou_appliquees,
    )
    from backend.services.jobs_google import creer_job, lancer_en_tache_de_fond

    rapport = _planifier(session, annee_id, "definitive", site_id)
    cibles = [m for m in rapport.mouvements if m.email]
    if not cibles:
        raise HTTPException(400, "Aucun élève avec une adresse à relever.")

    config = charger_config(session)
    try:
        client = ClientGoogle(config)
    except ValueError as e:
        raise HTTPException(400, str(e)) from None

    class _Lecture:
        def __init__(self, mouvement):
            self.action = "relever"
            self.email = mouvement.email
            self.libelle = f"Relever l'OU de {mouvement.email}"
            self.personne_id = mouvement.personne_id
            # Renseignée par la lecture : le job mémorise ensuite ce champ.
            self.ou_visee = None
            self.etape = None

    lectures = [_Lecture(m) for m in cibles]
    job = creer_job(
        phase="releve",
        libelle=f"Relevé de {len(lectures)} OU dans Google",
        operations=lectures,
    )
    # Chaque lecture pointe vers son étape : c'est elle que le job consulte
    # après coup pour savoir quoi mémoriser.
    for lecture, etape in zip(lectures, job.etapes):
        lecture.etape = etape

    def relever_une(lecture) -> None:
        constat = client.lire_utilisateur(lecture.email)
        if constat.erreur:
            raise RuntimeError(constat.erreur)
        if not constat.existe:
            raise RuntimeError("Compte absent de Google")
        lecture.etape.ou_visee = constat.ou

    def memoriser(appliquees) -> None:
        from backend.database import _SessionLocal

        s = _SessionLocal()
        try:
            enregistrer_ou_appliquees(s, appliquees)
        finally:
            s.close()

    lancer_en_tache_de_fond(job, lectures, appliquer=relever_une, au_succes=memoriser)
    return ReleveOut(job_id=job.id, nb_a_relever=len(lectures))
