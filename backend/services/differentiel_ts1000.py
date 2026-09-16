"""Le différentiel TS1000, calculé contre l'état réel de la centrale.

## Pourquoi ce module remplace le calcul depuis le référentiel

`exports_jpm` comparait deux années du référentiel. C'est le bon calcul
pour KoXo ou Google, qui reçoivent un état complet — ce n'en est pas un
pour TS1000, qui attend des **changements par rapport à ce qu'il détient**,
et dont le contenu dérive de son côté : un collègue déplace un interne, un
badge est encodé à la main, une carte est réaffectée.

Le différentiel part donc du fichier `Users.xls` que la centrale exporte,
exactement comme l'export PMB et l'export CardStudio partent du fichier de
Charlemagne. Ce qui est comparé est ce qui est réellement en place.

## Le CardId ne se perd jamais

Le `CardId` est l'identifiant matériel de la carte encodée. Une ligne de
modification qui le laisse vide **casse la carte** : elle cesse d'ouvrir.
Chaque ligne réémise reprend donc la sienne, et un contrôle final le
vérifie avant de rendre le fichier.

## Un groupe d'accès n'est pas un groupe de classe

Dans TS1000, `Group` ne porte qu'une valeur. Un interne, un AVS, un agent
d'entretien y est rangé dans un groupe qui lui **ouvre des portes** — pas
dans sa classe. Proposer de le ramener vers sa classe lui ferme l'internat
ou le local technique.

La règle est donc absolue : **on ne propose un déplacement que depuis un
groupe de classe**, c'est-à-dire un groupe déclaré dans la Table de
correspondance. Tout le reste est laissé tel quel et compté à part. La
première version de ce calcul, faite à la main en septembre 2026, proposait
quarante-neuf déplacements dont quarante-trois annulaient une réparation
importée la veille.

## L'internat s'apprend, il ne se devine pas

Un pensionnaire — régime `P` chez Charlemagne — doit rejoindre le groupe
d'internat de son niveau. Le référentiel ne porte pas le niveau : il est
vide sur les 2132 snapshots. Plutôt que d'inventer une règle à partir du
code classe, le module **lit où sont déjà rangés les pensionnaires de la
même classe**, puis de la même famille de classes. Un pensionnaire dont
aucun camarade n'est encore placé est signalé, pas deviné.

## Une suppression est proposée, jamais décidée

« Absent du référentiel » n'est pas une preuve de départ — c'est la règle
apprise sur les comptes Google, et elle vaut ici. Les suppressions sortent
dans leur propre fichier, à relire.
"""
from __future__ import annotations

import io
from collections import Counter, defaultdict
from dataclasses import dataclass, field

from sqlalchemy.orm import Session

from backend.models import Personne, Site, Snapshot, TableCorrespondance

SITES_TS1000 = ("NDK", "SU")
"""NDE n'a ni contrôle d'accès ni serveur KoXo."""

COLONNES_MINIMALES = ("Op", "Id", "Name", "Group", "CardId")

REGIME_PENSIONNAIRE = "P"


class DifferentielImpossible(Exception):
    """Le calcul est refusé, et le message dit pourquoi."""


@dataclass
class Mouvement:
    """Une ligne à porter dans TS1000, et pourquoi."""

    op: str
    badge: str
    nom: str
    groupe_actuel: str | None
    groupe_vise: str | None
    motif: str
    a_une_carte: bool = False
    ligne: dict = field(default_factory=dict)
    """La ligne d'origine, réémise telle quelle — CardId compris."""


