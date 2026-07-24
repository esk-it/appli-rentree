"""Ingestion unifiée des exports Charlemagne (élèves + adultes).

Un seul chemin, paramétré par le `type` de population. À chaque ligne :

1. Lit et normalise les champs.
2. Détecte les homonymes intra-export.
3. Résout le site via `TableCorrespondance` (élèves uniquement).
4. Refuse si des classes sont absentes de la table (§8 du prompt).
5. Rapproche par clé pivot `(type, id_charlemagne)`.
6. Crée ou met à jour la `Personne` (login figé si déjà présent).
7. Crée un `Snapshot` si l'état constaté diffère du dernier snapshot.

Deux modes :

- **simulation** : lit, évalue, produit le rapport, ne commit rien.
- **reel** : idem + commit.

Le rapport est le même dans les deux cas — la seule différence est la
persistance. C'est aussi le socle du garde-fou "simulation par défaut"
qu'exige le prompt §8.
"""
from __future__ import annotations

import hashlib
from dataclasses import dataclass, field
from datetime import date, datetime
from pathlib import Path
from typing import Any

import pandas as pd
from sqlalchemy.orm import Session

from backend.models import (
    AnneeScolaire,
    Personne,
    Site,
    Snapshot,
    TableCorrespondance,
)
from backend.services.arbitrage import (
    cle_collision_login,
    cle_homonymie_ingestion,
    creer_ou_reprendre as creer_arbitrage,
)
from backend.services.parser_charlemagne import lire_htm, lire_xlsx
from backend.services.regles_metier import (
    calculer_login_base,
    detecter_homonymes_ingestion,
    proposer_suffixe,
)

# ---------------------------------------------------------------------------
# Vocabulaire
# ---------------------------------------------------------------------------

TYPES_PERSONNE = ("eleve", "adulte")


# ---------------------------------------------------------------------------
# Résumés retournés au caller
# ---------------------------------------------------------------------------


@dataclass
class HomonymeDansExport:
    """Un groupe de lignes du même export qui partagent (nom, prénom)."""

    nom_normalise: str
    prenom_normalise: str
    ids_charlemagne: list[int]


@dataclass
class CollisionLoginIngestion:
    """Un login déjà pris a nécessité un suffixe pour une nouvelle personne."""

    id_charlemagne: int
    nom: str
    prenom: str
    login_base: str
    login_attribue: str
    """login effectivement attribué à la nouvelle personne (avec suffixe)."""
    personnes_deja_presentes: list[dict]
    """Personnes qui portent déjà des variantes du login (pour arbitrage §5)."""


@dataclass
class RapportIngestion:
    type_personne: str
    annee_libelle: str
    mode: str  # "simulation" | "reel"

    nb_lignes_lues: int = 0
    nb_lignes_ingerees: int = 0
    nb_lignes_ignorees: int = 0
    """Lignes sans nom+prénom ou sans id_charlemagne exploitable."""

    nb_personnes_creees: int = 0
    nb_personnes_mises_a_jour: int = 0
    nb_snapshots_crees: int = 0
    nb_snapshots_identiques: int = 0
    """Personnes dont l'état n'a pas bougé depuis le dernier snapshot."""

    classes_inconnues: list[str] = field(default_factory=list)
    """Codes classes présents dans l'export mais absents de TableCorrespondance
    (élèves uniquement)."""

    homonymes_intra_export: list[HomonymeDansExport] = field(default_factory=list)
    collisions_login: list[CollisionLoginIngestion] = field(default_factory=list)
    erreurs: list[str] = field(default_factory=list)

    est_bloquee: bool = False
    """True si l'ingestion s'est arrêtée avant commit à cause de classes
    inconnues (mode `reel`). En simulation, `est_bloquee` reste False mais
    `classes_inconnues` est renseignée."""


# ---------------------------------------------------------------------------
# Détection du type d'export
# ---------------------------------------------------------------------------


