"""L'inventaire du parc : chaque Chromebook, où il est, et les gestes qui le déplacent.

## D'où vient la liste

De Google, et de nulle part ailleurs : la console connaît les 570 machines
de l'établissement, avec leur unité d'organisation, leur étiquette et leur
emplacement. Le relevé est gardé (`AppareilGoogle`) et l'écran s'ouvre
dessus sans attendre le réseau.

Ce que Google ne sait pas — qu'une machine est dans l'armoire, en panne,
ou qu'on vient de la confier à un prof avant d'avoir corrigé l'étiquette —
vit dans `SuiviChromebook`. L'inventaire superpose les deux, et un geste
noté dans le programme l'emporte toujours sur ce que dit la console.

## Comment on lit une machine dans la console

Constaté sur l'instance réelle (16/11/2026) :

- **Personnel** (`/1. Chromebooks/1. Personnel éducatif`) : l'étiquette
  porte l'adresse du porteur (178 sur 195). Celles du parc de prêt portent
  un rôle — `Prof_08`, `Stagiaire 9` — et sont **le stock**. D'autres
  portent un service, `VS Ste Ursule` : elles sont tenues, pas libres.
- **Élèves** (`/1. Chromebooks/2. Élèves/...`) : l'**emplacement** dit où
  est la machine — `K-B5-13`, `SU-B3-C12`, `SU-CDI`, `NDK-BTS` — et
  l'étiquette sa place dans ce lieu (`K-B5-13-08`).
- **NDE** (`/2. NDE/Appareils/...`) : l'emplacement, ou à défaut la
  dernière branche de l'unité (`B100`, `CDI`). La branche `Déclassé`
  range les machines hors service.

## L'échange transfère une place

Remplacer la machine d'un prof et remplacer la machine n°8 d'un chariot
sont le même geste : la machine qui arrive du stock **prend la place** de
celle qui part — son étiquette, son emplacement, son unité — et celle qui
part prend l'étiquette de stock que l'arrivante libère (`Prof_08`), ou
part en panne. C'est pourquoi `echanger` ne demande pas « à qui », sauf
quand il n'y a pas d'ancienne machine.

## Google suit, il ne précède pas

Le geste est noté d'abord, en base, et c'est seulement ensuite que les
étiquettes sont écrites dans la console. Si Google refuse — droit non
accordé, réseau absent — rien n'est perdu : la machine figure parmi les
étiquettes à reporter, et le bouton se rejoue.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from datetime import date, datetime, timedelta

from sqlalchemy.orm import Session

from backend.models import (
    Accessoire,
    AnneeScolaire,
    AppareilGoogle,
    MouvementMateriel,
    PanneChromebook,
    Parametre,
    Personne,
    PretAccessoire,
    Snapshot,
    SuiviChromebook,
)
from backend.models.parc_inventaire import RAISONS
from backend.models.parc_materiel import ORGANES
from backend.services.parc_materiel import GesteImpossible

PREFIXE_PERSONNEL = "/1. Chromebooks/1. Personnel"
PREFIXE_ELEVES = "/1. Chromebooks/2. El"
PREFIXE_NDE = "/2. NDE"

ADRESSE = re.compile(r"^[^@\s]+@[^@\s]+\.[a-z]{2,}$", re.I)
ETIQUETTE_STOCK = re.compile(r"^(prof_|stagiaire|pr[eê]t|remplac|stock|r[eé]serve)", re.I)
"""Étiquettes du parc de prêt : un rôle à pourvoir, pas une personne
(`Prof_08`, `Stagiaire 9`).

Pas `CHB-PROF-004` : ces machines sont déjà données (Johann, 16/11/2026),
l'étiquette ne dit simplement pas à qui."""

ETIQUETTE_INCONNUE = re.compile(r"^maintenance", re.I)
"""Étiquettes qui ne situent pas la machine. Les `Maintenance` peuvent être
chez un adulte comme dans la pile des machines en panne : personne ne le
sait plus (Johann, 16/11/2026). Elles sont « à localiser », et c'est
l'inventaire qui tranchera."""

PLACE = re.compile(r"^([A-Z]+-[A-Z]?\d+-[A-Z0-9]+)-\d+\b", re.I)
"""Le code d'une place dans un chariot : `K-B5-13-08` → chariot `K-B5-13`."""

ACTIF = "ACTIVE"
MOIS_DORMANCE = 12
SEUILS_DEFAUT = {"machines": 3, "chargeurs": 3}
CLE_SEUILS = "parc.seuils"

DEVENIRS = {"stock": "en_stock", "hs": "hs", "reforme": "reforme"}


# ---------------------------------------------------------------------------
# Lire une machine
# ---------------------------------------------------------------------------


def categorie(ou: str | None) -> str:
    ou = ou or ""
    if ou.startswith(PREFIXE_PERSONNEL):
        return "personnel"
    if ou.startswith(PREFIXE_ELEVES):
        return "eleves"
    if ou.startswith(PREFIXE_NDE):
        return "nde"
    return "autre"


def site_de(ou: str | None, emplacement: str | None, etiquette: str | None) -> str | None:
    ou, emplacement, etiquette = ou or "", emplacement or "", etiquette or ""
    if ou.startswith(PREFIXE_NDE) or emplacement.upper().startswith("NDE"):
        return "NDE"
    if (
        "Ursule" in ou
        or re.match(r"^SU[-\s]", emplacement, re.I)
        or re.match(r"^SU[-\s]", etiquette, re.I)
        or "Ste Ursule" in etiquette
    ):
        return "SU"
    if (
        "Kreisker" in ou
        or re.match(r"^(K|NDK)[-\s]", emplacement, re.I)
        or re.match(r"^(K|PC-NDK)[-\s]", etiquette, re.I)
    ):
        return "NDK"
    return None


def _dort(derniere_synchro: str | None, aujourd_hui: date) -> bool:
    if not derniere_synchro:
        return True
    try:
        vue = datetime.fromisoformat(derniere_synchro.replace("Z", "+00:00")).date()
    except ValueError:
        return False
    return vue < aujourd_hui - timedelta(days=30 * MOIS_DORMANCE)


def _meme(a: str | None, b: str | None) -> bool:
    return (a or "").strip().lower() == (b or "").strip().lower()


