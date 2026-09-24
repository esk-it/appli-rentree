"""Modèle SQLAlchemy : FicheFusionnee — le numéro d'une fiche réunie à une autre.

## Pourquoi une personne peut avoir deux fiches

L'identité d'une personne est sa fiche Charlemagne. Or l'établissement
tient **deux bases** Charlemagne : NDE d'un côté, NDK et SU de l'autre. Une
élève qui passe de la 3e à NDE à la seconde à NDK reçoit une seconde fiche,
un second numéro, un second badge — et le référentiel en faisait deux
personnes.

Constaté en septembre 2026 : les vingt-neuf adresses que l'écran
« Départager » présentait comme disputées par des homonymes étaient
**toutes** une seule personne en deux fiches. Vingt-huit élèves venus de
NDE, et une réinscription à NDK. Pas un seul homonyme.

## Ce que la table retient

La fiche absorbée par une fusion : son numéro, son badge, son
identifiant, et ce qu'elle disait au moment de disparaître. Elle ne décrit
plus personne — la personne, c'est la fiche gardée, vers laquelle
`personne_id` pointe.

Trois usages :

- **Reconnaître l'ancien numéro.** Réingérer l'export NDE de l'an dernier
  ne doit pas recréer la fiche qu'on vient de réunir. L'ingestion passe par
  `backend.services.fusion.personne_par_cle`, qui suit ce renvoi.
- **Garder l'identifiant pris.** Un identifiant n'est jamais recyclé,
  même celui d'une fiche qui n'existe plus : `login_est_libre` le refuse.
- **Pouvoir dire ce qui s'est passé.** `etat_json` garde la fiche telle
  qu'elle était, années comprises : c'est ce qu'il faudrait pour la
  reconstituer si la fusion était une erreur.
"""
from __future__ import annotations

from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from backend.database import Base


class FicheFusionnee(Base):
    __tablename__ = "fiche_fusionnee"

    id: Mapped[int] = mapped_column(primary_key=True)

    personne_id: Mapped[int] = mapped_column(
        ForeignKey("personne.id", ondelete="CASCADE"), index=True
    )
    """La fiche gardée — celle qui décrit la personne désormais."""

    type: Mapped[str] = mapped_column(String(10))
    id_charlemagne: Mapped[int] = mapped_column(Integer, index=True)
    """Le numéro de la fiche absorbée. Avec `type`, l'ancienne clé pivot."""

    badge: Mapped[int] = mapped_column(Integer, index=True)
    login: Mapped[str] = mapped_column(String(50), index=True)
    """L'identifiant de la fiche absorbée. Il reste pris : un identifiant
    n'est jamais recyclé, et celui-ci a pu servir sur un serveur KoXo."""

    nom: Mapped[str] = mapped_column(String(100))
    prenom: Mapped[str] = mapped_column(String(100))
    site: Mapped[str | None] = mapped_column(String(20), nullable=True)
    email_constate: Mapped[str | None] = mapped_column(String(200), nullable=True)

    etat_json: Mapped[str] = mapped_column(Text, default="{}")
    """La fiche absorbée telle qu'elle était, et ses années."""

    fusionnee_le: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    __table_args__ = (
        UniqueConstraint("type", "id_charlemagne", name="uq_fiche_fusionnee_cle"),
    )

    @property
    def cle_pivot(self) -> str:
        return f"{'E' if self.type == 'eleve' else 'A'}{self.id_charlemagne}"

    def __repr__(self) -> str:  # pragma: no cover
        return f"<FicheFusionnee {self.cle_pivot} → personne {self.personne_id}>"