def detecter_type_export(df: pd.DataFrame) -> str | None:
    """Détermine si l'export ressemble à un fichier élèves ou adultes.

    Heuristique : la présence des colonnes spécifiques adultes (poste_occupe,
    matieres, civilite, adresse_1) l'emporte. Sinon, code_classe/code_regime
    → élève.
    """
    cols = set(df.columns)
    indices_adultes = {
        "poste_occupe",
        "matieres",
        "civilite",
        "adresse_1",
        "email_personnel",
        "date_naissance",
    }
    if cols & indices_adultes:
        return "adulte"
    indices_eleves = {"code_classe", "code_regime", "num_badge"}
    if cols & indices_eleves:
        return "eleve"
    return None


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _lire_dataframe(chemin: Path) -> pd.DataFrame:
    suffix = chemin.suffix.lower()
    if suffix in (".htm", ".html"):
        return lire_htm(chemin)
    if suffix in (".xlsx", ".xls"):
        return lire_xlsx(chemin)
    raise ValueError(f"Format non supporté : {suffix}")


def _s(v: Any) -> str | None:
    """Convertit en str strippée, ou None si vide/NaN."""
    if v is None or (isinstance(v, float) and pd.isna(v)) or pd.isna(v):
        return None
    s = str(v).strip()
    return s or None


def _date(v: Any) -> date | None:
    if v is None or pd.isna(v):
        return None
    if isinstance(v, date):
        return v
    if hasattr(v, "date"):
        return v.date()
    try:
        return pd.to_datetime(v).date()
    except Exception:
        return None


def _int(v: Any) -> int | None:
    if v is None or pd.isna(v):
        return None
    try:
        return int(float(v))
    except (TypeError, ValueError):
        return None


def _hash_etat_snapshot(**champs: Any) -> str:
    """Empreinte stable des champs constatés d'un snapshot — sert l'idempotence."""
    parts = []
    for k in sorted(champs):
        v = champs[k]
        if isinstance(v, date):
            v = v.isoformat()
        parts.append(f"{k}={v!r}")
    return hashlib.sha256("|".join(parts).encode("utf-8")).hexdigest()[:32]


def _etat_snapshot_actuel(personne: Personne, annee_id: int, session: Session) -> str | None:
    """Hash du dernier snapshot connu pour (personne, année). None si aucun."""
    dernier = (
        session.query(Snapshot)
        .filter_by(personne_id=personne.id, annee_scolaire_id=annee_id)
        .order_by(Snapshot.date_ingestion.desc())
        .first()
    )
    if dernier is None:
        return None
    return _hash_etat_snapshot(
        nom=dernier.nom,
        prenom=dernier.prenom,
        nom_usage=dernier.nom_usage,
        classe=dernier.classe,
        niveau=dernier.niveau,
        code_etablissement=dernier.code_etablissement,
        regime=dernier.regime,
        chemin_photo=dernier.chemin_photo,
        date_entree=dernier.date_entree,
        poste_occupe=dernier.poste_occupe,
        matieres=dernier.matieres,
        classes_prof_principal=dernier.classes_prof_principal,
        classe_precedente=dernier.classe_precedente,
        classe_an_prochain=dernier.classe_an_prochain,
    )


# ---------------------------------------------------------------------------
# Point d'entrée
# ---------------------------------------------------------------------------


def ingerer_export(
    session: Session,
    chemin_fichier: Path,
    type_personne: str,
    libelle_annee: str,
    mode: str = "simulation",
) -> RapportIngestion:
    """Ingère un export Charlemagne dans le référentiel.

    Args:
        session: SQLAlchemy session.
        chemin_fichier: fichier HTM/XLSX à lire.
        type_personne: `eleve` ou `adulte`.
        libelle_annee: année scolaire cible, ex. `2025-2026`.
        mode: `simulation` (défaut, ne commit rien) ou `reel`.

    Returns:
        Un `RapportIngestion` détaillé, sans aucun secret persisté.
    """
    if type_personne not in TYPES_PERSONNE:
        raise ValueError(f"type_personne doit être {TYPES_PERSONNE}, reçu : {type_personne!r}")
    if mode not in ("simulation", "reel"):
        raise ValueError(f"mode doit être 'simulation' ou 'reel', reçu : {mode!r}")

    rapport = RapportIngestion(
        type_personne=type_personne, annee_libelle=libelle_annee, mode=mode
    )

    # 1. Parse
    try:
        df = _lire_dataframe(chemin_fichier)
    except Exception as e:
        rapport.erreurs.append(f"Lecture impossible : {e}")
        rapport.est_bloquee = True
        return rapport

    rapport.nb_lignes_lues = int(len(df))

    if type_personne == "eleve":
        return _ingerer_eleves(session, df, libelle_annee, mode, rapport)
    return _ingerer_adultes(session, df, libelle_annee, mode, rapport)


