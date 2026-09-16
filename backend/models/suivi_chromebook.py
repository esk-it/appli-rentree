"""Modèle SQLAlchemy : SuiviChromebook — ce qui a été fait d'une machine.

Google dit où en est l'étiquette d'un appareil ; il ne dit pas si la
machine a été **rendue**, ni à qui elle vient d'être **confiée**. Ces deux
gestes sont physiques : ils précèdent de plusieurs jours, parfois de
semaines, la mise à jour de l'étiquette dans la console.

Sans trace, la liste des machines à réclamer reste identique du premier au
dernier jour de la rentrée, et rien ne distingue celle qu'on attend
toujours de celle qu'on a récupérée ce matin.

La clé est le **numéro de série** : il ne change pas, contrairement à
l'étiquette, à l'unité d'organisation ou au porteur.

Cette table ne remplace pas Google — elle note ce qui s'est passé entre
deux relevés, et l'écran signale l'écart quand l'étiquette n'a pas suivi.
"""
from __future__ import annotations

from datetime import date, datetime

from sqlalchemy import Date, DateTime, String
from sqlalchemy.orm import Mapped, mapped_column

from backend.database import Base


class SuiviChromebook(Base):
    __tablename__ = "suivi_chromebook"

    id: Mapped[int] = mapped_column(primary_key=True)

    serie: Mapped[str] = mapped_column(String(80), unique=True, index=True)
    """Numéro de série de l'appareil — la seule identité stable."""

    recupere_le: Mapped[date | None] = mapped_column(Date, nullable=True)
    """Date à laquelle la machine a été physiquement rendue."""

    recupere_de: Mapped[str | None] = mapped_column(String(200), nullable=True)
    """Adresse du partant qui la détenait, gardée pour l'historique."""

    attribue_a: Mapped[str | None] = mapped_column(String(200), nullable=True)
    """Adresse de la personne à qui la machine vient d'être confiée."""

    attribue_le: Mapped[date | None] = mapped_column(Date, nullable=True)

    note: Mapped[str | None] = mapped_column(String(500), nullable=True)

    etat: Mapped[str] = mapped_column(String(20), default="en_service")
    """Une valeur parmi `ETATS_MACHINE` — voir `parc_materiel`.

    Le suivi ne notait que des mouvements : rendue, confiée. Il ne savait
    pas dire si une machine est disponible, morte, ou simplement en
    circulation — donc ni « combien m'en reste-t-il en stock », ni
    « lesquelles puis-je démonter ». La valeur par défaut est
    `en_service` : c'est l'état des machines déjà suivies au moment où la
    colonne apparaît, et le seul qui ne prétende rien de neuf."""

    etat_depuis: Mapped[date | None] = mapped_column(Date, nullable=True)
    """Depuis quand elle est dans cet état. Une machine en stock depuis
    deux ans et une rentrée hier ne posent pas la même question."""

    date_derniere_maj: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow, onupdate=datetime.utcnow
    )

    def __repr__(self) -> str:  # pragma: no cover
        etat = "rendue" if self.recupere_le else "en circulation"
        return f"<SuiviChromebook {self.serie} {etat}>"
