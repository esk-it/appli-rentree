"""Rattachement d'une personne à un site, pour une année donnée.

## Pourquoi ce n'est pas `Personne.site_id`

Ce champ est un **état courant** : il vaut ce qu'a écrit la dernière
ingestion. Or on ne prépare pas forcément la dernière année ingérée, et
rien n'oblige à ingérer les années dans l'ordre.

Le cas n'a rien d'exotique, c'est le parcours normal d'un collégien :
une élève de 3e à Sainte-Ursule qui passe en 2nde au Kreisker garde
`site_id = SU` tant que l'année suivante n'a pas été ingérée — et si on
réingère l'année précédente après, elle y revient. Sur l'export réel de
la rentrée 2026, 143 élèves étaient dans ce cas : toute la cohorte
montant du collège au lycée.

S'appuyer sur ce champ fait donc dépendre les exports de l'ordre des
ingestions. Ils partaient sur le mauvais serveur KoXo et dans la
mauvaise OU Google.

## La règle

La **Table de correspondance** dit à quel site appartient une classe :
c'est déjà elle qui fait autorité au moment de l'ingestion. Pour une
année donnée, le site d'un élève est donc celui de sa classe **dans
cette année-là**.

Les codes classe sont uniques tous sites confondus — hypothèse déjà
faite par l'ingestion, qui mappe classe → site sur le seul code.

## Les adultes

Ils n'ont pas de classe, et la Table ne dit rien de leur rattachement.
Pour eux `Personne.site_id` reste l'autorité, faute de mieux — deviner
serait exactement ce que le programme s'interdit.
"""
from __future__ import annotations

from sqlalchemy.orm import Session

from backend.models import Personne, Snapshot, TableCorrespondance


def site_par_classe(session: Session) -> dict[str, int]:
    """Index `code classe → site_id`.

    Une classe déclarée pour plusieurs sites est **écartée** : sans
    unicité, choisir serait arbitraire. Les personnes concernées
    retomberont sur leur site enregistré, et la bascule les signalera.
    """
    par_code: dict[str, set[int]] = {}
    for tc in session.query(TableCorrespondance).all():
        par_code.setdefault(tc.classe_code_court, set()).add(tc.site_id)
    return {code: next(iter(ids)) for code, ids in par_code.items() if len(ids) == 1}


def ids_personnes_du_site(
    session: Session,
    *,
    site_id: int,
    annee_id: int,
    type_personne: str,
) -> set[int]:
    """Personnes rattachées à `site_id` pour l'année `annee_id`.

    Élèves : rattachement déduit de la classe du snapshot de cette année.
    Adultes : `Personne.site_id`, faute de classe.

    Un élève dont la classe est absente de la Table — ou déclarée pour
    plusieurs sites — retombe sur son site enregistré : mieux vaut le
    voir dans un export, même imparfait, que le faire disparaître
    silencieusement de tous.
    """
    if type_personne != "eleve":
        return {
            pid
            for (pid,) in session.query(Personne.id)
            .filter(Personne.site_id == site_id, Personne.type == type_personne)
            .all()
        }

    index = site_par_classe(session)

    # Snapshot le plus récent de l'année pour chaque élève
    derniers: dict[int, Snapshot] = {}
    for snap in (
        session.query(Snapshot)
        .join(Personne, Snapshot.personne_id == Personne.id)
        .filter(Snapshot.annee_scolaire_id == annee_id, Personne.type == "eleve")
        .all()
    ):
        prec = derniers.get(snap.personne_id)
        if prec is None or snap.date_ingestion > prec.date_ingestion:
            derniers[snap.personne_id] = snap

    sites_enregistres = dict(
        session.query(Personne.id, Personne.site_id)
        .filter(Personne.type == "eleve")
        .all()
    )

    retenus: set[int] = set()
    for pid, snap in derniers.items():
        resolu = index.get(snap.classe or "")
        if resolu is None:
            resolu = sites_enregistres.get(pid)
        if resolu == site_id:
            retenus.add(pid)
    return retenus
