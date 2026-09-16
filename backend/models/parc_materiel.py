"""Modèles SQLAlchemy : l'état des machines, leurs pannes, les accessoires.

## Pourquoi une machine morte reste en base

Un Chromebook hors service n'est pas un déchet : c'est une réserve
d'organes sains. Deux machines HS — l'une à la batterie, l'autre au clavier
— en font une qui marche. C'est le geste courant dans un parc scolaire, et
il ne se décide qu'à partir d'un inventaire des **pannes**.

D'où la règle qui commande tout ce module : une panne désigne un
**organe**, pris dans une liste fermée. Une note libre — « écran cassé »
ici, « problème d'affichage » là — ne se croise pas, et aucun écran ne
pourra jamais répondre à « de quoi puis-je en remonter une ».

## Pourquoi la panne est une table et non un champ

Une machine peut avoir trois pannes, et c'est le nombre et la nature qui
décident si elle est réparable ou si elle devient donneuse. Une machine
dont la seule panne est la batterie se répare avec la batterie d'une
machine dont la seule panne est le clavier.

## Le prélèvement écrit des deux côtés

Prendre le clavier de A pour réparer B résout la panne « clavier » de B
**et** en crée une chez A. La seconde écriture est celle qu'on oublie, et
l'oublier fait mentir la réserve au bout de quelques mois. `prelevee_pour`
relie les deux, pour qu'on puisse toujours dire où est parti l'organe.

## Accessoire n'est pas machine, prêt n'est pas attribution

Une machine est **attribuée** — pour l'année, à un élève, c'est durable. Un
chargeur est **prêté** : il est censé revenir, et ce qui intéresse est
justement ce qui n'est pas revenu. D'où une date de retour prévue, et une
date de rendu qui reste vide tant que l'objet est dehors.

Le modèle dit « accessoire » et non « chargeur » : le stock suivant sera
fait de souris ou d'adaptateurs, et ce serait refaire le même travail.
"""
from __future__ import annotations

from datetime import date, datetime

from sqlalchemy import Date, DateTime, String
from sqlalchemy.orm import Mapped, mapped_column

from backend.database import Base

ETATS_MACHINE = ("en_service", "en_stock", "hs", "reforme")
"""`en_service` : confiée à quelqu'un · `en_stock` : disponible ·
`hs` : en panne, gardée comme réserve de pièces · `reforme` : jetée, mais
la trace demeure — savoir qu'une machine a existé évite de la chercher."""

ORGANES = (
    "ecran",
    "charniere",
    "clavier",
    "trackpad",
    "batterie",
    "port_charge",
    "haut_parleur",
    "webcam",
    "carte_mere",
    "coque",
    "autre",
)
"""Les charnières et les écrans d'abord : sur un parc scolaire, ce sont eux
qui cassent. `carte_mere` ferme le sort d'une machine — rien ne se prélève
d'utile au-delà. `autre` existe pour ne pas forcer une classification
fausse, mais ne se croise pas : deux « autre » ne font pas une pièce."""

RESOLUTIONS = ("reparee", "piece_prelevee", "abandonnee")
"""Comment une panne a cessé d'en être une. `piece_prelevee` dit que
l'organe est parti ailleurs — la machine n'est pas réparée, elle est
donneuse."""

ETATS_ACCESSOIRE = ("en_stock", "prete", "hs", "reforme")

TYPES_ACCESSOIRE = ("chargeur", "souris", "adaptateur", "cable", "housse", "autre")


class PanneChromebook(Base):
    """Un organe mort sur une machine. Plusieurs par machine."""

    __tablename__ = "panne_chromebook"

    id: Mapped[int] = mapped_column(primary_key=True)

    serie: Mapped[str] = mapped_column(String(80), index=True)
    """Numéro de série de la machine touchée — la même clé que le suivi.

    Pas de clé étrangère : une panne peut être constatée sur une machine
    que le suivi ne connaît pas encore, et refuser la saisie à ce
    moment-là ferait perdre le constat."""

    organe: Mapped[str] = mapped_column(String(30), index=True)
    """Une valeur parmi `ORGANES`."""

    constatee_le: Mapped[date | None] = mapped_column(Date, nullable=True)

    note: Mapped[str | None] = mapped_column(String(500), nullable=True)
    """Le détail que l'organe ne dit pas — « charnière droite », « ne tient
    plus la charge au-delà d'une heure »."""

    resolue_le: Mapped[date | None] = mapped_column(Date, nullable=True)
    resolution: Mapped[str | None] = mapped_column(String(20), nullable=True)
    """Une valeur parmi `RESOLUTIONS`, ou `None` tant que la panne court."""

    prelevee_pour: Mapped[str | None] = mapped_column(String(80), nullable=True)
    """Série de la machine qui a reçu l'organe, quand cette panne est née
    d'un prélèvement. C'est ce qui permet de remonter le fil."""

    date_creation: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    @property
    def ouverte(self) -> bool:
        return self.resolue_le is None

    def __repr__(self) -> str:  # pragma: no cover
        etat = "ouverte" if self.ouverte else self.resolution
        return f"<Panne {self.serie} {self.organe} {etat}>"


class Accessoire(Base):
    """Un objet prêtable, identifié par son numéro de série."""

    __tablename__ = "accessoire"

    id: Mapped[int] = mapped_column(primary_key=True)

    serie: Mapped[str] = mapped_column(String(80), unique=True, index=True)
    """Le numéro de série du fabricant. Aucune étiquette à coller : les
    chargeurs en portent un, et c'est la même identité que les machines."""

    type: Mapped[str] = mapped_column(String(20), default="chargeur")
    """Une valeur parmi `TYPES_ACCESSOIRE`."""

    etat: Mapped[str] = mapped_column(String(20), default="en_stock")
    """Une valeur parmi `ETATS_ACCESSOIRE`. `prete` se déduit d'un prêt en
    cours, mais reste écrit ici : la question « combien m'en reste-t-il »
    doit se répondre sans parcourir l'historique des prêts."""

    note: Mapped[str | None] = mapped_column(String(500), nullable=True)

    date_derniere_maj: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow, onupdate=datetime.utcnow
    )

    def __repr__(self) -> str:  # pragma: no cover
        return f"<Accessoire {self.type} {self.serie} {self.etat}>"


class PretAccessoire(Base):
    """Un accessoire sorti, et ce qu'on attend de son retour."""

    __tablename__ = "pret_accessoire"

    id: Mapped[int] = mapped_column(primary_key=True)

    accessoire_serie: Mapped[str] = mapped_column(String(80), index=True)

    prete_a: Mapped[str] = mapped_column(String(200))
    """Qui l'a — une adresse, un nom, une classe. Volontairement libre : on
    prête aussi bien à un élève qu'à un professeur ou à une salle."""

    prete_le: Mapped[date | None] = mapped_column(Date, nullable=True)
    retour_prevu_le: Mapped[date | None] = mapped_column(Date, nullable=True)
    """C'est elle qui fait la différence avec une attribution : un prêt a
    une échéance, et l'écran met en tête ce qui l'a dépassée."""

    rendu_le: Mapped[date | None] = mapped_column(Date, nullable=True)
    """Vide tant que l'objet est dehors."""

    note: Mapped[str | None] = mapped_column(String(500), nullable=True)

    date_creation: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    @property
    def en_cours(self) -> bool:
        return self.rendu_le is None

    def __repr__(self) -> str:  # pragma: no cover
        return f"<Pret {self.accessoire_serie} → {self.prete_a}>"
