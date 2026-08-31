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

    ou_sortants: Mapped[str | None] = mapped_column(String(200), nullable=True)
    """OU d'archivage propre à ce site, utilisée **telle quelle**.

    Les conventions diffèrent d'un site à l'autre parce qu'elles se sont
    installées avant le programme : NDE range ses partants dans un
    `/2. NDE/Sortie` unique, sans date. Imposer une règle commune
    obligerait à déplacer l'existant pour rien.

    Vide : le site suit la convention datée, `<racine>/Comptes à supprimer
    au JJ-MM-AAAA`, où la racine vient du paramètre `google.ou_sortants`."""
    """Domaine Google Workspace utilisé pour les emails : lekreisker.fr, ndecleder.fr."""

    prefixe_annee_ou: Mapped[str] = mapped_column(String(20))
    """Préfixe utilisé dans le nom des OU annuelles : NDE (donne NDE2026), NDK, SU."""

    organisation_etiquettes: Mapped[str | None] = mapped_column(
        String(150), nullable=True
    )
    """Ce qu'affiche le bandeau des étiquettes de comptes.

    KoXo y met le nom de l'organisation de son annuaire — « OGEC PAUL
    AURELIEN » pour NDK et SU. NDE n'a pas d'annuaire, mais son étiquette
    doit porter le sien : « OGEC NOTRE DAME D ESPERANCE ». Ce n'est ni le
    nom court du site ni son nom complet, d'où sa propre colonne."""

    base_koxo: Mapped[str | None] = mapped_column(String(20), nullable=True)
    """Le serveur KoXo où les élèves de ce site ont un compte. `None` quand
    le site n'en a pas.

    Ce n'est pas une redondance avec `nom` : l'établissement tient **un
    serveur par domaine Active Directory**, pas un par site. NDK et SU ont
    chacun le leur ; NDE n'en a aucun, ses élèves n'ayant qu'un compte
    Google.

    De là découle la seule chose qui compte pour les identifiants : deux
    personnes ne se gênent que si elles partagent un serveur. Sans cette
    colonne, l'arrivée de NDE levait cinquante-six collisions d'identifiant
    dont aucune n'était réelle — ses élèves étaient comparés à ceux de deux
    annuaires où ils n'ont pas de compte."""

    numero_ordre: Mapped[int] = mapped_column(Integer)
    """Numéro d'ordre pour l'arborescence OU : 2 (NDE), 3 (NDK), 4 (SU), 7 (Sortis)."""

    def prefixe_racine_ou(self) -> str:
        """`/<numero_ordre>. <nom>` — racine de l'arborescence OU du site."""
        return f"/{self.numero_ordre}. {self.nom}"

    def __repr__(self) -> str:  # pragma: no cover
        return f"<Site {self.nom}>"
