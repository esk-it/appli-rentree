"""Un mot de passe gardé sous clé, jamais en clair.

## Ce que cette table contient — et ce qu'elle ne contient pas

Elle garde des mots de passe **chiffrés**. Ni le mot de passe maître ni la
clé qui en dérive n'y figurent : la clé se recalcule à chaque ouverture, à
partir de ce que l'utilisateur saisit, et ne vit qu'en mémoire.

La conséquence est double, et elle est voulue. Le fichier de base, copié
seul, ne vaut rien — c'est ce qui rend le coffre acceptable sur un poste de
travail. Et un mot de passe maître oublié rend le coffre définitivement
illisible : il n'existe aucun moyen de le retrouver, sinon le coffre ne
protégerait rien.

## Pourquoi du chiffrement et non une empreinte

On veut **réafficher** ces mots de passe, pas les vérifier. Une empreinte
répondrait « c'est bien celui-là » sans jamais le rendre. Il faut donc un
chiffrement réversible, et il faut qu'il soit authentifié : AES-GCM refuse
de déchiffrer une donnée modifiée plutôt que de rendre n'importe quoi.

## Un enregistrement par personne, par cible et par base

Le même mot de passe sert aujourd'hui à KoXo et à Google, mais rien ne le
garantit demain, et un professeur peut en avoir un différent dans chacun
des deux serveurs KoXo. La clé porte donc les trois.
"""
from __future__ import annotations

from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Integer, LargeBinary, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from backend.database import Base


class SecretConserve(Base):
    __tablename__ = "secret_conserve"

    id: Mapped[int] = mapped_column(primary_key=True)

    personne_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("personne.id"), index=True
    )

    cible: Mapped[str] = mapped_column(String(20), default="koxo")
    """`koxo` ou `google`. Le mot de passe est le même aujourd'hui ; le
    distinguer coûte une colonne et évite d'avoir à démêler plus tard."""

    site: Mapped[str | None] = mapped_column(String(20), nullable=True)
    """La base dont vient ce mot de passe, quand il y en a plusieurs."""

    nonce: Mapped[bytes] = mapped_column(LargeBinary(12))
    """Tiré au hasard pour chaque enregistrement. Réutiliser un nonce avec
    la même clé casserait AES-GCM ; il est donc par enregistrement, jamais
    par coffre."""

    chiffre: Mapped[bytes] = mapped_column(LargeBinary)

    origine: Mapped[str] = mapped_column(String(20), default="koxo")
    """`koxo` — relevé dans un export — ou `genere` — fabriqué par le
    programme pour un site qui n'a pas de KoXo. La distinction compte : un
    mot de passe généré n'existe nulle part ailleurs, et le perdre oblige à
    réinitialiser le compte."""

    date_maj: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow, onupdate=datetime.utcnow
    )

    __table_args__ = (
        UniqueConstraint(
            "personne_id", "cible", "site", name="uq_secret_personne_cible_site"
        ),
    )

    def __repr__(self) -> str:  # pragma: no cover
        return f"<SecretConserve personne={self.personne_id} {self.cible}>"
