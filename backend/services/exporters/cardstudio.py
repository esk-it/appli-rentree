"""Génération des XLSX d'import pour CardStudio (impression badges).

CardStudio lit une feuille Excel pour imprimer les badges physiques (visuel
avec photo, nom, classe, chambre). Format calqué sur le `BadgesESK.xls`
historique :

Colonnes (13) :
- Etablissement (court : "KREISKER" ou "SAINTE-URSULE")
- Code établissement (02-COL, 03-LY, 04-LP)
- Code niveau
- Code classe
- Num Badge
- Code Régime
- Nom et prénom
- Nom
- Prénom
- Photo (chemin UNC vers l'image — utilisé par CardStudio)
- Date Entrée pour tri (YYYYMMDD)
- NomFichierPhoto (juste le nom du fichier, sans le chemin)
- Chambres (numéro chambre internat, vide pour la plupart)

On produit un fichier par groupe (KREISKER pour NDK_LY+NDK_LP,
SAINTE-URSULE pour SU, NDE pour NDE). L'utilisateur lance CardStudio
avec le fichier correspondant à la session d'impression.
"""
from __future__ import annotations

import base64
import os.path
from dataclasses import dataclass
from io import BytesIO

from openpyxl import Workbook
from sqlalchemy.orm import Session

from backend.models import AnneeScolaire, EleveSnapshot, Etablissement

# Mapping code_court d'établissement → nom du groupe CardStudio cible.
# Calqué sur le BadgesESK historique : "KREISKER" regroupait LY et LP.
ETAB_VERS_GROUPE_CARDSTUDIO = {
    "SU": "SAINTE-URSULE",
    "NDK_LY": "KREISKER",
    "NDK_LP": "KREISKER",
    "NDE": "NDE",
}

COLONNES_CARDSTUDIO = [
    "Etablissement",
    "Code établissement",
    "Code niveau",
    "Code classe",
    "Num Badge",
    "Code Régime",
    "Nom et prénom",
    "Nom",
    "Prénom",
    "Photo",
    "Date Entrée pour tri",
    "NomFichierPhoto",
    "Chambres",
]


@dataclass
class FichierGenere:
    nom: str
    contenu_base64: str  # XLSX encodé en base64 (binaire)
    nb_lignes: int
    description: str


def _nom_fichier_photo(chemin: str | None) -> str:
    """Extrait juste le nom du fichier d'un chemin UNC ou local."""
    if not chemin:
        return ""
    # Supporte les deux séparateurs (UNC = backslash, parfois forward)
    base = os.path.basename(chemin.replace("\\", "/"))
    return base


def _date_pour_tri(date_obj) -> str:
    """Format YYYYMMDD attendu par CardStudio (cohérent avec Charlemagne)."""
    if date_obj is None:
        return ""
    return date_obj.strftime("%Y%m%d")


def _ligne_cardstudio(
    eleve: EleveSnapshot, etab: Etablissement, groupe: str
) -> list:
    return [
        groupe,  # Etablissement (nom court du groupe)
        etab.code_charlemagne,  # Code établissement
        eleve.code_niveau or "",
        eleve.code_classe or "",
        eleve.num_badge if eleve.num_badge is not None else "",
        eleve.code_regime or "",
        f"{eleve.nom or ''} {eleve.prenom or ''}".strip(),  # Nom et prénom
        eleve.nom or "",
        eleve.prenom or "",
        eleve.photo_chemin or "",  # Photo (UNC complet)
        _date_pour_tri(eleve.date_entree),
        _nom_fichier_photo(eleve.photo_chemin),  # NomFichierPhoto
        "",  # Chambres : pas encore dans nos données
    ]


def generer_exports_cardstudio(
    session: Session,
    libelle_n: str,
) -> list[FichierGenere]:
    """Génère un XLSX CardStudio par groupe pour l'année N.

    Returns:
        Liste de FichierGenere (1 par groupe : KREISKER, SAINTE-URSULE, …),
        chacun avec son XLSX encodé en base64.
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

    # Groupement par groupe CardStudio
    par_groupe: dict[str, list[tuple[EleveSnapshot, Etablissement]]] = {}
    for e in eleves:
        etab = etabs_par_id.get(e.etablissement_id)
        if not etab:
            continue
        groupe = ETAB_VERS_GROUPE_CARDSTUDIO.get(etab.code_court, etab.code_court)
        par_groupe.setdefault(groupe, []).append((e, etab))

    fichiers: list[FichierGenere] = []
    for groupe, paires in par_groupe.items():
        # Trie : par code classe puis par nom (cohérent avec un atelier d'impression)
        paires_triees = sorted(
            paires,
            key=lambda x: (
                x[0].code_classe or "",
                x[0].nom or "",
                x[0].prenom or "",
            ),
        )

        wb = Workbook()
        ws = wb.active
        ws.title = "Badges"
        ws.append(COLONNES_CARDSTUDIO)
        for eleve, etab in paires_triees:
            ws.append(_ligne_cardstudio(eleve, etab, groupe))

        # Largeurs auto-ajustées (approximatif mais suffisant pour la lisibilité)
        for col_idx, col_name in enumerate(COLONNES_CARDSTUDIO, start=1):
            ws.column_dimensions[ws.cell(1, col_idx).column_letter].width = max(
                len(col_name) + 2, 14
            )

        bio = BytesIO()
        wb.save(bio)
        contenu_b64 = base64.b64encode(bio.getvalue()).decode("ascii")

        fichiers.append(
            FichierGenere(
                nom=f"CardStudio_{groupe}_{libelle_n}.xlsx",
                contenu_base64=contenu_b64,
                nb_lignes=len(paires_triees),
                description=f"Badges à imprimer pour {groupe}",
            )
        )

    return fichiers