@dataclass
class Poste:
    """Une machine de l'inventaire, telle que le programme la comprend."""

    serie: str
    modele: str = ""
    ou: str = ""
    categorie: str = "autre"
    """`personnel`, `eleves`, `nde`, `autre`, ou `hors_google` quand seul
    le suivi la connaît."""
    site: str | None = None
    statut_google: str | None = None
    etiquette: str = ""
    """Ce que la console porte aujourd'hui."""
    emplacement: str = ""
    etat: str = "en_service"
    """`en_service`, `en_stock`, `hs`, `reforme`, `introuvable` (notés),
    `desactivee` (Google) ou `a_localiser` — la console ne permet pas de
    dire où elle est."""
    pointe_le: date | None = None
    """Vue de ses yeux lors d'un inventaire, ce jour-là."""
    porteur_probable: str | None = None
    """Le dernier adulte qui s'en est servi, d'après Google — quand
    l'étiquette ne dit pas à qui elle est, ou dit autre chose."""
    porteur_probable_nom: str | None = None
    porteur: str | None = None
    """L'adresse de la personne qui l'a, pour une machine du personnel."""
    porteur_nom: str | None = None
    porteur_detail: str | None = None
    porteur_parti: bool | None = None
    """La personne n'est plus inscrite cette année : la machine est à récupérer."""
    tenue_par: str | None = None
    """Un service ou un rôle qui n'est pas une adresse — `VS Ste Ursule`."""
    lieu: str | None = None
    """La salle ou le chariot, pour une machine élève."""
    depuis: date | None = None
    pannes: list[str] = field(default_factory=list)
    derniere_synchro: str | None = None
    derniers_utilisateurs: list[str] = field(default_factory=list)
    dort: bool = False
    fin_maj: date | None = None
    note: str | None = None
    source: str = "google"
    """`suivi` quand un geste du programme a fixé l'état, `google` sinon."""
    a_reporter: list[str] = field(default_factory=list)
    """Ce que Google doit encore recevoir : `étiquette`, `emplacement`, `unité`."""
    etiquette_voulue: str | None = None
    emplacement_voulu: str | None = None
    ou_voulue: str | None = None
    a_verifier: str | None = None
    device_id: str | None = None
    present_google: bool = True


def _lieu(p: Poste) -> str | None:
    """La salle ou le chariot d'une machine élève.

    L'emplacement le dit, sauf quand il porte par erreur le code de la place
    (`K-B5-17-11` au lieu de `K-B5-17`) : on en garde le chariot, et la
    machine est signalée pour qu'on corrige la console. À NDE, faute
    d'emplacement, la dernière branche de l'unité nomme la salle (`B100`).
    """
    emplacement = p.emplacement
    place = PLACE.match(emplacement or "")
    if place:
        p.a_verifier = (
            f"son emplacement Google « {emplacement} » est le code d'une place, "
            f"pas celui du chariot ({place.group(1)})"
        )
        return place.group(1).upper()
    if emplacement:
        return emplacement
    if p.categorie == "nde":
        branches = [b for b in p.ou.split("/") if b]
        if len(branches) > 2:
            return branches[-1]
    return None


def _situer_selon_google(p: Poste, aujourd_hui: date) -> None:
    """L'état d'une machine dont le programme n'a noté aucun geste."""
    etiquette = p.etiquette
    if p.statut_google and p.statut_google != ACTIF:
        p.etat = "desactivee"
        return
    if "classé" in p.ou or re.search(r"HS$", etiquette):
        # NDE range ses machines mortes dans `Déclassé`, sous `TAB01HS`.
        p.etat = "hs"
        p.lieu = p.emplacement or None
        return
    if p.categorie == "personnel":
        if ADRESSE.match(etiquette):
            p.etat = "en_service"
            p.porteur = etiquette.lower()
            if p.dort:
                p.a_verifier = (
                    "étiquetée au nom de quelqu'un, mais muette depuis plus "
                    "d'un an : elle est sans doute rangée ailleurs"
                )
        elif ETIQUETTE_STOCK.match(etiquette):
            p.etat = "en_stock"
        elif ETIQUETTE_INCONNUE.match(etiquette):
            p.etat = "a_localiser"
            p.tenue_par = etiquette
        elif re.match(r"^chb-prof", etiquette, re.I):
            p.etat = "en_service"
            p.tenue_par = etiquette
            p.a_verifier = "donnée, mais son étiquette ne dit pas à qui"
        elif etiquette:
            p.etat = "en_service"
            p.tenue_par = etiquette
        else:
            p.etat = "a_localiser"
            p.a_verifier = "aucune étiquette : ni un porteur, ni le stock"
        return
    if p.categorie in ("eleves", "nde"):
        p.etat = "en_service"
        p.lieu = _lieu(p)
        return
    p.etat = "en_service"
    if ADRESSE.match(etiquette):
        p.porteur = etiquette.lower()


def _situer(p: Poste, s: SuiviChromebook | None, aujourd_hui: date) -> None:
    """Superpose le suivi au relevé : un geste noté l'emporte sur Google."""
    if s is None:
        _situer_selon_google(p, aujourd_hui)
        return

    p.note = s.note
    p.etiquette_voulue = s.etiquette_voulue
    p.emplacement_voulu = s.emplacement_voulu
    p.ou_voulue = s.ou_voulue

    p.pointe_le = s.pointe_le
    if s.etat in ("hs", "reforme", "introuvable"):
        p.etat = s.etat
        p.depuis = s.etat_depuis
        p.source = "suivi"
        p.lieu = p.emplacement or None
        return
    if p.statut_google and p.statut_google != ACTIF:
        p.etat = "desactivee"
        return

    if s.attribue_a:
        p.etat = "en_service"
        p.porteur = s.attribue_a.lower()
        p.depuis = s.attribue_le
        p.source = "suivi"
        return
    if s.etat_depuis is not None:
        # Un geste du programme a fixé l'état : on le croit.
        p.etat = s.etat or "en_service"
        p.depuis = s.etat_depuis
        p.source = "suivi"
        if p.etat == "en_service":
            place = s.etiquette_voulue or p.etiquette
            p.lieu = (
                s.emplacement_voulu if s.emplacement_voulu is not None else p.emplacement
            ) or None
            if ADRESSE.match(place or ""):
                p.porteur = place.lower()
            elif p.categorie == "personnel" and place:
                p.tenue_par = place
        return
    if s.recupere_le:
        # Rendue à la rentrée, et pas encore redonnée : elle est au stock.
        p.etat = "en_stock"
        p.depuis = s.recupere_le
        p.source = "suivi"
        return
    _situer_selon_google(p, aujourd_hui)