# ---------------------------------------------------------------------------
# Ingestion élèves
# ---------------------------------------------------------------------------


def _ingerer_eleves(
    session: Session,
    df: pd.DataFrame,
    libelle_annee: str,
    mode: str,
    rapport: RapportIngestion,
) -> RapportIngestion:
    # Initialisation du compteur (aussi appelé par la fonction publique mais
    # utile quand _ingerer_eleves est appelé directement — cf. tests unitaires).
    rapport.nb_lignes_lues = int(len(df))

    # a. Vérifie que les colonnes essentielles sont présentes
    for col in ("id_charlemagne", "nom", "prenom", "code_classe"):
        if col not in df.columns:
            rapport.erreurs.append(f"Colonne obligatoire manquante : {col}")
    if rapport.erreurs:
        rapport.est_bloquee = True
        return rapport

    # b. Détecte les homonymes intra-export (pré-check, ne bloque pas)
    lignes = df.to_dict(orient="records")
    for grp in detecter_homonymes_ingestion(lignes, "nom", "prenom"):
        rapport.homonymes_intra_export.append(
            HomonymeDansExport(
                nom_normalise=grp.cle_normalisee[0],
                prenom_normalise=grp.cle_normalisee[1],
                ids_charlemagne=[
                    _int(l.get("id_charlemagne"))
                    for l in grp.lignes
                    if _int(l.get("id_charlemagne")) is not None
                ],
            )
        )

    # c. Précharge le mapping classe → site depuis TableCorrespondance
    correspondances = session.query(TableCorrespondance).all()
    classe_vers_site: dict[str, int] = {
        c.classe_code_court: c.site_id for c in correspondances
    }
    classes_utilisees = {
        _s(l.get("code_classe")) for l in lignes if _s(l.get("code_classe"))
    }
    classes_inconnues = sorted(
        c for c in classes_utilisees if c and c not in classe_vers_site
    )
    rapport.classes_inconnues = classes_inconnues

    # d. En mode `reel`, blocage si classes inconnues (§8 du prompt).
    #    En simulation, on continue pour donner un rapport complet.
    if classes_inconnues and mode == "reel":
        rapport.est_bloquee = True
        return rapport

    # e. Récupère ou crée l'AnneeScolaire (même en simulation on la crée pour
    #    la relation dans Snapshot — annulée si simulation via rollback final).
    annee = _resoudre_annee(session, libelle_annee)

    # e-bis. Persiste les homonymies détectées comme Arbitrage en attente.
    _persister_arbitrages_homonymies(session, rapport, "eleve")

    # f. Boucle d'ingestion
    for ligne in lignes:
        id_ch = _int(ligne.get("id_charlemagne"))
        nom = _s(ligne.get("nom"))
        prenom = _s(ligne.get("prenom"))
        if id_ch is None or not nom or not prenom:
            rapport.nb_lignes_ignorees += 1
            continue

        # Résolution site — si classe inconnue, on saute la personne
        code_classe = _s(ligne.get("code_classe"))
        site_id = classe_vers_site.get(code_classe) if code_classe else None
        if code_classe and site_id is None:
            # Déjà comptabilisé dans classes_inconnues
            rapport.nb_lignes_ignorees += 1
            continue

        _traiter_ligne_eleve(
            session=session,
            ligne=ligne,
            id_ch=id_ch,
            nom=nom,
            prenom=prenom,
            code_classe=code_classe,
            site_id=site_id,
            annee=annee,
            rapport=rapport,
        )

    # g. Commit ou rollback selon le mode
    if mode == "reel" and not rapport.est_bloquee:
        session.commit()
    else:
        session.rollback()

    return rapport


