"""Le parc : ce qui marche, ce qui dort, ce qui est mort et ce qu'on en tire.

## La question que ce module existe pour répondre

« J'ai une machine morte de la batterie et une autre morte du clavier —
est-ce que je peux en refaire une ? » Personne ne peut y répondre depuis un
tableau de machines : il faut croiser les **organes**, et c'est ce que fait
`analyser_atelier`.

C'est aussi pourquoi une panne désigne un organe pris dans une liste
fermée. Deux notes libres ne se croisent pas.

## La politique de remontage

Réparer une machine consomme des donneuses, et une donneuse sacrifiée ne
sera jamais réparée. Il faut donc choisir, et le choix retenu est le plus
simple à défendre : **on répare d'abord celles qui ont le moins de pannes**,
en prélevant sur celles qui en ont le plus. Une machine à qui il manque un
clavier vaut mieux qu'une machine à qui il manque un écran, un clavier et
une charnière — la seconde finira donneuse de toute façon.

Deux organes ne se croisent pas :

- `autre`, parce que deux « autre » ne font pas une pièce. Une machine qui
  en porte une n'est pas déclarée remontable, elle est signalée à part ;
- `carte_mere` se croise comme les autres, mais une machine qui en manque
  n'a plus grand-chose d'utile à donner — ce n'est pas au programme de le
  décider, il le montre et l'on tranche.

## Ce que le module ne fait pas

Il ne répare rien tout seul. `analyser_atelier` est en lecture seule et
propose ; `prelever` est le geste, et il faut le demander. La proposition
n'est qu'un plan sur le papier : c'est le tournevis qui décide.
"""
from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass, field
from datetime import date

from sqlalchemy.orm import Session

from backend.models import Accessoire, PanneChromebook, PretAccessoire, SuiviChromebook
from backend.models.parc_materiel import (
    ETATS_ACCESSOIRE,
    ETATS_MACHINE,
    ORGANES,
    RESOLUTIONS,
    TYPES_ACCESSOIRE,
)

ORGANES_NON_CROISABLES = {"autre"}
"""Organes qui ne comptent pas comme une pièce interchangeable."""


class GesteImpossible(Exception):
    """Le geste est refusé, et le message dit pourquoi."""


# ---------------------------------------------------------------------------
# État du parc
# ---------------------------------------------------------------------------


@dataclass
class Machine:
    serie: str
    etat: str
    etat_depuis: date | None = None
    attribue_a: str | None = None
    attribue_le: date | None = None
    note: str | None = None
    pannes_ouvertes: list[str] = field(default_factory=list)
    """Organes morts, non encore résolus."""

    @property
    def reparable_sur_le_papier(self) -> bool:
        """Aucune panne d'organe non croisable ne la condamne d'avance."""
        return not (set(self.pannes_ouvertes) & ORGANES_NON_CROISABLES)


@dataclass
class SynthesesParEtat:
    en_service: int = 0
    en_stock: int = 0
    hs: int = 0
    reforme: int = 0


def etat_du_parc(session: Session) -> tuple[list[Machine], SynthesesParEtat]:
    """Toutes les machines suivies, avec leurs pannes ouvertes.

    Lecture seule. Ne lit que la base : l'inventaire Google est un autre
    sujet, et les deux se recoupent dans l'écran, pas ici.
    """
    pannes: dict[str, list[str]] = defaultdict(list)
    for p in session.query(PanneChromebook).filter(PanneChromebook.resolue_le.is_(None)):
        pannes[p.serie].append(p.organe)

    machines = [
        Machine(
            serie=m.serie,
            etat=m.etat or "en_service",
            etat_depuis=m.etat_depuis,
            attribue_a=m.attribue_a,
            attribue_le=m.attribue_le,
            note=m.note,
            pannes_ouvertes=sorted(pannes.get(m.serie, [])),
        )
        for m in session.query(SuiviChromebook).order_by(SuiviChromebook.serie)
    ]

    synthese = SynthesesParEtat()
    for m in machines:
        if hasattr(synthese, m.etat):
            setattr(synthese, m.etat, getattr(synthese, m.etat) + 1)
    return machines, synthese