def _a_reporter(p: Poste, s: SuiviChromebook | None, g: AppareilGoogle | None) -> list[str]:
    if s is None or g is None or not g.present:
        return []
    manque = []
    voulue = s.etiquette_voulue or s.attribue_a
    if voulue and not _meme(voulue, g.etiquette):
        manque.append("étiquette")
    if s.emplacement_voulu is not None and not _meme(s.emplacement_voulu, g.emplacement):
        manque.append("emplacement")
    if s.ou_voulue and s.ou_voulue != (g.ou or ""):
        manque.append("unité")
    return manque


# ---------------------------------------------------------------------------
# Les personnes
# ---------------------------------------------------------------------------


def _annee_courante(session: Session) -> AnneeScolaire | None:
    return session.query(AnneeScolaire).order_by(AnneeScolaire.libelle.desc()).first()


@dataclass
class Personnel:
    adresse: str
    nom: str
    prenom: str
    type: str
    detail: str | None
    inscrit: bool
    """Inscrite cette année. Faux : partie, ou pas encore réimportée."""
    site: str | None = None


def annuaire(session: Session) -> dict[str, Personnel]:
    """Toutes les personnes qui ont une adresse, indexées par elle."""
    annee = _annee_courante(session)
    inscrits: set[int] = set()
    if annee is not None:
        inscrits = {
            pid
            for (pid,) in session.query(Snapshot.personne_id)
            .filter(Snapshot.annee_scolaire_id == annee.id)
            .distinct()
        }
    from backend.models import Site

    sites = {s.id: s.nom for s in session.query(Site)}
    resultat: dict[str, Personnel] = {}
    for p in session.query(Personne):
        adresse = (p.email_constate or p.email_attribuee or "").strip().lower()
        if not adresse:
            continue
        detail = p.poste_occupe if p.type != "eleve" else p.classe
        resultat[adresse] = Personnel(
            adresse=adresse,
            nom=p.nom_usage or p.nom,
            prenom=p.prenom,
            type=p.type,
            detail=detail,
            inscrit=p.id in inscrits,
            site=sites.get(p.site_id),
        )
    return resultat


# ---------------------------------------------------------------------------
# L'inventaire
# ---------------------------------------------------------------------------


@dataclass
class FinMisesAJour:
    depassee: int = 0
    cette_annee: int = 0
    """Avant la fin de l'année scolaire en cours (31 août)."""
    l_an_prochain: int = 0


@dataclass
class Inventaire:
    postes: list[Poste] = field(default_factory=list)
    par_etat: dict[str, int] = field(default_factory=dict)
    par_categorie: dict[str, int] = field(default_factory=dict)
    chargeurs_en_stock: int = 0
    seuils: dict[str, int] = field(default_factory=lambda: dict(SEUILS_DEFAUT))
    alertes: list[str] = field(default_factory=list)
    fin_maj: FinMisesAJour = field(default_factory=FinMisesAJour)
    releve_le: datetime | None = None
    pointage_depuis: date | None = None
    """Début de l'inventaire en cours : une machine vue avant ne compte pas."""
    pointees: int = 0
    a_pointer: int = 0

    @property
    def nb_a_reporter(self) -> int:
        return sum(1 for p in self.postes if p.a_reporter)


def lire_seuils(session: Session) -> dict[str, int]:
    import json

    ligne = session.query(Parametre).filter_by(cle=CLE_SEUILS).one_or_none()
    seuils = dict(SEUILS_DEFAUT)
    if ligne is not None:
        try:
            seuils.update({k: int(v) for k, v in json.loads(ligne.valeur_json).items()})
        except (ValueError, TypeError, AttributeError):
            pass
    return seuils


def poser_seuils(session: Session, seuils: dict[str, int]) -> dict[str, int]:
    import json

    propres = lire_seuils(session)
    for cle in SEUILS_DEFAUT:
        if cle in seuils and seuils[cle] is not None:
            propres[cle] = max(0, int(seuils[cle]))
    ligne = session.query(Parametre).filter_by(cle=CLE_SEUILS).one_or_none()
    if ligne is None:
        ligne = Parametre(cle=CLE_SEUILS, valeur_json="{}")
        session.add(ligne)
    ligne.valeur_json = json.dumps(propres)
    session.commit()
    return propres


COMPTE_PERSONNEL = re.compile(r"^[a-z][a-z-]*\.[a-z][a-z-]*\d*@", re.I)
"""`prenom.nom@` : la forme des comptes nominatifs de l'établissement."""

JOURS_USAGE_RECENT = 60
"""Une connexion plus ancienne ne dit plus qui a la machine aujourd'hui."""


def _jours_depuis(derniere_synchro: str | None, aujourd_hui: date) -> int | None:
    if not derniere_synchro:
        return None
    try:
        vue = datetime.fromisoformat(derniere_synchro.replace("Z", "+00:00")).date()
    except ValueError:
        return None
    return (aujourd_hui - vue).days


def _deviner_porteur(p: Poste, personnes: dict[str, Personnel], aujourd_hui: date) -> None:
    """Qui s'en sert, d'après les « utilisateurs et activité récents » de Google.

    Google garde la liste des derniers comptes connectés, le plus récent
    d'abord (Johann, 16/11/2026 : « tu dois pouvoir savoir à qui
    l'assigner »). On en retient le premier **adulte** connu du référentiel
    — un élève qui a emprunté la machine, ou le compte technique qui l'a
    enrôlée, ne disent pas à qui elle est confiée.

    Ce n'est qu'une proposition : une machine prêtée une heure garde le
    nom de l'emprunteur. Elle n'est faite que sur les machines du
    personnel, et seulement si l'appareil a servi récemment.
    """
    if p.categorie != "personnel" or not p.derniers_utilisateurs:
        return
    if p.etat in ("hs", "reforme", "introuvable", "desactivee"):
        return
    jours = _jours_depuis(p.derniere_synchro, aujourd_hui)
    if jours is None or jours > 30 * MOIS_DORMANCE:
        return
    adulte = next(
        (u for u in p.derniers_utilisateurs if u in personnes and personnes[u].type != "eleve"),
        None,
    )
    if adulte is not None:
        qui = personnes[adulte]
        nom = f"{qui.prenom} {qui.nom}"
    else:
        # Un compte personnel que le référentiel ne connaît pas : un
        # personnel arrivé depuis le dernier export, ou absent de
        # Charlemagne. Constaté sur les CHB-PROF (16/11/2026). On le
        # propose, en le disant — mais jamais un élève connu, ni un compte
        # technique (`admin@`, `chromebook@`).
        adulte = next(
            (u for u in p.derniers_utilisateurs if u not in personnes and COMPTE_PERSONNEL.match(u)),
            None,
        )
        if adulte is None:
            return
        nom = f"{adulte} (hors référentiel)"

    if p.porteur:
        # L'étiquette nomme quelqu'un : on ne signale que la contradiction.
        if adulte != p.porteur and jours <= JOURS_USAGE_RECENT:
            p.porteur_probable, p.porteur_probable_nom = adulte, nom
            p.a_verifier = p.a_verifier or (
                f"au nom de {p.porteur_nom or p.porteur}, mais c'est {nom} qui s'en sert"
            )
        return
    if p.etat == "en_stock":
        if jours <= JOURS_USAGE_RECENT:
            p.porteur_probable, p.porteur_probable_nom = adulte, nom
            quand = (
                "aujourd'hui" if jours <= 0
                else "hier" if jours == 1
                else f"il y a {jours} jours"
            )
            p.a_verifier = f"au stock, mais {nom} s'en est servi {quand} : prêtée sans être notée ?"
        return
    # À localiser, ou tenue par une étiquette qui ne nomme personne.
    p.porteur_probable, p.porteur_probable_nom = adulte, nom
    p.a_verifier = f"utilisée en dernier par {nom} — sans doute la sienne"


