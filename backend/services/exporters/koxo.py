"""Génération des CSV d'import pour KoXo (gestion des comptes AD).

Produit 3 fichiers par établissement et par population :
- KoXo_<etab>_Tous : état complet visé pour l'année N
- KoXo_<etab>_Nouveaux : entrants uniquement (avec MDP générés)
- KoXo_<etab>_Anciens : sortants (à supprimer côté KoXo)

Format : CSV séparateur virgule, encodage UTF-8 BOM (Excel-friendly).
Colonnes (10) :
  Groupe primaire | Groupe secondaire | Titre | Nom | Prénom |
  Identifiant | ID unique | Mot de passe | Date de naissance | Email
"""
from __future__ import annotations

import csv
import io
import random
from dataclasses import dataclass

from sqlalchemy.orm import Session

from backend.models import AnneeScolaire, EleveSnapshot, Etablissement
from backend.services.comparaison import comparer_annees
from backend.services.regles_metier import (
    email_lekreisker,
    generer_mot_de_passe,
    groupe_primaire_koxo,
    login_koxo,
)

# Mapping code_court d'établissement → code de groupe KoXo cible.
# Dans l'historique XLSX : SU et NDK (NDK regroupe LY + LP).
ETAB_VERS_GROUPE_KOXO = {
    "SU": "SU",
    "NDK_LY": "NDK",
    "NDK_LP": "NDK",
    "NDE": "NDE",  # à confirmer côté KoXo
}

