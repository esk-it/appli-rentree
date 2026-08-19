"""Génération des exports CSV pour JPM/SmartAir (contrôle d'accès badges).

Format différentiel — colonne `Op` valant :
- `a` : ajout (nouveau badge)
- `b` : suppression (badge à révoquer)
- `m` : modification (changement de groupe / classe)

Colonnes principales : `Op, Id, Name, CardId, Group, ActivationDate, ExpirationDate`
+ ~20 colonnes techniques constantes ou vides.

## Différentiel

Contrairement à KoXo/Google (qui produisent un état complet), JPM attend
uniquement les changements. On compare annee_source vs annee_cible :

- **Nouveau** (dans cible, absent source) → ligne `Op=a`
- **Modifié** (classe différente) → ligne `Op=m`
- **Sortant** (dans source, absent cible) → ligne `Op=b`
- Identiques → ignorés

## CardId

Le `CardId` (identifiant matériel hexadécimal du badge physique) est
inconnu à notre programme — il est fourni par SmartAir au premier
enregistrement du badge. Pour les nouveaux, on laisse vide ; SmartAir
créera. Pour les modifications, on utilise `Id` (num_badge) comme clé.
"""
from __future__ import annotations

import csv
import io
from dataclasses import dataclass, field
from typing import Literal

from sqlalchemy.orm import Session
from backend.services.rattachement import ids_personnes_du_site

from backend.models import Personne, Site, Snapshot

# Ordre officiel des colonnes JPM/SmartAir (28 au total, extrait du XLSX historique)
COLONNES_JPM = [
    "Op", "Id", "Name", "CardId", "Group",
    "Technology", "ActivationDate", "ActivationTime", "ExpirationDate", "ExpirationTime",
    "Grants", "PIN", "OverB", "ADA", "OpeningsReg", "OpeningsOverflow",
    "ModifiesLockingPlan", "Updateable", "UpdateInterval", "Level",
    "Track1", "Track2", "Reles", "Data1", "Data2", "Data3", "Data4", "MSISD",
]

# Valeurs techniques constantes (héritées de l'export historique du prédécesseur)
DEFAUTS_JPM = {
    "Technology": "P",
    "Grants": "FFFFFF",
}


@dataclass
class RapportExportJpm:
    site_nom: str
    nb_ajouts: int = 0
    nb_suppressions: int = 0
    nb_modifications: int = 0
    nom_fichier_suggere: str = ""

    @property
    def nb_total(self) -> int:
        return self.nb_ajouts + self.nb_suppressions + self.nb_modifications


def generer_csv_jpm(
    session: Session,
    *,
    site_id: int,
    annee_cible_id: int,
    annee_source_id: int,
) -> tuple[bytes, RapportExportJpm]:
    """Génère le CSV différentiel JPM/SmartAir pour un site."""
    site = session.query(Site).filter_by(id=site_id).one_or_none()
    if site is None:
        raise ValueError(f"Site introuvable : {site_id}")

    # JPM = uniquement les élèves (les adultes n'ont pas de badge d'accès dans ce contexte)
    src = _snapshots_par_personne(session, annee_source_id, site, "eleve")
    tgt = _snapshots_par_personne(session, annee_cible_id, site, "eleve")

    ids_src = set(src)
    ids_tgt = set(tgt)
    personnes = {p.id: p for p in session.query(Personne).filter(
        Personne.id.in_(ids_src | ids_tgt)
    ).all()}

    lignes: list[dict] = []
    rapport = RapportExportJpm(site_nom=site.nom)

    # Ajouts (dans cible, absent source)
    for pid in ids_tgt - ids_src:
        lignes.append(_ligne("a", personnes[pid], tgt[pid]))
        rapport.nb_ajouts += 1

    # Suppressions (dans source, absent cible)
    for pid in ids_src - ids_tgt:
        lignes.append(_ligne("b", personnes[pid], src[pid]))
        rapport.nb_suppressions += 1

    # Modifications : classe différente entre source et cible
    for pid in ids_src & ids_tgt:
        if (src[pid].classe or "") != (tgt[pid].classe or ""):
            lignes.append(_ligne("m", personnes[pid], tgt[pid]))
            rapport.nb_modifications += 1

    contenu = _encoder_csv(lignes)
    rapport.nom_fichier_suggere = f"JPM_{site.nom}_differentiel.csv"
    return contenu, rapport


def _snapshots_par_personne(session, annee_id, site, type_personne):
    q = (
        session.query(Snapshot)
        .join(Personne, Snapshot.personne_id == Personne.id)
        .filter(
            Snapshot.annee_scolaire_id == annee_id,
            Personne.id.in_(
                ids_personnes_du_site(
                    session, site_id=site.id,
                    annee_id=annee_id, type_personne=type_personne,
                )
            ),
            Personne.type == type_personne,
        )
        .order_by(Snapshot.personne_id, Snapshot.date_ingestion.desc())
    )
    derniers = {}
    for s in q.all():
        if s.personne_id not in derniers:
            derniers[s.personne_id] = s
    return derniers


def _ligne(op: str, personne: Personne, snapshot: Snapshot) -> dict:
    """Construit une ligne JPM avec les valeurs par défaut techniques."""
    ligne = {col: "" for col in COLONNES_JPM}
    ligne.update(DEFAUTS_JPM)
    ligne["Op"] = op
    ligne["Id"] = str(personne.badge) if personne.badge else ""
    ligne["Name"] = f"{personne.nom} {personne.prenom}".strip()
    # CardId : vide pour a (SmartAir génère), vide pour b/m (SmartAir retrouve par Id)
    ligne["CardId"] = ""
    ligne["Group"] = snapshot.classe or ""
    return ligne


def _encoder_csv(lignes: list[dict]) -> bytes:
    buf = io.StringIO(newline="")
    writer = csv.DictWriter(buf, fieldnames=COLONNES_JPM, quoting=csv.QUOTE_MINIMAL)
    writer.writeheader()
    for l in lignes:
        writer.writerow(l)
    return buf.getvalue().encode("utf-8", errors="replace")
