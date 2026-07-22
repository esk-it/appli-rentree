"""Modèle SQLAlchemy : TableCorrespondance — configuration métier des classes.

Fait le pont entre les codes classe Charlemagne et les cibles :
- unité d'organisation Google (pré-rentrée et définitive),
- adresse du groupe Google (mailing list de la classe),
- adresse du groupe Google des profs de cette classe.

**Configuration éditable dans l'interface, jamais codée en dur.** Une
classe absente de cette table est un cas bloquant à l'ingestion — le
programme refuse plutôt que d'affecter par défaut.
"""
from __future__ import annotations

from sqlalchemy import ForeignKey, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from backend.database import Base


class TableCorrespondance(Base):
    __tablename__ = "table_correspondance"

    id: Mapped[int] = mapped_column(primary_key=True)

    site_id: Mapped[int] = mapped_column(ForeignKey("site.id"), index=True)

    classe_charlemagne_long: Mapped[str] = mapped_column(String(100), index=True)
    """Libellé long Charlemagne — ex. `TROISIEME FUSHIA`, `PREMIERE AGORA`, `SIXIEME 1`."""

    classe_code_court: Mapped[str] = mapped_column(String(30), index=True)
    """Code court utilisé dans les exports — ex. `3F`, `1_BPAGORA`, `61`."""

    groupe_google: Mapped[str | None] = mapped_column(String(200), nullable=True)
    """Mailing list de la classe — ex. `3eme-fuschia@ndecleder.fr`, `2nde-1@lekreisker.fr`."""

    ou_pre_rentree: Mapped[str] = mapped_column(String(200))
    """OU utilisée pendant la préparation (sans la classe) —
    ex. `/2. NDE/NDE2026`."""

    ou_definitive: Mapped[str] = mapped_column(String(200))
    """OU cible finale (avec la classe) — ex. `/2. NDE/NDE2026/3F`."""

    groupe_profs_google: Mapped[str | None] = mapped_column(String(200), nullable=True)
    """Groupe Google des profs enseignant dans cette classe — ex. `profs-2nde-gatl@lekreisker.fr`."""

    site: Mapped["Site"] = relationship()

    __table_args__ = (
        UniqueConstraint(
            "site_id", "classe_code_court", name="uq_table_correspondance_site_classe_court"
        ),
    )

    def __repr__(self) -> str:  # pragma: no cover
        return f"<TableCorrespondance {self.classe_code_court} → {self.ou_definitive}>"
