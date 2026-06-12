"""Modèles SQLAlchemy : Chambre et AffectationChambre.

Gestion de l'internat : déclaration des chambres physiques disponibles
(par bâtiment, étage, capacité) et affectation des élèves internes à
ces chambres pour chaque année scolaire.
"""
from __future__ import annotations

from sqlalchemy import ForeignKey, Integer, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from backend.database import Base


class Chambre(Base):
    __tablename__ = "chambre"

    id: Mapped[int] = mapped_column(primary_key=True)
    numero: Mapped[str] = mapped_column(String(20), unique=True, index=True)
    batiment: Mapped[str | None] = mapped_column(String(50), nullable=True)
    etage: Mapped[str | None] = mapped_column(String(20), nullable=True)
    capacite_max: Mapped[int] = mapped_column(Integer, default=1)
    notes: Mapped[str | None] = mapped_column(String(200), nullable=True)

    def __repr__(self) -> str:  # pragma: no cover
        return f"<Chambre {self.numero}>"


class AffectationChambre(Base):
    """Affecte un élève à une chambre pour une année donnée."""

    __tablename__ = "affectation_chambre"

    id: Mapped[int] = mapped_column(primary_key=True)
    chambre_id: Mapped[int] = mapped_column(
        ForeignKey("chambre.id"), index=True
    )
    eleve_snapshot_id: Mapped[int] = mapped_column(
        ForeignKey("eleve_snapshot.id"), index=True
    )

    chambre: Mapped["Chambre"] = relationship()

    # Un élève ne peut être dans qu'une seule chambre par snapshot
    __table_args__ = (
        UniqueConstraint(
            "eleve_snapshot_id",
            name="uq_affectation_eleve_unique_par_snapshot",
        ),
    )
