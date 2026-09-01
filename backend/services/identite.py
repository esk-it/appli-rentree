"""Corriger le nom ou le prénom de quelqu'un au référentiel.

## Pourquoi ce geste manquait

Le référentiel se remplit par ingestion : ce que Charlemagne écrit fait
foi, et il n'y avait aucun moyen de le contredire. Or il se trompe, ou il
est en retard. Un professeur inscrit sous « Efflam » se prénomme
« Imhotep » ; le compte Google a été corrigé le jour même, le référentiel
est resté sur l'ancien, et chaque export le réécrivait.

## Ce que change un renommage, et ce qu'il ne change pas

**Les exports suivent.** Les colonnes Nom et Prénom viennent de la
personne, pas de la photographie : KoXo mettra le compte à jour à la
prochaine synchronisation, sans le déplacer ni le renommer.

**L'adresse calculée suit aussi**, et c'est souvent le but :
`efflam.parmentier@` devient `imhotep.parmentier@`, qui est précisément
l'adresse principale que porte le compte Google. Sauf si une adresse est
**constatée** ou **attribuée** — celles-là ont été décidées, et un
changement de prénom n'a pas à les défaire.

**L'identifiant ne bouge pas.** `eparmentie` est ce que KoXo détient, et
le référentiel le recopie dans l'export : le changer présenterait à la
synchronisation un identifiant inconnu, qui renommerait le compte de
l'annuaire — répertoire personnel et profil compris. Renommer un compte
Windows n'est pas une correction d'orthographe. Si l'identifiant doit
vraiment changer, cela se fait dans KoXo, et le Contrôle le reprend.

## Ce qui l'écrasera

Une réingestion Charlemagne réécrit nom et prénom depuis la source. Tant
que Charlemagne dit « Efflam », la correction est à refaire. La seule
réparation durable est en amont — le programme le dit plutôt que de le
laisser découvrir.
"""
from __future__ import annotations

from dataclasses import dataclass, field

from sqlalchemy.orm import Session

from backend.models import Personne


class ModificationImpossible(Exception):
    """Ce qui empêche la correction, dit avant d'écrire."""


@dataclass
class RapportIdentite:
    personne_id: int
    nom_avant: str
    prenom_avant: str
    nom_apres: str
    prenom_apres: str
    login: str
    """Inchangé — il appartient à la base KoXo."""

    email_avant: str | None = None
    email_apres: str | None = None
    changements: list[str] = field(default_factory=list)
    reste_a_faire: list[str] = field(default_factory=list)

    @property
    def a_change(self) -> bool:
        return bool(self.changements)


def modifier_identite(
    session: Session,
    personne_id: int,
    *,
    nom: str | None = None,
    prenom: str | None = None,
    mode: str = "simulation",
) -> RapportIdentite:
    """Corrige le nom et/ou le prénom. Ne touche ni l'identifiant ni le badge.

    Args:
        nom, prenom: la nouvelle valeur, ou `None` pour ne pas y toucher.
        mode: `simulation` n'écrit rien et sert à montrer les conséquences.
    """
    if mode not in ("simulation", "reel"):
        raise ValueError(f"mode invalide : {mode!r}")

    p = session.query(Personne).filter_by(id=personne_id).one_or_none()
    if p is None:
        raise ModificationImpossible(f"Personne introuvable : {personne_id}")

    nom_apres = (nom if nom is not None else p.nom) or ""
    prenom_apres = (prenom if prenom is not None else p.prenom) or ""
    nom_apres, prenom_apres = nom_apres.strip(), prenom_apres.strip()
    if not nom_apres or not prenom_apres:
        raise ModificationImpossible(
            "Le nom et le prénom sont l'un et l'autre requis."
        )

    rapport = RapportIdentite(
        personne_id=p.id,
        nom_avant=p.nom or "", prenom_avant=p.prenom or "",
        nom_apres=nom_apres, prenom_apres=prenom_apres,
        login=p.login or "",
        email_avant=p.email,
    )

    if nom_apres != (p.nom or ""):
        rapport.changements.append(f"Nom : « {p.nom} » → « {nom_apres} »")
    if prenom_apres != (p.prenom or ""):
        rapport.changements.append(f"Prénom : « {p.prenom} » → « {prenom_apres} »")
    if not rapport.changements:
        rapport.email_apres = rapport.email_avant
        return rapport

    ancien_nom, ancien_prenom = p.nom, p.prenom
    p.nom, p.prenom = nom_apres, prenom_apres
    rapport.email_apres = p.email
    if not (mode == "reel"):
        p.nom, p.prenom = ancien_nom, ancien_prenom

    if rapport.email_apres != rapport.email_avant:
        rapport.changements.append(
            f"Adresse calculée : « {rapport.email_avant} » → "
            f"« {rapport.email_apres} »"
        )
        rapport.reste_a_faire.append(
            "Vérifie que cette adresse est bien celle du compte Google — "
            "Conformité → Adresses la confrontera à ce que Google détient."
        )
    elif p.email_constate or p.email_attribuee:
        origine = "constatée dans Google" if p.email_constate else "attribuée à la main"
        rapport.reste_a_faire.append(
            f"L'adresse « {rapport.email_avant} » est {origine} : elle ne suit "
            "pas le changement de nom. Corrige-la à part si elle doit changer."
        )

    rapport.reste_a_faire.append(
        f"L'identifiant « {p.login} » ne change pas : c'est celui que KoXo "
        "détient, et le modifier ici ferait renommer le compte de l'annuaire "
        "à la prochaine synchronisation."
    )
    rapport.reste_a_faire.append(
        "Une réingestion Charlemagne réécrira nom et prénom depuis la source : "
        "fais corriger Charlemagne, sinon la correction sera à refaire."
    )

    if mode == "reel":
        session.commit()
    else:
        session.rollback()
    return rapport
