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

from sqlalchemy import DateTime, Integer, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from backend.database import Base


class LoginReserve(Base):
    __tablename__ = "login_reserve"

    id: Mapped[int] = mapped_column(primary_key=True)

    login: Mapped[str] = mapped_column(String(50), index=True)
    """L'identifiant retenu.

    Pas unique : deux bases KoXo peuvent détenir le même identifiant pour
    deux personnes. C'est `(login, badge)` qui l'est — un constat par
    titulaire.
    """

    source: Mapped[str] = mapped_column(String(30), default="amorcage_koxo")
    """D'où il a été constaté : `amorcage_koxo`, `controle_koxo`."""

    badge: Mapped[int | None] = mapped_column(Integer, nullable=True, index=True)
    """L'ID unique que la source associait à cet identifiant, quand elle en
    donnait un d'exploitable.

    C'est ce qui permet de distinguer deux situations que rien ne sépare
    autrement : un identifiant orphelin, qu'on peut rendre — et un
    identifiant que **deux bases KoXo distinctes** attribuent chacune à
    quelqu'un. L'établissement tient un serveur par site ; un frère au
    lycée et une sœur au collège portent légitimement `lbernard` chacun
    dans sa base. Le référentiel, lui, n'en garde qu'un. Ce n'est pas un
    défaut à corriger, et vouloir le corriger casserait l'autre."""

    site: Mapped[str | None] = mapped_column(String(20), nullable=True, index=True)
    """La base d'où vient le constat — le nom du site.

    Sans elle, l'export reprenait un identifiant constaté sans regarder
    d'où il venait. Lou-Ann BERNARD tient `lbernard` dans la base de SU ;
    montée au lycée, elle figure dans l'export de NDK, où `lbernard`
    appartient à Liam BERNARD. La création a échoué sur l'annuaire, sept
    élèves dans ce cas — tous des montants de 3e en 2nde.

    Un identifiant constaté ne fait autorité que **dans sa propre base**.
    """

    nom: Mapped[str | None] = mapped_column(String(120), nullable=True)
    prenom: Mapped[str | None] = mapped_column(String(120), nullable=True)

    motif: Mapped[str | None] = mapped_column(String(300), nullable=True)
    """Pourquoi la ligne n'a pas pu être chargée — c'est ce qu'il faudra
    corriger dans la source pour lever la réservation proprement."""

    date_constat: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    __table_args__ = (
        UniqueConstraint("login", "badge", name="uq_login_reserve_login_badge"),
    )

    def __repr__(self) -> str:  # pragma: no cover
        return f"<LoginReserve {self.login} ({self.source})>"
