"""Endpoints d'import des exports Charlemagne."""
from __future__ import annotations

from pathlib import Path

from fastapi import APIRouter, HTTPException, UploadFile

from backend.config import DOSSIER_INPUT
from backend.services.parser_charlemagne import lire_htm, lire_xlsx

router = APIRouter(prefix="/api/charlemagne", tags=["charlemagne"])


@router.get("/fichiers")
def lister_fichiers() -> list[dict]:
    """Liste les exports Charlemagne déposés dans data/input/."""
    fichiers = []
    for f in sorted(DOSSIER_INPUT.iterdir()):
        if f.suffix.lower() in {".htm", ".html", ".xlsx", ".xls"}:
            fichiers.append({
                "nom": f.name,
                "taille_octets": f.stat().st_size,
                "modifie_le": f.stat().st_mtime,
            })
    return fichiers


@router.post("/upload")
async def uploader_fichier(fichier: UploadFile) -> dict:
    """Reçoit un fichier d'export et le pose dans data/input/."""
    if not fichier.filename:
        raise HTTPException(400, "Nom de fichier manquant")
    cible = DOSSIER_INPUT / fichier.filename
    contenu = await fichier.read()
    cible.write_bytes(contenu)
    return {"nom": fichier.filename, "taille_octets": len(contenu)}


@router.get("/apercu")
def apercu_fichier(nom: str, limite: int = 200) -> dict:
    """Lit un fichier d'export et renvoie ses lignes (jusqu'à `limite`) en JSON.

    Cet endpoint sert l'aperçu côté UI — pas le traitement en base.
    """
    chemin = DOSSIER_INPUT / nom
    if not chemin.exists():
        raise HTTPException(404, f"Fichier introuvable : {nom}")
    if chemin.suffix.lower() in {".htm", ".html"}:
        df = lire_htm(chemin)
    elif chemin.suffix.lower() in {".xlsx", ".xls"}:
        df = lire_xlsx(chemin)
    else:
        raise HTTPException(400, f"Format non supporté : {chemin.suffix}")

    # Conversion JSON-safe : dates → string ISO, NaN → None
    df_extrait = df.head(limite).copy()
    for col in df_extrait.columns:
        if df_extrait[col].dtype.kind == "M":  # datetime
            df_extrait[col] = df_extrait[col].dt.strftime("%Y-%m-%d")
    df_extrait = df_extrait.where(df_extrait.notna(), None)

    return {
        "nom_fichier": nom,
        "nb_lignes_total": int(len(df)),
        "colonnes": list(df.columns),
        "lignes": df_extrait.to_dict(orient="records"),
        "stats": _stats_globales(df),
    }


def _stats_globales(df) -> dict:
    """Statistiques rapides pour le dashboard d'accueil."""
    stats: dict[str, object] = {"total": int(len(df))}
    if "nouvel_eleve" in df.columns:
        stats["nouveaux"] = int(df["nouvel_eleve"].sum())
    if "nom_etablissement" in df.columns:
        stats["par_etablissement"] = (
            df["nom_etablissement"].value_counts().to_dict()
        )
    if "code_regime" in df.columns:
        stats["par_regime"] = df["code_regime"].value_counts().to_dict()
    if "code_niveau" in df.columns:
        stats["par_niveau"] = df["code_niveau"].value_counts().to_dict()
    return stats