# ---------------------------------------------------------------------------
# L'atelier : ce qu'on peut remonter
# ---------------------------------------------------------------------------


@dataclass
class Remontage:
    """Une machine réparable, et sur quoi prélever pour y arriver."""

    serie: str
    organes_manquants: list[str]
    donneurs: dict[str, str]
    """`{organe: série de la machine qui le fournit}`."""


@dataclass
class Atelier:
    machines_hs: list[Machine] = field(default_factory=list)
    remontages: list[Remontage] = field(default_factory=list)
    organes_disponibles: dict[str, int] = field(default_factory=dict)
    """Combien de machines HS portent encore cet organe intact."""

    bloquees: list[tuple[str, list[str]]] = field(default_factory=list)
    """`(série, organes introuvables)` — rien dans la réserve ne les couvre."""

    @property
    def nb_remontables(self) -> int:
        return len(self.remontages)


def analyser_atelier(session: Session) -> Atelier:
    """Ce que la réserve permet de remonter. Ne modifie rien.

    Une machine est *remontable* si chacune de ses pannes ouvertes trouve,
    sur une autre machine HS, le même organe intact — et si ce donneur n'a
    pas déjà été promis à une autre réparation.
    """
    machines, _ = etat_du_parc(session)
    hs = [m for m in machines if m.etat == "hs"]

    # Qui porte encore quoi. Un organe est « intact » sur une machine HS
    # quand aucune panne ouverte ne le désigne.
    intacts: dict[str, list[str]] = defaultdict(list)
    for m in hs:
        morts = set(m.pannes_ouvertes)
        for organe in ORGANES:
            if organe in ORGANES_NON_CROISABLES or organe in morts:
                continue
            intacts[organe].append(m.serie)

    atelier = Atelier(
        machines_hs=hs,
        organes_disponibles={o: len(v) for o, v in sorted(intacts.items()) if v},
    )

    # Les moins abîmées d'abord : ce sont celles qui coûtent le moins de
    # pièces, et chaque réparation consomme la réserve des suivantes.
    candidates = sorted(
        (m for m in hs if m.pannes_ouvertes),
        key=lambda m: (len(m.pannes_ouvertes), m.serie),
    )
    promis: set[tuple[str, str]] = set()  # (organe, donneur) déjà engagés
    sacrifiees: set[str] = set()

    for m in candidates:
        if m.serie in sacrifiees:
            continue
        if not m.reparable_sur_le_papier:
            atelier.bloquees.append(
                (m.serie, sorted(set(m.pannes_ouvertes) & ORGANES_NON_CROISABLES))
            )
            continue

        choix: dict[str, str] = {}
        manquants: list[str] = []
        for organe in m.pannes_ouvertes:
            donneur = next(
                (
                    d
                    for d in intacts.get(organe, [])
                    if d != m.serie
                    and d not in sacrifiees
                    and (organe, d) not in promis
                    # On ne démonte pas une machine qu'on vient de réparer.
                    and d not in {r.serie for r in atelier.remontages}
                ),
                None,
            )
            if donneur is None:
                manquants.append(organe)
            else:
                choix[organe] = donneur

        if manquants:
            atelier.bloquees.append((m.serie, manquants))
            continue

        atelier.remontages.append(
            Remontage(
                serie=m.serie,
                organes_manquants=list(m.pannes_ouvertes),
                donneurs=choix,
            )
        )
        for organe, donneur in choix.items():
            promis.add((organe, donneur))
            sacrifiees.add(donneur)

    return atelier


# ---------------------------------------------------------------------------
# Les gestes
# ---------------------------------------------------------------------------


def changer_etat(
    session: Session, serie: str, etat: str, *, note: str | None = None
) -> SuiviChromebook:
    """Pose l'état d'une machine, en créant son suivi s'il n'existe pas."""
    if etat not in ETATS_MACHINE:
        raise GesteImpossible(f"État inconnu : {etat!r}. Attendu : {ETATS_MACHINE}.")
    m = _machine(session, serie, creer=True)
    m.etat = etat
    m.etat_depuis = date.today()
    if note is not None:
        m.note = note
    session.commit()
    return m


