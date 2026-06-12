"""Génération du CSV bulk-import pour Google Workspace (Education).

Format CSV importable depuis l'Admin Google Workspace → Utilisateurs →
Importer des utilisateurs.

Colonnes minimales requises :
- First Name [Required]
- Last Name [Required]
- Email Address [Required]
- Password [Required if account is new]
- Org Unit Path [Optional, mais on l'utilise pour classer]

L'Org Unit (unité organisationnelle) suit le pattern observé dans le XLSX
historique de l'utilisateur :
    /<site>/<site><année_compact>/<code_classe>
exemple : "/SU/SU2026/31" pour un 6e dans la classe 31 du collège.

Le mapping site → préfixe court est paramétrable dans MAPPING_SITE_OU.
"""
from __future__ import annotations

import csv
import io
import random
from dataclasses import dataclass

from sqlalchemy.orm import Session

from backend.models import AnneeScolaire, EleveSnapshot, Etablissement
from backend.services.configuration import get_param
from backend.services.regles_metier import email_lekreisker, generer_mot_de_passe

# Mapping code_court d'établissement → segment d'OU Google
MAPPING_SITE_OU = {
    "SU": "SU",
    "NDK_LY": "NDK_LY",
    "NDK_LP": "NDK_LP",
    "NDE": "NDE",
}

COLONNES_GOOGLE = [
    "First Name [Required]",
    "Last Name [Required]",
    "Email Address [Required]",
    "Password [Required]",
    "Org Unit Path [Required]",
    "New Primary Email",
    "Recovery Email",
    "Employee ID",
]


@dataclass
class FichierGenere:
    nom: str
    contenu: str
    nb_lignes: int
    description: str


def _annee_compact(libelle: str) -> str:
    """`2025-2026` → `2026` (l'année de la rentrée)."""
    if "-" in libelle:
        return libelle.split("-")[-1]
    return libelle


def _ou_path(
    site: str,
    libelle_annee: str,
    code_classe: str | None,
    template: str = "/{site}/{site}{annee_compact}/{classe}",
) -> str:
    """Construit l'Org Unit Path Google selon le template configuré."""
    seg_site = MAPPING_SITE_OU.get(site, site)
    seg_annee = _annee_compact(libelle_annee)
    return template.format(
        site=seg_site,
        annee_compact=seg_annee,
        classe=code_classe or "",
    )


def _ligne_google(
    eleve: EleveSnapshot,
    etab: Etablissement,
    libelle_annee: str,
    avec_mdp: bool,
    rng: random.Random,
    domaine_email: str = "lekreisker.fr",
    ou_template: str = "/{site}/{site}{annee_compact}/{classe}",
) -> dict[str, str]:
    return {
        "First Name [Required]": eleve.prenom or "",
        "Last Name [Required]": eleve.nom or "",
        "Email Address [Required]": email_lekreisker(
            eleve.prenom or "", eleve.nom or "", domaine=domaine_email
        ),
        "Password [Required]": generer_mot_de_passe(rng) if avec_mdp else "",
        "Org Unit Path [Required]": _ou_path(
            etab.code_court, libelle_annee, eleve.code_classe, template=ou_template
        ),
        "New Primary Email": "",
        "Recovery Email": "",
        "Employee ID": str(eleve.num_badge) if eleve.num_badge is not None else "",
    }


def _serialiser_csv_google(lignes: list[dict[str, str]]) -> str:
    """CSV virgule, UTF-8 BOM (compat Google Admin et Excel)."""
    buf = io.StringIO()
    writer = csv.DictWriter(
        buf, fieldnames=COLONNES_GOOGLE, lineterminator="\r\n"
    )
    writer.writeheader()
    for ligne in lignes:
        writer.writerow(ligne)
    return "﻿" + buf.getvalue()


def generer_exports_google(
    session: Session,
    libelle_n: str,
    badges_n_minus_1: set[int] | None = None,
    seed: int | None = None,
) -> list[FichierGenere]:
    """Génère les CSV Google Workspace pour l'année N.

    Produit deux fichiers :
    - **Tous** : tous les élèves de N, avec OU path à jour (sans MDP — les
      comptes existent déjà). Pratique pour faire un dry-run et vérifier les OU.
    - **Nouveaux** : seulement les entrants (avec MDP générés), pour création.

    Args:
        badges_n_minus_1: optionnel — set des badges présents en N-1, pour
                          calculer les "Nouveaux" sans dépendre du module
                          comparaison.
    """
    rng = random.Random(seed) if seed is not None else random.Random()
    domaine_email = get_param(session, "email.domaine", "lekreisker.fr")
    ou_template = get_param(
        session, "google.ou_template", "/{site}/{site}{annee_compact}/{classe}"
    )

    annee_n = (
        session.query(AnneeScolaire).filter_by(libelle=libelle_n).one_or_none()
    )
    if annee_n is None:
        raise ValueError(f"Snapshot N introuvable : {libelle_n}")

    etabs_par_id: dict[int, Etablissement] = {
        e.id: e for e in session.query(Etablissement).all()
    }
    eleves = (
        session.query(EleveSnapshot).filter_by(annee_scolaire_id=annee_n.id).all()
    )

    badges_n_1 = badges_n_minus_1 or set()

    fichiers: list[FichierGenere] = []

    # 1. Fichier "Tous" (sans MDP)
    eleves_tries = sorted(
        eleves, key=lambda e: (e.nom or "", e.prenom or "")
    )
    lignes_tous = []
    for e in eleves_tries:
        etab = etabs_par_id.get(e.etablissement_id)
        if not etab:
            continue
        lignes_tous.append(
            _ligne_google(e, etab, libelle_n, avec_mdp=False, rng=rng, domaine_email=domaine_email, ou_template=ou_template)
        )
    fichiers.append(
        FichierGenere(
            nom=f"Google_Eleves_Tous_{libelle_n}.csv",
            contenu=_serialiser_csv_google(lignes_tous),
            nb_lignes=len(lignes_tous),
            description=f"Tous les élèves {libelle_n} (vérification OU, sans MDP)",
        )
    )

    # 2. Fichier "Nouveaux" (avec MDP générés)
    if badges_n_1:
        nouveaux = [
            e
            for e in eleves_tries
            if e.num_badge is not None and e.num_badge not in badges_n_1
        ]
        lignes_nouv = []
        for e in nouveaux:
            etab = etabs_par_id.get(e.etablissement_id)
            if not etab:
                continue
            lignes_nouv.append(
                _ligne_google(e, etab, libelle_n, avec_mdp=True, rng=rng, domaine_email=domaine_email, ou_template=ou_template)
            )
        fichiers.append(
            FichierGenere(
                nom=f"Google_Eleves_Nouveaux_{libelle_n}.csv",
                contenu=_serialiser_csv_google(lignes_nouv),
                nb_lignes=len(lignes_nouv),
                description=(
                    f"Entrants {libelle_n} — comptes à créer "
                    f"(MDP générés inclus)"
                ),
            )
        )

    return fichiers
