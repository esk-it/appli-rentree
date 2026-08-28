"""Endpoints d'exports vers les cibles (KoXo, Google, PMB, JPM, CardStudio).

Le contenu du fichier est renvoyé en base64 dans un JSON — le frontend
décode et déclenche le téléchargement (choix Tauri, pour éviter les popups
du webview).

## Enregistrement du cycle de vie

Chaque export accepte `enregistrer_prevus`. Quand ce drapeau est vrai et
que la catégorie est `nouveaux`, les personnes du fichier sont inscrites
en `CompteCible(etat="prevu")` sur la cible concernée — c'est ce qui
alimente l'écran Suivi. La confirmation de l'import effectif se fait
ensuite via `POST /api/suivi/confirmer-creation`.
"""
from __future__ import annotations

import base64
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session

from backend.database import db_session
from backend.models import Site
from backend.services.cycle_vie import (
    SUFFIXE_PAR_DEFAUT,
    SUFFIXE_SERVEUR_PAR_SITE,
    enregistrer_prevus_pour_export,
)
from backend.services.exports_cardstudio import generer_xlsx_cardstudio
from backend.services.exports_google import (
    generer_csv_google,
    generer_csv_google_avec_mdp,
)
from backend.services.exports_google_groupes import generer_csv_groupes_google
from backend.services.exports_jpm import generer_csv_jpm
from backend.services.exports_koxo import generer_csv_koxo
from backend.services.exports_pmb import generer_csv_pmb
from backend.services.journal import journaliser

router = APIRouter(prefix="/api/exports", tags=["exports"])


def _libelle_annee(session: Session, annee_id: int | None) -> str | None:
    if annee_id is None:
        return None
    from backend.models import AnneeScolaire

    a = session.query(AnneeScolaire).filter_by(id=annee_id).one_or_none()
    return a.libelle if a else None


def _journaliser_export(
    session: Session,
    *,
    cible: str,
    site_nom: str,
    type_personne: str | None,
    categorie: str | None,
    annee_cible_id: int,
    annee_source_id: int | None,
    resultat: dict,
) -> None:
    """Trace l'export dans le journal. Ne bloque jamais la génération."""
    try:
        journaliser(
            session,
            type_operation="export",
            cible=cible,
            annee_libelle=_libelle_annee(session, annee_cible_id),
            annee_source_libelle=_libelle_annee(session, annee_source_id),
            parametres={
                "site": site_nom,
                "type_personne": type_personne,
                "categorie": categorie,
            },
            resultat=resultat,
        )
        session.commit()
    except Exception:  # pragma: no cover — le journal ne doit rien casser
        session.rollback()


def _cible_pour_export(session: Session, famille: str, site_id: int) -> str:
    """Résout le code cible d'un export.

    `koxo` et `pmb` ont une instance par site (NDE rattaché à NDK) ; les
    autres familles sont uniques.
    """
    if famille not in ("koxo", "pmb"):
        return famille
    site = session.query(Site).filter_by(id=site_id).one_or_none()
    nom = site.nom.upper() if site else ""
    suffixe = SUFFIXE_SERVEUR_PAR_SITE.get(nom, SUFFIXE_PAR_DEFAUT)
    return f"{famille}_{suffixe}"


def _enregistrer_si_demande(
    session: Session,
    *,
    demande: bool,
    famille: str,
    site_id: int,
    type_personne: str,
    categorie: str,
    annee_cible_id: int,
    annee_source_id: int | None,
) -> int:
    """Inscrit les personnes de l'export en `prevu`. Retourne le nb créé.

    Ne fait rien hors catégorie `nouveaux` : inscrire « tous » en prévu
    n'aurait pas de sens (les comptes existants sont déjà actifs), et
    « anciens » relève de la politique de sortie, pas de la création.
    """
    if not demande or categorie != "nouveaux":
        return 0
    cible = _cible_pour_export(session, famille, site_id)
    rapport = enregistrer_prevus_pour_export(
        session,
        site_id=site_id,
        type_personne=type_personne,
        annee_cible_id=annee_cible_id,
        annee_source_id=annee_source_id,
        categorie=categorie,
        cible_unique=cible,
    )
    session.commit()
    return rapport.nb_crees


