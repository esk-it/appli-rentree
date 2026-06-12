"""Orchestrateur : lance tous les générateurs et bundle en un ZIP.

Cette fonction permet à l'utilisateur de cliquer un seul bouton pour produire
tous les fichiers d'import (KoXo + PMB + CardStudio + SmartAir + Google)
pour une année donnée. Le ZIP est organisé en sous-dossiers par cible :

```
Rentree_<annee>.zip
├── KoXo/
│   ├── KoXo_SU_Eleves_Tous_2025-2026.csv
│   ├── KoXo_SU_Eleves_Nouveaux_2025-2026.csv (si N-1)
│   └── ...
├── PMB/
│   ├── PMB_SU_Lecteurs_2025-2026.csv
│   └── PMB_NDK_Lecteurs_2025-2026.csv
├── CardStudio/
│   ├── CardStudio_SAINTE-URSULE_2025-2026.xlsx
│   └── CardStudio_KREISKER_2025-2026.xlsx
├── SmartAir/
│   └── SmartAir_Eleves_2025-2026.csv
├── Google/
│   └── Google_Eleves_Tous_2025-2026.csv
└── README.txt   (résumé + procédure)
```
"""
from __future__ import annotations

import base64
import io
import zipfile
from dataclasses import dataclass
from datetime import datetime

from sqlalchemy.orm import Session

from backend.models import AnneeScolaire, EleveSnapshot
from backend.services.exporters.cardstudio import generer_exports_cardstudio
from backend.services.exporters.google import generer_exports_google
from backend.services.exporters.google_adultes import generer_exports_google_adultes
from backend.services.exporters.koxo import generer_exports_koxo
from backend.services.exporters.koxo_adultes import generer_exports_koxo_adultes
from backend.services.exporters.pmb import generer_exports_pmb
from backend.services.exporters.smartair import (
    generer_exports_smartair,
    parser_export_smartair_n_minus_1,
)


@dataclass
class ResumeFichier:
    cible: str
    nom: str
    nb_lignes: int


@dataclass
class ResultatTout:
    nom_archive: str
    contenu_base64: str  # ZIP encodé base64
    taille_octets: int
    nb_fichiers: int
    fichiers: list[ResumeFichier]


README_TEMPLATE = """\
Bundle d'imports — Rentrée {annee_n}

Généré le {date}
Comparaison avec : {annee_n_1}

Cibles incluses dans ce ZIP
===========================

{stats_cibles}

Procédure générale
==================

Chaque sous-dossier contient les fichiers à importer dans le logiciel
correspondant. Le détail de la procédure est dans la page de chaque
générateur dans l'application Appli Rentrée.

Ordre conseillé d'import (de moins critique à plus critique) :
1. PMB (CDI)
2. CardStudio (impression badges visuels)
3. KoXo (comptes Active Directory)
4. Google Workspace (comptes Google)
5. SmartAir (contrôle d'accès portes)

Note : les fichiers "Nouveaux" contiennent les mots de passe générés
automatiquement. Conserve ces fichiers en sécurité pour distribuer
les MDP aux élèves au premier accès.
"""


def _annee_compact(libelle: str) -> str:
    if "-" in libelle:
        return libelle.split("-")[-1]
    return libelle


