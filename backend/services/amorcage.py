"""Amorçage du référentiel — chargement des Personnes depuis les comptes existants.

Avant la première ingestion Charlemagne, on charge le référentiel depuis les
**comptes déjà en place côté KoXo** (et plus tard Google/PMB). Ainsi les
`Personne` sont créées avec leurs **vrais logins figés**, ceux que
l'utilisateur connaît déjà. Aucune régénération : le login KoXo existant
est l'autorité (§7.1 du prompt).

**Pas de mot de passe stocké.** Le fichier KoXo en contient un, on ne le
lit même pas côté persistance (§7.1 : « le mot de passe n'est jamais
persisté »).

## Rapprochement

Clé pivot : `(type, id_charlemagne)` déduit du badge :
- Élève : `id = (badge - 10000) / 10`
- Adulte : `id = badge`

## Idempotence

Un second amorçage du même fichier ne recrée rien :
- Personne inexistante → création (login pris du fichier)
- Personne existante avec même login → rien
- Personne existante avec login différent → **on garde celui en base**
  (login figé à vie) + log warning (le fichier KoXo diverge)
"""
from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

from sqlalchemy.orm import Session

from backend.models import Personne, Site
from backend.services.parser_koxo import deduire_id_charlemagne, lire_csv_koxo

# ---------------------------------------------------------------------------
# Rapport typé
# ---------------------------------------------------------------------------


@dataclass
class PersonneAmorcee:
    ligne_source: int
    num_badge: int
    id_charlemagne: int
    nom: str
    prenom: str
    login: str
    action: str  # "creee" | "deja_presente_identique" | "conflit_login"


@dataclass
class LigneRejetee:
    ligne_source: int
    raison: str
    valeurs: dict = field(default_factory=dict)


@dataclass
class RapportAmorcage:
    type_personne: str  # "eleve" | "adulte"
    site: str
    mode: str  # "simulation" | "reel"

    nb_lignes_lues: int = 0
    nb_creations: int = 0
    nb_deja_presentes: int = 0
    nb_conflits_login: int = 0
    nb_rejets: int = 0

    personnes: list[PersonneAmorcee] = field(default_factory=list)
    rejets: list[LigneRejetee] = field(default_factory=list)
    conflits: list[dict] = field(default_factory=list)
    """Détail des cas où le login du fichier diverge de celui en base."""

    contient_mots_de_passe: bool = False
    """True si le fichier avait une colonne « Mot de passe » avec des valeurs.
    Signalé pour rappeler que ces valeurs ne sont PAS conservées."""

    erreurs: list[str] = field(default_factory=list)
    est_bloque: bool = False


# ---------------------------------------------------------------------------
# Point d'entrée
# ---------------------------------------------------------------------------


def amorcer_depuis_koxo(
    session: Session,
    chemin_fichier: Path,
    *,
    site_id: int,
    type_personne: str,
    mode: str = "simulation",
) -> RapportAmorcage:
    """Charge un export KoXo dans le référentiel.

    Args:
        session: SQLAlchemy session (commit uniquement en mode réel).
        chemin_fichier: fichier .csv de l'export KoXo.
        site_id: ID du Site auquel rattacher les Personnes créées.
        type_personne: `eleve` ou `adulte`. Détermine la formule badge → ID.
        mode: `simulation` ou `reel`.

    Returns:
        Un RapportAmorcage typé.
    """
    if mode not in ("simulation", "reel"):
        raise ValueError(f"mode invalide : {mode!r}")
    if type_personne not in ("eleve", "adulte"):
        raise ValueError(f"type_personne invalide : {type_personne!r}")

    site = session.query(Site).filter_by(id=site_id).one_or_none()
    if site is None:
        raise ValueError(f"Site introuvable : {site_id}")

    rapport = RapportAmorcage(type_personne=type_personne, site=site.nom, mode=mode)

    try:
        df = lire_csv_koxo(chemin_fichier)
    except Exception as e:
        rapport.erreurs.append(f"Lecture impossible : {e}")
        rapport.est_bloque = True
        return rapport

    rapport.nb_lignes_lues = int(len(df))

    # Détecte la présence d'une colonne mot de passe (avertissement UI)
    rapport.contient_mots_de_passe = bool(
        "_mot_de_passe_ignore" in df.columns
        and df["_mot_de_passe_ignore"].notna().any()
    )

    # Vérifie les colonnes essentielles
    for col in ("num_badge", "nom", "prenom", "login"):
        if col not in df.columns:
            rapport.erreurs.append(f"Colonne obligatoire manquante : {col}")
    if rapport.erreurs:
        rapport.est_bloque = True
        return rapport

    for i, ligne in enumerate(df.to_dict(orient="records"), start=2):
        _traiter_ligne(session, ligne, i, site_id, type_personne, rapport)

    if mode == "reel" and not rapport.est_bloque:
        session.commit()
    else:
        session.rollback()

    return rapport


