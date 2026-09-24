"""Le trombinoscope d'une classe, en PDF.

## Pourquoi un PDF, et pas l'écran

Un professeur principal le demande à la rentrée, un surveillant le colle
au mur : le trombinoscope part sur papier. L'écran du Référentiel le
montre ; ce module le met en page A4 et le fait imprimer par le navigateur
du poste, comme les étiquettes (`impression_pdf`).

## Les photos voyagent dans la page

Elles sont lues sur le partage et posées dans le HTML, en données. Le
navigateur qui imprime n'a donc pas à rejoindre le partage lui-même — un
chemin réseau qu'il n'ouvrirait pas donnerait une planche de cases vides,
sans rien dire. Une photo illisible, ou absente, laisse les initiales : un
visage qui manque se voit sur la planche, il ne la fait pas échouer.
"""
from __future__ import annotations

import base64
import html
from dataclasses import dataclass
from datetime import date
from pathlib import Path

from sqlalchemy.orm import Session

from backend.models import AnneeScolaire, Personne, Site, Snapshot, TableCorrespondance

TYPES_IMAGE = {".jpg": "image/jpeg", ".jpeg": "image/jpeg", ".png": "image/png"}
TAILLE_MAX_PHOTO = 4 * 1024 * 1024
"""Au-delà, la photo n'est pas embarquée : quatre mégaoctets par visage
feraient d'une classe un PDF qu'on n'envoie plus par mail."""


class TrombinoscopeImpossible(ValueError):
    """La planche ne peut pas être faite, et le message dit pourquoi."""


@dataclass
class Trombinoscope:
    classe: str
    annee: str
    site: str | None
    html: str
    nb_eleves: int
    nb_sans_photo: int


def _photo_en_donnees(chemin: str | None) -> str | None:
    if not chemin:
        return None
    p = Path(chemin)
    mime = TYPES_IMAGE.get(p.suffix.lower())
    if mime is None:
        return None
    try:
        if p.stat().st_size > TAILLE_MAX_PHOTO:
            return None
        return f"data:{mime};base64,{base64.b64encode(p.read_bytes()).decode('ascii')}"
    except OSError:
        return None


def composer(
    session: Session, *, classe: str, annee_id: int | None = None
) -> Trombinoscope:
    """La planche HTML d'une classe, photos comprises.

    Raises:
        TrombinoscopeImpossible: année inconnue, ou personne dans la classe.
    """
    from backend.services.inventaire_photos import (
        InventaireImpossible,
        chemins_attribues,
    )

    annees = session.query(AnneeScolaire).all()
    if annee_id is None:
        annee = max(annees, key=lambda a: a.libelle) if annees else None
    else:
        annee = next((a for a in annees if a.id == annee_id), None)
    if annee is None:
        raise TrombinoscopeImpossible("Aucune année scolaire à montrer.")

    derniers: dict[int, Snapshot] = {}
    for sn in (
        session.query(Snapshot)
        .filter(Snapshot.annee_scolaire_id == annee.id)
        .order_by(Snapshot.date_ingestion, Snapshot.id)
    ):
        derniers[sn.personne_id] = sn
    ids = [pid for pid, sn in derniers.items() if (sn.classe or "").strip() == classe]
    eleves = sorted(
        session.query(Personne)
        .filter(Personne.id.in_(ids or [0]), Personne.type == "eleve")
        .all(),
        key=lambda p: (p.nom or "", p.prenom or ""),
    )
    if not eleves:
        raise TrombinoscopeImpossible(
            f"Aucun élève inscrit en {classe} pour {annee.libelle}."
        )

    try:
        photos = chemins_attribues(session, annee_id=annee.id)
    except InventaireImpossible:
        photos = {}

    t = session.query(TableCorrespondance).filter_by(classe_code_court=classe).first()
    site = None
    if t is not None:
        s = session.get(Site, t.site_id)
        site = s.nom if s else None

    cases = []
    sans_photo = 0
    for p in eleves:
        donnees = _photo_en_donnees(photos.get(p.id))
        if donnees is None:
            sans_photo += 1
            initiales = html.escape(((p.prenom or "?")[:1] + (p.nom or "?")[:1]).upper())
            visage = f'<div class="visage vide">{initiales}</div>'
        else:
            visage = f'<img class="visage" src="{donnees}" alt="">'
        cases.append(
            f'<div class="case">{visage}<div class="prenom">{html.escape(p.prenom or "")}</div>'
            f'<div class="nom">{html.escape(p.nom or "")}</div></div>'
        )

    titre = f"{classe} — {annee.libelle}"
    sous_titre = " · ".join(
        x for x in (site, f"{len(eleves)} élèves", f"édité le {date.today():%d/%m/%Y}") if x
    )
    page = f"""<!doctype html>
<html lang="fr"><head><meta charset="utf-8"><title>Trombinoscope {html.escape(titre)}</title>
<style>
@page {{ size: A4 portrait; margin: 12mm; }}
* {{ box-sizing: border-box; }}
body {{ margin: 0; font-family: "Segoe UI", Arial, sans-serif; color: #1E1B3A; }}
header {{ display: flex; align-items: baseline; justify-content: space-between;
  border-bottom: 1.5px solid #1E1B3A; padding-bottom: 3mm; margin-bottom: 5mm; }}
h1 {{ margin: 0; font-size: 20pt; }}
.sous {{ font-size: 9.5pt; color: #55526B; }}
.grille {{ display: grid; grid-template-columns: repeat(6, 1fr); gap: 5mm 4mm; }}
.case {{ break-inside: avoid; text-align: center; }}
.visage {{ display: block; width: 100%; aspect-ratio: 3 / 4; object-fit: cover;
  border-radius: 2mm; background: #ECEAF3; }}
.vide {{ display: flex; align-items: center; justify-content: center;
  font-size: 18pt; font-weight: 700; color: #8A87A0; border: 0.4mm dashed #B8B4CC; }}
.prenom {{ margin-top: 1.5mm; font-size: 9pt; line-height: 1.15; }}
.nom {{ font-size: 9pt; font-weight: 700; text-transform: uppercase; line-height: 1.15; }}
</style></head>
<body>
<header><h1>{html.escape(titre)}</h1><span class="sous">{html.escape(sous_titre)}</span></header>
<div class="grille">{"".join(cases)}</div>
</body></html>"""
    return Trombinoscope(
        classe=classe, annee=annee.libelle, site=site, html=page,
        nb_eleves=len(eleves), nb_sans_photo=sans_photo,
    )
