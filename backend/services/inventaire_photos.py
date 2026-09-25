"""Qui a une photo, qui n'en a pas, et où elle devrait être.

## Pourquoi un module plutôt qu'une anomalie

Le manque de photos était détecté comme une anomalie parmi huit : un
booléen derrière une case à cocher, qui disait « 9 photos orphelines » sans
dire lesquelles. Or la question posée est toujours la même et toujours
nominative : *« donne-moi la liste, avec nom, prénom et classe »* — parce
qu'elle sert à relancer les professeurs principaux, classe par classe.

Une anomalie répond « il y a un problème ». Ici on veut le fichier qu'on
imprime et qu'on distribue.

## Ce que le module ne fait pas

Il ne va pas chercher la photo ailleurs, ni n'en fabrique une. Il lit le
partage et il compte. La photo elle-même est prise par le photographe, et
déposée par la vie scolaire : le programme constate.

## Le coût, et pourquoi il est assumé ici

Un accès disque par élève sur un partage réseau — deux mille appels. C'est
trop cher pour tourner à chaque ouverture d'écran, et c'est pour cela que
l'accueil ne le lance pas seul. Ici, c'est le sujet de l'écran : on
l'attend, et on le demande.
"""
from __future__ import annotations

import json
import os
import re
from collections import defaultdict
from dataclasses import dataclass, field
from pathlib import Path

from sqlalchemy.orm import Session

from backend.models import Parametre, Personne, Snapshot

EXTENSIONS = (".jpg", ".jpeg", ".png", ".bmp")
"""Ce que CardStudio sait poser sur un badge."""


class InventaireImpossible(Exception):
    """Le relevé est refusé, et le message dit pourquoi."""


@dataclass
class EleveSansPhoto:
    personne_id: int
    nom: str
    prenom: str
    classe: str
    site: str | None
    badge: int | None
    chemin_attendu: str | None
    """Là où le fichier aurait dû se trouver — c'est ce qu'on regarde en
    premier quand on doute du relevé."""

    pistes: list[str] = field(default_factory=list)
    """Fichiers portant ce nom avec une parenthèse qu'on n'a pas su
    rattacher. Les nommer vaut mieux que les taire : c'est souvent la
    photo, sous une abréviation de classe que le référentiel n'écrit pas
    ainsi."""


@dataclass
class InventairePhotos:
    dossier: str = ""
    type_personne: str = "eleve"
    nb_eleves: int = 0
    nb_avec: int = 0
    manquantes: list[EleveSansPhoto] = field(default_factory=list)
    par_classe: dict[str, dict[str, int]] = field(default_factory=dict)
    """`{classe: {"avec": n, "sans": n}}` — la maille à laquelle on relance."""
    dossiers_injoignables: dict[str, int] = field(default_factory=dict)
    """`{dossier: nb de personnes}` pour les dossiers qu'on n'a pas pu lire.

    Ces personnes ne sont **pas** comptées sans photo : on ne sait rien
    d'elles. Le cas se présente dès qu'un site a son propre dossier et que
    le partage n'est pas encore en place — le relevé des deux autres ne
    doit pas en tomber, ni ce site-là passer pour vide."""

    @property
    def nb_sans(self) -> int:
        return len(self.manquantes)

    @property
    def nb_a_verifier(self) -> int:
        """Manquantes pour lesquelles un fichier presque juste existe."""
        return sum(1 for e in self.manquantes if e.pistes)

    @property
    def taux(self) -> float:
        return self.nb_avec / self.nb_eleves if self.nb_eleves else 0.0

    @property
    def classes_incompletes(self) -> list[str]:
        """Celles où il manque au moins une photo, les pires d'abord."""
        return [
            c
            for c, n in sorted(
                self.par_classe.items(), key=lambda kv: (-kv[1]["sans"], kv[0])
            )
            if n["sans"]
        ]


def dossier_photos(session: Session, *, type_personne: str = "eleve") -> str | None:
    """Le dossier de cette population.

    Les photos du personnel vivent à part, hors de l'arborescence par
    année : un seul réglage ne peut pas servir les deux.
    """
    cle = (
        "chemin_dossier_photos_adultes"
        if type_personne == "adulte"
        else "chemin_dossier_photos"
    )
    param = session.query(Parametre).filter_by(cle=cle).one_or_none()
    if param is None:
        return None
    try:
        return json.loads(param.valeur_json) or None
    except (json.JSONDecodeError, TypeError):
        return None


