"""Modèles SQLAlchemy : Envoi et LigneEnvoi — ce qui est parti, et quand.

## Le manque que ça comble

Le programme produit des fichiers — KoXo, PMB, CardStudio — et pour
Sodexo il ne produit rien du tout : le CSV naît d'un classeur Google.
Dans les deux cas, une fois le fichier déposé chez le destinataire,
**plus rien ne s'en souvient**.

La question qui revient chaque semaine est pourtant celle-là : *« qu'est-ce
qui a bougé depuis la dernière fois que j'ai envoyé ? »* Sans réponse, on
renvoie tout le monde à chaque fois — ce qui, chez Sodexo, refait des
comptes qui existent, et chez CardStudio réimprime des cartes déjà faites.

Un envoi garde donc **la liste de ce qu'il contenait**, personne par
personne et classe par classe. Comparer cette liste à l'état du jour
donne exactement les trois nombres qu'on cherche : qui est entré, qui est
sorti, qui a changé de classe.

## Déclaré, pas deviné

Pour les systèmes que le programme alimente, l'envoi s'enregistre au
moment où le fichier est produit. Pour Sodexo, le programme ne fabrique
rien : c'est l'utilisateur qui **déclare** avoir transmis, et le
programme prend acte.

Prétendre le deviner serait pire que ne rien savoir : un envoi supposé
qui n'a pas eu lieu fait croire que la restauration est à jour.

## Ce que ce n'est pas

Ce n'est ni un journal, ni une sauvegarde. Le journal dit *qu'une action
a eu lieu* ; l'envoi dit *ce que le destinataire a reçu*. Les deux se
ressemblent le jour où on les écrit et divergent dès le lendemain, quand
un élève change de classe sans que rien ne soit renvoyé.
"""
from __future__ import annotations

from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Integer, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from backend.database import Base

SYSTEMES_DESTINATAIRES = (
    "sodexo",
    "cardstudio",
    "koxo",
    "pmb",
    "jpm",
    "google",
)
"""Ceux à qui l'on transmet quelque chose.

Google y figure bien qu'il ait une API : un export CSV de comptes reste
un envoi, et savoir quand le dernier est parti a la même valeur.
"""


class Envoi(Base):
    __tablename__ = "envoi"

    id: Mapped[int] = mapped_column(primary_key=True)

    systeme: Mapped[str] = mapped_column(String(20), index=True)
    """Une valeur de `SYSTEMES_DESTINATAIRES`."""

    annee_scolaire_id: Mapped[int] = mapped_column(
        ForeignKey("annee_scolaire.id"), index=True
    )

    envoye_le: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow, index=True
    )

    nb_lignes: Mapped[int] = mapped_column(Integer, default=0)

    nom_fichier: Mapped[str | None] = mapped_column(String(200), nullable=True)
    """Le fichier produit, quand il y en a un. Vide pour un envoi déclaré."""

    declare: Mapped[bool] = mapped_column(default=False)
    """Vrai quand l'utilisateur a dit « c'est parti » sans que le
    programme ait fabriqué le fichier — le cas de Sodexo, dont le CSV naît
    d'un classeur Google. La distinction se voit à l'écran : un envoi
    déclaré vaut ce que vaut la parole de celui qui l'a déclaré."""

    note: Mapped[str | None] = mapped_column(String(300), nullable=True)

    lignes: Mapped[list["LigneEnvoi"]] = relationship(
        back_populates="envoi", cascade="all, delete-orphan"
    )

    def __repr__(self) -> str:  # pragma: no cover
        return f"<Envoi {self.systeme} {self.envoye_le:%d/%m/%Y} {self.nb_lignes}>"


class LigneEnvoi(Base):
    __tablename__ = "ligne_envoi"

    id: Mapped[int] = mapped_column(primary_key=True)

    envoi_id: Mapped[int] = mapped_column(
        ForeignKey("envoi.id", ondelete="CASCADE"), index=True
    )
    envoi: Mapped["Envoi"] = relationship(back_populates="lignes")

    personne_id: Mapped[int] = mapped_column(
        ForeignKey("personne.id", ondelete="CASCADE"), index=True
    )

    classe: Mapped[str | None] = mapped_column(String(30), nullable=True)
    """La classe telle qu'elle est partie.

    C'est elle qui rend le « a changé de classe » calculable : sans elle,
    on ne saurait dire que d'un élève il est parti ou arrivé, jamais qu'il
    a bougé.
    """

    def __repr__(self) -> str:  # pragma: no cover
        return f"<LigneEnvoi {self.personne_id} {self.classe}>"
