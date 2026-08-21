"""Retrouver une personne dans Google quand son nom n'est pas écrit pareil.

## Le problème

Un tableau tenu à la main et un annuaire Google ne s'accordent presque
jamais sur l'orthographe. Sur l'instance de l'établissement, quatre
enseignants passaient pour absents de Google alors que leur compte
existait :

    CARBONELL-ROMO Rosa Maria  →  Rosa CARBONELL
    HAMON-DIAZ Carolina        →  Carolina HAMON
    LE JALU Jayaparathy        →  Jaya LE JALU
    MORIO Erwann               →  Erwan MORIO

Un nom composé dont Google ne garde que la première part, un prénom
composé réduit à son premier terme, un diminutif, une lettre en trop.
Quatre variantes distinctes, toutes mécaniques.

## La méthode

Des passes successives, de la plus stricte à la plus souple. La première
qui désigne **exactement une** personne l'emporte ; une passe qui en
désigne plusieurs ne conclut pas et laisse la suivante essayer sur une
autre base. Aucune ne devine : chacune énonce une règle, et le
rapprochement retenu dit laquelle, pour qu'un humain puisse le vérifier
d'un coup d'œil.

Un rapprochement obtenu autrement que par l'égalité stricte reste donc
**visible**. C'est ce qui le distingue d'une heuristique silencieuse :
il est appliqué, mais il n'est pas caché.

## Ce que la méthode refuse

Deux homonymes ne sont jamais départagés — choisir reviendrait à tirer au
sort. Et la tolérance orthographique s'arrête à une lettre : au-delà,
`MARTIN` et `MARTIH` ne sont plus une faute de frappe mais deux
personnes.
"""
from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass

SEPARATEURS = re.compile(r"[-\s'’]+")

LONGUEUR_MINI_PREFIXE = 4
"""En deçà, « Jan » rapprocherait Janick, Janine et Janvier."""


def normaliser(texte: str | None) -> str:
    """Minuscules, sans accents, sans ponctuation ni espaces."""
    sans = unicodedata.normalize("NFD", (texte or "").strip().lower())
    return re.sub(
        r"[^a-z0-9]", "", "".join(c for c in sans if unicodedata.category(c) != "Mn")
    )


def parts(texte: str | None) -> list[str]:
    """Composantes d'un nom composé : `LE JALU` → `[le, jalu]`."""
    sans = unicodedata.normalize("NFD", (texte or "").strip().lower())
    sans = "".join(c for c in sans if unicodedata.category(c) != "Mn")
    return [p for p in (re.sub(r"[^a-z0-9]", "", x) for x in SEPARATEURS.split(sans)) if p]


def distance_un(a: str, b: str) -> bool:
    """Vrai si une seule insertion, suppression ou substitution les sépare.

    Suffit pour `Erwann` / `Erwan` sans ouvrir la porte à des noms
    seulement voisins — et se calcule sans matrice.
    """
    if a == b:
        return False
    court, long = (a, b) if len(a) <= len(b) else (b, a)
    if len(long) - len(court) > 1:
        return False
    i = j = 0
    ecart = False
    while i < len(court) and j < len(long):
        if court[i] == long[j]:
            i += 1
            j += 1
            continue
        if ecart:
            return False
        ecart = True
        if len(court) == len(long):
            i += 1
        j += 1
    return True


@dataclass
class Candidat:
    email: str
    nom: str
    prenom: str


@dataclass
class Rapprochement:
    email: str | None
    methode: str
    """`exact`, `nom_compose`, `prenom_compose`, `prenom_abrege`,
    `orthographe`, `adresse`, ou `aucun` / `ambigu`."""
    approximatif: bool = False
    """Vrai dès que l'égalité stricte n'a pas suffi : à faire vérifier."""
    candidats: list[str] | None = None
    """Renseigné quand plusieurs personnes conviennent également."""

    @property
    def trouve(self) -> bool:
        return self.email is not None