def _fin_annee_scolaire(aujourd_hui: date) -> date:
    annee = aujourd_hui.year if aujourd_hui.month < 9 else aujourd_hui.year + 1
    return date(annee, 8, 31)


def inventaire(session: Session, *, aujourd_hui: date | None = None) -> Inventaire:
    """Chaque machine connue, avec son état et ce qu'il reste à reporter. Lecture seule."""
    aujourd_hui = aujourd_hui or date.today()
    google = {g.serie: g for g in session.query(AppareilGoogle)}
    suivis = {s.serie: s for s in session.query(SuiviChromebook)}
    pannes: dict[str, list[str]] = {}
    for pa in session.query(PanneChromebook).filter(PanneChromebook.resolue_le.is_(None)):
        pannes.setdefault(pa.serie, []).append(pa.organe)
    personnes = annuaire(session)

    inv = Inventaire(seuils=lire_seuils(session))
    for serie in sorted(set(google) | set(suivis)):
        g, s = google.get(serie), suivis.get(serie)
        if g is not None:
            p = Poste(
                serie=serie,
                modele=g.modele or "",
                ou=g.ou or "",
                categorie=categorie(g.ou),
                statut_google=g.statut,
                etiquette=g.etiquette or "",
                emplacement=g.emplacement or "",
                derniere_synchro=g.derniere_synchro,
                derniers_utilisateurs=[
                    u for u in (g.derniers_utilisateurs or "").split(",") if u
                ],
                fin_maj=g.fin_maj,
                device_id=g.device_id,
                present_google=bool(g.present),
            )
            p.dort = _dort(g.derniere_synchro, aujourd_hui)
        else:
            p = Poste(serie=serie, categorie="hors_google", present_google=False)
        _situer(p, s, aujourd_hui)
        p.pannes = sorted(pannes.get(serie, []))
        p.a_reporter = _a_reporter(p, s, g)
        p.site = site_de(p.ou, p.lieu or p.emplacement, p.etiquette_voulue or p.etiquette)
        if p.porteur:
            qui = personnes.get(p.porteur)
            if qui is not None:
                p.porteur_nom = f"{qui.prenom} {qui.nom}"
                p.porteur_detail = qui.detail
                p.porteur_parti = not qui.inscrit
                p.site = p.site or qui.site
        _deviner_porteur(p, personnes, aujourd_hui)
        inv.postes.append(p)

    for p in inv.postes:
        if p.etat == "en_stock" and ADRESSE.match(p.etiquette) and not p.a_reporter:
            p.a_verifier = p.a_verifier or (
                f"au stock, mais son étiquette Google porte encore {p.etiquette}"
            )
        inv.par_etat[p.etat] = inv.par_etat.get(p.etat, 0) + 1
        inv.par_categorie[p.categorie] = inv.par_categorie.get(p.categorie, 0) + 1

    fin = _fin_annee_scolaire(aujourd_hui)
    for p in inv.postes:
        if p.fin_maj is None or p.etat in ("reforme", "desactivee", "introuvable"):
            continue
        if p.fin_maj < aujourd_hui:
            inv.fin_maj.depassee += 1
        elif p.fin_maj <= fin:
            inv.fin_maj.cette_annee += 1
        elif p.fin_maj <= date(fin.year + 1, 8, 31):
            inv.fin_maj.l_an_prochain += 1

    inv.pointage_depuis = debut_pointage(session)
    if inv.pointage_depuis is not None:
        for p in inv.postes:
            if p.etat in ("reforme", "desactivee") or not p.present_google and p.categorie != "hors_google":
                continue
            if p.pointe_le is not None and p.pointe_le >= inv.pointage_depuis:
                inv.pointees += 1
            else:
                inv.a_pointer += 1

    inv.chargeurs_en_stock = (
        session.query(Accessoire).filter_by(type="chargeur", etat="en_stock").count()
    )
    lus = [g.lu_le for g in google.values() if g.lu_le]
    inv.releve_le = max(lus) if lus else None

    stock = inv.par_etat.get("en_stock", 0)
    if google and stock < inv.seuils["machines"]:
        inv.alertes.append(
            f"Plus que {stock} machine{'s' if stock > 1 else ''} au stock "
            f"(seuil : {inv.seuils['machines']})."
        )
    if inv.chargeurs_en_stock < inv.seuils["chargeurs"]:
        inv.alertes.append(
            f"Plus que {inv.chargeurs_en_stock} chargeur"
            f"{'s' if inv.chargeurs_en_stock > 1 else ''} de rechange "
            f"(seuil : {inv.seuils['chargeurs']})."
        )
    partis = [p for p in inv.postes if p.porteur_parti and p.etat == "en_service"]
    if partis:
        inv.alertes.append(
            f"{len(partis)} machine{'s sont' if len(partis) > 1 else ' est'} encore "
            "au nom de quelqu'un qui n'est plus inscrit cette année : à récupérer."
        )
    a_localiser = inv.par_etat.get("a_localiser", 0)
    if a_localiser:
        inv.alertes.append(
            f"{a_localiser} machine{'s' if a_localiser > 1 else ''} que la console ne "
            "permet pas de situer : l'onglet « Inventorier » les met en tête."
        )
    if inv.nb_a_reporter:
        inv.alertes.append(
            f"{inv.nb_a_reporter} étiquette{'s' if inv.nb_a_reporter > 1 else ''} "
            "Google à mettre à jour après un geste noté ici."
        )
    return inv


