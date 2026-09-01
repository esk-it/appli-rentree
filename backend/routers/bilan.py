"""Le bilan de rentrée : ce qui est en place, ce qui reste, ce qui cloche.

La lecture est **explicite** et jamais automatique. Dresser le bilan lit
tous les comptes du domaine et les membres de tous les groupes de classe —
plusieurs milliers d'appels sur l'instance réelle. Le faire au chargement
de l'écran ferait payer cette attente à chaque passage, y compris quand on
vient juste regarder le dernier résultat.
"""
from __future__ import annotations

from dataclasses import asdict

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy.orm import Session

from backend.database import db_session
from backend.models import TableCorrespondance
from backend.services.google_api import ClientGoogle, charger_config

router = APIRouter(prefix="/api/bilan", tags=["bilan"])


class ChiffresOut(BaseModel):
    inscrits: int
    avec_compte: int
    sans_compte: int
    en_ou_definitive: int
    en_ou_attente: int
    dans_leur_groupe: int


class ConstatOut(BaseModel):
    genre: str
    gravite: str
    personne_id: int | None
    nom: str
    prenom: str
    classe: str | None
    site: str | None
    email: str | None
    detail: str
    geste: str


class ResteOut(BaseModel):
    genre: str
    nombre: int
    libelle: str
    geste: str
    exemples: list[str]


class BilanOut(BaseModel):
    annee_libelle: str
    chiffres: ChiffresOut
    par_site: dict[str, ChiffresOut]
    nb_bloquants: int
    nb_attention: int
    par_genre: dict[str, int]
    tout_est_en_place: bool
    constats: list[ConstatOut]
    restes: list[ResteOut]


def _chiffres(c) -> ChiffresOut:
    return ChiffresOut(**{**asdict(c), "sans_compte": c.sans_compte})


@router.get("", response_model=BilanOut)
def dresser(
    annee_id: int = Query(..., description="Année dont on dresse le bilan"),
    annee_source_id: int | None = Query(
        None,
        description="Année précédente — sans elle, les sortants ne sont pas "
                    "repérés, et le contrôle est omis plutôt que rendu faux.",
    ),
    site_id: int | None = Query(None),
    session: Session = Depends(db_session),
) -> BilanOut:
    """Confronte tout le référentiel à tout Google. Ne modifie rien.

    Chaque écart porte le geste à faire et l'écran où le faire : un bilan
    qui ne dit pas quoi faire se relit une fois, puis s'ignore.
    """
    from backend.services.bilan_rentree import dresser_bilan

    try:
        client = ClientGoogle(charger_config(session))
    except ValueError as e:
        raise HTTPException(400, str(e)) from None

    try:
        comptes = client.lister_utilisateurs()
    except Exception as e:
        raise HTTPException(502, f"Lecture Google impossible : {type(e).__name__}: {e}")

    adresses = {
        (t.groupe_google or "").strip().lower()
        for t in session.query(TableCorrespondance).all()
        if (t.groupe_google or "").strip()
    }
    membres: dict[str, list[str] | None] = {}
    for g in sorted(adresses):
        try:
            membres[g] = client.lister_membres(g)
        except Exception:
            # `None`, pas `[]` : un groupe que Google ne connaît pas n'est
            # pas un groupe vide, et confondre les deux ferait signaler
            # toute une classe comme absente de sa liste.
            membres[g] = None

    try:
        b = dresser_bilan(
            session, comptes, membres,
            annee_id=annee_id, annee_source_id=annee_source_id, site_id=site_id,
        )
    except ValueError as e:
        raise HTTPException(404, str(e)) from None

    return BilanOut(
        annee_libelle=b.annee_libelle,
        chiffres=_chiffres(b.chiffres),
        par_site={k: _chiffres(v) for k, v in b.par_site.items()},
        nb_bloquants=b.nb_bloquants,
        nb_attention=b.nb_attention,
        par_genre=b.par_genre,
        tout_est_en_place=b.tout_est_en_place,
        constats=[ConstatOut(**vars(c)) for c in b.constats],
        restes=[ResteOut(**vars(r)) for r in b.restes],
    )
