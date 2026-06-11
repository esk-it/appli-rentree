"""Modèle SQLAlchemy : AnneeScolaire (snapshot d'une rentrée)."""
from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import Boolean, DateTime, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from backend.database import Base

if TYPE_CHECKING:
    from backend.models.eleve_snapshot import EleveSnapshot


class AnneeScolaire(Base):
    __tablename__ = "annee_scolaire"

    id: Mapped[int] = mapped_column(primary_key=True)
    libelle: Mapped[str] = mapped_column(String(20), unique=True, index=True)  # "2025-2026"
    date_creation: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow
    )
    est_active: Mapped[bool] = mapped_column(Boolean, default=True)

    eleves: Mapped[list["EleveSnapshot"]] = relationship(
        back_populates="annee",
        cascade="all, delete-orphan",
    )

    def __repr__(self) -> str:  # pragma: no cover
        return f"<AnneeScolaire {self.libelle}>"