@dataclass
class RapportTS1000:
    colonnes: list[str] = field(default_factory=list)
    nb_lignes_lues: int = 0
    nb_inscrits: int = 0

    creations: list[Mouvement] = field(default_factory=list)
    deplacements: list[Mouvement] = field(default_factory=list)
    internat: list[Mouvement] = field(default_factory=list)
    suppressions: list[Mouvement] = field(default_factory=list)

    proteges: list[Mouvement] = field(default_factory=list)
    """Dans un groupe qui n'est pas une classe : jamais déplacés."""
    indetermines: list[Mouvement] = field(default_factory=list)
    """Pensionnaires dont le groupe d'internat n'a pas pu être appris."""

    groupes_internat: list[str] = field(default_factory=list)
    avertissements: list[str] = field(default_factory=list)

    @property
    def nb_total(self) -> int:
        return (
            len(self.creations)
            + len(self.deplacements)
            + len(self.internat)
            + len(self.suppressions)
        )

    @property
    def est_vide(self) -> bool:
        return self.nb_total == 0


def _texte(v) -> str:
    if v is None:
        return ""
    if isinstance(v, float):
        return str(int(v)) if v.is_integer() else str(v)
    return str(v).strip()


def _grille(contenu: bytes) -> list[list]:
    """Les cellules du classeur, quel que soit son âge.

    La centrale écrit du `.xls`, mais un fichier passé par Excel ressort en
    `.xlsx` — et l'utilisateur ne voit pas la différence. Refuser l'un des
    deux ferait échouer un fichier qui porte pourtant les bonnes données.
    Les `.xlsx` commencent par `PK` : ce sont des archives zip.
    """
    if contenu[:2] == b"PK":
        import openpyxl

        feuille = openpyxl.load_workbook(
            io.BytesIO(contenu), read_only=True, data_only=True
        ).active
        return [list(l) for l in feuille.iter_rows(values_only=True)]

    import xlrd

    feuille = xlrd.open_workbook(
        file_contents=contenu, encoding_override="cp1252"
    ).sheet_by_index(0)
    return [
        [feuille.cell_value(r, c) for c in range(feuille.ncols)]
        for r in range(feuille.nrows)
    ]


def lire_export_ts1000(contenu: bytes) -> tuple[list[str], dict[str, dict]]:
    """Lit `Users.xls` tel que la centrale l'écrit.

    Returns:
        `(colonnes dans leur ordre, {badge: ligne})`

    Raises:
        DifferentielImpossible: fichier illisible, ou dont l'en-tête n'est
            pas celui de TS1000.
    """
    try:
        cellules = _grille(contenu)
    except DifferentielImpossible:
        raise
    except Exception as e:
        raise DifferentielImpossible(
            f"Fichier illisible — est-ce bien l'export de TS1000 ? ({e})"
        ) from None

    if not cellules:
        raise DifferentielImpossible("Le fichier est vide.")

    colonnes = [_texte(v) for v in cellules[0]]
    manquantes = [c for c in COLONNES_MINIMALES if c not in colonnes]
    if manquantes:
        raise DifferentielImpossible(
            "Ce n'est pas l'export TS1000 : il y manque "
            + " et ".join(f"« {c} »" for c in manquantes)
            + ". L'en-tête lu commence par : "
            + ", ".join(colonnes[:5] or ["(rien)"])
            + "."
        )

    lignes: dict[str, dict] = {}
    for brute in cellules[1:]:
        d = {c: _texte(brute[i]) if i < len(brute) else "" for i, c in enumerate(colonnes)}
        if d.get("Id"):
            lignes[d["Id"]] = d
    return colonnes, lignes


def _inscrits(session: Session, annee_id: int) -> dict[str, tuple[Personne, str, str]]:
    """`{badge: (personne, classe, régime)}` pour les élèves des sites à badge."""
    sites = {s.id: s.nom for s in session.query(Site).all()}
    derniers: dict[int, Snapshot] = {}
    for sn in (
        session.query(Snapshot).filter(Snapshot.annee_scolaire_id == annee_id).all()
    ):
        prec = derniers.get(sn.personne_id)
        if prec is None or (
            sn.date_ingestion
            and prec.date_ingestion
            and sn.date_ingestion > prec.date_ingestion
        ):
            derniers[sn.personne_id] = sn

    out: dict[str, tuple[Personne, str, str]] = {}
    for p in session.query(Personne).filter(Personne.type == "eleve").all():
        sn = derniers.get(p.id)
        if sn is None or not (sn.classe or "").strip():
            continue
        if sites.get(p.site_id) not in SITES_TS1000 or not p.badge:
            continue
        out[str(p.badge)] = (p, sn.classe.strip(), (sn.regime or "").strip())
    return out