def construire_index(comptes: list[dict]) -> list[Candidat]:
    """Prépare les comptes Google pour les passes de rapprochement."""
    index = []
    for c in comptes:
        email = (c.get("email") or "").strip().lower()
        if email:
            index.append(
                Candidat(email=email, nom=c.get("nom") or "", prenom=c.get("prenom") or "")
            )
    return index


def _uniques(candidats: list[Candidat]) -> list[str]:
    return sorted({c.email for c in candidats})


def rapprocher(nom: str, prenom: str, index: list[Candidat]) -> Rapprochement:
    """Retrouve l'adresse d'une personne, ou dit pourquoi elle échappe.

    Les passes sont ordonnées : la première qui désigne exactement une
    personne l'emporte.
    """
    n, p = normaliser(nom), normaliser(prenom)
    parts_n, parts_p = parts(nom), parts(prenom)
    if not n:
        return Rapprochement(None, "aucun")

    def tenter(predicat, methode: str, approximatif: bool) -> Rapprochement | None:
        trouves = [c for c in index if predicat(c)]
        emails = _uniques(trouves)
        if len(emails) == 1:
            return Rapprochement(emails[0], methode, approximatif)
        if len(emails) > 1:
            # On mémorise l'ambiguïté sans conclure : une passe plus souple
            # ne la lèvera pas, mais une passe sur une autre base peut.
            return Rapprochement(None, "ambigu", approximatif, candidats=emails)
        return None

    passes = [
        # 1. Les deux champs coïncident exactement.
        (lambda c: normaliser(c.nom) == n and normaliser(c.prenom) == p,
         "exact", False),

        # 2. Google ne garde qu'une part du nom composé — ou l'inverse.
        (lambda c: normaliser(c.prenom) == p
         and (normaliser(c.nom) in parts_n or n in parts(c.nom)),
         "nom_compose", True),

        # 3. Le prénom composé est réduit à l'un de ses termes.
        (lambda c: normaliser(c.nom) == n
         and (normaliser(c.prenom) in parts_p or p in parts(c.prenom)),
         "prenom_compose", True),

        # 4. Diminutif : l'un des prénoms commence l'autre.
        (lambda c: normaliser(c.nom) == n and _prefixe(normaliser(c.prenom), p),
         "prenom_abrege", True),

        # 5. Une lettre d'écart, sur l'un des deux champs seulement.
        (lambda c: (normaliser(c.nom) == n and distance_un(normaliser(c.prenom), p))
         or (normaliser(c.prenom) == p and distance_un(normaliser(c.nom), n)),
         "orthographe", True),

        # 6. L'adresse porte le nom que l'annuaire écrit autrement.
        (lambda c: _adresse_porte(c.email, n, p), "adresse", True),

        # 7. Nom composé tronqué **et** prénom composé réduit.
        (lambda c: (normaliser(c.nom) in parts_n or n in parts(c.nom))
         and (normaliser(c.prenom) in parts_p or p in parts(c.prenom)),
         "nom_et_prenom_composes", True),
    ]

    ambigu: Rapprochement | None = None
    for predicat, methode, approximatif in passes:
        resultat = tenter(predicat, methode, approximatif)
        if resultat is None:
            continue
        if resultat.trouve:
            return resultat
        ambigu = ambigu or resultat

    return ambigu or Rapprochement(None, "aucun")


def _prefixe(a: str, b: str) -> bool:
    if not a or not b or a == b:
        return False
    court, long = (a, b) if len(a) <= len(b) else (b, a)
    return len(court) >= LONGUEUR_MINI_PREFIXE and long.startswith(court)


def _adresse_porte(email: str, n: str, p: str) -> bool:
    """L'adresse contient-elle le nom et le prénom cherchés ?

    `jaya.lejalu@…` porte bien `lejalu` : l'annuaire écrit le nom autrement,
    l'adresse, elle, garde la forme collée.
    """
    local = normaliser(email.split("@", 1)[0])
    if not local or len(n) < 3:
        return False
    return n in local and (len(p) < 3 or local.startswith(p[:3]))
