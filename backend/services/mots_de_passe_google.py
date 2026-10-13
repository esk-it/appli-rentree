"""Le mot de passe KoXo, et ce que Google en a fait.

## Pourquoi

KoXo est **le** mot de passe : il ouvre la session sur le réseau
pédagogique, Charlemagne en garde une copie, et Google en a reçu une à la
création du compte (Johann, 13 octobre 2026). Rien ne tient Google à jour
ensuite : un mot de passe réinitialisé dans KoXo y reste l'ancien, et un
élève qui change le sien dans Google s'écarte de KoXo.

Google ne se vérifie pas : il ne rend aucun mot de passe, et aucun appel ne
permet d'en éprouver un. Deux gestes restent possibles, et Johann a demandé
les deux — l'écriture « seulement sur mon clic » :

- **lire** dans le journal d'audit qui a changé son mot de passe Google, et
  quand : l'élève lui-même, ou un administrateur ;
- **imposer** à Google le mot de passe de KoXo, pour les comptes qu'il a
  choisis, après confirmation.

## Ce que l'imposition refuse

- une adresse **calculée** : on n'écrit jamais sur un compte qu'on n'a pas
  constaté ;
- un élève sans relevé KoXo au coffre : la copie de Charlemagne n'est pas
  le mot de passe, seulement ce qu'on en a recopié ;
- un relevé KoXo contredit par une source lue après lui
  (`coffre.releve_contredit`) : KoXo a peut-être changé, il faut le relire.

Le journal dit qui et combien, jamais le mot de passe.
"""
from __future__ import annotations

from collections import Counter
from dataclasses import dataclass, field
from datetime import date

from sqlalchemy.orm import Session

from backend.models import AnneeScolaire, Personne, SecretConserve, Site, Snapshot


class ImpositionImpossible(Exception):
    """Le geste est refusé dans son ensemble, et le message dit pourquoi."""


@dataclass
class ChangementGoogle:
    """Le dernier changement de mot de passe Google d'un élève."""

    personne_id: int
    nom: str
    prenom: str
    classe: str | None
    site: str | None
    adresse: str
    quand: str
    par: str
    par_l_eleve: bool
    nb_changements: int = 1


@dataclass
class RapportChangements:
    annee: str
    depuis: str
    nb_evenements: int = 0
    changements: list[ChangementGoogle] = field(default_factory=list)
    nb_hors_eleves: int = 0
    """Changements sur des comptes qui ne sont pas des élèves inscrits —
    personnels, anciens : comptés, pas listés."""


@dataclass
class ResultatImposition:
    personne_id: int
    nom: str
    prenom: str
    adresse: str | None
    statut: str
    """`impose`, `refuse` ou `echec`."""
    message: str | None = None
    releve_koxo: date | None = None
    """Le jour où le mot de passe donné à Google a été lu dans KoXo."""


def _annee(session: Session, annee_id: int | None) -> AnneeScolaire:
    if annee_id is not None:
        annee = session.get(AnneeScolaire, annee_id)
    else:
        annee = session.query(AnneeScolaire).order_by(AnneeScolaire.libelle.desc()).first()
    if annee is None:
        raise ImpositionImpossible("Aucune année scolaire dans le référentiel.")
    return annee


def _inscrits(session: Session, annee: AnneeScolaire) -> dict[int, str | None]:
    """`{personne_id: classe}` des élèves inscrits cette année-là."""
    classes: dict[int, str | None] = {}
    for sn in (
        session.query(Snapshot)
        .filter(Snapshot.annee_scolaire_id == annee.id)
        .order_by(Snapshot.date_ingestion, Snapshot.id)
    ):
        classes[sn.personne_id] = sn.classe
    return classes


