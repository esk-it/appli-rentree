"""Les adresses calculées que Google confirme, relevées une fois pour toutes.

## Pourquoi

Le référentiel distingue l'adresse *constatée* — celle d'un compte qui
existe — de l'adresse *calculée* (`prenom.nom@`), une hypothèse. Les élèves
de NDK et de SU ont été relevés à l'amorçage et dans les exports ; pas les
autres. Au 5 octobre 2026, 152 adultes et 74 élèves de NDE avaient une
adresse calculée qui désignait bel et bien leur compte Google, et le
Référentiel les affichait pourtant « calculée, pas encore relevée dans
Google ». Johann : « avec les connexions qu'on a sur Google, ça devrait être
simple de tout vérifier et d'adapter le référentiel ».

## Ce qui se relève sans demander

Une adresse attendue — attribuée, calculée, ou celle que la base KoXo
détient — qui est l'adresse ou l'alias d'un compte Google, quand tout
concorde :

- le compte porte le nom de la personne, aux accents, aux tirets et à
  l'ordre nom/prénom près ;
- aucune autre fiche ne revendique cette adresse — pas d'homonyme, ni
  d'aujourd'hui ni d'une année passée ;
- le compte ne porte pas le numéro Charlemagne de quelqu'un d'autre ;
- il n'est ni suspendu ni rangé chez les sortis.

Le relevé n'écrit que dans le référentiel, et l'adresse affichée ne change
pas : elle devient un constat. Rien n'est écrit dans Google.

## Ce qui se propose

Le reste, avec sa raison : l'adresse existe mais le compte porte un autre
nom (`victor.guez@`, alias du compte de Victor GHEZ), il est suspendu ou
rangé chez les sortis, un homonyme la revendique, ou l'adresse n'existe pas
mais un seul compte porte ce nom. On coche, on retient.

## Ce qui reste calculé

Aucun compte ne porte ce nom : il reste à créer — pour un élève, c'est
« Comptes Google des nouveaux », sous l'ingestion.
"""
from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass, field

from sqlalchemy.orm import Session

from backend.models import AnneeScolaire, Personne, Site, Snapshot


class ReleveImpossible(Exception):
    """Le relevé est refusé, et le message dit pourquoi."""


@dataclass
class AdresseReleve:
    personne_id: int
    nom: str
    prenom: str
    type: str
    site: str | None
    classe: str | None
    adresse_affichee: str | None
    """Celle que le référentiel montrait : calculée ou attribuée."""
    adresse_google: str | None
    """L'adresse principale du compte retrouvé — relevée ou proposée."""
    ou_google: str | None = None
    motif: str = ""
    google_id: str | None = None


@dataclass
class RapportReleve:
    annee: str
    nb_inscrits: int = 0
    nb_deja_constatees: int = 0
    relevees: list[AdresseReleve] = field(default_factory=list)
    """Confirmées par Google sans ambiguïté — enregistrées d'office."""
    a_verifier: list[AdresseReleve] = field(default_factory=list)
    """Un compte probable, mais quelque chose ne concorde pas."""
    sans_compte: list[AdresseReleve] = field(default_factory=list)
    """Aucun compte à ce nom : l'adresse reste calculée."""


def plier(texte: str | None) -> str:
    """`LE GALL`, `Le-Gall` et `le gall` se reconnaissent ; `Maëlys` et
    `Maelys` aussi."""
    t = unicodedata.normalize("NFKD", texte or "")
    t = "".join(c for c in t if not unicodedata.combining(c)).casefold()
    return re.sub(r"[\s_\-'’.]+", " ", t).strip()


def _meme_nom(p: Personne, u: dict) -> bool:
    """Le compte porte-t-il le nom de la personne ?

    Dans les deux ordres : sur l'instance réelle, des centaines de comptes
    portent le prénom dans le champ du nom — ils ont été créés ainsi. Le nom
    d'usage compte aussi.
    """
    g = (plier(u.get("nom")), plier(u.get("prenom")))
    prenom = plier(p.prenom)
    for nom in {plier(p.nom), plier(p.nom_usage)} - {""}:
        if g in ((nom, prenom), (prenom, nom)):
            return True
    return False


def _annee(session: Session, annee_id: int | None) -> AnneeScolaire:
    if annee_id is not None:
        annee = session.get(AnneeScolaire, annee_id)
    else:
        annee = session.query(AnneeScolaire).order_by(AnneeScolaire.libelle.desc()).first()
    if annee is None:
        raise ReleveImpossible("Aucune année scolaire dans le référentiel.")
    return annee


def _racines_des_sortis(session: Session) -> tuple[str, ...]:
    from backend.services.configuration import get_param

    racines = {(get_param(session, "google.ou_sortants") or "/7. Sortis").rstrip("/")}
    racines |= {(s.ou_sortants or "").strip().rstrip("/") for s in session.query(Site)}
    return tuple(sorted(r for r in racines if r))


