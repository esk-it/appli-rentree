"""Modèle SQLAlchemy : AnneeScolaire.

Représente une année scolaire de référence (ex. `2025-2026`). Sert de
rattachement pour les `Snapshot` — chaque ingestion crée une nouvelle
photo dans le contexte d'une année donnée.
"""
from __future__ import annotations

from datetime import datetime

from sqlalchemy import Boolean, DateTime, String
from sqlalchemy.orm import Mapped, mapped_column

from backend.database import Base


class AnneeScolaire(Base):
    __tablename__ = "annee_scolaire"

    id: Mapped[int] = mapped_column(primary_key=True)
    libelle: Mapped[str] = mapped_column(String(20), unique=True, index=True)
    """Format `AAAA-AAAA`, ex. `2025-2026`."""

    date_creation: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    est_active: Mapped[bool] = mapped_column(Boolean, default=True)

    def __repr__(self) -> str:  # pragma: no cover
        return f"<AnneeScolaire {self.libelle}>"
