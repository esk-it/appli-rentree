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

from fastapi import APIRouter, Depends, HTTPException, Query
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

# Seuls ces traitements écrivent dans Google, donc sont rejouables : leurs
# opérations portent un corps de requête. Un relevé ou une vérification n'en
# ont pas — les rejouer partirait sur le chemin d'écriture, à partir de rien.
PHASES_MODIFIANTES = {"pre_rentree", "definitive"}


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


# ---------------------------------------------------------------------------
# Exécution suivie — l'avancement élève par élève
# ---------------------------------------------------------------------------


class EtapeOut(BaseModel):
    index: int
    action: str
    email: str
    libelle: str
    ou_visee: str | None
    statut: str
    message: str | None


class JobOut(BaseModel):
    id: str
    phase: str
    libelle: str
    total: int
    nb_reussies: int
    nb_echecs: int
    nb_traitees: int
    progression: float
    est_termine: bool
    annule: bool
    erreur_fatale: str | None
    etapes: list[EtapeOut]


def _job_vers_out(job) -> JobOut:
    return JobOut(
        id=job.id,
        phase=job.phase,
        libelle=job.libelle,
        total=job.total,
        nb_reussies=job.nb_reussies,
        nb_echecs=job.nb_echecs,
        nb_traitees=job.nb_traitees,
        progression=job.progression,
        est_termine=job.est_termine,
        annule=job.annule,
        erreur_fatale=job.erreur_fatale,
        etapes=[
            EtapeOut(
                index=e.index, action=e.action, email=e.email, libelle=e.libelle,
                ou_visee=e.ou_visee, statut=e.statut, message=e.message,
            )
            for e in job.etapes
        ],
    )


def _memoriser_dans_sa_propre_session(appliquees: list[tuple[int, str]]) -> None:
    """Enregistre les OU appliquées depuis le thread du job.

    La session de la requête HTTP est close depuis longtemps quand le job
    se termine : il lui en faut une à lui, ouverte et fermée ici.
    """
    from backend.database import _SessionLocal
    from backend.services.google_api import enregistrer_ou_appliquees

    session = _SessionLocal()
    try:
        enregistrer_ou_appliquees(session, appliquees)
    finally:
        session.close()


@router.post("/jobs", response_model=JobOut)
def lancer_job(
    payload: ExecutionPayload, session: Session = Depends(db_session)
) -> JobOut:
    """Applique le plan côté Google en tâche de fond, avec suivi.

    Rend la main immédiatement : l'interface interroge ensuite
    `GET /jobs/{id}` pour afficher l'avancement.
    """
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
    if not plan.operations:
        raise HTTPException(400, "Aucune opération à appliquer.")

    from backend.services.jobs_google import creer_job, lancer_en_tache_de_fond

    libelle = (
        "Placement en OU de pré-rentrée"
        if payload.phase == "pre_rentree"
        else "Bascule vers les OU définitives"
    )
    job = creer_job(phase=payload.phase, libelle=libelle, operations=plan.operations)
    lancer_en_tache_de_fond(
        job,
        plan.operations,
        appliquer=client.appliquer_operation,
        au_succes=_memoriser_dans_sa_propre_session,
    )
    return _job_vers_out(job)


@router.get("/jobs/{job_id}", response_model=JobOut)
def suivre_job(job_id: str) -> JobOut:
    """État d'avancement — interrogé en boucle par l'interface."""
    from backend.services.jobs_google import obtenir_job

    job = obtenir_job(job_id)
    if job is None:
        raise HTTPException(404, f"Traitement introuvable : {job_id}")
    return _job_vers_out(job)


@router.get("/jobs", response_model=list[JobOut])
def lister_les_jobs() -> list[JobOut]:
    """Les traitements récents, le plus récent en tête."""
    from backend.services.jobs_google import lister_jobs

    return [_job_vers_out(j) for j in lister_jobs()]


@router.post("/jobs/{job_id}/annuler", response_model=JobOut)
def annuler_job(job_id: str) -> JobOut:
    """Arrête le traitement après l'étape en cours.

    On ne coupe jamais au milieu d'un appel : une opération est envoyée ou
    ne l'est pas.
    """
    from backend.services.jobs_google import demander_annulation, obtenir_job

    if not demander_annulation(job_id):
        job = obtenir_job(job_id)
        if job is None:
            raise HTTPException(404, f"Traitement introuvable : {job_id}")
        raise HTTPException(409, "Traitement déjà terminé.")
    return _job_vers_out(obtenir_job(job_id))