def _traiter_ligne_eleve(
    *,
    session: Session,
    ligne: dict,
    id_ch: int,
    nom: str,
    prenom: str,
    code_classe: str | None,
    site_id: int | None,
    annee: AnneeScolaire,
    rapport: RapportIngestion,
) -> None:
    """Traite une ligne d'export élève : Personne + Snapshot."""
    personne = (
        session.query(Personne)
        .filter_by(type="eleve", id_charlemagne=id_ch)
        .one_or_none()
    )
    est_nouveau = personne is None

    if est_nouveau:
        # Attribution du login — via proposer_suffixe pour gérer collisions
        base = calculer_login_base(prenom, nom)
        proposition = proposer_suffixe(session, base)
        if proposition is None:
            rapport.erreurs.append(
                f"Impossible d'attribuer un login pour {nom} {prenom} (id={id_ch})"
            )
            return
        if proposition.a_conflit:
            collision = CollisionLoginIngestion(
                id_charlemagne=id_ch,
                nom=nom,
                prenom=prenom,
                login_base=base,
                login_attribue=proposition.login_propose,
                personnes_deja_presentes=[
                    {
                        "personne_id": c.personne_id,
                        "cle_pivot": c.cle_pivot,
                        "login": c.login,
                        "type": c.type,
                        "nom": c.nom,
                        "prenom": c.prenom,
                    }
                    for c in proposition.personnes_en_conflit
                ],
            )
            rapport.collisions_login.append(collision)
            _persister_arbitrage_collision(session, collision, "eleve", annee.libelle)
        personne = Personne(
            type="eleve",
            id_charlemagne=id_ch,
            badge=Personne.calculer_badge("eleve", id_ch),
            login=proposition.login_propose,
            nom=nom,
            prenom=prenom,
            classe=code_classe,
            site_id=site_id,
            regime=_s(ligne.get("code_regime")),
            code_etablissement=_s(ligne.get("code_etablissement")),
            date_entree=_date(ligne.get("date_entree")),
            chemin_photo_constate=_s(ligne.get("photo_chemin")),
        )
        session.add(personne)
        session.flush()  # pour obtenir personne.id
        rapport.nb_personnes_creees += 1
    else:
        # Mise à jour de l'état courant — le login est FIGÉ, on ne touche pas
        _maj_champs_courants_eleve(personne, ligne, code_classe, site_id)
        rapport.nb_personnes_mises_a_jour += 1

    # Snapshot : ne crée qu'un nouveau si l'état diffère
    _peut_etre_creer_snapshot(
        session=session,
        personne=personne,
        annee=annee,
        ligne=ligne,
        type_personne="eleve",
        rapport=rapport,
    )

    rapport.nb_lignes_ingerees += 1


def _maj_champs_courants_eleve(
    personne: Personne, ligne: dict, code_classe: str | None, site_id: int | None
) -> None:
    """Met à jour uniquement les champs d'état courant (login figé)."""
    personne.nom = _s(ligne.get("nom")) or personne.nom
    personne.prenom = _s(ligne.get("prenom")) or personne.prenom
    personne.classe = code_classe
    personne.site_id = site_id
    personne.regime = _s(ligne.get("code_regime")) or personne.regime
    personne.code_etablissement = _s(ligne.get("code_etablissement")) or personne.code_etablissement
    de = _date(ligne.get("date_entree"))
    if de is not None:
        personne.date_entree = de
    photo = _s(ligne.get("photo_chemin"))
    if photo is not None:
        personne.chemin_photo_constate = photo


