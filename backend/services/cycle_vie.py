"""Cycle de vie des `CompteCible` — création et transitions d'état.

Comble le chaînon manquant du Lot 12 : le service `suivi.py` sait faire
transiter un `CompteCible`, mais rien ne les **créait**. Ce module les
alimente à partir du flux réel :

    génération d'un export « nouveaux »  → CompteCible(etat="prevu")
    confirmation de l'import côté cible  → etat="cree"
    personne présente dans l'année       → etat="actif"
    personne sortante (réconciliation)   → quarantaine (Google) ou purge

## Quelles cibles pour qui ?

| Cible | Population | Portée |
|---|---|---|
| `google` | élèves + adultes | tous les sites |
| `koxo_ndk` / `koxo_su` | élèves + adultes | un serveur par site |
| `pmb_ndk` / `pmb_su` | élèves + adultes | une instance par site |
| `jpm` | élèves uniquement | badges d'accès |
| `cardstudio` | élèves uniquement | impression badges |

**NDE** n'a ni serveur KoXo ni instance PMB propres : il est rattaché à
NDK par défaut (cf. `SUFFIXE_SERVEUR_PAR_SITE`). À ajuster ici si
l'infrastructure évolue — un seul endroit à changer.

## Identifiant externe

Renseigné à la création du `CompteCible` pour permettre le rapprochement
ultérieur avec la cible :

- `google` → email calculé
- toutes les autres → badge
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date

from sqlalchemy.orm import Session

from backend.models import CompteCible, Personne, Site, Snapshot
from backend.models.compte_cible import CIBLES, ETATS
from backend.services.suivi import marquer_sortant

# ---------------------------------------------------------------------------
# Mapping site → serveur KoXo / instance PMB
# ---------------------------------------------------------------------------

# NDE est rattaché à l'infrastructure NDK (pas de serveur propre).
SUFFIXE_SERVEUR_PAR_SITE = {
    "NDE": "ndk",
    "NDK": "ndk",
    "SU": "su",
}
SUFFIXE_PAR_DEFAUT = "ndk"

# Cibles réservées aux élèves (les adultes n'ont ni badge d'accès ni carte)
CIBLES_ELEVES_UNIQUEMENT = {"jpm", "cardstudio"}


def cibles_pour(site_nom: str, type_personne: str) -> list[str]:
    """Liste les cibles applicables à un couple (site, type de personne)."""
    if type_personne not in ("eleve", "adulte"):
        raise ValueError(f"type_personne invalide : {type_personne!r}")

    suffixe = SUFFIXE_SERVEUR_PAR_SITE.get(site_nom.upper(), SUFFIXE_PAR_DEFAUT)
    cibles = ["google", f"koxo_{suffixe}", f"pmb_{suffixe}"]
    if type_personne == "eleve":
        cibles += sorted(CIBLES_ELEVES_UNIQUEMENT)
    return [c for c in cibles if c in CIBLES]


# ---------------------------------------------------------------------------
# Rapports typés
# ---------------------------------------------------------------------------


@dataclass
class RapportCycleVie:
    """Résumé d'une opération de cycle de vie."""

    operation: str
    nb_crees: int = 0
    nb_transitions: int = 0
    nb_ignores: int = 0
    """Comptes déjà dans l'état visé, ou dans un état plus avancé."""

    details: list[dict] = field(default_factory=list)
    erreurs: list[str] = field(default_factory=list)


# ---------------------------------------------------------------------------
# Création : « prévu »
# ---------------------------------------------------------------------------


def _identifiant_externe(personne: Personne, cible: str) -> str | None:
    if cible == "google":
        return personne.email
    return str(personne.badge) if personne.badge else None


