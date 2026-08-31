"""Génération des exports CSV pour KoXo.

KoXo attend un CSV séparateur virgule, encodage cp1252, avec les colonnes :

    Groupe primaire | Groupe secondaire | Titre | Nom | Prénom |
    Identifiant | ID unique | Mot de passe | Date de naissance | Email

Trois catégories d'export par (site, type_personne) :

- **Tous** : l'état complet visé — toutes les Personnes actives sur ce site.
- **Nouveaux** : uniquement les entrants — Personnes présentes à l'année
  cible mais absentes de l'année source. À importer avec KoXo qui générera
  les mots de passe.
- **Anciens** : uniquement les sortants — Personnes présentes à l'année
  source mais absentes de la cible. À supprimer côté KoXo.

## Le mot de passe

**Vide dans tous les exports.** KoXo est l'autorité qui génère les MDP à la
création (§7.1). Notre programme ne les invente pas et ne les régénère
jamais pour les comptes existants.

## Groupe primaire / secondaire

- Élèves : `Elèves` / code classe Charlemagne (`31`, `1_G2`, …)
- Adultes : `Professeurs` / matière enseignée (`MATHEMATIQUES`, …)
"""
from __future__ import annotations

import csv
import io
from dataclasses import dataclass, field
from typing import Literal

from sqlalchemy.orm import Session
from backend.services.rattachement import (
    ids_personnes_du_site,
    ids_presents_annee,
)

from backend.models import Personne, Site, Snapshot

# ---------------------------------------------------------------------------
# Format KoXo
# ---------------------------------------------------------------------------

# Ordre officiel des colonnes (validé sur l'export historique du prédécesseur)
COLONNES_KOXO = [
    "Groupe primaire",
    "Groupe secondaire",
    "Titre",
    "Nom",
    "Prénom",
    "Identifiant",
    "ID unique",
    "Mot de passe",
    "Date de naissance",
    "Email",
]

ENCODAGE_KOXO = "cp1252"

LONGUEUR_MAX_GROUPE = 20
"""Au-delà, KoXo tronque le nom du groupe en lisant le fichier.

La limite ne s'applique qu'à l'import : un groupe créé à la main dans
l'interface porte le nom qu'on veut, et l'export de KoXo le rend entier.
Mais quand la synchronisation relit ce nom depuis un CSV, elle le coupe à
vingt caractères, ne reconnaît plus le groupe existant, en crée un jumeau
tronqué à côté, et y déplace les comptes.

Constaté sur l'instance réelle : trois groupes dépassaient la limite —
`SC. & TECH. MEDICO-SOCIALES`, `BIOCH. GENIE BIOLOGIQUE`, `ENTRETIEN -
MAINTENANCE` — et leurs dix comptes ont été déplacés vers
`SC. & TECH. MEDICO-S`, `BIOCH. GENIE BIOLOGI` et `ENTRETIEN - MAINTENA`.
`DIRECTRICE ADJOINTE`, dix-neuf caractères, n'a pas bougé.

Les remettre à la main ne suffit pas : la synchronisation suivante
retronque et redéplace. Il faut renommer le groupe dans KoXo.
"""

Categorie = Literal["tous", "nouveaux", "anciens"]


@dataclass
class ContexteExport:
    site: Site
    type_personne: str  # "eleve" | "adulte"
    categorie: Categorie
    annee_cible_id: int
    annee_source_id: int | None
    groupe_secondaire_force: str | None = None
    """Groupe secondaire imposé à toutes les lignes. Réservé aux sortants."""

    base_koxo: str | None = None
    """La base KoXo où ce fichier sera chargé, quand ce n'est pas celle du site.

    Les professeurs existent dans **les deux serveurs**, et chacun nomme ses
    groupes à sa façon : `DIRECTEUR` d'un côté, `PHYSIQUE-CHIMIE` de
    l'autre ; `DDFPT` ici, `Mathematiques` là. Le référentiel, lui, ne
    rattache un adulte qu'à un seul site — en pratique tous à NDK, parce
    que l'amorçage a lu cette base en premier.

    Sans ce paramètre, le même fichier servi aux deux serveurs déplaçait
    vingt-quatre comptes sur le second : il portait les groupes constatés
    dans la base de l'autre. On désigne donc la base visée, et les constats
    de celle-là font autorité.
    """

    @property
    def base(self) -> str:
        """La base dont les constats font autorité pour ce fichier."""
        return self.base_koxo or self.site.nom


@dataclass
class RapportExportKoxo:
    site_nom: str
    type_personne: str
    categorie: str
    nb_lignes: int
    nom_fichier_suggere: str
    groupe_secondaire_force: str | None = None
    avertissements: list[str] = field(default_factory=list)
    """Ce qui, dans ce fichier, empêchera la synchronisation de faire son
    travail — un compte sans ID unique ne sera pas reconnu, un groupe
    secondaire vide range le compte nulle part."""

    badges_conserves: list[int] = field(default_factory=list)
    """Les comptes que seule la décision de conserver fait figurer ici.

    Sans cette liste, on ne peut plus distinguer un compte présent de
    plein droit d'un compte reconduit à la main — et l'écran qui propose
    de les relâcher les perdait de vue dès qu'on les cochait."""


