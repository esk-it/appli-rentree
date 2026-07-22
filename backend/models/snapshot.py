"""Modèle SQLAlchemy : Snapshot — l'historique brut.

Un `Snapshot` est **l'état constaté** d'une personne à une date donnée
(une ingestion Charlemagne). Il ne porte pas d'identité — l'identité vit
dans `Personne`. Il porte des valeurs figées dans le temps qui permettent
d'auditer et de calculer n'importe quelle statistique rétroactivement.

**Conservés indéfiniment**, une ligne par personne et par ingestion.
"""
from __future__ import annotations

from datetime import date, datetime

from sqlalchemy import Date, DateTime, ForeignKey, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from backend.database import Base


class Snapshot(Base):
    __tablename__ = "snapshot"

    id: Mapped[int] = mapped_column(primary_key=True)

    personne_id: Mapped[int] = mapped_column(ForeignKey("personne.id"), index=True)
    annee_scolaire_id: Mapped[int] = mapped_column(ForeignKey("annee_scolaire.id"), index=True)

    date_ingestion: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, index=True)

    # État constaté à cette date (copie figée, indépendante de Personne)
    nom: Mapped[str] = mapped_column(String(100))
    prenom: Mapped[str] = mapped_column(String(100))
    nom_usage: Mapped[str | None] = mapped_column(String(100), nullable=True)

    classe: Mapped[str | None] = mapped_column(String(30), nullable=True)
    niveau: Mapped[str | None] = mapped_column(String(30), nullable=True)

    code_etablissement: Mapped[str | None] = mapped_column(String(20), nullable=True)
    """Code Charlemagne au moment du snapshot (02-COL / 03-LY / 04-LP)."""

    regime: Mapped[str | None] = mapped_column(String(5), nullable=True)
    chemin_photo: Mapped[str | None] = mapped_column(String(500), nullable=True)
    date_entree: Mapped[date | None] = mapped_column(Date, nullable=True)

    # Champs adultes copiés pour audit
    poste_occupe: Mapped[str | None] = mapped_column(String(100), nullable=True)
    matieres: Mapped[str | None] = mapped_column(String(500), nullable=True)
    classes_prof_principal: Mapped[str | None] = mapped_column(String(500), nullable=True)

    # Passage de classe issu de Charlemagne (élèves) : les 3 colonnes présentes dans l'export
    classe_precedente: Mapped[str | None] = mapped_column(String(30), nullable=True)
    classe_an_prochain: Mapped[str | None] = mapped_column(String(30), nullable=True)

    # Relations
    personne: Mapped["Personne"] = relationship()
    annee_scolaire: Mapped["AnneeScolaire"] = relationship()

    def __repr__(self) -> str:  # pragma: no cover
        return f"<Snapshot personne={self.personne_id} {self.date_ingestion.date()}>"
