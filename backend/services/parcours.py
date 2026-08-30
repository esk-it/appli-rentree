"""Où en est la rentrée — étape par étape, sans deviner.

## Ce que ce module répond

Le parcours de rentrée compte quinze étapes, et l'écran n'en connaissait
l'état que de cinq. Les dix autres — toute la partie Google — restaient
muettes : le rail montrait l'ordre sans jamais dire où l'on en était. C'est
précisément là qu'on se perd, parce qu'on travaille une rentrée sur
plusieurs jours en fermant l'application entre deux.

Le silence venait d'une raison honnête : ces étapes se constatent dans
Google, et le programme ne savait pas le lire. Il le sait maintenant. Mais
en cherchant, il s'avère que **cinq d'entre elles ne demandent pas Google
du tout** — le référentiel les porte déjà :

- la rotation de la Table se lit dans les chemins d'OU qu'elle déclare ;
- le contrôle KoXo se lit dans les constats qu'il a laissés ;
- la synchronisation KoXo se lit dans ces mêmes constats, en regardant si
  chaque élève de l'année s'y trouve ;
- la bascule se lit dans les OU que le programme a mémorisées en les
  appliquant ;
- les Chromebooks se lisent dans leur propre suivi.

## Deux coûts, deux moments

Les états tirés du référentiel se recalculent à chaque navigation : c'est
une poignée de requêtes locales. Ceux qui demandent Google — l'arborescence,
les adresses, les comptes, les groupes, la branche à vider — coûtent
plusieurs appels réseau chacun ; les relancer à chaque changement d'écran
rendrait l'application poussive pour un bénéfice nul.

Ils sont donc **fournis de l'extérieur** quand on les a, et valent `inconnu`
sinon. Le module ne va jamais chercher Google lui-même.

## Trois états, pas deux

`inconnu` n'est pas `à faire`. Une case qui resterait vide parce que
personne n'a regardé mentirait autant qu'une case cochée à tort — et
découragerait pour rien. Chaque état porte donc sa phrase : ce qu'on a
constaté, ou pourquoi on ne sait pas.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field

from sqlalchemy.orm import Session

from backend.models import (
    AnneeScolaire,
    Arbitrage,
    CompteCible,
    LoginReserve,
    Personne,
    Site,
    Snapshot,
    SuiviChromebook,
    TableCorrespondance,
)

FAITE = "faite"
A_FAIRE = "a_faire"
INCONNU = "inconnu"

ETAPES_GOOGLE = ("vider", "arborescence", "adresses", "comptes", "groupes")
"""Celles dont l'état ne se lit que dans Google, et qu'on ne calcule pas ici."""


@dataclass
class EtatEtape:
    id: str
    etat: str
    detail: str
    """Ce qui a été constaté, ou pourquoi on ne sait pas. Jamais vide."""
    source: str = "referentiel"


@dataclass
class RapportAvancement:
    annee_libelle: str = ""
    etapes: list[EtatEtape] = field(default_factory=list)

    @property
    def par_id(self) -> dict[str, EtatEtape]:
        return {e.id: e for e in self.etapes}

    @property
    def nb_faites(self) -> int:
        return sum(1 for e in self.etapes if e.etat == FAITE)

    @property
    def nb_inconnues(self) -> int:
        return sum(1 for e in self.etapes if e.etat == INCONNU)


def _annee_visee(libelle: str) -> str | None:
    """L'année que les unités d'organisation doivent porter.

    Le libellé `2026-2027` décrit l'année scolaire ; l'arbre Google porte
    celle qui la termine — `NDK2027`. C'est la seconde moitié du libellé.
    """
    m = re.fullmatch(r"(\d{4})-(\d{4})", (libelle or "").strip())
    return m.group(2) if m else None


def avancement(
    session: Session,
    *,
    annee_id: int,
    etats_google: dict[str, tuple[str, str]] | None = None,
) -> RapportAvancement:
    """L'état de chaque étape du parcours pour une année.

    Args:
        annee_id: l'année préparée.
        etats_google: `{id_etape: (etat, detail)}` pour les étapes qui se
            constatent dans Google. Absentes, elles valent `inconnu` — le
            module n'appelle jamais Google de lui-même.
    """
    annee = session.query(AnneeScolaire).filter_by(id=annee_id).one_or_none()
    if annee is None:
        raise ValueError(f"Année introuvable : {annee_id}")

    rapport = RapportAvancement(annee_libelle=annee.libelle)
    ajouter = lambda *a, **k: rapport.etapes.append(EtatEtape(*a, **k))  # noqa: E731

    # ------------------------------------------------------------------
    # Préparation — tout se lit dans le référentiel
    # ------------------------------------------------------------------
    sites = session.query(Site).all()
    ajouter(
        "sites",
        FAITE if sites else A_FAIRE,
        f"{len(sites)} site(s) déclaré(s)." if sites else "Aucun site déclaré.",
    )

    lignes = session.query(TableCorrespondance).all()
    sans_groupe = [l for l in lignes if not (l.groupe_google or "").strip()]
    if not lignes:
        ajouter("table", A_FAIRE, "La Table est vide.")
    else:
        ajouter(
            "table",
            FAITE,
            f"{len(lignes)} classes déclarées"
            + (
                f", dont {len(sans_groupe)} sans adresse de groupe."
                if sans_groupe
                else "."
            ),
        )

    nb_personnes = session.query(Personne).count()
    ajouter(
        "amorcage",
        FAITE if nb_personnes else A_FAIRE,
        f"{nb_personnes} personne(s) au référentiel."
        if nb_personnes
        else "Le référentiel est vide.",
    )

    ids_annee = {
        s.personne_id
        for s in session.query(Snapshot.personne_id).filter_by(
            annee_scolaire_id=annee_id
        )
    }
    ajouter(
        "ingestion",
        FAITE if ids_annee else A_FAIRE,
        f"{len(ids_annee)} personne(s) photographiée(s) en {annee.libelle}."
        if ids_annee
        else f"Aucun export Charlemagne ingéré pour {annee.libelle}.",
    )

    en_attente = (
        session.query(Arbitrage).filter(Arbitrage.decision.is_(None)).count()
    )
    ajouter(
        "arbitrage",
        A_FAIRE if en_attente else FAITE,
        f"{en_attente} arbitrage(s) en attente."
        if en_attente
        else "Aucun arbitrage en attente.",
    )

    # ------------------------------------------------------------------
    # Bascule — cinq étapes que le référentiel porte déjà
    # ------------------------------------------------------------------
    cible = _annee_visee(annee.libelle)
    if cible is None:
        ajouter("rotation", INCONNU, f"Libellé d'année inattendu : {annee.libelle!r}.")
    else:
        chemins = [l.ou_definitive or "" for l in lignes if l.ou_definitive]
        a_jour = [c for c in chemins if cible in c]
        if not chemins:
            ajouter("rotation", A_FAIRE, "Aucun chemin d'OU dans la Table.")
        elif len(a_jour) == len(chemins):
            ajouter("rotation", FAITE, f"Les {len(chemins)} chemins visent {cible}.")
        else:
            ajouter(
                "rotation",
                A_FAIRE,
                f"{len(chemins) - len(a_jour)} chemin(s) ne visent pas encore "
                f"{cible}.",
            )

    constats = session.query(LoginReserve).all()
    avec_site = [c for c in constats if c.site]
    if not constats:
        ajouter(
            "controle_koxo",
            A_FAIRE,
            "Aucun export KoXo n'a été passé au contrôle.",
        )
    elif not avec_site:
        ajouter(
            "controle_koxo",
            A_FAIRE,
            f"{len(constats)} identifiants relevés, mais sans leur base : "
            "refais le contrôle en désignant le site.",
        )
    else:
        bases = sorted({c.site for c in avec_site})
        ajouter(
            "controle_koxo",
            FAITE,
            f"{len(avec_site)} identifiants relevés dans : {', '.join(bases)}.",
        )

    # La synchronisation se constate dans ces mêmes constats : si chaque
    # élève de l'année s'y trouve, KoXo les détient tous.
    badges_constates = {c.badge for c in constats if c.badge}
    eleves = [
        p
        for p in session.query(Personne).filter_by(type="eleve").all()
        if p.id in ids_annee
    ]
    manquants = [p for p in eleves if p.badge and p.badge not in badges_constates]
    if not constats or not eleves:
        ajouter(
            "synchro_koxo",
            INCONNU,
            "Se constate en repassant un export KoXo au contrôle, après la "
            "synchronisation.",
        )
    elif manquants:
        ajouter(
            "synchro_koxo",
            A_FAIRE,
            f"{len(manquants)} élève(s) de l'année absents du dernier export "
            "KoXo contrôlé.",
        )
    else:
        ajouter(
            "synchro_koxo",
            FAITE,
            f"Les {len(eleves)} élèves de l'année figurent dans les exports "
            "KoXo contrôlés.",
        )

    # La bascule mémorise l'OU qu'elle a appliquée : nul besoin de Google.
    comptes = {
        c.personne_id: c
        for c in session.query(CompteCible).filter_by(cible="google").all()
    }
    places = [p for p in eleves if comptes.get(p.id) and comptes[p.id].ou_appliquee]
    if not eleves:
        ajouter("bascule", INCONNU, "Aucun élève photographié pour cette année.")
    elif not places:
        ajouter("bascule", A_FAIRE, "Aucun déplacement d'OU appliqué.")
    elif len(places) == len(eleves):
        ajouter(
            "bascule",
            FAITE,
            f"Les {len(eleves)} élèves ont reçu une OU du programme.",
        )
    else:
        ajouter(
            "bascule",
            A_FAIRE,
            f"{len(eleves) - len(places)} élève(s) n'ont pas encore été placés.",
        )

    suivis = session.query(SuiviChromebook).count()
    ajouter(
        "chromebooks",
        FAITE if suivis else INCONNU,
        f"{suivis} machine(s) suivie(s)."
        if suivis
        else "Aucun suivi de flotte enregistré.",
    )

    # ------------------------------------------------------------------
    # Ce qui ne se lit que dans Google
    # ------------------------------------------------------------------
    fournis = etats_google or {}
    for etape in ETAPES_GOOGLE:
        etat, detail = fournis.get(
            etape,
            (INCONNU, "Se constate dans Google — lance le contrôle de l'étape."),
        )
        ajouter(etape, etat, detail, source="google")

    return rapport
