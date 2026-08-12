"""Détection des anomalies du référentiel.

Regroupe en un seul endroit les incohérences qui méritent l'attention
avant une campagne de rentrée (§ statistiques du prompt de refonte) :

| Anomalie | Ce qu'elle signale |
|---|---|
| `classe_hors_table` | Classe présente dans un snapshot mais absente de la Table → bloque l'ingestion réelle et laisse l'OU vide côté Google |
| `arbitrage_en_attente` | Cas ambigu non tranché → bloque la simulation |
| `photo_orpheline` | Fichier photo attendu mais introuvable sur le partage → badge sans visuel |
| `personne_sans_site` | Personne sans site rattaché → aucune cible calculable |
| `personne_sans_email` | Login ou domaine manquant → ligne inexploitable côté Google |
| `compte_purge_echue` | Quarantaine terminée → suppression à décider |
| `classe_sans_groupe` | Classe sans adresse de groupe Google configurée |

Chaque anomalie porte une **gravité** :

- `bloquant` : empêche un traitement d'aboutir
- `attention` : n'empêche rien mais produit un résultat incomplet
- `information` : à connaître, sans urgence

Le service est en lecture seule et ne corrige jamais rien de lui-même.
"""
from __future__ import annotations

import json
from dataclasses import dataclass, field
from datetime import date
from pathlib import Path

from sqlalchemy.orm import Session

from backend.models import (
    Arbitrage,
    CompteCible,
    Personne,
    Site,
    Snapshot,
    TableCorrespondance,
)

GRAVITES = ("bloquant", "attention", "information")


@dataclass
class Anomalie:
    type: str
    gravite: str
    libelle: str
    """Description lisible, prête à afficher."""

    nb_concernes: int = 1
    details: list[str] = field(default_factory=list)
    """Échantillon d'éléments concernés (tronqué pour rester lisible)."""

    action_suggeree: str | None = None


@dataclass
class RapportAnomalies:
    annee_libelle: str | None
    anomalies: list[Anomalie] = field(default_factory=list)

    @property
    def nb_bloquants(self) -> int:
        return sum(1 for a in self.anomalies if a.gravite == "bloquant")

    @property
    def nb_total(self) -> int:
        return len(self.anomalies)

    @property
    def est_sain(self) -> bool:
        return self.nb_bloquants == 0


# Nombre d'éléments listés en détail avant troncature
_MAX_DETAILS = 25


def detecter_anomalies(
    session: Session,
    *,
    annee_id: int | None = None,
    verifier_photos: bool = False,
) -> RapportAnomalies:
    """Analyse le référentiel et retourne les anomalies détectées.

    Args:
        annee_id: restreint les vérifications liées aux snapshots à cette
            année. `None` = toutes années confondues.
        verifier_photos: active la vérification d'existence des fichiers
            photo. Coûteux (un accès disque par personne) et inutile si le
            partage réseau n'est pas monté — désactivé par défaut.
    """
    from backend.models import AnneeScolaire

    libelle = None
    if annee_id is not None:
        annee = session.query(AnneeScolaire).filter_by(id=annee_id).one_or_none()
        if annee is None:
            raise ValueError(f"Année introuvable : {annee_id}")
        libelle = annee.libelle

    rapport = RapportAnomalies(annee_libelle=libelle)

    for detecteur in (
        _classes_hors_table,
        _arbitrages_en_attente,
        _personnes_sans_site,
        _personnes_sans_email,
        _comptes_purge_echue,
        _classes_sans_groupe,
    ):
        anomalie = detecteur(session, annee_id)
        if anomalie is not None:
            rapport.anomalies.append(anomalie)

    if verifier_photos:
        anomalie = _photos_orphelines(session, annee_id)
        if anomalie is not None:
            rapport.anomalies.append(anomalie)

    # Bloquants d'abord, puis attention, puis information
    ordre = {g: i for i, g in enumerate(GRAVITES)}
    rapport.anomalies.sort(key=lambda a: (ordre.get(a.gravite, 9), a.type))
    return rapport


# ---------------------------------------------------------------------------
# Détecteurs
# ---------------------------------------------------------------------------


def _classes_hors_table(session: Session, annee_id: int | None) -> Anomalie | None:
    """Classes constatées dans les snapshots mais absentes de la Table."""
    q = session.query(Snapshot.classe).filter(Snapshot.classe.isnot(None))
    if annee_id is not None:
        q = q.filter(Snapshot.annee_scolaire_id == annee_id)
    classes_vues = {row[0] for row in q.distinct().all() if row[0]}

    classes_connues = {
        tc.classe_code_court
        for tc in session.query(TableCorrespondance.classe_code_court).all()
    }
    manquantes = sorted(classes_vues - classes_connues)
    if not manquantes:
        return None

    return Anomalie(
        type="classe_hors_table",
        gravite="bloquant",
        libelle=f"{len(manquantes)} classe(s) absente(s) de la Table de correspondance",
        nb_concernes=len(manquantes),
        details=manquantes[:_MAX_DETAILS],
        action_suggeree="Ajoute ces classes dans l'onglet Table de correspondance.",
    )


