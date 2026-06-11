"""Comparaison de deux snapshots d'années scolaires.

Détermine pour chaque élève :
- **Entrant** : présent en année N mais pas en N-1 → nouveau compte à créer
- **Restant** : présent dans les deux → mise à jour (changement de classe / régime / etc.)
- **Sortant** : présent en N-1 mais pas en N → compte à supprimer

Clé de matching : `num_badge`. Charlemagne attribue un badge stable par élève
sur toute sa scolarité dans l'ensemble. C'est le seul identifiant fiable pour
ce matching (un nom peut changer, une classe varie chaque année).

Edge case : si un élève n'a pas de badge (cas rare), on tombe en fallback sur
(nom normalisé + prénom normalisé) pour ne pas le perdre.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Iterable

from sqlalchemy.orm import Session
from unidecode import unidecode

from backend.models import AnneeScolaire, EleveSnapshot, Etablissement


@dataclass
class Changement:
    """Décrit une variation d'un champ entre N-1 et N."""

    champ: str
    ancien: str | None
    nouveau: str | None


@dataclass
class EleveResume:
    """Vue plate d'un EleveSnapshot pour l'API JSON."""

    id: int
    annee_id: int
    num_badge: int | None
    nom: str
    prenom: str
    etablissement_code: str
    etablissement_nom: str
    code_classe: str | None
    code_niveau: str | None
    code_regime: str | None
    est_nouveau_charlemagne: bool

    @classmethod
    def from_eleve(cls, e: EleveSnapshot, etab: Etablissement) -> "EleveResume":
        return cls(
            id=e.id,
            annee_id=e.annee_scolaire_id,
            num_badge=e.num_badge,
            nom=e.nom,
            prenom=e.prenom,
            etablissement_code=etab.code_court,
            etablissement_nom=etab.nom_long,
            code_classe=e.code_classe,
            code_niveau=e.code_niveau,
            code_regime=e.code_regime,
            est_nouveau_charlemagne=e.est_nouveau_charlemagne,
        )


@dataclass
class Restant:
    """Élève présent dans les deux années, avec ses changements détectés."""

    eleve_n: EleveResume
    changements: list[Changement] = field(default_factory=list)


@dataclass
class ResultatComparaison:
    annee_n_libelle: str
    annee_n_minus_1_libelle: str
    entrants: list[EleveResume]
    restants: list[Restant]
    sortants: list[EleveResume]


def _cle_matching(eleve: EleveSnapshot) -> tuple[str, str | int]:
    """Renvoie une clé permettant d'identifier un élève entre snapshots.

    Préfère num_badge (stable). Fallback sur (nom_norm, prenom_norm) si pas
    de badge — préfixe différent pour ne pas confondre les deux espaces de
    clés.
    """
    if eleve.num_badge is not None:
        return ("badge", eleve.num_badge)
    nom_n = unidecode(eleve.nom or "").upper().strip()
    prenom_n = unidecode(eleve.prenom or "").upper().strip()
    return ("nomprenom", f"{nom_n}|{prenom_n}")


def _detecter_changements(
    n_minus_1: EleveSnapshot,
    n: EleveSnapshot,
    etab_n_minus_1: Etablissement,
    etab_n: Etablissement,
) -> list[Changement]:
    """Détecte les variations entre deux versions d'un élève."""
    changements: list[Changement] = []
    paires = [
        ("classe", n_minus_1.code_classe, n.code_classe),
        ("niveau", n_minus_1.code_niveau, n.code_niveau),
        ("regime", n_minus_1.code_regime, n.code_regime),
        ("etablissement", etab_n_minus_1.code_court, etab_n.code_court),
        ("nom", n_minus_1.nom, n.nom),
        ("prenom", n_minus_1.prenom, n.prenom),
    ]
    for champ, ancien, nouveau in paires:
        a = (ancien or "").strip()
        b = (nouveau or "").strip()
        if a != b:
            changements.append(Changement(champ=champ, ancien=a or None, nouveau=b or None))
    return changements


def comparer_annees(
    session: Session,
    libelle_n: str,
    libelle_n_minus_1: str,
) -> ResultatComparaison:
    """Compare deux snapshots et retourne entrants / restants / sortants."""
    annee_n = (
        session.query(AnneeScolaire).filter_by(libelle=libelle_n).one_or_none()
    )
    annee_n_1 = (
        session.query(AnneeScolaire)
        .filter_by(libelle=libelle_n_minus_1)
        .one_or_none()
    )
    if annee_n is None:
        raise ValueError(f"Snapshot N introuvable : {libelle_n}")
    if annee_n_1 is None:
        raise ValueError(f"Snapshot N-1 introuvable : {libelle_n_minus_1}")
    if annee_n.id == annee_n_1.id:
        raise ValueError("Année N et N-1 doivent être différentes")

    # Index des établissements (un seul fetch)
    etabs_par_id: dict[int, Etablissement] = {
        e.id: e for e in session.query(Etablissement).all()
    }

    eleves_n = session.query(EleveSnapshot).filter_by(annee_scolaire_id=annee_n.id).all()
    eleves_n_1 = (
        session.query(EleveSnapshot).filter_by(annee_scolaire_id=annee_n_1.id).all()
    )

    # Indexation par clé de matching
    par_cle_n: dict[tuple[str, str | int], EleveSnapshot] = {
        _cle_matching(e): e for e in eleves_n
    }
    par_cle_n_1: dict[tuple[str, str | int], EleveSnapshot] = {
        _cle_matching(e): e for e in eleves_n_1
    }

    cles_n = set(par_cle_n.keys())
    cles_n_1 = set(par_cle_n_1.keys())

    entrants: list[EleveResume] = []
    restants: list[Restant] = []
    sortants: list[EleveResume] = []

    # Entrants : dans N mais pas N-1
    for cle in cles_n - cles_n_1:
        e = par_cle_n[cle]
        entrants.append(EleveResume.from_eleve(e, etabs_par_id[e.etablissement_id]))

    # Sortants : dans N-1 mais pas N
    for cle in cles_n_1 - cles_n:
        e = par_cle_n_1[cle]
        sortants.append(EleveResume.from_eleve(e, etabs_par_id[e.etablissement_id]))

    # Restants : dans les deux, avec détection des changements
    for cle in cles_n & cles_n_1:
        e_n = par_cle_n[cle]
        e_n_1 = par_cle_n_1[cle]
        etab_n = etabs_par_id[e_n.etablissement_id]
        etab_n_1 = etabs_par_id[e_n_1.etablissement_id]
        changements = _detecter_changements(e_n_1, e_n, etab_n_1, etab_n)
        restants.append(
            Restant(
                eleve_n=EleveResume.from_eleve(e_n, etab_n),
                changements=changements,
            )
        )

    # Tris cohérents pour l'affichage
    _trier_eleves(entrants)
    _trier_eleves(sortants)
    restants.sort(key=lambda r: (r.eleve_n.etablissement_code, r.eleve_n.nom, r.eleve_n.prenom))

    return ResultatComparaison(
        annee_n_libelle=annee_n.libelle,
        annee_n_minus_1_libelle=annee_n_1.libelle,
        entrants=entrants,
        restants=restants,
        sortants=sortants,
    )


def _trier_eleves(liste: list[EleveResume]) -> None:
    liste.sort(key=lambda e: (e.etablissement_code, e.nom, e.prenom))
