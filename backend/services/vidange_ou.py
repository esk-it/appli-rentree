"""Vidange d'une branche d'OU : archiver les comptes qui y sont restés.

## Le besoin

Une arborescence d'année conserve la promotion qui l'a occupée. Tant que
personne ne l'a vidée, ses comptes restent actifs — sur l'instance
réelle, 444 élèves partis en juin 2025 pouvaient encore se connecter
quatorze mois plus tard, dans les OU de leurs classes de terminale.

Et l'arbre le plus ancien doit être recyclé à chaque rentrée : le
renommer sans l'avoir vidé mélangerait une promotion sortante aux
nouveaux élèves.

## Déplacer, sans suspendre

Un compte de sortie **reste actif**. La quarantaine tient au fait d'être
sorti de l'arbre des classes, pas à la privation d'accès : l'élève parti
garde sa messagerie le temps de récupérer ce qui lui appartient, et
l'établissement le prévient avant la suppression. C'est ce que montre
l'instance — sur les 124 comptes déjà rangés dans les OU de sortie,
aucun n'est suspendu.

La suspension reste possible, mais elle se demande explicitement.

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
    date_echeance: date | None = None
    """Propre au compte : elle diffère de celle de la branche pour qui y a
    séjourné plus longtemps que son nom ne l'indique."""


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
    retardataires: list[CompteTrouve] = field(default_factory=list)
    """Comptes restés dans la branche alors que leur titulaire était encore
    là l'année suivante : la bascule précédente les a oubliés."""
    """Comptes laissés en place parce que la personne est encore inscrite."""

    avertissements: list[str] = field(default_factory=list)


def annee_depuis_ou(chemin: str) -> int | None:
    """Année de fin d'année scolaire lue dans le nom d'une branche.

    `/3. NDK/NDK2025` → 2025, soit l'année scolaire 2024-2025.
    """
    annees = re.findall(r"20\d\d", chemin or "")
    return int(annees[-1]) if annees else None


def _annee_fin(libelle: str | None) -> int | None:
    """`2025-2026` → 2026, l'année où cette année scolaire se termine."""
    annees = re.findall(r"20\d\d", libelle or "")
    return int(annees[-1]) if annees else None


def planifier_vidange(
    session: Session,
    comptes_google: list[dict],
    *,
    ou_source: str,
    annee_depart: int | None = None,
    ou_archivage: str | None = None,
    suspendre: bool = False,
    aujourd_hui: date | None = None,
) -> RapportVidange:
    """Construit le plan d'archivage des comptes d'une branche.

    Args:
        comptes_google: retour de `ClientGoogle.lister_utilisateurs`.
        ou_source: branche à vider, ex. `/3. NDK/NDK2025`.
        annee_depart: année de fin de scolarité. Déduite du nom de la
            branche si absente.
        ou_archivage: destination imposée. Sans elle, elle est déduite du
            site puis de l'échéance — mais un établissement qui range ses
            sortants dans une OU existante veut la nommer, pas la voir
            recalculée.
        suspendre: à vrai, coupe aussi l'accès. Faux par défaut : sortir
            de l'arbre des classes suffit à mettre en quarantaine.

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

    # Nom distinct : `ou_archivage` sert ensuite de variable locale, et la
    # fermeture ci-dessous lirait alors la valeur calculée au lieu de celle
    # demandée par l'appelant.
    destination_imposee = (ou_archivage or "").strip().rstrip("/")

    def archivage_pour(ech: date) -> str:
        if destination_imposee:
            return destination_imposee
        if site is not None and (site.ou_sortants or "").strip():
            return site.ou_sortants.strip().rstrip("/")
        from backend.services.configuration import get_param

        racine = (get_param(session, "google.ou_sortants") or "/7. Sortis").rstrip("/")
        return f"{racine}/Comptes à supprimer au {ech.strftime('%d-%m-%Y')}"

    ou_archivage = archivage_pour(echeance)

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

        # La branche date le départ de tout le monde. Mais un compte que la
        # bascule précédente a oublié y séjourne alors que son titulaire est
        # resté un an de plus : le référentiel le sait, et lui appliquer la
        # date de la branche écourterait sa quarantaine. On retient la plus
        # tardive des deux — jamais la plus courte.
        fin = _annee_fin(c.derniere_annee)
        if fin and fin > annee:
            depart_c = date(fin, 8, 31)
            echeance_c = date_echeance(depart_c)
            destination = archivage_pour(echeance_c)
            rapport.retardataires.append(c)
        else:
            echeance_c, destination = echeance, ou_archivage

        rapport.mouvements.append(
            MouvementVidange(
                email=c.email,
                ou_actuelle=c.ou,
                ou_visee=destination,
                date_echeance=echeance_c,
                suspendre=suspendre and not c.suspendu,
                nom=c.nom or c.nom_google,
                prenom=c.prenom or c.prenom_google,
                statut_referentiel=c.statut,
                personne_id=None,
            )
        )

    rapport.nb_a_archiver = len(rapport.mouvements)

    if rapport.retardataires:
        rapport.avertissements.append(
            f"{len(rapport.retardataires)} compte(s) figurent au référentiel "
            "dans une année postérieure au nom de la branche : la bascule "
            "précédente ne les a pas déplacés. Leur départ est daté de leur "
            "dernière année réelle, pas de celle de la branche — les archiver "
            "à la date de la branche écourterait leur conservation."
        )
    if rapport.epargnes:
        rapport.avertissements.append(
            f"{len(rapport.epargnes)} compte(s) laissé(s) en place : la personne "
            "figure dans l'année en cours. Les déplacer la sortirait de sa "
            "classe le jour de la rentrée."
        )
    if suspendre:
        rapport.avertissements.append(
            "La suspension est demandée : ces comptes ne pourront plus être "
            "consultés par leur titulaire. L'usage de l'établissement est de "
            "déplacer sans suspendre — décoche si ce n'était pas voulu."
        )
    if echeance <= (aujourd_hui or date.today()):
        rapport.avertissements.append(
            f"L'échéance calculée ({echeance.strftime('%d/%m/%Y')}) est déjà "
            "dépassée : ces comptes sont supprimables dès leur archivage."
        )
    return rapport