# ---------------------------------------------------------------------------
# Point d'entrée
# ---------------------------------------------------------------------------


def generer_csv_koxo(
    session: Session,
    *,
    site_id: int,
    type_personne: str,
    categorie: Categorie,
    annee_cible_id: int,
    annee_source_id: int | None = None,
    groupe_secondaire_force: str | None = None,
    base_koxo: str | None = None,
) -> tuple[bytes, RapportExportKoxo]:
    """Génère un CSV KoXo pour une catégorie donnée.

    Args:
        session: SQLAlchemy session (lecture seule).
        site_id: site cible (NDE/NDK/SU).
        type_personne: `eleve` ou `adulte`.
        categorie: `tous` | `nouveaux` | `anciens`.
        annee_cible_id: année de référence pour "tous" et "nouveaux".
        annee_source_id: année précédente — obligatoire pour "nouveaux" et
            "anciens" (la comparaison ne peut se faire sans référent).
        groupe_secondaire_force: groupe secondaire imposé à toutes les
            lignes. Réservé à `anciens` : il sert à rassembler les sortants
            dans un groupe dédié plutôt que de les laisser porter leur
            dernière classe.
        base_koxo: nom du site dont la base KoXo recevra ce fichier, quand
            ce n'est pas celle du site choisi. Sert à reprendre les groupes
            secondaires que **cette** base détient. Sans effet sur les
            élèves, dont la classe vient toujours de Charlemagne.

    Returns:
        Tuple (contenu CSV en bytes cp1252, rapport typé).

    Raises:
        ValueError: si les paramètres sont incohérents ou années introuvables.
    """
    if type_personne not in ("eleve", "adulte"):
        raise ValueError(f"type_personne invalide : {type_personne!r}")
    if categorie not in ("tous", "nouveaux", "anciens"):
        raise ValueError(f"categorie invalide : {categorie!r}")
    if categorie in ("nouveaux", "anciens") and annee_source_id is None:
        raise ValueError(
            f"annee_source_id requis pour categorie={categorie!r}"
        )
    if groupe_secondaire_force and categorie != "anciens":
        # Sur « tous » ou « nouveaux », forcer le groupe rassemblerait toute
        # une population dans une seule classe. Le paramètre n'a de sens que
        # pour ranger des sortants.
        raise ValueError(
            "groupe_secondaire_force n'est accepté que pour categorie="
            f"'anciens' (reçu {categorie!r})"
        )

    site = session.query(Site).filter_by(id=site_id).one_or_none()
    if site is None:
        raise ValueError(f"Site introuvable : {site_id}")

    ctx = ContexteExport(
        site=site,
        type_personne=type_personne,
        categorie=categorie,
        annee_cible_id=annee_cible_id,
        annee_source_id=annee_source_id,
        groupe_secondaire_force=(groupe_secondaire_force or "").strip() or None,
        base_koxo=(base_koxo or "").strip() or None,
    )

    conserves: list[dict] = []
    if categorie == "tous":
        lignes = _lignes_tous(session, ctx)
        conserves = _lignes_conservees(session, ctx, lignes)
        lignes += conserves
    elif categorie == "nouveaux":
        lignes = _lignes_nouveaux(session, ctx)
    else:
        lignes = _lignes_anciens(session, ctx)

    contenu = _encoder_csv(lignes)
    rapport = RapportExportKoxo(
        site_nom=site.nom,
        type_personne=type_personne,
        categorie=categorie,
        nb_lignes=len(lignes),
        nom_fichier_suggere=_nom_fichier(site.nom, type_personne, categorie),
        groupe_secondaire_force=ctx.groupe_secondaire_force,
        badges_conserves=[
            int(l["ID unique"]) for l in conserves if l["ID unique"].isdigit()
        ],
        avertissements=_relire(lignes, ctx)
        + _adultes_sans_site(session, ctx)
        + _groupes_absents_de_la_base(session, ctx, lignes)
        + _groupes_trop_longs(lignes)
        + _adresses_seulement_calculees(session, ctx, lignes)
        + _comptes_que_la_synchro_desactivera(session, ctx, lignes),
    )
    return contenu, rapport


def _adultes_sans_site(session: Session, ctx: ContexteExport) -> list[str]:
    """Les adultes qu'aucun export ne montrera, faute de rattachement.

    Un adulte est rattaché par `Personne.site_id`, et l'ingestion
    Charlemagne ne le renseigne pas : elle déduit le site de la classe, et
    un adulte n'en a pas. Un professeur arrivé par Charlemagne n'appartient
    donc à aucun site — et disparaît de **tous** les exports sans que rien
    ne le signale.

    Pour un élève, le programme préfère le montrer dans un export imparfait
    plutôt que le faire disparaître de tous. Pour un adulte, on ne peut pas
    en faire autant : on ignore quelle base viser, et les exports
    Charlemagne charrient des lignes de service — « RPP », « CNED », « VIE
    SCOLAIRE » — qu'il ne faut créer nulle part. On les nomme donc, et
    l'arbitrage reste humain.
    """
    if ctx.type_personne != "adulte":
        return []

    orphelins = (
        session.query(Personne)
        .join(Snapshot, Snapshot.personne_id == Personne.id)
        .filter(
            Personne.type == "adulte",
            Personne.site_id.is_(None),
            Snapshot.annee_scolaire_id == ctx.annee_cible_id,
        )
        .distinct()
        .all()
    )
    if not orphelins:
        return []

    qui = ", ".join(f"{p.prenom} {p.nom}" for p in orphelins[:6])
    return [
        f"{len(orphelins)} adulte(s) ne sont rattachés à aucun site et "
        f"n'apparaissent donc dans aucun export — {qui}"
        + (", …" if len(orphelins) > 6 else "")
        + ". Rattache ceux qui doivent avoir un compte."
    ]