def affecter(
    session: Session,
    serie: str,
    *,
    a: str | None,
    depuis: date | None = None,
    note: str | None = None,
) -> SuiviChromebook:
    """Confie une machine à quelqu'un, ou la reprend.

    ## Pourquoi l'état suit l'affectation, et non l'inverse

    « Confiée à quelqu'un » et « disponible » ne sont pas deux informations
    à tenir séparément : l'une est la conséquence de l'autre. Les laisser
    indépendantes, c'est permettre une machine `en_stock` attribuée à un
    prof — état que rien ne contredit et que personne ne remarque, jusqu'au
    jour où on la cherche dans l'armoire.

    Une machine **hors service** fait exception : la reprendre ne la rend
    pas disponible. On la récupère du prof, elle reste HS, et c'est
    l'atelier qui décidera de la suite.

    Args:
        a: à qui — `None` pour reprendre la machine.
        depuis: la date d'affectation, aujourd'hui par défaut. Une machine
            confiée en septembre et saisie en novembre garde septembre.

    Raises:
        GesteImpossible: numéro de série vide.
    """
    if not (serie or "").strip():
        raise GesteImpossible("Un numéro de série est requis.")

    m = _machine(session, serie, creer=True)
    porteur = (a or "").strip() or None

    m.attribue_a = porteur
    m.attribue_le = (depuis or date.today()) if porteur else None
    if note is not None:
        m.note = note

    if m.etat not in ("hs", "reforme"):
        nouvel_etat = "en_service" if porteur else "en_stock"
        if m.etat != nouvel_etat:
            m.etat = nouvel_etat
            m.etat_depuis = date.today()

    session.commit()
    return m


def declarer_panne(
    session: Session,
    serie: str,
    organe: str,
    *,
    note: str | None = None,
    passer_hs: bool = True,
) -> PanneChromebook:
    """Note un organe mort. Passe la machine en HS, sauf demande contraire.

    Une machine qui perd un organe cesse d'être utilisable — sauf pour les
    cas où l'on veut consigner un défaut sans retirer la machine du service
    (une charnière fendue qui tient encore).
    """
    if organe not in ORGANES:
        raise GesteImpossible(f"Organe inconnu : {organe!r}. Attendu : {ORGANES}.")
    deja = (
        session.query(PanneChromebook)
        .filter(
            PanneChromebook.serie == serie,
            PanneChromebook.organe == organe,
            PanneChromebook.resolue_le.is_(None),
        )
        .first()
    )
    if deja is not None:
        raise GesteImpossible(
            f"{serie} a déjà une panne ouverte sur « {organe} » — "
            "la résoudre avant d'en déclarer une autre."
        )

    panne = PanneChromebook(
        serie=serie, organe=organe, constatee_le=date.today(), note=note
    )
    session.add(panne)
    m = _machine(session, serie, creer=True)
    if passer_hs and m.etat != "hs":
        m.etat = "hs"
        m.etat_depuis = date.today()
    session.commit()
    return panne


