"""Modèles SQLAlchemy : le dernier relevé de la flotte, et le journal du parc.

## Pourquoi garder le relevé Google

L'inventaire ne se fait pas à la main : les 570 machines existent déjà dans
la console Google, avec leur numéro de série, leur unité d'organisation,
leur étiquette et leur emplacement. Les relire à chaque ouverture d'écran
coûte une dizaine de secondes et suppose le réseau ; les garder permet
d'ouvrir le parc tout de suite, et de dire **de quand date** ce qu'on voit.

`AppareilGoogle` est donc une copie, jamais une source : elle est écrasée
à chaque relevé, et ce que l'établissement a décidé d'une machine vit
dans `SuiviChromebook`.

## Pourquoi un journal

Le suivi ne garde que le dernier état : à qui la machine est confiée
aujourd'hui. Il ne sait pas dire qu'elle était chez quelqu'un d'autre le
mois dernier, ni pourquoi elle a changé de mains — et c'est la question
qu'on se pose quand un prof revient avec « ma machine d'avant marchait
mieux ». Chaque geste du parc (remise, reprise, échange, panne, prêt d'un
chargeur, étiquette écrite dans Google) laisse donc une ligne, qu'on ne
modifie jamais.
"""
from __future__ import annotations

from datetime import date, datetime

from sqlalchemy import Boolean, Date, DateTime, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from backend.database import Base

RAISONS = {
    "panne": "Panne",
    "casse": "Casse (chute, écran fêlé…)",
    "perte_vol": "Perte ou vol",
    "renouvellement": "Renouvellement (machine ancienne, trop lente)",
    "arrivee": "Arrivée d'un personnel",
    "remplacement": "Remplaçant ou stagiaire",
    "pret_temporaire": "Prêt temporaire",
    "depart": "Départ de l'établissement",
    "erreur": "Correction d'une erreur",
    "autre": "Autre",
}
"""Pourquoi une machine change de mains. Liste fermée, pour pouvoir compter
plus tard — combien de casses cette année — et une précision libre à côté
pour ce que la liste ne dit pas."""

GESTES = (
    "remise",        # une machine du stock confiée à quelqu'un ou à une salle
    "reprise",       # une machine rendue : au stock, en panne ou réformée
    "echange",       # les deux à la fois, liés par `autre_serie`
    "panne",
    "reparation",
    "prelevement",
    "reforme",
    "entree_stock",  # une machine ou un accessoire qui entre dans l'inventaire
    "pret",
    "don",
    "retour",
    "google",        # une étiquette écrite dans la console
    "pointage",      # vue lors d'un inventaire, et ce qu'on a constaté
)


class AppareilGoogle(Base):
    """Une machine telle que Google la décrivait au dernier relevé."""

    __tablename__ = "appareil_google"

    id: Mapped[int] = mapped_column(primary_key=True)
    serie: Mapped[str] = mapped_column(String(80), unique=True, index=True)
    device_id: Mapped[str | None] = mapped_column(String(80), nullable=True)
    """L'identifiant interne de Google : c'est lui, et non le numéro de
    série, qu'il faut pour écrire l'étiquette."""

    modele: Mapped[str | None] = mapped_column(String(120), nullable=True)
    ou: Mapped[str | None] = mapped_column(String(300), nullable=True)
    statut: Mapped[str | None] = mapped_column(String(30), nullable=True)
    etiquette: Mapped[str | None] = mapped_column(String(200), nullable=True)
    emplacement: Mapped[str | None] = mapped_column(String(200), nullable=True)
    derniers_utilisateurs: Mapped[str | None] = mapped_column(Text, nullable=True)
    """Adresses séparées par des virgules, la plus récente d'abord."""
    derniere_synchro: Mapped[str | None] = mapped_column(String(40), nullable=True)
    fin_maj: Mapped[date | None] = mapped_column(Date, nullable=True)
    """Date au-delà de laquelle Chrome OS ne la met plus à jour."""

    present: Mapped[bool] = mapped_column(Boolean, default=True)
    """Faux quand le dernier relevé ne l'a plus trouvée : supprimée de la
    console. On la garde, parce que le suivi peut encore la nommer."""
    lu_le: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)


class MouvementMateriel(Base):
    """Un geste du parc. Une ligne écrite n'est jamais modifiée."""

    __tablename__ = "mouvement_materiel"

    id: Mapped[int] = mapped_column(primary_key=True)
    quand: Mapped[datetime] = mapped_column(DateTime, default=datetime.now, index=True)
    """Heure locale : le journal se lit en heure de l'établissement."""

    objet: Mapped[str] = mapped_column(String(20), default="chromebook")
    """`chromebook` ou `accessoire`."""
    serie: Mapped[str] = mapped_column(String(80), index=True)
    geste: Mapped[str] = mapped_column(String(20))
    """Une valeur parmi `GESTES`."""

    de: Mapped[str | None] = mapped_column(String(200), nullable=True)
    """D'où elle vient : une adresse, une étiquette de salle, `stock`."""
    vers: Mapped[str | None] = mapped_column(String(200), nullable=True)
    """Où elle va : une adresse, une salle, `stock`, `hs`, `reforme`."""

    raison: Mapped[str | None] = mapped_column(String(30), nullable=True)
    """Une clé de `RAISONS`."""
    precision: Mapped[str | None] = mapped_column(String(500), nullable=True)

    autre_serie: Mapped[str | None] = mapped_column(String(80), nullable=True)
    """Dans un échange, l'autre machine — c'est ce qui permet de dire
    « remplacée par » et « a remplacé »."""

    google: Mapped[str | None] = mapped_column(String(300), nullable=True)
    """Ce qu'il est advenu de l'étiquette dans Google : écrite, ou pourquoi
    elle ne l'a pas été."""
