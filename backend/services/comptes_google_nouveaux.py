"""Les inscrits qui n'ont pas encore de compte Google, et leur création en un clic.

## Pourquoi

Un élève qui arrive en cours d'année faisait faire trois allers-retours :
un export Charlemagne, un export KoXo pour récupérer son mot de passe, puis
la création de son compte à la main dans la console Google. Johann recopie
de toute façon l'identifiant et le mot de passe dans Charlemagne (« ID
Réseau Péda », « MDP Réseau Péda ») une fois le compte KoXo fait — et
l'export enrichi les range au coffre depuis la v0.183. Le programme a donc
tout : l'adresse, l'unité, le groupe, le mot de passe. Il ne lui manquait
que le geste (1er octobre 2026).

Le geste reste un clic, pas un automatisme : créer un compte se voit dehors,
et l'écran montre d'abord qui serait créé, où, avec quelle adresse.

## Qui est « sans compte »

Le relevé lit une fois tous les comptes du domaine. Un inscrit de l'année a
un compte si son adresse — ou l'un des alias d'un compte — est la sienne,
ou si son numéro Charlemagne est inscrit sur un compte.

Un compte **au même nom** sous une autre adresse arrête tout : c'est
probablement le sien, créé à la main sous une autre orthographe. Il est
« à rattacher », jamais doublé. Sauf s'il appartient visiblement à quelqu'un
d'autre — son adresse est celle d'une autre fiche, ou il porte un autre
numéro Charlemagne : un homonyme n'empêche pas un compte.

## Le mot de passe

Celui du coffre, dans cet ordre : celui fabriqué pour Google là où il n'y a
pas de KoXo (NDE), celui de KoXo — qui fait foi —, celui que Charlemagne
porte. Sans mot de passe, pas de création : en inventer un ici ferait un
troisième mot de passe, que ni KoXo ni la fiche de l'élève ne connaissent.

## L'unité

Celle où sont ses camarades : l'unité définitive de sa classe si des
comptes y sont déjà, celle de pré-rentrée si c'est là qu'ils attendent. Le
programme n'a pas à deviner à quel moment de la campagne on se trouve —
les comptes de la classe le disent.
"""
from __future__ import annotations

import re
import unicodedata
from collections import Counter
from dataclasses import dataclass, field
from datetime import datetime

from sqlalchemy.orm import Session

from backend.models import (
    AnneeScolaire,
    CompteCible,
    Personne,
    SecretConserve,
    Site,
    Snapshot,
    TableCorrespondance,
)

ORDRE_DES_SECRETS = {"google": 0, "koxo": 1, "charlemagne": 2}
"""Quel mot de passe donner à Google quand le coffre en garde plusieurs."""


class CreationImpossible(Exception):
    """La création est refusée, et le message dit pourquoi."""


@dataclass
class CompteAFaire:
    personne_id: int
    nom: str
    prenom: str
    classe: str | None
    site: str | None
    adresse: str | None
    ou: str | None
    groupe: str | None
    origine_mot_de_passe: str | None
    """`google`, `koxo` ou `charlemagne` — d'où viendra le mot de passe."""
    bloque: str | None = None
    """Ce qui empêche la création, s'il y a quelque chose."""


@dataclass
class CompteARattacher:
    personne_id: int
    nom: str
    prenom: str
    classe: str | None
    adresse: str | None
    adresses_google: list[str]


@dataclass
class RapportNouveaux:
    annee: str
    nb_inscrits: int = 0
    nb_avec_compte: int = 0
    a_creer: list[CompteAFaire] = field(default_factory=list)
    a_rattacher: list[CompteARattacher] = field(default_factory=list)


@dataclass
class ResultatCreation:
    personne_id: int
    nom: str
    prenom: str
    adresse: str | None
    statut: str
    """`cree`, `existait` (Google l'avait déjà), `ignore` ou `echec`."""
    message: str | None = None
    ou: str | None = None
    groupe: str | None = None
    groupe_ok: bool = False


