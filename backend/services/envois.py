"""Ce qui est parti chez qui, et ce qui a bougé depuis.

Un envoi garde la liste de ce qu'il contenait. Comparer cette liste à
l'état du jour donne les trois seuls nombres qui intéressent : qui est
entré, qui est sorti, qui a changé de classe.

## Trois nombres, et pas un de plus

On pourrait comparer davantage — le régime, le nom d'usage, l'adresse.
Ce serait du bruit : le destinataire d'un envoi de rentrée agit sur
*qui mange où*, pas sur l'orthographe d'un prénom. Les trois mouvements
d'ici sont ceux qui lui font faire quelque chose.

## Pourquoi par classe

Parce que c'est l'unité du geste. Chez Sodexo on ouvre une classe et on
la corrige ; personne ne parcourt mille huit cents lignes. Une classe
sans changement n'a pas à être rouverte, et le dire économise l'essentiel
du travail.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime

from sqlalchemy import select
from sqlalchemy.orm import Session

from backend.models import Envoi, LigneEnvoi, Personne, Snapshot


@dataclass
class MouvementClasse:
    """Ce qui a bougé dans une classe depuis le dernier envoi."""

    classe: str
    nb_actuel: int
    entrants: list[str] = field(default_factory=list)
    sortants: list[str] = field(default_factory=list)
    arrives_d_ailleurs: list[str] = field(default_factory=list)
    """Déjà transmis, mais dans une autre classe — il a changé, pas rejoint."""

    @property
    def nb_changements(self) -> int:
        return len(self.entrants) + len(self.sortants) + len(self.arrives_d_ailleurs)


@dataclass
class EtatEnvoi:
    """Le dernier envoi d'un système, et l'écart avec aujourd'hui."""

    systeme: str
    envoye_le: datetime | None = None
    declare: bool = False
    nom_fichier: str | None = None
    nb_envoyes: int = 0
    nb_actuels: int = 0
    classes: list[MouvementClasse] = field(default_factory=list)

    @property
    def jamais_envoye(self) -> bool:
        return self.envoye_le is None

    @property
    def nb_changements(self) -> int:
        return sum(c.nb_changements for c in self.classes)

    @property
    def nb_classes_touchees(self) -> int:
        return sum(1 for c in self.classes if c.nb_changements)


def _inscrits(session: Session, annee_id: int) -> dict[int, str]:
    """Chaque élève de l'année et sa classe, la plus récemment ingérée."""
    courant: dict[int, tuple[datetime, str | None]] = {}
    q = (
        session.query(Snapshot.personne_id, Snapshot.classe, Snapshot.date_ingestion)
        .join(Personne, Personne.id == Snapshot.personne_id)
        .filter(Snapshot.annee_scolaire_id == annee_id, Personne.type == "eleve")
    )
    for pid, classe, quand in q:
        prec = courant.get(pid)
        if prec is None or (quand and prec[0] and quand > prec[0]):
            courant[pid] = (quand, classe)
    return {pid: c for pid, (_, c) in courant.items() if c}


def enregistrer(
    session: Session,
    *,
    systeme: str,
    annee_id: int,
    lignes: dict[int, str] | None = None,
    nom_fichier: str | None = None,
    declare: bool = False,
    note: str | None = None,
) -> Envoi:
    """Prend acte de ce qui vient de partir.

    `lignes` est `{personne_id: classe}`. Absent, l'état du jour est pris
    — c'est le cas d'un envoi déclaré, où l'utilisateur dit avoir
    transmis ce que le programme montrait à l'écran.
    """
    contenu = _inscrits(session, annee_id) if lignes is None else lignes

    envoi = Envoi(
        systeme=systeme,
        annee_scolaire_id=annee_id,
        envoye_le=datetime.utcnow(),
        nb_lignes=len(contenu),
        nom_fichier=nom_fichier,
        declare=declare,
        note=note,
    )
    session.add(envoi)
    session.flush()
    for pid, classe in contenu.items():
        session.add(LigneEnvoi(envoi_id=envoi.id, personne_id=pid, classe=classe))
    session.commit()
    return envoi


def dernier(session: Session, systeme: str, annee_id: int) -> Envoi | None:
    return (
        session.execute(
            select(Envoi)
            .where(Envoi.systeme == systeme, Envoi.annee_scolaire_id == annee_id)
            .order_by(Envoi.envoye_le.desc(), Envoi.id.desc())
            .limit(1)
        )
        .scalars()
        .first()
    )


def etat(session: Session, systeme: str, annee_id: int) -> EtatEnvoi:
    """Le dernier envoi, et classe par classe ce qui a bougé depuis.

    Sans envoi précédent, toutes les classes comptent leurs élèves comme
    des entrants : c'est exact, et c'est ce qu'un premier envoi contiendra.
    """
    actuels = _inscrits(session, annee_id)
    noms = {
        p.id: f"{p.prenom} {p.nom}".strip()
        for p in session.query(Personne).filter(Personne.id.in_(actuels)).all()
    } if actuels else {}

    e = dernier(session, systeme, annee_id)
    resultat = EtatEnvoi(systeme=systeme, nb_actuels=len(actuels))
    if e is not None:
        resultat.envoye_le = e.envoye_le
        resultat.declare = e.declare
        resultat.nom_fichier = e.nom_fichier
        resultat.nb_envoyes = e.nb_lignes

    envoyes: dict[int, str | None] = {}
    if e is not None:
        for l in session.query(LigneEnvoi).filter(LigneEnvoi.envoi_id == e.id):
            envoyes[l.personne_id] = l.classe
        manquants = [pid for pid in envoyes if pid not in noms]
        if manquants:
            for p in session.query(Personne).filter(Personne.id.in_(manquants)):
                noms[p.id] = f"{p.prenom} {p.nom}".strip()

    par_classe: dict[str, MouvementClasse] = {}

    def classe_de(code: str) -> MouvementClasse:
        return par_classe.setdefault(code, MouvementClasse(classe=code, nb_actuel=0))

    for pid, code in actuels.items():
        m = classe_de(code)
        m.nb_actuel += 1
        avant = envoyes.get(pid)
        if avant is None:
            m.entrants.append(noms.get(pid, str(pid)))
        elif avant != code:
            # Il était transmis, ailleurs : pour cette classe c'est une
            # arrivée, et pour l'ancienne un départ — les deux sont vrais,
            # et c'est le même élève qu'il faut déplacer, pas créer.
            m.arrives_d_ailleurs.append(noms.get(pid, str(pid)))

    for pid, code in envoyes.items():
        if code and actuels.get(pid) != code:
            classe_de(code).sortants.append(noms.get(pid, str(pid)))

    resultat.classes = sorted(par_classe.values(), key=lambda c: c.classe)
    return resultat
