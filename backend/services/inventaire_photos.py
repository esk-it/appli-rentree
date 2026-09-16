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


@dataclass
class InventairePhotos:
    dossier: str = ""
    nb_eleves: int = 0
    nb_avec: int = 0
    manquantes: list[EleveSansPhoto] = field(default_factory=list)
    par_classe: dict[str, dict[str, int]] = field(default_factory=dict)
    """`{classe: {"avec": n, "sans": n}}` — la maille à laquelle on relance."""

    @property
    def nb_sans(self) -> int:
        return len(self.manquantes)

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


def dossier_photos(session: Session) -> str | None:
    param = (
        session.query(Parametre).filter_by(cle="chemin_dossier_photos").one_or_none()
    )
    if param is None:
        return None
    try:
        return json.loads(param.valeur_json) or None
    except (json.JSONDecodeError, TypeError):
        return None


def _candidats(racine: Path, personne: Personne) -> list[Path]:
    """Les noms sous lesquels la photo de cette personne peut exister.

    Charlemagne nomme d'après l'état civil, avec des variations selon
    l'export. On essaie les formes rencontrées plutôt que d'en imposer une :
    déclarer manquante une photo qui est là ferait relancer une famille
    pour rien.
    """
    nom = (personne.nom or "").strip()
    prenom = (personne.prenom or "").strip()
    bases = [f"{nom} {prenom}", f"{nom}_{prenom}", f"{prenom} {nom}"]
    if personne.badge:
        bases.append(str(personne.badge))
    return [racine / f"{b}{ext}" for b in bases for ext in EXTENSIONS]


def relever(session: Session, *, annee_id: int) -> InventairePhotos:
    """Qui a sa photo sur le partage, et qui ne l'a pas.

    Raises:
        InventaireImpossible: dossier non réglé, ou inaccessible — les deux
            se disent différemment, parce qu'ils se corrigent différemment.
    """
    dossier = dossier_photos(session)
    if not dossier:
        raise InventaireImpossible(
            "Le dossier des photos n'est pas réglé. Il se déclare dans les "
            "Paramètres — c'est le partage où Charlemagne les dépose."
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
    inventaire = InventairePhotos(dossier=dossier)
    par_classe: dict[str, dict[str, int]] = defaultdict(lambda: {"avec": 0, "sans": 0})

    for p in session.query(Personne).filter(Personne.type == "eleve").all():
        sn = derniers.get(p.id)
        classe = (sn.classe or "").strip() if sn else ""
        if not classe:
            continue
        inventaire.nb_eleves += 1

        candidats = _candidats(racine, p)
        trouve = any(c.name.casefold() in presents for c in candidats)
        if trouve:
            inventaire.nb_avec += 1
            par_classe[classe]["avec"] += 1
        else:
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