def relever(
    session: Session, comptes_google: list[dict], *, annee_id: int | None = None
) -> RapportReleve:
    """Confronte les adresses non constatées des inscrits à l'annuaire.

    Ne modifie rien : `enregistrer` écrit ce qui a été relevé.

    Args:
        comptes_google: tous les comptes du domaine, tels que
            `ClientGoogle.lister_utilisateurs` les rend.
        annee_id: l'année dont on examine les inscrits ; par défaut la plus
            récente.
    """
    from backend.models import LoginReserve
    from backend.services.regles_metier import calculer_email

    annee = _annee(session, annee_id)
    rapport = RapportReleve(annee=annee.libelle)
    sortis = _racines_des_sortis(session)

    par_adresse: dict[str, dict] = {}
    par_nom: dict[tuple[str, str], list[dict]] = {}
    for u in comptes_google:
        principale = (u.get("email") or "").strip().lower()
        if not principale:
            continue
        par_adresse[principale] = u
        for a in u.get("alias") or []:
            par_adresse.setdefault((a or "").strip().lower(), u)
        cle = (plier(u.get("nom")), plier(u.get("prenom")))
        par_nom.setdefault(cle, []).append(u)
        if cle[0] != cle[1]:
            par_nom.setdefault((cle[1], cle[0]), []).append(u)

    sites = {s.id: s for s in session.query(Site)}
    classes: dict[int, str | None] = {}
    for sn in (
        session.query(Snapshot)
        .filter(Snapshot.annee_scolaire_id == annee.id)
        .order_by(Snapshot.date_ingestion, Snapshot.id)
    ):
        classes[sn.personne_id] = sn.classe

    # Ce que chaque fiche revendique — toutes les fiches, années passées
    # comprises : un ancien homonyme garde son adresse.
    def affichee(p: Personne) -> str | None:
        site = sites.get(p.site_id)
        a = p.email_attribuee or (
            calculer_email(p.prenom, p.nom, site.domaine_mail) if site else None
        )
        return (a or "").strip().lower() or None

    revendiquees: dict[str, set[int]] = {}
    tous = session.query(Personne).all()
    for p in tous:
        for a in {(p.email_constate or "").strip().lower(), affichee(p)} - {None, ""}:
            revendiquees.setdefault(a, set()).add(p.id)

    # L'adresse que chaque base KoXo détient en face d'un badge : un constat,
    # quand le calcul se trompe de particule (`isabelle.leduff@`).
    adresses_koxo: dict[int, set[str]] = {}
    for c in session.query(LoginReserve).filter(
        LoginReserve.badge.isnot(None), LoginReserve.email.isnot(None)
    ):
        a = (c.email or "").strip().lower()
        if "@" in a:
            adresses_koxo.setdefault(c.badge, set()).add(a)

    def ligne(p: Personne, u: dict | None, motif: str) -> AdresseReleve:
        site = sites.get(p.site_id)
        return AdresseReleve(
            personne_id=p.id, nom=p.nom or "", prenom=p.prenom or "", type=p.type,
            site=site.nom if site else None, classe=classes.get(p.id) or p.classe,
            adresse_affichee=affichee(p),
            adresse_google=(u.get("email") or "").lower() if u else None,
            ou_google=(u.get("ou") or None) if u else None,
            motif=motif, google_id=(u.get("id") or None) if u else None,
        )

    def autres_que(p: Personne, *adresses: str) -> set[int]:
        qui: set[int] = set()
        for a in adresses:
            qui |= revendiquees.get(a, set())
        return qui - {p.id}

    noms = {p.id: f"{p.prenom} {p.nom} ({p.cle_pivot})" for p in tous}

    for p in tous:
        if p.id not in classes:
            continue
        rapport.nb_inscrits += 1
        if p.email_constate:
            rapport.nb_deja_constatees += 1
            continue

        attendues = [a for a in [affichee(p), *sorted(adresses_koxo.get(p.badge, ()))] if a]
        trouves = list({id(u): u for a in attendues if (u := par_adresse.get(a))}.values())

        if len(trouves) > 1:
            rapport.a_verifier.append(ligne(
                p, None,
                "plusieurs comptes répondent à ses adresses : "
                + ", ".join(sorted(u["email"] for u in trouves)),
            ))
            continue

        if trouves:
            (u,) = trouves
            principale = (u.get("email") or "").lower()
            ou = u.get("ou") or ""
            autres = autres_que(p, principale, *[a for a in attendues if par_adresse.get(a) is u])
            numero = str(u.get("id_externe") or "").strip()
            if not _meme_nom(p, u):
                motif = f"le compte est au nom de {u.get('prenom', '')} {u.get('nom', '')}".rstrip()
            elif autres:
                motif = "revendiquée aussi par " + ", ".join(sorted(noms[i] for i in autres))
            elif numero and numero != str(p.id_charlemagne):
                motif = f"le compte porte un autre numéro Charlemagne ({numero})"
            elif u.get("suspendu"):
                motif = "le compte est suspendu"
            elif any(ou == r or ou.startswith(r + "/") for r in sortis):
                # L'adresse est bien la sienne ; c'est l'unité qui étonne
                # pour quelqu'un d'inscrit cette année.
                motif = f"inscrit cette année, mais son compte est rangé chez les sortis ({ou})"
            else:
                rapport.relevees.append(ligne(p, u, "adresse et nom concordent"))
                continue
            rapport.a_verifier.append(ligne(p, u, motif))
            continue

        # Aucune adresse attendue n'existe : un compte à son nom ?
        candidats = [
            u for u in par_nom.get((plier(p.nom), plier(p.prenom)), [])
            if not autres_que(p, (u.get("email") or "").lower())
        ]
        candidats = list({id(u): u for u in candidats}.values())
        if len(candidats) == 1:
            (u,) = candidats
            rapport.a_verifier.append(ligne(
                p, u,
                ("son adresse calculée n'existe pas" if affichee(p)
                 else "pas d'adresse calculable (sans site)")
                + " ; un seul compte porte son nom"
                + (" — suspendu" if u.get("suspendu") else ""),
            ))
        elif candidats:
            rapport.a_verifier.append(ligne(
                p, None,
                "plusieurs comptes portent son nom : "
                + ", ".join(sorted(u["email"] for u in candidats)),
            ))
        else:
            rapport.sans_compte.append(ligne(p, None, "aucun compte à son nom"))

    cle_tri = lambda r: (r.type, r.site or "~", r.nom, r.prenom)
    for liste in (rapport.relevees, rapport.a_verifier, rapport.sans_compte):
        liste.sort(key=cle_tri)
    return rapport