def _groupes_absents_de_la_base(
    session: Session, ctx: ContexteExport, lignes: list[dict]
) -> list[str]:
    """Les groupes secondaires que la base visée ne connaît pas encore.

    KoXo crée sans broncher le groupe qu'on lui présente. Un libellé
    Charlemagne qui n'existe pas dans la base y fait donc naître une
    discipline de plus, où l'enseignant se retrouve seul — et sans accès au
    répertoire partagé de ses collègues, rangés sous l'autre nom.

    Le programme ne tranche pas : `MATH. SCIENCES` et `Mathematiques` sont
    peut-être la même chose, et le décider serait deviner. Il nomme.
    """
    if ctx.type_personne != "adulte":
        return []

    from backend.models import LoginReserve

    connus = {
        _sans_casse_ni_accents(c.groupe_secondaire)
        for c in session.query(LoginReserve).filter_by(site=ctx.base).all()
        if (c.groupe_secondaire or "").strip()
    }
    if not connus:
        return [
            f"La base {ctx.base} n'a jamais été passée au Contrôle KoXo : le "
            "programme ignore quels groupes secondaires elle porte, et ne "
            "peut donc ni les préserver ni signaler ceux qu'elle créerait."
        ]

    inconnus: dict[str, list[str]] = {}
    for l in lignes:
        groupe = (l.get("Groupe secondaire") or "").strip()
        if not groupe or _sans_casse_ni_accents(groupe) in connus:
            continue
        inconnus.setdefault(groupe, []).append(
            f"{l.get('Prénom', '')} {l.get('Nom', '')}".strip()
        )
    if not inconnus:
        return []

    details = "; ".join(
        f"{groupe} ({', '.join(gens[:3])}{', …' if len(gens) > 3 else ''})"
        for groupe, gens in sorted(inconnus.items())
    )
    return [
        f"{len(inconnus)} groupe(s) secondaire(s) absents de la base "
        f"{ctx.base} — {details}. KoXo les créera : vérifie qu'ils ne font "
        "pas double emploi avec un groupe existant."
    ]


def _groupes_trop_longs(lignes: list[dict]) -> list[str]:
    """Prévient des groupes que KoXo coupera en lisant le fichier.

    Le déplacement est silencieux et se répète : chaque synchronisation
    recrée le jumeau tronqué et y ramène les comptes. Remettre les gens à
    la main ne tient donc pas — il faut renommer le groupe dans KoXo.

    Le message donne le nom raccourci tel que KoXo le fabriquera, pour
    qu'on reconnaisse le groupe parasite s'il existe déjà.
    """
    par_groupe: dict[str, int] = {}
    for l in lignes:
        g = (l.get("Groupe secondaire") or "").strip()
        if len(g) > LONGUEUR_MAX_GROUPE:
            par_groupe[g] = par_groupe.get(g, 0) + 1
    if not par_groupe:
        return []

    detail = " ; ".join(
        f"« {g} » → « {g[:LONGUEUR_MAX_GROUPE]} » ({n} compte{'s' if n > 1 else ''})"
        for g, n in sorted(par_groupe.items(), key=lambda x: -len(x[0]))
    )
    total = sum(par_groupe.values())
    return [
        f"{len(par_groupe)} groupe(s) dépassent {LONGUEUR_MAX_GROUPE} caractères : "
        f"KoXo les tronquera en lisant ce fichier, créera un groupe jumeau et y "
        f"déplacera {total} compte(s) — {detail}. Renomme-les dans KoXo avant de "
        "synchroniser : les remettre à la main ne tient pas, la synchronisation "
        "suivante recommence."
    ]