def dossier_de(
    session: Session,
    personne: Personne,
    *,
    sites: dict | None = None,
    communs: dict[str, str | None] | None = None,
) -> str | None:
    """Le dossier où chercher la photo de cette personne.

    Celui de **son site** quand le site en a un, sinon le dossier commun de
    sa population. NDK et SU partagent le dossier de Charlemagne ; NDE a
    ses photos à part, et les mélanger ferait se disputer les homonymes des
    deux établissements — une carte pourrait porter le visage d'un autre.

    C'est l'unique endroit où la règle s'écrit : les avatars, l'inventaire
    et les cartes la lisent tous ici.

    Args:
        sites: `{id: Site}` déjà chargé, pour ne pas relire la table à
            chaque personne d'un relevé de deux mille.
        communs: `{population: dossier}`, rempli au fil de l'eau — même
            raison : relire le paramètre pour chacun coûtait un tiers de
            seconde au relevé.
    """
    from backend.models import Site

    if sites is None:
        site = session.get(Site, personne.site_id) if personne.site_id else None
    else:
        site = sites.get(personne.site_id)
    if site is not None:
        propre = (
            site.dossier_photos_adultes
            if personne.type == "adulte"
            else site.dossier_photos_eleves
        )
        if (propre or "").strip():
            return propre.strip()
    if communs is None:
        return dossier_photos(session, type_personne=personne.type)
    if personne.type not in communs:
        communs[personne.type] = dossier_photos(session, type_personne=personne.type)
    return communs[personne.type]


def _sans_separateurs(texte: str) -> str:
    """`BTS_2` et `BTS2` désignent la même classe."""
    return re.sub(r"[\s_\-.]", "", texte or "").casefold()


def _bases(personne: Personne) -> list[str]:
    """Les écritures du nom rencontrées sur le partage.

    Charlemagne nomme d'après l'état civil, avec des variations selon
    l'export. On essaie les formes vues plutôt que d'en imposer une :
    déclarer manquante une photo qui est là ferait relancer une famille
    pour rien.
    """
    nom = (personne.nom or "").strip()
    prenom = (personne.prenom or "").strip()
    bases = [f"{nom} {prenom}", f"{nom}_{prenom}", f"{prenom} {nom}"]
    if personne.badge:
        bases.append(str(personne.badge))
    return bases


def _candidats(racine: Path, personne: Personne) -> list[Path]:
    """Les chemins exacts attendus, dans l'ordre de préférence."""
    return [racine / f"{b}{ext}" for b in _bases(personne) for ext in EXTENSIONS]


class Noms(set):
    """Les noms d'un dossier, repliés — et ceux à parenthèse, rangés par nom.

    Chercher les homonymes d'un élève parcourait tout le dossier : deux
    mille élèves, deux mille fichiers, quatre écritures du nom chacun —
    quinze millions de comparaisons, une seconde et demie du relevé. Rangés
    une fois par ce qui précède la parenthèse, ils se retrouvent d'un coup.
    """

    def __init__(self, noms=()):
        super().__init__(noms)
        self.parentheses: dict[str, list[str]] = defaultdict(list)
        for n in self:
            i = n.find(" (")
            while i >= 0:
                self.parentheses[n[:i]].append(n)
                i = n.find(" (", i + 1)


def _homonymes(presents: set[str], base: str) -> list[str]:
    """Les fichiers `NOM Prénom (quelque chose)` portant ce nom.

    Deux élèves du même nom ne peuvent pas partager un fichier : la vie
    scolaire ajoute alors la classe entre parenthèses — `SAOUT Marie (44)`
    et `SAOUT Marie (BTS2)`. Sans les chercher, les deux sont déclarées
    sans photo alors qu'elles en ont chacune une.
    """
    cle = base.casefold()
    candidats = (
        presents.parentheses.get(cle, ()) if isinstance(presents, Noms) else presents
    )
    prefixe = f"{cle} ("
    return sorted(
        n
        for n in candidats
        if n.startswith(prefixe) and Path(n).suffix.casefold() in EXTENSIONS
    )


