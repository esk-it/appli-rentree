"""Génération des exports CSV pour KoXo.

KoXo attend un CSV séparateur virgule, encodage cp1252, avec les colonnes :

    Groupe primaire | Groupe secondaire | Titre | Nom | Prénom |
    Identifiant | ID unique | Mot de passe | Date de naissance | Email

Trois catégories d'export par (site, type_personne) :

- **Tous** : l'état complet visé — toutes les Personnes actives sur ce site.
- **Nouveaux** : uniquement les entrants — Personnes présentes à l'année
  cible mais absentes de l'année source. À importer avec KoXo qui générera
  les mots de passe.
- **Anciens** : uniquement les sortants — Personnes présentes à l'année
  source mais absentes de la cible. À supprimer côté KoXo.

## Le mot de passe

**Vide dans tous les exports.** KoXo est l'autorité qui génère les MDP à la
création (§7.1). Notre programme ne les invente pas et ne les régénère
jamais pour les comptes existants.

## Groupe primaire / secondaire

- Élèves : `Elèves` / code classe Charlemagne (`31`, `1_G2`, …)
- Adultes : `Professeurs` / matière enseignée (`MATHEMATIQUES`, …)
"""
from __future__ import annotations

import csv
import io
from dataclasses import dataclass
from typing import Literal

from sqlalchemy.orm import Session
from backend.services.rattachement import (
    ids_personnes_du_site,
    ids_presents_annee,
)

from backend.models import Personne, Site, Snapshot

# ---------------------------------------------------------------------------
# Format KoXo
# ---------------------------------------------------------------------------

# Ordre officiel des colonnes (validé sur l'export historique du prédécesseur)
COLONNES_KOXO = [
    "Groupe primaire",
    "Groupe secondaire",
    "Titre",
    "Nom",
    "Prénom",
    "Identifiant",
    "ID unique",
    "Mot de passe",
    "Date de naissance",
    "Email",
]

ENCODAGE_KOXO = "cp1252"

Categorie = Literal["tous", "nouveaux", "anciens"]


@dataclass
class ContexteExport:
    site: Site
    type_personne: str  # "eleve" | "adulte"
    categorie: Categorie
    annee_cible_id: int
    annee_source_id: int | None


@dataclass
class RapportExportKoxo:
    site_nom: str
    type_personne: str
    categorie: str
    nb_lignes: int
    nom_fichier_suggere: str


# ---------------------------------------------------------------------------
# Point d'entrée
# ---------------------------------------------------------------------------


def generer_csv_koxo(
    session: Session,
    *,
    site_id: int,
    type_personne: str,
    categorie: Categorie,
    annee_cible_id: int,
    annee_source_id: int | None = None,
) -> tuple[bytes, RapportExportKoxo]:
    """Génère un CSV KoXo pour une catégorie donnée.

    Args:
        session: SQLAlchemy session (lecture seule).
        site_id: site cible (NDE/NDK/SU).
        type_personne: `eleve` ou `adulte`.
        categorie: `tous` | `nouveaux` | `anciens`.
        annee_cible_id: année de référence pour "tous" et "nouveaux".
        annee_source_id: année précédente — obligatoire pour "nouveaux" et
            "anciens" (la comparaison ne peut se faire sans référent).

    Returns:
        Tuple (contenu CSV en bytes cp1252, rapport typé).

    Raises:
        ValueError: si les paramètres sont incohérents ou années introuvables.
    """
    if type_personne not in ("eleve", "adulte"):
        raise ValueError(f"type_personne invalide : {type_personne!r}")
    if categorie not in ("tous", "nouveaux", "anciens"):
        raise ValueError(f"categorie invalide : {categorie!r}")
    if categorie in ("nouveaux", "anciens") and annee_source_id is None:
        raise ValueError(
            f"annee_source_id requis pour categorie={categorie!r}"
        )

    site = session.query(Site).filter_by(id=site_id).one_or_none()
    if site is None:
        raise ValueError(f"Site introuvable : {site_id}")

    ctx = ContexteExport(
        site=site,
        type_personne=type_personne,
        categorie=categorie,
        annee_cible_id=annee_cible_id,
        annee_source_id=annee_source_id,
    )

    if categorie == "tous":
        lignes = _lignes_tous(session, ctx)
    elif categorie == "nouveaux":
        lignes = _lignes_nouveaux(session, ctx)
    else:
        lignes = _lignes_anciens(session, ctx)

    contenu = _encoder_csv(lignes)
    rapport = RapportExportKoxo(
        site_nom=site.nom,
        type_personne=type_personne,
        categorie=categorie,
        nb_lignes=len(lignes),
        nom_fichier_suggere=_nom_fichier(site.nom, type_personne, categorie),
    )
    return contenu, rapport


