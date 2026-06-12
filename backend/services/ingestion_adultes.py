"""Ingestion d'un export Charlemagne des adultes/personnel.

Le format de l'export adultes Charlemagne n'est pas identique à celui des
élèves. On essaie de détecter les colonnes par leurs libellés normalisés,
avec un mapping flexible. Si une colonne attendue est absente, on s'en
passe (champ optionnel).

Colonnes attendues (alias possibles) :
- num_personnel : "num personnel", "n° personnel", "id" → INTEGER
- civilite : "civilite", "civilité", "titre" → STR
- nom : "nom" → STR (obligatoire)
- prenom : "prenom", "prénom" → STR (obligatoire)
- date_naissance : "date de naissance", "ddn", "datnais" → DATE
- fonction : "fonction", "categorie", "catégorie" → STR
- matieres : "matiere", "matière", "matieres", "matières", "discipline(s)" → STR
- email : "email", "mail", "courriel" → STR
- telephone : "telephone", "téléphone", "tel" → STR
- code_etablissement : "code etablissement", "etab", "etablissement" → STR
"""
from __future__ import annotations

from pathlib import Path

import pandas as pd
from sqlalchemy.orm import Session
from unidecode import unidecode

from backend.models import AdulteSnapshot, AnneeScolaire, Etablissement
from backend.services.etablissement_seed import ETABLISSEMENTS_CONNUS
from backend.services.parser_charlemagne import lire_htm, lire_xlsx

# Map nom normalisé → champ Python
COLONNES_ADULTES = {
    "num personnel": "num_personnel",
    "n personnel": "num_personnel",
    "id": "num_personnel",
    "identifiant": "num_personnel",
    "civilite": "civilite",
    "titre": "civilite",
    "nom": "nom",
    "prenom": "prenom",
    "date de naissance": "date_naissance",
    "ddn": "date_naissance",
    "datnais": "date_naissance",
    "fonction": "fonction",
    "categorie": "fonction",
    "matiere": "matieres",
    "matieres": "matieres",
    "discipline": "matieres",
    "disciplines": "matieres",
    "email": "email_personnel",
    "mail": "email_personnel",
    "courriel": "email_personnel",
    "telephone": "telephone",
    "tel": "telephone",
    "code etablissement": "code_etablissement",
    "code etab": "code_etablissement",
    "etab": "code_etablissement",
    "etablissement": "code_etablissement",
    "nouvel adulte": "nouvel_adulte",
    "nouveau": "nouvel_adulte",
}


def _normaliser_libelle(libelle: str) -> str:
    return unidecode(str(libelle)).strip().lower().replace("°", "").replace(".", "")


def _detecter_si_export_adultes(df: pd.DataFrame) -> bool:
    """Heuristique : présence d'un libellé de colonne typique des adultes."""
    indices_adultes = {
        "fonction",
        "civilite",
        "matiere",
        "matieres",
        "discipline",
        "categorie",
    }
    cols_norm = {_normaliser_libelle(c) for c in df.columns}
    return bool(cols_norm & indices_adultes)


def _normaliser_colonnes_adultes(df: pd.DataFrame) -> pd.DataFrame:
    """Renomme les colonnes selon COLONNES_ADULTES (best effort)."""
    renames: dict[str, str] = {}
    for col in df.columns:
        cle = _normaliser_libelle(col)
        if cle in COLONNES_ADULTES:
            renames[col] = COLONNES_ADULTES[cle]
    return df.rename(columns=renames)


def _str_ou_none(valeur) -> str | None:
    if pd.isna(valeur) or valeur is None:
        return None
    s = str(valeur).strip()
    return s if s else None


