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
from dataclasses import dataclass, field
from datetime import date, datetime

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
    identifiant: str | None = None
    """L'identifiant que la source associe à ce mot de passe, s'il diffère
    de celui de la personne. Voir `SecretConserve.identifiant`."""
    releve_le: date | None = None
    """Le jour où sa source a été lue — un relevé ancien peut être dépassé."""
    retenu: bool = False
    """C'est celui qu'une étiquette imprimerait."""
    ecart: bool = False
    """Les sources de cette personne disent deux mots de passe différents."""
    autre_base: bool = False
    """Un compte KoXo sur la base d'un autre établissement (la DAO) : un
    autre compte, que l'étiquette ignore."""
    a_relire: bool = False
    """Le relevé KoXo de cette personne est contredit par une source lue
    après lui : KoXo a peut-être changé, il faut le relire."""


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
    identifiant: str | None = None,
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
    secret.identifiant = identifiant
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


def lire_secret(cle: bytes, secret: SecretConserve) -> str:
    """Le mot de passe d'un secret déjà trouvé — pour un geste qui l'envoie
    aussitôt ailleurs (la création d'un compte Google), sans le garder."""
    return _dechiffrer(cle, secret)


ORDRE_DES_CIBLES = ("koxo", "charlemagne", "google")
"""KoXo d'abord : c'est **le** mot de passe. Il ouvre la session sur le
réseau pédagogique ; Charlemagne en garde une copie saisie à la main, et
Google en a reçu une à la création du compte (Johann, 13 octobre 2026)."""


def secrets_a_remettre(
    secrets: list[SecretConserve], site, *, google_d_abord: bool = False
) -> list[SecretConserve]:
    """Les mots de passe de la personne sur son site, KoXo d'abord.

    KoXo est **le** mot de passe ; Charlemagne en est une copie, Google
    aussi. Mais le coffre ne garde que des **relevés** : ce que chaque
    source disait le jour où on l'a lue. Un relevé KoXo peut donc être
    dépassé — voir `releve_contredit`, qui le dit avant qu'on l'imprime.

    Le mot de passe fabriqué pour Google à l'arrivée d'un élève vient en
    dernier là où KoXo existe ; là où il n'existe pas (NDE), il est le seul
    et passe devant — comme quand on crée le compte Google lui-même
    (`google_d_abord`).

    Un mot de passe KoXo d'une **autre** base ouvre un autre compte —
    l'accès DAO d'un élève de SU sur le serveur de NDK — et n'en fait pas
    partie. Rien n'est déchiffré ici.
    """
    nom = site.nom if site is not None else None
    base = ((site.base_koxo or "").strip() or None) if site is not None else None
    google_devant = google_d_abord or (site is not None and not base)

    def recevable(s: SecretConserve) -> bool:
        if s.cible == "koxo":
            return s.site in (None, nom, base)
        if s.cible == "google":
            return s.site in (None, nom)
        return s.cible == "charlemagne"

    retenus = [s for s in secrets if recevable(s)]
    retenus.sort(key=lambda s: ORDRE_DES_CIBLES.index(s.cible))
    retenus.sort(key=lambda s: (s.cible != "google") if google_devant else (s.cible == "google"))
    return retenus


def releve_contredit(recevables: list[SecretConserve], cle: bytes) -> SecretConserve | None:
    """Le relevé plus récent qui contredit celui de KoXo, s'il y en a un.

    Vécu le 13 octobre 2026 : KoXo NDK avait été relu le 31 août. Le
    15 septembre, les 140 montants de SU y ont retrouvé leur mot de passe du
    collège ; Charlemagne, relu le 12 octobre, portait le bon. Le coffre
    imprimait le relevé KoXo sans regarder sa date — et l'étiquette d'Eléanor
    BRETON a porté un mot de passe qui n'existait plus nulle part.

    KoXo reste prioritaire, mais un relevé KoXo contredit par une source lue
    **après lui** n'est plus sûr : KoXo a peut-être changé depuis. On ne
    l'imprime pas, on ne le donne pas à Google — on demande de relire KoXo.
    Relu le même jour ou après, KoXo l'emporte, et l'écart dit qu'il faut
    corriger l'autre source.
    """
    if not recevables or recevables[0].cible != "koxo":
        return None
    premier = recevables[0]
    valeur = None
    for s in recevables[1:]:
        if releve_le(s) <= releve_le(premier):
            continue
        if valeur is None:
            valeur = _dechiffrer(cle, premier)
        if _dechiffrer(cle, s) != valeur:
            return s
    return None


