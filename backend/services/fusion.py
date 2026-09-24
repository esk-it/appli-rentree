"""Deux fiches, une seule personne : les réunir.

## Le problème

L'identité d'une personne est sa fiche Charlemagne — `E<id>` pour un
élève. Une nouvelle fiche fait une nouvelle personne, sans discussion :
c'est ce qui rend le référentiel sûr. Mais l'établissement tient deux bases
Charlemagne, NDE d'un côté, NDK et SU de l'autre, et un élève qui passe de
NDE à NDK y reçoit une seconde fiche.

Sur la base réelle, en septembre 2026, vingt-neuf adresses étaient
« visées par plusieurs personnes ». L'écran qui les départageait n'offrait
qu'une issue : une adresse suffixée pour la seconde. Aaron SAILLOUR, en 4J
à NDE l'an dernier, en 3e prépa-métiers à NDK cette année, se voyait donc
proposer `aaron.saillour2@` — un second compte pour un élève qui a déjà le
sien. Les vingt-neuf étaient dans ce cas : vingt-huit venus de NDE, et Maël
PRONOST, réinscrit à NDK sous un nouveau numéro. Pas un homonyme.

Le doublon ne gênait pas que l'adresse. L'ancienne fiche de Maël portait
une sortie prévue : son compte, toujours en service, était promis au
dossier des comptes à supprimer.

## Ce que fait la fusion

La fiche **inscrite l'année la plus récente** reste : c'est celle que
Charlemagne continue d'exporter, et celle dont KoXo porte le badge.
L'autre lui est rattachée :

- ses années rejoignent le parcours de la fiche gardée — sauf une année
  où la fiche gardée a déjà sa classe : celle-là fait foi ;
- ce qui manque à la fiche gardée — l'adresse du compte Google, surtout —
  est repris de l'ancienne : le compte suit la personne ;
- ses comptes suivis passent à la fiche gardée quand elle n'en a pas pour
  la même cible. Une **sortie** prévue pour l'ancienne fiche n'est jamais
  reprise sur une personne inscrite cette année : elle est toujours là ;
- son numéro, son badge et son identifiant restent dans `FicheFusionnee` :
  l'ingestion reconnaît l'ancien numéro, et l'identifiant reste pris.

Rien n'est touché dans Google ni dans KoXo.

## Qui choisit la fiche gardée

Le programme, et pas l'appelant. Garder l'ancienne ferait décrire la
personne par une fiche que plus aucun export ne porte, pendant que la
fiche vivante deviendrait un « ancien numéro » dont l'ingestion
n'écouterait plus que l'historique. La règle ne se discute pas, donc elle
ne se demande pas.

## Ce qu'elle refuse

Une fiche avec elle-même, et un élève avec un adulte : leurs numérotations
Charlemagne sont indépendantes. Deux fiches inscrites toutes les deux
cette année se réunissent, mais avec un avertissement : c'est la situation
de deux homonymes, et la réinscription sous un nouveau numéro n'en est
qu'un cas rare.
"""
from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field
from datetime import datetime

from sqlalchemy.orm import Session

from backend.models import (
    AnneeScolaire,
    CompteCible,
    FicheFusionnee,
    LigneEnvoi,
    Personne,
    SecretConserve,
    Site,
    Snapshot,
    TableCorrespondance,
    VerdictCoherence,
)

ETATS_DE_SORTIE = ("quarantaine", "purge")
"""Un compte suivi dans l'un de ces états est promis au départ."""

NOMS_CIBLES = {
    "google": "Google",
    "koxo_ndk": "KoXo NDK",
    "koxo_su": "KoXo SU",
    "pmb_ndk": "PMB NDK",
    "pmb_su": "PMB SU",
    "jpm": "JPM",
    "cardstudio": "CardStudio",
}

CHAMPS_REPRIS = (
    ("ine", "l'INE"),
    ("date_naissance", "la date de naissance"),
    ("email_constate", "l'adresse du compte Google"),
    ("google_user_id", "l'identifiant interne du compte Google"),
    ("email_professionnel", "l'adresse professionnelle"),
    ("email_personnel", "l'adresse personnelle"),
    ("civilite", "la civilité"),
    ("poste_occupe", "le poste"),
    ("matieres", "les matières"),
    ("classes_prof_principal", "les classes de professeur principal"),
)
"""Ce que la fiche gardée reprend de l'ancienne quand elle ne l'a pas.

Ni la classe, ni le site, ni la photo : ils décrivent l'inscription, et
c'est celle de la fiche gardée qui est vraie aujourd'hui. Ni la date
d'entrée : entrer à NDE n'est pas entrer à NDK.
"""


