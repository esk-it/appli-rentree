"""Modèle SQLAlchemy : CompteCible — cycle de vie par (Personne, cible).

Une ligne par couple `(Personne, cible)`. L'état n'est **jamais global** à
la personne : elle peut être supprimée d'un système et active dans un
autre pendant 18 mois (quarantaine Google).

## États

```
prevu → cree → actif → quarantaine → purge
```

- `prevu` : décidé côté référentiel, pas encore appliqué sur la cible
- `cree` : appliqué (compte créé sur la cible)
- `actif` : personne présente en Charlemagne, compte utilisé
- `quarantaine` : personne partie, compte encore présent (uniquement pour Google, 18 mois)
- `purge` : compte définitivement supprimé de la cible

## Politique de sortie par cible

| Cible | Sortie |
|---|---|
| koxo_ndk, koxo_su, pmb_ndk, pmb_su, jpm, cardstudio | Suppression immédiate |
| google | Quarantaine 18 mois, puis suppression |
"""
from __future__ import annotations

from datetime import date, datetime

from sqlalchemy import Date, DateTime, ForeignKey, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from backend.database import Base

from typing import TYPE_CHECKING

if TYPE_CHECKING:  # pragma: no cover
    from backend.models.personne import Personne



# Vocabulaire figé (valeurs stables en base — ne pas renommer sans migration)
CIBLES = (
    "koxo_ndk",
    "koxo_su",
    "google",
    "pmb_ndk",
    "pmb_su",
    "jpm",
    "cardstudio",
)

ETATS = ("prevu", "cree", "actif", "quarantaine", "purge")


class CompteCible(Base):
    __tablename__ = "compte_cible"

    id: Mapped[int] = mapped_column(primary_key=True)

    personne_id: Mapped[int] = mapped_column(ForeignKey("personne.id"), index=True)

    cible: Mapped[str] = mapped_column(String(30), index=True)
    """Code cible parmi CIBLES."""

    etat: Mapped[str] = mapped_column(String(20), index=True)
    """État parmi ETATS."""

    date_prevue_purge: Mapped[date | None] = mapped_column(Date, nullable=True, index=True)
    """Date à laquelle une purge est prévue (utilisé pour Google en quarantaine)."""

    identifiant_externe: Mapped[str | None] = mapped_column(String(100), nullable=True)
    """Identifiant côté cible : badge pour KoXo/JPM/CardStudio, google_user_id pour Google,
    INE ou badge pour PMB selon config."""

    ou_appliquee: Mapped[str | None] = mapped_column(String(200), nullable=True)
    """Dernière OU **connue** pour ce compte (Google uniquement).

    Deux origines possibles : une OU que nous avons demandée, ou une OU
    relevée dans Google. La seconde est plus sûre — elle décrit le réel —
    mais suppose l'API configurée.

    Sans cette trace, impossible de dire qui a déjà été placé et qui reste
    à déplacer : la bascule serait à refaire en entier à chaque fois, sans
    moyen de vérifier qu'elle a porté."""

    date_creation: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    date_derniere_maj: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow, onupdate=datetime.utcnow
    )

    note: Mapped[str | None] = mapped_column(String(500), nullable=True)

    personne: Mapped["Personne"] = relationship()

    __table_args__ = (
        UniqueConstraint("personne_id", "cible", name="uq_compte_cible_personne_cible"),
    )

    def __repr__(self) -> str:  # pragma: no cover
        return f"<CompteCible personne={self.personne_id} {self.cible} {self.etat}>"
