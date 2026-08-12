"""Journal des opérations — écriture et relecture des `Generation`.

Chaque opération produisant un résultat (ingestion, amorçage, import de
la Table, export, transition de cycle de vie) laisse une trace. Objectifs :

- **Audit** : retrouver ce qui a été fait, quand, avec quels paramètres.
- **Comparaison inter-années** : `comparer_avec_precedent()` met en regard
  le résultat courant et celui de la même opération l'année d'avant, pour
  repérer un chiffre aberrant avant qu'il ne fasse des dégâts.

## Ce qui n'est jamais journalisé

Les mots de passe. Les rapports d'export ne les contiennent pas, et
`_nettoyer()` retire par précaution toute clé dont le nom évoque un
secret — un futur champ ajouté par mégarde ne fuitera pas ici.
"""
from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any

from sqlalchemy.orm import Session

from backend.models import Generation
from backend.models.generation import TYPES_OPERATION

# Fragments de noms de clés qui ne doivent jamais être journalisés
_CLES_SENSIBLES = ("mot_de_passe", "password", "mdp", "secret", "token", "base64")


def _nettoyer(donnees: dict[str, Any] | None) -> dict[str, Any]:
    """Retire les clés sensibles et les valeurs non sérialisables.

    Le filtre est volontairement large : mieux vaut perdre une info de
    debug que journaliser un secret.
    """
    if not donnees:
        return {}
    propre: dict[str, Any] = {}
    for cle, valeur in donnees.items():
        nom = str(cle).lower()
        if any(frag in nom for frag in _CLES_SENSIBLES):
            continue
        try:
            json.dumps(valeur)
        except (TypeError, ValueError):
            valeur = str(valeur)
        propre[cle] = valeur
    return propre


def journaliser(
    session: Session,
    *,
    type_operation: str,
    cible: str | None = None,
    mode: str | None = None,
    annee_libelle: str | None = None,
    annee_source_libelle: str | None = None,
    parametres: dict[str, Any] | None = None,
    resultat: dict[str, Any] | None = None,
    notes: str | None = None,
) -> Generation:
    """Enregistre une opération dans le journal. Le caller commit."""
    if type_operation not in TYPES_OPERATION:
        raise ValueError(
            f"type_operation doit être {TYPES_OPERATION}, reçu : {type_operation!r}"
        )

    generation = Generation(
        type_operation=type_operation,
        cible=cible,
        mode=mode,
        annee_libelle=annee_libelle,
        annee_source_libelle=annee_source_libelle,
        parametres_json=json.dumps(_nettoyer(parametres), ensure_ascii=False, default=str),
        resultat_json=json.dumps(_nettoyer(resultat), ensure_ascii=False, default=str),
        notes=notes,
    )
    session.add(generation)
    session.flush()
    return generation


def lister(
    session: Session,
    *,
    type_operation: str | None = None,
    cible: str | None = None,
    annee_libelle: str | None = None,
    limite: int = 100,
) -> list[Generation]:
    """Historique, du plus récent au plus ancien."""
    q = session.query(Generation)
    if type_operation:
        q = q.filter(Generation.type_operation == type_operation)
    if cible:
        q = q.filter(Generation.cible == cible)
    if annee_libelle:
        q = q.filter(Generation.annee_libelle == annee_libelle)
    return q.order_by(Generation.date_creation.desc()).limit(limite).all()


# ---------------------------------------------------------------------------
# Comparaison inter-années
# ---------------------------------------------------------------------------


@dataclass
class EcartCompteur:
    compteur: str
    valeur_courante: int
    valeur_precedente: int

    @property
    def ecart(self) -> int:
        return self.valeur_courante - self.valeur_precedente

    @property
    def ecart_relatif(self) -> float | None:
        """Variation en pourcentage. `None` si la référence est nulle
        (une hausse depuis zéro n'a pas de taux interprétable)."""
        if self.valeur_precedente == 0:
            return None
        return (self.ecart / self.valeur_precedente) * 100

    @property
    def est_aberrant(self) -> bool:
        """Vrai si l'écart mérite un coup d'œil avant de valider.

        Seuil : plus de 50 % de variation sur un effectif d'au moins 10.
        En dessous, les petits nombres produisent trop de faux positifs
        (passer de 2 à 4 sortants n'est pas une anomalie).
        """
        if max(self.valeur_courante, self.valeur_precedente) < 10:
            return False
        rel = self.ecart_relatif
        return rel is not None and abs(rel) > 50


@dataclass
class ComparaisonJournal:
    trouvee: bool
    """Faux si aucune opération comparable n'existe dans l'historique."""

    reference_id: int | None = None
    reference_date: str | None = None
    reference_annee: str | None = None
    ecarts: list[EcartCompteur] = None  # type: ignore[assignment]

    def __post_init__(self) -> None:
        if self.ecarts is None:
            self.ecarts = []

    @property
    def aberrations(self) -> list[EcartCompteur]:
        return [e for e in self.ecarts if e.est_aberrant]


def comparer_avec_precedent(
    session: Session,
    *,
    type_operation: str,
    cible: str | None,
    annee_libelle: str | None,
    resultat_courant: dict[str, Any],
) -> ComparaisonJournal:
    """Compare un résultat aux compteurs de la même opération, année d'avant.

    « Même opération » = même `type_operation` et même `cible`, sur une
    **année différente** de celle en cours. On retient la plus récente.
    """
    q = session.query(Generation).filter(Generation.type_operation == type_operation)
    if cible:
        q = q.filter(Generation.cible == cible)
    if annee_libelle:
        q = q.filter(Generation.annee_libelle != annee_libelle)

    reference = q.order_by(Generation.date_creation.desc()).first()
    if reference is None:
        return ComparaisonJournal(trouvee=False)

    precedent = reference.resultat
    ecarts: list[EcartCompteur] = []
    for cle, valeur in _nettoyer(resultat_courant).items():
        if not isinstance(valeur, int) or isinstance(valeur, bool):
            continue
        ancienne = precedent.get(cle)
        if not isinstance(ancienne, int) or isinstance(ancienne, bool):
            continue
        ecarts.append(
            EcartCompteur(
                compteur=cle, valeur_courante=valeur, valeur_precedente=ancienne
            )
        )

    return ComparaisonJournal(
        trouvee=True,
        reference_id=reference.id,
        reference_date=reference.date_creation.isoformat(),
        reference_annee=reference.annee_libelle,
        ecarts=sorted(ecarts, key=lambda e: e.compteur),
    )