class FusionImpossible(ValueError):
    """La fusion demandée n'a pas de sens."""


@dataclass
class AnneeVecue:
    annee: str
    classe: str | None
    site: str | None


@dataclass
class FicheResumee:
    personne_id: int
    cle_pivot: str
    nom: str
    prenom: str
    login: str
    badge: int
    site: str | None
    classe: str | None
    email_constate: str | None
    annees: list[AnneeVecue] = field(default_factory=list)
    """De la plus récente à la plus ancienne."""


@dataclass
class RapportFusion:
    mode: str
    garde: FicheResumee
    absorbee: FicheResumee
    motif_du_choix: str
    annees_rattachees: list[str] = field(default_factory=list)
    annees_ecartees: list[str] = field(default_factory=list)
    repris: list[str] = field(default_factory=list)
    abandonnes: list[str] = field(default_factory=list)
    avertissements: list[str] = field(default_factory=list)


# ---------------------------------------------------------------------------
# Lecture
# ---------------------------------------------------------------------------


def personne_par_cle(
    session: Session, type_personne: str, id_charlemagne: int
) -> tuple[Personne | None, bool]:
    """La personne qu'un numéro Charlemagne désigne, et par quel chemin.

    Renvoie `(personne, par_ancienne_fiche)`. Le second vaut vrai quand le
    numéro est celui d'une fiche réunie à une autre : il reconnaît la
    personne, mais ne la décrit plus — l'appelant ne doit pas s'en servir
    pour réécrire sa classe ou son site.
    """
    p = (
        session.query(Personne)
        .filter_by(type=type_personne, id_charlemagne=id_charlemagne)
        .one_or_none()
    )
    if p is not None:
        return p, False
    f = (
        session.query(FicheFusionnee)
        .filter_by(type=type_personne, id_charlemagne=id_charlemagne)
        .one_or_none()
    )
    if f is None:
        return None, False
    return session.get(Personne, f.personne_id), True


def annee_la_plus_recente(session: Session) -> AnneeScolaire | None:
    annees = session.query(AnneeScolaire).all()
    return max(annees, key=lambda a: a.libelle) if annees else None


def annees_vecues(
    session: Session, personne_ids: list[int]
) -> dict[int, list[AnneeVecue]]:
    """Par personne, une ligne par année : la dernière classe constatée.

    Le site se déduit de la classe par la table de correspondance — un
    snapshot n'en garde pas. Un code de classe que deux sites partageraient
    ne désigne aucun site plutôt que le mauvais.
    """
    if not personne_ids:
        return {}
    libelles = {a.id: a.libelle for a in session.query(AnneeScolaire).all()}
    noms_sites = {s.id: s.nom for s in session.query(Site).all()}
    site_de_classe: dict[str, str | None] = {}
    for t in session.query(TableCorrespondance).all():
        nom = noms_sites.get(t.site_id)
        deja = site_de_classe.get(t.classe_code_court, nom)
        site_de_classe[t.classe_code_court] = nom if deja == nom else None

    derniere: dict[int, dict[int, str | None]] = {}
    for s in (
        session.query(Snapshot)
        .filter(Snapshot.personne_id.in_(personne_ids))
        .order_by(Snapshot.date_ingestion, Snapshot.id)
    ):
        derniere.setdefault(s.personne_id, {})[s.annee_scolaire_id] = s.classe

    return {
        pid: sorted(
            (
                AnneeVecue(
                    annee=libelles.get(aid, "?"),
                    classe=classe,
                    site=site_de_classe.get(classe) if classe else None,
                )
                for aid, classe in par_annee.items()
            ),
            key=lambda x: x.annee,
            reverse=True,
        )
        for pid, par_annee in derniere.items()
    }