def _trouver(presents: set[str], personne: Personne, classe: str) -> str | None:
    """Le fichier de cette personne, quand il ne fait aucun doute.

    La parenthèse porte la classe, mais pas toujours telle que le
    référentiel l'écrit : `(BTS2)` se déduit de `BTS_2`, `(TMCV1)` ne se
    déduit pas de `T_BPMCV1`. On ne tranche que ce qui se déduit —
    attribuer au jugé mettrait le visage d'une élève sur la carte de son
    homonyme.
    """
    # La parenthèse d'abord : elle désigne quelqu'un exprès, quand le nom
    # nu ne désigne que « la personne qui s'appelle ainsi ».
    classe_normalisee = _sans_separateurs(classe)
    if classe_normalisee:
        for base in _bases(personne):
            for fichier in _homonymes(presents, base):
                suffixe = fichier[len(base) + 2 : fichier.rfind(")")]
                if _sans_separateurs(suffixe) == classe_normalisee:
                    return fichier

    for base in _bases(personne):
        for ext in EXTENSIONS:
            if f"{base}{ext}".casefold() in presents:
                return f"{base}{ext}"
    return None


def _pistes(
    presents: set[str],
    personne: Personne,
    pris: set[str],
    disputes: set[str],
) -> list[str]:
    """Les fichiers portant ce nom qui restent à rattacher.

    Deux sortes : les parenthésés dont le suffixe n'a pas été reconnu, et
    le fichier au nom nu que plusieurs personnes revendiquaient. Les deux
    méritent d'être nommés — un fichier retiré du compte sans être montré
    laisse croire qu'il n'existe pas.

    Un fichier attribué avec certitude à quelqu'un n'est en revanche jamais
    proposé à un autre : ce serait inviter précisément l'erreur que la
    parenthèse existe pour éviter.
    """
    vus: list[str] = []
    for base in _bases(personne):
        vus += [f for f in _homonymes(presents, base) if f not in pris]
        vus += [
            f"{base}{ext}".casefold()
            for ext in EXTENSIONS
            if f"{base}{ext}".casefold() in disputes
        ]
    return sorted(set(vus))


@dataclass
class Lecture:
    """Un dossier du partage, lu une fois."""

    racine: Path
    dossier: str
    reels: dict[str, str]
    """Nom de fichier replié → nom réel. Le partage se lit sans égard à la
    casse, mais un chemin qu'on écrit dans un fichier doit être le vrai."""
    presents: set[str]
    disputes: set[str] = field(default_factory=set)
    pris: set[str] = field(default_factory=set)


@dataclass
class Parcours:
    """Le partage lu une fois, et ce qu'on en a déduit.

    Deux écrans posent la même question au même dossier : *qui a sa
    photo ?* pour relancer les familles, et *où est-elle ?* pour la poser
    sur une carte. La règle du fichier disputé — une image revendiquée par
    deux homonymes n'appartient à aucun des deux — ne doit exister qu'à un
    seul endroit : dupliquée, elle finirait par diverger, et la carte
    porterait le visage que la liste déclarait douteux.

    ## Un dossier par site, quand il le faut

    Les disputes se jugent **dans un dossier**, jamais entre deux : un
    `MARTIN Léa.jpg` dans le dossier de NDE et un autre dans celui de NDK
    sont deux photos de deux élèves, pas une photo que deux élèves se
    disputent.
    """

    lectures: dict[str, Lecture]
    retenus: list[tuple[Personne, str, str | None, Lecture]]
    """(personne, classe, fichier trouvé — replié, dossier où il l'a été)."""
    sites: dict[int, str]
    injoignables: dict[str, int] = field(default_factory=dict)

    @property
    def dossier(self) -> str:
        """Les dossiers lus, pour l'affichage."""
        return " · ".join(self.lectures) or ""


