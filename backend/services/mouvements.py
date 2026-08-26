"""Qui entre, qui sort, qui reste — pour une année donnée.

## Deux populations, deux sources

Le mouvement d'un **élève** se lit dans les photographies annuelles : il
entre s'il apparaît dans l'année sans figurer dans la précédente, il sort
s'il y figure sans apparaître dans la suivante. C'est déductible, et c'est
déduit.

Le mouvement d'un **adulte** ne s'y lit pas : les adultes n'ont pas de
photographie annuelle. Il vient du tableau des professeurs, où il est porté
par la couleur de la ligne — `arrivant`, `sortant`, `en_poste`. Sans ce
tableau chargé pour l'année demandée, le mouvement des adultes est
inconnu, et l'est dit.

## Ce qui n'est pas déductible n'est pas deviné

Les entrants d'une année se calculent contre l'année précédente ; ses
sortants contre la suivante. Quand l'année voisine n'a pas été ingérée, la
question n'a pas de réponse — et la mauvaise réponse serait spectaculaire :
sans année précédente, **tout le monde** paraîtrait entrant.

Le rapport porte donc, pour chaque sens, soit une liste, soit la raison
pour laquelle il n'y en a pas.
"""
from __future__ import annotations

from dataclasses import dataclass, field

from sqlalchemy.orm import Session

from backend.models import AnneeScolaire, MouvementProf, Personne, Snapshot
from backend.services.rapprochement import construire_index, rapprocher

MOUVEMENTS = ("entrant", "sortant", "present")

# Les codes du tableau des professeurs, traduits en mouvement. Ceux qui n'y
# figurent pas — `formation`, `remplace`, `inconnu` — décrivent une
# situation, pas une entrée ni une sortie : la personne est là.
CODE_VERS_MOUVEMENT = {"arrivant": "entrant", "sortant": "sortant"}


@dataclass
class LigneMouvement:
    """Une personne, et ce qu'elle fait cette année-là."""

    mouvement: str
    """`entrant`, `sortant` ou `present`."""
    nom: str
    prenom: str
    personne_id: int | None = None
    """`None` quand la ligne vient du tableau des professeurs et qu'aucune
    personne du référentiel ne lui correspond — un arrivant sans compte,
    typiquement. C'est une information, pas une anomalie."""
    cle_pivot: str | None = None
    login: str | None = None
    email: str | None = None
    badge: int | None = None
    type: str = ""
    site: str | None = None
    classe: str | None = None
    """Classe de l'année demandée, pour un élève."""
    classe_precedente: str | None = None
    classe_suivante: str | None = None
    discipline: str | None = None
    """Matière, pour un adulte."""
    detail: str = ""
    """La phrase qui résume le mouvement : « 2_1 → 1_G1 », « remplace
    Morgane CLOITRE », « arrivant sans compte au référentiel »."""
    methode_rapprochement: str | None = None
    """Comment la ligne du tableau a été reliée au référentiel, quand elle
    l'a été autrement que par égalité stricte."""


@dataclass
class RapportMouvements:
    annee: str = ""
    type_personne: str = ""
    source: str = ""
    """`photographies annuelles` ou `tableau des professeurs`."""
    annee_precedente: str | None = None
    annee_suivante: str | None = None
    lignes: list[LigneMouvement] = field(default_factory=list)
    entrants_connus: bool = True
    sortants_connus: bool = True
    raisons: dict[str, str] = field(default_factory=dict)
    """Pour `entrant` et `sortant`, pourquoi la liste ne peut pas être
    établie — vide quand elle le peut."""

    @property
    def nb_par_mouvement(self) -> dict[str, int]:
        compte = {m: 0 for m in MOUVEMENTS}
        for l in self.lignes:
            compte[l.mouvement] = compte.get(l.mouvement, 0) + 1
        return compte


def _annees_triees(session: Session) -> list[AnneeScolaire]:
    """Par libellé : `2025-2026` précède `2026-2027`, et le tri le sait."""
    return sorted(session.query(AnneeScolaire).all(), key=lambda a: a.libelle)


def _voisines(
    session: Session, annee_id: int
) -> tuple[AnneeScolaire | None, AnneeScolaire, AnneeScolaire | None]:
    annees = _annees_triees(session)
    for i, a in enumerate(annees):
        if a.id == annee_id:
            return (
                annees[i - 1] if i > 0 else None,
                a,
                annees[i + 1] if i + 1 < len(annees) else None,
            )
    raise ValueError(f"Année introuvable : {annee_id}")


def _classes_par_personne(session: Session, annee_id: int) -> dict[int, str]:
    """La classe de chacun pour une année. Le dernier snapshot fait foi."""
    classes: dict[int, str] = {}
    for s in (
        session.query(Snapshot)
        .filter(Snapshot.annee_scolaire_id == annee_id)
        .order_by(Snapshot.id)
    ):
        if s.classe:
            classes[s.personne_id] = s.classe
    return classes


def mouvements_annee(
    session: Session,
    *,
    annee_id: int,
    type_personne: str,
    site: str | None = None,
) -> RapportMouvements:
    """Le mouvement de chaque personne d'une population, pour une année.

    Args:
        annee_id: l'année observée.
        type_personne: `eleve` ou `adulte` — ils ne se lisent pas dans la
            même source.
        site: code de site (`NDE`, `NDK`, `SU`), pour restreindre.
    """
    if type_personne not in ("eleve", "adulte"):
        raise ValueError(f"type_personne invalide : {type_personne!r}")

    precedente, annee, suivante = _voisines(session, annee_id)
    rapport = RapportMouvements(
        annee=annee.libelle,
        type_personne=type_personne,
        annee_precedente=precedente.libelle if precedente else None,
        annee_suivante=suivante.libelle if suivante else None,
    )

    if type_personne == "eleve":
        _mouvements_eleves(session, rapport, precedente, annee, suivante)
    else:
        _mouvements_adultes(session, rapport, annee)

    if site:
        rapport.lignes = [l for l in rapport.lignes if l.site == site]
    rapport.lignes.sort(key=lambda l: (l.nom.lower(), l.prenom.lower()))
    return rapport


