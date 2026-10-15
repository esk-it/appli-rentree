"""La rentrée conduite comme un tutoriel : chapitres, étapes, constats.

## Ce que Johann a demandé (15 octobre 2026)

« Un truc vraiment guidé, limite on te prend par la main » : qu'une
personne qui n'a jamais fait de rentrée la réussisse en suivant les écrans.
Chaque écran dit ce qu'il faut faire, le fait depuis l'écran, montre un
**avant / après** — ce qui a été fait réellement —, et on ne passe au
suivant qu'une fois l'étape **validée**. Les réglages faits une fois pour
toutes sortent de la campagne. Maquettes : tour 7 et 7 bis du canvas.

## Ce que ce module porte

- le **catalogue** : six chapitres, dix-huit étapes, dans l'ordre ;
- les **mesures** de chaque étape — ce qui se constate dans le référentiel,
  et, sur demande, dans Google ;
- l'**état** de la campagne d'une année : ce qui est validé, quand, avec
  quel avant et quel après ; l'étape courante ; celles qui restent fermées.

Les textes qui guident — le but, les gestes, le piège, le schéma du
logiciel où cliquer — vivent dans l'interface (`src/lib/rentree/`). Ici,
ce qui se mesure et ce qui se décide.

## Ce qui ouvre une étape

L'ordre est strict : une étape s'ouvre quand la précédente est validée —
ou **reportée**, pour celles qui ne peuvent pas encore se faire (les
professeurs avant le 1er septembre). Une étape validée se rouvre ; elle
redevient « en cours ».

## Ce qui valide une étape

Ses mesures **bloquantes** doivent être bonnes : « 0 compte à créer ».
Sinon, la validation est refusée et dit pourquoi — à moins de la forcer
avec une raison, gardée avec l'étape. Une mesure inconnue (Google pas
encore relu) n'est pas une mesure bonne. Une étape sans mesure (imprimer
les étiquettes) se valide sur la parole de qui l'a faite.
"""
from __future__ import annotations

import json
import re
from collections.abc import Callable
from dataclasses import asdict, dataclass, field
from datetime import date, datetime

from sqlalchemy.orm import Session

from backend.models import (
    AnneeScolaire,
    Arbitrage,
    CompteCible,
    EtapeRentree,
    LoginReserve,
    Personne,
    Site,
    Snapshot,
    TableCorrespondance,
)


class RentreeImpossible(Exception):
    """Le geste est refusé, et le message dit pourquoi."""


# ---------------------------------------------------------------------------
# Le catalogue
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class Chapitre:
    id: str
    titre: str
    couleur: str


CHAPITRES = (
    Chapitre("ouvrir", "Ouvrir l'année", "#8F80FF"),
    Chapitre("eleves", "Élèves et professeurs", "#2BC4D8"),
    Chapitre("comptes", "Les comptes", "#16995F"),
    Chapitre("google", "Google", "#2F6CE0"),
    Chapitre("documents", "Les documents", "#FF7A59"),
    Chapitre("clore", "Clore", "#FFB938"),
)


@dataclass(frozen=True)
class Etape:
    id: str
    chapitre: str
    titre: str
    mesures: tuple[str, ...] = ()
    reportable: bool = False
    """Peut être laissée pour plus tard sans bloquer la suite."""
    pas_avant: str | None = None
    """`MM-JJ` : rien ne sert de la faire plus tôt dans l'année scolaire."""


