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

# 18 mois = ~547 jours
QUARANTAINE_GOOGLE = timedelta(days=548)

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
        compte.date_prevue_purge = today + QUARANTAINE_GOOGLE
    else:
        compte.etat = "purge"
        compte.date_prevue_purge = today

    session.flush()
    return TransitionCompte(
        personne_id=personne_id, cible=cible,
        etat_avant=etat_avant, etat_apres=compte.etat,
        date_prevue_purge=compte.date_prevue_purge,
    )


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
