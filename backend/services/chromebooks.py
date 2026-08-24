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

## Trois noms pour une seule machine

Un appareil peut porter un autocollant à un nom, une étiquette Google à un
autre, et servir tous les jours à un troisième. C'est arrivé : étiquette
`julien.martial`, autocollant `adele.lemordant`, connexions
`samuel.ouchia-lebars`. Aucun de ces trois n'est faux ; ils datent
simplement d'époques différentes.

Devant une machine pareille, la question n'est pas « à qui est-elle ? »
mais « qu'est-ce qu'on sait d'elle ? ». Le rapport rassemble donc, pour
chaque appareil, ce que chaque source en dit — sans arbitrer entre elles —
plus deux renseignements qui font souvent basculer la décision : la
personne étiquetée est-elle encore là, et combien d'autres machines
portent le même nom.

## Le tableau des enseignants ne couvre pas tout le monde

Une machine étiquetée au nom d'une AESH restait muette : la personne
n'apparaît pas au tableau des professeurs, donc rien à en dire. C'était
regarder par la mauvaise fenêtre. Le compte Google, lui, existe pour tout
le monde, et l'unité d'organisation où il est rangé dit à quel titre la
personne est là — `/6. Personnel/AESH`, `/5. Professeurs`,
`/7. Sortis/Profs sortis`.

Le rapport interroge donc les deux : le tableau pour le mouvement de
l'année, le compte pour l'existence, la suspension, l'emplacement et la
dernière connexion. Un compte absent, suspendu, ou rangé dans une branche
de sortie explique à lui seul qu'une machine soit revenue.

## Quand rien n'explique un retour

Une machine posée sur le bureau appelle une explication, et le programme
en trouve souvent une : le porteur est parti, son compte a disparu,
l'appareil est désactivé, il en avait un autre. Mais il arrive que tous
les signaux disent le contraire — la personne est en poste, son compte est
actif, c'est sa seule machine et elle a servi la semaine dernière.

Le dire vaut mieux que de rester vague. L'absence d'explication est
elle-même un constat : la raison est hors de ce que l'application voit, et
la seule suite utile est d'aller la demander. La note recueille la réponse.

## Lire, et pas seulement montrer

Aligner des champs ne suffit pas. « Étiquette julien.martial, connexions
samuel.ouchia-lebars, porteur en congé formation » : les trois faits sont
là, mais c'est leur rapprochement qui dit la chose — Julien est absent
cette année, Samuel se sert de sa machine pendant ce temps.

Le rapport propose donc une **lecture** : une ou deux phrases qui relient
les faits. Chacune vient d'une règle nommée, vérifiable en relisant les
champs affichés juste à côté. Ce qui relève de l'inférence le dit —
« sans doute », « probablement » — parce qu'une machine qui change de
mains ne laisse pas de trace, et que le programme ne fera jamais mieux que
supposer.

Aucune de ces phrases ne décide quoi que ce soit. Elles épargnent le
raisonnement, pas le jugement.

## Une machine rendue n'est pas forcément réattribuable

Google désactive un appareil qu'on a retiré du parc, et son étiquette lui
survit : on retrouve donc des machines au nom de quelqu'un qui n'y est
pour rien, parfois sans synchronisation depuis des années. Les rendre ne
les remet pas en circulation — mais ne rien dire laisse chercher pourquoi
elles n'apparaissent nulle part.