def changements(
    session: Session, evenements: list[dict], *, depuis: str, annee_id: int | None = None
) -> RapportChangements:
    """Rattache les changements de mot de passe Google aux élèves inscrits.

    Args:
        evenements: retour de `ClientGoogle.changements_de_mot_de_passe`.
    """
    annee = _annee(session, annee_id)
    rapport = RapportChangements(annee=annee.libelle, depuis=depuis, nb_evenements=len(evenements))
    classes = _inscrits(session, annee)
    sites = {s.id: s.nom for s in session.query(Site)}
    eleves = (
        session.query(Personne)
        .filter(Personne.id.in_(list(classes) or [0]), Personne.type == "eleve")
        .all()
    )
    par_adresse: dict[str, Personne] = {}
    for p in eleves:
        for a in (p.email_constate, p.email):
            if a:
                par_adresse.setdefault(a.strip().lower(), p)

    derniers: dict[int, ChangementGoogle] = {}
    compte: Counter[int] = Counter()
    for ev in evenements:
        p = par_adresse.get((ev.get("email") or "").lower())
        if p is None:
            rapport.nb_hors_eleves += 1
            continue
        compte[p.id] += 1
        quand = ev.get("quand") or ""
        if p.id in derniers and derniers[p.id].quand >= quand:
            continue
        derniers[p.id] = ChangementGoogle(
            personne_id=p.id, nom=p.nom or "", prenom=p.prenom or "",
            classe=classes.get(p.id) or p.classe, site=sites.get(p.site_id),
            adresse=(ev.get("email") or "").lower(), quand=quand,
            par=ev.get("par") or "", par_l_eleve=bool(ev.get("par_l_utilisateur")),
        )
    for pid, c in derniers.items():
        c.nb_changements = compte[pid]
    rapport.changements = sorted(
        derniers.values(), key=lambda c: (c.site or "~", c.classe or "~", c.nom, c.prenom)
    )
    return rapport


def imposer(
    session: Session, client, cle: bytes, personne_ids: list[int]
) -> list[ResultatImposition]:
    """Donne à Google le mot de passe KoXo des élèves désignés.

    Une écriture dans Google : ne s'appelle que sur confirmation. Chaque
    élève est vérifié avant l'envoi ; un refus n'arrête pas les suivants.
    """
    from backend.services.coffre import (
        lire_secret,
        releve_contredit,
        releve_le,
        secrets_a_remettre,
    )
    from backend.services.journal import journaliser

    sites = {s.id: s for s in session.query(Site)}
    resultats: list[ResultatImposition] = []
    for pid in dict.fromkeys(personne_ids):
        p = session.get(Personne, pid)
        if p is None:
            continue
        base = dict(personne_id=pid, nom=p.nom or "", prenom=p.prenom or "",
                    adresse=p.email_constate)

        def refuser(message: str) -> None:
            resultats.append(ResultatImposition(**base, statut="refuse", message=message))

        if p.type != "eleve":
            refuser("Réservé aux élèves : un adulte gère son mot de passe Google lui-même.")
            continue
        if not p.email_constate:
            refuser("Adresse calculée, pas encore constatée dans Google : on n'écrit pas "
                    "sur un compte qu'on n'a pas vu. Relève-la d'abord.")
            continue
        site = sites.get(p.site_id)
        recevables = secrets_a_remettre(
            session.query(SecretConserve).filter_by(personne_id=pid).all(), site
        )
        sans_koxo = site is not None and not (site.base_koxo or "").strip()
        attendu = "google" if sans_koxo else "koxo"
        if not recevables or recevables[0].cible != attendu:
            refuser(
                "Aucun mot de passe fabriqué au coffre pour ce site sans KoXo."
                if sans_koxo else
                "Aucun relevé KoXo au coffre : la copie de Charlemagne n'est pas le "
                "mot de passe. Verse au coffre l'export KoXo de son site."
            )
            continue
        if releve_contredit(recevables, cle) is not None:
            refuser("Son relevé KoXo est contredit par une source lue après lui : KoXo a "
                    "peut-être changé. Verse au coffre un export KoXo récent.")
            continue

        r = ResultatImposition(**base, statut="impose", releve_koxo=releve_le(recevables[0]))
        try:
            client.imposer_mot_de_passe(p.email_constate, lire_secret(cle, recevables[0]))
        except Exception as e:
            r.statut, r.message = "echec", f"{type(e).__name__}: {e}"
        resultats.append(r)

    # Le journal compte et désigne par numéro ; ni nom, ni mot de passe.
    journaliser(
        session,
        type_operation="identifiant",
        cible="google",
        mode="reel",
        parametres={"personnes": [r.personne_id for r in resultats if r.statut == "impose"]},
        resultat=dict(Counter(r.statut for r in resultats)),
        notes="Mot de passe KoXo imposé aux comptes Google, sur confirmation.",
    )
    session.commit()
    return resultats
