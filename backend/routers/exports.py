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
from backend.services.google_api import ClientGoogle, charger_config
from backend.services.journal import journaliser
from backend.services.repartition_pmb import (
    RepartitionImpossible,
    repartir_export_pmb,
)

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


# ---------------------------------------------------------------------------
# Comptes que la synchronisation désactiverait
# ---------------------------------------------------------------------------


class CompteMenaceOut(BaseModel):
    badge: int
    login: str
    nom: str
    prenom: str
    groupe_secondaire: str | None
    email: str | None
    conserver: bool
    motif: str
    personne_id: int | None = None


class DesactivationsOut(BaseModel):
    site_nom: str
    base: str
    type_personne: str
    nb_dans_la_base: int
    nb_dans_l_export: int
    nb_menaces: int
    nb_conserves: int
    comptes: list[CompteMenaceOut]
    avertissements: list[str]


@router.get("/koxo/desactivations", response_model=DesactivationsOut)
def desactivations_koxo(
    site_id: int,
    type_personne: Literal["eleve", "adulte"],
    annee_cible_id: int,
    base_koxo: str | None = None,
    session: Session = Depends(db_session),
) -> DesactivationsOut:
    """Nomme les comptes que la synchronisation désactiverait. Lecture seule.

    KoXo annonce un nombre au moment de lancer l'opération — « Désactiver
    7 » — sans dire lesquels. Les voir avant, avec la raison de leur
    absence, est ce qui permet d'en garder un.
    """
    from backend.services.comptes_a_desactiver import comptes_a_desactiver

    try:
        r = comptes_a_desactiver(
            session,
            site_id=site_id,
            type_personne=type_personne,
            annee_cible_id=annee_cible_id,
            base_koxo=base_koxo,
        )
    except ValueError as e:
        raise HTTPException(400, str(e)) from None

    return DesactivationsOut(
        site_nom=r.site_nom,
        base=r.base,
        type_personne=r.type_personne,
        nb_dans_la_base=r.nb_dans_la_base,
        nb_dans_l_export=r.nb_dans_l_export,
        nb_menaces=r.nb_menaces,
        nb_conserves=r.nb_conserves,
        comptes=[CompteMenaceOut(**vars(c)) for c in r.comptes],
        avertissements=r.avertissements,
    )


class ConservationPayload(BaseModel):
    badges: list[int]
    base: str
    """La base KoXo concernée. La décision vaut par serveur : un professeur
    peut mériter d'être gardé au lycée et pas au collège."""
    conserver: bool


class ConservationOut(BaseModel):
    nb_touches: int
    conserver: bool


@router.post("/koxo/conserver", response_model=ConservationOut)
def conserver_comptes(
    payload: ConservationPayload, session: Session = Depends(db_session)
) -> ConservationOut:
    """Garde (ou relâche) des comptes que l'export ne reconduirait pas."""
    from backend.services.comptes_a_desactiver import definir_conservation

    n = definir_conservation(
        session,
        badges=payload.badges,
        base=payload.base,
        conserver=payload.conserver,
    )
    session.commit()
    return ConservationOut(nb_touches=n, conserver=payload.conserver)


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


class RepartitionPmbPayload(BaseModel):
    """L'export PMB de Charlemagne, à couper en un fichier par instance.

    Le contenu passe en base64 dans le JSON plutôt qu'en multipart : c'est
    le contournement déjà retenu pour l'ingestion, le webview Tauri
    rejetant silencieusement certains envois multipart.
    """

    fichier_base64: str
    annee_libelle: str


class PaquetPmbOut(BaseModel):
    site_nom: str
    nom_fichier: str
    nb_eleves: int
    classes: list[str]
    contenu_base64: str


class LignePmbOut(BaseModel):
    badge: str
    nom: str
    prenom: str
    code_classe: str
    motif: str


class RepartitionPmbReponse(BaseModel):
    nb_lignes_lues: int
    nb_reparties: int
    paquets: list[PaquetPmbOut]
    ecartees: list[LignePmbOut]
    inconnus_du_referentiel: list[LignePmbOut]