def _adresses_seulement_calculees(
    session: Session, ctx: ContexteExport, lignes: list[dict]
) -> list[str]:
    """Prévient quand le fichier écrira des adresses que rien n'a vérifiées.

    La synchronisation écrit la colonne Email dans la base. Une adresse
    calculée est une hypothèse : `prenom.nom@domaine`, sans savoir comment
    la maison traite les particules ni les noms d'usage. Sur l'instance
    réelle, l'export des professeurs allait en réécrire trente-huit, dont
    trente-trois que Google contredisait — `isabelle.leduff@` remplacée
    par `isabelle.le.duff@`, qui n'existe pas.

    Un entrant n'a pas encore de compte : son adresse ne peut être que
    calculée, et c'est normal. Le message ne compte donc que les lignes qui
    **écrasent** quelque chose : une adresse constatée existe dans la base,
    et le fichier en porte une autre.
    """
    if ctx.type_personne != "adulte":
        return []

    from backend.models import LoginReserve

    constats = {
        c.badge: (c.email or "").strip()
        for c in session.query(LoginReserve)
        .filter(LoginReserve.site == ctx.base, LoginReserve.badge.isnot(None))
        .all()
        if (c.email or "").strip()
    }
    if not constats:
        return []

    ecrases = [
        l
        for l in lignes
        if (l.get("ID unique") or "").isdigit()
        and int(l["ID unique"]) in constats
        and (l.get("Email") or "").strip().lower()
        != constats[int(l["ID unique"])].lower()
    ]
    if not ecrases:
        return []

    qui = ", ".join(f"{l['Prénom']} {l['Nom']}" for l in ecrases[:4])
    return [
        f"{len(ecrases)} adresse(s) remplaceront celle que la base détient — "
        f"{qui}" + (", …" if len(ecrases) > 4 else "") + ". Passe par "
        "Conformité → Adresses pour les vérifier dans Google avant de "
        "synchroniser."
    ]


def _comptes_que_la_synchro_desactivera(
    session: Session, ctx: ContexteExport, lignes: list[dict]
) -> list[str]:
    """Annonce, en les nommant, les comptes que la synchronisation désactivera.

    KoXo donne ce nombre au moment de lancer l'opération, sans les noms :
    « Désactiver 7 ». Sept qui ? Il fallait exporter la base et comparer
    les fichiers à la main pour l'apprendre. Sur l'instance réelle, la
    liste contenait un remplaçant attendu pour la rentrée.

    Le fichier ne pouvant pas mentir sur ce point — il vaut état complet —
    autant le dire ici, où la décision se prend encore.
    """
    if ctx.categorie != "tous":
        return []

    from backend.models import LoginReserve

    presents = {
        int(l["ID unique"]) for l in lignes if (l.get("ID unique") or "").isdigit()
    }
    groupe = "Elèves" if ctx.type_personne == "eleve" else "Professeurs"
    manquants = []
    vus: set[int] = set()
    for c in (
        session.query(LoginReserve)
        .filter(LoginReserve.site == ctx.base, LoginReserve.badge.isnot(None))
        .order_by(LoginReserve.date_constat.desc())
        .all()
    ):
        if c.badge in vus or c.badge in presents:
            continue
        vus.add(c.badge)
        gp = (c.groupe_primaire or "").strip().lower()
        if gp and gp != groupe.lower():
            continue
        if not gp:
            p = session.query(Personne).filter_by(badge=c.badge).one_or_none()
            if p is None or p.type != ctx.type_personne:
                continue
        manquants.append(c)

    if not manquants:
        return []

    qui = ", ".join(
        f"{(c.prenom or '').strip()} {(c.nom or '').strip()}".strip() or c.login
        for c in manquants[:8]
    )
    return [
        f"La synchronisation désactivera {len(manquants)} compte(s) de la base "
        f"{ctx.base} : {qui}" + (", …" if len(manquants) > 8 else "") + ". "
        "Décoche ceux à garder dans « Comptes menacés » avant d'exporter."
    ]


def _relire(lignes: list[dict], ctx: ContexteExport) -> list[str]:
    """Ce que ce fichier fera mal, dit avant de l'importer.

    La synchronisation reconnaît un compte par son ID unique. Une ligne qui
    n'en porte pas ne sera pas reconnue : elle créera un doublon, ou en mode
    destructif fera disparaître le compte existant. Mieux vaut l'apprendre
    ici qu'après.
    """
    avertissements = []

    sans_id = [l for l in lignes if not (l.get("ID unique") or "").strip()]
    if sans_id:
        qui = ", ".join(f"{l['Prénom']} {l['Nom']}" for l in sans_id[:5])
        avertissements.append(
            f"{len(sans_id)} ligne(s) sans ID unique — {qui}"
            + (", …" if len(sans_id) > 5 else "")
            + ". La synchronisation ne les reconnaîtra pas."
        )

    sans_login = [l for l in lignes if not (l.get("Identifiant") or "").strip()]
    if sans_login:
        avertissements.append(
            f"{len(sans_login)} ligne(s) sans identifiant. KoXo en générera "
            "un : vérifie qu'il ne s'agit pas de comptes qui en ont déjà un."
        )

    sans_groupe = [l for l in lignes if not (l.get("Groupe secondaire") or "").strip()]
    if sans_groupe:
        qui = ", ".join(f"{l['Prénom']} {l['Nom']}" for l in sans_groupe[:5])
        avertissements.append(
            f"{len(sans_groupe)} ligne(s) sans groupe secondaire — {qui}"
            + (", …" if len(sans_groupe) > 5 else "")
            + ". Ces comptes ne seront rangés dans aucune classe."
        )

    if ctx.groupe_secondaire_force:
        avertissements.append(
            f"Les {len(lignes)} sortants porteront le groupe secondaire "
            f"« {ctx.groupe_secondaire_force} » au lieu de leur dernière "
            "classe. Synchronise ce fichier en mode NON destructif : le mode "
            "destructif supprime tout ce qui n'y figure pas."
        )

    return avertissements


