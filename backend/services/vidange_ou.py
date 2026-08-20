"""Vidange d'une branche d'OU : archiver les comptes qui y sont restés.

## Le besoin

Une arborescence d'année conserve la promotion qui l'a occupée. Tant que
personne ne l'a vidée, ses comptes restent actifs — sur l'instance
réelle, 444 élèves partis en juin 2025 pouvaient encore se connecter
quatorze mois plus tard, dans les OU de leurs classes de terminale.

Et l'arbre le plus ancien doit être recyclé à chaque rentrée : le
renommer sans l'avoir vidé mélangerait une promotion sortante aux
nouveaux élèves.

## L'échéance

Elle court depuis le **départ réel**, pas depuis aujourd'hui. Un compte
laissé trois ans a déjà purgé sa quarantaine ; lui accorder 18 mois de
plus à compter du traitement reviendrait à récompenser l'oubli.

L'année du départ se lit dans le nom de la branche — `NDK2025` désigne
l'année scolaire qui s'achève en 2025 — et la sortie est datée au 31
août, faute de mieux : Google ne conserve pas la date de désinscription.

## Le garde-fou

Un compte dont la personne est **encore inscrite** n'est jamais touché,
quelle que soit l'OU où il se trouve. C'est le cas d'un élève replacé à
la main, ou d'un redoublant resté dans l'arbre précédent : le suspendre
le priverait de son compte le jour de la rentrée.

Rien n'est envoyé ici : ce module construit un plan, l'exécution est un
geste distinct et confirmé.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from datetime import date

from sqlalchemy.orm import Session

from backend.models import Site
from backend.services.inspection_ou import (
    ENCORE_INSCRIT,
    CompteTrouve,
    recouper_avec_referentiel,
)


@dataclass
class MouvementVidange:
    email: str
    ou_actuelle: str
    ou_visee: str
    suspendre: bool
    nom: str
    prenom: str
    statut_referentiel: str
    personne_id: int | None = None


@dataclass
class RapportVidange:
    ou_source: str
    ou_archivage: str
    date_depart: date
    date_echeance: date

    nb_trouves: int = 0
    nb_a_archiver: int = 0
    nb_deja_suspendus: int = 0
    mouvements: list[MouvementVidange] = field(default_factory=list)
    epargnes: list[CompteTrouve] = field(default_factory=list)
    """Comptes laissés en place parce que la personne est encore inscrite."""

    avertissements: list[str] = field(default_factory=list)


def annee_depuis_ou(chemin: str) -> int | None:
    """Année de fin d'année scolaire lue dans le nom d'une branche.

    `/3. NDK/NDK2025` → 2025, soit l'année scolaire 2024-2025.
    """
    annees = re.findall(r"20\d\d", chemin or "")
    return int(annees[-1]) if annees else None


def planifier_vidange(
    session: Session,
    comptes_google: list[dict],
    *,
    ou_source: str,
    annee_depart: int | None = None,
    aujourd_hui: date | None = None,
) -> RapportVidange:
    """Construit le plan d'archivage des comptes d'une branche.

    Args:
        comptes_google: retour de `ClientGoogle.lister_utilisateurs`.
        ou_source: branche à vider, ex. `/3. NDK/NDK2025`.
        annee_depart: année de fin de scolarité. Déduite du nom de la
            branche si absente.

    Raises:
        ValueError: si l'année de départ ne peut être ni lue ni déduite.
    """
    from backend.services.exports_google import calculer_ou_sortants
    from backend.services.suivi import date_echeance

    annee = annee_depart or annee_depuis_ou(ou_source)
    if annee is None:
        raise ValueError(
            f"Impossible de déduire l'année de départ de {ou_source!r} — "
            "précise-la explicitement."
        )

    depart = date(annee, 8, 31)
    echeance = date_echeance(depart)

    # Le site se reconnaît au préfixe de la branche : il porte parfois sa
    # propre convention d'archivage.
    site = None
    for s in session.query(Site).all():
        if s.prefixe_annee_ou and s.prefixe_annee_ou in ou_source:
            site = s
            break

    if site is not None and (site.ou_sortants or "").strip():
        ou_archivage = site.ou_sortants.strip().rstrip("/")
    else:
        from backend.services.configuration import get_param

        racine = (get_param(session, "google.ou_sortants") or "/7. Sortis").rstrip("/")
        ou_archivage = f"{racine}/Comptes à supprimer au {echeance.strftime('%d-%m-%Y')}"

    inspection = recouper_avec_referentiel(session, comptes_google, prefixe_ou=ou_source)
    rapport = RapportVidange(
        ou_source=ou_source,
        ou_archivage=ou_archivage,
        date_depart=depart,
        date_echeance=echeance,
        nb_trouves=inspection.nb_total,
    )

    for c in inspection.comptes:
        if c.statut == ENCORE_INSCRIT:
            rapport.epargnes.append(c)
            continue
        if c.suspendu:
            rapport.nb_deja_suspendus += 1
        rapport.mouvements.append(
            MouvementVidange(
                email=c.email,
                ou_actuelle=c.ou,
                ou_visee=ou_archivage,
                suspendre=not c.suspendu,
                nom=c.nom or c.nom_google,
                prenom=c.prenom or c.prenom_google,
                statut_referentiel=c.statut,
                personne_id=None,
            )
        )

    rapport.nb_a_archiver = len(rapport.mouvements)

    if rapport.epargnes:
        rapport.avertissements.append(
            f"{len(rapport.epargnes)} compte(s) laissé(s) en place : la personne "
            "figure dans l'année en cours. Les suspendre la priverait de son "
            "compte le jour de la rentrée."
        )
    if echeance <= (aujourd_hui or date.today()):
        rapport.avertissements.append(
            f"L'échéance calculée ({echeance.strftime('%d/%m/%Y')}) est déjà "
            "dépassée : ces comptes sont supprimables dès leur archivage."
        )
    return rapport
