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


def rendre_rapport_texte(rapport: RapportSimulation) -> str:
    """Rapport de simulation en texte brut, lisible et archivable.

    Reprend la forme du récapitulatif du cahier des charges — un bloc par
    cible, avec les compteurs alignés. Destiné à être relu, comparé d'une
    année sur l'autre, ou collé dans un mail.
    """
    lignes: list[str] = []
    ajouter = lignes.append

    ajouter("=" * 62)
    ajouter("RAPPORT DE SIMULATION".center(62))
    ajouter("=" * 62)
    ajouter("")
    ajouter(f"Année source : {rapport.annee_source_libelle}")
    ajouter(f"Année cible  : {rapport.annee_cible_libelle}")
    ajouter("")

    # Verdict en tête : c'est l'information qu'on cherche en premier
    if rapport.est_pret_a_executer:
        ajouter(">>> PRÊT À EXÉCUTER — aucun blocage détecté")
    else:
        ajouter(f">>> {len(rapport.blocages)} BLOCAGE(S) À TRAITER")
        for b in rapport.blocages:
            ajouter(f"    - {b.description}")
    ajouter("")

    # Totaux par cible
    ajouter("-" * 62)
    ajouter("TOTAUX PAR CIBLE")
    ajouter("-" * 62)
    entete = f"{'Cible':<14}{'Créations':>11}{'Modifs':>10}{'Sortants':>10}{'Inchangés':>12}"
    ajouter(entete)
    for cible, t in sorted(rapport.totaux_par_cible.items()):
        ajouter(
            f"{cible:<14}{t['nouveaux']:>11}{t['modifies']:>10}"
            f"{t['sortants']:>10}{t['identiques']:>12}"
        )
    ajouter("")

    # Détail par site et population
    if rapport.lignes:
        ajouter("-" * 62)
        ajouter("DÉTAIL PAR SITE ET POPULATION")
        ajouter("-" * 62)
        ajouter(
            f"{'Site':<8}{'Type':<9}{'Cible':<12}{'Nouv.':>7}{'Modif.':>8}{'Sort.':>7}{'Ops':>6}"
        )
        for l in sorted(
            rapport.lignes, key=lambda x: (x.site_nom, x.type_personne, x.cible)
        ):
            ajouter(
                f"{l.site_nom:<8}{l.type_personne:<9}{l.cible:<12}"
                f"{l.nouveaux:>7}{l.modifies:>8}{l.sortants:>7}{l.total_operations:>6}"
            )
        ajouter("")

    ajouter("=" * 62)
    ajouter(
        "Simulation — aucune écriture n'a été effectuée sur les systèmes cibles."
    )
    return "\n".join(lignes)


def rendre_rapport_csv(rapport: RapportSimulation) -> str:
    """Même contenu au format CSV, pour analyse en tableur."""
    import csv
    import io

    buf = io.StringIO(newline="")
    writer = csv.writer(buf, delimiter=";")
    writer.writerow(
        ["site", "type_personne", "cible", "nouveaux", "modifies", "sortants",
         "identiques", "total_operations"]
    )
    for l in sorted(
        rapport.lignes, key=lambda x: (x.site_nom, x.type_personne, x.cible)
    ):
        writer.writerow([
            l.site_nom, l.type_personne, l.cible,
            l.nouveaux, l.modifies, l.sortants, l.identiques, l.total_operations,
        ])
    return buf.getvalue()


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