def choisir_garde(
    session: Session, a: Personne, b: Personne
) -> tuple[Personne, Personne, str]:
    """`(gardée, absorbée, motif)` — l'inscription la plus récente reste.

    À année égale, celle dont le dernier état constaté est le plus récent ;
    puis la plus récemment créée. Une réinscription sous un nouveau numéro
    donne la fiche la plus jeune : c'est elle que Charlemagne exporte.
    """
    libelles = {x.id: x.libelle for x in session.query(AnneeScolaire).all()}

    def derniere(p: Personne) -> tuple[str, datetime]:
        rows = (
            session.query(Snapshot.annee_scolaire_id, Snapshot.date_ingestion)
            .filter(Snapshot.personne_id == p.id)
            .all()
        )
        if not rows:
            return ("", datetime.min)
        return max((libelles.get(aid, ""), d or datetime.min) for aid, d in rows)

    da, db = derniere(a), derniere(b)
    garde, absorbee = (a, b) if (da, a.id) >= (db, b.id) else (b, a)
    dg, dabs = (da, db) if garde is a else (db, da)

    if not dg[0] and not dabs[0]:
        motif = (
            f"Aucune des deux fiches n'a d'année connue : la plus récente, "
            f"{garde.cle_pivot}, reste."
        )
    elif dg[0] != dabs[0]:
        motif = (
            f"La fiche {garde.cle_pivot} est inscrite en {dg[0]}"
            + (
                f" ; la dernière année de {absorbee.cle_pivot} est {dabs[0]}"
                if dabs[0]
                else f" ; {absorbee.cle_pivot} n'a jamais été inscrite"
            )
            + f". C'est {garde.cle_pivot} que Charlemagne continue d'exporter."
        )
    else:
        motif = (
            f"Les deux fiches sont inscrites en {dg[0]} : la plus récente, "
            f"{garde.cle_pivot}, reste."
        )
    return garde, absorbee, motif


# ---------------------------------------------------------------------------
# Fusion
# ---------------------------------------------------------------------------