# ---------------------------------------------------------------------------
# Le relevé
# ---------------------------------------------------------------------------


@dataclass
class Releve:
    nb: int = 0
    nouveaux: int = 0
    disparus: int = 0
    reconcilies: int = 0
    """Machines dont Google porte désormais ce que le programme voulait."""


def enregistrer_releve(
    session: Session, appareils: list[dict], *, maintenant: datetime | None = None
) -> Releve:
    """Écrase la copie locale par ce que Google vient de dire.

    Une machine que la console ne liste plus n'est pas effacée : le suivi
    peut encore la nommer. Elle est marquée absente.

    Quand Google porte enfin l'étiquette voulue, le vœu est effacé : un
    changement fait plus tard dans la console doit être respecté, pas
    signalé comme un oubli.
    """
    maintenant = maintenant or datetime.now()
    connus = {g.serie: g for g in session.query(AppareilGoogle)}
    suivis = {s.serie: s for s in session.query(SuiviChromebook)}
    vus: set[str] = set()
    r = Releve()

    for a in appareils:
        serie = (a.get("serie") or "").strip()
        if not serie or serie in vus:
            continue
        vus.add(serie)
        g = connus.get(serie)
        if g is None:
            g = AppareilGoogle(serie=serie)
            session.add(g)
            r.nouveaux += 1
        g.device_id = a.get("device_id") or g.device_id
        g.modele = a.get("modele") or ""
        g.ou = a.get("ou") or ""
        g.statut = a.get("statut") or ""
        g.etiquette = (a.get("etiquette") or "").strip()
        g.emplacement = (a.get("emplacement") or "").strip()
        g.derniers_utilisateurs = ",".join(a.get("derniers_utilisateurs") or [])
        g.derniere_synchro = a.get("derniere_synchro")
        fin = a.get("fin_maj")
        g.fin_maj = date.fromisoformat(fin) if fin else None
        g.present = True
        g.lu_le = maintenant
        r.nb += 1

        s = suivis.get(serie)
        if s is not None and _reconcilier(s, g):
            r.reconcilies += 1

    for serie, g in connus.items():
        if serie not in vus and g.present:
            g.present = False
            r.disparus += 1
    session.commit()
    return r


def _reconcilier(s: SuiviChromebook, g: AppareilGoogle) -> bool:
    """Efface les vœux que Google a exaucés. Vrai si au moins un l'était."""
    fait = False
    if s.etiquette_voulue and _meme(s.etiquette_voulue, g.etiquette):
        s.etiquette_voulue = None
        fait = True
    if s.emplacement_voulu is not None and _meme(s.emplacement_voulu, g.emplacement):
        s.emplacement_voulu = None
        fait = True
    if s.ou_voulue and s.ou_voulue == (g.ou or ""):
        s.ou_voulue = None
        fait = True
    return fait


# ---------------------------------------------------------------------------
# Les gestes
# ---------------------------------------------------------------------------


def _suivi(session: Session, serie: str) -> SuiviChromebook:
    s = session.query(SuiviChromebook).filter_by(serie=serie).one_or_none()
    if s is None:
        s = SuiviChromebook(serie=serie, etat="en_service")
        session.add(s)
        session.flush()
    return s


def noter(session: Session, **champs) -> MouvementMateriel:
    """Ajoute une ligne au journal. Ne valide pas la transaction."""
    m = MouvementMateriel(**champs)
    session.add(m)
    return m


def _decrire(p: Poste) -> str:
    if p.etat == "en_service":
        if p.porteur:
            return f"chez {p.porteur_nom or p.porteur}"
        if p.lieu:
            return f"en service, {p.lieu}"
        if p.tenue_par:
            return f"tenue par « {p.tenue_par} »"
        return "en service"
    return {
        "en_stock": "au stock",
        "hs": "hors service",
        "reforme": "réformée",
        "desactivee": "désactivée dans Google",
    }.get(p.etat, p.etat)


@dataclass
class Recu:
    """Ce que le geste a noté, et les machines dont Google doit suivre."""

    a_ecrire: list[str] = field(default_factory=list)
    message: str = ""