def releve_le(secret: SecretConserve) -> date:
    """Le jour où la source de ce mot de passe a été lue pour la dernière fois.

    Chaque ingestion Charlemagne et chaque versement KoXo réécrivent leurs
    secrets : `date_maj` est la date du dernier relevé.
    """
    return (secret.date_maj or datetime(1970, 1, 1)).date()


def secret_a_remettre(
    secrets: list[SecretConserve], site, *, google_d_abord: bool = False
) -> SecretConserve | None:
    """Le mot de passe que la personne utilise — voir `secrets_a_remettre`."""
    recevables = secrets_a_remettre(secrets, site, google_d_abord=google_d_abord)
    return recevables[0] if recevables else None


@dataclass
class SourceEcart:
    cible: str
    site: str | None
    releve_le: date
    retenu: bool


@dataclass
class EcartCoffre:
    """Une personne dont le coffre garde des mots de passe qui diffèrent."""

    personne_id: int
    nom: str
    prenom: str
    classe: str | None
    site: str | None
    sources: list[SourceEcart]
    a_relire: bool = False
    """KoXo est contredit par un relevé plus récent : rien ne s'imprime pour
    elle tant que KoXo n'est pas relu."""


def ecarts(session: Session, cle: bytes) -> list[EcartCoffre]:
    """Les personnes pour qui deux sources disent deux mots de passe.

    Ne rend aucun mot de passe : seulement qui, quelles sources, relues
    quand. KoXo fait foi : relu le plus récemment, l'écart dit que
    Charlemagne est à corriger ; relu avant l'autre source, il dit que le
    coffre est peut-être en retard sur KoXo, et qu'il faut le relire.
    """
    from collections import defaultdict

    from backend.models import Site

    sites = {s.id: s for s in session.query(Site)}
    siens: dict[int, list[SecretConserve]] = defaultdict(list)
    for s in session.query(SecretConserve):
        siens[s.personne_id].append(s)
    plusieurs = [pid for pid, liste in siens.items() if len(liste) > 1]
    personnes = {
        p.id: p for p in session.query(Personne).filter(Personne.id.in_(plusieurs or [0]))
    }

    resultat: list[EcartCoffre] = []
    for pid in plusieurs:
        p = personnes.get(pid)
        if p is None:
            continue
        site = sites.get(p.site_id)
        recevables = secrets_a_remettre(siens[pid], site)
        if len(recevables) < 2:
            continue
        if len({_dechiffrer(cle, s) for s in recevables}) < 2:
            continue
        resultat.append(EcartCoffre(
            personne_id=pid, nom=p.nom or "", prenom=p.prenom or "", classe=p.classe,
            site=site.nom if site else None,
            a_relire=releve_contredit(recevables, cle) is not None,
            sources=[
                SourceEcart(cible=s.cible, site=s.site, releve_le=releve_le(s), retenu=i == 0)
                for i, s in enumerate(recevables)
            ],
        ))
    resultat.sort(key=lambda e: (e.site or "~", e.classe or "~", e.nom, e.prenom))
    return resultat


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

    from backend.models import Site

    lignes = (
        session.query(SecretConserve, Personne)
        .join(Personne, Personne.id == SecretConserve.personne_id)
        .all()
    )
    sites = {s.id: s for s in session.query(Site)}
    tous_les_siens: dict[int, list[SecretConserve]] = {}
    for secret, personne in lignes:
        tous_les_siens.setdefault(personne.id, []).append(secret)
    trouves: list[SecretLu] = []
    for secret, personne in lignes:
        foin = _normaliser(
            f"{personne.nom} {personne.prenom} {personne.login} {personne.badge} "
            f"{secret.identifiant or ''}"
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
                identifiant=secret.identifiant,
                releve_le=releve_le(secret),
            )
        )
        lu = trouves[-1]
        recevables = secrets_a_remettre(
            tous_les_siens[personne.id], sites.get(personne.site_id)
        )
        lu.retenu = bool(recevables) and recevables[0] is secret
        lu.autre_base = secret not in recevables
        lu.ecart = len({_dechiffrer(cle, s) for s in recevables}) > 1
        lu.a_relire = lu.ecart and releve_contredit(recevables, cle) is not None
        if len(trouves) >= limite:
            break
    # KoXo avant Charlemagne : c'est lui, le mot de passe.
    trouves.sort(key=lambda s: (s.nom, s.prenom, s.cible == "charlemagne"))
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
    nb_retires: int = 0
    """Secrets que cette base contenait et que l'export ne confirme plus."""
    changes: list[str] = field(default_factory=list)
    """Ceux dont KoXo dit désormais autre chose que le relevé précédent —
    nommés, jamais le mot de passe. C'est le nombre qui aurait dû se voir
    après le 15 septembre : 140 montants dont le coffre gardait le mot de
    passe de la rentrée."""
    precedent_releve: date | None = None
    """Le jour du relevé que celui-ci remplace."""

    @property
    def resume(self) -> str:
        texte = (
            f"{self.nb_deposes} mot(s) de passe rangé(s) sur {self.nb_lignes} "
            f"ligne(s) lues"
        )
        if self.changes:
            depuis = (
                f" depuis le relevé du {self.precedent_releve:%d/%m}"
                if self.precedent_releve else ""
            )
            texte += f", dont {len(self.changes)} changé(s){depuis}"
        return texte