def _cle_nom(nom: str | None, prenom: str | None) -> str:
    """`LE GALL Yann` et `Le-Gall Yann` se reconnaissent."""
    t = unicodedata.normalize("NFKD", f"{nom or ''} {prenom or ''}")
    t = "".join(c for c in t if not unicodedata.combining(c)).casefold()
    return re.sub(r"[\s_\-]+", " ", t).strip()


def _annee(session: Session, annee_id: int | None) -> AnneeScolaire:
    if annee_id is not None:
        annee = session.get(AnneeScolaire, annee_id)
    else:
        annee = session.query(AnneeScolaire).order_by(AnneeScolaire.libelle.desc()).first()
    if annee is None:
        raise CreationImpossible("Aucune année scolaire dans le référentiel.")
    return annee


def _meilleur_secret(secrets: list[SecretConserve], site_nom: str | None):
    """Le mot de passe à donner à Google, sans l'ouvrir."""
    candidats = [
        s for s in secrets
        if s.cible in ORDRE_DES_SECRETS
        and not (s.cible == "google" and s.site not in (None, site_nom))
    ]
    candidats.sort(key=lambda s: ORDRE_DES_SECRETS[s.cible])
    return candidats[0] if candidats else None


def relever(
    session: Session, utilisateurs_google: list[dict], *, annee_id: int | None = None
) -> RapportNouveaux:
    """Qui, parmi les inscrits de l'année, n'a pas de compte Google.

    Args:
        utilisateurs_google: tous les comptes du domaine, tels que
            `ClientGoogle.lister_utilisateurs` les rend.
    """
    annee = _annee(session, annee_id)
    rapport = RapportNouveaux(annee=annee.libelle)

    derniers: dict[int, Snapshot] = {}
    for sn in (
        session.query(Snapshot)
        .filter(Snapshot.annee_scolaire_id == annee.id)
        .order_by(Snapshot.date_ingestion, Snapshot.id)
    ):
        derniers[sn.personne_id] = sn
    eleves = (
        session.query(Personne)
        .filter(Personne.id.in_(list(derniers) or [0]), Personne.type == "eleve")
        .all()
    )
    sites = {s.id: s for s in session.query(Site)}
    table = {(t.classe_code_court or "").strip(): t for t in session.query(TableCorrespondance)}

    adresses_google: set[str] = set()
    ids_externes: set[str] = set()
    par_nom: dict[str, list[dict]] = {}
    comptes_par_ou: Counter[str] = Counter()
    for u in utilisateurs_google:
        adresses_google.add((u.get("email") or "").lower())
        adresses_google.update(a.lower() for a in u.get("alias") or [])
        if u.get("id_externe"):
            ids_externes.add(str(u["id_externe"]))
        par_nom.setdefault(_cle_nom(u.get("nom"), u.get("prenom")), []).append(u)
        comptes_par_ou[u.get("ou") or ""] += 1

    # Les adresses et numéros que portent les autres fiches : un compte qui
    # les porte appartient à quelqu'un d'autre, homonyme ou non.
    adresses_des_fiches: dict[str, int] = {}
    numeros_des_fiches: dict[str, int] = {}
    for p in session.query(Personne):
        for a in (p.email_constate, p.email):
            if a:
                adresses_des_fiches.setdefault(a.lower(), p.id)
        if p.id_charlemagne is not None:
            numeros_des_fiches.setdefault(str(p.id_charlemagne), p.id)

    secrets: dict[int, list[SecretConserve]] = {}
    for s in session.query(SecretConserve).filter(
        SecretConserve.personne_id.in_([p.id for p in eleves] or [0])
    ):
        secrets.setdefault(s.personne_id, []).append(s)

    for p in eleves:
        rapport.nb_inscrits += 1
        adresse = (p.email or "").lower() or None
        if (adresse and adresse in adresses_google) or (
            p.id_charlemagne is not None and str(p.id_charlemagne) in ids_externes
        ):
            rapport.nb_avec_compte += 1
            continue

        sn = derniers[p.id]
        classe = (sn.classe or p.classe or "").strip() or None
        site = sites.get(p.site_id)

        homonymes = [
            u for u in par_nom.get(_cle_nom(p.nom, p.prenom), [])
            if adresses_des_fiches.get((u.get("email") or "").lower(), p.id) == p.id
            and numeros_des_fiches.get(str(u.get("id_externe") or ""), p.id) == p.id
        ]
        if homonymes:
            rapport.a_rattacher.append(
                CompteARattacher(
                    personne_id=p.id, nom=p.nom or "", prenom=p.prenom or "",
                    classe=classe, adresse=adresse,
                    adresses_google=sorted(u["email"] for u in homonymes),
                )
            )
            continue

        t = table.get(classe or "")
        ou = None
        if t is not None:
            definitive, attente = t.ou_definitive, t.ou_pre_rentree
            ou = attente if (
                attente and not comptes_par_ou.get(definitive) and comptes_par_ou.get(attente)
            ) else definitive
        secret = _meilleur_secret(secrets.get(p.id, []), site.nom if site else None)

        bloque = None
        if not adresse:
            bloque = "Adresse non calculable : la fiche n'a pas de site."
        elif t is None:
            bloque = f"Classe « {classe or '—'} » absente de la table de correspondance."
        elif secret is None:
            bloque = (
                "Aucun mot de passe au coffre : « MDP Réseau Péda » est-il "
                "rempli dans Charlemagne, et l'export ingéré coffre ouvert ?"
            )
        rapport.a_creer.append(
            CompteAFaire(
                personne_id=p.id, nom=p.nom or "", prenom=p.prenom or "",
                classe=classe, site=site.nom if site else None, adresse=adresse,
                ou=ou, groupe=(t.groupe_google or None) if t else None,
                origine_mot_de_passe=secret.cible if secret else None,
                bloque=bloque,
            )
        )

    rapport.a_creer.sort(key=lambda c: (c.site or "~", c.classe or "~", c.nom, c.prenom))
    rapport.a_rattacher.sort(key=lambda c: (c.classe or "~", c.nom, c.prenom))
    return rapport