# ---------------------------------------------------------------------------
# Récupération des lignes selon la catégorie
# ---------------------------------------------------------------------------


def _ids_detenus_par_la_base(session: Session, ctx: ContexteExport) -> set[int]:
    """Les adultes que cette base KoXo détient déjà, et qui enseignent encore.

    ## Le rattachement d'un adulte ne dit pas où il travaille

    Le référentiel rattache chaque personne à **un** site. Pour un élève
    c'est une vérité : il est inscrit quelque part. Pour un adulte, c'est un
    artefact — l'amorçage a lu la base de NDK en premier, et les 195 adultes
    y ont été rattachés. Aucun n'est rattaché à SU.

    Et Charlemagne ne tranche pas : sur l'instance réelle, les 214
    photographies d'adultes de l'année portent un **code établissement
    vide**. Rien, nulle part, ne dit qui enseigne à SU.

    ## Ce que ça coûtait

    L'export visant SU ne contenait donc presque aucun adulte, quand la
    base SU en détient 176. Un export « tous » valant état complet, la
    synchronisation proposait d'en désactiver 176 — dont 173 professeurs
    en exercice, beaucoup enseignant sur les deux sites.

    ## La règle

    La seule source qui sache qui travaille à SU est **la base de SU**.
    Un compte qu'elle détient, dont la personne figure encore chez
    Charlemagne cette année, est reconduit : il n'y a aucune raison de le
    fermer.

    Celui dont la personne a disparu de Charlemagne n'est pas reconduit
    pour autant — c'est un départ possible, et il revient à l'écran des
    comptes menacés, qui le nomme et laisse décider.

    Ne concerne que les adultes. Un élève appartient réellement à son
    site : le reconduire dans la base qu'il a quittée l'y maintiendrait
    alors qu'il a changé d'établissement.
    """
    if ctx.type_personne != "adulte":
        return set()

    from backend.models import LoginReserve

    badges = {
        c.badge
        for c in session.query(LoginReserve)
        .filter(LoginReserve.site == ctx.base, LoginReserve.badge.isnot(None))
        .all()
        if not (c.groupe_primaire or "").strip()
        or (c.groupe_primaire or "").strip().lower() == "professeurs"
    }
    if not badges:
        return set()

    return {
        pid
        for (pid,) in session.query(Personne.id)
        .filter(Personne.badge.in_(badges), Personne.type == "adulte")
        .all()
    }


def _lignes_tous(session: Session, ctx: ContexteExport) -> list[dict]:
    """État complet visé : toutes les Personnes du site+type ayant un snapshot
    dans l'année cible — plus, pour les adultes, celles que la base détient
    déjà."""
    ids = set(
        ids_personnes_du_site(
            session, site_id=ctx.site.id,
            annee_id=ctx.annee_cible_id, type_personne=ctx.type_personne,
        )
    )
    ids |= _ids_detenus_par_la_base(session, ctx)

    q = (
        session.query(Personne, Snapshot)
        .join(Snapshot, Snapshot.personne_id == Personne.id)
        .filter(
            Personne.id.in_(ids),
            Personne.type == ctx.type_personne,
            Snapshot.annee_scolaire_id == ctx.annee_cible_id,
        )
        .order_by(Personne.nom, Personne.prenom)
    )
    # Une personne peut avoir plusieurs snapshots dans une même année (multi-
    # ingestion) — on ne retient que le plus récent.
    par_personne: dict[int, Snapshot] = {}
    personnes_index: dict[int, Personne] = {}
    for p, s in q.all():
        precedent = par_personne.get(p.id)
        if precedent is None or s.date_ingestion > precedent.date_ingestion:
            par_personne[p.id] = s
            personnes_index[p.id] = p
    return [
        _formatter_ligne(
            session, personnes_index[pid], par_personne[pid], ctx.type_personne, ctx.base
        )
        for pid in par_personne
    ]