def _parcourir(
    session: Session, *, annee_id: int, type_personne: str
) -> Parcours:
    """Lit le partage et attribue ce qui ne fait pas de doute.

    Raises:
        InventaireImpossible: aucun dossier réglé, ou aucun joignable — les
            deux se disent différemment, parce qu'ils se corrigent
            différemment. Un seul dossier injoignable parmi plusieurs ne
            fait pas tomber le relevé : ses personnes sont mises de côté,
            et le rapport le dit.
    """
    from backend.models import Site

    tous_sites = {s.id: s for s in session.query(Site).all()}
    sites = {i: s.nom for i, s in tous_sites.items()}

    derniers: dict[int, Snapshot] = {}
    for sn in session.query(Snapshot).filter(Snapshot.annee_scolaire_id == annee_id):
        prec = derniers.get(sn.personne_id)
        if prec is None or (
            sn.date_ingestion
            and prec.date_ingestion
            and sn.date_ingestion > prec.date_ingestion
        ):
            derniers[sn.personne_id] = sn

    # Présent cette année, et lui seul : sans ce filtre, tout le personnel
    # passé serait compté comme sans photo, et la liste des relances serait
    # pleine de gens partis depuis des années.
    presents_annee = [
        (p, derniers[p.id])
        for p in session.query(Personne).filter(Personne.type == type_personne).all()
        if p.id in derniers
    ]
    communs: dict[str, str | None] = {}
    dossier_par_personne = {
        p.id: dossier_de(session, p, sites=tous_sites, communs=communs)
        for p, _ in presents_annee
    }
    # Le dossier commun est toujours du nombre, même si personne n'y est
    # attendu cette année : un réglage fait et un partage absent ne se
    # disent pas pareil, et on ne le saurait pas sans le lire.
    commun = dossier_photos(session, type_personne=type_personne)
    voulus = {d for d in dossier_par_personne.values() if d} | (
        {commun} if commun else set()
    )
    if not voulus:
        qui = "adultes" if type_personne == "adulte" else "élèves"
        raise InventaireImpossible(
            f"Le dossier des photos {qui} n'est pas réglé. Il se déclare "
            "dans les Paramètres — c'est le partage où Charlemagne les dépose."
        )

    # Un seul parcours par dossier plutôt qu'un test par nom candidat : sur
    # un partage réseau, lister une fois coûte bien moins que deux mille
    # interrogations de fichier.
    lectures: dict[str, Lecture] = {}
    injoignables: dict[str, int] = {}
    for dossier in sorted(voulus):
        racine = Path(dossier)
        if not racine.exists():
            injoignables[dossier] = 0
            continue
        # `os.scandir` et non `Path.iterdir` : l'entrée d'un listage sait
        # déjà si elle est un fichier, quand `Path.is_file()` le redemande
        # au serveur. Deux mille allers-retours SMB, c'était huit secondes
        # sur le partage réel ; le listage seul en prend quelques millièmes.
        with os.scandir(racine) as entrees:
            reels = {
                e.name.casefold(): e.name
                for e in entrees
                if os.path.splitext(e.name)[1].casefold() in EXTENSIONS
                and e.is_file()
            }
        lectures[dossier] = Lecture(
            racine=racine, dossier=dossier, reels=reels, presents=Noms(reels)
        )
    if not lectures:
        raise InventaireImpossible(
            "Dossier introuvable : "
            + ", ".join(sorted(injoignables))
            + ". Le partage réseau est-il monté sur ce poste ?"
        )

    # Première passe : qui revendique quoi, dossier par dossier. Rien n'est
    # attribué encore.
    retenus: list[tuple[Personne, str, str | None, Lecture]] = []
    revendications: dict[tuple[str, str], int] = defaultdict(int)
    for p, sn in presents_annee:
        dossier = dossier_par_personne.get(p.id)
        if not dossier:
            continue
        lecture = lectures.get(dossier)
        if lecture is None:
            injoignables[dossier] += 1
            continue
        # Un adulte n'a pas de classe : sa maille de regroupement est son
        # site. Exiger une classe l'écarterait purement et simplement.
        classe = (
            (sn.classe or "").strip()
            if type_personne == "eleve"
            else (sites.get(p.site_id) or "Sans site")
        )
        if not classe:
            continue
        trouve = _trouver(
            lecture.presents, p, classe if type_personne == "eleve" else ""
        )
        if trouve:
            revendications[(dossier, trouve.casefold())] += 1
        retenus.append((p, classe, trouve, lecture))

    # Un fichier revendiqué par deux personnes n'appartient à aucune des
    # deux : `BELLEC Manon.jpg` existe à côté de `BELLEC Manon (21).jpg` et
    # `(TMCV1).jpg`, et les deux Manon s'en réclamaient — chacune comptée
    # « avec photo », sur la même image. C'est précisément ce que la
    # parenthèse existe pour éviter ; on rend donc le fichier au doute.
    for (dossier, fichier), n in revendications.items():
        (lectures[dossier].disputes if n > 1 else lectures[dossier].pris).add(fichier)

    return Parcours(
        lectures=lectures,
        retenus=retenus,
        sites=sites,
        injoignables=injoignables,
    )


