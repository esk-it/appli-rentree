"""Modèle SQLAlchemy : Arbitrage — mémoire des décisions humaines.

Chaque décision prise par l'utilisateur sur un cas ambigu ou une
collision de login est enregistrée définitivement et **jamais redemandée**.

Le programme retrouve la décision passée grâce à `cle_cas` — une chaîne
stable qui décrit le contexte de manière déterministe.
"""
from __future__ import annotations

from datetime import datetime

from sqlalchemy import DateTime, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from backend.database import Base


# Types de cas connus
TYPES_CAS = (
    "collision_login",      # login calculé déjà pris
    "homonymie_ingestion",  # deux personnes de mêmes nom+prénom dans le même export
    "rapprochement",        # amorçage : rattacher un compte cible à une Personne
    "qualification",        # amorçage : classer un compte non rattaché
)


class Arbitrage(Base):
    __tablename__ = "arbitrage"

    id: Mapped[int] = mapped_column(primary_key=True)

    type_cas: Mapped[str] = mapped_column(String(30), index=True)
    """Un type parmi TYPES_CAS."""

    cle_cas: Mapped[str] = mapped_column(String(300), unique=True, index=True)
    """Clé déterministe qui identifie le cas — permet le rappel à l'ingestion suivante.
    Ex : `collision_login:jbars:E5292:A60`, `rapprochement:google:jean.dupont@…`."""

    decision: Mapped[str] = mapped_column(String(100))
    """Décision retenue. Valeur libre mais typée par convention selon `type_cas` :
    - collision_login → suffixe adopté (`suffixe:2`) ou `pas_de_conflit`
    - homonymie → `personnes_distinctes` ou `meme_personne`
    - rapprochement → `personne_id:N` ou `nouvelle_personne`
    - qualification → `fantome` / `compte_service` / `doublon` / `personne_reelle`
    """

    contexte_json: Mapped[str] = mapped_column(Text)
    """Contexte sérialisé JSON — utile pour audit et pour reconstruire l'écran de
    consultation ultérieure."""

    date_creation: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    note: Mapped[str | None] = mapped_column(String(500), nullable=True)
    """Note optionnelle laissée par l'utilisateur."""

    def __repr__(self) -> str:  # pragma: no cover
        return f"<Arbitrage {self.type_cas} {self.cle_cas[:40]}>"