ETAPES = (
    Etape("mise_en_place", "ouvrir", "Vérifier la mise en place", ("reglages_manquants",)),
    Etape("annee", "ouvrir", "Préparer l'année et ses unités", ("chemins_hors_annee",)),
    Etape("eleves", "eleves", "Charger l'export des élèves", ("eleves_inscrits", "classes_hors_table")),
    Etape("departager", "eleves", "Départager les cas ambigus", ("arbitrages_en_attente",)),
    Etape("professeurs", "eleves", "Charger les professeurs", ("adultes_inscrits",),
          reportable=True, pas_avant="09-01"),
    Etape("koxo", "comptes", "Synchroniser KoXo", ("eleves_absents_koxo",)),
    Etape("charlemagne_mdp", "comptes", "Recopier les mots de passe dans Charlemagne",
          ("mots_de_passe_divergents",)),
    Etape("comptes_google", "comptes", "Créer les comptes Google des nouveaux",
          ("eleves_sans_compte_google", "comptes_a_rattacher")),
    Etape("sortants", "google", "Ranger les sortants"),
    Etape("unites", "google", "Préparer les unités de l'année", ("unites_manquantes",)),
    Etape("bascule", "google", "Basculer les élèves dans leur classe", ("eleves_sans_unite",)),
    Etape("groupes", "google", "Les groupes de classe"),
    Etape("etiquettes", "documents", "Étiquettes et listes par classe"),
    Etape("cartes", "documents", "Les cartes (CardStudio)"),
    Etape("badges", "documents", "Les badges (TS1000)"),
    Etape("pmb_sodexo", "documents", "PMB et Sodexo"),
    Etape("chromebooks", "clore", "Les Chromebooks", reportable=True),
    Etape("bilan", "clore", "Le bilan de la rentrée"),
)

PAR_ID = {e.id: e for e in ETAPES}


# ---------------------------------------------------------------------------
# Les mesures
# ---------------------------------------------------------------------------


@dataclass
class Mesure:
    id: str
    libelle: str
    valeur: int | None
    """`None` : pas encore lue — Google pas interrogé, coffre fermé."""
    attendu: str
    """`zero` (bonne à 0), `positif` (bonne au-dessus de 0) ou `info`."""
    bloquante: bool
    detail: str = ""
    source: str = "referentiel"
    lu_le: str = ""

    @property
    def bonne(self) -> bool | None:
        if self.valeur is None:
            return None
        if self.attendu == "zero":
            return self.valeur == 0
        if self.attendu == "positif":
            return self.valeur > 0
        return True


@dataclass
class Contexte:
    """Ce dont les mesures ont besoin, lu une fois."""

    session: Session
    libelle: str
    """La rentrée conduite, « 2027-2028 »."""
    annee: AnneeScolaire | None = None
    """Son année dans le référentiel — absente tant que l'export n'est pas ingéré."""
    comptes_google: list[dict] | None = None
    ou_google: list[str] | None = None
    cle_coffre: bytes | None = None


def contexte(session: Session, libelle: str, **kw) -> Contexte:
    annee = session.query(AnneeScolaire).filter_by(libelle=libelle).one_or_none()
    return Contexte(session=session, libelle=libelle, annee=annee, **kw)


def _pas_ingeree(id_: str, libelle: str, attendu: str, bloquante: bool, ctx: Contexte) -> Mesure:
    return Mesure(id_, libelle, None, attendu, bloquante,
                  f"L'export de {ctx.libelle} n'est pas encore ingéré.")


def _inscrits(ctx: Contexte, type_personne: str) -> list[Personne]:
    if ctx.annee is None:
        return []
    ids = {
        pid for (pid,) in ctx.session.query(Snapshot.personne_id)
        .filter(Snapshot.annee_scolaire_id == ctx.annee.id).distinct()
    }
    return (
        ctx.session.query(Personne)
        .filter(Personne.id.in_(ids or {0}), Personne.type == type_personne)
        .all()
    )


def _annee_des_unites(libelle: str) -> str | None:
    """`2027-2028` → `2028` : l'arbre Google porte l'année qui se termine."""
    m = re.fullmatch(r"(\d{4})-(\d{4})", (libelle or "").strip())
    return m.group(2) if m else None


def _reglages_manquants(ctx: Contexte) -> Mesure:
    from backend.services.coffre import est_initialise
    from backend.services.google_api import charger_config

    manquent = []
    if charger_config(ctx.session).valider():
        manquent.append("la connexion à Google")
    if not est_initialise(ctx.session):
        manquent.append("le coffre des mots de passe")
    sites = ctx.session.query(Site).all()
    if not sites:
        manquent.append("les établissements")
    elif any(not (s.domaine_mail or "").strip() for s in sites):
        manquent.append("le domaine de messagerie d'un établissement")
    if not ctx.session.query(TableCorrespondance).count():
        manquent.append("la table des classes")
    return Mesure(
        "reglages_manquants", "Réglages qui manquent", len(manquent), "zero", True,
        "Manquent : " + ", ".join(manquent) + "." if manquent else "Tout est en place.",
    )


