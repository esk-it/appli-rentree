"""La répétition : tout le programme sur une copie de la base, Google en lecture seule.

## Ce que Johann a demandé (15 octobre 2026)

« Actuellement je ne sais pas ce qui va réellement fonctionner ou non, et
attendre le 01/07/2027 pour pouvoir essayer c'est chaud. » La visite montre
le chemin ; elle ne fait rien. La répétition fait tout — ingérer un export,
tourner la table, valider des étapes, verser au coffre — sur une copie.

## Ce qui est copié, ce qui est gardé

- **La base** : une copie, prise au moment où l'on commence, dans
  `repetition/` à côté de la vraie. Le programme entier bascule dessus —
  pas seulement la rentrée : un écran qui lirait la vraie base pendant
  qu'un autre écrit dans la copie montrerait des choses fausses.
- **Google** : lu pour de vrai — les comptes, les unités, les groupes —,
  jamais écrit. Toute requête qui n'est pas une lecture est refusée avant
  de partir, et l'erreur le dit.
- **Le reste du monde** — KoXo, Charlemagne, CardStudio, la centrale —, le
  programme n'y écrit pas : c'est la personne qui le fait. L'assistant le
  lui rappelle sur chaque geste qui modifierait l'un d'eux.

## Ce qui ramène à la vraie base

Quitter la répétition, ou relancer le programme : il démarre toujours sur
la vraie base. La copie reste, pour reprendre plus tard ; on la jette
quand on veut.
"""
from __future__ import annotations

import json
import shutil
import sqlite3
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker


class EcritureGoogleEnRepetition(RuntimeError):
    """Une écriture vers Google, refusée parce qu'une répétition est en cours."""


@dataclass
class EtatRepetition:
    active: bool
    copie_existe: bool
    copiee_le: str | None
    """Quand la copie a été prise (ISO) : ce qu'elle sait de la vraie base."""


_active = False
_reel: tuple | None = None
"""`(_engine, _SessionLocal)` de la vraie base, le temps de la répétition."""


def _dossier() -> Path:
    from backend import config

    return config.RACINE_DONNEES / "repetition"


def _copie() -> Path:
    return _dossier() / "appli_rentree.db"


def _fiche() -> Path:
    return _dossier() / "repetition.json"


def est_active() -> bool:
    return _active


def etat() -> EtatRepetition:
    copiee_le = None
    if _fiche().exists():
        try:
            copiee_le = json.loads(_fiche().read_text(encoding="utf-8")).get("copiee_le")
        except (OSError, ValueError):
            copiee_le = None
    return EtatRepetition(active=_active, copie_existe=_copie().exists(), copiee_le=copiee_le)


def _oublier_les_caches() -> None:
    """Ce qu'un service garde en mémoire d'une base ne vaut pas pour l'autre.

    Les identifiants de la copie et de la vraie base divergent dès qu'on
    crée quelque chose d'un côté : une attribution de photos gardée pour
    l'année 12 de la copie ne doit pas servir à l'année 12 de la vraie.
    """
    from backend.services import inventaire_photos

    with inventaire_photos._verrou_attributions:
        inventaire_photos._attributions.clear()


def _copier_la_base() -> None:
    """Une photo cohérente de la vraie base, même ouverte : l'API de sauvegarde de SQLite."""
    from backend import config

    _dossier().mkdir(parents=True, exist_ok=True)
    if _copie().exists():
        _copie().unlink()
    source = sqlite3.connect(f"file:{config.CHEMIN_DB}?mode=ro", uri=True)
    cible = sqlite3.connect(str(_copie()))
    try:
        source.backup(cible)
    finally:
        cible.close()
        source.close()
    _fiche().write_text(
        json.dumps({"copiee_le": datetime.now().isoformat(timespec="minutes")}),
        encoding="utf-8",
    )


def commencer(*, neuve: bool = False) -> EtatRepetition:
    """Bascule le programme sur la copie — neuve, ou celle d'une répétition précédente."""
    global _active, _reel
    from backend import database

    if _active:
        if not neuve:
            return etat()
        quitter()
    if neuve or not _copie().exists():
        _copier_la_base()

    _reel = (database._engine, database._SessionLocal)
    moteur = create_engine(
        f"sqlite:///{_copie()}", echo=False, future=True,
        connect_args={"check_same_thread": False},
    )
    database._engine = moteur
    database._SessionLocal = sessionmaker(
        bind=moteur, autocommit=False, autoflush=False, future=True
    )
    _active = True
    _oublier_les_caches()
    # Une copie reprise après une mise à jour du programme : même
    # migration que la vraie base au démarrage.
    database.init_db()
    return etat()


def quitter() -> EtatRepetition:
    """Revient à la vraie base. La copie reste, pour reprendre plus tard."""
    global _active, _reel
    from backend import database

    if _active and _reel is not None:
        moteur = database._engine
        database._engine, database._SessionLocal = _reel
        moteur.dispose()
        _oublier_les_caches()
    _active = False
    _reel = None
    return etat()


def jeter() -> EtatRepetition:
    """Quitte la répétition et efface sa copie."""
    quitter()
    shutil.rmtree(_dossier(), ignore_errors=True)
    return etat()


# ---------------------------------------------------------------------------
# Google en lecture seule
# ---------------------------------------------------------------------------


def _installer_la_garde() -> None:
    """Refuse, en répétition, toute requête Google qui n'est pas une lecture.

    Un seul point de passage : toutes les requêtes de `googleapiclient`
    passent par `HttpRequest.execute`. Garder chaque méthode d'écriture une
    à une en oublierait une ; garder la méthode HTTP n'en oublie aucune.
    """
    try:
        from googleapiclient import http as gh
    except ImportError:  # pragma: no cover — la bibliothèque est une dépendance
        return
    if getattr(gh.HttpRequest.execute, "_garde_repetition", False):
        return
    reel = gh.HttpRequest.execute

    def execute(self, *args, **kwargs):
        if _active and (self.method or "GET").upper() != "GET":
            raise EcritureGoogleEnRepetition(
                "Répétition : rien n'est envoyé à Google — Google n'y est que lu. "
                "Hors répétition, ce geste partirait pour de vrai."
            )
        return reel(self, *args, **kwargs)

    execute._garde_repetition = True
    gh.HttpRequest.execute = execute


_installer_la_garde()
