"""Retirer d'une année scolaire quelqu'un qui n'y était finalement pas.

## Le cas

Un élève est ingéré le 18 août : Charlemagne l'inscrit, le programme lui
fait un snapshot pour 2026-2027 et lui pose une classe. En septembre, il a
disparu de l'export — il ne s'est pas présenté, ou son inscription a été
annulée.

Le référentiel ne supprime jamais personne, et c'est délibéré : un login
réattribué casserait un compte existant. Mais il ne savait pas non plus
**désinscrire** — la personne restait dans sa dernière classe connue, à
gonfler l'effectif et à garder un compte Google actif. Dix cas à la
rentrée 2026, et rien à l'écran pour les traiter.

## Ce que « retirer de l'année » veut dire

Trois gestes, et pas un de plus :

1. le **snapshot de cette année** est supprimé — c'était une photographie
   d'un fait qui ne s'est pas produit ;
2. la **classe courante** est effacée si elle venait de cette année ;
3. le **site** est laissé tel quel — il dit d'où vient la personne, pas où
   elle est inscrite.

La personne, son login et son historique des autres années ne bougent pas.

## Ce que ça débloque

Une fois le snapshot retiré, la réconciliation la voit enfin comme une
**sortante** — présente à l'année précédente, absente de celle-ci — et
« Traiter les sortants » met son compte en quarantaine. C'est le chemin
normal du programme ; il fallait seulement cesser de la déclarer présente.

C'est pour cette raison que le compte n'est pas touché ici : un import ne
décide pas du sort d'un compte, et il n'y a pas de raison qu'une
désinscription le fasse davantage.
"""
from __future__ import annotations

from dataclasses import dataclass, field

from sqlalchemy.orm import Session

from backend.models import AnneeScolaire, Personne, Snapshot


@dataclass
class Retire:
    personne_id: int
    nom: str
    prenom: str
    classe_avant: str | None


@dataclass
class RapportDesinscription:
    annee_libelle: str
    mode: str
    retires: list[Retire] = field(default_factory=list)
    ignores: list[str] = field(default_factory=list)
    """Ceux qu'on n'a pas touchés, et pourquoi."""

    @property
    def nb_retires(self) -> int:
        return len(self.retires)


def retirer_de_lannee(
    session: Session,
    personne_ids: list[int],
    *,
    annee_id: int,
    mode: str = "simulation",
) -> RapportDesinscription:
    """Retire ces personnes de l'année : snapshot supprimé, classe effacée.

    Args:
        mode: `simulation` n'écrit rien et dit ce qui serait fait.

    Raises:
        ValueError: année inconnue, ou mode invalide.
    """
    if mode not in ("simulation", "reel"):
        raise ValueError(f"mode invalide : {mode!r}")
    annee = session.query(AnneeScolaire).filter_by(id=annee_id).one_or_none()
    if annee is None:
        raise ValueError(f"Année introuvable : {annee_id}")

    rapport = RapportDesinscription(annee_libelle=annee.libelle, mode=mode)
    if not personne_ids:
        return rapport

    personnes = {
        p.id: p
        for p in session.query(Personne).filter(Personne.id.in_(personne_ids)).all()
    }
    for pid in personne_ids:
        p = personnes.get(pid)
        if p is None:
            rapport.ignores.append(f"personne {pid} introuvable")
            continue

        snaps = (
            session.query(Snapshot)
            .filter(
                Snapshot.personne_id == pid,
                Snapshot.annee_scolaire_id == annee_id,
            )
            .all()
        )
        if not snaps:
            # Rien à retirer : elle n'était pas inscrite à cette année. Le
            # dire plutôt que de compter un retrait qui n'a pas eu lieu.
            rapport.ignores.append(
                f"{p.prenom} {p.nom} n'a pas de snapshot pour {annee.libelle}"
            )
            continue

        rapport.retires.append(
            Retire(personne_id=pid, nom=p.nom, prenom=p.prenom, classe_avant=p.classe)
        )
        if mode != "reel":
            continue

        for s in snaps:
            session.delete(s)
        # La classe courante venait de cette inscription : elle tombe avec
        # elle. Une classe fantôme est ce qui gonflait les effectifs.
        p.classe = None

    if mode == "reel":
        session.commit()
    else:
        session.rollback()
    return rapport