def _chemins_hors_annee(ctx: Contexte) -> Mesure:
    cible = _annee_des_unites(ctx.libelle)
    chemins = [
        t.ou_definitive for t in ctx.session.query(TableCorrespondance) if t.ou_definitive
    ]
    if cible is None or not chemins:
        return Mesure("chemins_hors_annee", "Classes qui visent une autre année", None,
                      "zero", True, "La table des classes est vide.")
    hors = [c for c in chemins if cible not in c]
    return Mesure(
        "chemins_hors_annee", "Classes qui visent une autre année", len(hors), "zero", True,
        f"Les {len(chemins)} classes visent les unités …{cible}." if not hors
        else f"{len(hors)} classe(s) visent encore une autre année que …{cible}.",
    )


def _eleves_inscrits(ctx: Contexte) -> Mesure:
    if ctx.annee is None:
        return Mesure("eleves_inscrits", "Élèves inscrits cette année", 0, "positif", True,
                      f"L'export de {ctx.libelle} n'est pas encore ingéré.")
    n = len(_inscrits(ctx, "eleve"))
    return Mesure("eleves_inscrits", "Élèves inscrits cette année", n, "positif", True,
                  f"{n} élève(s) photographié(s) en {ctx.libelle}.")


def _classes_hors_table(ctx: Contexte) -> Mesure:
    if ctx.annee is None:
        return _pas_ingeree("classes_hors_table", "Classes absentes de la table", "zero", True, ctx)
    connues = {
        (t.classe_code_court or "").strip() for t in ctx.session.query(TableCorrespondance)
    }
    classes = {
        (c or "").strip() for (c,) in ctx.session.query(Snapshot.classe)
        .filter(Snapshot.annee_scolaire_id == ctx.annee.id).distinct()
    } - {""}
    hors = sorted(classes - connues)
    return Mesure(
        "classes_hors_table", "Classes absentes de la table", len(hors), "zero", True,
        ("À compléter : " + ", ".join(hors[:8]) + ("…" if len(hors) > 8 else ""))
        if hors else "Chaque classe a sa ligne dans la table.",
    )


def _arbitrages_en_attente(ctx: Contexte) -> Mesure:
    n = ctx.session.query(Arbitrage).filter(Arbitrage.decision.is_(None)).count()
    return Mesure("arbitrages_en_attente", "Cas à départager", n, "zero", True,
                  "Plus rien à trancher." if not n else f"{n} décision(s) attendent.")


def _adultes_inscrits(ctx: Contexte) -> Mesure:
    n = len(_inscrits(ctx, "adulte"))
    return Mesure("adultes_inscrits", "Professeurs et personnels de l'année", n, "positif",
                  True, f"{n} adulte(s) photographié(s) en {ctx.libelle}.")


def _eleves_absents_koxo(ctx: Contexte) -> Mesure:
    if ctx.annee is None:
        return _pas_ingeree("eleves_absents_koxo", "Élèves absents de KoXo", "zero", True, ctx)
    sites ={s.id: s for s in ctx.session.query(Site)}
    avec_koxo = {sid for sid, s in sites.items() if (s.base_koxo or "").strip()}
    eleves = [p for p in _inscrits(ctx, "eleve") if p.site_id in avec_koxo]
    vus: dict[str, set[int]] = {}
    for c in ctx.session.query(LoginReserve).filter(LoginReserve.badge.isnot(None)):
        vus.setdefault(c.site or "", set()).add(c.badge)
    if not vus:
        return Mesure("eleves_absents_koxo", "Élèves absents de KoXo", None, "zero", True,
                      "Se constate en redonnant au programme l'export de chaque base KoXo.")
    absents = [
        p for p in eleves
        if p.badge not in vus.get(sites[p.site_id].nom, set())
        and p.badge not in vus.get((sites[p.site_id].base_koxo or "").strip(), set())
    ]
    return Mesure(
        "eleves_absents_koxo", "Élèves absents de KoXo", len(absents), "zero", True,
        f"Les {len(eleves)} élèves de NDK et SU sont dans KoXo." if not absents
        else f"{len(absents)} élève(s) absent(s) du dernier export KoXo relu.",
    )


