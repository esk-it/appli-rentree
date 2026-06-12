"""Modèle SQLAlchemy : AdulteSnapshot (un adulte/prof à une année donnée).

Symétrique à EleveSnapshot mais avec des champs spécifiques au personnel :
- fonction (PROF, AESH, SURVEILLANT, SECRETAIRE, ...)
- matieres (chaîne libre, ex. "MATH;PHYS-CHIMIE")
- civilite (M., Mme, Mlle)

L'identifiant stable d'un adulte côté Charlemagne est un numéro de personnel
ou parfois un INE personnel. À défaut, on retombe sur (nom + prénom).
"""
from __future__ import annotations

from datetime import date
from typing import TYPE_CHECKING

from sqlalchemy import Boolean, Date, ForeignKey, Integer, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from backend.database import Base

if TYPE_CHECKING:
    from backend.models.annee_scolaire import AnneeScolaire
    from backend.models.etablissement import Etablissement


class AdulteSnapshot(Base):
    """Un adulte (personnel) tel qu'il apparaît dans un export Charlemagne."""

    __tablename__ = "adulte_snapshot"

    id: Mapped[int] = mapped_column(primary_key=True)
    annee_scolaire_id: Mapped[int] = mapped_column(
        ForeignKey("annee_scolaire.id"), index=True
    )
    etablissement_id: Mapped[int | None] = mapped_column(
        ForeignKey("etablissement.id"), nullable=True, index=True
    )

    # Identifiants stables (au moins un des deux devrait être présent)
    num_personnel: Mapped[int | None] = mapped_column(
        Integer, nullable=True, index=True
    )
    # Champs personne
    civilite: Mapped[str | None] = mapped_column(String(10), nullable=True)
    nom: Mapped[str] = mapped_column(String(100))
    prenom: Mapped[str] = mapped_column(String(100))
    date_naissance: Mapped[date | None] = mapped_column(Date, nullable=True)

    # Champs fonction
    fonction: Mapped[str | None] = mapped_column(String(50), nullable=True)
    matieres: Mapped[str | None] = mapped_column(String(500), nullable=True)
    email_personnel: Mapped[str | None] = mapped_column(String(200), nullable=True)
    telephone: Mapped[str | None] = mapped_column(String(50), nullable=True)

    est_nouveau_charlemagne: Mapped[bool] = mapped_column(Boolean, default=False)

    annee: Mapped["AnneeScolaire"] = relationship()
    etablissement: Mapped["Etablissement | None"] = relationship()

    # Un seul snapshot par (année, num_personnel). Sans num_personnel,
    # on tolère mais la déduplication se fait au niveau du parser.
    __table_args__ = (
        UniqueConstraint(
            "annee_scolaire_id",
            "num_personnel",
            name="uq_adulte_snapshot_annee_personnel",
        ),
    )

    def __repr__(self) -> str:  # pragma: no cover
        return f"<AdulteSnapshot {self.nom} {self.prenom} ({self.fonction})>"
