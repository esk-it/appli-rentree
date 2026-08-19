"""Génération des exports XLSX pour CardStudio (impression visuelle des badges).

CardStudio attend un XLSX avec 13 colonnes (extrait de BadgesESK.xls) :

    Etablissement | Code établissement | Code niveau | Code classe |
    Num Badge | Code Régime | Nom et prénom | Nom | Prénom | Photo |
    Date Entrée pour tri | NomFichierPhoto | Chambres

Uniquement les élèves (les adultes n'ont pas de badge visuel).

## Photo

`NomFichierPhoto` = nom du fichier attendu dans le partage réseau
``\\ESK-APP01\\...\\<NomFichierPhoto>`` (le chemin exact est un paramètre app).
Format historique : `NOM Prénom.jpg`.

## Chambres

Numéro de chambre pour les internes — pour l'instant vide. À enrichir
plus tard depuis un fichier de dortoir dédié si besoin.
"""
from __future__ import annotations

import io
from dataclasses import dataclass
from typing import Literal

import openpyxl
from sqlalchemy.orm import Session
from backend.services.rattachement import (
    ids_personnes_du_site,
    ids_presents_annee,
)

from backend.models import Personne, Site, Snapshot

COLONNES_CARDSTUDIO = [
    "Etablissement", "Code établissement", "Code niveau", "Code classe",
    "Num Badge", "Code Régime", "Nom et prénom", "Nom", "Prénom",
    "Photo", "Date Entrée pour tri", "NomFichierPhoto", "Chambres",
]

Categorie = Literal["tous", "nouveaux"]


@dataclass
class RapportExportCardStudio:
    site_nom: str
    nb_lignes: int
    nom_fichier_suggere: str


def generer_xlsx_cardstudio(
    session: Session,
    *,
    site_id: int,
    categorie: Categorie,
    annee_cible_id: int,
    annee_source_id: int | None = None,
) -> tuple[bytes, RapportExportCardStudio]:
    """Génère le XLSX CardStudio pour un site (élèves uniquement)."""
    if categorie not in ("tous", "nouveaux"):
        raise ValueError(f"categorie invalide : {categorie!r}")
    if categorie == "nouveaux" and annee_source_id is None:
        raise ValueError("annee_source_id requis pour categorie='nouveaux'")

    site = session.query(Site).filter_by(id=site_id).one_or_none()
    if site is None:
        raise ValueError(f"Site introuvable : {site_id}")

    tgt = _snapshots_par_personne(session, annee_cible_id, site)
    if categorie == "nouveaux":
        # Nouveau dans l'établissement, pas dans le site : un élève montant
        # du collège au lycée a déjà son badge, il ne faut pas en refaire un.
        deja_la = ids_presents_annee(
            session, annee_id=annee_source_id, type_personne="eleve"
        )
        selection = {k: v for k, v in tgt.items() if k not in deja_la}
    else:
        selection = tgt

    personnes = {p.id: p for p in session.query(Personne).filter(
        Personne.id.in_(selection)
    ).all()}
    lignes = [_ligne(personnes[pid], selection[pid], site) for pid in selection if pid in personnes]

    contenu = _encoder_xlsx(lignes)
    nom = f"CardStudio_{site.nom}_{categorie}.xlsx"
    return contenu, RapportExportCardStudio(site_nom=site.nom, nb_lignes=len(lignes), nom_fichier_suggere=nom)


def _snapshots_par_personne(session, annee_id, site):
    q = (
        session.query(Snapshot)
        .join(Personne, Snapshot.personne_id == Personne.id)
        .filter(
            Snapshot.annee_scolaire_id == annee_id,
            Personne.id.in_(
                ids_personnes_du_site(
                    session, site_id=site.id,
                    annee_id=annee_id, type_personne="eleve",
                )
            ),
            Personne.type == "eleve",
        )
        .order_by(Snapshot.personne_id, Snapshot.date_ingestion.desc())
    )
    derniers = {}
    for s in q.all():
        if s.personne_id not in derniers:
            derniers[s.personne_id] = s
    return derniers


def _ligne(personne: Personne, snapshot: Snapshot, site: Site) -> dict:
    nom_fichier_photo = (snapshot.chemin_photo or f"{personne.nom} {personne.prenom}.jpg").strip()
    date_entree = personne.date_entree.strftime("%Y%m%d") if personne.date_entree else ""
    return {
        "Etablissement": site.nom_complet or site.nom,
        "Code établissement": snapshot.code_etablissement or "",
        "Code niveau": snapshot.niveau or "",
        "Code classe": snapshot.classe or "",
        "Num Badge": personne.badge or "",
        "Code Régime": snapshot.regime or personne.regime or "",
        "Nom et prénom": f"{personne.nom} {personne.prenom}",
        "Nom": personne.nom or "",
        "Prénom": personne.prenom or "",
        "Photo": "",  # image binaire non embarquée — CardStudio va chercher via NomFichierPhoto
        "Date Entrée pour tri": date_entree,
        "NomFichierPhoto": nom_fichier_photo,
        "Chambres": "",  # à enrichir depuis un fichier de dortoir plus tard
    }


def _encoder_xlsx(lignes: list[dict]) -> bytes:
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = "Badges"
    ws.append(COLONNES_CARDSTUDIO)
    for l in lignes:
        ws.append([l.get(c, "") for c in COLONNES_CARDSTUDIO])
    buf = io.BytesIO()
    wb.save(buf)
    return buf.getvalue()
