"""Exécution suivie des opérations Google, étape par étape.

## Pourquoi un job plutôt qu'un appel

Déplacer un millier d'élèves demande un appel HTTP par personne, soit
plusieurs minutes. Une requête unique qui rend la main à la fin laisse
l'utilisateur devant un écran figé, sans savoir où ça en est ni ce qui a
échoué — et un échec au 800e ne dit rien des 799 précédents.

Le traitement tourne donc en tâche de fond et publie son avancement :
l'interface interroge l'état et affiche chaque ligne au fur et à mesure,
avec sa réussite ou son message d'erreur.

## Reprise

Un échec n'interrompt pas le reste. Les opérations en échec restent
identifiables pour être rejouées seules, sans repasser sur ce qui a
déjà abouti — c'est le propre d'un traitement partiellement appliqué :
on ne recommence pas, on complète.

## Portée

Les jobs vivent en mémoire du processus. Un redémarrage du backend les
perd — acceptable : ce sont des traces d'exécution, pas des données. Ce
qui compte est persisté au fil de l'eau (`CompteCible.ou_appliquee`).
"""
from __future__ import annotations

import threading
import uuid
from dataclasses import dataclass, field
from datetime import datetime
from typing import Callable

STATUTS_ETAPE = ("attente", "en_cours", "reussi", "echec")


@dataclass
class EtapeJob:
    """Une opération unitaire et son issue."""

    index: int
    action: str
    email: str
    libelle: str
    personne_id: int | None = None
    ou_visee: str | None = None

    statut: str = "attente"
    message: str | None = None
    """Message d'erreur de Google, tel quel — c'est lui qui permet de
    comprendre un refus (quota, compte inexistant, OU absente…)."""


@dataclass
class JobGoogle:
    id: str
    phase: str
    libelle: str
    total: int

    etapes: list[EtapeJob] = field(default_factory=list)
    demarre_le: datetime = field(default_factory=datetime.utcnow)
    termine_le: datetime | None = None
    annule: bool = False
    erreur_fatale: str | None = None

    @property
    def nb_reussies(self) -> int:
        return sum(1 for e in self.etapes if e.statut == "reussi")

    @property
    def nb_echecs(self) -> int:
        return sum(1 for e in self.etapes if e.statut == "echec")

    @property
    def nb_traitees(self) -> int:
        return self.nb_reussies + self.nb_echecs

    @property
    def est_termine(self) -> bool:
        return self.termine_le is not None

    @property
    def progression(self) -> float:
        return self.nb_traitees / self.total if self.total else 1.0


# Registre en mémoire — un seul processus backend.
_JOBS: dict[str, JobGoogle] = {}
_OPERATIONS: dict[str, list] = {}
"""Opérations d'origine, conservées à part : elles portent les payloads
Google, qu'on ne veut ni sérialiser vers l'interface ni journaliser. Elles
servent à rejouer les échecs sans recalculer le plan."""
_VERROU = threading.Lock()


def creer_job(*, phase: str, libelle: str, operations) -> JobGoogle:
    """Enregistre un job à l'état initial, sans rien exécuter."""
    job = JobGoogle(
        id=uuid.uuid4().hex[:12],
        phase=phase,
        libelle=libelle,
        total=len(operations),
        etapes=[
            EtapeJob(
                index=i,
                action=o.action,
                email=o.email,
                libelle=o.libelle,
                personne_id=getattr(o, "personne_id", None),
                ou_visee=getattr(o, "ou_visee", None),
            )
            for i, o in enumerate(operations)
        ],
    )
    with _VERROU:
        _JOBS[job.id] = job
        _OPERATIONS[job.id] = list(operations)
    return job


def operations_du_job(job_id: str) -> list:
    with _VERROU:
        return list(_OPERATIONS.get(job_id, []))


def operations_en_echec(job_id: str) -> list:
    """Les seules opérations à rejouer — ce qui a abouti n'est pas refait."""
    job = obtenir_job(job_id)
    ops = operations_du_job(job_id)
    if job is None or not ops:
        return []
    return [ops[e.index] for e in job.etapes if e.statut == "echec" and e.index < len(ops)]


def obtenir_job(job_id: str) -> JobGoogle | None:
    with _VERROU:
        return _JOBS.get(job_id)


def lister_jobs(limite: int = 20) -> list[JobGoogle]:
    with _VERROU:
        jobs = sorted(_JOBS.values(), key=lambda j: j.demarre_le, reverse=True)
    return jobs[:limite]


def demander_annulation(job_id: str) -> bool:
    """Arrête le job après l'étape en cours.

    On ne coupe pas au milieu d'un appel : une opération est envoyée ou
    ne l'est pas, jamais à moitié.
    """
    job = obtenir_job(job_id)
    if job is None or job.est_termine:
        return False
    job.annule = True
    return True


def purger_jobs_termines(garder: int = 10) -> int:
    """Limite le registre aux N derniers jobs terminés."""
    with _VERROU:
        termines = sorted(
            (j for j in _JOBS.values() if j.est_termine),
            key=lambda j: j.termine_le or j.demarre_le,
            reverse=True,
        )
        a_retirer = termines[garder:]
        for j in a_retirer:
            _JOBS.pop(j.id, None)
            _OPERATIONS.pop(j.id, None)
    return len(a_retirer)


def executer_job(
    job: JobGoogle,
    operations,
    appliquer: Callable[[object], None],
    *,
    au_succes: Callable[[list[tuple[int, str]]], None] | None = None,
) -> None:
    """Déroule les opérations, une par une, en publiant l'avancement.

    Args:
        appliquer: envoie une opération à Google. Lève en cas d'échec.
        au_succes: reçoit les couples `(personne_id, ou)` réellement
            appliqués, pour les mémoriser. Appelé une fois à la fin plutôt
            qu'à chaque étape : une écriture par élève ferait un millier de
            transactions pour rien.

    Ne lève jamais : un échec est consigné dans l'étape concernée et le
    traitement continue. Une exception hors opération (perte de connexion,
    credentials invalidées) arrête le job et est reportée dans
    `erreur_fatale`.
    """
    appliquees: list[tuple[int, str]] = []
    try:
        for etape, operation in zip(job.etapes, operations):
            if job.annule:
                break
            etape.statut = "en_cours"
            try:
                appliquer(operation)
            except Exception as e:
                etape.statut = "echec"
                etape.message = f"{type(e).__name__}: {e}"
                continue
            etape.statut = "reussi"
            if etape.personne_id and etape.ou_visee:
                appliquees.append((etape.personne_id, etape.ou_visee))
    except Exception as e:  # pragma: no cover — dépend du réseau
        job.erreur_fatale = f"{type(e).__name__}: {e}"
    finally:
        if au_succes is not None and appliquees:
            try:
                au_succes(appliquees)
            except Exception as e:  # pragma: no cover
                job.erreur_fatale = (
                    f"Opérations appliquées mais non mémorisées : {type(e).__name__}: {e}"
                )
        job.termine_le = datetime.utcnow()


def lancer_en_tache_de_fond(
    job: JobGoogle,
    operations,
    appliquer: Callable[[object], None],
    *,
    au_succes: Callable[[list[tuple[int, str]]], None] | None = None,
) -> None:
    """Démarre `executer_job` dans un thread, sans attendre."""
    fil = threading.Thread(
        target=executer_job,
        args=(job, operations, appliquer),
        kwargs={"au_succes": au_succes},
        daemon=True,
        name=f"job-google-{job.id}",
    )
    fil.start()
