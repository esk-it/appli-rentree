"""Le coffre : retrouver un mot de passe sans rouvrir KoXo.

## Pourquoi il existe

Retrouver le mot de passe d'un élève obligeait à ouvrir KoXo, chercher le
compte, lire la fiche. Et pour NDE, qui n'a pas de serveur KoXo, le mot de
passe n'existe nulle part : perdre la feuille imprimée voulait dire
réinitialiser le compte.

## Ce qui protège quoi

Un mot de passe maître, saisi à l'ouverture. Il n'est **jamais enregistré**,
nulle part. Il sert à dériver une clé — par `scrypt`, volontairement lent,
pour qu'essayer des millions de mots de passe coûte cher — et cette clé ne
vit qu'en mémoire, le temps de la session.

Ce que la base contient, ce sont des mots de passe chiffrés par AES-GCM.
Copié seul, le fichier ne vaut rien : c'est la propriété qui rend un coffre
acceptable sur un poste de travail. Sa contrepartie est absolue — **un mot
de passe maître oublié rend le coffre définitivement illisible**. Il n'y a
pas de récupération, sinon il n'y aurait pas de protection.

## Le vérificateur

Un seul enregistrement chiffre une phrase connue. Il permet de dire « ce
n'est pas le bon mot de passe » tout de suite, plutôt que de laisser
découvrir l'erreur en déchiffrant un secret au hasard — et surtout d'éviter
d'écrire de nouveaux secrets sous une clé fausse, ce qui les rendrait
illisibles avec la bonne.

## Pourquoi AES-GCM et non un simple chiffrement

Il est **authentifié** : une donnée modifiée est refusée au lieu de rendre
n'importe quoi. Sur des mots de passe, rendre n'importe quoi serait pire
que refuser.
"""
from __future__ import annotations

import hashlib
import json
import os
import secrets
import string
import unicodedata
from dataclasses import dataclass

from cryptography.exceptions import InvalidTag
from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from sqlalchemy.orm import Session

from backend.models import Parametre, Personne, SecretConserve

CLE_SEL = "coffre.sel"
CLE_VERIFICATEUR = "coffre.verificateur"

TEMOIN = b"appli-rentree/coffre/v1"
"""La phrase que chiffre le vérificateur. Sa valeur importe peu ; ce qui
compte est qu'elle soit constante et connue."""

# Paramètres scrypt : environ 100 ms sur un poste de bureau. Assez court
# pour ne pas gêner à l'ouverture, assez long pour rendre une attaque par
# dictionnaire ruineuse.
SCRYPT_N = 2**14
SCRYPT_R = 8
SCRYPT_P = 1


class CoffreVerrouille(Exception):
    """Le coffre ne peut pas être ouvert, et le message dit pourquoi."""


class CoffreDejaInitialise(Exception):
    """Il existe déjà un mot de passe maître ; le changer est un autre geste."""


@dataclass
class SecretLu:
    personne_id: int
    nom: str
    prenom: str
    login: str | None
    classe: str | None
    cible: str
    site: str | None
    origine: str
    mot_de_passe: str


# ---------------------------------------------------------------------------
# Le mot de passe maître
# ---------------------------------------------------------------------------


def _parametre(session: Session, cle: str) -> str | None:
    p = session.query(Parametre).filter_by(cle=cle).one_or_none()
    return json.loads(p.valeur_json) if p else None


def _ecrire_parametre(session: Session, cle: str, valeur) -> None:
    p = session.query(Parametre).filter_by(cle=cle).one_or_none()
    if p is None:
        p = Parametre(cle=cle, valeur_json=json.dumps(valeur))
        session.add(p)
    else:
        p.valeur_json = json.dumps(valeur)


def est_initialise(session: Session) -> bool:
    return _parametre(session, CLE_VERIFICATEUR) is not None


def _deriver(mot_de_passe: str, sel: bytes) -> bytes:
    """Transforme le mot de passe maître en clé de chiffrement.

    `scrypt` est choisi pour sa lenteur et sa consommation mémoire : c'est
    ce qui rend une attaque par dictionnaire coûteuse. La dérivation est
    refaite à chaque ouverture — la clé n'est jamais conservée.
    """
    if not mot_de_passe:
        raise CoffreVerrouille("Aucun mot de passe maître fourni.")
    return hashlib.scrypt(
        mot_de_passe.encode("utf-8"),
        salt=sel,
        n=SCRYPT_N,
        r=SCRYPT_R,
        p=SCRYPT_P,
        dklen=32,
    )