def _mdp_par_id_unique(contenu_csv: bytes) -> dict[int, str]:
    """`{ID unique: mot de passe}` lu dans un export KoXo, en mémoire.

    **Par ID unique, jamais par identifiant.** Un identifiant n'a de sens
    que dans sa propre base : `cdeniel` désigne Chloé DENIEL dans celle de
    NDK et Clément DENIEL dans celle de SU. Rapprocher par login versait le
    mot de passe de l'un dans la fiche de l'autre — un mot de passe faux
    est pire qu'un mot de passe absent, parce qu'on le croit bon.

    L'ID unique, lui, est le badge Charlemagne : il désigne la même
    personne partout, et c'est déjà la clé sur laquelle KoXo lui-même
    reconnaît ses comptes.
    """
    import csv as _csv
    import io as _io

    from unidecode import unidecode as _unidecode

    texte = None
    for encodage in ("cp1252", "utf-8"):
        try:
            texte = contenu_csv.decode(encodage)
            break
        except UnicodeDecodeError:
            continue
    if texte is None:
        raise ValueError("Impossible de décoder le CSV KoXo (ni cp1252, ni utf-8)")

    premiere = texte.split("\n", 1)[0]
    sep = "," if premiere.count(",") >= premiere.count(";") else ";"

    par_id: dict[int, str] = {}
    for ligne in _csv.DictReader(_io.StringIO(texte), delimiter=sep):
        identifiant = mdp = None
        for cle_col, val in ligne.items():
            if cle_col is None:
                continue
            k = _unidecode(str(cle_col).strip().lower())
            if k == "id unique":
                identifiant = (val or "").strip()
            elif k == "mot de passe":
                mdp = (val or "").strip()
        if identifiant and identifiant.isdigit() and mdp:
            par_id[int(identifiant)] = mdp
    return par_id