# ---------------------------------------------------------------------------
# Récupération des lignes selon la catégorie
# ---------------------------------------------------------------------------


def _lignes_tous(session: Session, ctx: ContexteExport) -> list[dict]:
    """État complet visé : toutes les Personnes du site+type ayant un snapshot
    dans l'année cible."""
    q = (
        session.query(Personne, Snapshot)
        .join(Snapshot, Snapshot.personne_id == Personne.id)
        .filter(
            Personne.id.in_(
                ids_personnes_du_site(
                    session, site_id=ctx.site.id,
                    annee_id=ctx.annee_cible_id, type_personne=ctx.type_personne,
                )
            ),
            Personne.type == ctx.type_personne,
            Snapshot.annee_scolaire_id == ctx.annee_cible_id,
        )
        .order_by(Personne.nom, Personne.prenom)
    )
    # Une personne peut avoir plusieurs snapshots dans une même année (multi-
    # ingestion) — on ne retient que le plus récent.
    par_personne: dict[int, Snapshot] = {}
    personnes_index: dict[int, Personne] = {}
    for p, s in q.all():
        precedent = par_personne.get(p.id)
        if precedent is None or s.date_ingestion > precedent.date_ingestion:
            par_personne[p.id] = s
            personnes_index[p.id] = p
    return [
        _formatter_ligne(personnes_index[pid], par_personne[pid], ctx.type_personne)
        for pid in par_personne
    ]


def _lignes_nouveaux(session: Session, ctx: ContexteExport) -> list[dict]:
    """Nouveaux entrants : présents à annee_cible, absents à annee_source."""
    # Entrée dans l'établissement, pas dans le site : l'année source est
    # comparée tous sites confondus. Sinon une élève montant de SU à NDK
    # passerait pour une nouvelle, et l'on tenterait de créer un compte
    # Google qu'elle possède déjà.
    ids_source = ids_presents_annee(
        session, annee_id=ctx.annee_source_id, type_personne=ctx.type_personne
    )
    snapshots_cible = _snapshots_annee_par_personne(session, ctx.annee_cible_id, ctx)

    ids_nouveaux = set(snapshots_cible) - ids_source
    personnes = _charger_personnes(session, ids_nouveaux)
    return [
        _formatter_ligne(personnes[pid], snapshots_cible[pid], ctx.type_personne)
        for pid in ids_nouveaux
        if pid in personnes
    ]


def _lignes_anciens(session: Session, ctx: ContexteExport) -> list[dict]:
    """Sortants : présents à annee_source, absents à annee_cible."""
    snapshots_source = _snapshots_annee_par_personne(session, ctx.annee_source_id, ctx)
    # Départ de l'établissement, pas du site : l'année cible est comparée
    # tous sites confondus. Sinon la même élève passerait pour une
    # sortante de SU, et son compte serait suspendu le jour de sa rentrée.
    ids_cible = ids_presents_annee(
        session, annee_id=ctx.annee_cible_id, type_personne=ctx.type_personne
    )

    ids_anciens = set(snapshots_source) - ids_cible
    personnes = _charger_personnes(session, ids_anciens)
    return [
        _formatter_ligne(personnes[pid], snapshots_source[pid], ctx.type_personne)
        for pid in ids_anciens
        if pid in personnes
    ]