def _constater(p: Personne, adresse: str, google_id: str | None) -> None:
    p.email_constate = adresse
    if google_id and not p.google_user_id:
        p.google_user_id = google_id
    # Une adresse attribuée levait une homonymie faute de mieux : le constat
    # la remplace, comme quand on fige une adresse sur la fiche.
    p.email_attribuee = None


def enregistrer(session: Session, rapport: RapportReleve) -> int:
    """Écrit les adresses relevées. Le journal garde qui, sans les adresses.

    Returns:
        Le nombre d'adresses enregistrées.
    """
    from backend.services.journal import journaliser

    n = 0
    for r in rapport.relevees:
        p = session.get(Personne, r.personne_id)
        if p is None or p.email_constate or not r.adresse_google:
            continue
        _constater(p, r.adresse_google, r.google_id)
        n += 1
    if n:
        journaliser(
            session,
            type_operation="identifiant",
            cible="google",
            mode="reel",
            annee_libelle=rapport.annee,
            parametres={"personnes": [r.personne_id for r in rapport.relevees]},
            resultat={
                "relevees": n, "a_verifier": len(rapport.a_verifier),
                "sans_compte": len(rapport.sans_compte),
            },
            notes="Adresses calculées confirmées dans l'annuaire Google.",
        )
    session.commit()
    return n


@dataclass
class AdresseRetenue:
    personne_id: int
    adresse: str | None
    retenue: bool
    motif: str = ""


def retenir(
    session: Session, comptes: dict[str, dict | None], choix: dict[int, str]
) -> list[AdresseRetenue]:
    """Enregistre les propositions qu'on a cochées, vérifiées à nouveau.

    L'adresse doit toujours exister dans Google — l'adresse principale du
    compte est gardée, même si l'on a coché un alias — et aucune autre fiche
    ne doit l'avoir déjà constatée.

    Args:
        comptes: `{adresse: description}` telle que
            `ClientGoogle.lire_utilisateurs` la rend, `None` pour une
            adresse que Google ne connaît pas.
        choix: `{personne_id: adresse}`.
    """
    from backend.services.journal import journaliser

    connus = {(a or "").strip().lower(): u for a, u in comptes.items()}
    resultats: list[AdresseRetenue] = []
    for pid, adresse in choix.items():
        a = (adresse or "").strip().lower()
        p = session.get(Personne, pid)
        u = connus.get(a)
        if p is None:
            resultats.append(AdresseRetenue(pid, a, False, "fiche introuvable"))
            continue
        if u is None:
            resultats.append(AdresseRetenue(pid, a, False, "cette adresse n'existe plus dans Google"))
            continue
        principale = u["email"].lower()
        titulaire = (
            session.query(Personne)
            .filter(Personne.email_constate == principale, Personne.id != pid)
            .first()
        )
        if titulaire is not None:
            resultats.append(AdresseRetenue(
                pid, principale, False,
                f"déjà l'adresse de {titulaire.prenom} {titulaire.nom} ({titulaire.cle_pivot})",
            ))
            continue
        _constater(p, principale, u.get("id"))
        resultats.append(AdresseRetenue(pid, principale, True))

    faites = [r.personne_id for r in resultats if r.retenue]
    if faites:
        journaliser(
            session,
            type_operation="identifiant",
            cible="google",
            mode="reel",
            parametres={"personnes": faites},
            resultat={"retenues": len(faites), "refusees": len(resultats) - len(faites)},
            notes="Adresses proposées par le relevé Google, retenues à la main.",
        )
    session.commit()
    return resultats