def chemins_attribues(
    session: Session, *, annee_id: int, type_personne: str = "eleve"
) -> dict[int, str]:
    """Le chemin réseau de la photo, pour qui en a une sans conteste.

    C'est ce que CardStudio réclame : pas un nom de fichier reconstruit à
    la volée, mais le chemin d'un fichier dont on vient de constater
    l'existence. Une carte se fabrique une fois ; un chemin faux ne se
    découvre qu'à l'impression, sur une carte déjà gâchée.

    Les absents et les litiges sont simplement **hors du dictionnaire** :
    l'appelant décide quoi en faire, et il doit le décider.
    """
    parcours = _parcourir(session, annee_id=annee_id, type_personne=type_personne)
    # `_trouver` rend tantôt le nom tel que la personne s'écrit (branche du
    # nom nu), tantôt une entrée déjà repliée (branche des homonymes). C'est
    # la forme repliée qui indexe le partage, ici comme dans les revendications.
    attribues: dict[int, str] = {}
    for p, _classe, trouve, lecture in parcours.retenus:
        if not trouve:
            continue
        cle = trouve.casefold()
        if cle in lecture.disputes or cle not in lecture.reels:
            continue
        attribues[p.id] = str(lecture.racine / lecture.reels[cle])
    return attribues


def relever(
    session: Session, *, annee_id: int, type_personne: str = "eleve"
) -> InventairePhotos:
    """Qui a sa photo sur le partage, et qui ne l'a pas.

    Args:
        type_personne: `eleve` ou `adulte`. Chacun a son dossier, et ils ne
            se recoupent pas — chercher un professeur parmi les photos
            d'élèves ne ferait que des absences fausses.

    Raises:
        InventaireImpossible: dossier non réglé, ou inaccessible.
    """
    parcours = _parcourir(session, annee_id=annee_id, type_personne=type_personne)
    sites = parcours.sites

    inventaire = InventairePhotos(
        dossier=parcours.dossier,
        type_personne=type_personne,
        dossiers_injoignables=dict(parcours.injoignables),
    )
    par_classe: dict[str, dict[str, int]] = defaultdict(lambda: {"avec": 0, "sans": 0})

    # Seconde passe : ce qui reste, et les pistes encore libres — dans le
    # dossier de chacun.
    for p, classe, trouve, lecture in parcours.retenus:
        presents, disputes, pris = lecture.presents, lecture.disputes, lecture.pris
        inventaire.nb_eleves += 1
        if trouve and trouve.casefold() not in disputes:
            inventaire.nb_avec += 1
            par_classe[classe]["avec"] += 1
            continue

        candidats = _candidats(lecture.racine, p)
        par_classe[classe]["sans"] += 1
        inventaire.manquantes.append(
            EleveSansPhoto(
                personne_id=p.id,
                nom=p.nom or "",
                prenom=p.prenom or "",
                classe=classe,
                site=sites.get(p.site_id),
                badge=p.badge,
                chemin_attendu=str(candidats[0]) if candidats else None,
                pistes=_pistes(presents, p, pris, disputes),
            )
        )

    inventaire.manquantes.sort(key=lambda e: (e.classe, e.nom, e.prenom))
    inventaire.par_classe = dict(par_classe)
    return inventaire


def classeur(inventaire: InventairePhotos) -> bytes:
    """La liste des manquantes, triée par classe — celle qu'on distribue."""
    import io

    import openpyxl

    classeur = openpyxl.Workbook()
    feuille = classeur.active
    feuille.title = "Photos manquantes"
    feuille.append(["Classe", "Nom", "Prénom", "Site", "Badge", "Fichier attendu"])
    for e in inventaire.manquantes:
        feuille.append(
            [e.classe, e.nom, e.prenom, e.site or "", e.badge or "", e.chemin_attendu or ""]
        )
    for colonne, largeur in zip("ABCDEF", (12, 26, 20, 8, 10, 60)):
        feuille.column_dimensions[colonne].width = largeur

    tampon = io.BytesIO()
    classeur.save(tampon)
    return tampon.getvalue()
