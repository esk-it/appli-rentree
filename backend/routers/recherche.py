"""Endpoint de recherche globale cross-snapshot.

Cherche dans tous les snapshots d'élèves et adultes par nom, prénom,
badge, num_personnel. Regroupe par personne (clé num_badge ou nom+prénom)
pour montrer son historique multi-année.
"""
from __future__ import annotations

from collections import defaultdict

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel
from sqlalchemy import or_
from sqlalchemy.orm import Session
from unidecode import unidecode

from backend.database import db_session
from backend.models import (
    AdulteSnapshot,
    AnneeScolaire,
    EleveSnapshot,
    Etablissement,
)

router = APIRouter(prefix="/api/recherche", tags=["recherche"])


class ApparitionEleve(BaseModel):
    annee_libelle: str
    code_classe: str | None
    code_niveau: str | None
    etablissement_code: str
    code_regime: str | None


class ResultatEleve(BaseModel):
    type: str = "eleve"
    nom: str
    prenom: str
    num_badge: int | None
    apparitions: list[ApparitionEleve]


class ApparitionAdulte(BaseModel):
    annee_libelle: str
    fonction: str | None
    matieres: str | None
    etablissement_code: str | None


class ResultatAdulte(BaseModel):
    type: str = "adulte"
    nom: str
    prenom: str
    num_personnel: int | None
    apparitions: list[ApparitionAdulte]


class ResponseRecherche(BaseModel):
    terme: str
    nb_eleves: int
    nb_adultes: int
    eleves: list[ResultatEleve]
    adultes: list[ResultatAdulte]


def _match(terme: str, *valeurs: str | None) -> bool:
    """Match insensible à la casse + sans accents."""
    if not terme:
        return False
    t = unidecode(terme).lower()
    for v in valeurs:
        if not v:
            continue
        if t in unidecode(str(v)).lower():
            return True
    return False


@router.get("", response_model=ResponseRecherche)
def rechercher(
    q: str = Query(..., min_length=1, description="Terme de recherche"),
    limite: int = Query(30, ge=1, le=200),
    session: Session = Depends(db_session),
) -> ResponseRecherche:
    """Recherche globale dans tous les snapshots.

    Pour les chiffres : match exact sur num_badge / num_personnel.
    Pour les lettres : LIKE insensible à la casse sur nom, prénom.
    """
    terme = q.strip()
    annees_par_id = {
        a.id: a for a in session.query(AnneeScolaire).all()
    }
    etabs_par_id = {
        e.id: e for e in session.query(Etablissement).all()
    }

    # Construction des filtres SQL
    pattern = f"%{terme}%"
    eleve_filtres = [
        EleveSnapshot.nom.ilike(pattern),
        EleveSnapshot.prenom.ilike(pattern),
    ]
    try:
        as_int = int(terme)
        eleve_filtres.append(EleveSnapshot.num_badge == as_int)
    except ValueError:
        pass

    eleves = session.query(EleveSnapshot).filter(or_(*eleve_filtres)).all()
    adulte_filtres = [
        AdulteSnapshot.nom.ilike(pattern),
        AdulteSnapshot.prenom.ilike(pattern),
    ]
    try:
        as_int = int(terme)
        adulte_filtres.append(AdulteSnapshot.num_personnel == as_int)
    except ValueError:
        pass

    adultes = session.query(AdulteSnapshot).filter(or_(*adulte_filtres)).all()

    # Regroupement par "personne" pour les élèves
    groupes_eleves: dict[tuple, dict] = defaultdict(
        lambda: {"resume": None, "apparitions": []}
    )
    for e in eleves:
        cle = (
            ("badge", e.num_badge)
            if e.num_badge is not None
            else ("nomprenom", unidecode(e.nom or "").upper(), unidecode(e.prenom or "").upper())
        )
        groupes_eleves[cle]["resume"] = (e.nom, e.prenom, e.num_badge)
        annee = annees_par_id.get(e.annee_scolaire_id)
        etab = etabs_par_id.get(e.etablissement_id)
        groupes_eleves[cle]["apparitions"].append(
            ApparitionEleve(
                annee_libelle=annee.libelle if annee else "?",
                code_classe=e.code_classe,
                code_niveau=e.code_niveau,
                etablissement_code=etab.code_court if etab else "?",
                code_regime=e.code_regime,
            )
        )

    # Regroupement adultes
    groupes_adultes: dict[tuple, dict] = defaultdict(
        lambda: {"resume": None, "apparitions": []}
    )
    for a in adultes:
        cle = (
            ("perso", a.num_personnel)
            if a.num_personnel is not None
            else ("nomprenom", unidecode(a.nom or "").upper(), unidecode(a.prenom or "").upper())
        )
        groupes_adultes[cle]["resume"] = (a.nom, a.prenom, a.num_personnel)
        annee = annees_par_id.get(a.annee_scolaire_id)
        etab = etabs_par_id.get(a.etablissement_id) if a.etablissement_id else None
        groupes_adultes[cle]["apparitions"].append(
            ApparitionAdulte(
                annee_libelle=annee.libelle if annee else "?",
                fonction=a.fonction,
                matieres=a.matieres,
                etablissement_code=etab.code_court if etab else None,
            )
        )

    # Tri par récence (dernière apparition) + nom
    def _trier_eleves(items):
        for v in items.values():
            v["apparitions"].sort(key=lambda x: x.annee_libelle, reverse=True)
        return sorted(
            items.values(),
            key=lambda v: (v["resume"][0] or "", v["resume"][1] or ""),
        )

    resultats_eleves = [
        ResultatEleve(
            nom=v["resume"][0] or "",
            prenom=v["resume"][1] or "",
            num_badge=v["resume"][2],
            apparitions=v["apparitions"],
        )
        for v in _trier_eleves(groupes_eleves)[:limite]
    ]

    resultats_adultes = [
        ResultatAdulte(
            nom=v["resume"][0] or "",
            prenom=v["resume"][1] or "",
            num_personnel=v["resume"][2],
            apparitions=v["apparitions"],
        )
        for v in _trier_eleves(groupes_adultes)[:limite]
    ]

    return ResponseRecherche(
        terme=terme,
        nb_eleves=len(resultats_eleves),
        nb_adultes=len(resultats_adultes),
        eleves=resultats_eleves,
        adultes=resultats_adultes,
    )