def enregistrer_prevus(
    session: Session,
    personne_ids: list[int],
    cibles: list[str],
) -> RapportCycleVie:
    """Crée les `CompteCible` manquants à l'état `prevu`.

    Idempotent : un compte déjà présent (quel que soit son état) n'est pas
    touché — on ne fait jamais reculer un état.
    """
    rapport = RapportCycleVie(operation="enregistrer_prevus")
    if not personne_ids or not cibles:
        return rapport

    for c in cibles:
        if c not in CIBLES:
            rapport.erreurs.append(f"cible inconnue ignorée : {c!r}")
    cibles = [c for c in cibles if c in CIBLES]

    personnes = {
        p.id: p
        for p in session.query(Personne).filter(Personne.id.in_(personne_ids)).all()
    }

    # Index des comptes déjà présents pour éviter N requêtes
    existants = {
        (c.personne_id, c.cible)
        for c in session.query(CompteCible)
        .filter(CompteCible.personne_id.in_(personne_ids))
        .all()
    }

    for pid in personne_ids:
        personne = personnes.get(pid)
        if personne is None:
            rapport.erreurs.append(f"personne introuvable : {pid}")
            continue
        for cible in cibles:
            if (pid, cible) in existants:
                rapport.nb_ignores += 1
                continue
            session.add(
                CompteCible(
                    personne_id=pid,
                    cible=cible,
                    etat="prevu",
                    identifiant_externe=_identifiant_externe(personne, cible),
                )
            )
            rapport.nb_crees += 1
            rapport.details.append(
                {"personne_id": pid, "cible": cible, "etat": "prevu"}
            )

    session.flush()
    return rapport


def enregistrer_prevus_pour_export(
    session: Session,
    *,
    site_id: int,
    type_personne: str,
    annee_cible_id: int,
    annee_source_id: int | None = None,
    categorie: str = "nouveaux",
    cible_unique: str | None = None,
) -> RapportCycleVie:
    """Enregistre en `prevu` les personnes qui figurent dans un export donné.

    Appelé au moment de générer un CSV « nouveaux » : les personnes du
    fichier sont désormais *prévues* sur la cible concernée.

    Args:
        cible_unique: si fourni, seule cette cible est enregistrée (ex.
            `koxo_ndk` quand on génère l'export KoXo). Sinon, toutes les
            cibles applicables au couple (site, type).
    """
    site = session.query(Site).filter_by(id=site_id).one_or_none()
    if site is None:
        raise ValueError(f"Site introuvable : {site_id}")

    ids = _personnes_de_lexport(
        session,
        site=site,
        type_personne=type_personne,
        categorie=categorie,
        annee_cible_id=annee_cible_id,
        annee_source_id=annee_source_id,
    )
    cibles = [cible_unique] if cible_unique else cibles_pour(site.nom, type_personne)
    return enregistrer_prevus(session, ids, cibles)


def _personnes_de_lexport(
    session: Session,
    *,
    site: Site,
    type_personne: str,
    categorie: str,
    annee_cible_id: int,
    annee_source_id: int | None,
) -> list[int]:
    """Reproduit la sélection des exports : tous / nouveaux / anciens."""
    ids_cible = _ids_annee(session, annee_cible_id, site, type_personne)
    if categorie == "tous":
        return sorted(ids_cible)
    if annee_source_id is None:
        raise ValueError(f"annee_source_id requis pour categorie={categorie!r}")
    ids_source = _ids_annee(session, annee_source_id, site, type_personne)
    if categorie == "nouveaux":
        return sorted(ids_cible - ids_source)
    if categorie == "anciens":
        return sorted(ids_source - ids_cible)
    raise ValueError(f"categorie invalide : {categorie!r}")


def _ids_annee(
    session: Session, annee_id: int, site: Site, type_personne: str
) -> set[int]:
    q = (
        session.query(Snapshot.personne_id)
        .join(Personne, Snapshot.personne_id == Personne.id)
        .filter(
            Snapshot.annee_scolaire_id == annee_id,
            Personne.site_id == site.id,
            Personne.type == type_personne,
        )
    )
    return {row[0] for row in q.all()}


# ---------------------------------------------------------------------------
# Transitions en avant : prevu → cree → actif
# ---------------------------------------------------------------------------

# Ordre des états — sert à empêcher tout retour en arrière
_RANG_ETAT = {etat: i for i, etat in enumerate(ETATS)}


def _avancer(compte: CompteCible, etat_vise: str) -> bool:
    """Fait avancer un compte vers `etat_vise`. Retourne True si transition.

    Ne recule jamais : un compte `actif` reste `actif` si on demande `cree`.
    """
    if _RANG_ETAT[etat_vise] <= _RANG_ETAT[compte.etat]:
        return False
    compte.etat = etat_vise
    return True


