"""Modèle SQLAlchemy : Generation (historique des exports lancés).

Trace chaque génération avec ses paramètres, pour pouvoir re-générer
exactement la même chose à n'importe quel moment. Le contenu des
fichiers n'est PAS stocké (trop volumineux) — uniquement les paramètres.
"""
from __future__ import annotations

from datetime import datetime

from sqlalchemy import DateTime, Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from backend.database import Base


class Generation(Base):
    __tablename__ = "generation"

    id: Mapped[int] = mapped_column(primary_key=True)
    date_creation: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow, index=True
    )
    cible: Mapped[str] = mapped_column(String(50))  # koxo, pmb, cardstudio, smartair, google, tout, koxo-adultes, ...
    annee_n: Mapped[str] = mapped_column(String(20))
    annee_n_minus_1: Mapped[str | None] = mapped_column(String(20), nullable=True)
    nb_fichiers: Mapped[int] = mapped_column(Integer)
    nb_lignes_total: Mapped[int] = mapped_column(Integer)
    notes: Mapped[str | None] = mapped_column(String(500), nullable=True)

    def __repr__(self) -> str:  # pragma: no cover
        return f"<Generation {self.cible} {self.annee_n} ({self.date_creation})>"
