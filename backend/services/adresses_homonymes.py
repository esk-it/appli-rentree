"""Deux personnes, une seule adresse : trancher avant que Google refuse.

## Le problème

L'adresse se calcule `prenom.nom@domaine`. Deux personnes du même prénom et
du même nom produisent donc la **même**. La règle des identifiants sait
s'en sortir depuis toujours — elle suffixe, `hguillou2` naît à côté de
`hguillou`. La règle des adresses ne le savait pas.

Sur l'instance réelle, deux Hugo GUILLOU sans lien — un en 1re à NDK, un
entrant en 6e à SU — se voyaient attribuer `hugo.guillou@lekreisker.fr`
tous les deux. L'export Google du collégien portait l'adresse du lycéen.
Google refuse une adresse déjà prise ; et il lui arrive de refuser le
fichier entier plutôt que la ligne, comme la colonne « Gemini Enterprise »
l'avait montré.

Le cas est rare — un seul sur 2 006 personnes — mais il est silencieux, et
il tombe le jour où l'on crée les comptes.

## Les deux numérotations sont indépendantes

On pourrait croire qu'il suffit de reprendre le suffixe de l'identifiant.
C'est faux, et les comptes réels le disent : `alix.cabioch2@` appartient à
`acabioch`, sans suffixe, et `jules.salaun@` appartient à `jsalaun1`. Un
identifiant se dispute sur `initiale+nom`, une adresse sur `prenom.nom` —
les collisions ne tombent pas aux mêmes endroits, et chaque espace
distribue ses numéros pour lui-même.

La maison écrit le suffixe collé au nom, sans séparateur :
`camille.hascoet2@`, `clemence.lebras1@`, `enora.creach2@`. On suit.

## Qui garde l'adresse sans suffixe

Celui dont le compte **existe déjà** : son adresse est constatée dans
Google, on ne va pas la lui changer. Si aucun des deux n'a de compte, le
plus ancien badge la garde — il faut une règle, autant qu'elle soit stable
d'une exécution à l'autre.

## Pourquoi c'est écrit, et pas recalculé

Un suffixe qui changerait d'un export au suivant créerait un second compte
au lieu de retrouver le premier. La décision est donc gardée dans
`email_attribuee`, et ne bouge plus.
"""
from __future__ import annotations

from dataclasses import dataclass, field

from sqlalchemy.orm import Session

from backend.models import AnneeScolaire, Personne, Snapshot

SUFFIXE_MAX = 50
"""Au-delà, on renonce plutôt que de tourner : cinquante homonymes stricts
signalent un problème de données, pas une famille nombreuse."""


@dataclass
class Homonymie:
    """Une adresse revendiquée par plusieurs personnes."""

    adresse: str
    garde_par: str
    """« Prénom NOM (badge) » — celui qui conserve l'adresse sans suffixe."""

    motif_du_choix: str
    a_trancher: list["AttributionProposee"] = field(default_factory=list)


@dataclass
class AttributionProposee:
    personne_id: int
    badge: int | None
    nom: str
    prenom: str
    login: str | None
    site: str | None
    adresse_actuelle: str
    adresse_proposee: str


@dataclass
class RapportHomonymes:
    nb_examines: int = 0
    homonymies: list[Homonymie] = field(default_factory=list)

    @property
    def nb_a_trancher(self) -> int:
        return sum(len(h.a_trancher) for h in self.homonymies)


