"""Rotation annuelle des unités d'organisation Google.

## Le mouvement réel

L'arborescence Google porte l'année dans son nom — `/3. NDK/NDK2026` —
et cette année est celle qui **se termine** : `NDK2026` contient la
photo de l'année scolaire 2025-2026.

À chaque rentrée, l'arbre le plus ancien s'est vidé de lui-même (ses
élèves sont partis ou ont été déplacés). Il est alors renommé pour
l'année qui arrive, et devient la destination de la campagne : les
élèves de `NDK2026` rejoignent `NDK2027`, d'abord à sa racine pendant la
pré-rentrée, puis dans leur classe le jour J.

## Ce que fait ce service

La Table de correspondance décrit la destination : elle doit donc suivre
ce renommage. Rejouer 87 lignes à la main chaque année est une source
d'erreur silencieuse — une ligne oubliée envoie une classe entière dans
l'arbre de l'an dernier, et le programme n'a aucun moyen de le savoir :
les deux chemins sont également valides à ses yeux.

Le remplacement ne porte que sur les **chemins d'OU**. Les adresses de
groupes ne contiennent pas d'année et ne doivent pas bouger.

## Un fragment peut se cacher dans un nombre plus long

`2026` apparaît aussi dans `SALLE12026`. Remplacer par sous-chaîne y
changerait le sens du chemin sans que personne ne l'ait voulu, et l'erreur
ne se manifesterait qu'à la bascule, sur une classe. Le service ne refuse
pas ces cas — le fragment reste libre, c'est ce qui permet de viser
`NDK2026` plutôt que `2026` — mais il les compte et les signale, pour que
la décision soit prise en connaissance de cause.

## Simulation d'abord

Comme partout ailleurs : le rapport décrit ce qui changerait, ligne par
ligne, avant que quoi que ce soit ne soit écrit.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field

from sqlalchemy.orm import Session

from backend.models import Site, TableCorrespondance

# Seules ces colonnes portent un chemin d'OU.
COLONNES_OU = ("ou_pre_rentree", "ou_definitive")


@dataclass
class LigneRenommee:
    id: int
    classe: str
    site: str | None
    avant_pre_rentree: str
    apres_pre_rentree: str
    avant_definitive: str
    apres_definitive: str


@dataclass
class RapportRotation:
    chercher: str
    remplacer: str
    mode: str

    nb_lignes_examinees: int = 0
    nb_lignes_modifiees: int = 0
    nb_dans_un_nombre: int = 0
    """Occurrences trouvées à l'intérieur d'une suite de chiffres plus longue."""
    annees_presentes: dict[str, int] = field(default_factory=dict)
    """Millésimes réellement écrits dans les chemins, et leur nombre.

    Sans eux, « 87 lignes ne contiennent pas 2025 » laisse chercher ce
    qu'elles contiennent — alors que c'est la seule chose utile à savoir."""
    lignes: list[LigneRenommee] = field(default_factory=list)
    avertissements: list[str] = field(default_factory=list)

    @property
    def nb_inchangees(self) -> int:
        return self.nb_lignes_examinees - self.nb_lignes_modifiees


def renommer_dans_les_ou(
    session: Session,
    *,
    chercher: str,
    remplacer: str,
    site_id: int | None = None,
    mode: str = "simulation",
) -> RapportRotation:
    """Remplace un fragment dans les chemins d'OU de la Table.

    Args:
        chercher: fragment à remplacer, typiquement l'année (`2026`).
        remplacer: ce qui le remplace (`2027`).
        site_id: restreint à un site. `None` = tous.
        mode: `simulation` (défaut) ou `reel`.

    Raises:
        ValueError: si le fragment est vide, ou identique au remplacement.
    """
    if mode not in ("simulation", "reel"):
        raise ValueError(f"mode invalide : {mode!r}")
    if not chercher:
        raise ValueError("Le fragment à chercher ne peut pas être vide.")
    if chercher == remplacer:
        raise ValueError("Le fragment cherché et son remplacement sont identiques.")

    rapport = RapportRotation(chercher=chercher, remplacer=remplacer, mode=mode)
    noms_sites = {s.id: s.nom for s in session.query(Site).all()}

    q = session.query(TableCorrespondance)
    if site_id is not None:
        q = q.filter(TableCorrespondance.site_id == site_id)

    # Une occurrence encadrée de chiffres n'est pas le millésime qu'on croit.
    noye = re.compile(r"\d" + re.escape(chercher) + r"|" + re.escape(chercher) + r"\d")

    for tc in q.order_by(TableCorrespondance.classe_code_court).all():
        rapport.nb_lignes_examinees += 1
        pre = tc.ou_pre_rentree or ""
        deff = tc.ou_definitive or ""
        rapport.nb_dans_un_nombre += len(noye.findall(pre)) + len(noye.findall(deff))
        for millesime in re.findall(r"(?<!\d)(20\d\d)(?!\d)", pre + " " + deff):
            rapport.annees_presentes[millesime] = (
                rapport.annees_presentes.get(millesime, 0) + 1
            )
        nouveau_pre = pre.replace(chercher, remplacer)
        nouveau_def = deff.replace(chercher, remplacer)
        if nouveau_pre == pre and nouveau_def == deff:
            continue

        rapport.nb_lignes_modifiees += 1
        rapport.lignes.append(
            LigneRenommee(
                id=tc.id,
                classe=tc.classe_code_court,
                site=noms_sites.get(tc.site_id),
                avant_pre_rentree=pre,
                apres_pre_rentree=nouveau_pre,
                avant_definitive=deff,
                apres_definitive=nouveau_def,
            )
        )
        if mode == "reel":
            tc.ou_pre_rentree = nouveau_pre
            tc.ou_definitive = nouveau_def

    if rapport.nb_dans_un_nombre:
        rapport.avertissements.append(
            f"{rapport.nb_dans_un_nombre} occurrence(s) de {chercher!r} sont "
            "prises dans une suite de chiffres plus longue et seront remplacées "
            "elles aussi. Vérifie l'aperçu ligne par ligne : ce n'est "
            "probablement pas un millésime."
        )

    # Une ligne épargnée n'est pas anodine : elle enverra sa classe dans
    # l'arbre de l'an dernier, sans que rien ne le signale ensuite.
    if rapport.nb_inchangees:
        declare = ", ".join(
            f"{a} ({n} chemins)" for a, n in sorted(rapport.annees_presentes.items())
        )
        if rapport.nb_lignes_modifiees == 0:
            rapport.avertissements.append(
                f"Aucun chemin ne contient {chercher!r} : rien n'a changé. "
                + (f"La Table déclare aujourd'hui {declare}." if declare
                   else "Aucun millésime n'apparaît dans les chemins.")
            )
        else:
            rapport.avertissements.append(
                f"{rapport.nb_inchangees} ligne(s) ne contiennent pas {chercher!r} "
                "et restent en l'état. Vérifie qu'elles visent bien la bonne "
                "année — une seule oubliée envoie toute une classe dans l'arbre "
                "précédent."
            )

    if mode == "reel":
        session.commit()
    else:
        session.rollback()
    return rapport
