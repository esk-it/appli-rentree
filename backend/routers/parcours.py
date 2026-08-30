"""Où en est la rentrée — l'avancement du parcours, étape par étape.

Deux routes, pour deux coûts.

`GET /avancement` ne lit que le référentiel : quelques requêtes locales,
appelable à chaque changement d'écran. Les étapes qui se constatent dans
Google y valent `inconnu`.

`POST /avancement/google` interroge Google — plusieurs appels réseau — et
renvoie le même rapport, ces cinq étapes renseignées. C'est un geste
délibéré, jamais un effet de bord de la navigation.
"""
from __future__ import annotations

from dataclasses import asdict

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session

from backend.database import db_session
from backend.services.parcours import A_FAIRE, FAITE, INCONNU, avancement

router = APIRouter(prefix="/api/parcours", tags=["parcours"])


class EtatEtapeOut(BaseModel):
    id: str
    etat: str
    detail: str
    source: str


class AvancementOut(BaseModel):
    annee_libelle: str
    nb_faites: int
    nb_inconnues: int
    etapes: list[EtatEtapeOut]


def _to_out(rapport) -> AvancementOut:
    return AvancementOut(
        annee_libelle=rapport.annee_libelle,
        nb_faites=rapport.nb_faites,
        nb_inconnues=rapport.nb_inconnues,
        etapes=[EtatEtapeOut(**asdict(e)) for e in rapport.etapes],
    )


@router.get("/avancement", response_model=AvancementOut)
def lire_avancement(
    annee_id: int, session: Session = Depends(db_session)
) -> AvancementOut:
    """L'avancement lisible sans réseau. Rejoué à chaque navigation."""
    try:
        return _to_out(avancement(session, annee_id=annee_id))
    except ValueError as e:
        raise HTTPException(400, str(e)) from None


class AvancementGooglePayload(BaseModel):
    annee_id: int
    site_id: int | None = None


def etats_google_depuis(
    session: Session,
    *,
    annee_id: int,
    comptes: list[dict] | None = None,
    diff=None,
    erreurs: dict[str, str] | None = None,
) -> dict[str, tuple[str, str]]:
    """Traduit ce que Google a répondu en états d'étapes. Ne va rien chercher.

    Séparer la lecture du réseau et l'interprétation permet d'éprouver
    celle-ci sans Google — et c'est elle qui porte les décisions : ce qui
    compte comme fait, et ce qu'on avoue ne pas savoir.

    Args:
        comptes: retour de `lister_utilisateurs`, ou `None` s'il a échoué.
        diff: rapport de composition des groupes, ou `None`.
        erreurs: `{id_etape: raison}` pour ce qui n'a pas pu être lu.
    """
    from backend.models import Personne, Snapshot

    erreurs = erreurs or {}
    resultats: dict[str, tuple[str, str]] = {}

    for etape, raison in erreurs.items():
        resultats[etape] = (INCONNU, raison)

    if comptes is not None:
        from backend.services.adresses_divergentes import detecter_divergences

        r = detecter_divergences(session, comptes, annee_id=annee_id)
        resultats["adresses"] = (
            (FAITE, f"{r.nb_examines} adresse(s) examinée(s), aucune divergente.")
            if not r.divergences
            else (
                A_FAIRE,
                f"{len(r.divergences)} adresse(s) ne désignent aucun compte, "
                f"dont {r.nb_resolvables} corrigeable(s).",
            )
        )

        ids = {
            s.personne_id
            for s in session.query(Snapshot.personne_id).filter_by(
                annee_scolaire_id=annee_id
            )
        }
        connues = {(u.get("email") or "").lower() for u in comptes}
        for u in comptes:
            connues.update(a.lower() for a in (u.get("alias") or []) if a)
        eleves = [
            p
            for p in session.query(Personne).filter_by(type="eleve").all()
            if p.id in ids and p.email
        ]
        absents = [p for p in eleves if p.email.lower() not in connues]
        if not eleves:
            resultats["comptes"] = (
                INCONNU,
                "Aucun élève photographié pour cette année.",
            )
        elif absents:
            resultats["comptes"] = (
                A_FAIRE,
                f"{len(absents)} élève(s) sans compte Google.",
            )
        else:
            resultats["comptes"] = (
                FAITE,
                f"Les {len(eleves)} élèves de l'année ont un compte.",
            )

    if diff is not None:
        resultats["groupes"] = (
            (FAITE, "Chaque classe a la composition attendue.")
            if diff.nb_a_ajouter == 0
            else (A_FAIRE, f"{diff.nb_a_ajouter} entrée(s) de groupe à appliquer.")
        )
        absents = list(diff.groupes_absents)
        resultats["arborescence"] = (
            (FAITE, "Tous les groupes déclarés existent dans Google.")
            if not absents
            else (
                A_FAIRE,
                f"{len(absents)} groupe(s) déclarés dans la Table sont absents "
                "de Google.",
            )
        )

    # « Vider » se constate sur l'arbre de l'année révolue, que la Table ne
    # décrit plus : le programme ne sait pas le désigner seul.
    resultats.setdefault(
        "vider",
        (
            INCONNU,
            "Se constate sur l'arbre de l'année révolue, que la Table ne "
            "décrit plus — regarde l'écran Sortants.",
        ),
    )
    return resultats


def _lire_google(session: Session, annee_id: int, site_id: int | None):
    """Va chercher chez Google, et rend ce qu'il a obtenu — ou pourquoi non.

    Chaque lecture est isolée : celle qui échoue laisse ses étapes à
    `inconnu` avec la raison, plutôt que de faire tomber les autres.
    """
    from backend.routers.google_api import _diff_groupes
    from backend.services.google_api import ClientGoogle, charger_config

    erreurs: dict[str, str] = {}
    comptes = diff = None

    try:
        client = ClientGoogle(charger_config(session))
    except Exception as e:  # noqa: BLE001
        for etape in ("adresses", "comptes", "arborescence", "groupes"):
            erreurs[etape] = f"Google n'est pas interrogeable : {e}"
        return comptes, diff, erreurs

    try:
        comptes = client.lister_utilisateurs()
    except Exception as e:  # noqa: BLE001
        for etape in ("adresses", "comptes"):
            erreurs[etape] = f"Lecture des comptes impossible : {e}"

    try:
        _, diff = _diff_groupes(session, annee_id, site_id)
    except Exception as e:  # noqa: BLE001
        for etape in ("arborescence", "groupes"):
            erreurs[etape] = f"Lecture des groupes impossible : {e}"

    return comptes, diff, erreurs


@router.post("/avancement/google", response_model=AvancementOut)
def lire_avancement_google(
    payload: AvancementGooglePayload, session: Session = Depends(db_session)
) -> AvancementOut:
    """L'avancement complet, Google interrogé. Geste délibéré, pas un réflexe."""
    comptes, diff, erreurs = _lire_google(
        session, payload.annee_id, payload.site_id
    )
    etats = etats_google_depuis(
        session, annee_id=payload.annee_id, comptes=comptes, diff=diff,
        erreurs=erreurs,
    )
    try:
        return _to_out(
            avancement(session, annee_id=payload.annee_id, etats_google=etats)
        )
    except ValueError as e:
        raise HTTPException(400, str(e)) from None
