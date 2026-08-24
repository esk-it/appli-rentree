"""Rapprochement de la flotte Chromebook et des enseignants.

## Où se cache l'information

Google offre un champ « utilisateur annoté » qui semble fait pour dire à
qui l'appareil est confié. Dans cette instance il porte partout le même
compte d'administration technique : il ne désigne personne.

L'établissement range l'information ailleurs, dans l'**étiquette**
(`annotatedAssetId`). Les appareils du personnel y portent l'adresse de
leur porteur ; ceux des élèves, un code d'emplacement (`K-B5-13-08`) ; et
le parc de prêt, un nom de rôle (`Prof_08`, `Stagiaire 9`).

Ce module lit donc l'étiquette, et ne s'en tient pas là : les **derniers
utilisateurs** de l'appareil, que Google enregistre seul, servent de
contre-épreuve. Quand les deux se contredisent, on ne tranche pas — deux
appareils échangés par erreur se voient précisément à cet endroit, et
c'est l'humain qui le corrige.

## Une étiquette survit à la machine qu'elle décrit

Trois appareils portent l'adresse d'une même enseignante ; un seul a
synchronisé cette année, les deux autres dorment depuis 2024 et 2025. Ce
ne sont pas trois machines en circulation, mais une vivante et deux
étiquettes que personne n'a corrigées en les rangeant.

La **dernière synchronisation** départage : au-delà d'un an sans donner
signe de vie, un appareil n'est plus chez quelqu'un, il est quelque part.
Le rapport le dit plutôt que de le compter comme un dû.

## Le geste part de la machine, pas de la personne

Rendre un Chromebook, c'est en avoir un dans les mains et lire le numéro
inscrit dessous. Chercher d'abord le nom de son porteur supposé suppose
que l'étiquette est juste — c'est-à-dire précisément ce qui manque quand
on en a besoin. D'où `chercher_appareil`, qui accepte un numéro de série,
une étiquette, ou une adresse, et rend ce que Google sait de l'appareil,
quel qu'en soit le porteur déclaré.

## Le parc pour lui-même

Les quatre listes d'action — à réclamer, à équiper, libres, à vérifier —
répondent à la rentrée. Elles ne disent rien du parc : combien de
machines, de quels modèles, où, et combien ne donnent plus signe de vie.
Cinq cents appareils qu'on ne peut regarder qu'à travers ce qu'il y a à en
faire restent invisibles le reste de l'année.

## Ce qu'il en tire

À qui réclamer une machine — les partants qui en détiennent une. À qui en
donner une — les arrivants qui n'en ont pas. Et lesquelles sont libres :
le parc de prêt, plus celles dont le porteur n'a plus de compte.

## Un tableau et un annuaire ne s'écrivent jamais pareil

Le tableau ne porte pas d'adresse : le lien vers Google se fait par le
nom. Or un nom composé y perd souvent sa seconde part, un prénom composé
son second terme, et une orthographe hésite. Le rapprochement passe donc
par `rapprochement.py`, qui applique des règles successives et dit
laquelle a conclu — un lien obtenu autrement que par l'égalité stricte
reste affiché comme tel, à vérifier d'un coup d'œil.

## Ce qu'on a fait, et qu'on doit pouvoir revoir

Une machine confiée quitte les listes d'actions — c'est le but. Mais elle
quitte aussi le champ de vision : rien ne rappelait ensuite à qui elle
était allée, ni de qui elle venait. Or c'est exactement la question qu'on
se pose trois semaines plus tard, quand quelqu'un réclame la sienne.

Le suivi gardait déjà les faits ; le journal les rejoue, du plus récent au
plus ancien. Il ne déduit rien de Google : il raconte les gestes que
l'établissement a notés.

## Rendre en juin et revenir en septembre

Un enseignant qui ignore s'il sera reconduit rend sa machine avant l'été.
S'il revient, il figure au tableau comme n'importe quel titulaire — et se
retrouve sans appareil, sans que rien ne le signale : il n'est ni un
arrivant, ni un partant.

Le suivi permet de le voir, parce qu'il garde **de qui** chaque machine a
été reprise. Quelqu'un dont on a noté la restitution et qui figure encore
au tableau n'est pas parti : il est revenu, et il lui faut de nouveau une
machine.

## Ce que Google ne peut pas savoir

Rendre une machine et en confier une autre sont des gestes **physiques**.
Ils précèdent de plusieurs jours, parfois de semaines, la mise à jour de
l'étiquette dans la console. Sans mémoire, la liste des machines à
réclamer resterait identique du premier au dernier jour de la rentrée.

Le suivi tenu par l'application se superpose donc au relevé : une machine
notée rendue quitte la liste des réclamations, et une personne à qui on
vient d'en confier une quitte celle des équipements. Quand l'étiquette
Google finit par diverger de ce suivi, l'écart est signalé — c'est le
rappel qu'il reste à mettre la console à jour.

## Ce qu'il ne fait pas

Aucune écriture dans Google. Le droit demandé est en lecture seule, et
réattribuer une machine reste un geste physique : le programme dit ce
qu'il constate, il ne déplace rien.
"""
from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass, field