def detecter_homonymies(
    session: Session,
    *,
    annee_id: int | None = None,
    adresses_google: set[str] | None = None,
) -> RapportHomonymes:
    """Repère les adresses que plusieurs personnes revendiquent.

    Args:
        annee_id: restreint aux personnes présentes cette année-là. `None` =
            la plus récente, celle qu'on prépare.
        adresses_google: adresses déjà ouvertes, principales et alias. Un
            suffixe libre au référentiel mais pris dans Google ne servirait
            à rien : la création échouerait pareillement.
    """
    if annee_id is None:
        annees = session.query(AnneeScolaire).all()
        annee_id = max(annees, key=lambda a: a.libelle).id if annees else None

    q = session.query(Personne)
    if annee_id is not None:
        ids = {
            pid
            for (pid,) in session.query(Snapshot.personne_id)
            .filter(Snapshot.annee_scolaire_id == annee_id)
            .distinct()
            .all()
        }
        q = q.filter(Personne.id.in_(ids))
    gens = q.all()

    par_adresse: dict[str, list[Personne]] = {}
    for p in gens:
        a = (p.email or "").strip().lower()
        if a:
            par_adresse.setdefault(a, []).append(p)

    # Tout ce qui est déjà pris, quelle que soit l'année : une adresse
    # libérée par un sortant n'est pas à recycler tant que son compte vit.
    prises = {
        (p.email or "").strip().lower()
        for p in session.query(Personne).all()
        if (p.email or "").strip()
    }
    prises |= {a.strip().lower() for a in (adresses_google or set()) if a}

    rapport = RapportHomonymes(nb_examines=len(gens))
    for adresse, gens_ici in sorted(par_adresse.items()):
        if len(gens_ici) < 2:
            continue
        garde, motif = _qui_garde(gens_ici)
        h = Homonymie(
            adresse=adresse,
            garde_par=f"{garde.prenom} {garde.nom} (badge {garde.badge})",
            motif_du_choix=motif,
        )
        for p in gens_ici:
            if p.id == garde.id:
                continue
            proposee = _prochaine_libre(adresse, prises)
            prises.add(proposee)
            h.a_trancher.append(
                AttributionProposee(
                    personne_id=p.id, badge=p.badge, nom=p.nom, prenom=p.prenom,
                    login=p.login, site=p.site.nom if p.site else None,
                    adresse_actuelle=adresse, adresse_proposee=proposee,
                )
            )
        rapport.homonymies.append(h)
    return rapport


def appliquer_attributions(
    session: Session, rapport: RapportHomonymes, *, mode: str = "simulation"
) -> int:
    """Écrit les adresses choisies. Renvoie le nombre attribué.

    Ne touche jamais `email_constate` : un compte qui existe garde son
    adresse, c'est là que la personne se connecte.
    """
    if mode not in ("simulation", "reel"):
        raise ValueError(f"mode invalide : {mode!r}")

    a_faire = [x for h in rapport.homonymies for x in h.a_trancher]
    if not a_faire:
        return 0

    gens = {
        p.id: p
        for p in session.query(Personne)
        .filter(Personne.id.in_([x.personne_id for x in a_faire]))
        .all()
    }
    n = 0
    for x in a_faire:
        p = gens.get(x.personne_id)
        if p is None or p.email_constate:
            continue
        p.email_attribuee = x.adresse_proposee
        n += 1

    if mode == "reel":
        session.commit()
    else:
        session.rollback()
    return n


# ---------------------------------------------------------------------------
# Détail
# ---------------------------------------------------------------------------


def _qui_garde(gens: list[Personne]) -> tuple[Personne, str]:
    """Celui dont le compte existe déjà, sinon le badge le plus ancien."""
    constates = [p for p in gens if p.email_constate]
    if len(constates) == 1:
        return constates[0], "son compte existe déjà sous cette adresse"
    if len(constates) > 1:
        # Deux comptes ouverts sur la même adresse est impossible dans
        # Google : l'un des deux la porte en alias. On garde le plus ancien
        # et on signale, plutôt que de trancher au hasard.
        gagnant = min(constates, key=lambda p: (p.badge or 0))
        return gagnant, "plusieurs comptes constatés — vérifie les alias"
    return (
        min(gens, key=lambda p: (p.badge or 0)),
        "aucun compte n'existe encore : le badge le plus ancien la garde",
    )


def _prochaine_libre(adresse: str, prises: set[str]) -> str:
    """`hugo.guillou@x.fr` → `hugo.guillou2@x.fr` si `…1` est pris.

    Le suffixe se colle au nom, sans séparateur — c'est la graphie des
    comptes existants : `camille.hascoet2@`, `clemence.lebras1@`.
    """
    locale, _, domaine = adresse.partition("@")
    for i in range(1, SUFFIXE_MAX + 1):
        candidate = f"{locale}{i}@{domaine}"
        if candidate not in prises:
            return candidate
    raise ValueError(
        f"Aucun suffixe libre pour {adresse} en dessous de {SUFFIXE_MAX}"
    )
