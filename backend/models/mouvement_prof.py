"""Modèle SQLAlchemy : MouvementProf — le tableau des enseignants, conservé.

Le mouvement de chaque enseignant — sortant, arrivant, en formation,
remplacé — vit dans un classeur tenu à la main, où il est porté par la
couleur de sa ligne. Le lire est une chose ; le garder en est une autre.

Sans cette table, chaque consultation de l'écran Chromebooks réclamait le
fichier à nouveau. Un import doit charger des données, pas les emprunter
le temps d'un affichage : c'est ce que font déjà l'ingestion Charlemagne
et l'amorçage KoXo, et il n'y a pas de raison que celui-ci fasse
autrement.

Les lignes sont rattachées à une **année scolaire** : le tableau de la
rentrée suivante ne remplace pas celui d'avant, il s'ajoute. On peut donc
relire ce qu'on a fait l'an dernier, et un réimport ne détruit que
l'année qu'il concerne.
"""
from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import DateTime, ForeignKey, Integer, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from backend.database import Base

if TYPE_CHECKING:  # pragma: no cover
    from backend.models.annee_scolaire import AnneeScolaire


class MouvementProf(Base):
    __tablename__ = "mouvement_prof"

    id: Mapped[int] = mapped_column(primary_key=True)

    annee_scolaire_id: Mapped[int] = mapped_column(
        ForeignKey("annee_scolaire.id"), index=True
    )

    nom: Mapped[str] = mapped_column(String(120), index=True)
    prenom: Mapped[str] = mapped_column(String(120))
    civilite: Mapped[str | None] = mapped_column(String(20), nullable=True)
    discipline: Mapped[str | None] = mapped_column(String(120), nullable=True)

    code: Mapped[str] = mapped_column(String(20), index=True)
    """`sortant`, `arrivant`, `formation`, `remplace`, `en_poste`, `inconnu`."""

    libelle: Mapped[str | None] = mapped_column(String(200), nullable=True)
    """Le libellé de légende, tel qu'écrit dans le classeur."""

    couleur: Mapped[str | None] = mapped_column(String(30), nullable=True)
    """Teinte lue sur la ligne, gardée pour pouvoir remonter à la source."""

    ligne: Mapped[int | None] = mapped_column(Integer, nullable=True)
    """Numéro de ligne dans le classeur — utile pour retrouver un cas."""

    date_import: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    annee_scolaire: Mapped["AnneeScolaire"] = relationship()

    __table_args__ = (
        # Deux personnes portant le même nom dans une même année seraient
        # de toute façon indiscernables pour le rapprochement.
        UniqueConstraint(
            "annee_scolaire_id", "nom", "prenom", name="uq_mouvement_prof_annee_nom"
        ),
    )

    def __repr__(self) -> str:  # pragma: no cover
        return f"<MouvementProf {self.nom} {self.prenom} {self.code}>"
