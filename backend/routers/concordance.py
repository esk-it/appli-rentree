"""Croiser Charlemagne, le référentiel, Google et KoXo.

La lecture est **explicite** : elle parcourt tous les comptes du domaine et
les membres de chaque groupe de classe — compte une minute. La faire au
chargement de l'écran ferait payer cette attente à chaque passage.

Ce routeur ne corrige rien. La correction passe par le changement de
classe (`POST /api/mouvements/changer-classe`, avec `reprise=true`), qui
sait déjà déplacer l'unité et échanger les groupes en un geste, et qui
journalise. Dupliquer cette logique ici en ferait deux à maintenir.
"""
from __future__ import annotations

import base64

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session

from backend.database import db_session
from backend.models import TableCorrespondance
from backend.services.concordance import ConcordanceImpossible, croiser
from backend.services.google_api import ClientGoogle, charger_config

router = APIRouter(prefix="/api/concordance", tags=["concordance"])


class ConcordancePayload(BaseModel):
    """L'export Charlemagne, et de quoi lire les autres sources.

    Les fichiers passent en base64 dans le JSON plutôt qu'en multipart :
    c'est le contournement déjà retenu pour l'ingestion, le webview Tauri
    rejetant silencieusement certains envois multipart.
    """

    fichier_base64: str
    annee_id: int
    koxo_base64: str | None = None
    interroger_google: bool = True


class LigneOut(BaseModel):
    personne_id: int | None
    badge: str
    nom: str
    prenom: str
    site: str | None
    charlemagne: str | None
    referentiel: str | None
    google_classe: str | None
    google_ou: str | None
    koxo: str | None
    genres: list[str]
    propose: str | None


class ConcordanceReponse(BaseModel):
    annee_libelle: str
    google_consulte: bool
    koxo_fourni: bool
    nb_lignes_lues: int
    nb_accord: int
    nb_a_corriger: int
    par_genre: dict[str, int]
    classes_concernees: list[str]
    lignes: list[LigneOut]
    avertissements: list[str] = []


@router.post("", response_model=ConcordanceReponse)
def croiser_les_sources(
    payload: ConcordancePayload, session: Session = Depends(db_session)
) -> ConcordanceReponse:
    """Met côte à côte ce que chaque système dit de la classe d'un élève.

    Quatre systèmes la portent, et chacun l'apprend à un moment différent.
    Le bilan comparait le référentiel à Google, le contrôle KoXo comparait
    KoXo au référentiel, et Charlemagne n'entrait que par l'ingestion :
    personne ne voyait les quatre ensemble.
    """
    avertissements: list[str] = []

    try:
        brut = base64.b64decode(payload.fichier_base64)
    except Exception as e:
        raise HTTPException(400, f"Base64 invalide : {e}") from e

    lignes_koxo = None
    if payload.koxo_base64:
        from tempfile import NamedTemporaryFile
        from pathlib import Path

        from backend.services.controle_koxo import lire_export_brut

        try:
            contenu = base64.b64decode(payload.koxo_base64)
        except Exception as e:
            raise HTTPException(400, f"Base64 KoXo invalide : {e}") from e
        with NamedTemporaryFile(suffix=".csv", delete=False) as tmp:
            tmp.write(contenu)
            chemin = Path(tmp.name)
        try:
            lignes_koxo = lire_export_brut(chemin)
        except Exception as e:
            raise HTTPException(400, f"Export KoXo illisible : {e}") from None
        finally:
            try:
                chemin.unlink()
            except OSError:
                pass

    comptes = None
    membres: dict[str, list[str] | None] | None = None
    if payload.interroger_google:
        try:
            client = ClientGoogle(charger_config(session))
        except ValueError as e:
            # Sans Google, on croise quand même Charlemagne et le
            # référentiel : une colonne muette vaut mieux qu'un refus.
            avertissements.append(f"Google non interrogé : {e}")
            client = None
        if client is not None:
            try:
                comptes = client.lister_utilisateurs()
            except Exception as e:
                raise HTTPException(
                    502, f"Lecture Google impossible : {type(e).__name__}: {e}"
                ) from None
            adresses = {
                (t.groupe_google or "").strip().lower()
                for t in session.query(TableCorrespondance).all()
                if (t.groupe_google or "").strip()
            }
            membres = {}
            for g in sorted(adresses):
                try:
                    membres[g] = client.lister_membres(g)
                except Exception:
                    # `None`, pas `[]` : un groupe que Google ne connaît pas
                    # n'est pas un groupe vide, et confondre les deux ferait
                    # signaler toute une classe.
                    membres[g] = None

    try:
        r = croiser(
            session, brut, annee_id=payload.annee_id,
            comptes_google=comptes, membres_par_groupe=membres,
            lignes_koxo=lignes_koxo,
        )
    except ConcordanceImpossible as e:
        raise HTTPException(400, str(e)) from None

    return ConcordanceReponse(
        annee_libelle=r.annee_libelle,
        google_consulte=r.google_consulte,
        koxo_fourni=r.koxo_fourni,
        nb_lignes_lues=r.nb_lignes_lues,
        nb_accord=r.nb_accord,
        nb_a_corriger=r.nb_a_corriger,
        par_genre=r.par_genre(),
        classes_concernees=r.classes_concernees,
        lignes=[LigneOut(**vars(l)) for l in r.lignes],
        avertissements=avertissements,
    )