def _lignes_conservees(
    session: Session, ctx: ContexteExport, deja: list[dict]
) -> list[dict]:
    """Les comptes qu'on a décidé de garder, reconduits tels que la base les tient.

    Un export « tous » vaut état complet : la synchronisation désactive
    tout compte du groupe primaire qui n'y figure pas. Pour un sortant
    c'est le but ; pour un remplaçant que Charlemagne ne porte pas encore,
    c'est une porte fermée un matin de rentrée.

    La ligne est recopiée du constat — identifiant, groupe secondaire,
    adresse — et non recalculée : on ne veut rien changer à ce compte,
    seulement le montrer à la synchronisation pour qu'elle le laisse
    tranquille.

    Seul `tous` est concerné. `nouveaux` et `anciens` sont des fichiers
    partiels, qui ne servent jamais d'état complet : y ajouter des
    conservés n'aurait aucun sens.
    """
    from backend.models import LoginReserve

    groupe_primaire = "Elèves" if ctx.type_personne == "eleve" else "Professeurs"
    presents = {
        l["ID unique"] for l in deja if (l.get("ID unique") or "").strip()
    }

    constats = (
        session.query(LoginReserve)
        .filter(
            LoginReserve.site == ctx.base,
            LoginReserve.conserver.is_(True),
            LoginReserve.badge.isnot(None),
        )
        .order_by(LoginReserve.date_constat.desc())
        .all()
    )

    lignes: list[dict] = []
    vus: set[int] = set()
    for c in constats:
        if c.badge in vus or str(c.badge) in presents:
            continue
        vus.add(c.badge)

        personne = (
            session.query(Personne).filter_by(badge=c.badge).one_or_none()
        )

        # Un export porte une population, et une seule. Sans ce tri, un
        # élève conservé dans cette base se serait retrouvé dans le fichier
        # des professeurs, sous le groupe primaire `Professeurs` — la
        # synchronisation l'aurait déplacé hors des élèves.
        gp = (c.groupe_primaire or "").strip().lower()
        if gp:
            if gp != groupe_primaire.lower():
                continue
        elif personne is None or personne.type != ctx.type_personne:
            continue
        email = (c.email or "").strip()
        if not email and personne is not None:
            email = personne.email or ""

        lignes.append(
            {
                "Groupe primaire": groupe_primaire,
                "Groupe secondaire": (c.groupe_secondaire or "").strip(),
                "Titre": "",
                "Nom": (c.nom or (personne.nom if personne else "")) or "",
                "Prénom": (c.prenom or (personne.prenom if personne else "")) or "",
                "Identifiant": c.login or "",
                "ID unique": str(c.badge),
                "Mot de passe": "",
                "Date de naissance": "",
                "Email": email,
            }
        )
    return lignes


def _lignes_nouveaux(session: Session, ctx: ContexteExport) -> list[dict]:
    """Nouveaux entrants : présents à annee_cible, absents à annee_source."""
    # Entrée dans l'établissement, pas dans le site : l'année source est
    # comparée tous sites confondus. Sinon une élève montant de SU à NDK
    # passerait pour une nouvelle, et l'on tenterait de créer un compte
    # Google qu'elle possède déjà.
    ids_source = ids_presents_annee(
        session, annee_id=ctx.annee_source_id, type_personne=ctx.type_personne
    )
    snapshots_cible = _snapshots_annee_par_personne(session, ctx.annee_cible_id, ctx)

    ids_nouveaux = set(snapshots_cible) - ids_source
    personnes = _charger_personnes(session, ids_nouveaux)
    return [
        _formatter_ligne(
            session, personnes[pid], snapshots_cible[pid], ctx.type_personne, ctx.base
        )
        for pid in ids_nouveaux
        if pid in personnes
    ]


def _lignes_anciens(session: Session, ctx: ContexteExport) -> list[dict]:
    """Sortants : présents à annee_source, absents à annee_cible."""
    snapshots_source = _snapshots_annee_par_personne(session, ctx.annee_source_id, ctx)
    # Départ de l'établissement, pas du site : l'année cible est comparée
    # tous sites confondus. Sinon la même élève passerait pour une
    # sortante de SU, et son compte serait suspendu le jour de sa rentrée.
    ids_cible = ids_presents_annee(
        session, annee_id=ctx.annee_cible_id, type_personne=ctx.type_personne
    )

    ids_anciens = set(snapshots_source) - ids_cible
    personnes = _charger_personnes(session, ids_anciens)
    lignes = [
        _formatter_ligne(
            session, personnes[pid], snapshots_source[pid], ctx.type_personne, ctx.base
        )
        for pid in ids_anciens
        if pid in personnes
    ]

    # Sans destination forcée, la ligne d'un sortant porte sa **dernière
    # classe** — c'est le seul groupe que le référentiel lui connaisse.
    # Synchronisé tel quel, KoXo le remettrait dans cette classe, au milieu
    # de la promotion suivante. Le rassembler dans un groupe dédié est ce
    # que recommande la documentation KoXo pour la bascule annuelle : les
    # comptes restent, identifiables, et la suppression devient un geste
    # distinct et daté.
    if ctx.groupe_secondaire_force:
        for ligne in lignes:
            ligne["Groupe secondaire"] = ctx.groupe_secondaire_force
    return lignes


# ---------------------------------------------------------------------------
# Helpers de requête
# ---------------------------------------------------------------------------


def _ids_personnes_annee(session: Session, annee_id: int, ctx: ContexteExport) -> set[int]:
    q = (
        session.query(Snapshot.personne_id)
        .join(Personne, Snapshot.personne_id == Personne.id)
        .filter(
            Snapshot.annee_scolaire_id == annee_id,
            Personne.id.in_(
                ids_personnes_du_site(
                    session, site_id=ctx.site.id,
                    annee_id=annee_id, type_personne=ctx.type_personne,
                )
            ),
            Personne.type == ctx.type_personne,
        )
    )
    return {row[0] for row in q.all()}