def echanger(
    session: Session,
    *,
    ancienne: str | None = None,
    nouvelle: str | None = None,
    porteur: str | None = None,
    raison: str,
    precision: str | None = None,
    devenir: str = "stock",
    organes: list[str] | tuple[str, ...] = (),
    etiquette_ancienne: str | None = None,
    chargeur: str | None = None,
    aujourd_hui: date | None = None,
) -> Recu:
    """Remet, reprend ou échange une machine — en un seul geste.

    - `nouvelle` seule : une machine du stock confiée à `porteur` ;
    - `ancienne` seule : une machine rendue, qui part au stock, en panne ou
      à la réforme ;
    - les deux : la nouvelle prend la place de l'ancienne.

    Args:
        porteur: adresse (ou rôle) de la personne. Facultatif quand
            l'ancienne machine dit déjà à qui elle était.
        devenir: ce que devient l'ancienne — `stock`, `hs` ou `reforme`.
        organes: les pannes de l'ancienne, quand elle part en `hs`.
        etiquette_ancienne: l'étiquette à lui donner dans Google. Par
            défaut, celle du stock que la nouvelle libère (`Prof_08`).
        chargeur: série d'un chargeur du stock, donné avec la machine.

    Raises:
        GesteImpossible: le message dit pourquoi, et rien n'est écrit.
    """
    aujourd_hui = aujourd_hui or date.today()
    ancienne = (ancienne or "").strip() or None
    nouvelle = (nouvelle or "").strip() or None
    porteur = (porteur or "").strip() or None
    if porteur and ADRESSE.match(porteur):
        porteur = porteur.lower()

    if raison not in RAISONS:
        raise GesteImpossible(f"Raison inconnue : {raison!r}.")
    if not ancienne and not nouvelle:
        raise GesteImpossible("Il faut au moins une machine : celle qui part, ou celle qui arrive.")
    if ancienne and ancienne == nouvelle:
        raise GesteImpossible("Une machine ne s'échange pas contre elle-même.")
    if devenir not in DEVENIRS:
        raise GesteImpossible(f"Devenir inconnu : {devenir!r}. Attendu : stock, hs ou reforme.")
    inconnus = [o for o in organes if o not in ORGANES]
    if inconnus:
        raise GesteImpossible(f"Organe inconnu : {', '.join(inconnus)}.")

    postes = {p.serie: p for p in inventaire(session, aujourd_hui=aujourd_hui).postes}
    pa = postes.get(ancienne) if ancienne else None
    pn = postes.get(nouvelle) if nouvelle else None

    if ancienne and pa is None:
        pa = Poste(serie=ancienne, categorie="hors_google", present_google=False)
    if pa is not None and pa.etat in ("hs", "reforme") and nouvelle is None:
        raise GesteImpossible(f"{ancienne} est déjà {_decrire(pa)} : il n'y a rien à reprendre.")
    if nouvelle:
        if pn is None:
            raise GesteImpossible(
                f"{nouvelle} est inconnue de l'inventaire. Relis la flotte Google, "
                "ou vérifie le numéro de série."
            )
        if pn.etat != "en_stock":
            raise GesteImpossible(
                f"{nouvelle} n'est pas au stock : elle est {_decrire(pn)}. "
                "Seule une machine du stock peut être remise."
            )

    # La place que la nouvelle va occuper : celle de l'ancienne, ou la
    # personne désignée quand il n'y en avait pas.
    if porteur:
        place_etiquette = porteur
        place_emplacement = pa.emplacement if pa is not None and pa.emplacement else None
    elif pa is not None:
        place_etiquette = pa.porteur or pa.etiquette_voulue or pa.etiquette or None
        place_emplacement = (
            pa.emplacement_voulu if pa.emplacement_voulu is not None else pa.emplacement
        ) or None
    else:
        place_etiquette, place_emplacement = None, None
    if nouvelle and not place_etiquette:
        raise GesteImpossible(
            f"À qui confier {nouvelle} ? Choisis une personne, ou la machine qu'elle remplace."
        )
    qui = porteur or (pa.porteur if pa is not None else None) or place_etiquette
    precision = (precision or "").strip() or None

    if nouvelle:
        s = _suivi(session, nouvelle)
        est_adresse = bool(ADRESSE.match(place_etiquette or ""))
        s.attribue_a = place_etiquette if est_adresse else None
        s.attribue_le = aujourd_hui if est_adresse else None
        s.recupere_le = None
        s.recupere_de = None
        s.etat = "en_service"
        s.etat_depuis = aujourd_hui
        s.etiquette_voulue = place_etiquette
        s.emplacement_voulu = place_emplacement
        if pa is not None and pa.ou and pn.ou and pa.ou != pn.ou:
            s.ou_voulue = pa.ou
        noter(
            session,
            serie=nouvelle,
            geste="echange" if ancienne else "remise",
            de="stock",
            vers=place_etiquette,
            raison=raison,
            precision=precision,
            autre_serie=ancienne,
        )

    if ancienne:
        s = _suivi(session, ancienne)
        s.recupere_le = aujourd_hui
        s.recupere_de = pa.porteur or pa.etiquette or None
        s.attribue_a = None
        s.attribue_le = None
        s.etat = DEVENIRS[devenir]
        s.etat_depuis = aujourd_hui
        if etiquette_ancienne is not None and etiquette_ancienne.strip():
            s.etiquette_voulue = etiquette_ancienne.strip()
        elif pn is not None and pn.etiquette and not ADRESSE.match(pn.etiquette):
            s.etiquette_voulue = pn.etiquette
        else:
            s.etiquette_voulue = {"stock": "Stock", "hs": "HS", "reforme": "Réformé"}[devenir]
        if pn is not None:
            if not _meme(pn.emplacement, pa.emplacement):
                s.emplacement_voulu = pn.emplacement or ""
            if pn.ou and pa.ou and pn.ou != pa.ou:
                s.ou_voulue = pn.ou
        elif pa.emplacement:
            s.emplacement_voulu = ""
        noter(
            session,
            serie=ancienne,
            geste="echange" if nouvelle else ("reforme" if devenir == "reforme" else "reprise"),
            de=pa.porteur or pa.etiquette or None,
            vers=devenir,
            raison=raison,
            precision=precision,
            autre_serie=nouvelle,
        )
        if devenir == "hs":
            deja = {
                x.organe
                for x in session.query(PanneChromebook).filter(
                    PanneChromebook.serie == ancienne, PanneChromebook.resolue_le.is_(None)
                )
            }
            for organe in organes:
                if organe in deja:
                    continue
                session.add(
                    PanneChromebook(
                        serie=ancienne, organe=organe, constatee_le=aujourd_hui, note=precision
                    )
                )
            if organes:
                noter(
                    session,
                    serie=ancienne,
                    geste="panne",
                    precision=", ".join(organes),
                    raison=raison,
                )

    if chargeur:
        _donner_chargeur(session, chargeur, a_qui=qui or "?", aujourd_hui=aujourd_hui)

    session.commit()

    morceaux = []
    if nouvelle and ancienne:
        morceaux.append(f"{nouvelle} remplace {ancienne}")
    elif nouvelle:
        morceaux.append(f"{nouvelle} confiée")
    else:
        morceaux.append(f"{ancienne} reprise")
    if ancienne:
        morceaux.append(
            {"stock": "l'ancienne retourne au stock", "hs": "l'ancienne part à l'atelier",
             "reforme": "l'ancienne est réformée"}[devenir]
        )
    if chargeur:
        morceaux.append(f"chargeur {chargeur} donné")
    return Recu(
        a_ecrire=[x for x in (nouvelle, ancienne) if x],
        message=" — ".join(morceaux),
    )


def _donner_chargeur(session: Session, serie: str, *, a_qui: str, aujourd_hui: date) -> None:
    a = session.query(Accessoire).filter_by(serie=serie).one_or_none()
    if a is None:
        raise GesteImpossible(f"Chargeur inconnu : {serie}.")
    if a.etat != "en_stock":
        raise GesteImpossible(f"{serie} n'est pas au stock : il ne peut pas être donné.")
    session.add(
        PretAccessoire(
            accessoire_serie=serie, prete_a=a_qui, prete_le=aujourd_hui, definitif=True
        )
    )
    a.etat = "donne"
    noter(session, objet="accessoire", serie=serie, geste="don", de="stock", vers=a_qui)


