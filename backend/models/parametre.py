"""Modèle SQLAlchemy : Parametre (configuration clé/valeur).

Stocke les paramètres de l'application (domaine email, template OU,
longueur MDP, etc.) sous forme de clé/valeur. La valeur est stockée
en JSON pour supporter des types riches (str, int, bool, list, dict).
"""
from __future__ import annotations

from datetime import datetime

from sqlalchemy import DateTime, String
from sqlalchemy.orm import Mapped, mapped_column

from backend.database import Base


class Parametre(Base):
    __tablename__ = "parametre"

    id: Mapped[int] = mapped_column(primary_key=True)
    cle: Mapped[str] = mapped_column(String(100), unique=True, index=True)
    valeur_json: Mapped[str] = mapped_column(String)
    modifie_le: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow, onupdate=datetime.utcnow
    )
