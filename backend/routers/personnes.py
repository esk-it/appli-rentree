"""Endpoints de consultation du référentiel Personne.

La création se fait via l'ingestion (Lot 3) et l'amorçage (Lot 9) — pas
ici. Seule écriture exposée : figer l'adresse mail d'une personne, pour
les cas que le programme refuse de trancher seul (homonymes visant la
même adresse, adresse historique hors convention).
"""
from __future__ import annotations

from datetime import date, datetime

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from backend.database import db_session
from backend.models import Personne, Site
from backend.services.regles_metier import calculer_email

router = APIRouter(prefix="/api/personnes", tags=["personnes"])


class PersonneOut(BaseModel):
    id: int
    type: str
    id_charlemagne: int
    cle_pivot: str
    badge: int
    login: str
    email: str | None
    email_est_constate: bool
    """True si l'adresse vient d'un compte existant, False si elle est calculée."""
    google_user_id: str | None
    nom: str
    prenom: str
    nom_usage: str | None
    classe: str | None
    niveau: str | None
    code_etablissement: str | None
    regime: str | None
    site: str | None
    date_entree: date | None
    civilite: str | None
    poste_occupe: str | None
    matieres: str | None
    date_creation: datetime
    date_derniere_maj: datetime


def _serialiser(p: Personne, sites_par_id: dict[int, Site]) -> PersonneOut:
    site = sites_par_id.get(p.site_id) if p.site_id else None
    # Recalcul local plutôt que `p.email` : la relation `p.site` déclencherait
    # une requête par personne alors que les sites sont déjà chargés ici.
    if p.email_constate:
        email = p.email_constate
    elif site:
        email = calculer_email(p.prenom, p.nom, site.domaine_mail) or None
    else:
        email = None
    return PersonneOut(
        id=p.id,
        type=p.type,
        id_charlemagne=p.id_charlemagne,
        cle_pivot=p.cle_pivot,
        badge=p.badge,
        login=p.login,
        email=email,
        email_est_constate=bool(p.email_constate),
        google_user_id=p.google_user_id,
        nom=p.nom,
        prenom=p.prenom,
        nom_usage=p.nom_usage,
        classe=p.classe,
        niveau=p.niveau,
        code_etablissement=p.code_etablissement,
        regime=p.regime,
        site=site.nom if site else None,
        date_entree=p.date_entree,
        civilite=p.civilite,
        poste_occupe=p.poste_occupe,
        matieres=p.matieres,
        date_creation=p.date_creation,
        date_derniere_maj=p.date_derniere_maj,
    )


@router.get("", response_model=list[PersonneOut])
def lister_personnes(
    type: str | None = Query(None, description="Filtre : `eleve` ou `adulte`"),
    site: str | None = Query(None, description="Filtre par code site (NDE, NDK, SU)"),
    session: Session = Depends(db_session),
) -> list[PersonneOut]:
    """Liste toutes les personnes du référentiel, avec filtres optionnels."""
    sites_par_id = {s.id: s for s in session.query(Site).all()}
    q = session.query(Personne)
    if type:
        q = q.filter_by(type=type)
    if site:
        site_obj = next((s for s in sites_par_id.values() if s.nom == site), None)
        if site_obj is None:
            return []
        q = q.filter_by(site_id=site_obj.id)
    q = q.order_by(Personne.type, Personne.nom, Personne.prenom)
    return [_serialiser(p, sites_par_id) for p in q.all()]


@router.get("/{personne_id}", response_model=PersonneOut)
def obtenir_personne(
    personne_id: int, session: Session = Depends(db_session)
) -> PersonneOut:
    """Consulte une personne par son id référentiel."""
    p = session.query(Personne).filter_by(id=personne_id).one_or_none()
    if p is None:
        raise HTTPException(404, f"Personne introuvable : {personne_id}")
    sites_par_id = {s.id: s for s in session.query(Site).all()}
    return _serialiser(p, sites_par_id)


@router.get("/par-cle-pivot/{cle}", response_model=PersonneOut)
def obtenir_par_cle_pivot(
    cle: str, session: Session = Depends(db_session)
) -> PersonneOut:
    """Consulte une personne par sa clé pivot sérialisée (`E5292`, `A60`)."""
    if not cle or cle[0] not in ("E", "A"):
        raise HTTPException(400, f"Clé pivot invalide : {cle} (format attendu : E<n> ou A<n>)")
    try:
        id_ch = int(cle[1:])
    except ValueError:
        raise HTTPException(400, f"Clé pivot invalide : {cle}") from None
    type_p = "eleve" if cle[0] == "E" else "adulte"
    p = (
        session.query(Personne)
        .filter_by(type=type_p, id_charlemagne=id_ch)
        .one_or_none()
    )
    if p is None:
        raise HTTPException(404, f"Personne introuvable : {cle}")
    sites_par_id = {s.id: s for s in session.query(Site).all()}
    return _serialiser(p, sites_par_id)


class EmailPayload(BaseModel):
    email: str | None = Field(
        None,
        description=(
            "Adresse à figer pour cette personne. `null` ou chaîne vide "
            "rétablit l'adresse calculée."
        ),
        max_length=200,
    )


@router.patch("/{personne_id}/email", response_model=PersonneOut)
def definir_email_constate(
    personne_id: int,
    payload: EmailPayload,
    session: Session = Depends(db_session),
) -> PersonneOut:
    """Fige l'adresse mail d'une personne, ou rétablit le calcul.

    Sert aux cas que le programme refuse de trancher seul : deux homonymes
    dont l'un possède déjà `prenom.nom@`, une adresse historique hors
    convention. Une fois saisie, elle fait autorité comme si elle avait été
    relevée dans un export.
    """
    p = session.query(Personne).filter_by(id=personne_id).one_or_none()
    if p is None:
        raise HTTPException(404, f"Personne introuvable : {personne_id}")

    adresse = (payload.email or "").strip().lower()
    if adresse:
        if "@" not in adresse or adresse.startswith("@") or adresse.endswith("@"):
            raise HTTPException(400, f"Adresse invalide : {payload.email!r}")
        deja_pris = (
            session.query(Personne)
            .filter(Personne.email_constate == adresse, Personne.id != personne_id)
            .first()
        )
        if deja_pris is not None:
            raise HTTPException(
                409,
                f"{adresse} est déjà l'adresse de {deja_pris.prenom} "
                f"{deja_pris.nom} ({deja_pris.cle_pivot})",
            )
        p.email_constate = adresse
    else:
        p.email_constate = None

    session.commit()
    sites_par_id = {s.id: s for s in session.query(Site).all()}
    return _serialiser(p, sites_par_id)