class ExportKoxoPayload(BaseModel):
    site_id: int
    type_personne: Literal["eleve", "adulte"]
    categorie: Literal["tous", "nouveaux", "anciens"]
    annee_cible_id: int
    annee_source_id: int | None = None
    enregistrer_prevus: bool = False
    groupe_secondaire_force: str | None = None
    """Groupe secondaire imposé à toutes les lignes. Réservé aux sortants :
    il sert à les rassembler dans un groupe dédié plutôt que de les laisser
    porter leur dernière classe."""

    base_koxo: str | None = None
    """Nom du site dont la base KoXo recevra ce fichier, s'il diffère du site
    choisi. Les professeurs vivent dans les deux serveurs, qui nomment leurs
    groupes différemment ; c'est la base visée qui fait autorité."""


class ExportKoxoReponse(BaseModel):
    site_nom: str
    type_personne: str
    categorie: str
    nb_lignes: int
    nom_fichier: str
    contenu_base64: str
    """Contenu CSV encodé cp1252 puis base64 — le frontend décode et déclenche
    le téléchargement."""
    nb_prevus_enregistres: int = 0
    groupe_secondaire_force: str | None = None
    avertissements: list[str] = []


@router.post("/koxo", response_model=ExportKoxoReponse)
def exporter_koxo(
    payload: ExportKoxoPayload, session: Session = Depends(db_session)
) -> ExportKoxoReponse:
    """Génère un CSV KoXo (Tous / Nouveaux / Anciens) pour un site donné."""
    try:
        contenu, rapport = generer_csv_koxo(
            session=session,
            site_id=payload.site_id,
            type_personne=payload.type_personne,
            categorie=payload.categorie,
            annee_cible_id=payload.annee_cible_id,
            annee_source_id=payload.annee_source_id,
            groupe_secondaire_force=payload.groupe_secondaire_force,
            base_koxo=payload.base_koxo,
        )
        nb_prevus = _enregistrer_si_demande(
            session,
            demande=payload.enregistrer_prevus,
            famille="koxo",
            site_id=payload.site_id,
            type_personne=payload.type_personne,
            categorie=payload.categorie,
            annee_cible_id=payload.annee_cible_id,
            annee_source_id=payload.annee_source_id,
        )
    except ValueError as e:
        raise HTTPException(400, str(e))

    _journaliser_export(
        session, cible="koxo", site_nom=rapport.site_nom,
        type_personne=payload.type_personne, categorie=payload.categorie,
        annee_cible_id=payload.annee_cible_id, annee_source_id=payload.annee_source_id,
        resultat={"nb_lignes": rapport.nb_lignes, "nb_prevus_enregistres": nb_prevus},
    )

    return ExportKoxoReponse(
        site_nom=rapport.site_nom,
        type_personne=rapport.type_personne,
        categorie=rapport.categorie,
        nb_lignes=rapport.nb_lignes,
        nom_fichier=rapport.nom_fichier_suggere,
        contenu_base64=base64.b64encode(contenu).decode("ascii"),
        nb_prevus_enregistres=nb_prevus,
        groupe_secondaire_force=rapport.groupe_secondaire_force,
        avertissements=rapport.avertissements,
    )


# ---------------------------------------------------------------------------
# Google Workspace (Lot 10a)
# ---------------------------------------------------------------------------


class ExportGooglePayload(BaseModel):
    site_id: int
    type_personne: Literal["eleve", "adulte"]
    categorie: Literal["tous", "nouveaux", "anciens"]
    annee_cible_id: int
    annee_source_id: int | None = None
    enregistrer_prevus: bool = False


class ExportGoogleReponse(BaseModel):
    site_nom: str
    type_personne: str
    categorie: str
    nb_lignes: int
    nb_sans_ou: int
    nom_fichier: str
    contenu_base64: str
    nb_prevus_enregistres: int = 0
    avertissements: list[str] = []