Chaque appareil porte donc, le cas échéant, **le motif** qui l'écarte des
machines disponibles. Et une note libre permet d'inscrire ce qu'on a
décidé d'en faire, puisque le programme ne peut pas le déduire.

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
    motif_indisponible: str | None = None
    """Pourquoi elle ne rejoint pas les machines à attribuer."""
    note: str | None = None
    """Ce que l'établissement a décidé d'en faire. Texte libre."""
    porteur_en_poste: bool | None = None
    """La personne de l'étiquette figure-t-elle encore au tableau ? `None`
    si l'étiquette ne désigne personne d'identifiable."""
    porteur_code: str | None = None
    """Son mouvement : `sortant`, `en_poste`, `arrivant`…"""
    homonymes_etiquette: int = 0
    """Autres machines portant la même étiquette. Trois pour une même
    enseignante signale des étiquettes jamais corrigées."""
    autres_machines_actives: int = 0
    """Autres appareils en service au même nom.

    Déclaré ici avec une valeur par défaut, et pas seulement affecté
    dans la boucle qui le calcule : celle-ci saute les appareils sans
    porteur, qui se retrouvaient alors dépourvus de l'attribut — et la
    lecture échouait sur eux.
    """
    lecture: list[str] = field(default_factory=list)
    """Ce que les faits, mis ensemble, racontent de cette machine."""
    porteur_compte_existe: bool | None = None
    porteur_ou: str | None = None
    """Unité d'organisation du compte : elle dit à quel titre la personne
    est là, quand le tableau des enseignants ne la connaît pas."""
    porteur_suspendu: bool | None = None
    porteur_vu_le: str | None = None
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
    remplace_qui: str | None = None
    """Nom de la personne remplacée, quand la raison est `remplace`."""
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
    note: str | None = None
    motif_indisponible: str | None = None

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
                note=(suivi.get(a.get("serie") or "") or {}).get("note"),
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
            remplace_qui=getattr(p, "remplace_qui", None),
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
    # Marquer les appareils selon ce qu'il y a à en faire : c'est cela que
    # la vue du parc colore, et non l'état technique de la machine.
    attendus = {a.serie for p in rapport.a_recuperer for a in p.appareils}
    libres = {a.serie for a in rapport.disponibles}
    for a in rapport.appareils:
        a.a_recuperer = a.serie in attendus
        a.libre = a.serie in libres
        if a.libre or a.attribue_a:
            continue
        # Une machine qu'on vient de rendre et qui n'apparaît pas parmi les
        # disponibles doit dire pourquoi : sans motif, on la cherche.
        if not a.est_actif:
            a.motif_indisponible = (
                "désactivée dans Google — elle ne peut plus être réattribuée"
            )
        elif not a.ou.startswith(prefixe_personnel):
            a.motif_indisponible = (
                f"hors du parc du personnel ({a.ou}) — le programme ne la "
                "propose pas pour un enseignant"
            )
        elif a.recupere_le:
            a.motif_indisponible = (
                "rendue, mais son étiquette désigne encore quelqu'un : "
                "corrige-la dans la console pour qu'elle redevienne disponible"
            )

    # Ce que chaque source dit de l'appareil, sans arbitrer entre elles.
    from collections import Counter as _Compteur

    porte_par = _Compteur(a.porteur for a in rapport.appareils if a.porteur)
    mouvement_par_adresse = {
        p.email: p.code for p in rapport.profs if p.email
    }
    # Le compte existe pour tout le monde, là où le tableau ne couvre que
    # les enseignants : c'est lui qui renseigne sur une AESH, un agent, ou
    # quelqu'un déjà rangé dans une branche de sortie.
    comptes_par_adresse = {
        (c.get("email") or "").lower(): c for c in comptes if c.get("email")
    }

    for a in rapport.appareils:
        if not a.porteur:
            continue
        a.homonymes_etiquette = porte_par[a.porteur] - 1
        a.autres_machines_actives = sum(
            1
            for autre in rapport.appareils
            if autre.porteur == a.porteur
            and autre.serie != a.serie
            and autre.est_actif
            and not autre.dort
        )
        code = mouvement_par_adresse.get(a.porteur)
        if code is not None:
            a.porteur_code = code
            a.porteur_en_poste = code != "sortant"

        compte = comptes_par_adresse.get(a.porteur)
        a.porteur_compte_existe = compte is not None
        if compte is not None:
            a.porteur_ou = compte.get("ou")
            a.porteur_suspendu = bool(compte.get("suspendu"))
            a.porteur_vu_le = compte.get("derniere_connexion")

    # Les personnes que le rapport vient de conclure « revenues » : la
    # lecture s'en sert pour ne pas dire inexpliqué un retour qu'il a
    # lui-même expliqué.
    revenus = {
        p.email for p in rapport.a_attribuer if p.raison == "revenu" and p.email
    }

    for a in rapport.appareils:
        a.lecture = _lire(a, mouvement_par_adresse, revenus)

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
                note=a.note,
                motif_indisponible=a.motif_indisponible,
            )
        )
    rapport.historique.sort(key=lambda m: m.quand, reverse=True)

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