COLONNES_KOXO = [
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
    contenu: str  # CSV en UTF-8 (avec BOM pour Excel)
    nb_lignes: int
    description: str


def _ligne_koxo(
    eleve: EleveSnapshot,
    avec_mdp: bool,
    rng: random.Random,
) -> dict[str, str]:
    """Construit une ligne CSV KoXo à partir d'un EleveSnapshot."""
    return {
        "Groupe primaire": groupe_primaire_koxo(est_adulte=False),
        "Groupe secondaire": eleve.code_classe or "",
        "Titre": "",
        "Nom": eleve.nom or "",
        "Prénom": eleve.prenom or "",
        "Identifiant": login_koxo(eleve.prenom or "", eleve.nom or ""),
        "ID unique": str(eleve.num_badge) if eleve.num_badge is not None else "",
        "Mot de passe": generer_mot_de_passe(rng) if avec_mdp else "",
        "Date de naissance": "",
        "Email": email_lekreisker(eleve.prenom or "", eleve.nom or ""),
    }


def _serialiser_csv(lignes: list[dict[str, str]]) -> str:
    """Sérialise une liste de dicts en CSV virgule, UTF-8 avec BOM."""
    buf = io.StringIO()
    # BOM Excel-friendly : on l'ajoute après écriture
    writer = csv.DictWriter(buf, fieldnames=COLONNES_KOXO, lineterminator="\r\n")
    writer.writeheader()
    for ligne in lignes:
        writer.writerow(ligne)
    return "﻿" + buf.getvalue()


def generer_exports_koxo(
    session: Session,
    libelle_n: str,
    libelle_n_minus_1: str | None = None,
    seed: int | None = None,
) -> list[FichierGenere]:
    """Génère tous les fichiers KoXo pour les snapshots fournis.

    Args:
        session: SQLAlchemy session
        libelle_n: snapshot année N (état cible)
        libelle_n_minus_1: snapshot année N-1 (pour calculer Nouveaux/Anciens).
                           Si None, seul "Tous" est généré.
        seed: pour la reproductibilité des mots de passe en test

    Returns:
        Liste de FichierGenere — un par (etab_koxo × type), à proposer
        au téléchargement côté UI.
    """
    rng = random.Random(seed) if seed is not None else random.Random()

    # Snapshot N
    annee_n = (
        session.query(AnneeScolaire).filter_by(libelle=libelle_n).one_or_none()
    )
    if annee_n is None:
        raise ValueError(f"Snapshot N introuvable : {libelle_n}")

    etabs_par_id: dict[int, Etablissement] = {
        e.id: e for e in session.query(Etablissement).all()
    }

    eleves_n = (
        session.query(EleveSnapshot).filter_by(annee_scolaire_id=annee_n.id).all()
    )

    # 1. Groupement des élèves N par groupe KoXo cible
    par_groupe_koxo: dict[str, list[EleveSnapshot]] = {}
    for e in eleves_n:
        etab = etabs_par_id.get(e.etablissement_id)
        if not etab:
            continue
        groupe = ETAB_VERS_GROUPE_KOXO.get(etab.code_court, etab.code_court)
        par_groupe_koxo.setdefault(groupe, []).append(e)

    fichiers: list[FichierGenere] = []

    # 2. Fichier "Tous" par groupe KoXo
    for groupe, liste in par_groupe_koxo.items():
        liste_triee = sorted(liste, key=lambda e: (e.nom or "", e.prenom or ""))
        lignes = [_ligne_koxo(e, avec_mdp=False, rng=rng) for e in liste_triee]
        fichiers.append(
            FichierGenere(
                nom=f"KoXo_{groupe}_Eleves_Tous_{libelle_n}.csv",
                contenu=_serialiser_csv(lignes),
                nb_lignes=len(lignes),
                description=f"État complet des élèves {groupe} pour {libelle_n}",
            )
        )

    # 3. Si on a un snapshot N-1, on calcule Nouveaux/Anciens via la comparaison
    if libelle_n_minus_1 is None:
        return fichiers

    res = comparer_annees(session, libelle_n, libelle_n_minus_1)

    # Index pour retrouver l'EleveSnapshot original à partir de l'id
    eleves_n_par_id = {e.id: e for e in eleves_n}
    eleves_n_1_par_id = {
        e.id: e
        for e in session.query(EleveSnapshot)
        .filter_by(
            annee_scolaire_id=session.query(AnneeScolaire)
            .filter_by(libelle=libelle_n_minus_1)
            .one()
            .id
        )
        .all()
    }

    # 4. "Nouveaux" — entrants par groupe (avec MDP générés)
    entrants_par_groupe: dict[str, list[EleveSnapshot]] = {}
    for resume in res.entrants:
        e = eleves_n_par_id.get(resume.id)
        if e is None:
            continue
        etab = etabs_par_id.get(e.etablissement_id)
        groupe = ETAB_VERS_GROUPE_KOXO.get(etab.code_court if etab else "", "AUTRE")
        entrants_par_groupe.setdefault(groupe, []).append(e)

    for groupe, liste in entrants_par_groupe.items():
        liste_triee = sorted(liste, key=lambda e: (e.nom or "", e.prenom or ""))
        lignes = [_ligne_koxo(e, avec_mdp=True, rng=rng) for e in liste_triee]
        fichiers.append(
            FichierGenere(
                nom=f"KoXo_{groupe}_Eleves_Nouveaux_{libelle_n}.csv",
                contenu=_serialiser_csv(lignes),
                nb_lignes=len(lignes),
                description=f"Élèves entrants {groupe} — comptes à créer (mots de passe inclus)",
            )
        )

    # 5. "Anciens" — sortants par groupe (sans MDP, ils seront supprimés)
    sortants_par_groupe: dict[str, list[EleveSnapshot]] = {}
    for resume in res.sortants:
        e = eleves_n_1_par_id.get(resume.id)
        if e is None:
            continue
        etab = etabs_par_id.get(e.etablissement_id)
        groupe = ETAB_VERS_GROUPE_KOXO.get(etab.code_court if etab else "", "AUTRE")
        sortants_par_groupe.setdefault(groupe, []).append(e)

    for groupe, liste in sortants_par_groupe.items():
        liste_triee = sorted(liste, key=lambda e: (e.nom or "", e.prenom or ""))
        lignes = [_ligne_koxo(e, avec_mdp=False, rng=rng) for e in liste_triee]
        fichiers.append(
            FichierGenere(
                nom=f"KoXo_{groupe}_Eleves_Anciens_{libelle_n}.csv",
                contenu=_serialiser_csv(lignes),
                nb_lignes=len(lignes),
                description=f"Élèves sortants {groupe} — comptes à supprimer",
            )
        )

    return fichiers