def _mots_de_passe_divergents(ctx: Contexte) -> Mesure:
    if ctx.cle_coffre is None:
        return Mesure("mots_de_passe_divergents", "KoXo et Charlemagne en désaccord", None,
                      "zero", True, "Ouvre le coffre : il faut déchiffrer pour comparer.",
                      source="coffre")
    from backend.services.coffre import ecarts

    n = len(ecarts(ctx.session, ctx.cle_coffre))
    return Mesure(
        "mots_de_passe_divergents", "KoXo et Charlemagne en désaccord", n, "zero", True,
        "Chaque mot de passe de Charlemagne est celui de KoXo." if not n
        else f"{n} personne(s) : Charlemagne ne porte pas le mot de passe de KoXo.",
        source="coffre",
    )


def _google_requis(id_: str, libelle: str, attendu: str, bloquante: bool) -> Mesure:
    return Mesure(id_, libelle, None, attendu, bloquante,
                  "Se lit dans Google : « Relire dans Google ».", source="google")


def _eleves_sans_compte_google(ctx: Contexte) -> Mesure:
    if ctx.annee is None:
        return _pas_ingeree("eleves_sans_compte_google", "Comptes Google à créer", "zero", True, ctx)
    if ctx.comptes_google is None:
        return _google_requis("eleves_sans_compte_google", "Comptes Google à créer", "zero", True)
    from backend.services.comptes_google_nouveaux import relever

    r = relever(ctx.session, ctx.comptes_google, annee_id=ctx.annee.id)
    return Mesure(
        "eleves_sans_compte_google", "Comptes Google à créer", len(r.a_creer), "zero", True,
        f"{r.nb_avec_compte} élève(s) sur {r.nb_inscrits} ont leur compte.",
        source="google",
    )


def _comptes_a_rattacher(ctx: Contexte) -> Mesure:
    if ctx.annee is None:
        return _pas_ingeree("comptes_a_rattacher", "Comptes au même nom, à rattacher", "zero", False, ctx)
    if ctx.comptes_google is None:
        return _google_requis("comptes_a_rattacher", "Comptes au même nom, à rattacher", "zero", False)
    from backend.services.comptes_google_nouveaux import relever

    r = relever(ctx.session, ctx.comptes_google, annee_id=ctx.annee.id)
    return Mesure(
        "comptes_a_rattacher", "Comptes au même nom, à rattacher", len(r.a_rattacher), "zero",
        False, "Ils n'empêchent pas de continuer." if r.a_rattacher else "Aucun.",
        source="google",
    )


def _unites_manquantes(ctx: Contexte) -> Mesure:
    if ctx.ou_google is None:
        return _google_requis("unites_manquantes", "Unités de l'année qui manquent", "zero", True)
    from backend.services.ou_google import analyser_conformite

    r = analyser_conformite(ctx.session, ctx.ou_google, autoriser_renommage=False)
    return Mesure(
        "unites_manquantes", "Unités de l'année qui manquent", r.nb_a_creer, "zero", True,
        f"Les {len(r.ou_attendues)} unités attendues existent." if not r.nb_a_creer
        else f"{r.nb_a_creer} unité(s) à créer avant de basculer.",
        source="google",
    )


def _eleves_sans_unite(ctx: Contexte) -> Mesure:
    if ctx.annee is None:
        return _pas_ingeree("eleves_sans_unite", "Élèves pas encore placés dans leur classe",
                            "zero", True, ctx)
    eleves = _inscrits(ctx, "eleve")
    places = {
        c.personne_id for c in ctx.session.query(CompteCible).filter_by(cible="google")
        if c.ou_appliquee
    }
    sans = [p for p in eleves if p.id not in places]
    return Mesure(
        "eleves_sans_unite", "Élèves pas encore placés dans leur classe", len(sans), "zero", True,
        f"Les {len(eleves)} élèves ont reçu leur unité." if not sans
        else f"{len(sans)} élève(s) pas encore basculé(s).",
    )