def _arbitrages_en_attente(session: Session, annee_id: int | None) -> Anomalie | None:
    arbitrages = (
        session.query(Arbitrage).filter(Arbitrage.date_decision.is_(None)).all()
    )
    if not arbitrages:
        return None

    par_type: dict[str, int] = {}
    for a in arbitrages:
        par_type[a.type_cas] = par_type.get(a.type_cas, 0) + 1

    return Anomalie(
        type="arbitrage_en_attente",
        gravite="bloquant",
        libelle=f"{len(arbitrages)} cas ambigu(s) attendent une décision",
        nb_concernes=len(arbitrages),
        details=[f"{t} : {n}" for t, n in sorted(par_type.items())],
        action_suggeree="Tranche-les dans l'onglet Arbitrage.",
    )


def _personnes_sans_site(session: Session, annee_id: int | None) -> Anomalie | None:
    personnes = session.query(Personne).filter(Personne.site_id.is_(None)).all()
    if not personnes:
        return None
    return Anomalie(
        type="personne_sans_site",
        gravite="bloquant",
        libelle=f"{len(personnes)} personne(s) sans site rattaché",
        nb_concernes=len(personnes),
        details=[f"{p.cle_pivot} {p.nom} {p.prenom}" for p in personnes[:_MAX_DETAILS]],
        action_suggeree=(
            "Sans site, aucune cible n'est calculable (ni OU, ni email). "
            "Vérifie que leur classe figure dans la Table de correspondance, "
            "puis relance l'ingestion."
        ),
    )


def _personnes_sans_email(session: Session, annee_id: int | None) -> Anomalie | None:
    """Personne dont l'email n'est pas calculable (login ou site manquant)."""
    sans_email = [
        p
        for p in session.query(Personne).all()
        if p.email is None and p.site_id is not None
    ]
    if not sans_email:
        return None
    return Anomalie(
        type="personne_sans_email",
        gravite="attention",
        libelle=f"{len(sans_email)} personne(s) sans email calculable",
        nb_concernes=len(sans_email),
        details=[f"{p.cle_pivot} {p.nom} {p.prenom}" for p in sans_email[:_MAX_DETAILS]],
        action_suggeree="Ces personnes seront absentes des exports Google et groupes.",
    )


def _comptes_purge_echue(session: Session, annee_id: int | None) -> Anomalie | None:
    comptes = (
        session.query(CompteCible)
        .filter(
            CompteCible.etat == "quarantaine",
            CompteCible.date_prevue_purge <= date.today(),
        )
        .all()
    )
    if not comptes:
        return None
    return Anomalie(
        type="compte_purge_echue",
        gravite="attention",
        libelle=f"{len(comptes)} compte(s) dont la date de purge est échue",
        nb_concernes=len(comptes),
        details=[
            f"{c.cible} — {c.identifiant_externe or c.personne_id} "
            f"(échéance {c.date_prevue_purge})"
            for c in comptes[:_MAX_DETAILS]
        ],
        action_suggeree=(
            "La suppression définitive se fait manuellement côté cible, "
            "après vérification."
        ),
    )


def _classes_sans_groupe(session: Session, annee_id: int | None) -> Anomalie | None:
    """Classes de la Table sans adresse de groupe Google configurée."""
    sans_groupe = [
        tc
        for tc in session.query(TableCorrespondance).all()
        if not tc.groupe_google
    ]
    if not sans_groupe:
        return None
    return Anomalie(
        type="classe_sans_groupe",
        gravite="information",
        libelle=f"{len(sans_groupe)} classe(s) sans adresse de groupe Google",
        nb_concernes=len(sans_groupe),
        details=[tc.classe_code_court for tc in sans_groupe[:_MAX_DETAILS]],
        action_suggeree=(
            "Ces classes seront absentes de l'export Groupes Google. "
            "Complète la colonne « groupe Google » si tu veux les mailing lists."
        ),
    )


def _photos_orphelines(session: Session, annee_id: int | None) -> Anomalie | None:
    """Personnes dont le fichier photo attendu est introuvable sur le partage."""
    from backend.models import Parametre

    param = (
        session.query(Parametre).filter_by(cle="chemin_dossier_photos").one_or_none()
    )
    if param is None:
        return None
    try:
        dossier = json.loads(param.valeur_json)
    except (json.JSONDecodeError, TypeError):
        return None
    if not dossier:
        return None

    racine = Path(dossier)
    if not racine.exists():
        return Anomalie(
            type="photo_dossier_inaccessible",
            gravite="attention",
            libelle=f"Dossier photos inaccessible : {dossier}",
            nb_concernes=0,
            action_suggeree=(
                "Vérifie que le partage réseau est monté et accessible en "
                "lecture depuis ce poste."
            ),
        )

    orphelines: list[str] = []
    for p in session.query(Personne).filter(Personne.type == "eleve").all():
        nom_fichier = p.chemin_photo_constate or f"{p.nom} {p.prenom}.jpg"
        if not (racine / nom_fichier).exists():
            orphelines.append(f"{p.cle_pivot} — {nom_fichier}")

    if not orphelines:
        return None
    return Anomalie(
        type="photo_orpheline",
        gravite="information",
        libelle=f"{len(orphelines)} photo(s) attendue(s) mais introuvable(s)",
        nb_concernes=len(orphelines),
        details=orphelines[:_MAX_DETAILS],
        action_suggeree=(
            "Ces élèves auront un badge sans visuel et un avatar initiales "
            "dans l'application."
        ),
    )