def _peut_etre_creer_snapshot(
    *,
    session: Session,
    personne: Personne,
    annee: AnneeScolaire,
    ligne: dict,
    type_personne: str,
    rapport: RapportIngestion,
) -> None:
    """Crée un Snapshot si les valeurs constatées diffèrent du dernier snapshot."""
    champs_snapshot = {
        "nom": _s(ligne.get("nom")) or personne.nom,
        "prenom": _s(ligne.get("prenom")) or personne.prenom,
        "nom_usage": _s(ligne.get("nom_usage")),
        "classe": personne.classe,
        "niveau": _s(ligne.get("code_niveau")),
        "code_etablissement": personne.code_etablissement,
        "regime": personne.regime,
        "chemin_photo": personne.chemin_photo_constate,
        "date_entree": personne.date_entree,
        "poste_occupe": personne.poste_occupe,
        "matieres": personne.matieres,
        "classes_prof_principal": personne.classes_prof_principal,
        "classe_precedente": _s(ligne.get("code_classe_precedente")),
        "classe_an_prochain": _s(ligne.get("code_classe_an_prochain")),
    }

    hash_courant = _hash_etat_snapshot(**champs_snapshot)
    hash_dernier = _etat_snapshot_actuel(personne, annee.id, session)

    if hash_dernier == hash_courant:
        rapport.nb_snapshots_identiques += 1
        return

    snap = Snapshot(
        personne_id=personne.id,
        annee_scolaire_id=annee.id,
        **champs_snapshot,
    )
    session.add(snap)
    session.flush()
    rapport.nb_snapshots_crees += 1


# ---------------------------------------------------------------------------
# Ingestion adultes
# ---------------------------------------------------------------------------


def _ingerer_adultes(
    session: Session,
    df: pd.DataFrame,
    libelle_annee: str,
    mode: str,
    rapport: RapportIngestion,
) -> RapportIngestion:
    rapport.nb_lignes_lues = int(len(df))
    for col in ("id_charlemagne", "nom", "prenom"):
        if col not in df.columns:
            rapport.erreurs.append(f"Colonne obligatoire manquante : {col}")
    if rapport.erreurs:
        rapport.est_bloquee = True
        return rapport

    lignes = df.to_dict(orient="records")

    # Homonymes intra-export
    for grp in detecter_homonymes_ingestion(lignes, "nom", "prenom"):
        rapport.homonymes_intra_export.append(
            HomonymeDansExport(
                nom_normalise=grp.cle_normalisee[0],
                prenom_normalise=grp.cle_normalisee[1],
                ids_charlemagne=[
                    _int(l.get("id_charlemagne"))
                    for l in grp.lignes
                    if _int(l.get("id_charlemagne")) is not None
                ],
            )
        )

    annee = _resoudre_annee(session, libelle_annee)

    _persister_arbitrages_homonymies(session, rapport, "adulte")

    for ligne in lignes:
        id_ch = _int(ligne.get("id_charlemagne"))
        nom = _s(ligne.get("nom"))
        prenom = _s(ligne.get("prenom"))
        if id_ch is None or not nom or not prenom:
            rapport.nb_lignes_ignorees += 1
            continue
        _traiter_ligne_adulte(
            session=session,
            ligne=ligne,
            id_ch=id_ch,
            nom=nom,
            prenom=prenom,
            annee=annee,
            rapport=rapport,
        )

    if mode == "reel":
        session.commit()
    else:
        session.rollback()
    return rapport


def _traiter_ligne_adulte(
    *,
    session: Session,
    ligne: dict,
    id_ch: int,
    nom: str,
    prenom: str,
    annee: AnneeScolaire,
    rapport: RapportIngestion,
) -> None:
    personne = (
        session.query(Personne)
        .filter_by(type="adulte", id_charlemagne=id_ch)
        .one_or_none()
    )
    est_nouveau = personne is None

    if est_nouveau:
        base = calculer_login_base(prenom, nom)
        proposition = proposer_suffixe(session, base)
        if proposition is None:
            rapport.erreurs.append(
                f"Impossible d'attribuer un login pour {nom} {prenom} (id={id_ch})"
            )
            return
        if proposition.a_conflit:
            collision = CollisionLoginIngestion(
                id_charlemagne=id_ch,
                nom=nom,
                prenom=prenom,
                login_base=base,
                login_attribue=proposition.login_propose,
                personnes_deja_presentes=[
                    {
                        "personne_id": c.personne_id,
                        "cle_pivot": c.cle_pivot,
                        "login": c.login,
                        "type": c.type,
                        "nom": c.nom,
                        "prenom": c.prenom,
                    }
                    for c in proposition.personnes_en_conflit
                ],
            )
            rapport.collisions_login.append(collision)
            _persister_arbitrage_collision(session, collision, "adulte", annee.libelle)
        personne = Personne(
            type="adulte",
            id_charlemagne=id_ch,
            badge=Personne.calculer_badge("adulte", id_ch),
            login=proposition.login_propose,
            nom=nom,
            prenom=prenom,
            civilite=_s(ligne.get("civilite")),
            poste_occupe=_s(ligne.get("poste_occupe")),
            matieres=_s(ligne.get("matieres")),
            classes_prof_principal=_s(ligne.get("classes_prof_principal")),
            email_professionnel=_s(ligne.get("email_professionnel")),
            email_personnel=_s(ligne.get("email_personnel")),
        )
        session.add(personne)
        session.flush()
        rapport.nb_personnes_creees += 1
    else:
        _maj_champs_courants_adulte(personne, ligne)
        rapport.nb_personnes_mises_a_jour += 1

    _peut_etre_creer_snapshot(
        session=session,
        personne=personne,
        annee=annee,
        ligne=ligne,
        type_personne="adulte",
        rapport=rapport,
    )
    rapport.nb_lignes_ingerees += 1