MESURES: dict[str, Callable[[Contexte], Mesure]] = {
    "reglages_manquants": _reglages_manquants,
    "chemins_hors_annee": _chemins_hors_annee,
    "eleves_inscrits": _eleves_inscrits,
    "classes_hors_table": _classes_hors_table,
    "arbitrages_en_attente": _arbitrages_en_attente,
    "adultes_inscrits": _adultes_inscrits,
    "eleves_absents_koxo": _eleves_absents_koxo,
    "mots_de_passe_divergents": _mots_de_passe_divergents,
    "eleves_sans_compte_google": _eleves_sans_compte_google,
    "comptes_a_rattacher": _comptes_a_rattacher,
    "unites_manquantes": _unites_manquantes,
    "eleves_sans_unite": _eleves_sans_unite,
}

MESURES_GOOGLE = {"eleves_sans_compte_google", "comptes_a_rattacher", "unites_manquantes"}


def mesurer(ctx: Contexte, etape_id: str) -> list[Mesure]:
    maintenant = datetime.now().isoformat(timespec="minutes")
    sortie = []
    for mid in PAR_ID[etape_id].mesures:
        m = MESURES[mid](ctx)
        if m.valeur is not None:
            m.lu_le = maintenant
        sortie.append(m)
    return sortie


# ---------------------------------------------------------------------------
# L'état de la campagne
# ---------------------------------------------------------------------------


@dataclass
class EtatEtape:
    id: str
    chapitre: str
    titre: str
    rang: int
    statut: str
    """`validee`, `reportee`, `en_cours`, `a_faire` (ouverte, jamais
    commencée) ou `fermee` (une étape précédente n'est pas finie)."""
    validee_le: str | None = None
    note: str | None = None
    reportable: bool = False
    pas_avant: str | None = None
    gestes: list[str] = field(default_factory=list)
    gestes_le: dict = field(default_factory=dict)
    """L'heure de chaque geste déclaré : ce que le bilan du chapitre raconte."""
    avant: dict = field(default_factory=dict)
    apres: dict = field(default_factory=dict)


@dataclass
class EtatCampagne:
    annee: str
    """Le libellé de la rentrée, « 2027-2028 »."""
    annee_id: int | None
    """Son année dans le référentiel, une fois l'export ingéré."""
    chapitres: list[dict]
    etapes: list[EtatEtape]
    courante: str | None
    """La première étape ni validée ni reportée."""

    @property
    def nb_validees(self) -> int:
        return sum(1 for e in self.etapes if e.statut == "validee")


def _lignes(session: Session, libelle: str) -> dict[str, EtapeRentree]:
    return {l.etape: l for l in session.query(EtapeRentree).filter_by(annee=libelle)}


def _finie(lignes: dict[str, EtapeRentree]) -> bool:
    return all(
        (l := lignes.get(e.id)) is not None and l.statut in ("validee", "reportee")
        for e in ETAPES
    )


def etat(session: Session, *, annee: str | None = None) -> EtatCampagne:
    """La campagne d'une rentrée — par défaut, celle qui se prépare."""
    libelle = annee or annee_a_preparer(session)[0]
    lignes = _lignes(session, libelle)
    etapes: list[EtatEtape] = []
    courante = None
    for rang, e in enumerate(ETAPES, start=1):
        l = lignes.get(e.id)
        if l is not None and l.statut in ("validee", "reportee"):
            statut = l.statut
        elif courante is None:
            courante = e.id
            statut = "en_cours" if l is not None else "a_faire"
        else:
            statut = "fermee"
        etapes.append(EtatEtape(
            id=e.id, chapitre=e.chapitre, titre=e.titre, rang=rang, statut=statut,
            validee_le=l.validee_le.isoformat(timespec="minutes") if l and l.validee_le else None,
            note=l.note if l else None, reportable=e.reportable, pas_avant=e.pas_avant,
            gestes=[g["id"] for g in json.loads(l.gestes_json or "[]")] if l else [],
            gestes_le={g["id"]: g["le"] for g in json.loads(l.gestes_json or "[]")} if l else {},
            avant=json.loads(l.avant_json or "{}") if l else {},
            apres=json.loads(l.apres_json or "{}") if l else {},
        ))
    a = session.query(AnneeScolaire.id).filter_by(libelle=libelle).scalar()
    return EtatCampagne(
        annee=libelle, annee_id=a,
        chapitres=[asdict(c) for c in CHAPITRES], etapes=etapes, courante=courante,
    )


