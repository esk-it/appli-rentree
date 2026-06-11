"""Modèle SQLAlchemy : Etablissement.

Représente un des 3 (ou 4 à terme) établissements de l'ensemble scolaire :
- SU = Collège Sainte-Ursule (code Charlemagne 02-COL)
- NDK_LY = L.E.G.T. Notre-Dame du Kreisker (03-LY)
- NDK_LP = L.P. Notre-Dame du Kreisker (04-LP)
- NDE = Notre-Dame d'Espérance (code à confirmer à la première inclusion dans l'export)
"""
from __future__ import annotations

from sqlalchemy import String
from sqlalchemy.orm import Mapped, mapped_column

from backend.database import Base


class Etablissement(Base):
    __tablename__ = "etablissement"

    id: Mapped[int] = mapped_column(primary_key=True)
    code_charlemagne: Mapped[str] = mapped_column(String(20), unique=True, index=True)
    code_court: Mapped[str] = mapped_column(String(10))
    nom_long: Mapped[str] = mapped_column(String(200))
    type: Mapped[str] = mapped_column(String(20))  # college | lycee_general | lycee_pro | inconnu

    def __repr__(self) -> str:  # pragma: no cover
        return f"<Etablissement {self.code_court} ({self.code_charlemagne})>"