def entrer_au_stock(
    session: Session, serie: str, *, precision: str | None = None, aujourd_hui: date | None = None
) -> None:
    """Déclare une machine disponible : rangée dans l'armoire, prête à servir.

    Sert aussi bien à une machine neuve qu'à une machine réparée hors du
    programme. Une machine confiée à quelqu'un se reprend par `echanger`.
    """
    aujourd_hui = aujourd_hui or date.today()
    serie = (serie or "").strip()
    if not serie:
        raise GesteImpossible("Un numéro de série est requis.")
    s = _suivi(session, serie)
    if s.attribue_a:
        raise GesteImpossible(
            f"{serie} est confiée à {s.attribue_a} : reprends-la d'abord, pour garder la trace."
        )
    # Une machine qui revient au stock remarche : ses pannes ouvertes sont
    # réparées, sans quoi l'atelier continuerait d'en compter les organes
    # comme morts.
    ouvertes = (
        session.query(PanneChromebook)
        .filter(PanneChromebook.serie == serie, PanneChromebook.resolue_le.is_(None))
        .all()
    )
    for panne in ouvertes:
        panne.resolue_le = aujourd_hui
        panne.resolution = "reparee"
    avant = s.etat
    s.etat = "en_stock"
    s.etat_depuis = aujourd_hui
    s.recupere_le = s.recupere_le or aujourd_hui
    if avant in ("hs", "reforme") and (s.etiquette_voulue or "").upper() in ("HS", "RÉFORMÉ"):
        s.etiquette_voulue = "Stock"
    noter(
        session,
        serie=serie,
        geste="entree_stock",
        de=avant,
        vers="stock",
        precision="; ".join(
            x for x in (precision, ouvertes and "pannes closes : " + ", ".join(p.organe for p in ouvertes)) if x
        )
        or None,
    )
    session.commit()


# ---------------------------------------------------------------------------
# L'inventaire physique
# ---------------------------------------------------------------------------

CLE_POINTAGE = "parc.pointage_depuis"

CONSTATS = ("conforme", "stock", "porteur", "lieu", "hs", "reforme", "introuvable")
"""Ce qu'on peut dire d'une machine qu'on a sous les yeux — ou qu'on n'a
pas trouvée."""


def debut_pointage(session: Session) -> date | None:
    import json

    ligne = session.query(Parametre).filter_by(cle=CLE_POINTAGE).one_or_none()
    if ligne is None:
        return None
    try:
        valeur = json.loads(ligne.valeur_json)
        return date.fromisoformat(valeur) if valeur else None
    except (ValueError, TypeError):
        return None


def commencer_pointage(session: Session, depuis: date | None = None) -> date:
    """Ouvre un inventaire : les machines vues avant cette date sont à revoir."""
    import json

    depuis = depuis or date.today()
    ligne = session.query(Parametre).filter_by(cle=CLE_POINTAGE).one_or_none()
    if ligne is None:
        ligne = Parametre(cle=CLE_POINTAGE, valeur_json="null")
        session.add(ligne)
    ligne.valeur_json = json.dumps(depuis.isoformat())
    session.commit()
    return depuis


def pointer(
    session: Session,
    serie: str,
    *,
    constat: str,
    porteur: str | None = None,
    lieu: str | None = None,
    organes: list[str] | tuple[str, ...] = (),
    note: str | None = None,
    aujourd_hui: date | None = None,
) -> str:
    """Note ce qu'on constate d'une machine pendant l'inventaire. Rend une phrase.

    ## Une correction, pas un geste

    Échanger suppose de piocher au stock ; ici on ne déplace rien, on
    **rectifie** ce que le programme croyait. Une machine trouvée chez un
    prof y est notée, d'où qu'elle vienne. C'est ainsi que l'inventaire
    nettoie le référentiel des erreurs accumulées.

    L'étiquette Google qui en découle passe dans « à reporter » : on les
    écrit toutes d'un clic à la fin, plutôt qu'à chaque machine scannée.

    Args:
        constat: une valeur de `CONSTATS`.
        porteur: pour `porteur` — l'adresse de la personne.
        lieu: pour `lieu` — la salle ou le chariot (`K-B5-13`).
        organes: pour `hs` — ce qui est mort.
    """
    aujourd_hui = aujourd_hui or date.today()
    serie = (serie or "").strip()
    if not serie:
        raise GesteImpossible("Un numéro de série est requis.")
    if constat not in CONSTATS:
        raise GesteImpossible(f"Constat inconnu : {constat!r}.")
    inconnus = [o for o in organes if o not in ORGANES]
    if inconnus:
        raise GesteImpossible(f"Organe inconnu : {', '.join(inconnus)}.")

    avant = next(
        (p for p in inventaire(session, aujourd_hui=aujourd_hui).postes if p.serie == serie), None
    )
    if constat == "conforme" and (avant is None or avant.etat == "a_localiser"):
        raise GesteImpossible(
            "Le programme ne sait pas où elle est : dis-lui ce que tu constates "
            "(au stock, chez quelqu'un, dans une salle, en panne)."
        )
    description_avant = _decrire(avant) if avant else "inconnue du programme"
    s = _suivi(session, serie)
    note = (note or "").strip() or None

    def poser_etat(etat: str) -> None:
        if s.etat != etat or s.etat_depuis is None:
            s.etat = etat
            s.etat_depuis = aujourd_hui

    if constat == "conforme":
        apres = description_avant
    elif constat == "stock":
        poser_etat("en_stock")
        if s.attribue_a or (avant and avant.porteur):
            s.recupere_de = s.attribue_a or avant.porteur
        s.attribue_a = None
        s.attribue_le = None
        s.recupere_le = s.recupere_le or aujourd_hui
        etiquette = avant.etiquette if avant else ""
        if not ETIQUETTE_STOCK.match(etiquette or ""):
            s.etiquette_voulue = "Stock"
        apres = "au stock"
    elif constat == "porteur":
        qui = (porteur or "").strip()
        if not qui:
            raise GesteImpossible("Chez qui ? Choisis la personne.")
        if ADRESSE.match(qui):
            qui = qui.lower()
            # Déjà notée chez elle : on garde la date où elle l'a reçue.
            if not (_meme(s.attribue_a, qui) and s.attribue_le):
                s.attribue_le = aujourd_hui
            s.attribue_a = qui
        else:
            s.attribue_a = None
        poser_etat("en_service")
        s.recupere_le = None
        s.etiquette_voulue = qui
        apres = f"chez {qui}"
    elif constat == "lieu":
        ou = (lieu or "").strip()
        if not ou:
            raise GesteImpossible("Dans quelle salle, ou quel chariot ?")
        poser_etat("en_service")
        s.attribue_a = None
        s.attribue_le = None
        s.recupere_le = None
        s.emplacement_voulu = ou
        apres = f"en service, {ou}"
    elif constat in ("hs", "reforme", "introuvable"):
        poser_etat(constat)
        if s.attribue_a:
            s.recupere_de = s.attribue_a
        s.attribue_a = None
        s.attribue_le = None
        if constat == "hs":
            deja = {
                x.organe
                for x in session.query(PanneChromebook).filter(
                    PanneChromebook.serie == serie, PanneChromebook.resolue_le.is_(None)
                )
            }
            for organe in organes:
                if organe not in deja:
                    session.add(PanneChromebook(serie=serie, organe=organe,
                                                constatee_le=aujourd_hui, note=note))
        apres = {"hs": "hors service", "reforme": "réformée", "introuvable": "introuvable"}[constat]
        if constat == "hs" and organes:
            apres += " (" + ", ".join(organes) + ")"

    s.pointe_le = aujourd_hui
    if note:
        s.note = note
    noter(
        session,
        serie=serie,
        geste="pointage",
        de=description_avant[:200],
        vers=apres[:200],
        precision=note,
    )
    session.commit()
    if constat == "conforme":
        return f"{serie} vue : {apres}, comme prévu."
    return f"{serie} : {description_avant} → {apres}."