def _ouverte(session: Session, libelle: str, etape_id: str) -> EtapeRentree:
    """La ligne de l'étape, créée à sa première ouverture. Refuse une étape fermée."""
    if etape_id not in PAR_ID:
        raise RentreeImpossible(f"Étape inconnue : {etape_id}")
    campagne = etat(session, annee=libelle)
    e = next(x for x in campagne.etapes if x.id == etape_id)
    if e.statut == "fermee":
        precedente = next(
            x for x in campagne.etapes if x.id == campagne.courante
        )
        raise RentreeImpossible(
            f"Cette étape s'ouvrira après « {precedente.titre} » (étape {precedente.rang})."
        )
    ligne = _lignes(session, libelle).get(etape_id)
    if ligne is None:
        ligne = EtapeRentree(annee=libelle, etape=etape_id, statut="en_cours")
        session.add(ligne)
        session.flush()
    return ligne


def _photo(mesures: list[Mesure]) -> dict:
    return {
        m.id: {"libelle": m.libelle, "valeur": m.valeur, "detail": m.detail, "lu_le": m.lu_le,
               "bonne": m.bonne, "bloquante": m.bloquante}
        for m in mesures if m.valeur is not None
    }


def ouvrir(session: Session, ctx: Contexte, etape_id: str) -> list[Mesure]:
    """Ouvre l'étape et relève ses mesures — l'« avant », s'il n'existe pas encore.

    Une mesure lue pour la première fois (Google relu plus tard) complète
    l'avant : c'est sa première valeur constatée.
    """
    ligne = _ouverte(session, ctx.libelle, etape_id)
    mesures = mesurer(ctx, etape_id)
    if ligne.statut == "en_cours":
        avant = json.loads(ligne.avant_json or "{}")
        for mid, photo in _photo(mesures).items():
            avant.setdefault(mid, photo)
        ligne.avant_json = json.dumps(avant, ensure_ascii=False)
    session.commit()
    return mesures


def declarer_geste(session: Session, libelle: str, etape_id: str, geste: str,
                   *, fait: bool = True) -> list[str]:
    """Un geste que le programme ne voit pas — « c'est importé dans KoXo »."""
    ligne = _ouverte(session, libelle, etape_id)
    gestes = [g for g in json.loads(ligne.gestes_json or "[]") if g["id"] != geste]
    if fait:
        gestes.append({"id": geste, "le": datetime.now().isoformat(timespec="minutes")})
    ligne.gestes_json = json.dumps(gestes, ensure_ascii=False)
    session.commit()
    return [g["id"] for g in gestes]


def valider(session: Session, ctx: Contexte, etape_id: str, *, forcer: bool = False,
            note: str | None = None) -> EtatEtape:
    """Valide l'étape sur ce qui est constaté maintenant — l'« après ».

    Refuse tant qu'une mesure bloquante n'est pas bonne — inconnue compris —,
    sauf à forcer avec une raison.
    """
    ligne = _ouverte(session, ctx.libelle, etape_id)
    mesures = mesurer(ctx, etape_id)
    pas_bonnes = [m for m in mesures if m.bloquante and m.bonne is not True]
    if pas_bonnes and not forcer:
        raise RentreeImpossible(
            "Pas encore : " + " ; ".join(
                f"{m.libelle} — {m.detail}" for m in pas_bonnes
            )
        )
    if pas_bonnes and not (note or "").strip():
        raise RentreeImpossible("Valider malgré un écart demande d'en dire la raison.")
    ligne.statut = "validee"
    ligne.validee_le = datetime.now()
    ligne.apres_json = json.dumps(_photo(mesures), ensure_ascii=False)
    ligne.note = (note or "").strip() or None
    session.commit()
    return next(e for e in etat(session, annee=ctx.libelle).etapes if e.id == etape_id)


def reporter(session: Session, libelle: str, etape_id: str, *, note: str | None = None) -> None:
    """Laisse passer une étape qui ne peut pas encore se faire."""
    if not PAR_ID.get(etape_id, Etape("", "", "")).reportable:
        raise RentreeImpossible("Cette étape ne se reporte pas : la suite en dépend.")
    ligne = _ouverte(session, libelle, etape_id)
    ligne.statut = "reportee"
    ligne.note = (note or "").strip() or "Reportée."
    session.commit()