def _apprendre_internat(
    lignes: dict[str, dict],
    inscrits: dict[str, tuple[Personne, str, str]],
    codes_classe: set[str],
) -> tuple[set[str], dict[str, str], dict[str, str]]:
    """Où sont rangés les pensionnaires déjà placés.

    Le niveau étant absent du référentiel, on ne le devine pas : on regarde
    où se trouvent les camarades. Deux niveaux de repli, du plus précis au
    moins précis, et rien au-delà.

    Returns:
        `(groupes d'internat, {classe: groupe}, {famille de classe: groupe})`
    """
    groupes_internat = {
        d["Group"]
        for d in lignes.values()
        if d["Group"] and d["Group"] not in codes_classe
        and "interne" in d["Group"].casefold()
    }

    par_classe: dict[str, Counter] = defaultdict(Counter)
    par_famille: dict[str, Counter] = defaultdict(Counter)
    for badge, d in lignes.items():
        if d["Group"] not in groupes_internat:
            continue
        connu = inscrits.get(badge)
        if connu is None:
            continue
        _, classe, _ = connu
        par_classe[classe][d["Group"]] += 1
        par_famille[_famille(classe)][d["Group"]] += 1

    return (
        groupes_internat,
        {c: n.most_common(1)[0][0] for c, n in par_classe.items() if n},
        {f: n.most_common(1)[0][0] for f, n in par_famille.items() if n},
    )


def _famille(classe: str) -> str:
    """Le regroupement grossier d'un code classe — `2_5` et `2_8` ensemble.

    Sert uniquement de second repli quand aucun pensionnaire de la classe
    exacte n'est encore placé. Une famille n'a pas de sens métier : c'est
    juste « ce qui commence pareil ».
    """
    c = classe.strip()
    if "_" in c:
        return c.split("_", 1)[0]
    return c[:1]