@router.post("/pmb", response_model=RepartitionPmbReponse)
def repartir_pmb(
    payload: RepartitionPmbPayload, session: Session = Depends(db_session)
) -> RepartitionPmbReponse:
    """Coupe l'export PMB de Charlemagne en un fichier par instance PMB.

    Le programme ne fabrique pas ce fichier : sept de ses treize colonnes
    (adresse, code postal, ville, téléphone, année de naissance, sexe)
    n'existent ni dans le référentiel ni dans l'export qu'il ingère. Il
    apporte la seule chose que Charlemagne ignore — quel code classe
    appartient à quel établissement.
    """
    try:
        brut = base64.b64decode(payload.fichier_base64)
    except Exception as e:
        raise HTTPException(400, f"Base64 invalide : {e}") from e

    try:
        r = repartir_export_pmb(session, brut, annee_libelle=payload.annee_libelle)
    except RepartitionImpossible as e:
        raise HTTPException(400, str(e)) from None

    # Le journal passe ici par `journaliser` et non par `_journaliser_export` :
    # cette répartition n'a ni site ni année choisis dans l'écran — elle les
    # découvre dans le fichier.
    try:
        journaliser(
            session,
            type_operation="export",
            cible="pmb",
            annee_libelle=payload.annee_libelle,
            parametres={"sites": [p.site_nom for p in r.paquets]},
            resultat={
                "nb_lignes_lues": r.nb_lignes_lues,
                "nb_reparties": r.nb_reparties,
                "nb_ecartees": len(r.ecartees),
                "nb_inconnus": len(r.inconnus_du_referentiel),
                "fichiers": {p.site_nom: p.nb_eleves for p in r.paquets},
            },
        )
        session.commit()
    except Exception:  # pragma: no cover — le journal ne doit rien casser
        session.rollback()

    return RepartitionPmbReponse(
        nb_lignes_lues=r.nb_lignes_lues,
        nb_reparties=r.nb_reparties,
        paquets=[
            PaquetPmbOut(
                site_nom=p.site_nom, nom_fichier=p.nom_fichier,
                nb_eleves=p.nb_eleves, classes=p.classes,
                contenu_base64=base64.b64encode(p.contenu_csv).decode("ascii"),
            )
            for p in r.paquets
        ],
        ecartees=[LignePmbOut(**vars(e)) for e in r.ecartees],
        inconnus_du_referentiel=[
            LignePmbOut(**vars(i)) for i in r.inconnus_du_referentiel
        ],
    )


# ---------------------------------------------------------------------------
# Retour vers Charlemagne — les adresses qu'il ne connaît pas
# ---------------------------------------------------------------------------


class AdressesCharlemagnePayload(BaseModel):
    fichier_base64: str
    annee_libelle: str = ""


class ConstatAdresseOut(BaseModel):
    badge: str
    nom: str
    prenom: str
    classe: str
    adresse_charlemagne: str
    adresse_referentiel: str
    origine: str
    detail: str


class AdressesCharlemagneReponse(BaseModel):
    nb_lignes_lues: int
    nb_deja_bonnes: int
    nb_a_importer: int
    google_consulte: bool
    nom_fichier: str
    contenu_base64: str
    a_remplir: list[ConstatAdresseOut]
    a_corriger: list[ConstatAdresseOut]
    a_verifier: list[ConstatAdresseOut]
    alias_dans_charlemagne: list[ConstatAdresseOut]
    referentiel_a_tort: list[ConstatAdresseOut]
    adresse_personnelle: list[ConstatAdresseOut]
    conflit: list[ConstatAdresseOut]
    hors_referentiel: list[ConstatAdresseOut]
    sans_adresse_nulle_part: list[ConstatAdresseOut]