def fusionner(
    session: Session, id_a: int, id_b: int, *, mode: str = "simulation"
) -> RapportFusion:
    """Réunit deux fiches d'une même personne. Renvoie ce qui a été fait.

    En `simulation`, rien n'est écrit : le rapport dit ce que la fusion
    ferait. En `reel`, elle est journalisée et validée.
    """
    if mode not in ("simulation", "reel"):
        raise ValueError(f"mode invalide : {mode!r}")
    if id_a == id_b:
        raise FusionImpossible("Une fiche ne se réunit pas avec elle-même.")
    a, b = session.get(Personne, id_a), session.get(Personne, id_b)
    if a is None or b is None:
        manquant = id_a if a is None else id_b
        raise FusionImpossible(f"Fiche introuvable : {manquant}.")
    if a.type != b.type:
        raise FusionImpossible(
            "Un élève et un adulte ne se réunissent pas : leurs numéros "
            "Charlemagne appartiennent à deux numérotations différentes."
        )

    garde, absorbee, motif = choisir_garde(session, a, b)
    noms_sites = {s.id: s.nom for s in session.query(Site).all()}
    vecues = annees_vecues(session, [garde.id, absorbee.id])

    def resumer(p: Personne) -> FicheResumee:
        return FicheResumee(
            personne_id=p.id, cle_pivot=p.cle_pivot, nom=p.nom,
            prenom=p.prenom, login=p.login, badge=p.badge,
            site=noms_sites.get(p.site_id), classe=p.classe,
            email_constate=p.email_constate, annees=vecues.get(p.id, []),
        )

    rapport = RapportFusion(
        mode=mode, garde=resumer(garde), absorbee=resumer(absorbee),
        motif_du_choix=motif,
    )
    courante = annee_la_plus_recente(session)
    libelles = {x.id: x.libelle for x in session.query(AnneeScolaire).all()}

    # -- Ce qui doit faire hésiter ------------------------------------------
    inscrits = set()
    if courante is not None:
        inscrits = {
            pid
            for (pid,) in session.query(Snapshot.personne_id)
            .filter(
                Snapshot.annee_scolaire_id == courante.id,
                Snapshot.personne_id.in_([garde.id, absorbee.id]),
            )
            .distinct()
        }
    if len(inscrits) == 2:
        rapport.avertissements.append(
            f"Les deux fiches sont inscrites en {courante.libelle}. C'est la "
            "situation de deux homonymes : ne les réunis que si tu sais que "
            "c'est la même personne — une réinscription sous un nouveau "
            "numéro, par exemple."
        )
    from backend.services.regles_metier import normaliser_nom

    if (normaliser_nom(garde.nom), normaliser_nom(garde.prenom)) != (
        normaliser_nom(absorbee.nom), normaliser_nom(absorbee.prenom)
    ):
        rapport.avertissements.append(
            f"Les noms diffèrent : {garde.prenom} {garde.nom} et "
            f"{absorbee.prenom} {absorbee.nom}."
        )
    contradiction = _contradiction(garde, absorbee)
    if contradiction:
        rapport.avertissements.append(contradiction)
    if (
        garde.email_constate
        and absorbee.email_constate
        and garde.email_constate.lower() != absorbee.email_constate.lower()
    ):
        rapport.avertissements.append(
            f"Deux comptes Google pour une même personne : "
            f"{garde.email_constate} reste, {absorbee.email_constate} n'est "
            "plus suivi. Il faudra le supprimer, ou en faire un alias, dans "
            "Google."
        )

    # -- Les années -----------------------------------------------------------
    derniere_classe = {v.annee: v.classe for v in rapport.garde.annees}
    annees_garde = {
        aid
        for (aid,) in session.query(Snapshot.annee_scolaire_id)
        .filter(Snapshot.personne_id == garde.id)
        .distinct()
    }
    rattaches: list[int] = []
    ecartes: list[dict] = []
    for v in rapport.absorbee.annees:
        if v.annee in derniere_classe:
            rapport.annees_ecartees.append(
                f"{v.annee} · {v.classe or 'sans classe'} — "
                f"{garde.cle_pivot} y a déjà sa classe "
                f"({derniere_classe[v.annee] or 'sans classe'}), qui fait foi"
            )
        else:
            rapport.annees_rattachees.append(
                f"{v.annee} · {v.classe or 'sans classe'}"
                + (f" ({v.site})" if v.site else "")
            )
    for s in session.query(Snapshot).filter_by(personne_id=absorbee.id).all():
        if s.annee_scolaire_id in annees_garde:
            ecartes.append(
                {
                    "annee": libelles.get(s.annee_scolaire_id),
                    "classe": s.classe,
                    "date_ingestion": s.date_ingestion.isoformat()
                    if s.date_ingestion
                    else None,
                }
            )
            session.delete(s)
        else:
            s.personne_id = garde.id
            rattaches.append(s.id)

    # -- Ce qui manque à la fiche gardée ----------------------------------------
    for champ, libelle in CHAMPS_REPRIS:
        ancienne, actuelle = getattr(absorbee, champ), getattr(garde, champ)
        if ancienne and not actuelle:
            setattr(garde, champ, ancienne)
            rapport.repris.append(
                libelle
                if champ == "google_user_id"
                else f"{libelle} : {_afficher(ancienne)}"
            )
    if garde.email_constate and garde.email_attribuee:
        # Un constat remplace une attribution, comme à la saisie : garder
        # l'adresse attribuée la ferait resurgir le jour où l'on efface le
        # constat.
        garde.email_attribuee = None

    # -- Les comptes suivis -------------------------------------------------------
    inscrite = garde.id in inscrits
    comptes_garde = {
        c.cible: c
        for c in session.query(CompteCible).filter_by(personne_id=garde.id)
    }
    abandonnes: list[dict] = []
    for c in session.query(CompteCible).filter_by(personne_id=absorbee.id).all():
        nom = NOMS_CIBLES.get(c.cible, c.cible)
        destination = c.ou_appliquee or c.etat
        if c.cible in comptes_garde:
            if c.etat in ETATS_DE_SORTIE:
                rapport.abandonnes.append(
                    f"{nom} : la sortie prévue pour {absorbee.cle_pivot} "
                    f"({destination}) — le compte est celui de "
                    f"{garde.cle_pivot}, toujours suivi "
                    f"({comptes_garde[c.cible].etat})"
                )
            else:
                rapport.abandonnes.append(
                    f"{nom} : le suivi de {absorbee.cle_pivot} ({c.etat}) "
                    f"s'efface devant celui de {garde.cle_pivot} "
                    f"({comptes_garde[c.cible].etat})"
                )
        elif c.etat in ETATS_DE_SORTIE and inscrite:
            rapport.abandonnes.append(
                f"{nom} : la sortie prévue pour {absorbee.cle_pivot} "
                f"({destination}) — la personne est inscrite en "
                f"{courante.libelle}"
            )
        else:
            c.personne_id = garde.id
            rapport.repris.append(f"le suivi du compte {nom} ({c.etat})")
            continue
        abandonnes.append(
            {
                "cible": c.cible, "etat": c.etat, "ou_appliquee": c.ou_appliquee,
                "identifiant_externe": c.identifiant_externe,
            }
        )
        session.delete(c)

    cles_secrets = {
        (s.cible, s.site)
        for s in session.query(SecretConserve).filter_by(personne_id=garde.id)
    }
    for s in session.query(SecretConserve).filter_by(personne_id=absorbee.id).all():
        quoi = f"le mot de passe {NOMS_CIBLES.get(s.cible, s.cible)} {s.site or ''}".rstrip()
        if (s.cible, s.site) in cles_secrets:
            rapport.abandonnes.append(
                f"{quoi} de {absorbee.cle_pivot} — {garde.cle_pivot} a le sien"
            )
            session.delete(s)
        else:
            s.personne_id = garde.id
            rapport.repris.append(quoi)

    # -- Ce qui a été envoyé, et les verdicts ---------------------------------
    envois_garde = {
        eid
        for (eid,) in session.query(LigneEnvoi.envoi_id).filter(
            LigneEnvoi.personne_id == garde.id
        )
    }
    nb_lignes = 0
    for l in session.query(LigneEnvoi).filter_by(personne_id=absorbee.id).all():
        if l.envoi_id in envois_garde:
            session.delete(l)
        else:
            l.personne_id = garde.id
            nb_lignes += 1
    if nb_lignes:
        rapport.repris.append(
            f"{nb_lignes} ligne{'s' if nb_lignes > 1 else ''} d'envoi"
        )
    # Un verdict de cohérence décrit une fiche : celle-ci n'existera plus.
    # La prochaine Concordance juge la personne sur sa fiche gardée.
    session.query(VerdictCoherence).filter_by(personne_id=absorbee.id).delete()

    # -- L'ancien numéro -----------------------------------------------------------
    # Une fiche déjà absorbée par celle-ci suit le mouvement : son numéro
    # doit mener à la personne, pas à une fiche qui n'existe plus.
    session.query(FicheFusionnee).filter_by(personne_id=absorbee.id).update(
        {FicheFusionnee.personne_id: garde.id}
    )
    session.add(
        FicheFusionnee(
            personne_id=garde.id,
            type=absorbee.type,
            id_charlemagne=absorbee.id_charlemagne,
            badge=absorbee.badge,
            login=absorbee.login,
            nom=absorbee.nom,
            prenom=absorbee.prenom,
            site=noms_sites.get(absorbee.site_id),
            email_constate=absorbee.email_constate,
            etat_json=json.dumps(
                {
                    "fiche": {
                        k: getattr(absorbee, k)
                        for k in (
                            "nom", "prenom", "nom_usage", "classe", "niveau",
                            "code_etablissement", "regime", "email_constate",
                            "email_attribuee", "google_user_id",
                            "chemin_photo_constate", "civilite", "poste_occupe",
                            "matieres", "classes_prof_principal",
                            "email_professionnel", "email_personnel", "ine",
                        )
                    }
                    | {
                        "site": noms_sites.get(absorbee.site_id),
                        "date_naissance": absorbee.date_naissance.isoformat()
                        if absorbee.date_naissance
                        else None,
                        "date_entree": absorbee.date_entree.isoformat()
                        if absorbee.date_entree
                        else None,
                        "date_creation": absorbee.date_creation.isoformat()
                        if absorbee.date_creation
                        else None,
                    },
                    "annees": [asdict(v) for v in rapport.absorbee.annees],
                    "snapshots_rattaches": rattaches,
                    "snapshots_ecartes": ecartes,
                    "comptes_abandonnes": abandonnes,
                    "motif": motif,
                },
                ensure_ascii=False,
            ),
        )
    )
    session.flush()
    session.delete(absorbee)
    session.flush()

    if mode == "reel":
        from backend.services.journal import journaliser

        journaliser(
            session,
            type_operation="fusion",
            cible=garde.type,
            mode="reel",
            annee_libelle=courante.libelle if courante else None,
            parametres={
                "garde": rapport.garde.cle_pivot,
                "absorbee": rapport.absorbee.cle_pivot,
            },
            resultat={
                "nom": f"{garde.prenom} {garde.nom}",
                "motif": motif,
                "annees_rattachees": rapport.annees_rattachees,
                "annees_ecartees": rapport.annees_ecartees,
                "repris": rapport.repris,
                "abandonnes": rapport.abandonnes,
                "avertissements": rapport.avertissements,
            },
        )
        session.commit()
    else:
        session.rollback()
    return rapport