# ---------------------------------------------------------------------------
# Helpers de requête
# ---------------------------------------------------------------------------


def _ids_personnes_annee(session: Session, annee_id: int, ctx: ContexteExport) -> set[int]:
    q = (
        session.query(Snapshot.personne_id)
        .join(Personne, Snapshot.personne_id == Personne.id)
        .filter(
            Snapshot.annee_scolaire_id == annee_id,
            Personne.id.in_(
                ids_personnes_du_site(
                    session, site_id=ctx.site.id,
                    annee_id=annee_id, type_personne=ctx.type_personne,
                )
            ),
            Personne.type == ctx.type_personne,
        )
    )
    return {row[0] for row in q.all()}


def _snapshots_annee_par_personne(
    session: Session, annee_id: int, ctx: ContexteExport
) -> dict[int, Snapshot]:
    q = (
        session.query(Snapshot)
        .join(Personne, Snapshot.personne_id == Personne.id)
        .filter(
            Snapshot.annee_scolaire_id == annee_id,
            Personne.id.in_(
                ids_personnes_du_site(
                    session, site_id=ctx.site.id,
                    annee_id=annee_id, type_personne=ctx.type_personne,
                )
            ),
            Personne.type == ctx.type_personne,
        )
        .order_by(Snapshot.personne_id, Snapshot.date_ingestion.desc())
    )
    derniers: dict[int, Snapshot] = {}
    for s in q.all():
        if s.personne_id not in derniers:
            derniers[s.personne_id] = s
    return derniers


def _charger_personnes(session: Session, ids: set[int]) -> dict[int, Personne]:
    if not ids:
        return {}
    q = session.query(Personne).filter(Personne.id.in_(ids))
    return {p.id: p for p in q.all()}


# ---------------------------------------------------------------------------
# Formatage d'une ligne KoXo
# ---------------------------------------------------------------------------


def _formatter_ligne(personne: Personne, snapshot: Snapshot, type_personne: str) -> dict:
    """Construit une ligne au format KoXo. Le MDP est TOUJOURS vide (KoXo génère)."""
    groupe_primaire = "Elèves" if type_personne == "eleve" else "Professeurs"

    if type_personne == "eleve":
        groupe_secondaire = snapshot.classe or ""
    else:
        # Adultes : matière enseignée, ou service pour non-profs
        groupe_secondaire = (snapshot.matieres or snapshot.poste_occupe or "").split(";")[0].strip()

    email = personne.email or ""

    return {
        "Groupe primaire": groupe_primaire,
        "Groupe secondaire": groupe_secondaire,
        "Titre": "",
        "Nom": personne.nom or "",
        "Prénom": personne.prenom or "",
        "Identifiant": personne.login or "",
        "ID unique": str(personne.badge) if personne.badge else "",
        "Mot de passe": "",  # KoXo génère
        "Date de naissance": "",
        "Email": email,
    }


# ---------------------------------------------------------------------------
# Sortie
# ---------------------------------------------------------------------------


def _encoder_csv(lignes: list[dict]) -> bytes:
    """Encode en cp1252 (attendu par KoXo côté Windows)."""
    buf = io.StringIO(newline="")
    writer = csv.DictWriter(buf, fieldnames=COLONNES_KOXO, quoting=csv.QUOTE_MINIMAL)
    writer.writeheader()
    for l in lignes:
        writer.writerow(l)
    return buf.getvalue().encode(ENCODAGE_KOXO, errors="replace")


def _nom_fichier(site_nom: str, type_personne: str, categorie: str) -> str:
    """`KoXo_NDK_eleves_nouveaux.csv` etc."""
    pop = "eleves" if type_personne == "eleve" else "adultes"
    return f"KoXo_{site_nom}_{pop}_{categorie}.csv"