ADRESSE = re.compile(r"^[^@\s]+@[^@\s]+\.[a-z]{2,}$", re.I)

# Étiquettes du parc de prêt : un rôle, pas une personne.
ROLES = re.compile(r"^(prof|stagiaire|maintenance|vs|pret|remplac)", re.I)

ACTIF = "ACTIVE"

MOIS_DORMANCE = 12
"""Au-delà, l'appareil n'a plus donné signe de vie : son étiquette ne
décrit plus sa situation, elle décrit son passé."""


def normaliser(texte: str | None) -> str:
    sans = unicodedata.normalize("NFD", (texte or "").strip().lower())
    return re.sub(
        r"[^a-z]", "", "".join(c for c in sans if unicodedata.category(c) != "Mn")
    )


@dataclass
class Appareil:
    serie: str
    modele: str
    ou: str
    statut: str
    etiquette: str
    porteur: str | None
    """Adresse lue dans l'étiquette, si c'en est une."""
    derniers_utilisateurs: list[str] = field(default_factory=list)
    emplacement: str = ""
    derniere_synchro: str | None = None

    recupere_le: str | None = None
    """Date de restitution notée dans l'application."""
    recupere_de: str | None = None
    """Adresse de qui l'a rendue — c'est elle qui trahit un retour."""
    a_recuperer: bool = False
    """Son porteur quitte l'établissement : la machine est attendue."""
    libre: bool = False
    """Parc de prêt, ou étiquetée au nom d'un compte qui n'existe plus."""
    attribue_a: str | None = None
    """Adresse à qui elle a été confiée, avant mise à jour de l'étiquette."""
    attribue_le: str | None = None

    @property
    def est_de_pret(self) -> bool:
        return bool(ROLES.match(self.etiquette)) and self.porteur is None

    @property
    def dort(self) -> bool:
        """Aucune synchronisation depuis plus d'un an — ou jamais."""
        from datetime import datetime, timedelta

        if not self.derniere_synchro:
            return True
        try:
            vue = datetime.fromisoformat(
                self.derniere_synchro.replace("Z", "+00:00")
            ).replace(tzinfo=None)
        except ValueError:
            return False
        return vue < datetime.utcnow() - timedelta(days=30 * MOIS_DORMANCE)

    @property
    def est_actif(self) -> bool:
        return self.statut == ACTIF


@dataclass
class Discordance:
    appareil: Appareil
    attendu: str
    constates: list[str]
    """Ce que Google a enregistré : qui s'est réellement connecté dessus."""


@dataclass
class LigneProf:
    nom: str
    prenom: str
    discipline: str
    code: str
    email: str | None
    appareils: list[Appareil] = field(default_factory=list)
    attribue: str | None = None
    """Série d'une machine confiée dans l'application, avant que Google le sache."""
    raison: str = ""
    """Pourquoi cette personne attend une machine : `arrivant`, `remplace`,
    ou `revenu` — elle a rendu la sienne avant l'été et elle est de retour."""
    methode: str = "exact"
    """Comment l'adresse a été retrouvée : `exact`, `nom_compose`, …"""
    approximatif: bool = False
    """Vrai quand l'égalité stricte n'a pas suffi."""
    homonymes: list[str] = field(default_factory=list)
    """Adresses également plausibles, quand aucune ne peut être choisie."""


@dataclass
class MouvementMachine:
    """Un geste noté sur une machine : reprise, remise, ou les deux."""

    serie: str
    modele: str
    etiquette: str
    rendu_par: str | None = None
    rendu_par_nom: str | None = None
    rendu_le: str | None = None
    confie_a: str | None = None
    confie_a_nom: str | None = None
    confie_le: str | None = None

    @property
    def quand(self) -> str:
        """La date du geste le plus récent — c'est elle qui ordonne."""
        return max(self.confie_le or "", self.rendu_le or "")


