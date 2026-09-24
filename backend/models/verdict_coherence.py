"""Modèle SQLAlchemy : VerdictCoherence — ce qu'un croisement a constaté.

## Pourquoi garder le résultat

La Concordance croise Charlemagne, le référentiel, Google et KoXo sur
demande : un export à déposer, l'annuaire Google à interroger, une bonne
minute d'attente. Le résultat vivait dans l'écran et mourait avec lui.

Deux endroits le réclamaient pourtant :

- la colonne **Cohérent** du référentiel, qui n'avait le droit d'écrire
  que « Pas vérifié » — annoncer « cohérent » sans avoir comparé ferait
  passer pour vérifié ce que personne n'a regardé ;
- l'écran **Cohérence**, qui dessine les liens entre systèmes et doit
  dire lesquels sont à jour sans relancer le croisement à l'ouverture.

Une ligne par personne **et par système**, plutôt qu'un verdict global :
un croisement sans export KoXo n'a rien constaté de KoXo, et ne doit pas
effacer ce que le croisement d'hier en savait. Chaque lien vieillit à son
rythme, et la date le dit.

## Ce que le verdict n'est pas

Ce n'est pas un cache : personne ne le relit pour éviter un calcul. C'est
une **observation datée**, au même titre qu'un relevé. Un verdict de la
semaine dernière reste affiché — avec son âge — parce qu'un constat vieux
et signalé vaut mieux qu'une case vide qui laisse croire qu'on n'a jamais
regardé.
"""
from __future__ import annotations

from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from backend.database import Base

SYSTEMES_COMPARES = ("charlemagne", "google", "koxo")
"""Les trois systèmes où la cohérence se vérifie.

PMB, Sodexo et CardStudio reçoivent des fichiers mais n'en rendent
aucun : il n'y a rien à comparer. Ils se suivent autrement — Sodexo par
ses envois, CardStudio par les cartes déjà faites. Si PMB rend un jour
un export exploitable, c'est ici qu'il s'ajoutera.
"""

ETATS = ("accord", "ecart", "absent")
"""`absent` n'est pas un écart : la personne n'existe pas dans ce
système. Pour un élève de NDE, qui n'a pas de KoXo, c'est normal ; pour
un élève de SU, c'est un compte à créer. Seul l'écran sait faire la
différence, et il ne le peut que si la base ne les confond pas."""


class VerdictCoherence(Base):
    __tablename__ = "verdict_coherence"
    __table_args__ = (
        UniqueConstraint("personne_id", "systeme", name="uq_verdict_personne_systeme"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)

    personne_id: Mapped[int] = mapped_column(
        ForeignKey("personne.id", ondelete="CASCADE"), index=True
    )

    systeme: Mapped[str] = mapped_column(String(20), index=True)
    """Une valeur de `SYSTEMES_COMPARES`."""

    etat: Mapped[str] = mapped_column(String(10))
    """Une valeur de `ETATS`."""

    genre: Mapped[str | None] = mapped_column(String(40), nullable=True)
    """Le genre d'écart, tel que la Concordance le nomme — `referentiel`,
    `google`, `groupe`, `koxo`… Il dit *quoi* réparer là où l'état ne dit
    que *s'il y a* quelque chose à réparer."""

    attendu: Mapped[str | None] = mapped_column(String(60), nullable=True)
    """Ce que le référentiel dit de la classe."""

    constate: Mapped[str | None] = mapped_column(String(60), nullable=True)
    """Ce que ce système en dit. Les deux côte à côte suffisent à
    comprendre l'écart sans rouvrir le croisement."""

    verifie_le: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, index=True
    )

    def __repr__(self) -> str:  # pragma: no cover
        return f"<VerdictCoherence {self.personne_id} {self.systeme}={self.etat}>"
