"""Modèle SQLAlchemy : Site.

Représente un site physique de l'ensemble scolaire (NDE, NDK, SU) avec
son domaine de messagerie Google Workspace et son préfixe d'unité
d'organisation dans Google Admin.

Le domaine de messagerie est **dérivé du site** — un élève NDE aura son
mail en @ndecleder.fr, un élève NDK ou SU en @lekreisker.fr. Les deux
domaines coexistent dans la même console Google Workspace.
"""
from __future__ import annotations

from sqlalchemy import Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from backend.database import Base


class Site(Base):
    __tablename__ = "site"

    id: Mapped[int] = mapped_column(primary_key=True)
    nom: Mapped[str] = mapped_column(String(20), unique=True, index=True)
    """Code court : NDE, NDK, SU."""

    nom_complet: Mapped[str] = mapped_column(String(150))
    """Ex : Notre-Dame d'Espérance, Notre-Dame du Kreisker, Sainte-Ursule."""

    domaine_mail: Mapped[str] = mapped_column(String(100))
    """Domaine Google Workspace utilisé pour les emails : lekreisker.fr, ndecleder.fr."""

    prefixe_annee_ou: Mapped[str] = mapped_column(String(20))
    """Préfixe utilisé dans le nom des OU annuelles : NDE (donne NDE2026), NDK, SU."""

    numero_ordre: Mapped[int] = mapped_column(Integer)
    """Numéro d'ordre pour l'arborescence OU : 2 (NDE), 3 (NDK), 4 (SU), 7 (Sortis)."""

    def prefixe_racine_ou(self) -> str:
        """`/<numero_ordre>. <nom>` — racine de l'arborescence OU du site."""
        return f"/{self.numero_ordre}. {self.nom}"

    def __repr__(self) -> str:  # pragma: no cover
        return f"<Site {self.nom}>"
