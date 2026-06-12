"""Génération du CSV d'import SmartAir (contrôle d'accès JPM/Salto).

Format à 28 colonnes (calqué sur l'export SmartAir N-1 historique).
Colonnes-clés :
- **Op** : opération à effectuer côté SmartAir
    - `a` = ajouter (nouveau badge)
    - `b` = supprimer (départ)
    - `m` = modifier (changement de classe / régime)
    - vide = pas de changement
- **Id** : numéro de badge Charlemagne (clé stable)
- **Name** : "NOM Prénom"
- **CardId** : identifiant hex de la carte physique (ex. E012FFFE1A37D38F).
  **Pas inventable** — vient de l'export SmartAir N-1 ou est rempli par le
  premier scan. Si non disponible, on laisse vide.
- **Group** : code classe Charlemagne (1_BPAGORA, 4J, etc.)

Le reste des colonnes sont des valeurs par défaut largement constantes
issues de la convention de l'établissement (Technology=P, Grants=FFFFFF,
UpdateInterval=168, Level=1, Reles=1, …).

Si un export SmartAir N-1 a été fourni (via upload), on l'utilise pour :
1. Récupérer les CardId des élèves déjà présents
2. Calculer les Op (a/b/m) en comparant avec l'année N
"""
from __future__ import annotations

import csv
import io
from dataclasses import dataclass

from sqlalchemy.orm import Session

from backend.models import AnneeScolaire, EleveSnapshot, Etablissement

COLONNES_SMARTAIR = [
    "Op",
    "Id",
    "Name",
    "CardId",
    "Group",
    "Technology",
    "ActivationDate",
    "ActivationTime",
    "ExpirationDate",
    "ExpirationTime",
    "Grants",
    "PIN",
    "OverB",
    "ADA",
    "OpeningsReg",
    "OpeningsOverflow",
    "ModifiesLockingPlan",
    "Updateable",
    "UpdateInterval",
    "Level",
    "Track1",
    "Track2",
    "Reles",
    "Data1",
    "Data2",
    "Data3",
    "Data4",
    "MSISD",
]

# Valeurs par défaut SmartAir (issues de l'export historique).
DEFAUTS_SMARTAIR: dict[str, str] = {
    "Technology": "P",
    "Grants": "FFFFFF",
    "OverB": "0",
    "ADA": "0",
    "OpeningsReg": "1",
    "OpeningsOverflow": "0",
    "ModifiesLockingPlan": "1",
    "Updateable": "0",
    "UpdateInterval": "168",
    "Level": "1",
    "Reles": "1",
}


@dataclass
class FichierGenere:
    nom: str
    contenu: str
    nb_lignes: int
    description: str


def _ligne_smartair(
    eleve: EleveSnapshot,
    op: str,
    card_id: str = "",
) -> dict[str, str]:
    """Construit une ligne CSV SmartAir."""
    ligne = {c: "" for c in COLONNES_SMARTAIR}
    ligne.update(DEFAUTS_SMARTAIR)
    ligne["Op"] = op
    ligne["Id"] = str(eleve.num_badge) if eleve.num_badge is not None else ""
    ligne["Name"] = f"{eleve.nom or ''} {eleve.prenom or ''}".strip()
    ligne["CardId"] = card_id
    ligne["Group"] = eleve.code_classe or ""
    return ligne


def _serialiser_csv_smartair(lignes: list[dict[str, str]]) -> str:
    """CSV séparateur point-virgule (convention SmartAir), UTF-8 BOM."""
    buf = io.StringIO()
    writer = csv.DictWriter(
        buf,
        fieldnames=COLONNES_SMARTAIR,
        delimiter=";",
        lineterminator="\r\n",
        quoting=csv.QUOTE_MINIMAL,
    )
    writer.writeheader()
    for ligne in lignes:
        writer.writerow(ligne)
    return "﻿" + buf.getvalue()


