"""Ingestion d'un export Charlemagne dans la base SQLite.

Pipeline :
1. Parse le fichier (HTM ou XLSX) via parser_charlemagne
2. Crée (ou réutilise) un AnneeScolaire avec le libellé fourni
3. Pour chaque ligne :
   - Crée l'Etablissement s'il n'existe pas (basé sur le code Charlemagne)
   - Crée l'EleveSnapshot
4. Commit transactionnel : tout réussit ou rien n'est inséré
"""
from __future__ import annotations

from pathlib import Path

import pandas as pd
from sqlalchemy.orm import Session

from backend.models import AnneeScolaire, EleveSnapshot, Etablissement
from backend.services.etablissement_seed import ETABLISSEMENTS_CONNUS
from backend.services.parser_charlemagne import lire_htm, lire_xlsx


def _str_ou_none(valeur) -> str | None:
    if pd.isna(valeur) or valeur is None:
        return None
    s = str(valeur).strip()
    return s if s else None


def ingerer_export(
    session: Session,
    chemin_fichier: Path,
    libelle_annee: str,
    remplacer_si_existe: bool = False,
) -> dict:
    """Ingère un export Charlemagne comme snapshot d'année.

    Args:
        session: session SQLAlchemy ouverte
        chemin_fichier: chemin absolu du fichier .htm / .xlsx / .xls
        libelle_annee: "2025-2026", "2026-2027", etc.
        remplacer_si_existe: si True, vide d'abord les élèves de cette année
                             avant de réimporter. Utile pour corriger un
                             import partiel sans créer de doublons.

    Returns:
        dict avec annee_scolaire_id, libelle, nb_eleves_inseres,
        nb_etablissements_crees, par_etablissement
    """
    # 1. Parse le fichier
    suffix = chemin_fichier.suffix.lower()
    if suffix in (".htm", ".html"):
        df = lire_htm(chemin_fichier)
    elif suffix in (".xlsx", ".xls"):
        df = lire_xlsx(chemin_fichier)
    else:
        raise ValueError(f"Format non supporté : {suffix}")

    # 2. AnneeScolaire (crée ou récupère)
    annee = (
        session.query(AnneeScolaire).filter_by(libelle=libelle_annee).one_or_none()
    )
    if annee is None:
        annee = AnneeScolaire(libelle=libelle_annee, est_active=True)
        session.add(annee)
        session.flush()
    elif remplacer_si_existe:
        # Vide les EleveSnapshot existants pour repartir propre
        session.query(EleveSnapshot).filter_by(annee_scolaire_id=annee.id).delete()
        session.flush()

    # 3. Cache des établissements (code_charlemagne → Etablissement)
    cache_etabs: dict[str, Etablissement] = {
        e.code_charlemagne: e for e in session.query(Etablissement).all()
    }
    nb_etabs_crees = 0

    # 4. Boucle d'insertion
    nb_eleves = 0
    par_etab: dict[str, int] = {}

    for _, row in df.iterrows():
        code_etab = _str_ou_none(row.get("code_etablissement"))
        if not code_etab:
            continue  # ligne sans établissement = inexploitable

        # Récupère ou crée l'établissement
        etab = cache_etabs.get(code_etab)
        if etab is None:
            connu = ETABLISSEMENTS_CONNUS.get(code_etab, {})
            nom_long_charlemagne = _str_ou_none(row.get("nom_etablissement"))
            etab = Etablissement(
                code_charlemagne=code_etab,
                code_court=connu.get("code_court", code_etab),
                nom_long=connu.get("nom_long") or nom_long_charlemagne or code_etab,
                type=connu.get("type", "inconnu"),
            )
            session.add(etab)
            session.flush()
            cache_etabs[code_etab] = etab
            nb_etabs_crees += 1

        # Crée l'EleveSnapshot
        num_badge = row.get("num_badge")
        eleve = EleveSnapshot(
            annee_scolaire_id=annee.id,
            etablissement_id=etab.id,
            num_badge=int(num_badge) if pd.notna(num_badge) else None,
            code_classe=_str_ou_none(row.get("code_classe")),
            code_niveau=_str_ou_none(row.get("code_niveau")),
            code_regime=_str_ou_none(row.get("code_regime")),
            nom=_str_ou_none(row.get("nom")) or "??",
            prenom=_str_ou_none(row.get("prenom")) or "",
            date_entree=row["date_entree"].date()
            if "date_entree" in df.columns and pd.notna(row.get("date_entree"))
            else None,
            est_nouveau_charlemagne=bool(row.get("nouvel_eleve", False)),
            photo_chemin=_str_ou_none(row.get("photo_chemin")),
        )
        session.add(eleve)
        nb_eleves += 1
        par_etab[etab.code_court] = par_etab.get(etab.code_court, 0) + 1

    session.commit()
    return {
        "annee_scolaire_id": annee.id,
        "libelle": annee.libelle,
        "nb_eleves_inseres": nb_eleves,
        "nb_etablissements_crees": nb_etabs_crees,
        "par_etablissement": par_etab,
    }