# ---------------------------------------------------------------------------
# Traitement ligne par ligne
# ---------------------------------------------------------------------------


def _traiter_ligne(
    session: Session,
    ligne: dict,
    ligne_num: int,
    site_id: int,
    type_personne: str,
    rapport: RapportAmorcage,
) -> None:
    num_badge = ligne.get("num_badge")
    nom = ligne.get("nom")
    prenom = ligne.get("prenom")
    login = ligne.get("login")

    if num_badge is None:
        rapport.rejets.append(LigneRejetee(ligne_num, "num_badge manquant", ligne))
        rapport.nb_rejets += 1
        return
    if not nom or not prenom:
        rapport.rejets.append(LigneRejetee(ligne_num, "nom/prénom manquant", ligne))
        rapport.nb_rejets += 1
        return
    if not login:
        rapport.rejets.append(LigneRejetee(ligne_num, "login manquant", ligne))
        rapport.nb_rejets += 1
        return

    try:
        num_badge_int = int(num_badge)
    except (TypeError, ValueError):
        rapport.rejets.append(LigneRejetee(ligne_num, "num_badge non entier", ligne))
        rapport.nb_rejets += 1
        return

    id_ch = deduire_id_charlemagne(num_badge_int, type_personne)
    if id_ch is None:
        rapport.rejets.append(
            LigneRejetee(
                ligne_num,
                f"badge {num_badge_int} ne dérive pas un id_charlemagne valide pour {type_personne}",
                ligne,
            )
        )
        rapport.nb_rejets += 1
        return

    # Vérifie si une Personne existe déjà avec cette clé pivot
    existante = (
        session.query(Personne)
        .filter_by(type=type_personne, id_charlemagne=id_ch)
        .one_or_none()
    )

    if existante is not None:
        if existante.login == login:
            rapport.nb_deja_presentes += 1
            rapport.personnes.append(
                PersonneAmorcee(
                    ligne_source=ligne_num,
                    num_badge=num_badge_int,
                    id_charlemagne=id_ch,
                    nom=nom,
                    prenom=prenom,
                    login=login,
                    action="deja_presente_identique",
                )
            )
        else:
            # Le login figé en base l'emporte — on ne l'écrase JAMAIS
            rapport.nb_conflits_login += 1
            rapport.conflits.append(
                {
                    "ligne_source": ligne_num,
                    "cle_pivot": existante.cle_pivot,
                    "nom": existante.nom,
                    "prenom": existante.prenom,
                    "login_en_base": existante.login,
                    "login_dans_fichier": login,
                }
            )
            rapport.personnes.append(
                PersonneAmorcee(
                    ligne_source=ligne_num,
                    num_badge=num_badge_int,
                    id_charlemagne=id_ch,
                    nom=nom,
                    prenom=prenom,
                    login=existante.login,  # garde celui en base
                    action="conflit_login",
                )
            )
        return

    # Vérifie qu'aucune autre Personne ne porte déjà ce login (unicité globale)
    if session.query(Personne).filter_by(login=login).one_or_none() is not None:
        rapport.rejets.append(
            LigneRejetee(
                ligne_num,
                f"login {login!r} déjà pris par une autre personne (unicité globale)",
                ligne,
            )
        )
        rapport.nb_rejets += 1
        return

    # Création
    personne = Personne(
        type=type_personne,
        id_charlemagne=id_ch,
        badge=num_badge_int,
        login=login,
        nom=str(nom),
        prenom=str(prenom),
        site_id=site_id,
    )
    session.add(personne)
    session.flush()
    rapport.nb_creations += 1
    rapport.personnes.append(
        PersonneAmorcee(
            ligne_source=ligne_num,
            num_badge=num_badge_int,
            id_charlemagne=id_ch,
            nom=str(nom),
            prenom=str(prenom),
            login=login,
            action="creee",
        )
    )