def calculer_differentiel(
    session: Session,
    contenu: bytes,
    *,
    annee_id: int,
) -> RapportTS1000:
    """Ce qu'il faudrait porter dans TS1000. Ne modifie rien.

    Args:
        contenu: l'export `Users.xls` de la centrale, tel quel.
        annee_id: l'année dont les inscriptions font foi.
    """
    colonnes, lignes = lire_export_ts1000(contenu)
    inscrits = _inscrits(session, annee_id)

    codes_classe = {
        (t.classe_code_court or "").strip()
        for t in session.query(TableCorrespondance).all()
        if (t.classe_code_court or "").strip()
    }
    if not codes_classe:
        raise DifferentielImpossible(
            "La table de correspondance est vide : sans elle, rien ne "
            "distingue un groupe de classe d'un groupe d'accès, et tout "
            "déplacement proposé serait à l'aveugle."
        )

    groupes_internat, par_classe, par_famille = _apprendre_internat(
        lignes, inscrits, codes_classe
    )

    rapport = RapportTS1000(
        colonnes=colonnes,
        nb_lignes_lues=len(lignes),
        nb_inscrits=len(inscrits),
        groupes_internat=sorted(groupes_internat),
    )

    def mouvement(op, badge, d, groupe_vise, motif, personne=None):
        nom = (
            _texte(d.get("Name"))
            if d
            else f"{personne.nom} {personne.prenom}".strip()
        )
        return Mouvement(
            op=op,
            badge=badge,
            nom=nom,
            groupe_actuel=_texte(d.get("Group")) if d else None,
            groupe_vise=groupe_vise,
            motif=motif,
            a_une_carte=bool(d and _texte(d.get("CardId"))),
            ligne=dict(d) if d else {},
        )

    for badge, (personne, classe, regime) in sorted(inscrits.items()):
        d = lignes.get(badge)

        if d is None:
            neuve = {c: "" for c in colonnes}
            neuve.update(
                {
                    "Op": "a",
                    "Id": badge,
                    "Name": f"{personne.nom} {personne.prenom}".strip(),
                    "Group": classe,
                }
            )
            for defaut, valeur in (("PIN", "FFFFFF"), ("ADA", "0"), ("Technology", "P")):
                if defaut in neuve:
                    neuve[defaut] = valeur
            m = mouvement("a", badge, neuve, classe, "Inscrit, inconnu de TS1000", personne)
            m.groupe_actuel = None
            rapport.creations.append(m)
            continue

        groupe = _texte(d.get("Group"))

        # Pensionnaire rangé dans sa classe : il doit passer à l'internat.
        if regime == REGIME_PENSIONNAIRE and groupe not in groupes_internat:
            vise = par_classe.get(classe) or par_famille.get(_famille(classe))
            if vise:
                rapport.internat.append(
                    mouvement("m", badge, d, vise, f"Pensionnaire de {classe}")
                )
            else:
                rapport.indetermines.append(
                    mouvement(
                        "m", badge, d, None,
                        f"Pensionnaire de {classe} — aucun camarade déjà placé, "
                        "le groupe d'internat ne peut pas être appris",
                    )
                )
            continue

        if groupe == classe:
            continue

        if groupe in codes_classe:
            rapport.deplacements.append(
                mouvement("m", badge, d, classe, f"Rangé en {groupe}, inscrit en {classe}")
            )
        else:
            # Groupe d'accès : on n'y touche pas. Voir l'en-tête du module.
            rapport.proteges.append(
                mouvement("m", badge, d, None, f"Dans le groupe d'accès « {groupe} »")
            )

    for badge, d in sorted(lignes.items()):
        if badge in inscrits:
            continue
        if _texte(d.get("Group")) in codes_classe:
            rapport.suppressions.append(
                mouvement("b", badge, d, None, "Dans une classe, plus inscrit")
            )

    if not groupes_internat:
        rapport.avertissements.append(
            "Aucun groupe d'internat repéré dans l'export : les pensionnaires "
            "ne seront pas proposés au déplacement."
        )
    if rapport.indetermines:
        rapport.avertissements.append(
            f"{len(rapport.indetermines)} pensionnaire(s) sans destination "
            "apprise — les placer une première fois à la main suffit, le "
            "calcul suivant saura."
        )
    if rapport.suppressions:
        rapport.avertissements.append(
            f"{len(rapport.suppressions)} suppression(s) proposée(s) : "
            "« absent du référentiel » n'est pas une preuve de départ. "
            "À relire avant d'importer."
        )
    return rapport


def ecrire_classeur(colonnes: list[str], mouvements: list[Mouvement]) -> bytes:
    """Un classeur au format que la centrale relit, colonnes d'origine.

    Chaque ligne est celle de l'export, avec `Op` et `Group` réécrits — tout
    le reste passe tel quel, à commencer par le `CardId`.
    """
    import openpyxl

    classeur = openpyxl.Workbook()
    feuille = classeur.active
    feuille.title = "Sheet 1"
    feuille.append(colonnes)
    for m in mouvements:
        ligne = dict(m.ligne)
        ligne["Op"] = m.op
        if m.groupe_vise is not None:
            ligne["Group"] = m.groupe_vise
        feuille.append([ligne.get(c, "") for c in colonnes])

    tampon = io.BytesIO()
    classeur.save(tampon)
    return tampon.getvalue()


def controler_cardid(
    colonnes: list[str], mouvements: list[Mouvement]
) -> list[str]:
    """Les badges dont la carte serait cassée par le fichier produit.

    Une ligne de modification qui perd son `CardId` fait cesser d'ouvrir la
    carte encodée. Le contrôle tourne avant de rendre le fichier, pas après.
    """
    perdus = []
    for m in mouvements:
        if m.op == "a":
            continue
        if m.a_une_carte and not _texte(m.ligne.get("CardId")):
            perdus.append(m.badge)
    return perdus
