"""Génération Google Workspace pour les adultes/personnel.

OU Path différent des élèves : on les place dans une OU dédiée au personnel.
Pattern par défaut : /Personnel/<fonction>/.
"""
from __future__ import annotations

import csv
import io
import random
from dataclasses import dataclass

from sqlalchemy.orm import Session

from backend.models import AdulteSnapshot, AnneeScolaire
from backend.services.configuration import get_param
from backend.services.regles_metier import email_lekreisker, generer_mot_de_passe

COLONNES_GOOGLE_ADULTES = [
    "First Name [Required]",
    "Last Name [Required]",
    "Email Address [Required]",
    "Password [Required]",
    "Org Unit Path [Required]",
    "New Primary Email",
    "Recovery Email",
    "Employee ID",
    "Department",
]


@dataclass
class FichierGenere:
    nom: str
    contenu: str
    nb_lignes: int
    description: str


def _ou_path_adulte(fonction: str | None, template: str) -> str:
    """Construit l'OU path pour un adulte."""
    f = (fonction or "Autre").upper()
    return template.format(fonction=f)


def _ligne_adulte_google(
    a: AdulteSnapshot,
    avec_mdp: bool,
    rng: random.Random,
    domaine_email: str,
    ou_template: str,
) -> dict[str, str]:
    return {
        "First Name [Required]": a.prenom or "",
        "Last Name [Required]": a.nom or "",
        "Email Address [Required]": email_lekreisker(
            a.prenom or "", a.nom or "", domaine=domaine_email
        ),
        "Password [Required]": generer_mot_de_passe(rng) if avec_mdp else "",
        "Org Unit Path [Required]": _ou_path_adulte(a.fonction, ou_template),
        "New Primary Email": "",
        "Recovery Email": a.email_personnel or "",
        "Employee ID": str(a.num_personnel) if a.num_personnel is not None else "",
        "Department": a.matieres or a.fonction or "",
    }


def _serialiser_csv(lignes: list[dict[str, str]]) -> str:
    buf = io.StringIO()
    writer = csv.DictWriter(
        buf, fieldnames=COLONNES_GOOGLE_ADULTES, lineterminator="\r\n"
    )
    writer.writeheader()
    for l in lignes:
        writer.writerow(l)
    return "﻿" + buf.getvalue()


def generer_exports_google_adultes(
    session: Session,
    libelle_n: str,
    libelle_n_minus_1: str | None = None,
    seed: int | None = None,
) -> list[FichierGenere]:
    """Génère les CSV Google Workspace pour les adultes."""
    rng = random.Random(seed) if seed is not None else random.Random()
    domaine_email = get_param(session, "email.domaine", "lekreisker.fr")
    ou_template = get_param(
        session, "google.ou_template_adultes", "/Personnel/{fonction}"
    )

    annee_n = (
        session.query(AnneeScolaire).filter_by(libelle=libelle_n).one_or_none()
    )
    if annee_n is None:
        raise ValueError(f"Snapshot N introuvable : {libelle_n}")

    adultes = (
        session.query(AdulteSnapshot)
        .filter_by(annee_scolaire_id=annee_n.id)
        .all()
    )

    fichiers: list[FichierGenere] = []
    triés = sorted(adultes, key=lambda a: (a.nom or "", a.prenom or ""))

    lignes_tous = [
        _ligne_adulte_google(a, False, rng, domaine_email, ou_template)
        for a in triés
    ]
    fichiers.append(
        FichierGenere(
            nom=f"Google_Adultes_Tous_{libelle_n}.csv",
            contenu=_serialiser_csv(lignes_tous),
            nb_lignes=len(lignes_tous),
            description="Personnel — état complet (vérif OU)",
        )
    )

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
            nouveaux = [
                a
                for a in triés
                if (a.nom or "", a.prenom or "") not in cle_n_1
            ]
            lignes_nouv = [
                _ligne_adulte_google(a, True, rng, domaine_email, ou_template)
                for a in nouveaux
            ]
            fichiers.append(
                FichierGenere(
                    nom=f"Google_Adultes_Nouveaux_{libelle_n}.csv",
                    contenu=_serialiser_csv(lignes_nouv),
                    nb_lignes=len(lignes_nouv),
                    description="Personnel entrant — comptes à créer (MDP générés)",
                )
            )

    return fichiers
