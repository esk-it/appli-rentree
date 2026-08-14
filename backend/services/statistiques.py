"""Service de statistiques génériques (Lot 13).

Fournit des agrégations lues depuis les Snapshots + Personnes pour un
tableau de bord. Toutes les stats sont **dérivées** de la base — aucune
donnée agrégée n'est pré-calculée ni stockée. Ajouter une stat = ajouter
une méthode ici, pas de migration.
"""
from __future__ import annotations

from collections import Counter
from dataclasses import dataclass, field

from sqlalchemy import func
from sqlalchemy.orm import Session

from backend.models import Arbitrage, Personne, Site, Snapshot


@dataclass
class StatValeur:
    """Une entrée dans un histogramme (label, effectif)."""
    label: str
    valeur: int


@dataclass
class StatsAnnee:
    annee_id: int
    annee_libelle: str

    nb_personnes: int = 0
    nb_eleves: int = 0
    nb_adultes: int = 0

    par_site: list[StatValeur] = field(default_factory=list)
    par_regime: list[StatValeur] = field(default_factory=list)
    par_niveau: list[StatValeur] = field(default_factory=list)
    par_etablissement_charlemagne: list[StatValeur] = field(default_factory=list)


@dataclass
class StatsReferentiel:
    """Stats indépendantes d'une année — sur l'ensemble du référentiel."""
    nb_personnes_total: int = 0
    nb_eleves_total: int = 0
    nb_adultes_total: int = 0
    nb_sites: int = 0
    nb_classes_table: int = 0
    """Lignes de la Table de correspondance. Permet de savoir si la
    configuration métier est faite, plutôt que de le déduire de l'absence
    d'anomalie — absence qui est trivialement vraie sur un référentiel vide."""
    nb_annees_scolaires: int = 0
    nb_arbitrages_en_attente: int = 0
    nb_arbitrages_tranches: int = 0


def stats_referentiel(session: Session) -> StatsReferentiel:
    """Vue transverse du référentiel (ne dépend pas d'une année)."""
    from backend.models import TableCorrespondance

    return StatsReferentiel(
        nb_personnes_total=session.query(Personne).count(),
        nb_eleves_total=session.query(Personne).filter_by(type="eleve").count(),
        nb_adultes_total=session.query(Personne).filter_by(type="adulte").count(),
        nb_sites=session.query(Site).count(),
        nb_classes_table=session.query(TableCorrespondance).count(),
        nb_annees_scolaires=session.query(func.count(func.distinct(Snapshot.annee_scolaire_id))).scalar() or 0,
        nb_arbitrages_en_attente=session.query(Arbitrage).filter(Arbitrage.date_decision.is_(None)).count(),
        nb_arbitrages_tranches=session.query(Arbitrage).filter(Arbitrage.date_decision.isnot(None)).count(),
    )


def stats_annee(session: Session, annee_id: int) -> StatsAnnee:
    """Répartitions par site/régime/niveau/établissement pour une année donnée."""
    from backend.models import AnneeScolaire

    annee = session.query(AnneeScolaire).filter_by(id=annee_id).one_or_none()
    if annee is None:
        raise ValueError(f"Année introuvable : {annee_id}")

    stats = StatsAnnee(annee_id=annee.id, annee_libelle=annee.libelle)

    # Snapshots (le plus récent par personne dans cette année)
    q = (
        session.query(Snapshot, Personne)
        .join(Personne, Snapshot.personne_id == Personne.id)
        .filter(Snapshot.annee_scolaire_id == annee_id)
        .order_by(Snapshot.personne_id, Snapshot.date_ingestion.desc())
    )
    derniers: dict[int, tuple[Snapshot, Personne]] = {}
    for s, p in q.all():
        if s.personne_id not in derniers:
            derniers[s.personne_id] = (s, p)

    personnes = [p for _, p in derniers.values()]
    snapshots = [s for s, _ in derniers.values()]

    stats.nb_personnes = len(personnes)
    stats.nb_eleves = sum(1 for p in personnes if p.type == "eleve")
    stats.nb_adultes = sum(1 for p in personnes if p.type == "adulte")

    # Résolution nom du site (via id)
    sites = {s.id: s.nom for s in session.query(Site).all()}

    stats.par_site = _histogram(
        (sites.get(p.site_id) or "inconnu") for p in personnes
    )
    stats.par_regime = _histogram(
        (s.regime or "?") for s in snapshots
        if s.regime  # ignore les adultes sans régime
    )
    stats.par_niveau = _histogram((s.niveau or "?") for s in snapshots if s.niveau)
    stats.par_etablissement_charlemagne = _histogram(
        (s.code_etablissement or "?") for s in snapshots if s.code_etablissement
    )

    return stats


def _histogram(iterable) -> list[StatValeur]:
    """Compte les occurrences et trie par effectif décroissant."""
    c = Counter(iterable)
    return [StatValeur(label=k, valeur=v) for k, v in c.most_common()]
