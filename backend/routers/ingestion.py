"""Endpoint d'ingestion des exports Charlemagne.

Un seul endpoint, deux modes :

- `mode=simulation` (défaut) : lit, évalue, retourne le rapport sans commit.
- `mode=reel` : idem + commit — bloqué si des classes sont hors table.

Deux voies d'envoi :

- `POST /api/ingestion` (multipart) : upload direct du fichier.
- `POST /api/ingestion/base64` (JSON) : contenu en base64. Fallback quand le
  webview Tauri filtre le multipart (bug observé sur certaines
  combinaisons WebView2 + fichier .htm).
"""
from __future__ import annotations

import base64
from dataclasses import asdict
from pathlib import Path
from tempfile import NamedTemporaryFile

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
    avertissements: list[str] = []
    est_bloquee: bool


def _rapport_vers_out(r: RapportIngestion) -> RapportOut:
    return RapportOut(**asdict(r))


def _executer_ingestion(
    session: Session,
    chemin: Path,
    libelle_annee: str,
    type_personne: str,
    mode: str,
) -> RapportOut:
    """Cœur commun aux deux endpoints (multipart et base64)."""
    if mode not in ("simulation", "reel"):
        raise HTTPException(400, f"mode invalide : {mode!r}")
    if type_personne not in ("eleve", "adulte", "auto"):
        raise HTTPException(400, f"type_personne invalide : {type_personne!r}")

    # Auto-détection du type si demandé
    if type_personne == "auto":
        try:
            df = (
                lire_htm(chemin)
                if chemin.suffix.lower() in (".htm", ".html")
                else lire_xlsx(chemin)
            )
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

    # Trace l'ingestion — jamais bloquant pour le résultat rendu à l'appelant.
    try:
        from backend.services.journal import journaliser

        journaliser(
            session,
            type_operation="ingestion",
            cible=type_personne,
            mode=mode,
            annee_libelle=libelle_annee,
            parametres={"fichier": chemin.name},
            resultat={
                "nb_lignes_lues": rapport.nb_lignes_lues,
                "nb_lignes_ingerees": rapport.nb_lignes_ingerees,
                "nb_lignes_ignorees": rapport.nb_lignes_ignorees,
                "nb_personnes_creees": rapport.nb_personnes_creees,
                "nb_personnes_mises_a_jour": rapport.nb_personnes_mises_a_jour,
                "nb_snapshots_crees": rapport.nb_snapshots_crees,
                "nb_classes_inconnues": len(rapport.classes_inconnues),
                "nb_collisions_login": len(rapport.collisions_login),
                "nb_homonymes": len(rapport.homonymes_intra_export),
            },
        )
        session.commit()
    except Exception:  # pragma: no cover — le journal ne doit rien casser
        session.rollback()

    return _rapport_vers_out(rapport)


@router.post("", response_model=RapportOut)
async def ingerer(
    fichier: UploadFile = File(...),
    libelle_annee: str = Form(...),
    type_personne: str = Form("auto"),
    mode: str = Form("simulation"),
    session: Session = Depends(db_session),
) -> RapportOut:
    """Ingère un export via upload multipart.

    Ordre des paramètres calqué sur `POST /api/table-correspondance/import`
    (qui fonctionne en production) : `fichier` required en premier, puis
    les Form fields. Cette signature évite le rejet silencieux du webview
    Tauri observé quand `UploadFile` est optionnel en dernière position.
    """
    contenu = await fichier.read()
    if not contenu:
        raise HTTPException(400, "Fichier vide")

    suffix = Path(fichier.filename or "upload.htm").suffix or ".htm"
    with NamedTemporaryFile(suffix=suffix, delete=False) as tmp:
        tmp.write(contenu)
        chemin_tmp = Path(tmp.name)

    try:
        return _executer_ingestion(session, chemin_tmp, libelle_annee, type_personne, mode)
    finally:
        try:
            chemin_tmp.unlink()
        except OSError:
            pass


class IngerreBase64Payload(BaseModel):
    """Payload alternatif si le multipart pose problème (WebView2)."""

    fichier_base64: str
    nom_fichier: str
    libelle_annee: str
    type_personne: str = "auto"
    mode: str = "simulation"


@router.post("/base64", response_model=RapportOut)
def ingerer_base64(
    payload: IngerreBase64Payload, session: Session = Depends(db_session)
) -> RapportOut:
    """Ingère un export dont le contenu est envoyé en base64 dans le JSON.

    Fallback pour les cas où le multipart natif du webview échoue (bug
    Tauri v2 + WebView2 observé sur les .htm avec espace/accent dans le
    nom). L'appelant lit le fichier local et l'encode en base64 côté
    frontend.
    """
    try:
        contenu = base64.b64decode(payload.fichier_base64)
    except Exception as e:
        raise HTTPException(400, f"Base64 invalide : {e}") from e
    if not contenu:
        raise HTTPException(400, "Fichier vide")

    suffix = Path(payload.nom_fichier or "upload.htm").suffix or ".htm"
    with NamedTemporaryFile(suffix=suffix, delete=False) as tmp:
        tmp.write(contenu)
        chemin_tmp = Path(tmp.name)

    try:
        return _executer_ingestion(
            session, chemin_tmp, payload.libelle_annee, payload.type_personne, payload.mode
        )
    finally:
        try:
            chemin_tmp.unlink()
        except OSError:
            pass


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