def _snapshots_annee_par_personne(
    session: Session, annee_id: int, ctx: ContexteExport
) -> dict[int, Snapshot]:
    q = (
        session.query(Snapshot)
        .join(Personne, Snapshot.personne_id == Personne.id)
        .filter(
            Snapshot.annee_scolaire_id == annee_id,
            Personne.id.in_(
                ids_personnes_du_site(
                    session, site_id=ctx.site.id,
                    annee_id=annee_id, type_personne=ctx.type_personne,
                )
            ),
            Personne.type == ctx.type_personne,
        )
        .order_by(Snapshot.personne_id, Snapshot.date_ingestion.desc())
    )
    derniers: dict[int, Snapshot] = {}
    for s in q.all():
        if s.personne_id not in derniers:
            derniers[s.personne_id] = s
    return derniers


def _charger_personnes(session: Session, ids: set[int]) -> dict[int, Personne]:
    if not ids:
        return {}
    q = session.query(Personne).filter(Personne.id.in_(ids))
    return {p.id: p for p in q.all()}


# ---------------------------------------------------------------------------
# Formatage d'une ligne KoXo
# ---------------------------------------------------------------------------


def _login_pour(session: Session, personne: Personne, site: str | None) -> str:
    """L'identifiant à écrire : celui que la base détient, s'il est connu.

    `Personne.login` est unique dans tout le référentiel. Les identifiants,
    eux, vivent dans des espaces séparés : l'établissement tient une base
    KoXo par population — profs, élèves NDK, élèves SU. `ccueff` y désigne
    légitimement un adulte dans l'une et une élève dans l'autre.

    Le référentiel n'en garde qu'un et suffixe les autres. Écrire ce
    suffixe dans l'export présenterait à KoXo un identifiant qu'il ne
    connaît pas : reconnaissant le compte par son ID unique, il pourrait le
    **renommer**. Sur l'instance réelle, 28 lignes de l'export SU étaient
    dans ce cas.

    Un identifiant constaté fait autorité — c'est la règle du programme —
    **mais seulement dans sa propre base**. Une première version reprenait
    le constat sans regarder d'où il venait : Lou-Ann BERNARD, qui tient
    `lbernard` dans la base de SU, monte au lycée et l'emportait dans
    l'export de NDK, où `lbernard` appartient à Liam BERNARD. L'annuaire a
    refusé la création — sept élèves, tous des montants de 3e en 2nde.

    Hors de sa base, on garde donc l'identifiant du référentiel : unique,
    et de ce fait libre partout.
    """
    from backend.models import LoginReserve

    if personne.badge is None:
        return personne.login or ""
    if not site:
        return personne.login or ""
    constat = (
        session.query(LoginReserve)
        .filter_by(badge=personne.badge, site=site)
        .order_by(LoginReserve.date_constat.desc())
        .first()
    )
    if constat is not None and constat.login:
        return constat.login
    return personne.login or ""


def _groupe_pour(
    session: Session,
    personne: Personne,
    snapshot: Snapshot,
    type_personne: str,
    site: str | None,
) -> str:
    """Le groupe secondaire à écrire : celui que la base tient, pour un adulte.

    Les deux populations n'obéissent pas à la même règle, et les confondre
    casse l'une ou l'autre.

    Pour un **élève**, le groupe secondaire est sa classe. Elle change
    chaque année, c'est tout l'objet de la rentrée, et elle vient de
    Charlemagne. Rien à préserver.

    Pour un **adulte**, c'est sa matière ou son service — une organisation
    tenue à la main dans KoXo, que Charlemagne ne décrit pas fidèlement.
    Trois directrices adjointes y sont rangées sous leur fonction bien
    qu'elles enseignent aussi ; un directeur sous « DIRECTEUR » plutôt que
    sous « PHYSIQUE-CHIMIE » ; le personnel administratif sous un unique
    « ADMINISTRATIF » là où Charlemagne détaille sept postes.

    Écrire la matière par-dessus déplaçait vingt-trois comptes qui
    n'avaient aucune raison de bouger — et un enseignant ne change pas de
    matière d'une année sur l'autre. Le groupe secondaire commande
    l'accès au répertoire partagé de la discipline : le déplacer sans
    raison coûte un accès.

    Un compte qui n'existe pas encore n'a rien à préserver : il prend sa
    matière Charlemagne, et c'est bien ce qu'on veut pour un entrant.

    Comme pour l'identifiant, **le constat ne vaut que dans sa propre
    base** : il faut donc avoir passé l'export de cette base au contrôle,
    site désigné, pour que le programme sache ce qu'elle détient.
    """
    if type_personne == "eleve":
        return snapshot.classe or ""

    charlemagne = (snapshot.matieres or snapshot.poste_occupe or "").split(";")[0].strip()

    if personne.badge is None or not site:
        return charlemagne

    from backend.models import LoginReserve

    constat = (
        session.query(LoginReserve)
        .filter_by(badge=personne.badge, site=site)
        .order_by(LoginReserve.date_constat.desc())
        .first()
    )
    if constat is not None and (constat.groupe_secondaire or "").strip():
        return constat.groupe_secondaire.strip()

    # Compte à créer : aucun constat à préserver, la matière vient de
    # Charlemagne. Reste qu'elle peut ne pas s'écrire comme le groupe que la
    # base porte déjà — `MATHEMATIQUES` contre `Mathematiques`. Écrire la
    # graphie de Charlemagne ferait naître un second groupe à côté du
    # premier, et le professeur atterrirait seul dans une discipline où ses
    # collègues sont ailleurs.
    return _graphie_de_la_base(session, site, charlemagne)