# Libellés des mouvements, pour des phrases qui se lisent à voix haute.
_MOUVEMENTS = {
    "sortant": "quitte l'établissement",
    "arrivant": "vient d'arriver",
    "formation": "est en congé formation cette année",
    "remplace": "est remplacé une partie de l'année",
    "en_poste": "est toujours en poste",
}


# Branches où un compte encore actif signale autre chose qu'un enseignant
# en poste — une sortie déjà rangée, ou un autre statut dans la maison.
_BRANCHES_SORTIE = ("/7. Sortis",)


def _lire(
    a: Appareil,
    mouvements: dict[str, str],
    revenus: set[str] | None = None,
) -> list[str]:
    """Relie les faits d'un appareil en une ou deux phrases.

    Chaque phrase vient d'une règle nommée par son commentaire, et se
    vérifie sur les champs affichés à côté. Ce qui relève de la supposition
    le dit : une machine qui change de mains ne laisse pas de trace.
    """
    phrases: list[str] = []
    premier = a.derniers_utilisateurs[0] if a.derniers_utilisateurs else None
    mouvement = _MOUVEMENTS.get(a.porteur_code or "")

    # Hors service : c'est le fait qui prime sur tous les autres.
    if not a.est_actif:
        phrases.append(
            "Google a désactivé cet appareil : il ne peut plus être remis en "
            "service ni réattribué."
            + (
                f" Il ne s'est plus synchronisé depuis {a.derniere_synchro[:4]}."
                if a.derniere_synchro
                else " Il ne s'est jamais synchronisé."
            )
        )
        if a.porteur:
            phrases.append(
                "Son étiquette porte encore un nom : elle date d'avant sa mise "
                "hors service, et n'apprend rien sur qui l'avait en dernier."
            )
        return phrases

    # Une absence explique presque toujours qu'un autre s'en serve.
    if a.porteur and premier and premier != a.porteur and a.porteur_code in (
        "formation",
        "remplace",
    ):
        phrases.append(
            f"La personne étiquetée {mouvement} : c'est {premier} qui s'en sert "
            "pendant ce temps. Rien d'anormal."
        )

    # Un partant qui s'en sert encore : c'est la machine qu'on va réclamer.
    # La condition de fraîcheur est essentielle : la liste des derniers
    # utilisateurs est un historique, pas un présent. Sur une machine
    # endormie depuis deux ans, « s'en servait récemment » est faux, et la
    # phrase contredirait celle qui suit.
    elif a.porteur_code == "sortant" and premier == a.porteur and not a.dort:
        phrases.append(
            "La personne étiquetée quitte l'établissement et s'en servait "
            "encore récemment : c'est bien cette machine qu'il faut lui "
            "réclamer."
        )

    # L'étiquette contredite sans explication : un changement de mains.
    elif a.porteur and premier and premier != a.porteur:
        phrases.append(
            f"L'étiquette dit {a.porteur}, mais c'est {premier} qui s'en sert. "
            "La machine a sans doute changé de mains sans être réétiquetée."
        )

    # Plusieurs machines au même nom, dont celle-ci dort : l'étiquette a vécu.
    if a.homonymes_etiquette and a.dort:
        phrases.append(
            f"{a.homonymes_etiquette + 1} machines portent cette étiquette, et "
            "celle-ci ne donne plus signe de vie : la sienne est probablement "
            "l'une des autres."
        )
    elif a.dort:
        phrases.append(
            "Aucune connexion depuis plus d'un an. L'appareil est rangé "
            "quelque part, en panne, ou perdu — son étiquette ne dit plus où "
            "il est."
        )
    elif a.est_actif and not a.derniers_utilisateurs:
        phrases.append(
            "Aucune connexion enregistrée : appareil neuf, ou gardé en réserve "
            "sans avoir jamais servi."
        )

    # Ce que le compte du porteur apprend, quand le tableau se tait.
    if a.porteur:
        if a.porteur_compte_existe is False:
            phrases.append(
                "Le compte de la personne étiquetée n'existe plus dans Google : "
                "elle a quitté l'établissement, et la machine peut être "
                "réattribuée."
            )
        elif a.porteur_suspendu:
            phrases.append(
                "Son compte est suspendu : elle n'est plus en activité, "
                "ce qui explique que la machine soit revenue."
            )
        elif a.porteur_ou and a.porteur_ou.startswith(_BRANCHES_SORTIE):
            phrases.append(
                f"Son compte est rangé dans {a.porteur_ou} : elle est déjà "
                "traitée comme sortie."
            )
        elif a.porteur_code is None and a.porteur_ou:
            # Le silence du programme avait une cause : le tableau ne couvre
            # que les enseignants. Le dire vaut mieux que ne rien dire.
            phrases.append(
                f"Elle ne figure pas au tableau des enseignants — son compte "
                f"est rangé dans {a.porteur_ou}, elle n'y est donc pas à ce "
                "titre. Le programme ne connaît pas son mouvement de l'année."
                + (
                    f" Dernière connexion : {a.porteur_vu_le[:10]}."
                    if a.porteur_vu_le
                    else " Elle ne s'est jamais connectée."
                )
            )

    # Repris alors que son porteur est toujours là. Trois situations
    # distinctes, qui n'appellent pas la même conclusion.
    if a.recupere_le and a.porteur_en_poste and a.porteur_code != "sortant":
        if a.porteur in (revenus or ()):
            # Le rapport a déjà tiré la conséquence de cette reprise : dire
            # ici que rien ne l'explique contredirait l'autre écran.
            phrases.append(
                "Cette reprise est ce qui fait figurer la personne parmi "
                "celles à rééquiper : elle a rendu sa machine et elle est "
                "toujours au tableau. Attribue-lui une machine du parc de "
                "prêt quand elle revient."
            )
        elif a.autres_machines_actives:
            phrases.append(
                f"La personne étiquetée est toujours au tableau, et elle a "
                f"{a.autres_machines_actives} autre(s) machine(s) en service : "
                "celle-ci est vraisemblablement un ancien appareil dont "
                "l'étiquette a survécu. Elle ne manque donc à personne."
            )
        elif a.est_actif and not a.dort:
            # Tous les signaux contredisent un retour. Le dire franchement
            # vaut mieux qu'une phrase prudente qui n'aide personne.
            phrases.append(
                "Rien n'explique ce retour : la personne est en poste, son "
                "compte est actif"
                + (f" (vu le {a.porteur_vu_le[:10]})" if a.porteur_vu_le else "")
                + ", et c'est sa seule machine en service"
                + (
                    f", utilisée jusqu'au {a.derniere_synchro[:10]}"
                    if a.derniere_synchro
                    else ""
                )
                + ". La raison est hors de ce que le programme voit — panne, "
                "échange, dépôt avant l'été. Demande-lui, et note la réponse "
                "ici."
            )
        else:
            phrases.append(
                "Tu l'as reprise alors que la personne étiquetée est toujours "
                "au tableau, mais cet appareil ne donne plus signe de vie : "
                "c'est sans doute un ancien, dont l'étiquette a survécu."
            )

    return phrases
