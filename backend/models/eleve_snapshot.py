"""Modèle SQLAlchemy : EleveSnapshot (un élève à une année donnée)."""
from __future__ import annotations

from datetime import date
from typing import TYPE_CHECKING

from sqlalchemy import Boolean, Date, ForeignKey, Integer, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from backend.database import Base

if TYPE_CHECKING:
    from backend.models.annee_scolaire import AnneeScolaire
    from backend.models.etablissement import Etablissement


class EleveSnapshot(Base):
    """Un élève tel qu'il apparaît dans l'export Charlemagne d'une année.

    Un même élève (identifié par num_badge stable) apparaît potentiellement
    dans plusieurs snapshots d'années — c'est ce qui permet la comparaison
    N vs N-1 (entrants / restants / sortants).
    """

    __tablename__ = "eleve_snapshot"

    id: Mapped[int] = mapped_column(primary_key=True)
    annee_scolaire_id: Mapped[int] = mapped_column(
        ForeignKey("annee_scolaire.id"), index=True
    )
    etablissement_id: Mapped[int] = mapped_column(
        ForeignKey("etablissement.id"), index=True
    )

    num_badge: Mapped[int | None] = mapped_column(Integer, nullable=True, index=True)
    code_classe: Mapped[str | None] = mapped_column(String(30), nullable=True)
    code_niveau: Mapped[str | None] = mapped_column(String(30), nullable=True)
    code_regime: Mapped[str | None] = mapped_column(String(5), nullable=True)

    nom: Mapped[str] = mapped_column(String(100))
    prenom: Mapped[str] = mapped_column(String(100))

    date_entree: Mapped[date | None] = mapped_column(Date, nullable=True)
    est_nouveau_charlemagne: Mapped[bool] = mapped_column(Boolean, default=False)
    photo_chemin: Mapped[str | None] = mapped_column(String(500), nullable=True)

    annee: Mapped["AnneeScolaire"] = relationship(back_populates="eleves")
    etablissement: Mapped["Etablissement"] = relationship()

    # Un seul snapshot par (année, badge) — empêche les doubles imports accidentels
    __table_args__ = (
        UniqueConstraint(
            "annee_scolaire_id",
            "num_badge",
            name="uq_eleve_snapshot_annee_badge",
        ),
    )

    def __repr__(self) -> str:  # pragma: no cover
        return f"<EleveSnapshot {self.nom} {self.prenom} ({self.code_classe})>"
