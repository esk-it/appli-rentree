"""Génération des CSV d'import pour PMB (gestion du CDI / bibliothèque).

PMB (PhpMyBibli) gère les emprunteurs. Deux instances séparées chez ESK :
- `https://lycee-ndkreisker.basecdi.fr` pour les élèves NDK (LY + LP)
- `https://sainte-ursule.basecdi.fr` pour les élèves SU

→ on produit 2 fichiers distincts. Format : CSV séparateur point-virgule,
UTF-8 avec BOM (compat Excel), 1 ligne d'en-têtes.

Colonnes (basées sur le standard PMB d'import "Lecteurs") :
- cb (code barre) = numéro de badge, identifiant stable
- nom, prenom
- email
- classe (libellé de groupe)
- categ (catégorie d'emprunteur : "Élève")
- codestat (code statistique : on met le niveau Charlemagne)
- date_naissance (vide pour l'instant — pas dans l'export Charlemagne fourni)
- sexe (vide aussi)
- login, password (vide — PMB peut les générer)

Le format précis sera affiné au premier import test : si PMB rejette ou
attend d'autres colonnes, on ajustera la liste COLONNES_PMB ci-dessous.
"""
from __future__ import annotations

import csv
import io
from dataclasses import dataclass

from sqlalchemy.orm import Session

from backend.models import AnneeScolaire, EleveSnapshot, Etablissement
from backend.services.regles_metier import email_lekreisker

# Mapping code_court d'établissement → instance PMB cible
PMB_INSTANCES = {
    "SU": {
        "code": "SU",
        "url": "https://sainte-ursule.basecdi.fr",
        "etabs": ["SU"],
    },
    "NDK": {
        "code": "NDK",
        "url": "https://lycee-ndkreisker.basecdi.fr",
        "etabs": ["NDK_LY", "NDK_LP"],
    },
    # NDE : à compléter quand on aura l'URL et le périmètre
}

COLONNES_PMB = [
    "cb",
    "nom",
    "prenom",
    "email",
    "classe",
    "categ",
    "codestat",
    "date_naissance",
    "sexe",
    "login",
    "password",
]


@dataclass
class FichierGenere:
    nom: str
    contenu: str
    nb_lignes: int
    description: str


def _ligne_pmb(eleve: EleveSnapshot) -> dict[str, str]:
    """Construit une ligne CSV PMB à partir d'un EleveSnapshot."""
    return {
        "cb": str(eleve.num_badge) if eleve.num_badge is not None else "",
        "nom": eleve.nom or "",
        "prenom": eleve.prenom or "",
        "email": email_lekreisker(eleve.prenom or "", eleve.nom or ""),
        "classe": eleve.code_classe or "",
        "categ": "Élève",
        "codestat": eleve.code_niveau or "",
        "date_naissance": "",
        "sexe": "",
        "login": "",
        "password": "",
    }


def _serialiser_csv_pmb(lignes: list[dict[str, str]]) -> str:
    """CSV avec séparateur point-virgule, UTF-8 BOM Excel-friendly."""
    buf = io.StringIO()
    writer = csv.DictWriter(
        buf,
        fieldnames=COLONNES_PMB,
        delimiter=";",
        lineterminator="\r\n",
        quoting=csv.QUOTE_MINIMAL,
    )
    writer.writeheader()
    for ligne in lignes:
        writer.writerow(ligne)
    return "﻿" + buf.getvalue()


def generer_exports_pmb(
    session: Session,
    libelle_n: str,
) -> list[FichierGenere]:
    """Génère un CSV PMB par instance (SU et NDK) pour l'année N.

    Args:
        session: SQLAlchemy session
        libelle_n: snapshot année N

    Returns:
        Liste de 2 FichierGenere (un par instance PMB), prêts à téléverser
        sur l'interface admin PMB de chaque établissement.
    """
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

    fichiers: list[FichierGenere] = []
    for instance_code, instance in PMB_INSTANCES.items():
        eleves_instance = [
            e
            for e in eleves
            if etabs_par_id.get(e.etablissement_id)
            and etabs_par_id[e.etablissement_id].code_court in instance["etabs"]
        ]
        if not eleves_instance:
            continue
        eleves_tries = sorted(
            eleves_instance, key=lambda e: (e.nom or "", e.prenom or "")
        )
        lignes = [_ligne_pmb(e) for e in eleves_tries]
        fichiers.append(
            FichierGenere(
                nom=f"PMB_{instance_code}_Lecteurs_{libelle_n}.csv",
                contenu=_serialiser_csv_pmb(lignes),
                nb_lignes=len(lignes),
                description=f"Lecteurs à importer dans {instance['url']}",
            )
        )

    return fichiers
