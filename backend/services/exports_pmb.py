"""Génération des exports CSV pour PMB (logiciel documentaire CDI).

PMB accepte un CSV séparateur point-virgule, encodage utf-8, avec :

    login | nom | prenom | classe | email | statut

Chaque établissement (NDK et SU) a sa propre instance PMB :
- https://lycee-ndkreisker.basecdi.fr
- https://sainte-ursule.basecdi.fr

Un export = un site.

## INE

L'INE (identifiant national élève) est la clé stable côté PMB. Le champ
`login` de notre export peut être remplacé par l'INE si présent — pour
l'instant on utilise le login KoXo (les deux sont uniques par personne).
"""
from __future__ import annotations

import csv
import io
from dataclasses import dataclass
from typing import Literal

from sqlalchemy.orm import Session
from backend.services.rattachement import ids_personnes_du_site

from backend.models import Personne, Site, Snapshot

COLONNES_PMB = ["login", "nom", "prenom", "classe", "email", "statut"]
Categorie = Literal["tous", "nouveaux", "anciens"]


@dataclass
class RapportExportPmb:
    site_nom: str
    type_personne: str
    categorie: str
    nb_lignes: int
    nom_fichier_suggere: str


def generer_csv_pmb(
    session: Session,
    *,
    site_id: int,
    type_personne: str,
    categorie: Categorie,
    annee_cible_id: int,
    annee_source_id: int | None = None,
) -> tuple[bytes, RapportExportPmb]:
    if type_personne not in ("eleve", "adulte"):
        raise ValueError(f"type_personne invalide : {type_personne!r}")
    if categorie not in ("tous", "nouveaux", "anciens"):
        raise ValueError(f"categorie invalide : {categorie!r}")
    if categorie in ("nouveaux", "anciens") and annee_source_id is None:
        raise ValueError(f"annee_source_id requis pour categorie={categorie!r}")

    site = session.query(Site).filter_by(id=site_id).one_or_none()
    if site is None:
        raise ValueError(f"Site introuvable : {site_id}")

    lignes = _recuperer_lignes(session, site, type_personne, categorie, annee_cible_id, annee_source_id)
    contenu = _encoder_csv(lignes)

    pop = "eleves" if type_personne == "eleve" else "adultes"
    nom = f"PMB_{site.nom}_{pop}_{categorie}.csv"
    return contenu, RapportExportPmb(
        site_nom=site.nom, type_personne=type_personne,
        categorie=categorie, nb_lignes=len(lignes),
        nom_fichier_suggere=nom,
    )


def _recuperer_lignes(session, site, type_personne, categorie, annee_cible_id, annee_source_id):
    ids_cible = _snapshots_par_personne(session, annee_cible_id, site, type_personne)
    if categorie == "tous":
        selection = ids_cible
    else:
        ids_source = set(_snapshots_par_personne(session, annee_source_id, site, type_personne))
        if categorie == "nouveaux":
            selection = {k: v for k, v in ids_cible.items() if k not in ids_source}
        else:  # anciens
            snaps_source = _snapshots_par_personne(session, annee_source_id, site, type_personne)
            selection = {k: v for k, v in snaps_source.items() if k not in ids_cible}

    personnes = {p.id: p for p in session.query(Personne).filter(Personne.id.in_(selection)).all()}
    return [_formatter(personnes[pid], selection[pid], type_personne) for pid in selection if pid in personnes]


def _snapshots_par_personne(session, annee_id, site, type_personne):
    q = (
        session.query(Snapshot)
        .join(Personne, Snapshot.personne_id == Personne.id)
        .filter(
            Snapshot.annee_scolaire_id == annee_id,
            Personne.id.in_(
                ids_personnes_du_site(
                    session, site_id=site.id,
                    annee_id=annee_id, type_personne=type_personne,
                )
            ),
            Personne.type == type_personne,
        )
        .order_by(Snapshot.personne_id, Snapshot.date_ingestion.desc())
    )
    derniers = {}
    for s in q.all():
        if s.personne_id not in derniers:
            derniers[s.personne_id] = s
    return derniers


def _formatter(personne, snapshot, type_personne):
    return {
        "login": personne.login or "",
        "nom": personne.nom or "",
        "prenom": personne.prenom or "",
        "classe": snapshot.classe or "",
        "email": personne.email or "",
        "statut": "eleve" if type_personne == "eleve" else "personnel",
    }


def _encoder_csv(lignes):
    buf = io.StringIO(newline="")
    writer = csv.DictWriter(buf, fieldnames=COLONNES_PMB, delimiter=";", quoting=csv.QUOTE_MINIMAL)
    writer.writeheader()
    for l in lignes:
        writer.writerow(l)
    return buf.getvalue().encode("utf-8", errors="replace")
