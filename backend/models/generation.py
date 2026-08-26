"""Modèle SQLAlchemy : Generation — journal des opérations.

Trace **toute opération qui produit un résultat** : ingestion, amorçage,
import de la Table, génération d'un export. Deux usages :

1. **Audit** — savoir qui a fait quoi, quand, avec quels paramètres.
2. **Comparaison inter-années** — retrouver le rapport de la rentrée
   précédente pour repérer un chiffre aberrant (400 sortants au lieu
   de 160, cf. §5 du déroulé opérationnel).

Le **contenu des fichiers n'est jamais stocké** — trop volumineux, et
un export se régénère à l'identique depuis ses paramètres. Seuls les
paramètres et les compteurs sont conservés.

Aucun secret ne transite ici : les mots de passe ne figurent ni dans
`parametres_json` ni dans `resultat_json`.
"""
from __future__ import annotations

import json
from datetime import datetime
from typing import Any

from sqlalchemy import DateTime, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from backend.database import Base

# Familles d'opérations journalisées
TYPES_OPERATION = (
    "ingestion",
    "amorcage",
    "import_table",
    "export",
    "cycle_vie",
    # Toucher à un identifiant est assez rare, et assez lourd de
    # conséquences, pour mériter sa propre famille dans le journal.
    "identifiant",
)


class Generation(Base):
    __tablename__ = "generation"

    id: Mapped[int] = mapped_column(primary_key=True)

    date_creation: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow, index=True
    )

    type_operation: Mapped[str] = mapped_column(String(30), index=True)
    """Une valeur parmi TYPES_OPERATION."""

    cible: Mapped[str | None] = mapped_column(String(50), nullable=True, index=True)
    """Précision selon le type : `koxo`, `google`, `pmb`, `jpm`, `cardstudio`,
    `google_groupes` pour un export ; `eleve` / `adulte` pour une ingestion."""

    mode: Mapped[str | None] = mapped_column(String(20), nullable=True)
    """`simulation` ou `reel` quand la distinction s'applique."""

    annee_libelle: Mapped[str | None] = mapped_column(String(20), nullable=True, index=True)
    annee_source_libelle: Mapped[str | None] = mapped_column(String(20), nullable=True)

    parametres_json: Mapped[str] = mapped_column(Text, default="{}")
    """Paramètres de l'appel, sérialisés — permet de rejouer à l'identique."""

    resultat_json: Mapped[str] = mapped_column(Text, default="{}")
    """Compteurs du rapport (lignes lues, créations, rejets…)."""

    notes: Mapped[str | None] = mapped_column(String(500), nullable=True)

    # ------------------------------------------------------------------
    # Helpers de (dé)sérialisation
    # ------------------------------------------------------------------

    @property
    def parametres(self) -> dict[str, Any]:
        try:
            return json.loads(self.parametres_json or "{}")
        except (json.JSONDecodeError, TypeError):
            return {}

    @property
    def resultat(self) -> dict[str, Any]:
        try:
            return json.loads(self.resultat_json or "{}")
        except (json.JSONDecodeError, TypeError):
            return {}

    def __repr__(self) -> str:  # pragma: no cover
        return f"<Generation {self.type_operation}/{self.cible} {self.date_creation}>"