def ingerer_export_adultes(
    session: Session,
    chemin_fichier: Path,
    libelle_annee: str,
    remplacer_si_existe: bool = False,
) -> dict:
    """Ingère un export Charlemagne adultes comme snapshot.

    Returns:
        dict avec annee_scolaire_id, nb_adultes_inseres, fonctions_detectees
    """
    suffix = chemin_fichier.suffix.lower()
    if suffix in (".htm", ".html"):
        df = lire_htm(chemin_fichier)
    elif suffix in (".xlsx", ".xls"):
        df = lire_xlsx(chemin_fichier)
    else:
        raise ValueError(f"Format non supporté : {suffix}")

    if not _detecter_si_export_adultes(df):
        raise ValueError(
            "Ce fichier ne ressemble pas à un export Charlemagne d'adultes "
            "(aucune colonne fonction/civilité/discipline détectée). "
            "Si c'est un export élèves, utilise l'import élèves à la place."
        )

    df = _normaliser_colonnes_adultes(df)

    annee = (
        session.query(AnneeScolaire).filter_by(libelle=libelle_annee).one_or_none()
    )
    if annee is None:
        annee = AnneeScolaire(libelle=libelle_annee, est_active=True)
        session.add(annee)
        session.flush()
    elif remplacer_si_existe:
        session.query(AdulteSnapshot).filter_by(annee_scolaire_id=annee.id).delete()
        session.flush()

    cache_etabs: dict[str, Etablissement] = {
        e.code_charlemagne: e for e in session.query(Etablissement).all()
    }

    nb_adultes = 0
    fonctions: dict[str, int] = {}
    for _, row in df.iterrows():
        nom = _str_ou_none(row.get("nom"))
        prenom = _str_ou_none(row.get("prenom"))
        if not nom and not prenom:
            continue

        # Résolution établissement (optionnel pour adultes — certains profs
        # peuvent ne pas être rattachés à un établissement précis)
        code_etab = _str_ou_none(row.get("code_etablissement"))
        etablissement_id = None
        if code_etab:
            etab = cache_etabs.get(code_etab)
            if etab is None and code_etab in ETABLISSEMENTS_CONNUS:
                connu = ETABLISSEMENTS_CONNUS[code_etab]
                etab = Etablissement(
                    code_charlemagne=code_etab,
                    code_court=connu.get("code_court", code_etab),
                    nom_long=connu.get("nom_long", code_etab),
                    type=connu.get("type", "inconnu"),
                )
                session.add(etab)
                session.flush()
                cache_etabs[code_etab] = etab
            if etab:
                etablissement_id = etab.id

        # Champs structurés
        num_personnel = row.get("num_personnel")
        try:
            num_personnel = int(num_personnel) if pd.notna(num_personnel) else None
        except (TypeError, ValueError):
            num_personnel = None

        date_n = row.get("date_naissance")
        if pd.notna(date_n):
            if isinstance(date_n, str):
                try:
                    date_n = pd.to_datetime(date_n, dayfirst=True).date()
                except Exception:
                    date_n = None
            elif hasattr(date_n, "date"):
                date_n = date_n.date()
        else:
            date_n = None

        nouvel = row.get("nouvel_adulte")
        if pd.isna(nouvel):
            nouvel = False
        else:
            nouvel = str(nouvel).strip().upper() in {"O", "OUI", "TRUE", "1", "X"}

        fonction = _str_ou_none(row.get("fonction"))
        if fonction:
            fonctions[fonction] = fonctions.get(fonction, 0) + 1

        adulte = AdulteSnapshot(
            annee_scolaire_id=annee.id,
            etablissement_id=etablissement_id,
            num_personnel=num_personnel,
            civilite=_str_ou_none(row.get("civilite")),
            nom=nom or "",
            prenom=prenom or "",
            date_naissance=date_n,
            fonction=fonction,
            matieres=_str_ou_none(row.get("matieres")),
            email_personnel=_str_ou_none(row.get("email_personnel")),
            telephone=_str_ou_none(row.get("telephone")),
            est_nouveau_charlemagne=bool(nouvel),
        )
        session.add(adulte)
        nb_adultes += 1

    session.commit()
    return {
        "annee_scolaire_id": annee.id,
        "libelle": annee.libelle,
        "nb_adultes_inseres": nb_adultes,
        "fonctions_detectees": fonctions,
    }
