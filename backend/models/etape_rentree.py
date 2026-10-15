"""Modèle SQLAlchemy : EtapeRentree — où en est une étape de la rentrée.

## Pourquoi le garder

La rentrée se conduit comme un tutoriel : une étape après l'autre, et on
ne passe à la suivante qu'une fois la précédente **validée sur ce qui a
été constaté** (Johann, 15 octobre 2026). Elle s'étale sur trois
semaines, l'application se ferme entre deux : l'avancement doit vivre en
base, pas dans l'écran.

Une ligne par année et par étape. Ce qu'elle garde :

- l'**avant** : les mesures relevées à l'ouverture de l'étape — « 312
  comptes Google à créer » ;
- l'**après** : les mêmes, relevées au moment de la validation — « 0 » ;
- les **gestes** déclarés faits, ceux que le programme ne voit pas (un
  import dans KoXo) ;
- la date de validation, et la raison quand on a validé malgré un écart.

La rentrée suivante, on sait ce qui a été fait, et quand.

## Pourquoi le libellé de l'année, et pas l'année elle-même

La campagne 2027-2028 commence avant que l'année 2027-2028 n'existe :
c'est l'ingestion de l'export Charlemagne (étape 3) qui la crée, comme
elle l'a toujours fait. Créer l'année plus tôt ferait pointer tous les
écrans qui prennent « la plus récente » — Référentiel, étiquettes,
comptes Google — sur une année vide, des semaines durant.
"""
from __future__ import annotations

from datetime import datetime

from sqlalchemy import DateTime, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from backend.database import Base

STATUTS_ETAPE = ("en_cours", "validee", "reportee")
"""`a_faire` n'a pas de ligne : une étape jamais ouverte n'a rien à garder.
`reportee` : une étape qui ne peut pas encore se faire — les professeurs
avant le 1er septembre — et qu'on laisse passer pour avancer."""


class EtapeRentree(Base):
    __tablename__ = "etape_rentree"

    id: Mapped[int] = mapped_column(primary_key=True)
    annee: Mapped[str] = mapped_column(String(9), index=True)
    """Le libellé de la rentrée, « 2027-2028 »."""
    etape: Mapped[str] = mapped_column(String(40))
    statut: Mapped[str] = mapped_column(String(20), default="en_cours")

    avant_json: Mapped[str] = mapped_column(Text, default="{}")
    """`{mesure: {valeur, detail, lu_le}}` à l'ouverture — complété par la
    première lecture de Google pour les mesures qui en dépendent."""
    apres_json: Mapped[str] = mapped_column(Text, default="{}")
    gestes_json: Mapped[str] = mapped_column(Text, default="[]")
    """Les gestes déclarés faits, par identifiant, avec leur heure."""

    ouverte_le: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    validee_le: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    note: Mapped[str | None] = mapped_column(String(500), nullable=True)
    """Pourquoi on a validé malgré un écart, ou reporté."""

    __table_args__ = (
        UniqueConstraint("annee", "etape", name="uq_etape_rentree_annee"),
    )
