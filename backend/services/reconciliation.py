"""Réconciliation — classement d'une année cible par rapport à une année source.

Compare deux `AnneeScolaire` sur la clé pivot `(type, id_charlemagne)` et
classe chaque personne dans **cinq seaux** (§8.2 de gestion-rentree-logique) :

| Seau | Définition | Traitement |
|---|---|---|
| **nouveau**   | Absent de l'année source, présent dans la cible | Création à Google/KoXo/PMB |
| **identique** | Snapshots aux deux années, hash constaté identique | Aucune action |
| **modifie**   | Snapshots aux deux années, hash différent | Mise à jour ciblée |
| **sortant**   | Snapshot source sans équivalent cible | Politique de sortie (quarantaine) |
| **ambigu**    | Rapprochement incertain — arbitrage humain requis | Écran Arbitrage (Lot 5) |

Le service **ne modifie rien** : il lit les Snapshots persistés par
l'ingestion et produit un rapport typé. C'est un outil de lecture, pas un
processus. La cohérence du hash avec `ingestion._hash_etat_snapshot` est
garantie par un import direct de cette fonction — même vérité, un seul
endroit où changer la définition.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Iterable

from sqlalchemy.orm import Session

from backend.models import AnneeScolaire, Personne, Snapshot
from backend.services.ingestion import _hash_etat_snapshot as _hash_champs

# ---------------------------------------------------------------------------
# Vocabulaire
# ---------------------------------------------------------------------------

SEAUX = ("nouveau", "identique", "modifie", "sortant", "ambigu")


# ---------------------------------------------------------------------------
# Résumés typés
# ---------------------------------------------------------------------------


@dataclass
class ChangementChamp:
    """Un attribut qui a changé entre le snapshot source et le snapshot cible."""

    champ: str
    avant: str | None
    apres: str | None


@dataclass
class EntreeReconciliation:
    """Une personne classée dans un seau, avec le motif du classement."""

    personne_id: int
    cle_pivot: str  # `E5292` / `A60`
    type: str
    nom: str
    prenom: str
    login: str
    site_id: int | None
    classe_source: str | None
    classe_cible: str | None
    motif: str
    """Explication courte : « nouveau dans l'export », « classe 3B → 4A », etc."""

    changements: list[ChangementChamp] = field(default_factory=list)
    """Détail des attributs modifiés — vide sauf pour le seau `modifie`."""


@dataclass
class RapportReconciliation:
    annee_source_id: int
    annee_source_libelle: str
    annee_cible_id: int
    annee_cible_libelle: str
    type_personne: str | None
    """`eleve`, `adulte` ou `None` pour les deux."""

    nouveaux: list[EntreeReconciliation] = field(default_factory=list)
    identiques: list[EntreeReconciliation] = field(default_factory=list)
    modifies: list[EntreeReconciliation] = field(default_factory=list)
    sortants: list[EntreeReconciliation] = field(default_factory=list)
    ambigus: list[EntreeReconciliation] = field(default_factory=list)

    @property
    def compteurs(self) -> dict[str, int]:
        return {
            "nouveau": len(self.nouveaux),
            "identique": len(self.identiques),
            "modifie": len(self.modifies),
            "sortant": len(self.sortants),
            "ambigu": len(self.ambigus),
        }


# ---------------------------------------------------------------------------
# Champs comparés pour la diff — même liste que le hash d'ingestion
# ---------------------------------------------------------------------------

_CHAMPS_SNAPSHOT = (
    "nom",
    "prenom",
    "nom_usage",
    "classe",
    "niveau",
    "code_etablissement",
    "regime",
    "chemin_photo",
    "date_entree",
    "poste_occupe",
    "matieres",
    "classes_prof_principal",
    "classe_precedente",
    "classe_an_prochain",
)


def _hash_snapshot(snap: Snapshot) -> str:
    """Applique le hash d'ingestion sur les champs constatés d'un Snapshot."""
    return _hash_champs(**{c: getattr(snap, c) for c in _CHAMPS_SNAPSHOT})


def _diff_snapshots(source: Snapshot, cible: Snapshot) -> list[ChangementChamp]:
    """Retourne les attributs qui diffèrent entre deux snapshots."""
    changements: list[ChangementChamp] = []
    for c in _CHAMPS_SNAPSHOT:
        avant = getattr(source, c)
        apres = getattr(cible, c)
        if avant != apres:
            changements.append(
                ChangementChamp(
                    champ=c,
                    avant=None if avant is None else str(avant),
                    apres=None if apres is None else str(apres),
                )
            )
    return changements


# ---------------------------------------------------------------------------
# Point d'entrée
# ---------------------------------------------------------------------------


