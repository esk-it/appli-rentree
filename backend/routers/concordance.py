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
from pydantic import BaseModel, field_validator
from sqlalchemy.orm import Session

from backend.database import db_session
from backend.models import TableCorrespondance
from backend.services.coherence import (
    compter,
    enregistrer,
    etat_des_liens,
    verdicts_par_personne,
)
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
    koxo_base64: list[str] = []
    """Un export **par base** : KoXo a un serveur par établissement, et
    Charlemagne comme Google en couvrent plusieurs. Les déposer tous
    ensemble est le seul moyen de juger toute l'école en une passe."""
    interroger_google: bool = True

    @field_validator("koxo_base64", mode="before")
    @classmethod
    def _un_ou_plusieurs(cls, v):
        """Le champ n'a longtemps porté qu'un fichier ; il l'accepte encore."""
        if v is None:
            return []
        if isinstance(v, str):
            return [v] if v else []
        return v


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
    koxo_consulte: bool
    genres: list[str]
    propose: str | None


class ConcordanceReponse(BaseModel):
    annee_libelle: str
    google_consulte: bool
    koxo_fourni: bool
    koxo_sites: list[str] = []
    nb_lignes_lues: int
    nb_accord: int
    nb_a_corriger: int
    par_genre: dict[str, int]
    classes_concernees: list[str]
    lignes: list[LigneOut]
    avertissements: list[str] = []
    acces_secondaires: list[str] = []
    """Comptes posés sur la base KoXo d'un autre établissement — la DAO.
    Nommés, jamais comparés à la classe."""


def _lire_les_exports_koxo(fichiers: list[str]) -> tuple[list[list], list[str]]:
    """Les lignes de chaque base KoXo déposée, une liste par fichier.

    Elles restent **séparées** : chaque base dit de quel établissement elle
    parle, et c'est la réunion qui couvre l'école. Les fusionner avant de
    calculer cette couverture ferait disparaître une petite base derrière
    une grosse.

    KoXo a **un serveur par établissement** : on ne peut en exporter qu'un à
    la fois, alors que Charlemagne et Google couvrent toute l'école. Juger
    l'école entière demande donc de déposer les deux exports ensemble — les
    fusionner ici évite de relancer le croisement base par base, et surtout
    évite qu'une base absente fasse passer ses élèves pour introuvables.

    L'appariement se fait sur l'`ID unique`, où le programme écrit le badge
    Charlemagne. Un même badge deux fois est une anomalie, et les deux
    formes qu'elle prend ne se soignent pas pareil :

    - **dans un même export** : deux comptes réseau pour un seul élève
      (`lperon` et `lperon1`), nés d'une création rejouée ;
    - **entre deux exports** : un élève qui a changé d'établissement sans
      que son compte soit retiré de l'ancien serveur.

    Dans les deux cas on garde la première occurrence et on le dit, plutôt
    que de trancher en silence.
    """
    from pathlib import Path
    from tempfile import NamedTemporaryFile

    from backend.services.controle_koxo import lire_export_brut

    bases: list[list] = []
    avertissements: list[str] = []
    en_double: list[str] = []

    for rang, b64 in enumerate(fichiers, start=1):
        rang_dit = f"fichier {rang} sur {len(fichiers)}"
        try:
            contenu = base64.b64decode(b64)
        except Exception as e:
            raise HTTPException(400, f"Base64 KoXo invalide ({rang_dit}) : {e}") from e

        with NamedTemporaryFile(suffix=".csv", delete=False) as tmp:
            tmp.write(contenu)
            chemin = Path(tmp.name)
        try:
            # `lire_export_brut` rend cinq choses — les lignes, les colonnes
            # reconnues, le séparateur, l'encodage, et s'il portait des mots
            # de passe. Prendre le tuple entier pour la liste faisait passer
            # les mille six cent soixante-sept élèves pour absents de KoXo.
            du_fichier, colonnes, _sep, _enc, _mdp = lire_export_brut(chemin)
        except Exception as e:
            raise HTTPException(
                400, f"Export KoXo illisible ({rang_dit}) : {e}"
            ) from None
        finally:
            try:
                chemin.unlink()
            except OSError:
                pass

        if not du_fichier:
            raise HTTPException(
                400,
                f"L'export KoXo ne contient aucune ligne exploitable ({rang_dit}). "
                f"Colonnes reconnues : {', '.join(colonnes) or 'aucune'}.",
            )

        # Les doublons ne se cherchent qu'**à l'intérieur** d'une base. Un
        # même élève dans deux bases n'est pas une anomalie en soi : les
        # élèves de SU qui suivent la DAO au lycée ont un compte sur le
        # serveur de NDK. C'est le service, qui connaît le site de chacun,
        # qui dit lequel des deux fait foi.
        vus: dict[str, str] = {}
        retenues = []
        for l in du_fichier:
            ident = (getattr(l, "id_unique", "") or "").strip()
            login = (getattr(l, "login", "") or "").strip()
            if ident and ident in vus:
                qui = f"{getattr(l, 'prenom', '')} {getattr(l, 'nom', '')}".strip()
                en_double.append(f"{qui or ident} ({vus[ident]} et {login})")
                continue
            if ident:
                vus[ident] = login
            retenues.append(l)
        bases.append(retenues)

    if en_double:
        avertissements.append(
            f"{len(en_double)} élève(s) ont deux comptes dans la même base KoXo "
            "— une création rejouée. Le second est à supprimer dans KoXo : "
            + ", ".join(en_double[:12])
        )
    return bases, avertissements


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

    koxo_par_base = None
    if payload.koxo_base64:
        koxo_par_base, avertis = _lire_les_exports_koxo(payload.koxo_base64)
        avertissements.extend(avertis)

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
            koxo_par_base=koxo_par_base,
        )
    except ConcordanceImpossible as e:
        raise HTTPException(400, str(e)) from None

    # Le constat est rangé avant d'être rendu : sans ça, il mourait avec
    # l'écran, et la colonne « Cohérent » du référentiel n'avait jamais le
    # droit d'écrire autre chose que « Pas vérifié ».
    try:
        enregistrer(session, r)
    except Exception as e:  # pragma: no cover - le croisement prime
        # Ranger est un service rendu, pas la raison de l'appel : un échec
        # d'écriture ne doit pas emporter une minute de lecture Google.
        avertissements.append(f"Constat non enregistré : {type(e).__name__}: {e}")

    return ConcordanceReponse(
        annee_libelle=r.annee_libelle,
        google_consulte=r.google_consulte,
        koxo_fourni=r.koxo_fourni,
        koxo_sites=r.koxo_sites,
        nb_lignes_lues=r.nb_lignes_lues,
        nb_accord=r.nb_accord,
        nb_a_corriger=r.nb_a_corriger,
        par_genre=r.par_genre(),
        classes_concernees=r.classes_concernees,
        lignes=[LigneOut(**vars(l)) for l in r.lignes],
        avertissements=avertissements,
        acces_secondaires=r.acces_secondaires,
    )


