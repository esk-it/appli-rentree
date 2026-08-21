"""Endpoints CRUD de la table de correspondance classe → OU/groupe Google.

C'est la configuration métier centrale. Éditable dans l'interface, elle
est aussi importable en masse depuis un XLSX historique (endpoint `/import`).
"""
from __future__ import annotations

from dataclasses import asdict
from pathlib import Path
from tempfile import NamedTemporaryFile

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from backend.database import db_session
from backend.models import Site, TableCorrespondance
from backend.services.import_table import (
    RapportImportTable,
    apercu_onglets,
    importer_table,
)

router = APIRouter(prefix="/api/table-correspondance", tags=["table_correspondance"])


class LigneOut(BaseModel):
    id: int
    site_id: int
    site_nom: str
    classe_charlemagne_long: str
    classe_code_court: str
    groupe_google: str | None
    ou_pre_rentree: str
    ou_definitive: str
    groupe_profs_google: str | None


class LignePayload(BaseModel):
    site_id: int
    classe_charlemagne_long: str = Field(..., min_length=1, max_length=100)
    classe_code_court: str = Field(..., min_length=1, max_length=30)
    groupe_google: str | None = None
    ou_pre_rentree: str = Field(..., min_length=1, max_length=200)
    ou_definitive: str = Field(..., min_length=1, max_length=200)
    groupe_profs_google: str | None = None


def _serialiser(l: TableCorrespondance, sites_par_id: dict[int, Site]) -> LigneOut:
    return LigneOut(
        id=l.id,
        site_id=l.site_id,
        site_nom=sites_par_id[l.site_id].nom if l.site_id in sites_par_id else "?",
        classe_charlemagne_long=l.classe_charlemagne_long,
        classe_code_court=l.classe_code_court,
        groupe_google=l.groupe_google,
        ou_pre_rentree=l.ou_pre_rentree,
        ou_definitive=l.ou_definitive,
        groupe_profs_google=l.groupe_profs_google,
    )


@router.get("", response_model=list[LigneOut])
def lister(
    site: str | None = None, session: Session = Depends(db_session)
) -> list[LigneOut]:
    sites_par_id = {s.id: s for s in session.query(Site).all()}
    q = session.query(TableCorrespondance)
    if site:
        s_obj = next((v for v in sites_par_id.values() if v.nom == site), None)
        if not s_obj:
            return []
        q = q.filter_by(site_id=s_obj.id)
    q = q.order_by(TableCorrespondance.site_id, TableCorrespondance.classe_code_court)
    return [_serialiser(l, sites_par_id) for l in q.all()]


@router.post("", response_model=LigneOut)
def creer(
    payload: LignePayload, session: Session = Depends(db_session)
) -> LigneOut:
    sites_par_id = {s.id: s for s in session.query(Site).all()}
    if payload.site_id not in sites_par_id:
        raise HTTPException(400, f"Site {payload.site_id} introuvable")
    if (
        session.query(TableCorrespondance)
        .filter_by(site_id=payload.site_id, classe_code_court=payload.classe_code_court)
        .one_or_none()
    ):
        raise HTTPException(
            409,
            f"Ligne déjà présente : site={payload.site_id} classe={payload.classe_code_court}",
        )
    l = TableCorrespondance(**payload.model_dump())
    session.add(l)
    session.commit()
    session.refresh(l)
    return _serialiser(l, sites_par_id)


@router.put("/{ligne_id}", response_model=LigneOut)
def modifier(
    ligne_id: int, payload: LignePayload, session: Session = Depends(db_session)
) -> LigneOut:
    l = session.query(TableCorrespondance).filter_by(id=ligne_id).one_or_none()
    if l is None:
        raise HTTPException(404, "Ligne introuvable")
    for k, v in payload.model_dump().items():
        setattr(l, k, v)
    session.commit()
    session.refresh(l)
    sites_par_id = {s.id: s for s in session.query(Site).all()}
    return _serialiser(l, sites_par_id)


@router.delete("/{ligne_id}")
def supprimer(ligne_id: int, session: Session = Depends(db_session)) -> dict:
    l = session.query(TableCorrespondance).filter_by(id=ligne_id).one_or_none()
    if l is None:
        raise HTTPException(404, "Ligne introuvable")
    session.delete(l)
    session.commit()
    return {"ok": True, "supprime": ligne_id}


# ---------------------------------------------------------------------------
# Import automatique depuis un XLSX historique (Lot 6)
# ---------------------------------------------------------------------------


class RapportOut(BaseModel):
    mode: str
    onglet_utilise: str
    nb_lignes_lues: int
    nb_lignes_ingerees: int
    nb_creations: int
    nb_mises_a_jour: int
    nb_identiques: int
    lignes_importees: list[dict]
    lignes_rejetees: list[dict]
    sites_inconnus: list[str]
    erreurs: list[str]
    est_bloque: bool


