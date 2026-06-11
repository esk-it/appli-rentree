"""Règles métier de génération de comptes (login, email, mot de passe).

Reverse-engineerées à partir du XLSX historique (Gestion bases — rentrée 2025).

## Login KoXo
Format observé : `première lettre prénom (minuscule) + nom nettoyé (minuscules)`
limité à 10 caractères.

Exemples :
- "Tifenn ARGOUARC'H" → `targouarch`
- "Nawel BACH HAMBA" → `nbachhamba`
- "Loris BEN HAMOU--PEPIN" → `lbenhamoup` (tronqué à 10)

## Email lekreisker.fr
Format : `prenom.nom@lekreisker.fr`
- Tout en minuscules, accents retirés (unidecode)
- Apostrophes supprimées
- Espaces dans le nom → points
- Tirets doubles → tiret simple

Exemples :
- ARGOUARC'H Tifenn → tifenn.argouarch@lekreisker.fr
- BACH HAMBA Nawel → nawel.bach.hamba@lekreisker.fr
- BEN HAMOU--PEPIN Loris → loris.ben.hamou-pepin@lekreisker.fr

## Mot de passe auto-généré KoXo
Format observé : 6 lettres pseudo-prononçables (alternance consonne/voyelle)
+ 2 chiffres. Première lettre en majuscule.
Exemples : `Sateku68`, `Jitzam45`, `Sizuny72`, `Elouwu38`, `Rerele61`.
"""
from __future__ import annotations

import random
import re
import string

from unidecode import unidecode

CONSONNES = "bcdfgjklmnpqrstvwxz"  # h, y exclus pour éviter ambiguïtés
VOYELLES = "aeiou"
LONGUEUR_MAX_LOGIN = 10


def normaliser_pour_login(texte: str) -> str:
    """Minuscules, sans accents, ne garde que [a-z]."""
    if not texte:
        return ""
    s = unidecode(texte).lower()
    return re.sub(r"[^a-z]", "", s)


def normaliser_pour_email(texte: str, separateur_espaces: str = ".") -> str:
    """Variante pour l'email : minuscules, sans accents.

    - Apostrophes supprimées
    - Espaces remplacés par `separateur_espaces` (typiquement ".")
    - Tirets doubles compactés en tiret simple
    - Tirets simples conservés
    """
    if not texte:
        return ""
    s = unidecode(texte).lower()
    s = s.replace("'", "")  # apostrophes
    s = re.sub(r"-{2,}", "-", s)  # -- → -
    # Espaces → séparateur (et trim)
    s = re.sub(r"\s+", separateur_espaces, s.strip())
    # On garde [a-z0-9.-]
    s = re.sub(r"[^a-z0-9.\-]", "", s)
    return s


def login_koxo(prenom: str, nom: str) -> str:
    """Première lettre prénom + nom, lowercase, sans accents, max 10 chars."""
    p = normaliser_pour_login(prenom)
    n = normaliser_pour_login(nom)
    if not p:
        return n[:LONGUEUR_MAX_LOGIN]
    base = p[0] + n
    return base[:LONGUEUR_MAX_LOGIN]


def email_lekreisker(prenom: str, nom: str, domaine: str = "lekreisker.fr") -> str:
    """`prenom.nom@domaine` avec normalisation propre."""
    p = normaliser_pour_email(prenom)
    n = normaliser_pour_email(nom)
    if not p and not n:
        return ""
    if p and n:
        return f"{p}.{n}@{domaine}"
    return f"{p or n}@{domaine}"


def generer_mot_de_passe(rng: random.Random | None = None) -> str:
    """Génère un MDP type `Sateku68` : 6 lettres alternées + 2 chiffres.

    Args:
        rng: instance Random (pour reproductibilité en test). Si None,
             utilise un Random non-seedé (différent à chaque appel).
    """
    r = rng or random.Random()
    # Démarre par une consonne (statistiquement plus de prénoms en cnst)
    debut_consonne = r.choice([True, False])
    lettres: list[str] = []
    for i in range(6):
        if (i % 2 == 0) == debut_consonne:
            lettres.append(r.choice(CONSONNES))
        else:
            lettres.append(r.choice(VOYELLES))
    lettres[0] = lettres[0].upper()
    chiffres = f"{r.randint(0, 99):02d}"
    return "".join(lettres) + chiffres


def groupe_primaire_koxo(est_adulte: bool = False) -> str:
    """KoXo distingue Elèves vs Professeurs comme groupe primaire."""
    return "Professeurs" if est_adulte else "Elèves"