# ---------------------------------------------------------------------------
# Repérage
# ---------------------------------------------------------------------------


@dataclass
class Lien:
    """Ce que deux fiches ont à se dire."""

    probable: bool
    """Tout indique une seule personne."""
    preuve: str | None = None
    """`ine`, `naissance` ou `passage` — ce qui le fait penser."""
    contradiction: str | None = None
    """Ce qui prouve deux personnes, en une phrase. Jamais avec `probable`."""


PREUVES = {
    "ine": "Même INE",
    "naissance": "Même nom, même date de naissance",
}


def evaluer_lien(a: Personne, b: Personne, inscrits_courante: set[int]) -> Lien:
    """Deux fiches : une seule personne inscrite deux fois, ou deux personnes ?

    Par ordre de force :

    1. **L'INE.** Il suit l'élève d'un établissement à l'autre : le même,
       c'est le même élève — quel que soit le nom, quelle que soit l'année.
       Deux INE différents, ce sont deux élèves.
    2. **La date de naissance**, avec le même nom — à l'accent près :
       `QUÉMÉNEUR` et `QUEMENEUR` sont la même élève, écrite par deux
       secrétariats. Même date, même personne ; dates différentes, deux
       homonymes.
    3. **Le passage**, faute de mieux : même nom, et une seule des deux
       fiches inscrite cette année. L'autre est partie l'année où
       celle-ci est arrivée.

    Deux fiches inscrites toutes les deux, sans rien pour les rapprocher,
    sont deux personnes jusqu'à preuve du contraire : c'est exactement la
    situation de deux homonymes.
    """
    from backend.services.regles_metier import normaliser_nom

    if a.type != b.type:
        return Lien(False)
    if a.ine and b.ine:
        if a.ine == b.ine:
            return Lien(True, "ine")
        return Lien(False, contradiction=_contradiction(a, b))
    if (normaliser_nom(a.nom), normaliser_nom(a.prenom)) != (
        normaliser_nom(b.nom), normaliser_nom(b.prenom)
    ):
        return Lien(False)
    if a.date_naissance and b.date_naissance:
        if a.date_naissance == b.date_naissance:
            return Lien(True, "naissance")
        return Lien(False, contradiction=_contradiction(a, b))
    if (a.id in inscrits_courante) != (b.id in inscrits_courante):
        return Lien(True, "passage")
    return Lien(False)


