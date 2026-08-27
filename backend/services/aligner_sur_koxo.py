"""Aligner les identifiants du référentiel sur ceux que KoXo a retenus.

## Pourquoi ce geste existe

Le programme propose un identifiant, KoXo en décide. Il applique ses
propres règles — numérotation des homonymes à partir de 1, longueur
plafonnée à dix caractères, la base raccourcie pour faire place au
suffixe — et rien ne les lui impose de l'extérieur.

Quand elles diffèrent des nôtres, le compte naît sous un nom que le
référentiel ignore. C'est arrivé à la première synchronisation : deux
élèves proposés sous `mforbinsai2` et `lacquitter2`, onze caractères
chacun, ont été créés par KoXo sous un nom plus court. Le référentiel les
désigne encore par un identifiant qui n'existe nulle part.

Personne ne s'en apercevrait avant la rentrée suivante, où l'export
présenterait à KoXo des identifiants inconnus — et où la synchronisation
recréerait ou renommerait ces comptes.

## Le sens de la correction

C'est l'inverse de `rendre_identifiant`, et les deux se complètent :

- **Rendre** : le référentiel avait attribué à quelqu'un d'autre un
  identifiant que KoXo détenait déjà. On le remet à son détenteur.
- **Aligner** : KoXo a nommé un compte autrement que prévu. Le référentiel
  se range à ce qu'il constate.

Dans les deux cas, **la source fait autorité** — c'est la règle du
programme depuis le début, appliquée dans le sens qui convient.

## Ce que la fonction refuse

- **Un rapprochement par nom.** Seul l'ID unique relie une ligne à une
  personne ; c'est aussi la clé que KoXo utilise pour se reconnaître.
- **Un identifiant déjà porté** par quelqu'un d'autre au référentiel.
  L'aligner créerait un doublon là où on voulait lever une divergence : le
  cas est signalé, jamais tranché.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

from sqlalchemy.orm import Session

from backend.models import Personne


@dataclass
class Alignement:
    """Une divergence entre ce que KoXo détient et ce que le référentiel dit."""

    personne_id: int
    cle_pivot: str
    nom: str
    prenom: str
    badge: int
    login_referentiel: str
    login_koxo: str
    applicable: bool = True
    motif: str = ""
    """Renseigné quand l'alignement est refusé, avec sa raison."""


@dataclass
class RapportAlignement:
    fichier: str = ""
    site: str | None = None
    mode: str = "simulation"
    nb_lignes: int = 0
    nb_concordants: int = 0
    """Lignes dont l'identifiant est déjà celui du référentiel."""
    alignements: list[Alignement] = field(default_factory=list)
    avertissements: list[str] = field(default_factory=list)

    @property
    def nb_applicables(self) -> int:
        return sum(1 for a in self.alignements if a.applicable)

    @property
    def nb_bloques(self) -> int:
        return sum(1 for a in self.alignements if not a.applicable)


def aligner_sur_koxo(
    session: Session,
    chemin: str | Path,
    *,
    site: str | None = None,
    mode: str = "simulation",
) -> RapportAlignement:
    """Relit un export KoXo et range le référentiel sur ce qu'il constate.

    Args:
        chemin: l'export KoXo, pris **après** la synchronisation.
        site: le site dont vient cette base, pour la trace.
        mode: `simulation` ne commet rien.
    """
    if mode not in ("simulation", "reel"):
        raise ValueError(f"mode invalide : {mode!r}")

    from backend.services.controle_koxo import lire_export_brut

    lignes, _, _, _, _ = lire_export_brut(chemin)
    rapport = RapportAlignement(
        fichier=Path(chemin).name, site=site, mode=mode, nb_lignes=len(lignes)
    )

    par_badge = {p.badge: p for p in session.query(Personne).all() if p.badge}
    par_login = {p.login: p for p in session.query(Personne).all() if p.login}

    # Deux passes. La première recense les divergences ; la seconde décide
    # ce qui est applicable, car un identifiant occupé par quelqu'un qui
    # s'apprête lui-même à changer ne bloque rien : Julia et Jules MOAL
    # échangeaient `jmoal` et `jmoal2`, et se refusaient mutuellement.
    candidats: list[tuple[Personne, str]] = []
    for l in lignes:
        if not l.id_unique.isdigit() or not l.login:
            continue
        personne = par_badge.get(int(l.id_unique))
        if personne is None:
            continue
        if personne.login == l.login:
            rapport.nb_concordants += 1
            continue
        candidats.append((personne, l.login))

    # Les identifiants que ces personnes vont quitter.
    liberes = {p.login for p, _ in candidats if p.login}

    for personne, login_koxo in candidats:
        occupant = par_login.get(login_koxo)
        alignement = Alignement(
            personne_id=personne.id,
            cle_pivot=personne.cle_pivot,
            nom=personne.nom,
            prenom=personne.prenom,
            badge=personne.badge,
            login_referentiel=personne.login or "",
            login_koxo=login_koxo,
        )
        bloque = (
            occupant is not None
            and occupant.id != personne.id
            and occupant.login not in liberes
        )
        if bloque:
            alignement.applicable = False
            alignement.motif = (
                f"« {login_koxo} » est déjà l'identifiant de "
                f"{occupant.prenom} {occupant.nom} au référentiel, qui le "
                "garde. L'aligner créerait un doublon — vérifie d'abord de "
                "qui ce compte KoXo est celui."
            )
        rapport.alignements.append(alignement)

    if mode == "reel":
        # On libère avant d'attribuer : l'unicité est contrainte en base, et
        # deux lignes ne peuvent pas porter le même identifiant, fût-ce le
        # temps d'un flush.
        a_faire = [a for a in rapport.alignements if a.applicable]
        for a in a_faire:
            p = session.query(Personne).filter_by(id=a.personne_id).one()
            p.login = f"~{p.id}~"
        session.flush()
        for a in a_faire:
            p = session.query(Personne).filter_by(id=a.personne_id).one()
            p.login = a.login_koxo
        session.flush()

    if rapport.nb_bloques:
        rapport.avertissements.append(
            f"{rapport.nb_bloques} identifiant(s) ne peuvent pas être alignés "
            "sans créer un doublon au référentiel. Ils sont listés avec leur "
            "raison et n'ont pas été touchés."
        )
    return rapport
