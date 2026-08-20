"""Mise en conformité de l'arborescence Google avec la Table de correspondance.

## Le besoin

La Table décrit où chaque classe doit ranger ses élèves. Encore faut-il
que ces unités d'organisation existent : Google refuse un déplacement
vers une OU absente, et l'échec est silencieux au sens où rien, en
amont, ne l'annonce. Sur l'instance réelle, la rotation vers 2027 visait
90 OU dont **aucune** n'existait.

## Deux façons de préparer l'année

**Renommer** l'arbre de l'année révolue : `NDK2025` devient `NDK2027`,
et ses dizaines de classes suivent d'un seul geste. Rapide, mais l'arbre
garde les classes de son année d'origine — celles qui n'existaient pas
alors manqueront, celles qui ont disparu resteront.

**Créer** ce qui manque, une OU à la fois, exactement d'après la Table.
Plus long, mais le résultat correspond à l'année préparée.

Les deux se combinent, et c'est le cas courant : sur l'instance réelle,
renommer les arbres 2025 couvre 70 des 90 OU ; les 20 restantes sont des
classes nouvelles — plus le site NDE, qui n'a pas d'arbre 2025 à
recycler.

## Prudence

Ce module ne supprime jamais une OU. Une OU devenue inutile peut encore
contenir des comptes ; l'effacer les déplacerait à la racine sans
prévenir. Le nettoyage reste un geste manuel, après vérification.
"""
from __future__ import annotations

import re

from dataclasses import dataclass, field

from sqlalchemy.orm import Session

from backend.models import TableCorrespondance


@dataclass
class RenommageOU:
    ancien: str
    nouveau: str
    nb_sous_ou: int
    utile: bool = True
    """Faux si aucune OU attendue ne se trouve sous le nouveau chemin."""
    """Classes emportées par le renommage — elles suivent leur parent."""


@dataclass
class RapportConformiteOU:
    ou_attendues: list[str] = field(default_factory=list)
    ou_existantes: list[str] = field(default_factory=list)
    annees_table: list[str] = field(default_factory=list)
    """Années lues dans les chemins de la Table. Si l'année visée n'y figure
    pas, c'est la Table qui n'a pas été tournée — pas Google qui a du retard."""

    renommages: list[RenommageOU] = field(default_factory=list)
    a_creer: list[str] = field(default_factory=list)
    """Dans l'ordre parent-avant-enfant : Google exige que le parent existe."""

    deja_conformes: list[str] = field(default_factory=list)
    avertissements: list[str] = field(default_factory=list)

    @property
    def nb_a_creer(self) -> int:
        return len(self.a_creer)

    @property
    def est_conforme(self) -> bool:
        return not self.a_creer and not self.renommages


def _ordonner_par_profondeur(chemins: set[str]) -> list[str]:
    """Parents avant enfants, puis alphabétique.

    Créer `/A/B` avant `/A` échoue : Google veut un parent existant.
    """
    return sorted(chemins, key=lambda c: (c.count("/"), c))


def analyser_conformite(
    session: Session,
    ou_existantes: list[str],
    *,
    annee_source: str | None = None,
    annee_cible: str | None = None,
    autoriser_renommage: bool = True,
) -> RapportConformiteOU:
    """Compare l'arborescence réelle à ce que vise la Table.

    Args:
        ou_existantes: chemins retournés par `ClientGoogle.lister_ou`.
        annee_source: année à recycler, ex. `2025`. Ses arbres seront
            proposés au renommage vers `annee_cible`.
        annee_cible: année visée, ex. `2027`. Déduite de la Table si absente.
        autoriser_renommage: à faux, tout est créé à neuf et les arbres
            anciens sont laissés en place.
    """
    existantes = set(ou_existantes)

    attendues: set[str] = set()
    for tc in session.query(TableCorrespondance).all():
        for champ in (tc.ou_pre_rentree, tc.ou_definitive):
            if champ and champ.strip():
                attendues.add(champ.strip().rstrip("/"))

    rapport = RapportConformiteOU(
        ou_attendues=sorted(attendues),
        ou_existantes=sorted(existantes),
    )
    if not attendues:
        rapport.avertissements.append(
            "La Table de correspondance ne déclare aucune OU : rien à comparer."
        )
        return rapport

    # Années réellement déclarées par la Table. Un renommage vers une année
    # qu'elle ignore ne rapproche aucune OU attendue : il déplace un arbre
    # vers un nom que rien ne réclame.
    rapport.annees_table = sorted(
        {a for o in attendues for a in re.findall(r"(?<!\d)(\d{4})(?!\d)", o)}
    )
    if annee_cible and rapport.annees_table and annee_cible not in rapport.annees_table:
        rapport.avertissements.append(
            f"La Table déclare ses OU sous {', '.join(rapport.annees_table)}, "
            f"or l'année visée est {annee_cible} : aucune OU attendue ne se "
            "trouvera sous ce nom. Faire tourner la Table de correspondance "
            "avant d'appliquer — sinon le renommage déplace un arbre que rien "
            "ne réclame, et les créations garnissent l'année en cours."
        )

    # Après renommage, ces chemins seront disponibles sans rien créer.
    apres_renommage = set(existantes)
    if autoriser_renommage and annee_source and annee_cible:
        # Racines d'année : deux niveaux, `/3. NDK/NDK2025`
        racines = {
            o for o in existantes
            if o.count("/") == 2 and annee_source in o.rsplit("/", 1)[-1]
        }
        for racine in sorted(racines):
            nouveau_chemin = racine.replace(annee_source, annee_cible)
            if nouveau_chemin in existantes:
                rapport.avertissements.append(
                    f"{nouveau_chemin} existe déjà : {racine} n'est pas renommée, "
                    "pour ne pas fusionner deux arbres."
                )
                continue
            enfants = [o for o in existantes if o.startswith(racine + "/")]
            rapport.renommages.append(
                RenommageOU(
                    ancien=racine,
                    nouveau=nouveau_chemin,
                    nb_sous_ou=len(enfants),
                )
            )
            apres_renommage.add(nouveau_chemin)
            for e in enfants:
                apres_renommage.add(e.replace(racine, nouveau_chemin, 1))

    for r in rapport.renommages:
        r.utile = any(
            a == r.nouveau or a.startswith(r.nouveau + "/") for a in attendues
        )

    manquantes = attendues - apres_renommage
    rapport.a_creer = _ordonner_par_profondeur(_avec_parents(manquantes, apres_renommage))
    rapport.deja_conformes = sorted(attendues & apres_renommage)
    return rapport


def _avec_parents(manquantes: set[str], disponibles: set[str]) -> set[str]:
    """Ajoute les parents intermédiaires absents.

    La Table ne déclare que les OU de classe et d'attente ; si l'arbre
    d'année lui-même n'existe pas, il faut le créer avant ses enfants.
    """
    complet = set(manquantes)
    for chemin in manquantes:
        morceaux = chemin.strip("/").split("/")
        for i in range(1, len(morceaux)):
            parent = "/" + "/".join(morceaux[:i])
            if parent not in disponibles:
                complet.add(parent)
    return complet