def meme_personne_probable(
    a: Personne, b: Personne, inscrits_courante: set[int]
) -> bool:
    """Deux fiches qui ont tout d'une seule personne. Voir `evaluer_lien`."""
    return evaluer_lien(a, b, inscrits_courante).probable


def _contradiction(a: Personne, b: Personne) -> str | None:
    """Ce qui prouve deux personnes — un INE, une date de naissance."""
    if a.ine and b.ine and a.ine != b.ine:
        return (
            f"Deux INE différents ({a.ine}, {b.ine}) : ce sont deux élèves. "
            "L'INE suit l'élève d'un établissement à l'autre."
        )
    if (
        a.date_naissance
        and b.date_naissance
        and a.date_naissance != b.date_naissance
    ):
        return (
            f"Nés à deux dates différentes ({_afficher(a.date_naissance)}, "
            f"{_afficher(b.date_naissance)}) : ce sont deux homonymes."
        )
    return None


def _afficher(v) -> str:
    """Une date comme on l'écrit ici : `12/03/2012`. Le reste tel quel."""
    return v.strftime("%d/%m/%Y") if hasattr(v, "strftime") else str(v)


@dataclass
class Doublon:
    """Deux fiches d'une même personne, repérées sans adresse disputée."""

    garde: Personne
    absorbee: Personne
    preuve: str
    motif: str