def verser_export_koxo(
    session: Session,
    cle: bytes,
    contenu_csv: bytes,
    *,
    site: str | None = None,
    remplacer: bool = True,
) -> RapportVersement:
    """Range les mots de passe d'un export KoXo, rapprochés par ID unique.

    Voir `_mdp_par_id_unique` : le rapprochement par identifiant serait une
    faute, un même identifiant désignant deux personnes différentes dans
    deux bases.

    Le versement **remplace** ce que cette base avait déposé plutôt que de
    s'y ajouter : un export décrit l'état complet d'un serveur, et ce qu'il
    ne contient plus n'y est plus. C'est aussi ce qui permet de réparer —
    reverser un export corrige les attributions fautives au lieu de les
    laisser cohabiter avec les bonnes.

    Le remplacement ne touche que la population que l'export contient :
    un export des seuls élèves laisse les professeurs en place.

    `remplacer=False` relit sans rien retirer : pour un export déposé à
    une autre fin (la Cohérence), dont on ne sait pas s'il couvre toute la
    population — quelques classes seulement effaceraient les autres.
    """
    par_id = _mdp_par_id_unique(contenu_csv)
    rapport = RapportVersement(site=site, nb_lignes=len(par_id))
    if not par_id:
        # Un export pris sans les mots de passe ne dit rien du coffre : il
        # ne doit surtout pas le vider.
        return rapport

    # Un export KoXo décrit l'**état complet** de sa base. Ce qu'il ne
    # contient plus n'y est plus, et le garder ferait afficher un mot de
    # passe qui n'ouvre rien. C'est aussi ce qui rend le versement
    # réparateur : un dépôt mal attribué disparaît au lieu de survivre.
    #
    # Seuls les secrets relevés dans KoXo sont concernés — ceux que le
    # programme a fabriqués pour un site sans KoXo n'ont pas d'export qui
    # les confirme, et les effacer les perdrait pour de bon.
    #
    # Et seulement pour la population que l'export couvre. On n'exporte que
    # les groupes qu'on a glissés dans la liste de KoXo : un export des
    # seuls élèves ne dit rien des professeurs, et vidait leurs mots de
    # passe du coffre (constaté le 15 octobre 2026, en écrivant la rentrée
    # guidée).
    toutes = session.query(Personne).all()
    personnes = {p.badge: p for p in toutes if p.badge}
    type_de = {p.id: p.type for p in toutes}
    couverts = {personnes[b].type for b in par_id if b in personnes}
    anciens = [
        s for s in session.query(SecretConserve)
        .filter_by(cible="koxo", site=site, origine="koxo")
        .all()
        if type_de.get(s.personne_id) in couverts
    ]
    avant: dict[int, str] = {}
    for vieux in anciens:
        try:
            avant[vieux.personne_id] = _dechiffrer(cle, vieux)
        except CoffreVerrouille:
            pass
    if anciens:
        rapport.precedent_releve = max(releve_le(s) for s in anciens)
    if remplacer:
        for vieux in anciens:
            session.delete(vieux)
        rapport.nb_retires = len(anciens)
        session.flush()

    for badge, mdp in par_id.items():
        if not mdp:
            rapport.nb_sans_mot_de_passe += 1
            continue
        personne = personnes.get(badge)
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
        if personne.id in avant and avant[personne.id] != mdp:
            rapport.changes.append(f"{personne.prenom} {personne.nom}")
    rapport.changes.sort()
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


# ---------------------------------------------------------------------------
# Les mots de passe de service : un portail, pas une personne
# ---------------------------------------------------------------------------
#
# Johann, 19 octobre 2026 : « je trouve chiant de devoir aller récupérer le
# mot de passe [du portail Sodexo] sur l'ancienne procédure à chaque fois ».
# Il n'a rien à faire dans le code — il partirait dans le dépôt, et
# deviendrait faux au premier changement. Il se range donc ici, chiffré
# sous la clé du coffre, et ne se lit que coffre ouvert. Le nom du service
# est lié au chiffré (données associées) : un dépôt ne peut pas être lu
# sous le nom d'un autre.

SERVICES = {"sodexo_portail": "Portail Sodexo"}
"""Les mots de passe de service que le coffre accepte, et leur libellé."""


def _cle_service(nom: str) -> str:
    if nom not in SERVICES:
        raise KeyError(nom)
    return f"coffre.service.{nom}"


def deposer_service(session: Session, cle: bytes, nom: str, mot_de_passe: str) -> None:
    """Range le mot de passe d'un service. Remplace celui qui s'y trouvait."""
    if not mot_de_passe:
        raise ValueError("Aucun mot de passe à ranger.")
    nonce = os.urandom(12)
    chiffre = AESGCM(cle).encrypt(nonce, mot_de_passe.encode("utf-8"), nom.encode("utf-8"))
    _ecrire_parametre(session, _cle_service(nom), {
        "nonce": nonce.hex(), "chiffre": chiffre.hex(),
        "mis_a_jour_le": datetime.now().isoformat(timespec="minutes"),
    })


def service_range(session: Session, nom: str) -> str | None:
    """Quand le mot de passe a été rangé, ou `None` s'il ne l'a jamais été."""
    v = _parametre(session, _cle_service(nom))
    return (v or {}).get("mis_a_jour_le") if v else None


def lire_service(session: Session, cle: bytes, nom: str) -> str | None:
    """Le mot de passe du service, en clair — coffre ouvert seulement."""
    v = _parametre(session, _cle_service(nom))
    if not v:
        return None
    try:
        return AESGCM(cle).decrypt(
            bytes.fromhex(v["nonce"]), bytes.fromhex(v["chiffre"]), nom.encode("utf-8")
        ).decode("utf-8")
    except InvalidTag:
        raise CoffreVerrouille(
            "Ce mot de passe ne s'ouvre pas avec cette clé — il a été rangé sous "
            "un autre mot de passe maître."
        ) from None


def retirer_service(session: Session, nom: str) -> None:
    p = session.query(Parametre).filter_by(cle=_cle_service(nom)).one_or_none()
    if p is not None:
        session.delete(p)