@dataclass
class SyntheseParc:
    """Ce que le parc est, indépendamment de ce qu'il y a à y faire."""

    total: int = 0
    actifs: int = 0
    desactives: int = 0
    dormants: int = 0
    jamais_vus: int = 0
    par_modele: list[tuple[str, int]] = field(default_factory=list)
    par_ou: list[tuple[str, int]] = field(default_factory=list)


@dataclass
class RapportFlotte:
    appareils: list[Appareil] = field(default_factory=list)
    profs: list[LigneProf] = field(default_factory=list)
    a_recuperer: list[LigneProf] = field(default_factory=list)
    """Partants qui détiennent au moins une machine."""
    a_attribuer: list[LigneProf] = field(default_factory=list)
    """Arrivants sans machine."""
    disponibles: list[Appareil] = field(default_factory=list)
    orphelins: list[Appareil] = field(default_factory=list)
    """Étiquetés au nom de quelqu'un qui n'a plus de compte."""
    discordances: list[Discordance] = field(default_factory=list)
    sans_compte: list[LigneProf] = field(default_factory=list)
    """Enseignants du tableau qu'aucun compte Google ne porte."""
    rapproches: list[LigneProf] = field(default_factory=list)
    """Reliés à leur compte par une règle plus souple que l'égalité stricte."""
    etiquettes_a_mettre_a_jour: list[Appareil] = field(default_factory=list)
    """Confiées à quelqu'un dans l'application, mais l'étiquette dit autre chose."""
    recuperees: list[Appareil] = field(default_factory=list)
    parc: SyntheseParc = field(default_factory=SyntheseParc)
    historique: list[MouvementMachine] = field(default_factory=list)
    """Les gestes notés, du plus récent au plus ancien."""
    dormantes: list[Appareil] = field(default_factory=list)
    """Étiquetées au nom de quelqu'un, mais sans signe de vie depuis un an."""
    avertissements: list[str] = field(default_factory=list)

    @property
    def nb_a_recuperer(self) -> int:
        return sum(len(p.appareils) for p in self.a_recuperer)


def _porteur(etiquette: str) -> str | None:
    e = (etiquette or "").strip()
    return e.lower() if ADRESSE.match(e) else None