def initialiser(session: Session, mot_de_passe: str) -> bytes:
    """Crée le coffre et rend la clé. Refuse s'il existe déjà.

    Raises:
        CoffreDejaInitialise: un mot de passe maître est déjà en place.
        CoffreVerrouille: mot de passe vide ou trop court.
    """
    if est_initialise(session):
        raise CoffreDejaInitialise(
            "Le coffre a déjà un mot de passe maître. Le changer suppose de "
            "rechiffrer tout ce qu'il contient — c'est un autre geste."
        )
    if len(mot_de_passe or "") < 10:
        raise CoffreVerrouille(
            "Le mot de passe maître protège deux mille secrets : dix "
            "caractères au minimum, et de préférence une phrase."
        )

    sel = os.urandom(16)
    cle = _deriver(mot_de_passe, sel)
    nonce = os.urandom(12)
    temoin = AESGCM(cle).encrypt(nonce, TEMOIN, None)

    _ecrire_parametre(session, CLE_SEL, sel.hex())
    _ecrire_parametre(
        session, CLE_VERIFICATEUR, {"nonce": nonce.hex(), "chiffre": temoin.hex()}
    )
    session.flush()
    return cle


def ouvrir(session: Session, mot_de_passe: str) -> bytes:
    """Vérifie le mot de passe maître et rend la clé.

    Raises:
        CoffreVerrouille: coffre non initialisé, ou mot de passe faux.
    """
    sel_hex = _parametre(session, CLE_SEL)
    verif = _parametre(session, CLE_VERIFICATEUR)
    if not sel_hex or not verif:
        raise CoffreVerrouille(
            "Le coffre n'a pas encore de mot de passe maître."
        )

    cle = _deriver(mot_de_passe, bytes.fromhex(sel_hex))
    try:
        clair = AESGCM(cle).decrypt(
            bytes.fromhex(verif["nonce"]), bytes.fromhex(verif["chiffre"]), None
        )
    except InvalidTag:
        raise CoffreVerrouille("Mot de passe maître incorrect.") from None
    if clair != TEMOIN:
        raise CoffreVerrouille("Mot de passe maître incorrect.")
    return cle


# ---------------------------------------------------------------------------
# Déposer et lire
# ---------------------------------------------------------------------------


def deposer(
    session: Session,
    cle: bytes,
    *,
    personne_id: int,
    mot_de_passe: str,
    cible: str = "koxo",
    site: str | None = None,
    origine: str = "koxo",
) -> SecretConserve:
    """Range un mot de passe. Remplace celui qui s'y trouvait déjà."""
    if not mot_de_passe:
        raise ValueError("Aucun mot de passe à déposer.")

    nonce = os.urandom(12)
    chiffre = AESGCM(cle).encrypt(nonce, mot_de_passe.encode("utf-8"), None)

    secret = (
        session.query(SecretConserve)
        .filter_by(personne_id=personne_id, cible=cible, site=site)
        .one_or_none()
    )
    if secret is None:
        secret = SecretConserve(personne_id=personne_id, cible=cible, site=site)
        session.add(secret)
    secret.nonce = nonce
    secret.chiffre = chiffre
    secret.origine = origine
    session.flush()
    return secret


def _dechiffrer(cle: bytes, secret: SecretConserve) -> str:
    try:
        return AESGCM(cle).decrypt(secret.nonce, secret.chiffre, None).decode("utf-8")
    except InvalidTag:
        raise CoffreVerrouille(
            "Ce secret ne s'ouvre pas avec cette clé — il a été déposé sous "
            "un autre mot de passe maître."
        ) from None


def _normaliser(t: str) -> str:
    t = unicodedata.normalize("NFD", (t or "").lower())
    return "".join(c for c in t if not unicodedata.combining(c))


