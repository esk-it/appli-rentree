"""Modèle SQLAlchemy : LoginReserve — un identifiant vu ailleurs qu'ici.

## Pourquoi cette table existe

L'unicité d'un identifiant se vérifie dans le **référentiel** : avant d'en
attribuer un nouveau, le programme regarde si une `Personne` le porte déjà.
Il n'interroge pas KoXo — il ne le peut pas, KoXo n'expose pas d'API.

Ce contrôle est sain tant que le référentiel reflète KoXo, ce que
l'amorçage est chargé d'obtenir. Mais l'amorçage **rejette** les lignes
qu'il ne sait pas rattacher : badge absent, badge non entier, nom
manquant. Ces comptes-là restent alors invisibles, et leur identifiant
paraît libre.

Le premier entrant dont le nom produit le même identifiant se le voit
attribuer, et le titulaire historique récupère un suffixe. C'est arrivé :
l'ID unique d'une élève valait `llesaout2` au lieu de son badge, sa ligne
d'amorçage a été rejetée, et son identifiant `llesaout` est parti à une
homonyme entrante.

## Ce que la table retient

Un identifiant **constaté dans une source externe** que le référentiel n'a
pas su rattacher à une personne. Il est réservé : `login_est_libre` le
refuse, exactement comme s'il était porté.

La réservation tombe d'elle-même le jour où la personne entre au
référentiel avec cet identifiant — l'amorçage la lève alors, puisque la
`Personne` prend le relais.

Le nom et le prénom sont gardés tels que la source les écrivait : ils ne
servent pas au rapprochement, seulement à dire de qui il s'agit quand on
demande pourquoi un identifiant est refusé.
"""
from __future__ import annotations

from datetime import datetime

from sqlalchemy import DateTime, String
from sqlalchemy.orm import Mapped, mapped_column

from backend.database import Base


class LoginReserve(Base):
    __tablename__ = "login_reserve"

    id: Mapped[int] = mapped_column(primary_key=True)

    login: Mapped[str] = mapped_column(String(50), unique=True, index=True)
    """L'identifiant réservé. Unique : une seule raison suffit."""

    source: Mapped[str] = mapped_column(String(30), default="amorcage_koxo")
    """D'où il a été constaté. `amorcage_koxo` pour l'instant."""

    nom: Mapped[str | None] = mapped_column(String(120), nullable=True)
    prenom: Mapped[str | None] = mapped_column(String(120), nullable=True)

    motif: Mapped[str | None] = mapped_column(String(300), nullable=True)
    """Pourquoi la ligne n'a pas pu être chargée — c'est ce qu'il faudra
    corriger dans la source pour lever la réservation proprement."""

    date_constat: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    def __repr__(self) -> str:  # pragma: no cover
        return f"<LoginReserve {self.login} ({self.source})>"