@router.post("/google", response_model=ExportGoogleReponse)
def exporter_google(
    payload: ExportGooglePayload, session: Session = Depends(db_session)
) -> ExportGoogleReponse:
    """Génère un CSV Google Admin bulk-import."""
    try:
        contenu, rapport = generer_csv_google(
            session=session,
            site_id=payload.site_id,
            type_personne=payload.type_personne,
            categorie=payload.categorie,
            annee_cible_id=payload.annee_cible_id,
            annee_source_id=payload.annee_source_id,
        )
        nb_prevus = _enregistrer_si_demande(
            session,
            demande=payload.enregistrer_prevus,
            famille="google",
            site_id=payload.site_id,
            type_personne=payload.type_personne,
            categorie=payload.categorie,
            annee_cible_id=payload.annee_cible_id,
            annee_source_id=payload.annee_source_id,
        )
    except ValueError as e:
        raise HTTPException(400, str(e))

    _journaliser_export(
        session, cible="google", site_nom=rapport.site_nom,
        type_personne=payload.type_personne, categorie=payload.categorie,
        annee_cible_id=payload.annee_cible_id, annee_source_id=payload.annee_source_id,
        resultat={
            "nb_lignes": rapport.nb_lignes,
            "nb_sans_ou": rapport.nb_sans_ou,
            "nb_prevus_enregistres": nb_prevus,
        },
    )

    return ExportGoogleReponse(
        site_nom=rapport.site_nom,
        type_personne=rapport.type_personne,
        categorie=rapport.categorie,
        nb_lignes=rapport.nb_lignes,
        nb_sans_ou=rapport.nb_sans_ou,
        nom_fichier=rapport.nom_fichier_suggere,
        contenu_base64=base64.b64encode(contenu).decode("ascii"),
        nb_prevus_enregistres=nb_prevus,
    )


# ---------------------------------------------------------------------------
# Lot 8b — Boucle retour KoXo → Google (MDP en mémoire uniquement)
# ---------------------------------------------------------------------------


class ExportGoogleAvecMdpPayload(BaseModel):
    """Le CSV KoXo enrichi (avec MDP) est envoyé en base64 dans le corps JSON.

    Les MDP transitent en mémoire côté serveur uniquement — jamais persistés."""

    csv_koxo_base64: str
    site_id: int
    type_personne: Literal["eleve", "adulte"]
    categorie: Literal["tous", "nouveaux", "anciens"]
    annee_cible_id: int
    annee_source_id: int | None = None


class ExportGoogleAvecMdpReponse(BaseModel):
    site_nom: str
    type_personne: str
    categorie: str
    nb_lignes: int
    nb_lignes_avec_mdp: int
    nb_sans_ou: int
    nb_mdp_orphelins: int
    nom_fichier: str
    contenu_base64: str
    avertissements: list[str] = []


@router.post("/google-avec-mdp", response_model=ExportGoogleAvecMdpReponse)
def exporter_google_avec_mdp(
    payload: ExportGoogleAvecMdpPayload, session: Session = Depends(db_session)
) -> ExportGoogleAvecMdpReponse:
    """Enrichit un CSV Google avec les MDP extraits d'un CSV KoXo."""
    try:
        contenu_koxo = base64.b64decode(payload.csv_koxo_base64)
    except Exception as e:
        raise HTTPException(400, f"Base64 CSV KoXo invalide : {e}") from e
    if not contenu_koxo:
        raise HTTPException(400, "CSV KoXo vide")

    try:
        contenu, rapport = generer_csv_google_avec_mdp(
            session=session,
            csv_koxo_bytes=contenu_koxo,
            site_id=payload.site_id,
            type_personne=payload.type_personne,
            categorie=payload.categorie,
            annee_cible_id=payload.annee_cible_id,
            annee_source_id=payload.annee_source_id,
        )
    except ValueError as e:
        raise HTTPException(400, str(e))

    return ExportGoogleAvecMdpReponse(
        site_nom=rapport.site_nom,
        type_personne=rapport.type_personne,
        categorie=rapport.categorie,
        nb_lignes=rapport.nb_lignes,
        nb_lignes_avec_mdp=rapport.nb_lignes_avec_mdp,
        nb_sans_ou=rapport.nb_sans_ou,
        nb_mdp_orphelins=rapport.nb_mdp_orphelins,
        nom_fichier=rapport.nom_fichier_suggere,
        contenu_base64=base64.b64encode(contenu).decode("ascii"),
        avertissements=rapport.avertissements,
    )