def _graphie_de_la_base(session: Session, site: str, matiere: str) -> str:
    """La façon dont cette base écrit ce groupe, si elle le connaît.

    Le rapprochement ignore la casse et les accents, et rien d'autre : deux
    libellés qui ne diffèrent que par là désignent le même groupe, KoXo
    lui-même les confondant. Au-delà, on ne devine pas — `MATH. SCIENCES` et
    `Mathematiques` sont peut-être la même discipline, mais c'est une
    décision humaine, pas une déduction.
    """
    if not matiere:
        return matiere

    from backend.models import LoginReserve

    connus = {
        (c.groupe_secondaire or "").strip()
        for c in session.query(LoginReserve).filter_by(site=site).all()
        if (c.groupe_secondaire or "").strip()
    }
    cible = _sans_casse_ni_accents(matiere)
    for connu in sorted(connus):
        if _sans_casse_ni_accents(connu) == cible:
            return connu
    return matiere


def _sans_casse_ni_accents(t: str) -> str:
    import unicodedata

    t = unicodedata.normalize("NFD", (t or "").strip().upper())
    return "".join(c for c in t if not unicodedata.combining(c))


def _email_pour(
    session: Session, personne: Personne, site: str | None
) -> str:
    """L'adresse à écrire : un constat plutôt qu'une hypothèse.

    Trois sources, dans cet ordre :

    1. **l'adresse constatée dans Google** — vérifiée, elle fait foi ;
    2. **l'adresse que la base KoXo détient** — un constat, lui aussi ;
    3. **l'adresse calculée** — `prenom.nom@domaine`, une hypothèse.

    L'ordre importe parce que la synchronisation écrit ce fichier dans la
    base. Passer la troisième devant la deuxième remplaçait des adresses
    réelles par des adresses inventées : sur l'instance réelle, l'export
    des professeurs en réécrivait trente-huit, et Google a donné tort au
    calcul trente-trois fois. `isabelle.leduff@` devenait
    `isabelle.le.duff@`, qui n'existe pas.

    La règle des particules ne se déduit pas. `Le Duff` s'écrit `leduff`
    chez l'un et `le.duff` chez l'autre, selon l'année d'ouverture du
    compte ; `Jacqueline BLANC-COQUAND` répond à `jbc@`. Aucune règle ne
    retrouve ça, et il n'y a rien à retrouver puisque la base le sait.

    Le calcul garde sa place — un entrant n'a ni compte Google ni compte
    KoXo, et il faut bien lui proposer une adresse.
    """
    if personne.email_constate:
        return personne.email_constate

    if personne.badge is not None and site:
        from backend.models import LoginReserve

        constat = (
            session.query(LoginReserve)
            .filter_by(badge=personne.badge, site=site)
            .order_by(LoginReserve.date_constat.desc())
            .first()
        )
        if constat is not None and (constat.email or "").strip():
            return constat.email.strip()

    return personne.email or ""


def _formatter_ligne(
    session: Session,
    personne: Personne,
    snapshot: Snapshot,
    type_personne: str,
    site: str | None = None,
) -> dict:
    """Construit une ligne au format KoXo. Le MDP est TOUJOURS vide (KoXo génère)."""
    groupe_primaire = "Elèves" if type_personne == "eleve" else "Professeurs"
    groupe_secondaire = _groupe_pour(
        session, personne, snapshot, type_personne, site
    )

    email = _email_pour(session, personne, site)

    return {
        "Groupe primaire": groupe_primaire,
        "Groupe secondaire": groupe_secondaire,
        "Titre": "",
        "Nom": personne.nom or "",
        "Prénom": personne.prenom or "",
        "Identifiant": _login_pour(session, personne, site),
        "ID unique": str(personne.badge) if personne.badge else "",
        "Mot de passe": "",  # KoXo génère
        "Date de naissance": "",
        "Email": email,
    }


# ---------------------------------------------------------------------------
# Sortie
# ---------------------------------------------------------------------------


def _encoder_csv(lignes: list[dict]) -> bytes:
    """Encode en cp1252 (attendu par KoXo côté Windows)."""
    buf = io.StringIO(newline="")
    writer = csv.DictWriter(buf, fieldnames=COLONNES_KOXO, quoting=csv.QUOTE_MINIMAL)
    writer.writeheader()
    for l in lignes:
        writer.writerow(l)
    return buf.getvalue().encode(ENCODAGE_KOXO, errors="replace")


def _nom_fichier(site_nom: str, type_personne: str, categorie: str) -> str:
    """`KoXo_NDK_eleves_nouveaux.csv` etc."""
    pop = "eleves" if type_personne == "eleve" else "adultes"
    return f"KoXo_{site_nom}_{pop}_{categorie}.csv"
