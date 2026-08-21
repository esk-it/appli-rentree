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

## Où va la promotion, et sous quel nom

Un départ constaté au 31 août N rejoint l'OU datée du **31 décembre
N+1**. La lettre part à cette date, la suppression suit quatre mois plus
tard : vingt mois de conservation au total, au-delà des dix-huit que
l'établissement s'est engagé à tenir.

Cette règle n'est pas une invention : elle reproduit l'usage constaté.
Les enseignants partis en juin 2026 occupent bien l'OU du 31-12-2027.
Elle donne une OU par promotion, nommée par sa propre échéance, et
permet de traiter tout un lot d'un geste — une lettre, puis une
suppression — sans suivre les comptes un par un.

## Deux dates, pas une

L'établissement date ses OU de sortie — « Comptes à supprimer au
31-12-2027 ». Cette date est celle de la **lettre de prévenance**, pas de
la suppression : le titulaire est averti fin décembre que son compte
vivra encore quatre mois, et la suppression n'intervient qu'au terme de
ce délai. Le nom de l'OU dit donc quand le compte à rebours démarre.

Quand la destination porte une date lisible, c'est elle qui commande :
prévenance à cette date, suppression quatre mois plus tard. Sans date
lisible — l'OU de sortie de NDE n'en porte pas — on retombe sur la règle
générale ci-dessous.

## L'échéance par défaut

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

## Ce que le déplacement laisse comme trace

Un compte sorti de l'arbre des classes n'est plus visible nulle part si
rien ne l'enregistre : ni dans l'écran des sortants, ni dans la liste des
personnes à prévenir avant suppression. Chaque mouvement porte donc
l'identifiant de la personne quand le rapprochement l'a trouvée, pour que
le déplacement réussi puisse être reporté au référentiel.

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
    date_prevenance: date | None = None
    """Date de la lettre annonçant la suppression, lue dans le nom de l'OU."""

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


DELAI_APRES_PREVENANCE_MOIS = 4
"""Ce que la lettre annonce : le compte vit encore quatre mois."""

RACINE_SORTIE_DEFAUT = "/7. Sortis"


def ou_sortie_pour(annee_depart: int, racine: str = RACINE_SORTIE_DEFAUT) -> str:
    """Destination d'une promotion partie au 31 août `annee_depart`.

    Le 31 décembre de l'année suivante : seize mois après le départ pour
    la lettre, vingt en tout avant la suppression.
    """
    return f"{racine.rstrip('/')}/Comptes à supprimer au 31-12-{annee_depart + 1}"

_DATE_DANS_OU = re.compile(r"(?<!\d)(\d{2})-(\d{2})-(20\d\d)(?!\d)")


def date_prevenance(ou: str | None) -> date | None:
    """Date lue dans le nom d'une OU de sortie, ex. `… au 31-12-2027`.

    C'est la date de la lettre de prévenance. `None` si le nom n'en porte
    pas — auquel cas rien ne doit être déduit.
    """
    m = _DATE_DANS_OU.search(ou or "")
    if not m:
        return None
    jour, mois, annee = (int(x) for x in m.groups())
    try:
        return date(annee, mois, jour)
    except ValueError:
        return None


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

    # Le site se reconnaît au préfixe de la branche : il porte parfois sa
    # propre convention d'archivage, antérieure au programme.
    site = None
    for s_ in session.query(Site).all():
        if s_.prefixe_annee_ou and s_.prefixe_annee_ou in ou_source:
            site = s_
            break

    # Nom distinct : `ou_archivage` sert ensuite de variable locale, et les
    # fermetures ci-dessous liraient la valeur calculée au lieu de celle
    # demandée par l'appelant.
    destination_imposee = (ou_archivage or "").strip().rstrip("/")

    from backend.services.configuration import get_param

    racine = (
        get_param(session, "google.ou_sortants") or RACINE_SORTIE_DEFAUT
    ).rstrip("/")

    def destination_pour(annee_de_depart: int) -> str:
        """Où va une promotion partie au 31 août de cette année-là.

        Un choix explicite l'emporte sur tout : c'est une décision, pas une
        déduction. Sinon la convention du site, puis la règle du 31 décembre.
        """
        if destination_imposee:
            return destination_imposee
        if site is not None and (site.ou_sortants or "").strip():
            return site.ou_sortants.strip().rstrip("/")
        return ou_sortie_pour(annee_de_depart, racine)

    def calendrier_pour(chemin: str, annee_de_depart: int) -> tuple[date | None, date]:
        """Prévenance et suppression, lues sur la destination si elle est datée.

        C'est la destination qui commande, y compris quand le programme
        vient de la calculer : sans cela, le plan annoncerait une échéance
        que le nom de l'OU contredit.
        """
        prev = date_prevenance(chemin)
        if prev is not None:
            return prev, date_echeance(prev, mois=DELAI_APRES_PREVENANCE_MOIS)
        return None, date_echeance(date(annee_de_depart, 8, 31))

    ou_archivage = destination_pour(annee)
    prevenance, echeance = calendrier_pour(ou_archivage, annee)

    inspection = recouper_avec_referentiel(session, comptes_google, prefixe_ou=ou_source)
    rapport = RapportVidange(
        ou_source=ou_source,
        ou_archivage=ou_archivage,
        date_depart=depart,
        date_echeance=echeance,
        date_prevenance=prevenance,
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
        # Rester dans une branche dont le nom sous-estime son départ reste un
        # fait à signaler, même quand la destination impose son calendrier à
        # tout le monde : c'est la trace d'une bascule précédente incomplète.
        fin = _annee_fin(c.derniere_annee)
        en_retard = bool(fin and fin > annee)
        if en_retard:
            rapport.retardataires.append(c)

        if en_retard and not destination_imposee:
            # Parti un an plus tard, il relève de la promotion suivante :
            # lui appliquer le calendrier de cette branche écourterait sa
            # conservation de douze mois.
            destination = destination_pour(fin)
            _, echeance_c = calendrier_pour(destination, fin)
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
                personne_id=c.personne_id,
            )
        )

    rapport.nb_a_archiver = len(rapport.mouvements)

    if rapport.retardataires:
        detail = (
            "Ils suivent le calendrier de la destination, comme les autres."
            if destination_imposee
            else (
                "Ils rejoignent la destination de leur année réelle, pas "
                "celle de cette branche — la confondre écourterait leur "
                "conservation de douze mois."
            )
        )
        rapport.avertissements.append(
            f"{len(rapport.retardataires)} compte(s) figurent au référentiel "
            "dans une année postérieure au nom de la branche : la bascule "
            f"précédente ne les a pas déplacés. {detail}"
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
    if prevenance is not None:
        rapport.avertissements.append(
            f"La destination fixe le calendrier : prévenance le "
            f"{prevenance.strftime('%d/%m/%Y')}, suppression le "
            f"{echeance.strftime('%d/%m/%Y')}. La date lue dans le nom de "
            "l'OU annonce la lettre, pas la suppression."
        )
    if echeance <= (aujourd_hui or date.today()):
        rapport.avertissements.append(
            f"L'échéance calculée ({echeance.strftime('%d/%m/%Y')}) est déjà "
            "dépassée : ces comptes sont supprimables dès leur archivage."
        )
    return rapport