# ---------------------------------------------------------------------------
# Groupes Google (appartenances) — mailing lists de classe + groupes profs
# ---------------------------------------------------------------------------


class ExportGroupesPayload(BaseModel):
    site_id: int
    annee_id: int
    inclure_eleves: bool = True
    inclure_profs: bool = True


class ExportGroupesReponse(BaseModel):
    site_nom: str
    annee_libelle: str
    nb_lignes: int
    nb_lignes_eleves: int
    nb_lignes_profs: int
    nb_groupes_classes: int
    nb_groupes_profs: int
    classes_sans_groupe: list[str]
    groupes_profs_vides: list[str]
    nb_membres_sans_email: int
    nom_fichier: str
    contenu_base64: str


@router.post("/google-groupes", response_model=ExportGroupesReponse)
def exporter_groupes_google(
    payload: ExportGroupesPayload, session: Session = Depends(db_session)
) -> ExportGroupesReponse:
    """Génère le CSV d'appartenance aux groupes Google."""
    try:
        contenu, r = generer_csv_groupes_google(
            session=session,
            site_id=payload.site_id,
            annee_id=payload.annee_id,
            inclure_eleves=payload.inclure_eleves,
            inclure_profs=payload.inclure_profs,
        )
    except ValueError as e:
        raise HTTPException(400, str(e))

    return ExportGroupesReponse(
        site_nom=r.site_nom,
        annee_libelle=r.annee_libelle,
        nb_lignes=r.nb_lignes,
        nb_lignes_eleves=r.nb_lignes_eleves,
        nb_lignes_profs=r.nb_lignes_profs,
        nb_groupes_classes=r.nb_groupes_classes,
        nb_groupes_profs=r.nb_groupes_profs,
        classes_sans_groupe=r.classes_sans_groupe,
        groupes_profs_vides=r.groupes_profs_vides,
        nb_membres_sans_email=r.nb_membres_sans_email,
        nom_fichier=r.nom_fichier_suggere,
        contenu_base64=base64.b64encode(contenu).decode("ascii"),
    )


# ---------------------------------------------------------------------------
# Lot 11a — PMB
# ---------------------------------------------------------------------------


class ExportPmbPayload(BaseModel):
    site_id: int
    type_personne: Literal["eleve", "adulte"]
    categorie: Literal["tous", "nouveaux", "anciens"]
    annee_cible_id: int
    annee_source_id: int | None = None
    enregistrer_prevus: bool = False


class ExportPmbReponse(BaseModel):
    site_nom: str
    type_personne: str
    categorie: str
    nb_lignes: int
    nom_fichier: str
    contenu_base64: str
    nb_prevus_enregistres: int = 0


@router.post("/pmb", response_model=ExportPmbReponse)
def exporter_pmb(payload: ExportPmbPayload, session: Session = Depends(db_session)) -> ExportPmbReponse:
    try:
        contenu, rapport = generer_csv_pmb(
            session=session, site_id=payload.site_id, type_personne=payload.type_personne,
            categorie=payload.categorie, annee_cible_id=payload.annee_cible_id,
            annee_source_id=payload.annee_source_id,
        )
        nb_prevus = _enregistrer_si_demande(
            session,
            demande=payload.enregistrer_prevus,
            famille="pmb",
            site_id=payload.site_id,
            type_personne=payload.type_personne,
            categorie=payload.categorie,
            annee_cible_id=payload.annee_cible_id,
            annee_source_id=payload.annee_source_id,
        )
    except ValueError as e:
        raise HTTPException(400, str(e))
    return ExportPmbReponse(
        site_nom=rapport.site_nom, type_personne=rapport.type_personne,
        categorie=rapport.categorie, nb_lignes=rapport.nb_lignes,
        nom_fichier=rapport.nom_fichier_suggere,
        contenu_base64=base64.b64encode(contenu).decode("ascii"),
        nb_prevus_enregistres=nb_prevus,
    )