def _deja_present(erreur: Exception) -> bool:
    texte = str(erreur)
    return "409" in texte or "already exists" in texte.lower() or "duplicate" in texte.lower()


def creer(
    session: Session,
    client,
    cle: bytes,
    personne_ids: list[int],
    *,
    annee_id: int | None = None,
) -> list[ResultatCreation]:
    """Crée les comptes désignés, les place dans leur groupe, et le vérifie.

    Le relevé est refait d'abord, sur les comptes du domaine tels qu'ils
    sont maintenant : entre l'aperçu et le clic, quelqu'un a pu créer le
    compte à la main.
    """
    from backend.services.coffre import lire_secret
    from backend.services.google_api import payload_creation_utilisateur
    from backend.services.journal import journaliser

    rapport = relever(session, client.lister_utilisateurs(), annee_id=annee_id)
    a_creer = {c.personne_id: c for c in rapport.a_creer}
    resultats: list[ResultatCreation] = []

    for pid in dict.fromkeys(personne_ids):
        p = session.get(Personne, pid)
        if p is None:
            continue
        c = a_creer.get(pid)
        base = dict(personne_id=pid, nom=p.nom or "", prenom=p.prenom or "", adresse=p.email)
        if c is None:
            resultats.append(ResultatCreation(
                **base, statut="ignore",
                message="N'est plus à créer : un compte porte désormais son adresse, "
                        "son numéro ou son nom.",
            ))
            continue
        if c.bloque:
            resultats.append(ResultatCreation(**base, statut="ignore", message=c.bloque))
            continue

        site = session.get(Site, p.site_id) if p.site_id else None
        secret = _meilleur_secret(
            session.query(SecretConserve).filter_by(personne_id=pid).all(),
            site.nom if site else None,
        )
        mot_de_passe = lire_secret(cle, secret)
        r = ResultatCreation(**base, statut="cree", ou=c.ou, groupe=c.groupe)
        identifiant_google = None
        try:
            cree = client.creer_utilisateur(payload_creation_utilisateur(
                prenom=p.prenom or "", nom=p.nom or "", email=c.adresse,
                org_unit_path=c.ou, mot_de_passe=mot_de_passe,
                id_charlemagne=p.id_charlemagne, type_personne="eleve",
            ))
            identifiant_google = (cree or {}).get("id")
        except Exception as e:
            if not _deja_present(e):
                r.statut, r.message = "echec", f"{type(e).__name__}: {e}"
                resultats.append(r)
                continue
            r.statut, r.message = "existait", "Google avait déjà ce compte : rien n'a été écrasé."

        if c.groupe:
            try:
                client.ajouter_membre(c.groupe, c.adresse)
                r.groupe_ok = True
            except Exception as e:
                r.groupe_ok = _deja_present(e)
                if not r.groupe_ok:
                    r.message = f"Compte créé, mais le groupe {c.groupe} a refusé : {e}"

        p.email_constate = c.adresse
        compte = (
            session.query(CompteCible).filter_by(personne_id=pid, cible="google").one_or_none()
        )
        if compte is None:
            compte = CompteCible(personne_id=pid, cible="google", etat="cree")
            session.add(compte)
        elif compte.etat in ("prevu", None):
            compte.etat = "cree"
        compte.ou_appliquee = c.ou
        if identifiant_google:
            compte.identifiant_externe = identifiant_google
        compte.date_derniere_maj = datetime.utcnow()
        session.commit()
        resultats.append(r)

    # Le journal compte, il ne nomme ni ne dévoile : ni mot de passe, ni nom.
    journaliser(
        session,
        type_operation="cycle_vie",
        cible="google",
        mode="reel",
        annee_libelle=rapport.annee,
        parametres={"personnes": [r.personne_id for r in resultats]},
        resultat=dict(Counter(r.statut for r in resultats)),
        notes="Création de comptes Google depuis le relevé des inscrits sans compte.",
    )
    session.commit()
    return resultats