def prelever(
    session: Session,
    *,
    depuis: str,
    vers: str,
    organe: str,
    note: str | None = None,
) -> tuple[PanneChromebook, PanneChromebook]:
    """Prend un organe sur une machine pour en réparer une autre.

    **Deux écritures, un seul geste.** La panne de la receveuse est résolue
    en `piece_prelevee` côté donneuse, et la donneuse gagne une panne sur
    l'organe parti. C'est la seconde qu'on oublie quand on note à la main,
    et l'oublier fait mentir la réserve en quelques mois.

    Si la receveuse n'a plus aucune panne ouverte après coup, elle repasse
    en stock : elle remarche, et la laisser en HS la garderait invisible.

    Returns:
        `(panne résolue chez la receveuse, panne créée chez la donneuse)`
    """
    if depuis == vers:
        raise GesteImpossible("Une machine ne se prélève pas sur elle-même.")
    if organe not in ORGANES:
        raise GesteImpossible(f"Organe inconnu : {organe!r}.")

    a_reparer = (
        session.query(PanneChromebook)
        .filter(
            PanneChromebook.serie == vers,
            PanneChromebook.organe == organe,
            PanneChromebook.resolue_le.is_(None),
        )
        .first()
    )
    if a_reparer is None:
        raise GesteImpossible(
            f"{vers} n'a pas de panne ouverte sur « {organe} » : "
            "il n'y a rien à y remplacer."
        )

    deja_mort = (
        session.query(PanneChromebook)
        .filter(
            PanneChromebook.serie == depuis,
            PanneChromebook.organe == organe,
            PanneChromebook.resolue_le.is_(None),
        )
        .first()
    )
    if deja_mort is not None:
        raise GesteImpossible(
            f"{depuis} a déjà « {organe} » en panne : il n'y a rien à en tirer."
        )

    aujourdhui = date.today()
    a_reparer.resolue_le = aujourdhui
    a_reparer.resolution = "piece_prelevee"
    a_reparer.prelevee_pour = None

    manque = PanneChromebook(
        serie=depuis,
        organe=organe,
        constatee_le=aujourdhui,
        prelevee_pour=vers,
        note=note or f"Pièce prélevée pour {vers}",
    )
    session.add(manque)

    donneuse = _machine(session, depuis, creer=True)
    if donneuse.etat != "hs":
        donneuse.etat = "hs"
        donneuse.etat_depuis = aujourdhui

    session.flush()
    restantes = (
        session.query(PanneChromebook)
        .filter(
            PanneChromebook.serie == vers, PanneChromebook.resolue_le.is_(None)
        )
        .count()
    )
    receveuse = _machine(session, vers, creer=True)
    if restantes == 0 and receveuse.etat == "hs":
        receveuse.etat = "en_stock"
        receveuse.etat_depuis = aujourdhui

    session.commit()
    return a_reparer, manque


def resoudre_panne(
    session: Session, panne_id: int, resolution: str = "reparee"
) -> PanneChromebook:
    """Ferme une panne autrement que par un prélèvement."""
    if resolution not in RESOLUTIONS:
        raise GesteImpossible(f"Résolution inconnue : {resolution!r}.")
    panne = session.query(PanneChromebook).filter_by(id=panne_id).one_or_none()
    if panne is None:
        raise GesteImpossible(f"Panne {panne_id} introuvable.")
    if panne.resolue_le is not None:
        raise GesteImpossible("Cette panne est déjà résolue.")

    panne.resolue_le = date.today()
    panne.resolution = resolution
    session.flush()

    restantes = (
        session.query(PanneChromebook)
        .filter(
            PanneChromebook.serie == panne.serie,
            PanneChromebook.resolue_le.is_(None),
        )
        .count()
    )
    m = _machine(session, panne.serie, creer=True)
    if restantes == 0 and m.etat == "hs" and resolution == "reparee":
        m.etat = "en_stock"
        m.etat_depuis = date.today()
    session.commit()
    return panne


def _machine(session: Session, serie: str, *, creer: bool = False) -> SuiviChromebook:
    m = session.query(SuiviChromebook).filter_by(serie=serie).one_or_none()
    if m is None:
        if not creer:
            raise GesteImpossible(f"Machine inconnue : {serie}.")
        m = SuiviChromebook(serie=serie, etat="en_service")
        session.add(m)
        session.flush()
    return m


# ---------------------------------------------------------------------------
# Accessoires et prêts
# ---------------------------------------------------------------------------


@dataclass
class AccessoireEnMain:
    serie: str
    type: str
    etat: str
    note: str | None = None
    prete_a: str | None = None
    prete_le: date | None = None
    retour_prevu_le: date | None = None
    pret_id: int | None = None

    @property
    def en_retard(self) -> bool:
        return (
            self.retour_prevu_le is not None
            and self.prete_a is not None
            and self.retour_prevu_le < date.today()
        )


@dataclass
class Stock:
    accessoires: list[AccessoireEnMain] = field(default_factory=list)
    par_type: dict[str, dict[str, int]] = field(default_factory=dict)
    """`{type: {état: nombre}}` — « combien de chargeurs me reste-t-il ? »."""

    @property
    def en_retard(self) -> list[AccessoireEnMain]:
        return [a for a in self.accessoires if a.en_retard]


