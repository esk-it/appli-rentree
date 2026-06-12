"""Accès aux paramètres de configuration (lecture / écriture).

Les paramètres sont stockés dans la table `parametre` (clé / JSON value).
On expose un catalogue de paramètres connus avec leurs valeurs par défaut
pour qu'on puisse lister les options disponibles dans l'UI.
"""
from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any

from sqlalchemy.orm import Session

from backend.models import Parametre


@dataclass
class DefinitionParametre:
    cle: str
    libelle: str
    description: str
    type: str  # "str" | "int" | "bool" | "str_list"
    defaut: Any
    categorie: str


CATALOGUE: list[DefinitionParametre] = [
    DefinitionParametre(
        cle="email.domaine",
        libelle="Domaine email",
        description=(
            "Domaine utilisé pour construire les adresses email "
            "(<prenom.nom>@<domaine>)."
        ),
        type="str",
        defaut="lekreisker.fr",
        categorie="Email",
    ),
    DefinitionParametre(
        cle="google.ou_template",
        libelle="Template Org Unit Google",
        description=(
            "Pattern de l'Org Unit Path. Variables disponibles : "
            "{site}, {annee_compact}, {classe}."
        ),
        type="str",
        defaut="/{site}/{site}{annee_compact}/{classe}",
        categorie="Google Workspace",
    ),
    DefinitionParametre(
        cle="koxo.login_longueur_max",
        libelle="Longueur max du login KoXo",
        description=(
            "Tronque le login à cette longueur après concaténation "
            "première lettre prénom + nom."
        ),
        type="int",
        defaut=10,
        categorie="KoXo",
    ),
    DefinitionParametre(
        cle="mdp.longueur_lettres",
        libelle="Nombre de lettres dans le mot de passe",
        description="Nombre de lettres alternées (consonne/voyelle) dans le MDP généré.",
        type="int",
        defaut=6,
        categorie="Mots de passe",
    ),
    DefinitionParametre(
        cle="mdp.nb_chiffres",
        libelle="Nombre de chiffres dans le mot de passe",
        description="Nombre de chiffres à la fin du MDP généré.",
        type="int",
        defaut=2,
        categorie="Mots de passe",
    ),
]

# Index par clé pour lookup rapide
CATALOGUE_PAR_CLE: dict[str, DefinitionParametre] = {p.cle: p for p in CATALOGUE}


def get_param(session: Session, cle: str, defaut: Any = None) -> Any:
    """Lit un paramètre. Si absent, renvoie le défaut du catalogue ou `defaut`."""
    p = session.query(Parametre).filter_by(cle=cle).one_or_none()
    if p is None:
        if cle in CATALOGUE_PAR_CLE:
            return CATALOGUE_PAR_CLE[cle].defaut
        return defaut
    try:
        return json.loads(p.valeur_json)
    except json.JSONDecodeError:
        return defaut


def set_param(session: Session, cle: str, valeur: Any) -> None:
    """Écrit / met à jour un paramètre. Commit appelé par le routeur."""
    p = session.query(Parametre).filter_by(cle=cle).one_or_none()
    contenu = json.dumps(valeur, ensure_ascii=False)
    if p is None:
        p = Parametre(cle=cle, valeur_json=contenu)
        session.add(p)
    else:
        p.valeur_json = contenu


def get_tous_parametres(session: Session) -> dict[str, Any]:
    """Renvoie un dict {cle: valeur} pour tous les paramètres du catalogue
    (valeur de la DB si présente, sinon défaut)."""
    en_base = {p.cle: p for p in session.query(Parametre).all()}
    resultat: dict[str, Any] = {}
    for definition in CATALOGUE:
        if definition.cle in en_base:
            try:
                resultat[definition.cle] = json.loads(
                    en_base[definition.cle].valeur_json
                )
            except json.JSONDecodeError:
                resultat[definition.cle] = definition.defaut
        else:
            resultat[definition.cle] = definition.defaut
    return resultat
