"""Génération des exports d'appartenance aux groupes Google.

Format officiel du bulk-import « Membres de groupes » de Google Admin,
4 colonnes :

    Group Email [Required] | Member Email | Member Type | Member Role

Exemple :

    3eme-fuschia@ndecleder.fr | nathan.abiven@ndecleder.fr | USER | MEMBER
    profs-2nde-gatl@lekreisker.fr | john.bars@lekreisker.fr | USER | MEMBER

## Deux familles de groupes

La `TableCorrespondance` porte les deux adresses par classe :

| Colonne | Contenu | Membres |
|---|---|---|
| `groupe_google` | mailing list de la classe | les **élèves** de cette classe |
| `groupe_profs_google` | groupe des enseignants | les **adultes** intervenant dans cette classe |

## Comment on sait qu'un prof intervient dans une classe

Via le champ `classes_prof_principal` du snapshot adulte — issu de la
colonne Charlemagne « Liste des classes (prof principal) », valeurs
séparées par `;`. C'est la seule source disponible côté export
Charlemagne ; un enseignant qui intervient dans une classe sans en être
professeur principal n'y figure pas.

**Conséquence assumée** : les groupes profs sont incomplets par rapport à
la réalité pédagogique. Le rapport signale le nombre de classes sans
aucun prof rattaché pour rendre ce manque visible plutôt que silencieux.
"""
from __future__ import annotations

import csv
import io
from dataclasses import dataclass, field

from sqlalchemy.orm import Session

from backend.models import Personne, Site, Snapshot, TableCorrespondance

COLONNES_GROUPES = [
    "Group Email [Required]",
    "Member Email",
    "Member Type",
    "Member Role",
]

# UTF-8 BOM — même exigence que le bulk-import utilisateurs
BOM_UTF8 = b"\xef\xbb\xbf"


@dataclass
class RapportExportGroupes:
    site_nom: str
    annee_libelle: str

    nb_lignes: int = 0
    nb_lignes_eleves: int = 0
    nb_lignes_profs: int = 0

    nb_groupes_classes: int = 0
    nb_groupes_profs: int = 0

    classes_sans_groupe: list[str] = field(default_factory=list)
    """Classes présentes dans l'année mais sans adresse de groupe configurée
    dans la Table de correspondance."""

    groupes_profs_vides: list[str] = field(default_factory=list)
    """Groupes profs configurés mais sans aucun enseignant rattaché — le
    champ `classes_prof_principal` ne couvre pas toute la réalité."""

    nb_membres_sans_email: int = 0
    """Personnes ignorées faute d'email calculable (site ou login manquant)."""

    nom_fichier_suggere: str = ""


def generer_csv_groupes_google(
    session: Session,
    *,
    site_id: int,
    annee_id: int,
    inclure_eleves: bool = True,
    inclure_profs: bool = True,
) -> tuple[bytes, RapportExportGroupes]:
    """Génère le CSV d'appartenance aux groupes Google pour un site et une année.

    Args:
        inclure_eleves: alimente les mailing lists de classe.
        inclure_profs: alimente les groupes d'enseignants par classe.
    """
    from backend.models import AnneeScolaire

    site = session.query(Site).filter_by(id=site_id).one_or_none()
    if site is None:
        raise ValueError(f"Site introuvable : {site_id}")

    annee = session.query(AnneeScolaire).filter_by(id=annee_id).one_or_none()
    if annee is None:
        raise ValueError(f"Année introuvable : {annee_id}")

    if not inclure_eleves and not inclure_profs:
        raise ValueError("Il faut inclure au moins les élèves ou les profs")

    rapport = RapportExportGroupes(site_nom=site.nom, annee_libelle=annee.libelle)

    # Mapping classe → (groupe élèves, groupe profs)
    groupes_par_classe: dict[str, tuple[str | None, str | None]] = {}
    for tc in session.query(TableCorrespondance).filter_by(site_id=site.id).all():
        groupes_par_classe[tc.classe_code_court] = (
            tc.groupe_google,
            tc.groupe_profs_google,
        )

    lignes: list[dict] = []

    if inclure_eleves:
        lignes += _lignes_eleves(session, site, annee_id, groupes_par_classe, rapport)
    if inclure_profs:
        lignes += _lignes_profs(session, site, annee_id, groupes_par_classe, rapport)

    rapport.nb_lignes = len(lignes)
    rapport.nom_fichier_suggere = f"GroupesGoogle_{site.nom}_{annee.libelle}.csv"
    return _encoder_csv(lignes), rapport


# ---------------------------------------------------------------------------
# Élèves → mailing list de leur classe
# ---------------------------------------------------------------------------