# ---------------------------------------------------------------------------
# Ce que les croisements ont laissé derrière eux
# ---------------------------------------------------------------------------


class DetailOut(BaseModel):
    genre: str
    nb: int


class LienOut(BaseModel):
    systeme: str
    libelle: str
    etat: str
    nb_ecarts: int
    nb_absents: int
    nb_verifies: int
    verifie_le: str | None
    pourquoi: str | None
    details: list[DetailOut]


class LiensReponse(BaseModel):
    """Le schéma de la Cohérence : le centre, et les six liens."""

    nb_personnes: int
    nb_eleves: int
    nb_adultes: int
    nb_verifiees: int
    liens: list[LienOut]


@router.get("/liens", response_model=LiensReponse)
def liens(session: Session = Depends(db_session)) -> LiensReponse:
    """L'état de chaque lien, sans rien relancer.

    L'écran s'ouvre sur ce qu'on sait déjà. Croiser demande un export et
    une minute : le faire au chargement rendrait l'écran inutilisable
    pour le seul geste qu'on y fait le plus souvent — regarder.
    """
    chiffres = compter(session)
    return LiensReponse(
        **chiffres,
        liens=[
            LienOut(
                systeme=l.systeme,
                libelle=l.libelle,
                etat=l.etat,
                nb_ecarts=l.nb_ecarts,
                nb_absents=l.nb_absents,
                nb_verifies=l.nb_verifies,
                verifie_le=l.verifie_le.isoformat() if l.verifie_le else None,
                pourquoi=l.pourquoi,
                details=[DetailOut(**d) for d in l.details],
            )
            for l in etat_des_liens(session)
        ],
    )


class VerdictPersonneOut(BaseModel):
    etat: str
    verifie_le: str
    systemes: list[dict]


@router.get("/verdicts", response_model=dict[int, VerdictPersonneOut])
def verdicts(session: Session = Depends(db_session)):
    """Par personne, ce que le dernier croisement a constaté d'elle.

    Le référentiel s'en sert pour sa colonne « Cohérent ». Une personne
    absente de la réponse n'a jamais été croisée : la liste écrira « Pas
    vérifié » plutôt que de la déclarer cohérente sans l'avoir regardée.
    """
    return {
        pid: VerdictPersonneOut(
            etat=v["etat"],
            verifie_le=v["verifie_le"].isoformat(),
            systemes=v["systemes"],
        )
        for pid, v in verdicts_par_personne(session).items()
    }