def etiquettes(
    session: Session,
    cle: bytes,
    personne_ids: list[int],
    *,
    annee_id: int | None = None,
    modele: str | None = None,
    par_page: int = 18,
    police: str | None = None,
) -> tuple[list[tuple[str, bytes]], list[str]]:
    """Les étiquettes de quelques élèves, mot de passe du coffre compris.

    Pour l'élève qui arrive, sans relire l'export KoXo : son identifiant et
    son mot de passe sont au coffre, venus de Charlemagne ou de KoXo. Une
    planche par site — chacune porte le logo et la couleur du sien.

    Returns:
        `[(site, planche HTML)]`, et les élèves sans mot de passe au coffre.
    """
    from backend.services.coffre import lire_secret
    from backend.services.comptes_sans_koxo import fiches_html

    annee = _annee(session, annee_id)
    classes = {
        sn.personne_id: sn.classe
        for sn in session.query(Snapshot)
        .filter(Snapshot.annee_scolaire_id == annee.id, Snapshot.personne_id.in_(personne_ids or [0]))
        .order_by(Snapshot.date_ingestion, Snapshot.id)
    }
    sites = {s.id: s for s in session.query(Site)}
    par_site: dict[int, list[dict]] = {}
    sans_mot_de_passe: list[str] = []
    for pid in dict.fromkeys(personne_ids):
        p = session.get(Personne, pid)
        site = sites.get(p.site_id) if p else None
        if p is None or site is None:
            continue
        secret = _meilleur_secret(
            session.query(SecretConserve).filter_by(personne_id=pid).all(), site.nom
        )
        if secret is None:
            sans_mot_de_passe.append(f"{p.prenom} {p.nom}")
            continue
        classe = classes.get(pid) or p.classe or ""
        par_site.setdefault(site.id, []).append({
            "nom": p.nom or "", "prenom": p.prenom or "",
            "classe": classe, "groupe": classe,
            "login": secret.identifiant or p.login,
            "mot_de_passe": lire_secret(cle, secret),
            "adresse": p.email or "",
        })

    planches = [
        (
            sites[sid].nom,
            fiches_html(
                lignes,
                organisation=sites[sid].nom_complet or sites[sid].organisation_etiquettes or sites[sid].nom,
                annee=annee.libelle,
                avec_reseau=bool(sites[sid].base_koxo),
                site_nom=sites[sid].nom,
                modele=modele,
                par_page=par_page,
                police=police,
            ),
        )
        for sid, lignes in sorted(par_site.items(), key=lambda kv: sites[kv[0]].nom)
    ]
    return planches, sans_mot_de_passe
