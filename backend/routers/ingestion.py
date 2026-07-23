"""Endpoint d'ingestion des exports Charlemagne.

Un seul endpoint, deux modes :

- `mode=simulation` (défaut) : lit, évalue, retourne le rapport sans commit.
- `mode=reel` : idem + commit — bloqué si des classes sont hors table.

Le fichier peut être fourni par upload (multipart) ou déjà présent dans
`data/input/` (paramètre `nom_fichier`).
"""
from __future__ import annotations

from dataclasses import asdict
from pathlib import Path
from typing import Literal

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile
from pydantic import BaseModel
from sqlalchemy.orm import Session

from backend.config import DOSSIER_INPUT
from backend.database import db_session
from backend.services.ingestion import (
    TYPES_PERSONNE,
    RapportIngestion,
    detecter_type_export,
    ingerer_export,
)
from backend.services.parser_charlemagne import lire_htm, lire_xlsx

router = APIRouter(prefix="/api/ingestion", tags=["ingestion"])


class RapportOut(BaseModel):
    type_personne: str
    annee_libelle: str
    mode: str
    nb_lignes_lues: int
    nb_lignes_ingerees: int
    nb_lignes_ignorees: int
    nb_personnes_creees: int
    nb_personnes_mises_a_jour: int
    nb_snapshots_crees: int
    nb_snapshots_identiques: int
    classes_inconnues: list[str]
    homonymes_intra_export: list[dict]
    collisions_login: list[dict]
    erreurs: list[str]
    est_bloquee: bool


def _rapport_vers_out(r: RapportIngestion) -> RapportOut:
    return RapportOut(**asdict(r))


def _resoudre_fichier(nom_fichier: str | None, upload: UploadFile | None) -> Path:
    """Localise le fichier à ingérer : upload prioritaire, sinon data/input/."""
    if upload is not None:
        cible = DOSSIER_INPUT / upload.filename
        cible.write_bytes(upload.file.read())
        return cible
    if nom_fichier:
        chemin = DOSSIER_INPUT / nom_fichier
        if not chemin.exists():
            raise HTTPException(404, f"Fichier introuvable : {nom_fichier}")
        return chemin
    raise HTTPException(400, "Fournir soit un upload, soit `nom_fichier`.")


@router.post("", response_model=RapportOut)
def ingerer(
    libelle_annee: str = Form(...),
    type_personne: Literal["eleve", "adulte", "auto"] = Form("auto"),
    mode: Literal["simulation", "reel"] = Form("simulation"),
    nom_fichier: str | None = Form(None),
    fichier: UploadFile | None = File(None),
    session: Session = Depends(db_session),
) -> RapportOut:
    """Ingère un export. Mode `simulation` par défaut (garde-fou §8 du prompt)."""
    chemin = _resoudre_fichier(nom_fichier, fichier)

    # Auto-détection du type si demandé
    if type_personne == "auto":
        try:
            df = lire_htm(chemin) if chemin.suffix.lower() in (".htm", ".html") else lire_xlsx(chemin)
        except Exception as e:
            raise HTTPException(400, f"Lecture du fichier impossible : {e}") from e
        detecte = detecter_type_export(df)
        if detecte is None:
            raise HTTPException(
                400,
                "Type d'export non détecté automatiquement. Précise `type_personne=eleve` ou `adulte`.",
            )
        type_personne = detecte

    if type_personne not in TYPES_PERSONNE:
        raise HTTPException(400, f"type_personne invalide : {type_personne}")

    rapport = ingerer_export(
        session=session,
        chemin_fichier=chemin,
        type_personne=type_personne,
        libelle_annee=libelle_annee,
        mode=mode,
    )
    return _rapport_vers_out(rapport)


@router.get("/fichiers-dispo")
def lister_fichiers() -> list[dict]:
    """Liste les fichiers déposés dans data/input/ (extensions Charlemagne)."""
    if not DOSSIER_INPUT.exists():
        return []
    fichiers = []
    for f in sorted(DOSSIER_INPUT.iterdir()):
        if f.suffix.lower() in {".htm", ".html", ".xlsx", ".xls"}:
            fichiers.append(
                {
                    "nom": f.name,
                    "taille_octets": f.stat().st_size,
                    "modifie_le": f.stat().st_mtime,
                }
            )
    return fichiers
