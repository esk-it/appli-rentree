"""Moteur de simulation transverse — vue unifiée de ce que le programme ferait.

Pour un couple `(annee_source, annee_cible)`, agrège les opérations qui
seraient produites par chaque module cible (KoXo, Google, …) et les
présente dans un rapport de lecture. Aucune écriture.

C'est le rapport que l'utilisateur lit **avant de générer les CSV** — il
sait alors combien de comptes seront créés/supprimés/déplacés côté KoXo
et côté Google, et repère les blocages (arbitrages en attente, classes
hors table) qui l'empêchent d'aller plus loin.

## Structure

Par (site, type_personne, cible) : un `LigneSimulation` avec les
compteurs `nouveaux`, `identiques`, `modifies`, `sortants`. La cible peut
être `koxo` ou `google`.

Les compteurs proviennent de la même logique que la réconciliation — on
appelle en interne `reconcilier` puis on ré-agrège par cible.
"""
from __future__ import annotations

from dataclasses import dataclass, field

from sqlalchemy.orm import Session

from backend.models import AnneeScolaire, Arbitrage, Personne, Site
from backend.services.reconciliation import reconcilier

TYPES_PERSONNE = ("eleve", "adulte")
CIBLES = ("koxo", "google")


@dataclass
class LigneSimulation:
    site_id: int
    site_nom: str
    type_personne: str
    cible: str  # "koxo" | "google"
    nouveaux: int = 0
    identiques: int = 0
    modifies: int = 0
    sortants: int = 0

    @property
    def total_operations(self) -> int:
        """Nombre d'opérations qui produiraient un changement (hors identiques)."""
        return self.nouveaux + self.modifies + self.sortants


@dataclass
class BlocageSimulation:
    """Un point qui empêche l'exécution automatique."""

    type: str  # "arbitrage_en_attente" | "classe_hors_table"
    description: str
    valeur: str | None = None


@dataclass
class RapportSimulation:
    annee_source_id: int
    annee_source_libelle: str
    annee_cible_id: int
    annee_cible_libelle: str

    lignes: list[LigneSimulation] = field(default_factory=list)
    blocages: list[BlocageSimulation] = field(default_factory=list)

    nb_arbitrages_en_attente: int = 0
    """Personnes en arbitrage → à trancher avant tout traitement automatique."""

    @property
    def totaux_par_cible(self) -> dict[str, dict[str, int]]:
        """Agrégation transverse par cible : {cible: {nouveaux, modifies, sortants, identiques}}."""
        agg: dict[str, dict[str, int]] = {}
        for l in self.lignes:
            d = agg.setdefault(
                l.cible,
                {"nouveaux": 0, "identiques": 0, "modifies": 0, "sortants": 0},
            )
            d["nouveaux"] += l.nouveaux
            d["identiques"] += l.identiques
            d["modifies"] += l.modifies
            d["sortants"] += l.sortants
        return agg

    @property
    def est_pret_a_executer(self) -> bool:
        """True si aucun blocage majeur (arbitrages, classes hors table)."""
        return self.nb_arbitrages_en_attente == 0 and not self.blocages


# ---------------------------------------------------------------------------
# Point d'entrée
# ---------------------------------------------------------------------------


def simuler_globalement(
    session: Session,
    annee_source_id: int,
    annee_cible_id: int,
) -> RapportSimulation:
    """Produit le rapport transverse pour un couple (source, cible)."""
    annee_source = session.query(AnneeScolaire).filter_by(id=annee_source_id).one_or_none()
    annee_cible = session.query(AnneeScolaire).filter_by(id=annee_cible_id).one_or_none()
    if annee_source is None:
        raise ValueError(f"Année source introuvable : {annee_source_id}")
    if annee_cible is None:
        raise ValueError(f"Année cible introuvable : {annee_cible_id}")

    rapport = RapportSimulation(
        annee_source_id=annee_source.id,
        annee_source_libelle=annee_source.libelle,
        annee_cible_id=annee_cible.id,
        annee_cible_libelle=annee_cible.libelle,
    )

    # 1. Réconciliation globale — puis re-filtrage par (site, type)
    sites = session.query(Site).order_by(Site.numero_ordre).all()

    for site in sites:
        for type_p in TYPES_PERSONNE:
            counts = _compter_par_site_type(session, annee_source_id, annee_cible_id, site, type_p)
            if counts["total"] == 0:
                continue  # inutile de créer une ligne vide pour un couple sans personnes
            for cible in CIBLES:
                rapport.lignes.append(
                    LigneSimulation(
                        site_id=site.id,
                        site_nom=site.nom,
                        type_personne=type_p,
                        cible=cible,
                        nouveaux=counts["nouveaux"],
                        identiques=counts["identiques"],
                        modifies=counts["modifies"],
                        sortants=counts["sortants"],
                    )
                )

    # 2. Arbitrages en attente : bloquent l'exécution
    en_attente = session.query(Arbitrage).filter(Arbitrage.date_decision.is_(None)).count()
    rapport.nb_arbitrages_en_attente = en_attente
    if en_attente > 0:
        rapport.blocages.append(
            BlocageSimulation(
                type="arbitrage_en_attente",
                description=f"{en_attente} cas ambigu(s) attendent une décision humaine",
                valeur=str(en_attente),
            )
        )

    return rapport


# ---------------------------------------------------------------------------
# Helper : agrégation depuis la réconciliation
# ---------------------------------------------------------------------------


def _compter_par_site_type(
    session: Session,
    annee_source_id: int,
    annee_cible_id: int,
    site: Site,
    type_personne: str,
) -> dict[str, int]:
    """Réconcilie puis restreint aux personnes du (site, type) donné."""
    r = reconcilier(session, annee_source_id, annee_cible_id, type_personne=type_personne)

    def n(seau: str) -> int:
        return sum(1 for e in getattr(r, seau) if e.site_id == site.id)

    return {
        "nouveaux": n("nouveaux"),
        "identiques": n("identiques"),
        "modifies": n("modifies"),
        "sortants": n("sortants"),
        "total": n("nouveaux") + n("identiques") + n("modifies") + n("sortants"),
    }