def chercher(
    session: Session, cle: bytes, requete: str, *, limite: int = 25
) -> list[SecretLu]:
    """Retrouve des mots de passe par nom, prénom ou identifiant.

    La recherche porte sur l'identité, pas sur le secret : on ne cherche
    jamais « qui a ce mot de passe ». Sans accents ni casse, parce que
    « guegan » doit trouver « Guégan ».
    """
    q = _normaliser(requete).strip()
    if not q:
        return []

    lignes = (
        session.query(SecretConserve, Personne)
        .join(Personne, Personne.id == SecretConserve.personne_id)
        .all()
    )
    trouves: list[SecretLu] = []
    for secret, personne in lignes:
        foin = _normaliser(
            f"{personne.nom} {personne.prenom} {personne.login} {personne.badge}"
        )
        if q not in foin:
            continue
        trouves.append(
            SecretLu(
                personne_id=personne.id,
                nom=personne.nom or "",
                prenom=personne.prenom or "",
                login=personne.login,
                classe=personne.classe,
                cible=secret.cible,
                site=secret.site,
                origine=secret.origine,
                mot_de_passe=_dechiffrer(cle, secret),
            )
        )
        if len(trouves) >= limite:
            break
    trouves.sort(key=lambda s: (s.nom, s.prenom))
    return trouves


# ---------------------------------------------------------------------------
# Verser un export KoXo dans le coffre
# ---------------------------------------------------------------------------


@dataclass
class RapportVersement:
    site: str | None = None
    nb_lignes: int = 0
    nb_deposes: int = 0
    nb_sans_correspondance: int = 0
    nb_sans_mot_de_passe: int = 0

    @property
    def resume(self) -> str:
        return (
            f"{self.nb_deposes} mot(s) de passe rangé(s) sur {self.nb_lignes} "
            f"ligne(s) lues"
        )


def verser_export_koxo(
    session: Session, cle: bytes, contenu_csv: bytes, *, site: str | None = None
) -> RapportVersement:
    """Range les mots de passe d'un export KoXo, par identifiant.

    Le rapprochement se fait sur le login, pas sur le nom : c'est
    l'identifiant qui est unique dans une base KoXo, et c'est lui que
    l'export porte à côté du mot de passe.
    """
    from backend.services.exports_google import _extraire_mdp_depuis_csv_koxo

    par_login = _extraire_mdp_depuis_csv_koxo(contenu_csv)
    rapport = RapportVersement(site=site, nb_lignes=len(par_login))

    personnes = {
        p.login: p for p in session.query(Personne).all() if p.login
    }
    for login, mdp in par_login.items():
        if not mdp:
            rapport.nb_sans_mot_de_passe += 1
            continue
        personne = personnes.get(login)
        if personne is None:
            rapport.nb_sans_correspondance += 1
            continue
        deposer(
            session,
            cle,
            personne_id=personne.id,
            mot_de_passe=mdp,
            cible="koxo",
            site=site,
            origine="koxo",
        )
        rapport.nb_deposes += 1
    return rapport


# ---------------------------------------------------------------------------
# Fabriquer un mot de passe, pour un site qui n'a pas de KoXo
# ---------------------------------------------------------------------------

CONSONNES = "bcdfgjklmnpqrstvxz"
VOYELLES = "aeiou"


def fabriquer_mot_de_passe() -> str:
    """Un mot de passe à la forme de ceux que KoXo génère : `Aaaaaa99`.

    Mesuré sur 1665 mots de passe réels de l'établissement : 1663 suivent
    exactement cette forme — une majuscule, cinq minuscules, deux chiffres,
    huit caractères. Reprendre la même forme n'est pas de l'imitation
    gratuite : les élèves de deux sites sur trois ont déjà celle-là, les
    fiches se ressemblent, et les règles de complexité de l'annuaire sont
    déjà satisfaites par elle.

    Les syllabes alternent consonne et voyelle pour rester lisibles sur une
    feuille imprimée — c'est là que le mot de passe est recopié.
    """
    lettres = "".join(
        secrets.choice(CONSONNES) + secrets.choice(VOYELLES) for _ in range(3)
    )
    chiffres = "".join(secrets.choice(string.digits) for _ in range(2))
    return lettres.capitalize() + chiffres