def rouvrir(session: Session, libelle: str, etape_id: str) -> None:
    """Une étape validée redevient en cours — un export repris, un compte oublié.

    Les étapes suivantes restent validées : elles le disent elles-mêmes si
    ce qu'on y refait change leurs mesures.
    """
    ligne = _lignes(session, libelle).get(etape_id)
    if ligne is None:
        raise RentreeImpossible("Cette étape n'a jamais été ouverte.")
    ligne.statut = "en_cours"
    ligne.validee_le = None
    session.commit()


# ---------------------------------------------------------------------------
# Quelle rentrée, et à partir de quand
# ---------------------------------------------------------------------------


def _libelle_valide(libelle: str) -> tuple[int, int]:
    if not re.fullmatch(r"\d{4}-\d{4}", (libelle or "").strip()):
        raise RentreeImpossible(f"Année invalide : {libelle!r} (attendu : 2027-2028).")
    debut, fin = (int(x) for x in libelle.split("-"))
    if fin != debut + 1:
        raise RentreeImpossible(f"Année invalide : {libelle!r}.")
    return debut, fin


def s_ouvre_le(libelle: str) -> date:
    """Le 1er juillet : avant, la rentrée suivante n'a rien à préparer.

    Faire tourner la table des classes en octobre ferait viser les unités
    de l'année prochaine pendant que celle-ci tourne encore.
    """
    return date(_libelle_valide(libelle)[0], 7, 1)


def _derniere_chargee(session: Session) -> str | None:
    """La plus récente année dont un export a été ingéré."""
    return (
        session.query(AnneeScolaire.libelle)
        .join(Snapshot, Snapshot.annee_scolaire_id == AnneeScolaire.id)
        .order_by(AnneeScolaire.libelle.desc())
        .limit(1)
        .scalar()
    )


def commencer(session: Session, libelle: str, *, aujourd_hui: date | None = None) -> str:
    """Ouvre la campagne : sa première étape devient « en cours ».

    L'année elle-même n'est pas créée : l'ingestion de l'export le fera,
    comme toujours (voir `models/etape_rentree.py`).
    """
    ouverture = s_ouvre_le(libelle)
    if (aujourd_hui or date.today()) < ouverture:
        raise RentreeImpossible(
            f"La rentrée {libelle} se prépare à partir du {ouverture.strftime('%d/%m/%Y')} : "
            "avant, ses étapes viseraient l'année qui tourne encore."
        )
    derniere = _derniere_chargee(session)
    if derniere is not None and libelle < derniere:
        raise RentreeImpossible(f"La rentrée {libelle} est passée : {derniere} est déjà chargée.")
    _ouverte(session, libelle, ETAPES[0].id)
    session.commit()
    return libelle


def _suivante(libelle: str) -> str:
    debut = _libelle_valide(libelle)[0] + 1
    return f"{debut}-{debut + 1}"


def annee_a_preparer(session: Session) -> tuple[str, bool]:
    """La rentrée à conduire, et si sa campagne est déjà commencée.

    - une campagne commencée et pas finie, tant qu'aucune année plus
      récente n'a été chargée depuis ;
    - sinon l'année la plus récente du référentiel, si elle a été créée
      sans que rien n'y soit ingéré ;
    - sinon la rentrée qui suit la dernière année chargée ou la dernière
      campagne finie. 2026-2027 s'est faite avant l'assistant : c'est
      2027-2028 qui se prépare.
    """
    chargee = _derniere_chargee(session)
    campagnes = sorted(
        {a for (a,) in session.query(EtapeRentree.annee).distinct()}, reverse=True
    )
    for libelle in campagnes:
        if chargee is not None and libelle < chargee:
            break
        if not _finie(_lignes(session, libelle)):
            return libelle, True
    derniere = (
        session.query(AnneeScolaire.libelle).order_by(AnneeScolaire.libelle.desc()).limit(1).scalar()
    )
    if derniere is not None and derniere != chargee and derniere not in campagnes:
        return derniere, False
    connues = [x for x in (chargee, *campagnes) if x]
    if connues:
        return _suivante(max(connues)), False
    j = date.today()
    debut = j.year if j.month >= 7 else j.year - 1
    return f"{debut}-{debut + 1}", False