@router.post("/jobs/{job_id}/rejouer-echecs", response_model=JobOut)
def rejouer_echecs(job_id: str, session: Session = Depends(db_session)) -> JobOut:
    """Relance uniquement les opérations qui ont échoué.

    Ce qui a abouti n'est pas refait : on complète un traitement partiel,
    on ne le recommence pas.
    """
    from backend.services.jobs_google import (
        creer_job,
        lancer_en_tache_de_fond,
        obtenir_job,
        operations_en_echec,
    )

    precedent = obtenir_job(job_id)
    if precedent is None:
        raise HTTPException(404, f"Traitement introuvable : {job_id}")
    if not precedent.est_termine:
        raise HTTPException(409, "Traitement encore en cours.")

    # Un relevé ou une vérification lisent Google ; leurs opérations n'ont pas
    # de corps de requête. Les rejouer ici les enverrait sur le chemin
    # d'écriture — c'est-à-dire tenter une modification à partir de rien.
    if precedent.phase not in PHASES_MODIFIANTES:
        raise HTTPException(
            409,
            f"« {precedent.libelle} » ne modifie rien dans Google : il n'y a "
            "pas de reprise possible. Relance-le simplement.",
        )

    operations = operations_en_echec(job_id)
    if not operations:
        raise HTTPException(400, "Aucun échec à rejouer.")

    config = charger_config(session)
    try:
        client = ClientGoogle(config)
    except ValueError as e:
        raise HTTPException(400, str(e))

    job = creer_job(
        phase=precedent.phase,
        libelle=f"{precedent.libelle} — reprise des échecs",
        operations=operations,
    )
    lancer_en_tache_de_fond(
        job, operations,
        appliquer=client.appliquer_operation,
        au_succes=_memoriser_dans_sa_propre_session,
    )
    return _job_vers_out(job)


# ---------------------------------------------------------------------------
# Inspection d'une branche d'OU — « qui sont ces comptes ? »
# ---------------------------------------------------------------------------


class CompteTrouveOut(BaseModel):
    email: str
    ou: str
    suspendu: bool
    nom_google: str
    prenom_google: str
    derniere_connexion: str | None
    statut: str
    cle_pivot: str | None
    nom: str | None
    prenom: str | None
    derniere_annee: str | None
    derniere_classe: str | None


class InspectionOut(BaseModel):
    prefixe_ou: str
    annee_reference: str | None
    nb_total: int
    nb_sortis: int
    nb_encore_inscrits: int
    nb_inconnus: int
    comptes: list[CompteTrouveOut]


@router.get("/inspecter-ou", response_model=InspectionOut)
def inspecter_ou(
    ou: str = Query(..., min_length=1, description="Préfixe d'OU, ex. /3. NDK/NDK2025"),
    session: Session = Depends(db_session),
) -> InspectionOut:
    """Liste les comptes présents sous une branche d'OU, et dit qui ils sont.

    Lecture seule, des deux côtés : rien n'est modifié dans Google ni en
    base. Sert à comprendre ce qui traîne dans une arborescence avant de
    décider quoi en faire.
    """
    from backend.services.inspection_ou import recouper_avec_referentiel

    config = charger_config(session)
    try:
        client = ClientGoogle(config)
    except ValueError as e:
        raise HTTPException(400, str(e)) from None

    try:
        comptes = client.lister_utilisateurs(prefixe_ou=ou)
    except Exception as e:
        raise HTTPException(502, f"Lecture Google impossible : {type(e).__name__}: {e}")

    r = recouper_avec_referentiel(session, comptes, prefixe_ou=ou)
    return InspectionOut(
        prefixe_ou=r.prefixe_ou,
        annee_reference=r.annee_reference,
        nb_total=r.nb_total,
        nb_sortis=r.nb_sortis,
        nb_encore_inscrits=r.nb_encore_inscrits,
        nb_inconnus=r.nb_inconnus,
        comptes=[CompteTrouveOut(**vars(c)) for c in r.comptes],
    )