def reconcilier(
    session: Session,
    annee_source_id: int,
    annee_cible_id: int,
    type_personne: str | None = None,
) -> RapportReconciliation:
    """Compare deux années scolaires et renvoie le classement en 5 seaux.

    Args:
        session: SQLAlchemy session (lecture uniquement).
        annee_source_id: année servant de référentiel (souvent l'année N-1).
        annee_cible_id: année à évaluer (souvent l'année en cours après ingestion).
        type_personne: filtre optionnel `eleve` ou `adulte`. `None` = les deux.

    Raises:
        ValueError: si l'une des années n'existe pas ou si type_personne
            est invalide.
    """
    if type_personne is not None and type_personne not in ("eleve", "adulte"):
        raise ValueError(
            f"type_personne doit être 'eleve', 'adulte' ou None, reçu : {type_personne!r}"
        )

    annee_source = session.query(AnneeScolaire).filter_by(id=annee_source_id).one_or_none()
    annee_cible = session.query(AnneeScolaire).filter_by(id=annee_cible_id).one_or_none()
    if annee_source is None:
        raise ValueError(f"Année source introuvable : {annee_source_id}")
    if annee_cible is None:
        raise ValueError(f"Année cible introuvable : {annee_cible_id}")

    rapport = RapportReconciliation(
        annee_source_id=annee_source.id,
        annee_source_libelle=annee_source.libelle,
        annee_cible_id=annee_cible.id,
        annee_cible_libelle=annee_cible.libelle,
        type_personne=type_personne,
    )

    # 1. Derniers snapshots par personne pour chaque année (une ingestion peut
    #    en produire plusieurs si les valeurs constatées ont bougé).
    source_par_personne = _derniers_snapshots(session, annee_source_id, type_personne)
    cible_par_personne = _derniers_snapshots(session, annee_cible_id, type_personne)

    ids_source = set(source_par_personne)
    ids_cible = set(cible_par_personne)

    # 2. Charge les personnes concernées en une requête (pour login/nom/site)
    personnes = _charger_personnes(session, ids_source | ids_cible)

    # 3. Classement
    for pid in ids_cible - ids_source:
        rapport.nouveaux.append(
            _entree_pour(
                personnes[pid],
                snap_source=None,
                snap_cible=cible_par_personne[pid],
                motif="nouveau dans l'export cible",
            )
        )

    for pid in ids_source - ids_cible:
        rapport.sortants.append(
            _entree_pour(
                personnes[pid],
                snap_source=source_par_personne[pid],
                snap_cible=None,
                motif="présent dans l'année source, absent de la cible",
            )
        )

    for pid in ids_source & ids_cible:
        snap_src = source_par_personne[pid]
        snap_tgt = cible_par_personne[pid]
        if _hash_snapshot(snap_src) == _hash_snapshot(snap_tgt):
            rapport.identiques.append(
                _entree_pour(personnes[pid], snap_src, snap_tgt, motif="aucun changement")
            )
        else:
            changements = _diff_snapshots(snap_src, snap_tgt)
            motif = _resumer_changements(changements)
            entree = _entree_pour(personnes[pid], snap_src, snap_tgt, motif=motif)
            entree.changements = changements
            rapport.modifies.append(entree)

    # 4. Le seau « ambigu » reste vide tant que le Lot 5 (arbitrage) n'a pas
    #    branché les collisions de login et homonymies non tranchées.
    return rapport


# ---------------------------------------------------------------------------
# Helpers internes
# ---------------------------------------------------------------------------


def _derniers_snapshots(
    session: Session, annee_id: int, type_personne: str | None
) -> dict[int, Snapshot]:
    """Récupère le dernier `Snapshot` par personne pour une année donnée.

    Le tri par `date_ingestion` desc puis premier vu garantit qu'on retient
    l'ingestion la plus récente si plusieurs snapshots existent (multi-ingest).
    """
    q = (
        session.query(Snapshot)
        .join(Personne, Snapshot.personne_id == Personne.id)
        .filter(Snapshot.annee_scolaire_id == annee_id)
        .order_by(Snapshot.personne_id, Snapshot.date_ingestion.desc())
    )
    if type_personne is not None:
        q = q.filter(Personne.type == type_personne)

    derniers: dict[int, Snapshot] = {}
    for snap in q:
        if snap.personne_id not in derniers:
            derniers[snap.personne_id] = snap
    return derniers


def _charger_personnes(session: Session, ids: Iterable[int]) -> dict[int, Personne]:
    ids = list(ids)
    if not ids:
        return {}
    q = session.query(Personne).filter(Personne.id.in_(ids))
    return {p.id: p for p in q}


def _entree_pour(
    personne: Personne,
    snap_source: Snapshot | None,
    snap_cible: Snapshot | None,
    motif: str,
) -> EntreeReconciliation:
    return EntreeReconciliation(
        personne_id=personne.id,
        cle_pivot=personne.cle_pivot,
        type=personne.type,
        nom=personne.nom,
        prenom=personne.prenom,
        login=personne.login,
        site_id=personne.site_id,
        classe_source=snap_source.classe if snap_source else None,
        classe_cible=snap_cible.classe if snap_cible else None,
        motif=motif,
    )


def _resumer_changements(changements: list[ChangementChamp]) -> str:
    """Génère un motif lisible : `classe 3B → 4A`, ou `nom + regime` si plusieurs."""
    if not changements:
        return "changement détecté"
    # Cas fréquent : un seul champ → phrase précise
    if len(changements) == 1:
        c = changements[0]
        return f"{c.champ} {c.avant or '∅'} → {c.apres or '∅'}"
    # Sinon on cite les champs, tronqué
    noms = ", ".join(c.champ for c in changements[:4])
    if len(changements) > 4:
        noms += f", +{len(changements) - 4}"
    return f"changements : {noms}"
