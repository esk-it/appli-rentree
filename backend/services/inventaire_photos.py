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


def _homonymes(presents: set[str], base: str) -> list[str]:
    """Les fichiers `NOM Prénom (quelque chose)` portant ce nom.

    Deux élèves du même nom ne peuvent pas partager un fichier : la vie
    scolaire ajoute alors la classe entre parenthèses — `SAOUT Marie (44)`
    et `SAOUT Marie (BTS2)`. Sans les chercher, les deux sont déclarées
    sans photo alors qu'elles en ont chacune une.
    """
    prefixe = f"{base.casefold()} ("
    return sorted(
        n
        for n in presents
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


def relever(
    session: Session, *, annee_id: int, type_personne: str = "eleve"
) -> InventairePhotos:
    """Qui a sa photo sur le partage, et qui ne l'a pas.

    Args:
        type_personne: `eleve` ou `adulte`. Chacun a son dossier, et ils ne
            se recoupent pas — chercher un professeur parmi les photos
            d'élèves ne ferait que des absences fausses.

    Raises:
        InventaireImpossible: dossier non réglé, ou inaccessible — les deux
            se disent différemment, parce qu'ils se corrigent différemment.
    """
    dossier = dossier_photos(session, type_personne=type_personne)
    if not dossier:
        qui = "adultes" if type_personne == "adulte" else "élèves"
        raise InventaireImpossible(
            f"Le dossier des photos {qui} n'est pas réglé. Il se déclare "
            "dans les Paramètres — c'est le partage où Charlemagne les dépose."
        )
    racine = Path(dossier)
    if not racine.exists():
        raise InventaireImpossible(
            f"Dossier introuvable : {dossier}. Le partage réseau est-il monté "
            "sur ce poste ?"
        )

    derniers: dict[int, Snapshot] = {}
    for sn in session.query(Snapshot).filter(Snapshot.annee_scolaire_id == annee_id):
        prec = derniers.get(sn.personne_id)
        if prec is None or (
            sn.date_ingestion
            and prec.date_ingestion
            and sn.date_ingestion > prec.date_ingestion
        ):
            derniers[sn.personne_id] = sn

    # Un seul parcours du dossier plutôt qu'un test par nom candidat : sur un
    # partage réseau, lister une fois coûte bien moins que deux mille
    # interrogations de fichier.
    presents = {
        f.name.casefold()
        for f in racine.iterdir()
        if f.is_file() and f.suffix.casefold() in EXTENSIONS
    }

    from backend.models import Site

    sites = {s.id: s.nom for s in session.query(Site).all()}
    inventaire = InventairePhotos(dossier=dossier, type_personne=type_personne)
    par_classe: dict[str, dict[str, int]] = defaultdict(lambda: {"avec": 0, "sans": 0})

    # Première passe : qui revendique quoi. Rien n'est attribué encore.
    retenus: list[tuple[Personne, str, str | None]] = []
    revendications: dict[str, int] = defaultdict(int)
    for p in session.query(Personne).filter(Personne.type == type_personne).all():
        sn = derniers.get(p.id)
        # Présent cette année, et lui seul : sans ce filtre, tout le
        # personnel passé serait compté comme sans photo, et la liste des
        # relances serait pleine de gens partis depuis des années.
        if sn is None:
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
            presents, p, classe if type_personne == "eleve" else ""
        )
        if trouve:
            revendications[trouve.casefold()] += 1
        retenus.append((p, classe, trouve))

    # Un fichier revendiqué par deux personnes n'appartient à aucune des
    # deux : `BELLEC Manon.jpg` existe à côté de `BELLEC Manon (21).jpg` et
    # `(TMCV1).jpg`, et les deux Manon s'en réclamaient — chacune comptée
    # « avec photo », sur la même image. C'est précisément ce que la
    # parenthèse existe pour éviter ; on rend donc le fichier au doute.
    disputes = {f for f, n in revendications.items() if n > 1}
    pris = {f for f in revendications if f not in disputes}

    # Seconde passe : ce qui reste, et les pistes encore libres.
    for p, classe, trouve in retenus:
        inventaire.nb_eleves += 1
        if trouve and trouve.casefold() not in disputes:
            inventaire.nb_avec += 1
            par_classe[classe]["avec"] += 1
            continue

        candidats = _candidats(racine, p)
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
