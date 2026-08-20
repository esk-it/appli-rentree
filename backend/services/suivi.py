"""Service de suivi et purge des CompteCible (Lot 12).

Gère les transitions d'état :

    prevu → cree → actif → quarantaine → purge

Et le calcul automatique des dates de purge :

- Google : quarantaine 18 mois puis purge → `date_prevue_purge = today + 18 mois`
- Autres cibles (KoXo, PMB, JPM, CardStudio) : suppression immédiate,
  pas de quarantaine ; l'état passe directement à `purge` avec
  `date_prevue_purge = today`.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import date, timedelta

from sqlalchemy.orm import Session

from backend.models import CompteCible, Personne, Site
from backend.models.compte_cible import CIBLES, ETATS

# La règle de l'établissement : un compte sortant est conservé 18 mois, le
# temps qu'une demande de réactivation puisse arriver.
QUARANTAINE_MOIS = 18

# Conservé pour les appels existants ; l'échéance exacte se calcule en mois
# calendaires, qui tombent sur le même quantième et se lisent mieux qu'un
# décompte en jours.
QUARANTAINE_GOOGLE = timedelta(days=548)


def date_echeance(depart: date, *, mois: int = QUARANTAINE_MOIS) -> date:
    """Date de suppression : `depart` + N mois calendaires.

    En mois plutôt qu'en jours pour que l'échéance tombe sur le même
    quantième — une sortie au 31 août donne un 28 février, lisible, plutôt
    qu'un 18 février issu d'un décompte de 548 jours.

    Le quantième est ramené au dernier jour du mois quand il n'existe pas
    (31 août + 6 mois = 28 ou 29 février).
    """
    total = depart.month - 1 + mois
    annee = depart.year + total // 12
    mois_cible = total % 12 + 1
    # Dernier jour du mois cible
    if mois_cible == 12:
        fin = date(annee, 12, 31)
    else:
        fin = date(annee, mois_cible + 1, 1) - timedelta(days=1)
    return date(annee, mois_cible, min(depart.day, fin.day))

# Cibles avec quarantaine (sortie différée) vs immédiate
CIBLES_QUARANTAINE = {"google"}


@dataclass
class TransitionCompte:
    personne_id: int
    cible: str
    etat_avant: str
    etat_apres: str
    date_prevue_purge: date | None


def marquer_sortant(
    session: Session, personne_id: int, cible: str, *, aujourd_hui: date | None = None
) -> TransitionCompte:
    """Passe un compte cible de `actif` à `quarantaine` ou `purge` selon la cible.

    - Google → `quarantaine`, date de purge = today + 18 mois
    - Autres → `purge` immédiat, date de purge = today
    """
    if cible not in CIBLES:
        raise ValueError(f"cible invalide : {cible!r}")

    today = aujourd_hui or date.today()
    compte = session.query(CompteCible).filter_by(
        personne_id=personne_id, cible=cible
    ).one_or_none()
    if compte is None:
        raise ValueError(f"CompteCible introuvable : personne={personne_id} cible={cible}")

    etat_avant = compte.etat
    if cible in CIBLES_QUARANTAINE:
        compte.etat = "quarantaine"
        compte.date_prevue_purge = date_echeance(today)
    else:
        compte.etat = "purge"
        compte.date_prevue_purge = today

    session.flush()
    return TransitionCompte(
        personne_id=personne_id, cible=cible,
        etat_avant=etat_avant, etat_apres=compte.etat,
        date_prevue_purge=compte.date_prevue_purge,
    )


def enregistrer_sortie_anterieure(
    session: Session, personne_id: int, annee_fin: int
) -> bool:
    """Place en quarantaine un compte parti lors d'une année antérieure.

    Sert au rattrapage : un export « avec les sortants » remonte aussi les
    élèves partis les années d'avant. Leur compte Google existe encore — la
    politique est de le garder 18 mois, le temps d'une éventuelle demande de
    réactivation — mais rien ne le suivait, donc son échéance passait
    inaperçue.

    L'échéance se calcule depuis la **fin de la dernière année scolaire
    fréquentée** (31 août), et non depuis aujourd'hui : sans cela, rattraper
    un départ de 2025 lui donnerait 18 mois de plus à partir de maintenant.
    L'export ne portant pas de date de sortie précise, c'est l'approximation
    la plus fidèle disponible.

    Un compte déjà en quarantaine ou purgé n'est pas retouché.

    Returns:
        True si une transition a eu lieu.
    """
    compte = (
        session.query(CompteCible)
        .filter_by(personne_id=personne_id, cible="google")
        .one_or_none()
    )
    if compte is not None and compte.etat in ("quarantaine", "purge"):
        return False

    depart = date(annee_fin, 8, 31)
    if compte is None:
        compte = CompteCible(personne_id=personne_id, cible="google")
        session.add(compte)
    compte.etat = "quarantaine"
    compte.date_prevue_purge = date_echeance(depart)
    compte.note = f"Sortie constatée en fin d'année scolaire {annee_fin - 1}-{annee_fin}"
    session.flush()
    return True


def enregistrer_sortie(
    session: Session,
    personne_id: int,
    *,
    echeance: date,
    ou_visee: str,
    prevenance: date | None = None,
) -> bool:
    """Note qu'un compte a rejoint une OU de sortie, avec son échéance.

    Distinct de `mettre_en_quarantaine`, qui déduit l'échéance d'une année
    scolaire : ici elle est déjà connue — la destination l'impose, ou le
    plan l'a calculée. Un compte déplacé sans que rien ne l'enregistre
    disparaîtrait de l'écran des sortants et de la liste des personnes à
    prévenir avant suppression.

    Une quarantaine déjà en cours voit son échéance **mise à jour** : le
    compte vient de changer d'OU, donc de calendrier. Un compte purgé,
    lui, n'est pas ressuscité.

    Returns:
        True si quelque chose a été écrit.
    """
    compte = (
        session.query(CompteCible)
        .filter_by(personne_id=personne_id, cible="google")
        .one_or_none()
    )
    if compte is not None and compte.etat == "purge":
        return False
    if compte is None:
        compte = CompteCible(personne_id=personne_id, cible="google")
        session.add(compte)
    compte.etat = "quarantaine"
    compte.date_prevue_purge = echeance
    compte.ou_appliquee = ou_visee
    compte.note = (
        f"Déplacé vers {ou_visee}"
        + (f" — prévenance le {prevenance.strftime('%d/%m/%Y')}" if prevenance else "")
    )
    session.flush()
    return True


def comptes_a_purger(session: Session, *, aujourd_hui: date | None = None) -> list[CompteCible]:
    """Retourne les comptes en quarantaine dont la date de purge est échue."""
    today = aujourd_hui or date.today()
    return (
        session.query(CompteCible)
        .filter(
            CompteCible.etat == "quarantaine",
            CompteCible.date_prevue_purge <= today,
        )
        .all()
    )


@dataclass
class StatsSuivi:
    par_cible: dict[str, dict[str, int]]
    """Structure : {cible: {etat: count}}"""
    total_par_etat: dict[str, int]
    nb_purges_echues: int


def stats_suivi(session: Session, *, aujourd_hui: date | None = None) -> StatsSuivi:
    """Vue globale du suivi : combien de comptes dans chaque état, par cible."""
    par_cible: dict[str, dict[str, int]] = {c: {e: 0 for e in ETATS} for c in CIBLES}
    total: dict[str, int] = {e: 0 for e in ETATS}
    for c in session.query(CompteCible).all():
        if c.cible in par_cible and c.etat in par_cible[c.cible]:
            par_cible[c.cible][c.etat] += 1
            total[c.etat] += 1
    return StatsSuivi(
        par_cible=par_cible,
        total_par_etat=total,
        nb_purges_echues=len(comptes_a_purger(session, aujourd_hui=aujourd_hui)),
    )


def lister_par_etat(
    session: Session, etat: str, cible: str | None = None
) -> list[tuple[CompteCible, Personne, Site | None]]:
    """Liste les comptes dans un état donné (option : filtre par cible), avec
    la Personne + Site associés pour l'affichage."""
    if etat not in ETATS:
        raise ValueError(f"etat invalide : {etat!r}")

    q = (
        session.query(CompteCible, Personne, Site)
        .join(Personne, CompteCible.personne_id == Personne.id)
        .outerjoin(Site, Personne.site_id == Site.id)
        .filter(CompteCible.etat == etat)
    )
    if cible:
        q = q.filter(CompteCible.cible == cible)
    return [(c, p, s) for c, p, s in q.all()]