# ---------------------------------------------------------------------------
# Élèves — déduits des photographies annuelles
# ---------------------------------------------------------------------------


def _mouvements_eleves(session, rapport, precedente, annee, suivante) -> None:
    from backend.services.rattachement import ids_presents_annee

    rapport.source = "photographies annuelles"

    presents = ids_presents_annee(
        session, annee_id=annee.id, type_personne="eleve"
    )
    avant = (
        ids_presents_annee(session, annee_id=precedente.id, type_personne="eleve")
        if precedente
        else set()
    )
    apres = (
        ids_presents_annee(session, annee_id=suivante.id, type_personne="eleve")
        if suivante
        else set()
    )

    if precedente is None:
        rapport.entrants_connus = False
        rapport.raisons["entrant"] = (
            f"L'année qui précède {annee.libelle} n'a pas été ingérée. Sans "
            "elle, rien ne distingue un entrant d'un élève déjà là — ils "
            "paraîtraient tous nouveaux."
        )
    if suivante is None:
        rapport.sortants_connus = False
        rapport.raisons["sortant"] = (
            f"L'année qui suit {annee.libelle} n'a pas été ingérée. Un départ "
            "se constate en ne retrouvant pas l'élève l'année d'après : tant "
            "qu'elle manque, la question reste ouverte."
        )

    classes = _classes_par_personne(session, annee.id)
    classes_avant = _classes_par_personne(session, precedente.id) if precedente else {}
    classes_apres = _classes_par_personne(session, suivante.id) if suivante else {}

    gens = {
        p.id: p
        for p in session.query(Personne).filter(Personne.type == "eleve").all()
    }

    for pid in presents:
        p = gens.get(pid)
        if p is None:
            continue

        if rapport.entrants_connus and pid not in avant:
            mouvement = "entrant"
        elif rapport.sortants_connus and pid not in apres:
            mouvement = "sortant"
        else:
            mouvement = "present"

        ici = classes.get(pid)
        avant_c = classes_avant.get(pid)
        apres_c = classes_apres.get(pid)

        if mouvement == "entrant":
            detail = f"entre en {ici}" if ici else "entrant"
        elif mouvement == "sortant":
            detail = f"quitte la {ici}" if ici else "sortant"
        elif avant_c and ici and avant_c != ici:
            detail = f"{avant_c} → {ici}"
        elif ici:
            detail = f"reste en {ici}"
        else:
            detail = ""

        rapport.lignes.append(
            LigneMouvement(
                mouvement=mouvement,
                personne_id=p.id,
                cle_pivot=p.cle_pivot,
                nom=p.nom,
                prenom=p.prenom,
                login=p.login,
                email=p.email_constate,
                badge=p.badge,
                type="eleve",
                site=p.site.nom if p.site else None,
                classe=ici,
                classe_precedente=avant_c,
                classe_suivante=apres_c,
                detail=detail,
            )
        )


# ---------------------------------------------------------------------------
# Adultes — lus dans le tableau des professeurs
# ---------------------------------------------------------------------------


def _mouvements_adultes(session, rapport, annee) -> None:
    rapport.source = "tableau des professeurs"

    lignes = (
        session.query(MouvementProf)
        .filter(MouvementProf.annee_scolaire_id == annee.id)
        .all()
    )
    if not lignes:
        rapport.entrants_connus = False
        rapport.sortants_connus = False
        raison = (
            f"Aucun tableau des professeurs n'a été chargé pour {annee.libelle}. "
            "Le mouvement des adultes s'y lit — il ne se déduit pas des "
            "photographies annuelles, que les adultes n'ont pas."
        )
        rapport.raisons["entrant"] = raison
        rapport.raisons["sortant"] = raison
        return

    adultes = session.query(Personne).filter(Personne.type == "adulte").all()
    par_id = {p.id: p for p in adultes}
    index = construire_index(
        [{"email": str(p.id), "nom": p.nom, "prenom": p.prenom} for p in adultes]
    )

    for l in lignes:
        r = rapprocher(l.nom, l.prenom, index)
        p = par_id.get(int(r.email)) if r.trouve else None

        mouvement = CODE_VERS_MOUVEMENT.get(l.code, "present")

        if l.remplace_nom:
            detail = f"remplace {l.remplace_prenom or ''} {l.remplace_nom}".strip()
        elif mouvement == "entrant" and p is None:
            # Le cas le plus fréquent, et le plus utile à voir : un
            # arrivant n'a pas encore de compte, c'est précisément ce qui
            # reste à faire pour lui.
            detail = "arrivant sans compte au référentiel"
        elif l.libelle:
            detail = l.libelle
        else:
            detail = l.code

        rapport.lignes.append(
            LigneMouvement(
                mouvement=mouvement,
                personne_id=p.id if p else None,
                cle_pivot=p.cle_pivot if p else None,
                nom=l.nom,
                prenom=l.prenom,
                login=p.login if p else None,
                email=(p.email_constate if p else None),
                badge=p.badge if p else None,
                type="adulte",
                site=(p.site.nom if p and p.site else None),
                discipline=l.discipline,
                detail=detail,
                methode_rapprochement=(
                    r.methode if r.trouve and r.methode != "exact" else None
                ),
            )
        )