def etat_du_stock(session: Session) -> Stock:
    """Les accessoires, et pour ceux qui sont dehors, chez qui. Lecture seule."""
    prets_en_cours = {
        p.accessoire_serie: p
        for p in session.query(PretAccessoire).filter(PretAccessoire.rendu_le.is_(None))
    }

    stock = Stock()
    par_type: dict[str, dict[str, int]] = defaultdict(lambda: defaultdict(int))
    for a in session.query(Accessoire).order_by(Accessoire.type, Accessoire.serie):
        pret = prets_en_cours.get(a.serie)
        stock.accessoires.append(
            AccessoireEnMain(
                serie=a.serie,
                type=a.type,
                etat=a.etat,
                note=a.note,
                prete_a=pret.prete_a if pret else None,
                prete_le=pret.prete_le if pret else None,
                retour_prevu_le=pret.retour_prevu_le if pret else None,
                pret_id=pret.id if pret else None,
            )
        )
        par_type[a.type][a.etat] += 1
    stock.par_type = {t: dict(e) for t, e in par_type.items()}
    return stock


def enregistrer_accessoire(
    session: Session,
    serie: str,
    *,
    type_accessoire: str = "chargeur",
    note: str | None = None,
) -> Accessoire:
    if type_accessoire not in TYPES_ACCESSOIRE:
        raise GesteImpossible(f"Type inconnu : {type_accessoire!r}.")
    serie = (serie or "").strip()
    if not serie:
        raise GesteImpossible("Un accessoire se note par son numéro de série.")
    if session.query(Accessoire).filter_by(serie=serie).first() is not None:
        raise GesteImpossible(f"{serie} est déjà enregistré.")

    a = Accessoire(serie=serie, type=type_accessoire, etat="en_stock", note=note)
    session.add(a)
    session.commit()
    return a


def preter(
    session: Session,
    serie: str,
    *,
    a_qui: str,
    retour_prevu_le: date | None = None,
    note: str | None = None,
) -> PretAccessoire:
    """Sort un accessoire. Refuse ce qui est déjà dehors ou hors service."""
    a = session.query(Accessoire).filter_by(serie=serie).one_or_none()
    if a is None:
        raise GesteImpossible(f"Accessoire inconnu : {serie}.")
    if a.etat == "prete":
        dehors = (
            session.query(PretAccessoire)
            .filter(
                PretAccessoire.accessoire_serie == serie,
                PretAccessoire.rendu_le.is_(None),
            )
            .first()
        )
        chez = f" — il est chez {dehors.prete_a}" if dehors else ""
        raise GesteImpossible(f"{serie} est déjà prêté{chez}.")
    if a.etat in ("hs", "reforme"):
        raise GesteImpossible(f"{serie} est {a.etat} : il n'y a pas lieu de le prêter.")
    if not (a_qui or "").strip():
        raise GesteImpossible("Un prêt se fait à quelqu'un.")

    pret = PretAccessoire(
        accessoire_serie=serie,
        prete_a=a_qui.strip(),
        prete_le=date.today(),
        retour_prevu_le=retour_prevu_le,
        note=note,
    )
    session.add(pret)
    a.etat = "prete"
    session.commit()
    return pret


def rendre(session: Session, serie: str, *, etat: str = "en_stock") -> PretAccessoire:
    """Referme le prêt en cours. L'objet peut revenir cassé."""
    if etat not in ETATS_ACCESSOIRE or etat == "prete":
        raise GesteImpossible(f"État de retour invalide : {etat!r}.")
    pret = (
        session.query(PretAccessoire)
        .filter(
            PretAccessoire.accessoire_serie == serie,
            PretAccessoire.rendu_le.is_(None),
        )
        .first()
    )
    if pret is None:
        raise GesteImpossible(f"{serie} n'est pas en prêt.")

    pret.rendu_le = date.today()
    a = session.query(Accessoire).filter_by(serie=serie).one_or_none()
    if a is not None:
        a.etat = etat
    session.commit()
    return pret