def generer_tout(
    session: Session,
    libelle_n: str,
    libelle_n_minus_1: str | None = None,
    contenu_smartair_n_minus_1: str | None = None,
) -> ResultatTout:
    """Génère tous les exports et bundle en un ZIP."""
    annee_n = (
        session.query(AnneeScolaire).filter_by(libelle=libelle_n).one_or_none()
    )
    if annee_n is None:
        raise ValueError(f"Snapshot N introuvable : {libelle_n}")

    # Pré-calcul des badges N-1 si on a une année précédente (pour Google "Nouveaux")
    badges_n_1: set[int] | None = None
    if libelle_n_minus_1:
        annee_n_1 = (
            session.query(AnneeScolaire)
            .filter_by(libelle=libelle_n_minus_1)
            .one_or_none()
        )
        if annee_n_1 is not None:
            badges_n_1 = {
                e.num_badge
                for e in session.query(EleveSnapshot).filter_by(
                    annee_scolaire_id=annee_n_1.id
                )
                if e.num_badge is not None
            }

    # Parsing SmartAir N-1 (CardIds)
    card_ids: dict[int, str] | None = None
    badges_smartair_n_1: set[int] | None = None
    if contenu_smartair_n_minus_1:
        try:
            card_ids, badges_smartair_n_1 = parser_export_smartair_n_minus_1(
                contenu_smartair_n_minus_1
            )
        except Exception:
            pass  # Ignore silencieusement, on n'a pas les CardId mais on continue

    # 1. Lancement parallèle (en série, c'est suffisamment rapide)
    koxo = generer_exports_koxo(session, libelle_n, libelle_n_minus_1)
    koxo_adultes = generer_exports_koxo_adultes(
        session, libelle_n, libelle_n_minus_1
    )
    pmb = generer_exports_pmb(session, libelle_n)
    cardstudio = generer_exports_cardstudio(session, libelle_n)
    smartair = generer_exports_smartair(
        session,
        libelle_n,
        card_ids_existants=card_ids,
        badges_n_minus_1=badges_smartair_n_1,
    )
    google = generer_exports_google(
        session, libelle_n, badges_n_minus_1=badges_n_1
    )
    google_adultes = generer_exports_google_adultes(
        session, libelle_n, libelle_n_minus_1
    )

    # 2. Création du ZIP
    bio = io.BytesIO()
    fichiers_listes: list[ResumeFichier] = []

    with zipfile.ZipFile(bio, "w", zipfile.ZIP_DEFLATED) as zf:
        # KoXo Élèves
        for f in koxo:
            zf.writestr(f"KoXo/{f.nom}", f.contenu.encode("utf-8"))
            fichiers_listes.append(
                ResumeFichier(cible="KoXo", nom=f.nom, nb_lignes=f.nb_lignes)
            )
        # KoXo Adultes
        for f in koxo_adultes:
            zf.writestr(f"KoXo/{f.nom}", f.contenu.encode("utf-8"))
            fichiers_listes.append(
                ResumeFichier(cible="KoXo", nom=f.nom, nb_lignes=f.nb_lignes)
            )
        # PMB
        for f in pmb:
            zf.writestr(f"PMB/{f.nom}", f.contenu.encode("utf-8"))
            fichiers_listes.append(
                ResumeFichier(cible="PMB", nom=f.nom, nb_lignes=f.nb_lignes)
            )
        # CardStudio (binaire XLSX)
        for f in cardstudio:
            zf.writestr(
                f"CardStudio/{f.nom}",
                base64.b64decode(f.contenu_base64),
            )
            fichiers_listes.append(
                ResumeFichier(
                    cible="CardStudio", nom=f.nom, nb_lignes=f.nb_lignes
                )
            )
        # SmartAir
        for f in smartair:
            zf.writestr(f"SmartAir/{f.nom}", f.contenu.encode("utf-8"))
            fichiers_listes.append(
                ResumeFichier(
                    cible="SmartAir", nom=f.nom, nb_lignes=f.nb_lignes
                )
            )
        # Google Élèves
        for f in google:
            zf.writestr(f"Google/{f.nom}", f.contenu.encode("utf-8"))
            fichiers_listes.append(
                ResumeFichier(cible="Google", nom=f.nom, nb_lignes=f.nb_lignes)
            )
        # Google Adultes
        for f in google_adultes:
            zf.writestr(f"Google/{f.nom}", f.contenu.encode("utf-8"))
            fichiers_listes.append(
                ResumeFichier(cible="Google", nom=f.nom, nb_lignes=f.nb_lignes)
            )

        # README résumant le contenu
        stats_cibles = "\n".join(
            f"  [{f.cible:11}] {f.nom:55} ({f.nb_lignes} lignes)"
            for f in fichiers_listes
        )
        readme = README_TEMPLATE.format(
            annee_n=libelle_n,
            annee_n_1=libelle_n_minus_1 or "(aucune)",
            date=datetime.utcnow().strftime("%Y-%m-%d %H:%M UTC"),
            stats_cibles=stats_cibles,
        )
        zf.writestr("README.txt", readme.encode("utf-8"))

    contenu = bio.getvalue()
    return ResultatTout(
        nom_archive=f"Rentree_{libelle_n}.zip",
        contenu_base64=base64.b64encode(contenu).decode("ascii"),
        taille_octets=len(contenu),
        nb_fichiers=len(fichiers_listes),
        fichiers=fichiers_listes,
    )