def generer_exports_smartair(
    session: Session,
    libelle_n: str,
    card_ids_existants: dict[int, str] | None = None,
    badges_n_minus_1: set[int] | None = None,
) -> list[FichierGenere]:
    """Génère le CSV SmartAir pour l'année N.

    Args:
        session: SQLAlchemy session
        libelle_n: snapshot année N
        card_ids_existants: optionnel — map {num_badge: CardId hex} extrait
                            d'un précédent export SmartAir. Permet de
                            préserver le matching badge physique ↔ badge
                            logique.
        badges_n_minus_1: optionnel — set des num_badge présents l'an passé,
                          pour calculer correctement les Op (m vs a, et b).

    Returns:
        Un seul fichier CSV pour tout l'ensemble scolaire — SmartAir gère
        en général une seule base d'accès commune (pas de séparation
        SU/NDK comme PMB).
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

    card_ids_existants = card_ids_existants or {}
    badges_n_minus_1 = badges_n_minus_1 or set()
    badges_n = {e.num_badge for e in eleves if e.num_badge is not None}

    lignes: list[dict[str, str]] = []

    # Ajouts / modifications côté N
    for e in sorted(eleves, key=lambda x: (x.nom or "", x.prenom or "")):
        if e.num_badge is None:
            continue
        if e.num_badge in badges_n_minus_1:
            op = "m"  # modify
        else:
            op = "a"  # add
        card_id = card_ids_existants.get(e.num_badge, "")
        lignes.append(_ligne_smartair(e, op=op, card_id=card_id))

    # Suppressions : badges présents en N-1 mais plus en N
    badges_a_supprimer = badges_n_minus_1 - badges_n
    if badges_a_supprimer:
        # Pour les supprimés, on n'a pas l'EleveSnapshot N. On crée des
        # lignes minimales avec juste Op=b + Id + CardId (suffisant pour
        # SmartAir).
        for badge in sorted(badges_a_supprimer):
            ligne = {c: "" for c in COLONNES_SMARTAIR}
            ligne.update(DEFAUTS_SMARTAIR)
            ligne["Op"] = "b"
            ligne["Id"] = str(badge)
            ligne["CardId"] = card_ids_existants.get(badge, "")
            lignes.append(ligne)

    contenu = _serialiser_csv_smartair(lignes)

    # Calcul des stats descriptives
    nb_a = sum(1 for l in lignes if l["Op"] == "a")
    nb_m = sum(1 for l in lignes if l["Op"] == "m")
    nb_b = sum(1 for l in lignes if l["Op"] == "b")
    avec_cardid = sum(1 for l in lignes if l["CardId"])

    desc_op = f"{nb_a} ajout(s), {nb_m} modif(s), {nb_b} suppression(s)"
    desc_cardid = (
        f" · {avec_cardid}/{len(lignes)} avec CardId préservé"
        if card_ids_existants
        else f" · CardId à scanner (aucun export N-1 fourni)"
    )

    return [
        FichierGenere(
            nom=f"SmartAir_Eleves_{libelle_n}.csv",
            contenu=contenu,
            nb_lignes=len(lignes),
            description=f"Import SmartAir : {desc_op}{desc_cardid}",
        )
    ]


def parser_export_smartair_n_minus_1(
    contenu_csv: str,
) -> tuple[dict[int, str], set[int]]:
    """Parse un export SmartAir précédent pour récupérer les CardId.

    Returns:
        (card_ids_par_badge, badges_presents)
    """
    card_ids: dict[int, str] = {}
    badges: set[int] = set()
    # SmartAir N-1 peut utiliser ; ou , — on détecte automatiquement
    f = io.StringIO(contenu_csv.lstrip("﻿"))
    # Détection séparateur sur l'en-tête
    premier_chunk = contenu_csv.lstrip("﻿")[:500]
    delim = ";" if premier_chunk.count(";") > premier_chunk.count(",") else ","
    f.seek(0)
    reader = csv.DictReader(f, delimiter=delim)
    for ligne in reader:
        # L'export historique peut avoir des badges en float (90.0 au lieu de 9)
        # ou multipliés par 10. On essaie les deux interprétations.
        raw_id = (ligne.get("Id") or "").strip()
        if not raw_id:
            continue
        try:
            badge = int(float(raw_id))
        except (ValueError, TypeError):
            continue
        badges.add(badge)
        card_id = (ligne.get("CardId") or "").strip()
        if card_id:
            card_ids[badge] = card_id
    return card_ids, badges