def confirmer_creation(
    session: Session,
    *,
    cible: str,
    site_id: int | None = None,
    personne_ids: list[int] | None = None,
) -> RapportCycleVie:
    """Passe les comptes `prevu` à `cree` — après import effectif côté cible.

    C'est l'action que l'utilisateur déclenche quand il a réellement
    importé le CSV dans KoXo / Google / PMB.
    """
    if cible not in CIBLES:
        raise ValueError(f"cible invalide : {cible!r}")

    rapport = RapportCycleVie(operation="confirmer_creation")
    q = session.query(CompteCible).filter(
        CompteCible.cible == cible, CompteCible.etat == "prevu"
    )
    if personne_ids:
        q = q.filter(CompteCible.personne_id.in_(personne_ids))
    if site_id is not None:
        q = q.join(Personne, CompteCible.personne_id == Personne.id).filter(
            Personne.site_id == site_id
        )

    for compte in q.all():
        if _avancer(compte, "cree"):
            rapport.nb_transitions += 1
            rapport.details.append(
                {"personne_id": compte.personne_id, "cible": cible, "etat": "cree"}
            )
        else:
            rapport.nb_ignores += 1

    session.flush()
    return rapport


def activer(
    session: Session,
    *,
    cible: str,
    site_id: int | None = None,
    personne_ids: list[int] | None = None,
) -> RapportCycleVie:
    """Passe les comptes `cree` à `actif` (compte en service)."""
    if cible not in CIBLES:
        raise ValueError(f"cible invalide : {cible!r}")

    rapport = RapportCycleVie(operation="activer")
    q = session.query(CompteCible).filter(
        CompteCible.cible == cible, CompteCible.etat == "cree"
    )
    if personne_ids:
        q = q.filter(CompteCible.personne_id.in_(personne_ids))
    if site_id is not None:
        q = q.join(Personne, CompteCible.personne_id == Personne.id).filter(
            Personne.site_id == site_id
        )

    for compte in q.all():
        if _avancer(compte, "actif"):
            rapport.nb_transitions += 1
        else:
            rapport.nb_ignores += 1

    session.flush()
    return rapport


# ---------------------------------------------------------------------------
# Sortants : application automatique de la politique de sortie
# ---------------------------------------------------------------------------


def traiter_sortants(
    session: Session,
    annee_source_id: int,
    annee_cible_id: int,
    *,
    aujourd_hui: date | None = None,
) -> RapportCycleVie:
    """Applique la politique de sortie à tous les sortants de la réconciliation.

    Pour chaque personne du seau `sortant`, chacun de ses comptes cibles
    passe en `quarantaine` (Google, +18 mois) ou `purge` (les autres).

    Les comptes déjà en quarantaine/purge sont laissés tels quels — pas de
    recalcul de date, pour ne pas repousser indéfiniment une échéance.
    """
    from backend.services.reconciliation import reconcilier

    rapport = RapportCycleVie(operation="traiter_sortants")

    for type_personne in ("eleve", "adulte"):
        r = reconcilier(
            session, annee_source_id, annee_cible_id, type_personne=type_personne
        )
        for entree in r.sortants:
            comptes = (
                session.query(CompteCible)
                .filter(CompteCible.personne_id == entree.personne_id)
                .all()
            )
            for compte in comptes:
                # Déjà sorti : on ne retouche pas la date d'échéance
                if compte.etat in ("quarantaine", "purge"):
                    rapport.nb_ignores += 1
                    continue
                try:
                    t = marquer_sortant(
                        session,
                        entree.personne_id,
                        compte.cible,
                        aujourd_hui=aujourd_hui,
                    )
                except ValueError as e:
                    rapport.erreurs.append(str(e))
                    continue
                rapport.nb_transitions += 1
                rapport.details.append(
                    {
                        "personne_id": entree.personne_id,
                        "cle_pivot": entree.cle_pivot,
                        "nom": entree.nom,
                        "prenom": entree.prenom,
                        "cible": compte.cible,
                        "etat": t.etat_apres,
                        "date_prevue_purge": (
                            t.date_prevue_purge.isoformat()
                            if t.date_prevue_purge
                            else None
                        ),
                    }
                )

    session.flush()
    return rapport