def _lignes_eleves(
    session: Session,
    site: Site,
    annee_id: int,
    groupes_par_classe: dict[str, tuple[str | None, str | None]],
    rapport: RapportExportGroupes,
) -> list[dict]:
    derniers = _derniers_snapshots(session, site, annee_id, "eleve")
    personnes = _charger_personnes(session, set(derniers))

    lignes: list[dict] = []
    classes_sans_groupe: set[str] = set()
    groupes_touches: set[str] = set()

    for pid, snap in derniers.items():
        personne = personnes.get(pid)
        if personne is None:
            continue
        classe = snap.classe or ""
        if not classe:
            continue

        groupe = groupes_par_classe.get(classe, (None, None))[0]
        if not groupe:
            classes_sans_groupe.add(classe)
            continue

        email = personne.email
        if not email:
            rapport.nb_membres_sans_email += 1
            continue

        groupes_touches.add(groupe)
        lignes.append(_ligne(groupe, email))

    rapport.classes_sans_groupe = sorted(classes_sans_groupe)
    rapport.nb_groupes_classes = len(groupes_touches)
    rapport.nb_lignes_eleves = len(lignes)
    return lignes


# ---------------------------------------------------------------------------
# Adultes → groupe profs des classes où ils interviennent
# ---------------------------------------------------------------------------


def _lignes_profs(
    session: Session,
    site: Site,
    annee_id: int,
    groupes_par_classe: dict[str, tuple[str | None, str | None]],
    rapport: RapportExportGroupes,
) -> list[dict]:
    derniers = _derniers_snapshots(session, site, annee_id, "adulte")
    personnes = _charger_personnes(session, set(derniers))

    lignes: list[dict] = []
    vues: set[tuple[str, str]] = set()  # (groupe, email) — évite les doublons
    groupes_touches: set[str] = set()

    for pid, snap in derniers.items():
        personne = personnes.get(pid)
        if personne is None:
            continue

        classes = _decouper_classes(snap.classes_prof_principal)
        if not classes:
            continue

        email = personne.email
        if not email:
            rapport.nb_membres_sans_email += 1
            continue

        for classe in classes:
            groupe = groupes_par_classe.get(classe, (None, None))[1]
            if not groupe:
                continue
            cle = (groupe, email)
            if cle in vues:
                continue
            vues.add(cle)
            groupes_touches.add(groupe)
            lignes.append(_ligne(groupe, email))

    # Groupes profs configurés mais restés vides — le champ Charlemagne ne
    # couvre que les professeurs principaux, pas tous les intervenants.
    tous_groupes_profs = {
        g for _, g in groupes_par_classe.values() if g
    }
    rapport.groupes_profs_vides = sorted(tous_groupes_profs - groupes_touches)
    rapport.nb_groupes_profs = len(groupes_touches)
    rapport.nb_lignes_profs = len(lignes)
    return lignes


def _decouper_classes(valeur: str | None) -> list[str]:
    """`3A;4B; 5C ` → `["3A", "4B", "5C"]`."""
    if not valeur:
        return []
    return [c.strip() for c in str(valeur).split(";") if c.strip()]


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _derniers_snapshots(
    session: Session, site: Site, annee_id: int, type_personne: str
) -> dict[int, Snapshot]:
    q = (
        session.query(Snapshot)
        .join(Personne, Snapshot.personne_id == Personne.id)
        .filter(
            Snapshot.annee_scolaire_id == annee_id,
            Personne.site_id == site.id,
            Personne.type == type_personne,
        )
        .order_by(Snapshot.personne_id, Snapshot.date_ingestion.desc())
    )
    derniers: dict[int, Snapshot] = {}
    for s in q.all():
        if s.personne_id not in derniers:
            derniers[s.personne_id] = s
    return derniers


def _charger_personnes(session: Session, ids: set[int]) -> dict[int, Personne]:
    if not ids:
        return {}
    return {p.id: p for p in session.query(Personne).filter(Personne.id.in_(ids)).all()}


def _ligne(groupe: str, email: str) -> dict:
    return {
        "Group Email [Required]": groupe,
        "Member Email": email,
        "Member Type": "USER",
        "Member Role": "MEMBER",
    }


def _encoder_csv(lignes: list[dict]) -> bytes:
    buf = io.StringIO(newline="")
    writer = csv.DictWriter(buf, fieldnames=COLONNES_GROUPES, quoting=csv.QUOTE_MINIMAL)
    writer.writeheader()
    for l in lignes:
        writer.writerow(l)
    return BOM_UTF8 + buf.getvalue().encode("utf-8", errors="replace")