def _maj_champs_courants_adulte(personne: Personne, ligne: dict) -> None:
    personne.nom = _s(ligne.get("nom")) or personne.nom
    personne.prenom = _s(ligne.get("prenom")) or personne.prenom
    personne.civilite = _s(ligne.get("civilite")) or personne.civilite
    personne.poste_occupe = _s(ligne.get("poste_occupe")) or personne.poste_occupe
    personne.matieres = _s(ligne.get("matieres")) or personne.matieres
    personne.classes_prof_principal = (
        _s(ligne.get("classes_prof_principal")) or personne.classes_prof_principal
    )
    ep = _s(ligne.get("email_professionnel"))
    if ep is not None:
        personne.email_professionnel = ep
    ei = _s(ligne.get("email_personnel"))
    if ei is not None:
        personne.email_personnel = ei


# ---------------------------------------------------------------------------
# Utilitaires
# ---------------------------------------------------------------------------


def _resoudre_annee(session: Session, libelle: str) -> AnneeScolaire:
    """Récupère ou crée l'AnneeScolaire par libellé."""
    annee = session.query(AnneeScolaire).filter_by(libelle=libelle).one_or_none()
    if annee is None:
        annee = AnneeScolaire(libelle=libelle, est_active=True)
        session.add(annee)
        session.flush()
    return annee


def _persister_arbitrages_homonymies(
    session: Session,
    rapport: RapportIngestion,
    type_personne: str,
) -> None:
    """Crée un Arbitrage en attente par groupe d'homonymes intra-export.

    Idempotent via cle_cas — un même trio (nom, prénom, IDs) ne créera
    qu'un seul arbitrage même si l'ingestion est rejouée.
    """
    prefixe = "E" if type_personne == "eleve" else "A"
    for h in rapport.homonymes_intra_export:
        cles = [f"{prefixe}{i}" for i in h.ids_charlemagne]
        creer_arbitrage(
            session,
            type_cas="homonymie_ingestion",
            cle_cas=cle_homonymie_ingestion(h.nom_normalise, h.prenom_normalise, cles),
            contexte={
                "type_personne": type_personne,
                "nom_normalise": h.nom_normalise,
                "prenom_normalise": h.prenom_normalise,
                "ids_charlemagne": h.ids_charlemagne,
                "annee_libelle": rapport.annee_libelle,
            },
        )


def _persister_arbitrage_collision(
    session: Session,
    collision: CollisionLoginIngestion,
    type_personne: str,
    annee_libelle: str,
) -> None:
    """Crée un Arbitrage pour une collision de login détectée à l'ingestion."""
    prefixe = "E" if type_personne == "eleve" else "A"
    cle_pivot = f"{prefixe}{collision.id_charlemagne}"
    creer_arbitrage(
        session,
        type_cas="collision_login",
        cle_cas=cle_collision_login(collision.login_base, cle_pivot),
        contexte={
            "type_personne": type_personne,
            "id_charlemagne": collision.id_charlemagne,
            "nom": collision.nom,
            "prenom": collision.prenom,
            "login_base": collision.login_base,
            "login_attribue": collision.login_attribue,
            "personnes_deja_presentes": collision.personnes_deja_presentes,
            "annee_libelle": annee_libelle,
        },
    )