def _rapport_to_out(r: RapportImportTable) -> RapportOut:
    return RapportOut(
        mode=r.mode,
        onglet_utilise=r.onglet_utilise,
        nb_lignes_lues=r.nb_lignes_lues,
        nb_lignes_ingerees=r.nb_lignes_ingerees,
        nb_creations=r.nb_creations,
        nb_mises_a_jour=r.nb_mises_a_jour,
        nb_identiques=r.nb_identiques,
        lignes_importees=[asdict(li) for li in r.lignes_importees],
        lignes_rejetees=[asdict(lr) for lr in r.lignes_rejetees],
        sites_inconnus=r.sites_inconnus,
        erreurs=r.erreurs,
        est_bloque=r.est_bloque,
    )


@router.post("/import", response_model=RapportOut)
async def importer(
    fichier: UploadFile = File(...),
    mode: str = Form("simulation"),
    nom_onglet: str | None = Form(None),
    session: Session = Depends(db_session),
) -> RapportOut:
    """Importe la Table depuis un XLSX historique.

    - `mode=simulation` (défaut) : lit, mappe, produit le rapport sans commit.
    - `mode=reel` : idem + commit.
    """
    if mode not in ("simulation", "reel"):
        raise HTTPException(400, f"mode doit être 'simulation' ou 'reel', reçu : {mode!r}")

    contenu = await fichier.read()
    if not contenu:
        raise HTTPException(400, "Fichier vide")

    with NamedTemporaryFile(suffix=".xlsx", delete=False) as tmp:
        tmp.write(contenu)
        chemin_tmp = Path(tmp.name)

    try:
        rapport = importer_table(
            session=session,
            chemin_fichier=chemin_tmp,
            mode=mode,
            nom_onglet=nom_onglet,
        )
    finally:
        try:
            chemin_tmp.unlink()
        except OSError:
            pass

    return _rapport_to_out(rapport)


class OngletsApercuOut(BaseModel):
    onglets: dict[str, list[str]]


@router.post("/import/apercu", response_model=OngletsApercuOut)
async def apercu_import(fichier: UploadFile = File(...)) -> OngletsApercuOut:
    """Retourne les 3 premières lignes de chaque onglet — aide l'utilisateur
    à choisir le bon onglet si l'auto-détection est douteuse."""
    contenu = await fichier.read()
    if not contenu:
        raise HTTPException(400, "Fichier vide")

    with NamedTemporaryFile(suffix=".xlsx", delete=False) as tmp:
        tmp.write(contenu)
        chemin_tmp = Path(tmp.name)

    try:
        onglets = apercu_onglets(chemin_tmp)
    finally:
        try:
            chemin_tmp.unlink()
        except OSError:
            pass

    return OngletsApercuOut(onglets=onglets)


# ---------------------------------------------------------------------------
# Rotation annuelle des OU
# ---------------------------------------------------------------------------


class RotationPayload(BaseModel):
    chercher: str = Field(..., min_length=1, max_length=50)
    remplacer: str = Field(..., max_length=50)
    site_id: int | None = None
    mode: str = "simulation"


class LigneRenommeeOut(BaseModel):
    id: int
    classe: str
    site: str | None
    avant_pre_rentree: str
    apres_pre_rentree: str
    avant_definitive: str
    apres_definitive: str


class RotationOut(BaseModel):
    chercher: str
    remplacer: str
    mode: str
    nb_lignes_examinees: int
    nb_lignes_modifiees: int
    nb_inchangees: int
    nb_dans_un_nombre: int = 0
    annees_presentes: dict[str, int] = {}
    avertissements: list[str]
    lignes: list[LigneRenommeeOut]


@router.post("/rotation-ou", response_model=RotationOut)
def rotation_ou(
    payload: RotationPayload, session: Session = Depends(db_session)
) -> RotationOut:
    """Remplace un fragment dans les chemins d'OU — l'année, en pratique.

    L'arborescence Google porte l'année qui se termine : à chaque rentrée
    la Table doit viser l'arbre suivant. Le faire ligne à ligne est une
    source d'erreur invisible, les deux chemins étant également valides
    pour le programme.

    En mode `simulation`, rien n'est écrit.
    """
    from backend.services.rotation_ou import renommer_dans_les_ou

    try:
        r = renommer_dans_les_ou(
            session,
            chercher=payload.chercher,
            remplacer=payload.remplacer,
            site_id=payload.site_id,
            mode=payload.mode,
        )
    except ValueError as e:
        raise HTTPException(400, str(e)) from None

    return RotationOut(
        chercher=r.chercher,
        remplacer=r.remplacer,
        mode=r.mode,
        nb_lignes_examinees=r.nb_lignes_examinees,
        nb_lignes_modifiees=r.nb_lignes_modifiees,
        nb_inchangees=r.nb_inchangees,
        nb_dans_un_nombre=r.nb_dans_un_nombre,
        annees_presentes=r.annees_presentes,
        avertissements=r.avertissements,
        lignes=[LigneRenommeeOut(**vars(l)) for l in r.lignes],
    )