# ---------------------------------------------------------------------------
# Écrire dans Google
# ---------------------------------------------------------------------------


@dataclass
class EcritureGoogle:
    serie: str
    ok: bool
    message: str


def ecrire_dans_google(session: Session, client, series: list[str]) -> list[EcritureGoogle]:
    """Reporte dans la console ce que le programme a noté. Écrit chez Google.

    Ne s'appelle que sur un clic : c'est le seul endroit du module qui
    modifie la console. Un refus n'annule rien de ce qui a été noté — la
    machine reste parmi les étiquettes à reporter.
    """
    from backend.services.google_api import DroitManquant

    resultats: list[EcritureGoogle] = []
    refus: str | None = None
    for serie in series:
        s = session.query(SuiviChromebook).filter_by(serie=serie).one_or_none()
        g = session.query(AppareilGoogle).filter_by(serie=serie).one_or_none()
        if s is None:
            continue
        manque = _a_reporter(Poste(serie=serie), s, g)
        if not manque:
            if g is None or not g.present:
                resultats.append(
                    EcritureGoogle(serie, False, "inconnue de Google : relis la flotte")
                )
            continue
        if refus:
            resultats.append(EcritureGoogle(serie, False, refus))
            continue
        if not g.device_id:
            resultats.append(
                EcritureGoogle(serie, False, "identifiant Google inconnu : relis la flotte")
            )
            continue

        etiquette = (s.etiquette_voulue or s.attribue_a) if "étiquette" in manque else None
        emplacement = s.emplacement_voulu if "emplacement" in manque else None
        try:
            client.annoter_appareil(g.device_id, etiquette=etiquette, emplacement=emplacement)
            if "unité" in manque:
                client.deplacer_appareil(g.device_id, s.ou_voulue)
        except DroitManquant as e:
            refus = str(e)
            resultats.append(EcritureGoogle(serie, False, refus))
            noter(session, serie=serie, geste="google", vers=etiquette,
                  google=f"refusé : droit d'écriture non accordé")
            continue
        except Exception as e:  # réseau, quota, appareil supprimé
            message = f"{type(e).__name__} : {e}"[:280]
            resultats.append(EcritureGoogle(serie, False, message))
            noter(session, serie=serie, geste="google", vers=etiquette, google=f"échec : {message}")
            continue

        faits = []
        if etiquette is not None:
            g.etiquette = etiquette
            faits.append(f"étiquette « {etiquette} »")
        if emplacement is not None:
            g.emplacement = emplacement
            faits.append(f"emplacement « {emplacement or '(vide)'} »")
        if "unité" in manque:
            g.ou = s.ou_voulue
            faits.append(f"rangée dans {s.ou_voulue}")
        _reconcilier(s, g)
        texte = "écrit : " + ", ".join(faits)
        noter(session, serie=serie, geste="google", vers=etiquette, google=texte[:300])
        resultats.append(EcritureGoogle(serie, True, texte))
    session.commit()
    return resultats


def series_a_reporter(session: Session) -> list[str]:
    return [p.serie for p in inventaire(session).postes if p.a_reporter]


# ---------------------------------------------------------------------------
# Lire le journal, une fiche, ce que quelqu'un détient
# ---------------------------------------------------------------------------


def journal(
    session: Session,
    *,
    serie: str | None = None,
    personne: str | None = None,
    limite: int = 300,
) -> list[MouvementMateriel]:
    q = session.query(MouvementMateriel)
    if serie:
        q = q.filter(
            (MouvementMateriel.serie == serie) | (MouvementMateriel.autre_serie == serie)
        )
    if personne:
        p = personne.strip().lower()
        q = q.filter((MouvementMateriel.de == p) | (MouvementMateriel.vers == p))
    return q.order_by(MouvementMateriel.quand.desc(), MouvementMateriel.id.desc()).limit(limite).all()


@dataclass
class Detention:
    adresse: str
    nom: str | None
    detail: str | None
    inscrit: bool | None
    machines: list[Poste] = field(default_factory=list)
    accessoires: list[dict] = field(default_factory=list)


def detient(session: Session, adresse: str) -> Detention:
    """Ce qu'une personne a entre les mains : machines et accessoires."""
    adresse = (adresse or "").strip().lower()
    qui = annuaire(session).get(adresse)
    d = Detention(
        adresse=adresse,
        nom=f"{qui.prenom} {qui.nom}" if qui else None,
        detail=qui.detail if qui else None,
        inscrit=qui.inscrit if qui else None,
    )
    d.machines = [
        p for p in inventaire(session).postes if p.porteur == adresse and p.etat == "en_service"
    ]
    for pret in session.query(PretAccessoire).filter(PretAccessoire.rendu_le.is_(None)):
        if (pret.prete_a or "").strip().lower() != adresse:
            continue
        a = session.query(Accessoire).filter_by(serie=pret.accessoire_serie).one_or_none()
        d.accessoires.append(
            {
                "serie": pret.accessoire_serie,
                "type": a.type if a else "?",
                "depuis": pret.prete_le,
                "definitif": bool(pret.definitif),
            }
        )
    return d
