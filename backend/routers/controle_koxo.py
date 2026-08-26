"""Endpoint du contrôle avant synchronisation KoXo.

Voie base64, comme l'amorçage : le multipart est délibérément évité
(bug WebView2 observé au Lot 6).

Le contrôle **n'écrit rien**. Il n'a pas de mode simulation/réel parce
qu'il n'a pas de mode réel : il lit un export et raconte ce qu'il voit.
"""
from __future__ import annotations

import base64
from dataclasses import asdict
from pathlib import Path
from tempfile import NamedTemporaryFile

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session

from backend.database import db_session
from backend.services.controle_koxo import (
    RapportControle,
    controler_export_koxo,
    retenir_identifiants_constates,
)
from backend.services.rendre_identifiant import (
    RenduImpossible,
    rendre_identifiant,
)

router = APIRouter(prefix="/api/koxo", tags=["koxo"])


class ControlePayload(BaseModel):
    fichier_base64: str
    nom_fichier: str
    type_personne: str  # "eleve" | "adulte"
    site_id: int | None = None
    annee_id: int | None = None


class ControleOut(BaseModel):
    fichier: str
    type_personne: str
    nb_lignes: int
    nb_concordants: int
    colonnes_lues: list[str]
    separateur: str
    encodage: str
    date_naissance_renseignee: int
    contient_mots_de_passe: bool
    ecarts: list[dict]
    avertissements: list[str]
    nb_par_genre: dict[str, int]
    est_sain: bool


def _to_out(r: RapportControle) -> ControleOut:
    return ControleOut(
        fichier=r.fichier,
        type_personne=r.type_personne,
        nb_lignes=r.nb_lignes,
        nb_concordants=r.nb_concordants,
        colonnes_lues=r.colonnes_lues,
        separateur=r.separateur,
        encodage=r.encodage,
        date_naissance_renseignee=r.date_naissance_renseignee,
        contient_mots_de_passe=r.contient_mots_de_passe,
        ecarts=[asdict(e) for e in r.ecarts],
        avertissements=r.avertissements,
        nb_par_genre=r.nb_par_genre,
        est_sain=r.est_sain,
    )


@router.post("/controle", response_model=ControleOut)
def controler(
    payload: ControlePayload, session: Session = Depends(db_session)
) -> ControleOut:
    """Confronte un export KoXo au référentiel, sans rien modifier."""
    if payload.type_personne not in ("eleve", "adulte"):
        raise HTTPException(400, f"type_personne invalide : {payload.type_personne!r}")

    try:
        contenu = base64.b64decode(payload.fichier_base64)
    except Exception as e:
        raise HTTPException(400, f"Base64 invalide : {e}") from e
    if not contenu:
        raise HTTPException(400, "Fichier vide")

    suffixe = Path(payload.nom_fichier or "koxo.csv").suffix or ".csv"
    with NamedTemporaryFile(suffix=suffixe, delete=False) as tmp:
        tmp.write(contenu)
        chemin = Path(tmp.name)

    try:
        rapport = controler_export_koxo(
            session,
            chemin,
            type_personne=payload.type_personne,
            site_id=payload.site_id,
            annee_id=payload.annee_id,
        )
        # Le rapport ne modifie rien ; ceci garde trace de ce que l'export
        # détient, pour que le contrôle de l'autre base ne prenne pas ces
        # identifiants pour des erreurs à corriger.
        retenir_identifiants_constates(session, chemin)
        session.commit()
    except ValueError as e:
        raise HTTPException(400, str(e)) from None
    finally:
        # Le fichier porte des mots de passe en clair : il ne survit pas à
        # la requête, quoi qu'il arrive.
        try:
            chemin.unlink()
        except OSError:
            pass

    # Le nom du fichier déposé remplace celui du temporaire.
    rapport.fichier = payload.nom_fichier or rapport.fichier
    return _to_out(rapport)


class RendrePayload(BaseModel):
    login: str
    badge_titulaire: int
    mode: str = "simulation"


class RenduOut(BaseModel):
    login: str
    titulaire: str
    ancien_porteur: str
    nouveau_login_ancien_porteur: str
    echange: bool
    mode: str
    phrase: str
    """Ce qui a été fait — ou serait fait — en une phrase."""


@router.post("/rendre-identifiant", response_model=RenduOut)
def rendre(
    payload: RendrePayload, session: Session = Depends(db_session)
) -> RenduOut:
    """Rend un identifiant constaté à la personne qui le détient.

    La seule écriture de cet écran, et la seule circonstance où le
    programme touche à un identifiant : le rendre à qui le portait déjà,
    quand celui à qui il avait été attribué n'en a jamais rien fait.
    """
    if payload.mode not in ("simulation", "reel"):
        raise HTTPException(400, f"mode invalide : {payload.mode!r}")
    try:
        r = rendre_identifiant(
            session,
            login=payload.login,
            badge_titulaire=payload.badge_titulaire,
            mode=payload.mode,
        )
    except RenduImpossible as e:
        raise HTTPException(409, str(e)) from None
    except ValueError as e:
        raise HTTPException(400, str(e)) from None

    if payload.mode == "reel":
        from backend.services.journal import journaliser

        journaliser(
            session,
            type_operation="identifiant",
            cible="personne",
            mode="reel",
            parametres={"login": r.login, "badge_titulaire": payload.badge_titulaire},
            resultat={
                "titulaire": r.titulaire,
                "ancien_porteur": r.ancien_porteur,
                "nouveau_login": r.nouveau_login_ancien_porteur,
            },
        )
        session.commit()
    else:
        session.rollback()

    verbe = "rendu" if payload.mode == "reel" else "serait rendu"
    phrase = (
        f"« {r.login} » {verbe} à {r.titulaire} ; {r.ancien_porteur} "
        f"{'prend' if payload.mode == 'reel' else 'prendrait'} "
        f"« {r.nouveau_login_ancien_porteur} »"
        + (" (échange)" if r.echange else "")
        + "."
    )
    return RenduOut(
        login=r.login,
        titulaire=r.titulaire,
        ancien_porteur=r.ancien_porteur,
        nouveau_login_ancien_porteur=r.nouveau_login_ancien_porteur,
        echange=r.echange,
        mode=payload.mode,
        phrase=phrase,
    )