# ---------------------------------------------------------------------------
# Lot 11b — JPM / SmartAir (différentiel a/b/m)
# ---------------------------------------------------------------------------


class ExportJpmPayload(BaseModel):
    site_id: int
    annee_cible_id: int
    annee_source_id: int
    enregistrer_prevus: bool = False


class ExportJpmReponse(BaseModel):
    site_nom: str
    nb_ajouts: int
    nb_suppressions: int
    nb_modifications: int
    nb_total: int
    nom_fichier: str
    contenu_base64: str
    nb_prevus_enregistres: int = 0


@router.post("/jpm", response_model=ExportJpmReponse)
def exporter_jpm(payload: ExportJpmPayload, session: Session = Depends(db_session)) -> ExportJpmReponse:
    try:
        contenu, rapport = generer_csv_jpm(
            session=session, site_id=payload.site_id,
            annee_cible_id=payload.annee_cible_id,
            annee_source_id=payload.annee_source_id,
        )
        # JPM ne concerne que les élèves ; les « ajouts » (Op=a) sont les nouveaux.
        nb_prevus = _enregistrer_si_demande(
            session,
            demande=payload.enregistrer_prevus,
            famille="jpm",
            site_id=payload.site_id,
            type_personne="eleve",
            categorie="nouveaux",
            annee_cible_id=payload.annee_cible_id,
            annee_source_id=payload.annee_source_id,
        )
    except ValueError as e:
        raise HTTPException(400, str(e))
    return ExportJpmReponse(
        site_nom=rapport.site_nom,
        nb_ajouts=rapport.nb_ajouts, nb_suppressions=rapport.nb_suppressions,
        nb_modifications=rapport.nb_modifications, nb_total=rapport.nb_total,
        nom_fichier=rapport.nom_fichier_suggere,
        contenu_base64=base64.b64encode(contenu).decode("ascii"),
        nb_prevus_enregistres=nb_prevus,
    )


# ---------------------------------------------------------------------------
# Lot 11c — CardStudio (XLSX badges)
# ---------------------------------------------------------------------------


class ExportCardStudioPayload(BaseModel):
    site_id: int
    categorie: Literal["tous", "nouveaux"]
    annee_cible_id: int
    annee_source_id: int | None = None
    enregistrer_prevus: bool = False


class ExportCardStudioReponse(BaseModel):
    site_nom: str
    nb_lignes: int
    nom_fichier: str
    contenu_base64: str
    nb_prevus_enregistres: int = 0


@router.post("/cardstudio", response_model=ExportCardStudioReponse)
def exporter_cardstudio(payload: ExportCardStudioPayload, session: Session = Depends(db_session)) -> ExportCardStudioReponse:
    try:
        contenu, rapport = generer_xlsx_cardstudio(
            session=session, site_id=payload.site_id,
            categorie=payload.categorie, annee_cible_id=payload.annee_cible_id,
            annee_source_id=payload.annee_source_id,
        )
        nb_prevus = _enregistrer_si_demande(
            session,
            demande=payload.enregistrer_prevus,
            famille="cardstudio",
            site_id=payload.site_id,
            type_personne="eleve",
            categorie=payload.categorie,
            annee_cible_id=payload.annee_cible_id,
            annee_source_id=payload.annee_source_id,
        )
    except ValueError as e:
        raise HTTPException(400, str(e))
    return ExportCardStudioReponse(
        site_nom=rapport.site_nom, nb_lignes=rapport.nb_lignes,
        nom_fichier=rapport.nom_fichier_suggere,
        contenu_base64=base64.b64encode(contenu).decode("ascii"),
        nb_prevus_enregistres=nb_prevus,
    )