@router.post("/charlemagne-adresses", response_model=AdressesCharlemagneReponse)
def adresses_pour_charlemagne(
    payload: AdressesCharlemagnePayload, session: Session = Depends(db_session)
) -> AdressesCharlemagneReponse:
    """Dresse les adresses à renvoyer dans Charlemagne, vérifiées dans Google.

    Charlemagne est la source pour l'état civil et la classe, pas pour
    l'adresse : les comptes se créent ici, après son export de rentrée. Sa
    colonne reste donc vide pour toute la promotion entrante, et cette
    colonne se propage — c'est elle qu'il réexporte vers PMB et SoHappy.

    L'annuaire Google est lu **avant** de proposer quoi que ce soit : la
    plupart des adresses du référentiel sont calculées, et pousser un
    calcul dans Charlemagne propagerait l'erreur au lieu de la corriger.
    """
    from backend.services.adresses_charlemagne import confronter_adresses

    try:
        brut = base64.b64decode(payload.fichier_base64)
    except Exception as e:
        raise HTTPException(400, f"Base64 invalide : {e}") from e

    # Les deux étapes sont séparées : une configuration absente n'est pas une
    # panne de Google, et une faute de programmation ici ne doit pas se
    # déguiser en « Lecture Google impossible » — un message qui enverrait
    # chercher la panne du mauvais côté.
    try:
        client = ClientGoogle(charger_config(session))
    except ValueError as e:
        raise HTTPException(
            400,
            f"{e} — sans l'annuaire Google, aucune adresse ne peut être "
            "vérifiée, et le fichier ne serait qu'une liste de suppositions.",
        ) from None

    try:
        comptes = client.lister_utilisateurs()
    except Exception as e:
        raise HTTPException(
            502, f"Lecture Google impossible : {type(e).__name__}: {e}"
        ) from None

    try:
        r = confronter_adresses(
            session, brut, comptes_google=comptes,
            annee_libelle=payload.annee_libelle,
        )
    except RepartitionImpossible as e:
        raise HTTPException(400, str(e)) from None

    def _sortir(lignes) -> list[ConstatAdresseOut]:
        return [ConstatAdresseOut(**vars(c)) for c in lignes]

    try:
        journaliser(
            session,
            type_operation="export",
            cible="charlemagne",
            annee_libelle=payload.annee_libelle or None,
            parametres={"source": "colonne Email de Charlemagne"},
            resultat={
                "nb_lignes_lues": r.nb_lignes_lues,
                "nb_deja_bonnes": r.nb_deja_bonnes,
                "nb_a_importer": r.nb_a_importer,
                "nb_a_verifier": len(r.a_verifier),
                "nb_adresses_personnelles": len(r.adresse_personnelle),
            },
        )
        session.commit()
    except Exception:  # pragma: no cover — le journal ne doit rien casser
        session.rollback()

    return AdressesCharlemagneReponse(
        nb_lignes_lues=r.nb_lignes_lues,
        nb_deja_bonnes=r.nb_deja_bonnes,
        nb_a_importer=r.nb_a_importer,
        google_consulte=r.google_consulte,
        nom_fichier=r.nom_fichier,
        contenu_base64=base64.b64encode(r.csv_a_importer).decode("ascii"),
        a_remplir=_sortir(r.a_remplir),
        a_corriger=_sortir(r.a_corriger),
        a_verifier=_sortir(r.a_verifier),
        alias_dans_charlemagne=_sortir(r.alias_dans_charlemagne),
        referentiel_a_tort=_sortir(r.referentiel_a_tort),
        adresse_personnelle=_sortir(r.adresse_personnelle),
        conflit=_sortir(r.conflit),
        hors_referentiel=_sortir(r.hors_referentiel),
        sans_adresse_nulle_part=_sortir(r.sans_adresse_nulle_part),
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


# ---------------------------------------------------------------------------
# Les listes de rentrée, tirées d'un export KoXo
# ---------------------------------------------------------------------------


class ListesKoxoPayload(BaseModel):
    """L'export KoXo avec les mots de passe, et le site qu'il concerne."""

    koxo_base64: str
    site_id: int
    annee_cible_id: int
    annee_source_id: int | None = None


class ListesKoxoReponse(BaseModel):
    site_nom: str
    annee_libelle: str
    nb_tous: int
    nb_nouveaux: int
    sans_ligne_koxo: list[str]
    sans_mot_de_passe: list[str]
    koxo_hors_site: int
    nom_xlsx_tous: str
    xlsx_tous_base64: str
    nom_xlsx_nouveaux: str
    xlsx_nouveaux_base64: str
    nom_etiquettes_tous: str = ""
    etiquettes_tous_base64: str = ""
    nom_etiquettes: str
    etiquettes_base64: str


@router.post("/listes-koxo", response_model=ListesKoxoReponse)
def listes_koxo(
    payload: ListesKoxoPayload, session: Session = Depends(db_session)
) -> ListesKoxoReponse:
    """Trois documents de rentrée d'un seul export : liste, entrants, fiches.

    Le référentiel ne connaît pas les mots de passe — là où KoXo existe,
    c'est lui l'autorité. Or les trois en ont besoin. Ils se tirent donc de
    l'export KoXo pris **avec les mots de passe**.

    Ce que le programme ajoute à ce que KoXo sait déjà imprimer : distinguer
    les entrants, ce qui demande l'année précédente, et rendre un classeur
    qu'on trie plutôt qu'un tableau figé.
    """
    from pathlib import Path
    from tempfile import NamedTemporaryFile

    from backend.services.controle_koxo import lire_export_brut
    from backend.services.listes_depuis_koxo import (
        ListesImpossibles,
        listes_depuis_koxo,
    )

    try:
        contenu = base64.b64decode(payload.koxo_base64)
    except Exception as e:
        raise HTTPException(400, f"Base64 invalide : {e}") from e

    with NamedTemporaryFile(suffix=".csv", delete=False) as tmp:
        tmp.write(contenu)
        chemin = Path(tmp.name)
    try:
        lignes, colonnes, _sep, _enc, avait_mdp = lire_export_brut(
            chemin, garder_mots_de_passe=True
        )
    except Exception as e:
        raise HTTPException(400, f"Export KoXo illisible : {e}") from None
    finally:
        try:
            chemin.unlink()
        except OSError:
            pass

    if not avait_mdp:
        raise HTTPException(
            400,
            "Cet export ne porte pas de colonne « Mot de passe ». Reprends-le "
            "depuis KoXo en cochant l'inclusion des mots de passe — sans eux, "
            "ni les listes ni les étiquettes n'ont d'objet. Colonnes lues : "
            + (", ".join(colonnes) or "aucune"),
        )

    try:
        r = listes_depuis_koxo(
            session, lignes, site_id=payload.site_id,
            annee_cible_id=payload.annee_cible_id,
            annee_source_id=payload.annee_source_id,
        )
    except ListesImpossibles as e:
        raise HTTPException(400, str(e)) from None

    # Le journal ne porte ni mot de passe ni nom : seulement des nombres.
    try:
        journaliser(
            session,
            type_operation="export",
            cible="listes_koxo",
            annee_libelle=r.annee_libelle,
            parametres={"site": r.site_nom},
            resultat={
                "nb_tous": r.nb_tous, "nb_nouveaux": r.nb_nouveaux,
                "nb_sans_ligne_koxo": len(r.sans_ligne_koxo),
                "nb_sans_mot_de_passe": len(r.sans_mot_de_passe),
            },
        )
        session.commit()
    except Exception:  # pragma: no cover — le journal ne doit rien casser
        session.rollback()

    b64 = lambda o: base64.b64encode(o).decode("ascii")
    return ListesKoxoReponse(
        site_nom=r.site_nom, annee_libelle=r.annee_libelle,
        nb_tous=r.nb_tous, nb_nouveaux=r.nb_nouveaux,
        sans_ligne_koxo=r.sans_ligne_koxo,
        sans_mot_de_passe=r.sans_mot_de_passe,
        koxo_hors_site=r.koxo_hors_site,
        nom_xlsx_tous=r.nom_xlsx_tous, xlsx_tous_base64=b64(r.xlsx_tous),
        nom_xlsx_nouveaux=r.nom_xlsx_nouveaux,
        xlsx_nouveaux_base64=b64(r.xlsx_nouveaux),
        nom_etiquettes_tous=r.nom_etiquettes_tous,
        etiquettes_tous_base64=b64(r.etiquettes_tous),
        nom_etiquettes=r.nom_etiquettes,
        etiquettes_base64=b64(r.etiquettes_nouveaux),
    )
