"""Endpoints du mode API Google Workspace.

Trois étapes distinctes, dans cet ordre :

1. `GET /statut` — la configuration est-elle exploitable ?
2. `POST /plan` — que ferait-on ? (aucun envoi)
3. `POST /executer` — application effective, sur confirmation explicite

Aucun endpoint de suppression : le prompt l'interdit (§7.2). Un sortant est
suspendu et déplacé en OU d'archivage, jamais effacé.
"""
from __future__ import annotations

from datetime import date
from typing import Any, Literal

from fastapi import APIRouter, Depends, File, HTTPException, Query, UploadFile
from pydantic import BaseModel
from sqlalchemy.orm import Session

from backend.database import db_session
from backend.services.google_api import (
    ClientGoogle,
    OperationGoogle,
    charger_config,
    construire_plan,
    est_disponible,
    payload_deplacement_ou,
    payload_suspension,
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


# ---------------------------------------------------------------------------
# Vidange d'une branche d'OU
# ---------------------------------------------------------------------------


class MouvementVidangeOut(BaseModel):
    email: str
    ou_actuelle: str
    ou_visee: str
    suspendre: bool
    nom: str
    prenom: str
    statut_referentiel: str
    date_echeance: str | None = None


class EparneOut(BaseModel):
    email: str
    ou: str
    nom: str | None
    prenom: str | None
    classe: str | None = None
    """Classe de l'année préparée : là où la bascule le placera."""


class VidangeOut(BaseModel):
    ou_source: str
    ou_archivage: str
    date_depart: str
    date_echeance: str
    date_prevenance: str | None = None
    nb_trouves: int
    nb_a_archiver: int
    nb_deja_suspendus: int
    nb_epargnes: int
    nb_retardataires: int = 0
    avertissements: list[str]
    mouvements: list[MouvementVidangeOut]
    epargnes: list[EparneOut]


def _plan_vidange(
    session: Session,
    ou: str,
    annee_depart: int | None,
    ou_archivage: str | None = None,
    suspendre: bool = False,
):
    from backend.services.vidange_ou import planifier_vidange

    config = charger_config(session)
    try:
        client = ClientGoogle(config)
    except ValueError as e:
        raise HTTPException(400, str(e)) from None
    try:
        comptes = client.lister_utilisateurs(prefixe_ou=ou)
    except Exception as e:
        raise HTTPException(502, f"Lecture Google impossible : {type(e).__name__}: {e}")
    try:
        return client, planifier_vidange(
            session, comptes, ou_source=ou, annee_depart=annee_depart,
            ou_archivage=ou_archivage, suspendre=suspendre,
        )
    except ValueError as e:
        raise HTTPException(400, str(e)) from None


def _vidange_vers_out(r) -> VidangeOut:
    return VidangeOut(
        ou_source=r.ou_source,
        ou_archivage=r.ou_archivage,
        date_depart=r.date_depart.isoformat(),
        date_echeance=r.date_echeance.isoformat(),
        date_prevenance=r.date_prevenance.isoformat() if r.date_prevenance else None,
        nb_trouves=r.nb_trouves,
        nb_a_archiver=r.nb_a_archiver,
        nb_deja_suspendus=r.nb_deja_suspendus,
        nb_epargnes=len(r.epargnes),
        nb_retardataires=len(r.retardataires),
        avertissements=r.avertissements,
        mouvements=[
            MouvementVidangeOut(
                email=m.email,
                ou_actuelle=m.ou_actuelle,
                ou_visee=m.ou_visee,
                suspendre=m.suspendre,
                nom=m.nom,
                prenom=m.prenom,
                statut_referentiel=m.statut_referentiel,
                date_echeance=m.date_echeance.isoformat() if m.date_echeance else None,
            )
            for m in r.mouvements
        ],
        epargnes=[
            EparneOut(
                email=c.email, ou=c.ou, nom=c.nom, prenom=c.prenom,
                classe=c.derniere_classe,
            )
            for c in r.epargnes
        ],
    )


@router.get("/vidange-ou/plan", response_model=VidangeOut)
def plan_vidange(
    ou: str = Query(..., min_length=1),
    annee_depart: int | None = Query(None, description="Déduite du nom de l'OU si absente"),
    ou_archivage: str | None = Query(None, description="Destination imposée"),
    suspendre: bool = Query(False, description="Couper aussi l'accès"),
    session: Session = Depends(db_session),
) -> VidangeOut:
    """Ce que la vidange ferait. N'envoie rien."""
    _, r = _plan_vidange(session, ou, annee_depart, ou_archivage, suspendre)
    return _vidange_vers_out(r)


class LancerVidangePayload(BaseModel):
    ou: str
    annee_depart: int | None = None
    ou_archivage: str | None = None
    """Destination imposée. Sans elle, elle est déduite du site et de l'échéance."""
    suspendre: bool = False
    """L'usage est de déplacer sans suspendre : le compte reste consultable."""
    creer_destination: bool = True
    """Crée l'OU d'arrivée si Google ne la connaît pas encore."""
    confirmation: bool = False


@router.post("/vidange-ou", response_model=JobOut)
def lancer_vidange(
    payload: LancerVidangePayload, session: Session = Depends(db_session)
) -> JobOut:
    """Déplace les comptes de la branche vers l'OU d'archivage.

    Le compte **reste actif** sauf demande explicite : la quarantaine tient
    à la sortie de l'arbre des classes, pas à la privation d'accès. Les
    personnes encore inscrites sont écartées d'office.
    """
    if not payload.confirmation:
        raise HTTPException(
            400,
            "Confirmation requise : relis le plan puis renvoie "
            "`confirmation: true`.",
        )

    client, r = _plan_vidange(
        session, payload.ou, payload.annee_depart,
        payload.ou_archivage, payload.suspendre,
    )
    if not r.mouvements:
        raise HTTPException(400, "Aucun compte à archiver dans cette OU.")

    # Google refuse un déplacement vers une OU qu'il ne connaît pas, et le
    # refuse compte par compte : sans ce contrôle, les 437 opérations
    # échouent l'une après l'autre pour une seule cause, invisible.
    try:
        existantes = set(client.lister_ou())
    except Exception as e:
        raise HTTPException(502, f"Lecture Google impossible : {type(e).__name__}: {e}")

    destinations = sorted({m.ou_visee for m in r.mouvements})
    absentes = [d for d in destinations if d not in existantes]
    if absentes and not payload.creer_destination:
        raise HTTPException(
            400,
            "Destination absente de Google : "
            + ", ".join(absentes)
            + ". Crée-la dans la console, choisis-en une autre, ou relance "
            "en laissant le programme la créer.",
        )
    for chemin in absentes:
        try:
            client.creer_ou(chemin)
        except Exception as e:
            raise HTTPException(
                502,
                f"Création de {chemin} impossible : {type(e).__name__}: {e}. "
                "Rien n'a été déplacé.",
            )

    from backend.services.jobs_google import creer_job, lancer_en_tache_de_fond

    # Indexés par personne : le report au référentiel doit retrouver
    # l'échéance de chacun à partir des couples que le job lui rend.
    par_personne = {m.personne_id: m for m in r.mouvements if m.personne_id}

    def _reporter(appliquees: list[tuple[int, str]]) -> None:
        """Note au référentiel les sorties effectivement appliquées.

        Sans cela, 437 comptes changeraient d'OU sans laisser de trace :
        l'écran des sortants resterait vide et la liste des personnes à
        prévenir avant suppression n'existerait pas.
        """
        from backend.database import _SessionLocal
        from backend.services.suivi import enregistrer_sortie

        session_job = _SessionLocal()
        try:
            for personne_id, ou_visee in appliquees:
                mouvement = par_personne.get(personne_id)
                if mouvement is None or mouvement.date_echeance is None:
                    continue
                enregistrer_sortie(
                    session_job,
                    personne_id,
                    echeance=mouvement.date_echeance,
                    ou_visee=ou_visee,
                    prevenance=r.date_prevenance,
                )
            session_job.commit()
        finally:
            session_job.close()

    operations = [
        OperationGoogle(
            action="suspendre",  # nom historique : le déplacement passe par users.update
            email=m.email,
            payload={
                **(payload_suspension() if m.suspendre else {}),
                **payload_deplacement_ou(org_unit_path=m.ou_visee),
            },
            libelle=(
                f"{'Suspendre et déplacer' if m.suspendre else 'Déplacer'} "
                f"{m.email} vers {m.ou_visee}"
            ),
            personne_id=m.personne_id,
            ou_visee=m.ou_visee,
        )
        for m in r.mouvements
    ]
    job = creer_job(
        phase="vidange",
        libelle=f"Sortie de {r.ou_source} — {len(operations)} compte(s)",
        operations=operations,
    )
    lancer_en_tache_de_fond(
        job, operations,
        appliquer=client.appliquer_operation,
        au_succes=_reporter,
    )
    return _job_vers_out(job)


class DestinationSortieOut(BaseModel):
    chemin: str
    nb_occupants: int
    date_prevenance: str | None
    date_suppression: str | None
    etat: str
    """`a_venir`, `lettre_due`, `suppression_due`, ou `sans_date`."""
    existe: bool = True
    suggeree: bool = False
    """Celle que la règle du 31 décembre désigne pour la branche demandée."""


class DestinationsSortieOut(BaseModel):
    racine: str
    destinations: list[DestinationSortieOut]
    avertissements: list[str] = []


@router.get("/sortie/destinations", response_model=DestinationsSortieOut)
def destinations_sortie(
    pour_ou: str | None = Query(
        None, description="Branche à vider, pour suggérer sa destination"
    ),
    session: Session = Depends(db_session),
) -> DestinationsSortieOut:
    """Les OU de sortie existantes, avec leurs échéances et leur état.

    Lecture seule. Sert la liste déroulante de l'écran : saisir un chemin
    à la main expose à le taper de travers, et Google refuse alors chaque
    déplacement l'un après l'autre sans que rien ne l'ait annoncé.
    """
    from backend.services.configuration import get_param
    from backend.services.suivi import date_echeance
    from backend.services.vidange_ou import (
        DELAI_APRES_PREVENANCE_MOIS,
        RACINE_SORTIE_DEFAUT,
        annee_depuis_ou,
        date_prevenance,
        ou_sortie_pour,
    )

    racine = (
        get_param(session, "google.ou_sortants") or RACINE_SORTIE_DEFAUT
    ).rstrip("/")

    config = charger_config(session)
    try:
        client = ClientGoogle(config)
    except ValueError as e:
        raise HTTPException(400, str(e)) from None
    try:
        toutes = client.lister_ou()
        comptes = client.lister_utilisateurs(prefixe_ou=racine)
    except Exception as e:
        raise HTTPException(502, f"Lecture Google impossible : {type(e).__name__}: {e}")

    aujourd_hui = date.today()
    chemins = sorted(o for o in toutes if o == racine or o.startswith(racine + "/"))

    suggeree = None
    avertissements: list[str] = []
    if pour_ou:
        annee = annee_depuis_ou(pour_ou)
        if annee:
            suggeree = ou_sortie_pour(annee, racine)
            if suggeree not in chemins:
                chemins.append(suggeree)
                avertissements.append(
                    f"{suggeree} n'existe pas encore dans Google. Elle sera "
                    "créée au lancement — sans elle, chaque déplacement "
                    "échouerait l'un après l'autre."
                )

    sorties = []
    for chemin in sorted(set(chemins)):
        prevenance = date_prevenance(chemin)
        suppression = (
            date_echeance(prevenance, mois=DELAI_APRES_PREVENANCE_MOIS)
            if prevenance
            else None
        )
        if suppression and suppression <= aujourd_hui:
            etat = "suppression_due"
        elif prevenance and prevenance <= aujourd_hui:
            etat = "lettre_due"
        elif prevenance:
            etat = "a_venir"
        else:
            etat = "sans_date"
        sorties.append(
            DestinationSortieOut(
                chemin=chemin,
                nb_occupants=sum(1 for c in comptes if (c.get("ou") or "") == chemin),
                date_prevenance=prevenance.isoformat() if prevenance else None,
                date_suppression=suppression.isoformat() if suppression else None,
                etat=etat,
                existe=chemin in toutes,
                suggeree=(chemin == suggeree),
            )
        )
    return DestinationsSortieOut(
        racine=racine, destinations=sorties, avertissements=avertissements
    )


class OccupantSortieOut(BaseModel):
    email: str
    nom: str
    prenom: str
    ou: str
    suspendu: bool
    derniere_connexion: str | None


class OccupantsSortieOut(BaseModel):
    ou: str
    nb: int
    date_prevenance: str | None
    date_suppression: str | None
    nb_suspendus: int
    occupants: list[OccupantSortieOut]


@router.get("/sortie/occupants", response_model=OccupantsSortieOut)
def occupants_sortie(
    ou: str = Query(..., min_length=1),
    session: Session = Depends(db_session),
) -> OccupantsSortieOut:
    """Qui se trouve dans une OU de sortie, et sous quelle échéance.

    Lecture seule, et lue **dans Google** — pas dans le référentiel. La
    plupart de ces personnes sont parties avant les exports chargés :
    l'application ne les connaît pas, alors que l'OU, elle, sait
    exactement qui elle contient. C'est cette liste qui sert à prévenir
    les intéressés avant la suppression.
    """
    from backend.services.suivi import date_echeance
    from backend.services.vidange_ou import (
        DELAI_APRES_PREVENANCE_MOIS,
        date_prevenance,
    )

    config = charger_config(session)
    try:
        client = ClientGoogle(config)
    except ValueError as e:
        raise HTTPException(400, str(e)) from None
    try:
        comptes = client.lister_utilisateurs(prefixe_ou=ou)
    except Exception as e:
        raise HTTPException(502, f"Lecture Google impossible : {type(e).__name__}: {e}")

    prevenance = date_prevenance(ou)
    suppression = (
        date_echeance(prevenance, mois=DELAI_APRES_PREVENANCE_MOIS)
        if prevenance
        else None
    )
    return OccupantsSortieOut(
        ou=ou,
        nb=len(comptes),
        date_prevenance=prevenance.isoformat() if prevenance else None,
        date_suppression=suppression.isoformat() if suppression else None,
        nb_suspendus=sum(1 for c in comptes if c.get("suspendu")),
        occupants=[
            OccupantSortieOut(
                email=c.get("email") or "",
                nom=c.get("nom") or "",
                prenom=c.get("prenom") or "",
                ou=c.get("ou") or "",
                suspendu=bool(c.get("suspendu")),
                derniere_connexion=c.get("derniere_connexion"),
            )
            for c in sorted(comptes, key=lambda x: (x.get("nom") or "", x.get("prenom") or ""))
        ],
    )


# ---------------------------------------------------------------------------
# Flotte Chromebook
# ---------------------------------------------------------------------------


class AppareilOut(BaseModel):
    recupere_le: str | None = None
    attribue_a: str | None = None
    dort: bool = False
    a_recuperer: bool = False
    libre: bool = False
    serie: str
    modele: str
    ou: str
    statut: str
    etiquette: str
    porteur: str | None
    emplacement: str
    derniers_utilisateurs: list[str]
    derniere_synchro: str | None


class ProfAvecAppareilsOut(BaseModel):
    nom: str
    prenom: str
    discipline: str
    code: str
    email: str | None
    appareils: list[AppareilOut]
    attribue: str | None = None
    methode: str = "exact"
    approximatif: bool = False
    homonymes: list[str] = []
    raison: str = ""


class DiscordanceOut(BaseModel):
    appareil: AppareilOut
    attendu: str
    constates: list[str]


class ParcOut(BaseModel):
    total: int
    actifs: int
    desactives: int
    dormants: int
    jamais_vus: int
    par_modele: list[tuple[str, int]]
    par_ou: list[tuple[str, int]]


class FlotteOut(BaseModel):
    parc: ParcOut | None = None
    nb_appareils: int
    nb_profs: int
    nb_a_recuperer: int
    a_recuperer: list[ProfAvecAppareilsOut]
    a_attribuer: list[ProfAvecAppareilsOut]
    disponibles: list[AppareilOut]
    discordances: list[DiscordanceOut]
    sans_compte: list[ProfAvecAppareilsOut]
    rapproches: list[ProfAvecAppareilsOut]
    etiquettes_a_mettre_a_jour: list[AppareilOut]
    recuperees: list[AppareilOut]
    dormantes: list[AppareilOut]
    tous: list[AppareilOut]
    """Toute la flotte, pour la recherche par numéro depuis l'écran."""
    legende: list[dict]
    nb_par_code: dict[str, int]
    avertissements: list[str]
    tableau_importe_le: str | None = None
    """Quand le tableau des professeurs a été chargé. `None` s'il ne l'a
    jamais été — l'écran sait alors qu'il doit le réclamer."""


def _appareil_out(a) -> AppareilOut:
    return AppareilOut(
        serie=a.serie, modele=a.modele, ou=a.ou, statut=a.statut,
        etiquette=a.etiquette, porteur=a.porteur, emplacement=a.emplacement,
        derniers_utilisateurs=a.derniers_utilisateurs,
        derniere_synchro=a.derniere_synchro,
        recupere_le=a.recupere_le, attribue_a=a.attribue_a, dort=a.dort,
        a_recuperer=a.a_recuperer, libre=a.libre,
    )


def _prof_out(p) -> ProfAvecAppareilsOut:
    return ProfAvecAppareilsOut(
        nom=p.nom, prenom=p.prenom, discipline=p.discipline, code=p.code,
        email=p.email, appareils=[_appareil_out(a) for a in p.appareils],
        attribue=p.attribue, methode=p.methode,
        approximatif=p.approximatif, homonymes=p.homonymes, raison=p.raison,
    )


def _annee_courante(session) -> int:
    """L'année scolaire la plus récente — celle qu'on prépare."""
    from backend.models import AnneeScolaire

    annee = (
        session.query(AnneeScolaire).order_by(AnneeScolaire.libelle.desc()).first()
    )
    if annee is None:
        raise HTTPException(
            400,
            "Aucune année scolaire n'est chargée : ingère d'abord un export "
            "Charlemagne.",
        )
    return annee.id


@router.get("/chromebooks", response_model=FlotteOut)
def flotte_enregistree(session: Session = Depends(db_session)) -> FlotteOut:
    """La flotte croisée au tableau **déjà conservé**, sans rien redemander.

    Un import charge des données ; il ne les emprunte pas le temps d'un
    affichage. Tant qu'un tableau a été chargé pour l'année en cours,
    l'écran s'ouvre sans réclamer le classeur.
    """
    from backend.services.import_profs import date_import, lire_enregistres

    annee_id = _annee_courante(session)
    profs = lire_enregistres(session, annee_id=annee_id)
    if not profs:
        raise HTTPException(
            404,
            "Aucun tableau des professeurs n'a été chargé pour cette année. "
            "Dépose le classeur une fois : il sera conservé ensuite.",
        )
    return _croiser(session, profs, [], date_import(session, annee_id=annee_id))


@router.post("/chromebooks", response_model=FlotteOut)
async def analyser_chromebooks(
    fichier: UploadFile = File(..., description="Tableau des professeurs (.xlsx)"),
    session: Session = Depends(db_session),
) -> FlotteOut:
    """Charge le tableau des enseignants, le conserve, et croise la flotte.

    Aucune écriture dans Google : le droit demandé est en lecture seule, et
    réattribuer une machine reste un geste physique. Le classeur, lui, est
    lu puis effacé — ce sont les lignes qu'il contient qui sont gardées.
    """
    from pathlib import Path
    from tempfile import NamedTemporaryFile

    from backend.services.import_profs import (
        date_import,
        enregistrer,
        lire_fichier_profs,
    )

    # La connexion à Google est vérifiée par `_croiser`, plus bas : la
    # construire ici aussi demanderait un second jeton pour rien.
    contenu = await fichier.read()
    with NamedTemporaryFile(suffix=".xlsx", delete=False) as tmp:
        tmp.write(contenu)
        chemin = Path(tmp.name)
    try:
        rapport_profs = lire_fichier_profs(chemin)
    except ValueError as e:
        raise HTTPException(400, str(e)) from None
    finally:
        chemin.unlink(missing_ok=True)

    annee_id = _annee_courante(session)
    enregistrer(session, rapport_profs, annee_id=annee_id)
    return _croiser(
        session, rapport_profs.profs, rapport_profs.legende,
        date_import(session, annee_id=annee_id),
    )


def _croiser(session, profs, legende, importe_le) -> FlotteOut:
    """Confronte le tableau des enseignants à la flotte et aux comptes."""
    from backend.services.chromebooks import analyser_flotte

    config = charger_config(session)
    try:
        client = ClientGoogle(config)
    except ValueError as e:
        raise HTTPException(400, str(e)) from None
    if not client.appareils_disponibles:
        raise HTTPException(
            400,
            "Le droit de lecture des Chromebooks n'est pas accordé au compte "
            "de service. Ajoute le champ d'application "
            "admin.directory.device.chromeos.readonly à la délégation, dans "
            "la console d'administration.",
        )
    try:
        appareils = client.lister_appareils()
        comptes = client.lister_utilisateurs()
    except Exception as e:
        raise HTTPException(502, f"Lecture Google impossible : {type(e).__name__}: {e}")

    from backend.models import SuiviChromebook

    suivi = {
        x.serie: {
            "recupere_le": x.recupere_le.isoformat() if x.recupere_le else None,
            "attribue_a": x.attribue_a,
            "recupere_de": x.recupere_de,
        }
        for x in session.query(SuiviChromebook).all()
    }
    r = analyser_flotte(appareils, profs, comptes, suivi=suivi)
    return FlotteOut(
        nb_appareils=len(r.appareils),
        nb_profs=len(r.profs),
        nb_a_recuperer=r.nb_a_recuperer,
        a_recuperer=[_prof_out(p) for p in r.a_recuperer],
        a_attribuer=[_prof_out(p) for p in r.a_attribuer],
        disponibles=[_appareil_out(a) for a in r.disponibles],
        sans_compte=[_prof_out(p) for p in r.sans_compte],
        rapproches=[_prof_out(p) for p in r.rapproches],
        etiquettes_a_mettre_a_jour=[
            _appareil_out(a) for a in r.etiquettes_a_mettre_a_jour
        ],
        recuperees=[_appareil_out(a) for a in r.recuperees],
        dormantes=[_appareil_out(a) for a in r.dormantes],
        # Tout le parc, et non les seuls appareils du personnel : la vue
        # « Parc » sert justement à voir ce que les listes d'action cachent.
        tous=[_appareil_out(a) for a in r.appareils],
        parc=ParcOut(**vars(r.parc)),
        discordances=[
            DiscordanceOut(
                appareil=_appareil_out(d.appareil),
                attendu=d.attendu,
                constates=d.constates,
            )
            for d in r.discordances
        ],
        legende=[vars(e) for e in legende],
        nb_par_code={
            code: sum(1 for p in profs if p.code == code)
            for code in sorted({p.code for p in profs})
        },
        avertissements=r.avertissements,
        tableau_importe_le=importe_le.isoformat() if importe_le else None,
    )


class SuiviAppareilPayload(BaseModel):
    serie: str
    recupere: bool | None = None
    """Vrai note la restitution, faux l'annule."""
    recupere_de: str | None = None
    attribue_a: str | None = None
    """Adresse du nouveau porteur. Chaîne vide pour annuler l'attribution."""
    note: str | None = None


class SuiviAppareilOut(BaseModel):
    serie: str
    recupere_le: str | None
    recupere_de: str | None
    attribue_a: str | None
    attribue_le: str | None
    note: str | None


@router.post("/chromebooks/suivi", response_model=SuiviAppareilOut)
def noter_suivi_appareil(
    payload: SuiviAppareilPayload, session: Session = Depends(db_session)
) -> SuiviAppareilOut:
    """Note ce qui a été fait d'une machine — rendue, ou confiée à quelqu'un.

    Google ignore ces deux gestes : ils sont physiques et précèdent de
    plusieurs jours la mise à jour de l'étiquette. Sans cette trace, la
    liste des machines à réclamer resterait identique du premier au dernier
    jour de la rentrée.

    Rien n'est envoyé à Google : le droit accordé est en lecture seule.
    """
    from backend.models import SuiviChromebook

    serie = (payload.serie or "").strip()
    if not serie:
        raise HTTPException(400, "Numéro de série manquant.")

    ligne = (
        session.query(SuiviChromebook).filter_by(serie=serie).one_or_none()
    )
    if ligne is None:
        ligne = SuiviChromebook(serie=serie)
        session.add(ligne)

    if payload.recupere is not None:
        ligne.recupere_le = date.today() if payload.recupere else None
        ligne.recupere_de = payload.recupere_de if payload.recupere else None
        if payload.recupere:
            # Une machine rendue redevient libre : elle n'est plus confiée.
            ligne.attribue_a = None
            ligne.attribue_le = None

    if payload.attribue_a is not None:
        adresse = payload.attribue_a.strip().lower()
        ligne.attribue_a = adresse or None
        ligne.attribue_le = date.today() if adresse else None

    if payload.note is not None:
        ligne.note = payload.note.strip() or None

    session.commit()
    return SuiviAppareilOut(
        serie=ligne.serie,
        recupere_le=ligne.recupere_le.isoformat() if ligne.recupere_le else None,
        recupere_de=ligne.recupere_de,
        attribue_a=ligne.attribue_a,
        attribue_le=ligne.attribue_le.isoformat() if ligne.attribue_le else None,
        note=ligne.note,
    )


# ---------------------------------------------------------------------------
# Conformité de l'arborescence
# ---------------------------------------------------------------------------


class RenommageOut(BaseModel):
    ancien: str
    nouveau: str
    nb_sous_ou: int
    utile: bool = True


class ConformiteOUOut(BaseModel):
    nb_attendues: int
    nb_existantes: int
    nb_a_creer: int
    nb_deja_conformes: int
    est_conforme: bool
    annees_table: list[str] = []
    renommages: list[RenommageOut]
    a_creer: list[str]
    avertissements: list[str]


def _analyser_ou(session: Session, annee_source, annee_cible, renommer):
    from backend.services.ou_google import analyser_conformite

    config = charger_config(session)
    try:
        client = ClientGoogle(config)
    except ValueError as e:
        raise HTTPException(400, str(e)) from None
    try:
        existantes = client.lister_ou()
    except Exception as e:
        raise HTTPException(502, f"Lecture Google impossible : {type(e).__name__}: {e}")
    return client, analyser_conformite(
        session, existantes,
        annee_source=annee_source, annee_cible=annee_cible,
        autoriser_renommage=renommer,
    )


@router.get("/ou/conformite", response_model=ConformiteOUOut)
def conformite_ou(
    annee_source: str | None = Query(None, description="Année à recycler, ex. 2025"),
    annee_cible: str | None = Query(None, description="Année visée, ex. 2027"),
    renommer: bool = Query(True, description="Proposer le renommage des arbres"),
    session: Session = Depends(db_session),
) -> ConformiteOUOut:
    """Écart entre l'arborescence réelle et ce que vise la Table.

    Lecture seule. Sans ce contrôle, un déplacement vers une OU absente
    échoue élève par élève sans que rien ne l'ait annoncé.
    """
    _, r = _analyser_ou(session, annee_source, annee_cible, renommer)
    return ConformiteOUOut(
        nb_attendues=len(r.ou_attendues),
        nb_existantes=len(r.ou_existantes),
        nb_a_creer=r.nb_a_creer,
        nb_deja_conformes=len(r.deja_conformes),
        est_conforme=r.est_conforme,
        annees_table=r.annees_table,
        renommages=[RenommageOut(**vars(x)) for x in r.renommages],
        a_creer=r.a_creer,
        avertissements=r.avertissements,
    )


class AppliquerOUPayload(BaseModel):
    annee_source: str | None = None
    annee_cible: str | None = None
    renommer: bool = True
    confirmation: bool = False


@router.post("/ou/appliquer", response_model=JobOut)
def appliquer_conformite_ou(
    payload: AppliquerOUPayload, session: Session = Depends(db_session)
) -> JobOut:
    """Renomme puis crée les OU, dans cet ordre.

    Le renommage d'abord : il rend disponibles des dizaines de chemins que
    l'on n'aura donc pas à créer. Les créations suivent l'ordre
    parent-avant-enfant, exigé par Google.

    Aucune suppression : une OU devenue inutile peut encore contenir des
    comptes, et l'effacer les renverrait à la racine sans prévenir.
    """
    if not payload.confirmation:
        raise HTTPException(400, "Confirmation requise.")

    client, r = _analyser_ou(
        session, payload.annee_source, payload.annee_cible, payload.renommer
    )
    if r.est_conforme:
        raise HTTPException(400, "L'arborescence est déjà conforme à la Table.")

    from backend.services.jobs_google import creer_job, lancer_en_tache_de_fond

    class _Etape:
        def __init__(self, action, cible, libelle, extra=None):
            self.action = action
            self.email = cible  # le suivi affiche ce champ
            self.libelle = libelle
            self.personne_id = None
            self.ou_visee = None
            self.extra = extra

    etapes = [
        _Etape("renommer", x.ancien,
               f"Renommer {x.ancien} en {x.nouveau} ({x.nb_sous_ou} classes)",
               x.nouveau.rsplit("/", 1)[-1])
        for x in r.renommages
    ] + [
        _Etape("creer_ou", chemin, f"Créer {chemin}") for chemin in r.a_creer
    ]

    job = creer_job(
        phase="arborescence",
        libelle=f"Arborescence : {len(r.renommages)} renommage(s), {r.nb_a_creer} création(s)",
        operations=etapes,
    )

    def appliquer(etape) -> None:
        if etape.action == "renommer":
            client.renommer_ou(etape.email, etape.extra)
        else:
            client.creer_ou(etape.email)

    lancer_en_tache_de_fond(job, etapes, appliquer=appliquer)
    return _job_vers_out(job)


# ---------------------------------------------------------------------------
# Adresses divergentes
# ---------------------------------------------------------------------------


class DivergenceOut(BaseModel):
    personne_id: int
    cle_pivot: str
    nom: str
    prenom: str
    adresse_enregistree: str
    adresse_google: str | None
    ou_google: str | None
    resolvable: bool
    motif: str


class DivergencesOut(BaseModel):
    nb_examines: int
    nb_resolvables: int
    nb_ambigus: int
    divergences: list[DivergenceOut]


def _detecter_divergences(session: Session, annee_id):
    from backend.services.adresses_divergentes import detecter_divergences

    config = charger_config(session)
    try:
        client = ClientGoogle(config)
    except ValueError as e:
        raise HTTPException(400, str(e)) from None
    try:
        comptes = client.lister_utilisateurs()
    except Exception as e:
        raise HTTPException(502, f"Lecture Google impossible : {type(e).__name__}: {e}")
    return detecter_divergences(session, comptes, annee_id=annee_id)


@router.get("/adresses/divergences", response_model=DivergencesOut)
def divergences_adresses(
    annee_id: int | None = Query(None), session: Session = Depends(db_session)
) -> DivergencesOut:
    """Personnes dont l'adresse enregistrée n'existe pas dans Google.

    Ces écarts font échouer les déplacements un par un et poussent l'export
    des nouveaux à créer un doublon. Lecture seule.
    """
    r = _detecter_divergences(session, annee_id)
    return DivergencesOut(
        nb_examines=r.nb_examines,
        nb_resolvables=r.nb_resolvables,
        nb_ambigus=r.nb_ambigus,
        divergences=[DivergenceOut(**vars(d)) for d in r.divergences],
    )


class CorrigerPayload(BaseModel):
    annee_id: int | None = None
    mode: str = "simulation"


class CorrectionOut(BaseModel):
    nb_corrigees: int
    mode: str


@router.post("/adresses/corriger", response_model=CorrectionOut)
def corriger_adresses(
    payload: CorrigerPayload, session: Session = Depends(db_session)
) -> CorrectionOut:
    """Aligne les adresses enregistrées sur les comptes Google réels.

    Ne touche que les écarts sans ambiguïté. Ce que Google contient fait
    foi : c'est là que l'élève se connecte.
    """
    from backend.services.adresses_divergentes import appliquer_corrections

    if payload.mode not in ("simulation", "reel"):
        raise HTTPException(400, f"mode invalide : {payload.mode!r}")
    r = _detecter_divergences(session, payload.annee_id)
    n = appliquer_corrections(session, r, mode=payload.mode)
    return CorrectionOut(nb_corrigees=n, mode=payload.mode)


# ---------------------------------------------------------------------------
# Groupes de classe
# ---------------------------------------------------------------------------


class DiffGroupeOut(BaseModel):
    groupe: str
    classe: str
    site: str | None
    a_ajouter: list[str]
    a_retirer: list[str]
    inconnus: list[str]
    deja_membres: int
    existe: bool = True
    retenus: list[str] = []


class GroupesOut(BaseModel):
    annee_libelle: str
    nb_a_ajouter: int
    nb_a_retirer: int
    nb_inconnus: int
    nb_retenus: int = 0
    groupes_absents: list[str] = []
    sites_sans_eleve: list[str] = []
    classes_sans_groupe: list[str]
    avertissements: list[str]
    diffs: list[DiffGroupeOut]


def _diff_groupes(session: Session, annee_id: int, site_id):
    from backend.models import TableCorrespondance
    from backend.services.groupes_google import calculer_diff_groupes

    config = charger_config(session)
    try:
        client = ClientGoogle(config)
    except ValueError as e:
        raise HTTPException(400, str(e)) from None

    q = session.query(TableCorrespondance)
    if site_id is not None:
        q = q.filter(TableCorrespondance.site_id == site_id)
    adresses = {
        (tc.groupe_google or "").strip().lower()
        for tc in q.all()
        if (tc.groupe_google or "").strip()
    }

    membres: dict[str, list[str] | None] = {}
    for g in sorted(adresses):
        try:
            membres[g] = client.lister_membres(g)
        except Exception:
            # `None`, pas `[]` : un groupe que Google ne connaît pas ne se
            # remplit pas. Le confondre avec un groupe vide ferait planifier
            # des ajouts voués à échouer un par un.
            membres[g] = None
    try:
        return client, calculer_diff_groupes(
            session, membres, annee_id=annee_id, site_id=site_id
        )
    except ValueError as e:
        raise HTTPException(404, str(e)) from None


@router.get("/groupes/diff", response_model=GroupesOut)
def diff_groupes(
    annee_id: int = Query(...),
    site_id: int | None = Query(None),
    session: Session = Depends(db_session),
) -> GroupesOut:
    """Qui doit entrer et sortir de chaque groupe de classe. Lecture seule."""
    _, r = _diff_groupes(session, annee_id, site_id)
    return GroupesOut(
        annee_libelle=r.annee_libelle,
        nb_a_ajouter=r.nb_a_ajouter,
        nb_a_retirer=r.nb_a_retirer,
        nb_inconnus=r.nb_inconnus,
        nb_retenus=r.nb_retenus,
        groupes_absents=r.groupes_absents,
        sites_sans_eleve=r.sites_sans_eleve,
        classes_sans_groupe=r.classes_sans_groupe,
        avertissements=r.avertissements,
        diffs=[DiffGroupeOut(**vars(d)) for d in r.diffs],
    )


class SyncGroupesPayload(BaseModel):
    annee_id: int
    site_id: int | None = None
    retirer: bool = True
    """À faux, on n'ajoute que. Utile pour un premier passage prudent."""
    confirmation: bool = False


@router.post("/groupes/synchroniser", response_model=JobOut)
def synchroniser_groupes(
    payload: SyncGroupesPayload, session: Session = Depends(db_session)
) -> JobOut:
    """Applique les entrées et sorties de groupe.

    Les membres inconnus du référentiel ne sont jamais retirés : le
    programme ignore pourquoi ils sont là.
    """
    if not payload.confirmation:
        raise HTTPException(400, "Confirmation requise.")

    client, r = _diff_groupes(session, payload.annee_id, payload.site_id)

    class _Mvt:
        def __init__(self, action, groupe, email):
            self.action = action
            self.email = email
            self.groupe = groupe
            self.libelle = (
                f"{'Ajouter à' if action == 'ajouter' else 'Retirer de'} {groupe}"
            )
            self.personne_id = None
            self.ou_visee = None

    operations: list = []
    for d in r.diffs:
        operations += [_Mvt("ajouter", d.groupe, m) for m in d.a_ajouter]
        if payload.retirer:
            operations += [_Mvt("retirer", d.groupe, m) for m in d.a_retirer]

    if not operations:
        raise HTTPException(400, "Les groupes sont déjà à jour.")

    from backend.services.jobs_google import creer_job, lancer_en_tache_de_fond

    job = creer_job(
        phase="groupes",
        libelle=f"Groupes : {r.nb_a_ajouter} entrée(s), "
                f"{r.nb_a_retirer if payload.retirer else 0} sortie(s)",
        operations=operations,
    )

    def appliquer(m) -> None:
        if m.action == "ajouter":
            client.ajouter_membre(m.groupe, m.email)
        else:
            client.retirer_membre(m.groupe, m.email)

    lancer_en_tache_de_fond(job, operations, appliquer=appliquer)
    return _job_vers_out(job)


class GroupeACreerOut(BaseModel):
    adresse: str
    nom: str
    description: str
    classe: str
    site: str | None
    nb_membres_attendus: int


class CreationsGroupesOut(BaseModel):
    nb_a_creer: int
    nb_utiles: int
    """Groupes dont l'absence bloque effectivement des élèves aujourd'hui."""
    nb_membres_bloques: int
    groupes: list[GroupeACreerOut]


@router.get("/groupes/a-creer", response_model=CreationsGroupesOut)
def lister_groupes_a_creer(
    annee_id: int = Query(...),
    site_id: int | None = Query(None),
    session: Session = Depends(db_session),
) -> CreationsGroupesOut:
    """Les groupes déclarés dans la Table que Google ne connaît pas.

    Lecture seule. Tant qu'ils manquent, la composition de leurs classes ne
    peut pas être synchronisée : les ajouts échoueraient un par un.
    """
    from backend.services.groupes_google import groupes_a_creer

    _, r = _diff_groupes(session, annee_id, site_id)
    creations = groupes_a_creer(session, r)
    return CreationsGroupesOut(
        nb_a_creer=len(creations),
        nb_utiles=sum(1 for c in creations if c.nb_membres_attendus),
        nb_membres_bloques=r.nb_retenus,
        groupes=[GroupeACreerOut(**vars(c)) for c in creations],
    )


class CreerGroupesPayload(BaseModel):
    annee_id: int
    site_id: int | None = None
    adresses: list[str] | None = None
    """Restreint aux adresses citées. `None` = tous ceux qui manquent."""
    seulement_utiles: bool = False
    """À vrai, ne crée que les groupes qui débloquent des élèves. Une classe
    sans effectif cette année n'a pas besoin de sa liste tout de suite."""
    confirmation: bool = False


@router.post("/groupes/creer", response_model=JobOut)
def creer_groupes(
    payload: CreerGroupesPayload, session: Session = Depends(db_session)
) -> JobOut:
    """Crée les groupes manquants. Geste distinct de la synchronisation.

    Créer un groupe fait naître une adresse de messagerie ; ajouter un
    membre n'en crée aucune. Les deux ne méritent pas la même confirmation.
    Aucun groupe n'est jamais supprimé par le programme.
    """
    if not payload.confirmation:
        raise HTTPException(400, "Confirmation requise.")

    from backend.services.groupes_google import groupes_a_creer

    client, r = _diff_groupes(session, payload.annee_id, payload.site_id)
    creations = groupes_a_creer(session, r)
    if payload.seulement_utiles:
        creations = [c for c in creations if c.nb_membres_attendus]
    if payload.adresses is not None:
        voulues = {a.strip().lower() for a in payload.adresses}
        creations = [c for c in creations if c.adresse in voulues]
    if not creations:
        raise HTTPException(400, "Aucun groupe à créer.")

    class _Creation:
        def __init__(self, c):
            self.groupe = c.adresse
            self.email = c.adresse
            self.nom = c.nom
            self.description = c.description
            self.libelle = f"Créer {c.adresse} — {c.nom}"
            self.personne_id = None
            self.ou_visee = None

    operations = [_Creation(c) for c in creations]

    from backend.services.jobs_google import creer_job, lancer_en_tache_de_fond

    job = creer_job(
        phase="groupes",
        libelle=f"Création de {len(operations)} groupe(s)",
        operations=operations,
    )

    def appliquer(o) -> None:
        client.creer_groupe(o.groupe, o.nom, o.description)

    lancer_en_tache_de_fond(job, operations, appliquer=appliquer)
    return _job_vers_out(job)