def analyser_flotte(
    appareils_bruts: list[dict],
    profs: list,
    comptes: list[dict],
    *,
    suivi: dict[str, dict] | None = None,
    prefixe_personnel: str = "/1. Chromebooks/1. Personnel",
) -> RapportFlotte:
    """Croise les machines, le tableau des enseignants et les comptes Google.

    Args:
        appareils_bruts: retour de `ClientGoogle.lister_appareils`.
        profs: les `Prof` lus par `import_profs`.
        comptes: retour de `ClientGoogle.lister_utilisateurs`, pour relier
            un nom du tableau à une adresse — le tableau n'en porte pas.
        suivi: `{série: {recupere_le, attribue_a, …}}`, ce que
            l'établissement a noté avoir fait. Sans lui, l'analyse ne
            décrit que l'état de Google, qui ignore les gestes physiques.
    """
    suivi = suivi or {}
    rapport = RapportFlotte()

    for a in appareils_bruts:
        etiquette = (a.get("etiquette") or "").strip()
        rapport.appareils.append(
            Appareil(
                serie=a.get("serie") or "",
                modele=a.get("modele") or "",
                ou=a.get("ou") or "",
                statut=a.get("statut") or "",
                etiquette=etiquette,
                porteur=_porteur(etiquette),
                derniers_utilisateurs=[
                    u.lower() for u in (a.get("derniers_utilisateurs") or [])
                ],
                emplacement=a.get("emplacement") or "",
                derniere_synchro=a.get("derniere_synchro"),
                recupere_le=(suivi.get(a.get("serie") or "") or {}).get("recupere_le"),
                recupere_de=(suivi.get(a.get("serie") or "") or {}).get("recupere_de"),
                attribue_le=(suivi.get(a.get("serie") or "") or {}).get("attribue_le"),
                attribue_a=(suivi.get(a.get("serie") or "") or {}).get("attribue_a"),
            )
        )

    # Le tableau des enseignants ne porte pas d'adresse : elle vient des
    # comptes, rapprochés par nom et prénom — et les deux ne s'écrivent
    # jamais tout à fait pareil.
    from backend.services.rapprochement import construire_index, rapprocher

    adresses_connues = {
        (c.get("email") or "").lower() for c in comptes if c.get("email")
    }
    index = construire_index(comptes)

    # Une machine confiée dans l'application appartient déjà à son nouveau
    # porteur, quoi qu'en dise l'étiquette : c'est le geste physique qui
    # compte, la console suivra.
    rendues_par = {
        a.recupere_de.lower()
        for a in rapport.appareils
        if a.recupere_le and a.recupere_de
    }

    par_porteur: dict[str, list[Appareil]] = {}
    for ap in rapport.appareils:
        if ap.attribue_a:
            par_porteur.setdefault(ap.attribue_a, []).append(ap)
            if ap.porteur != ap.attribue_a:
                rapport.etiquettes_a_mettre_a_jour.append(ap)
            continue
        if ap.recupere_le:
            rapport.recuperees.append(ap)
            continue
        if ap.porteur:
            par_porteur.setdefault(ap.porteur, []).append(ap)

    for p in profs:
        lien = rapprocher(p.nom, p.prenom, index)
        adresse = lien.email
        ligne = LigneProf(
            nom=p.nom, prenom=p.prenom, discipline=p.discipline, code=p.code,
            email=adresse, appareils=par_porteur.get(adresse, []) if adresse else [],
            methode=lien.methode, approximatif=lien.approximatif,
            homonymes=lien.candidats or [],
        )
        if adresse and lien.approximatif:
            rapport.rapproches.append(ligne)
        ligne.attribue = next(
            (a.serie for a in ligne.appareils if a.attribue_a == adresse), None
        )
        rapport.profs.append(ligne)
        if adresse is None:
            rapport.sans_compte.append(ligne)
        if p.code == "sortant" and ligne.appareils:
            rapport.a_recuperer.append(ligne)
        elif not ligne.appareils and p.code != "sortant":
            # Un remplaçant reçoit une machine du parc de prêt, au même
            # titre qu'un arrivant : il enseigne, il lui en faut une.
            #
            # Et celui dont on a noté la restitution, mais qui figure
            # toujours au tableau, n'est pas parti : il a rendu sa machine
            # avant l'été par précaution, et il est revenu.
            if p.code in ("arrivant", "remplace"):
                ligne.raison = p.code
            elif adresse and adresse in rendues_par:
                ligne.raison = "revenu"
            else:
                # Un titulaire qui n'a jamais eu de machine n'en attend pas
                # une : le signaler noierait les cas qui comptent.
                rapport.profs[-1] = ligne
                continue
            rapport.a_attribuer.append(ligne)

    # Machines libres : le parc de prêt, et celles dont le porteur a disparu.
    for ap in rapport.appareils:
        if not ap.ou.startswith(prefixe_personnel) or not ap.est_actif:
            continue
        if ap.attribue_a:
            continue
        if ap.recupere_le:
            rapport.disponibles.append(ap)
            continue
        if ap.est_de_pret:
            rapport.disponibles.append(ap)
        elif ap.porteur and ap.porteur not in adresses_connues:
            rapport.orphelins.append(ap)
            rapport.disponibles.append(ap)

    # Contre-épreuve : l'étiquette dit une chose, l'usage en dit une autre.
    for ap in rapport.appareils:
        if ap.attribue_a or ap.recupere_le:
            continue
        if not ap.porteur or not ap.derniers_utilisateurs:
            continue
        if ap.porteur not in ap.derniers_utilisateurs:
            rapport.discordances.append(
                Discordance(
                    appareil=ap,
                    attendu=ap.porteur,
                    constates=ap.derniers_utilisateurs[:3],
                )
            )

    if rapport.discordances:
        rapport.avertissements.append(
            f"{len(rapport.discordances)} appareil(s) portent une étiquette que "
            "les connexions démentent. Deux machines échangées par erreur se "
            "voient ici — le programme ne tranche pas, il montre."
        )
    # Le journal : les gestes notés, remis en récit. Les noms viennent des
    # comptes, parce qu'une adresse seule ne dit pas grand-chose trois
    # semaines après.
    noms = {}
    for c in comptes:
        adresse = (c.get("email") or "").lower()
        if adresse:
            entier = f"{c.get('prenom') or ''} {c.get('nom') or ''}".strip()
            noms[adresse] = entier or None

    for a in rapport.appareils:
        if not (a.recupere_le or a.attribue_a):
            continue
        rapport.historique.append(
            MouvementMachine(
                serie=a.serie,
                modele=a.modele,
                etiquette=a.etiquette,
                rendu_par=a.recupere_de,
                rendu_par_nom=noms.get((a.recupere_de or "").lower()),
                rendu_le=a.recupere_le,
                confie_a=a.attribue_a,
                confie_a_nom=noms.get((a.attribue_a or "").lower()),
                confie_le=a.attribue_le,
            )
        )
    rapport.historique.sort(key=lambda m: m.quand, reverse=True)

    # Marquer les appareils selon ce qu'il y a à en faire : c'est cela que
    # la vue du parc colore, et non l'état technique de la machine.
    attendus = {a.serie for p in rapport.a_recuperer for a in p.appareils}
    libres = {a.serie for a in rapport.disponibles}
    for a in rapport.appareils:
        a.a_recuperer = a.serie in attendus
        a.libre = a.serie in libres

    from collections import Counter

    rapport.parc = SyntheseParc(
        total=len(rapport.appareils),
        actifs=sum(1 for a in rapport.appareils if a.est_actif),
        desactives=sum(1 for a in rapport.appareils if not a.est_actif),
        dormants=sum(1 for a in rapport.appareils if a.est_actif and a.dort),
        jamais_vus=sum(
            1 for a in rapport.appareils if a.est_actif and not a.derniere_synchro
        ),
        par_modele=Counter(
            a.modele or "modèle inconnu" for a in rapport.appareils
        ).most_common(),
        par_ou=Counter(a.ou or "sans OU" for a in rapport.appareils).most_common(),
    )

    rapport.dormantes = [
        a for a in rapport.appareils
        if a.porteur and a.dort and a.est_actif and not a.recupere_le
    ]
    revenus = [p for p in rapport.a_attribuer if p.raison == "revenu"]
    if revenus:
        rapport.avertissements.append(
            f"{len(revenus)} enseignant(s) ont rendu leur machine avant l'été et "
            "figurent toujours au tableau : ils sont revenus, et il leur en faut "
            "une de nouveau."
        )
    if rapport.dormantes:
        rapport.avertissements.append(
            f"{len(rapport.dormantes)} appareil(s) portent le nom de quelqu'un "
            "sans avoir synchronisé depuis plus d'un an. Leur étiquette décrit "
            "sans doute un porteur d'avant : ne les réclame pas sans vérifier."
        )
    if rapport.etiquettes_a_mettre_a_jour:
        rapport.avertissements.append(
            f"{len(rapport.etiquettes_a_mettre_a_jour)} machine(s) ont été "
            "confiées dans l'application sans que l'étiquette Google ait suivi. "
            "Le suivi fait foi ici ; la console reste à mettre à jour."
        )
    if rapport.rapproches:
        rapport.avertissements.append(
            f"{len(rapport.rapproches)} enseignant(s) ont été reliés à leur compte "
            "par une règle plus souple que l'égalité stricte — nom composé "
            "tronqué, prénom abrégé, orthographe. Le rapprochement est appliqué "
            "et affiché : un coup d'œil suffit à le démentir."
        )
    ambigus = [p for p in rapport.sans_compte if p.homonymes]
    if ambigus:
        rapport.avertissements.append(
            f"{len(ambigus)} enseignant(s) correspondent à plusieurs comptes à la "
            "fois : choisir reviendrait à tirer au sort."
        )
    if rapport.sans_compte:
        rapport.avertissements.append(
            f"{len(rapport.sans_compte)} enseignant(s) du tableau n'ont pas de "
            "compte Google retrouvé par leur nom : leurs machines ne peuvent pas "
            "leur être rattachées. La liste est dans l'onglet « Sans compte »."
        )
    return rapport


def chercher_appareil(rapport: RapportFlotte, requete: str) -> list[Appareil]:
    """Retrouve un appareil par son numéro, son étiquette ou une adresse.

    C'est l'entrée qui correspond au geste réel : on a la machine en main
    et on lit ce qui est inscrit dessus. Rien n'oblige l'étiquette à être
    juste — la recherche porte aussi sur les derniers utilisateurs, qui,
    eux, ne mentent pas sur qui s'en est servi.
    """
    q = (requete or "").strip().lower()
    if len(q) < 3:
        return []
    trouves = []
    for a in rapport.appareils:
        champs = [a.serie, a.etiquette, a.porteur or "", a.emplacement, a.modele]
        champs += a.derniers_utilisateurs
        if any(q in (c or "").lower() for c in champs):
            trouves.append(a)
    # Le plus récemment vu en premier : c'est celui qu'on a le plus de
    # chances d'avoir entre les mains.
    trouves.sort(key=lambda a: a.derniere_synchro or "", reverse=True)
    return trouves