def doublons(session: Session) -> list[Doublon]:
    """Les personnes en deux fiches, prouvées par l'INE ou la naissance.

    L'écran « Départager » les trouvait par l'adresse qu'elles se
    disputaient. Un élève passé de NDE à NDK sous une adresse neuve ne se
    dispute rien : ses deux fiches cohabitent sans bruit, son parcours
    coupé en deux, et il compte parmi les sortants d'un site et les
    entrants de l'autre. L'INE le retrouve ; la date de naissance, avec le
    nom, quand l'INE manque.

    Rien n'est réuni ici : c'est une liste, que l'écran présente.
    """
    from backend.services.regles_metier import normaliser_nom

    gens = session.query(Personne).all()
    courante = annee_la_plus_recente(session)
    inscrits: set[int] = set()
    if courante is not None:
        inscrits = {
            pid
            for (pid,) in session.query(Snapshot.personne_id)
            .filter(Snapshot.annee_scolaire_id == courante.id)
            .distinct()
        }

    groupes: dict[tuple, list[Personne]] = {}
    for p in gens:
        if p.ine:
            groupes.setdefault(("ine", p.type, p.ine), []).append(p)
        if p.date_naissance:
            groupes.setdefault(
                (
                    "naissance", p.type, normaliser_nom(p.nom),
                    normaliser_nom(p.prenom), p.date_naissance,
                ),
                [],
            ).append(p)

    vus: set[frozenset[int]] = set()
    trouves: list[Doublon] = []
    for cle, ps in groupes.items():
        for i, a in enumerate(ps):
            for b in ps[i + 1:]:
                paire = frozenset((a.id, b.id))
                if paire in vus:
                    continue
                lien = evaluer_lien(a, b, inscrits)
                if not lien.probable or lien.preuve not in ("ine", "naissance"):
                    continue
                vus.add(paire)
                garde, absorbee, _ = choisir_garde(session, a, b)
                vecues = annees_vecues(session, [garde.id, absorbee.id])
                trouves.append(
                    Doublon(
                        garde=garde,
                        absorbee=absorbee,
                        preuve=lien.preuve,
                        motif=decrire_passage(
                            garde, vecues.get(garde.id, []),
                            absorbee, vecues.get(absorbee.id, []),
                            preuve=lien.preuve,
                        ),
                    )
                )
    trouves.sort(key=lambda d: (d.garde.nom, d.garde.prenom))
    return trouves


def doublons_sans_adresse_disputee(session: Session) -> list[Doublon]:
    """Les doublons que les adresses disputées ne montrent pas déjà.

    Une paire qui se dispute une adresse est présentée avec elle ; la
    présenter deux fois ferait réunir deux fois. Une seule source pour
    l'écran et pour le compteur des constats : deux calculs finiraient
    par diverger.
    """
    from backend.services.anomalies import collisions_email

    deja = [{p.id for p in ps} for ps in collisions_email(session).values()]
    return [
        d for d in doublons(session)
        if not any({d.garde.id, d.absorbee.id} <= g for g in deja)
    ]


def decrire_passage(
    garde: Personne,
    annees_garde: list[AnneeVecue],
    absorbee: Personne,
    annees_absorbee: list[AnneeVecue],
    *,
    preuve: str | None = None,
) -> str:
    """Ce qui fait penser à une seule personne, en une phrase.

    « 4J à NDE en 2025-2026, puis 3_PM à NDK en 2026-2027 : un passage de
    NDE à NDK, pas deux homonymes. » La phrase met les deux années côte à
    côte : c'est ce qu'on regarde pour décider, et il faudrait sinon ouvrir
    les deux fiches.
    """
    entree = f"{PREUVES[preuve]}. " if preuve in PREUVES else ""
    if not annees_garde or not annees_absorbee:
        return entree + (
            "Une seule des deux fiches a une année connue."
            if entree
            else "Même nom, et une seule des deux fiches est inscrite cette année."
        )

    def situer(v: AnneeVecue, p: Personne) -> tuple[str, str | None]:
        site = v.site or (p.site.nom if p.site else None)
        texte = (
            (v.classe or "sans classe")
            + (f" à {site}" if site else "")
            + f" en {v.annee}"
        )
        return texte, site

    avant, site_avant = situer(annees_absorbee[0], absorbee)
    apres, site_apres = situer(annees_garde[0], garde)
    if site_avant and site_apres and site_avant != site_apres:
        return entree + (
            f"{avant}, puis {apres} : un passage de {site_avant} à "
            f"{site_apres}, pas deux homonymes."
        )
    return entree + (
        f"{avant} sous {absorbee.cle_pivot}, puis {apres} sous "
        f"{garde.cle_pivot} : une réinscription sous un nouveau numéro."
    )
