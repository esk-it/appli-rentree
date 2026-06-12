"""Génération KoXo pour les adultes/personnel (groupe primaire "Professeurs").

Symétrique à koxo.py pour les élèves. Différences :
- Groupe primaire = "Professeurs"
- Groupe secondaire = libellé de la fonction (PROF, AESH, SURVEILLANT...)
- Un seul fichier global "Adultes" (pas de SU/NDK car les profs sont souvent
  partagés entre établissements)
- Mot de passe généré uniquement pour les Nouveaux
"""
from __future__ import annotations

import csv
import io
import random
from dataclasses import dataclass

from sqlalchemy.orm import Session

from backend.models import AdulteSnapshot, AnneeScolaire
from backend.services.configuration import get_param
from backend.services.regles_metier import (
    email_lekreisker,
    generer_mot_de_passe,
    login_koxo,
)

COLONNES_KOXO_ADULTES = [
    "Groupe primaire",
    "Groupe secondaire",
    "Titre",
    "Nom",
    "Prénom",
    "Identifiant",
    "ID unique",
    "Mot de passe",
    "Date de naissance",
    "Email",
]


@dataclass
class FichierGenere:
    nom: str
    contenu: str
    nb_lignes: int
    description: str


def _ligne_adulte_koxo(
    a: AdulteSnapshot,
    avec_mdp: bool,
    rng: random.Random,
    domaine_email: str = "lekreisker.fr",
) -> dict[str, str]:
    return {
        "Groupe primaire": "Professeurs",
        "Groupe secondaire": a.fonction or "Personnel",
        "Titre": a.civilite or "",
        "Nom": a.nom or "",
        "Prénom": a.prenom or "",
        "Identifiant": login_koxo(a.prenom or "", a.nom or ""),
        "ID unique": str(a.num_personnel) if a.num_personnel is not None else "",
        "Mot de passe": generer_mot_de_passe(rng) if avec_mdp else "",
        "Date de naissance": a.date_naissance.strftime("%d/%m/%Y")
        if a.date_naissance
        else "",
        "Email": email_lekreisker(a.prenom or "", a.nom or "", domaine=domaine_email),
    }


def _serialiser_csv(lignes: list[dict[str, str]]) -> str:
    buf = io.StringIO()
    writer = csv.DictWriter(
        buf, fieldnames=COLONNES_KOXO_ADULTES, lineterminator="\r\n"
    )
    writer.writeheader()
    for l in lignes:
        writer.writerow(l)
    return "﻿" + buf.getvalue()


def generer_exports_koxo_adultes(
    session: Session,
    libelle_n: str,
    libelle_n_minus_1: str | None = None,
    seed: int | None = None,
) -> list[FichierGenere]:
    """Génère les CSV KoXo pour les adultes (Tous, Nouveaux, Anciens)."""
    rng = random.Random(seed) if seed is not None else random.Random()
    domaine_email = get_param(session, "email.domaine", "lekreisker.fr")

    annee_n = (
        session.query(AnneeScolaire).filter_by(libelle=libelle_n).one_or_none()
    )
    if annee_n is None:
        raise ValueError(f"Snapshot N introuvable : {libelle_n}")

    adultes_n = (
        session.query(AdulteSnapshot)
        .filter_by(annee_scolaire_id=annee_n.id)
        .all()
    )

    # Calcul des sets pour Nouveaux/Anciens si N-1 fourni
    cle_n_1: set[tuple[str, str]] = set()
    adultes_n_1: list[AdulteSnapshot] = []
    if libelle_n_minus_1:
        annee_n_1 = (
            session.query(AnneeScolaire)
            .filter_by(libelle=libelle_n_minus_1)
            .one_or_none()
        )
        if annee_n_1 is not None:
            adultes_n_1 = (
                session.query(AdulteSnapshot)
                .filter_by(annee_scolaire_id=annee_n_1.id)
                .all()
            )
            cle_n_1 = {(a.nom or "", a.prenom or "") for a in adultes_n_1}

    fichiers: list[FichierGenere] = []

    # 1. Tous
    triés = sorted(adultes_n, key=lambda a: (a.nom or "", a.prenom or ""))
    lignes = [
        _ligne_adulte_koxo(a, avec_mdp=False, rng=rng, domaine_email=domaine_email)
        for a in triés
    ]
    fichiers.append(
        FichierGenere(
            nom=f"KoXo_Adultes_Tous_{libelle_n}.csv",
            contenu=_serialiser_csv(lignes),
            nb_lignes=len(lignes),
            description=f"État complet personnel pour {libelle_n}",
        )
    )

    if not libelle_n_minus_1:
        return fichiers

    # 2. Nouveaux (présents en N pas en N-1)
    nouveaux = [
        a for a in triés if (a.nom or "", a.prenom or "") not in cle_n_1
    ]
    lignes_nouv = [
        _ligne_adulte_koxo(a, avec_mdp=True, rng=rng, domaine_email=domaine_email)
        for a in nouveaux
    ]
    fichiers.append(
        FichierGenere(
            nom=f"KoXo_Adultes_Nouveaux_{libelle_n}.csv",
            contenu=_serialiser_csv(lignes_nouv),
            nb_lignes=len(lignes_nouv),
            description="Adultes entrants — comptes à créer (MDP générés)",
        )
    )

    # 3. Anciens (présents en N-1 pas en N)
    cle_n = {(a.nom or "", a.prenom or "") for a in adultes_n}
    sortants = [
        a for a in adultes_n_1 if (a.nom or "", a.prenom or "") not in cle_n
    ]
    sortants_tries = sorted(
        sortants, key=lambda a: (a.nom or "", a.prenom or "")
    )
    lignes_anc = [
        _ligne_adulte_koxo(a, avec_mdp=False, rng=rng, domaine_email=domaine_email)
        for a in sortants_tries
    ]
    fichiers.append(
        FichierGenere(
            nom=f"KoXo_Adultes_Anciens_{libelle_n}.csv",
            contenu=_serialiser_csv(lignes_anc),
            nb_lignes=len(lignes_anc),
            description="Adultes sortants — comptes à supprimer",
        )
    )

    return fichiers
