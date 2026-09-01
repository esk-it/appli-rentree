"""Faire entrer quelqu'un en cours d'année, du référentiel jusqu'à Google.

## Ce qui manquait

Le programme savait déplacer une personne — changer sa classe, son unité
d'organisation, ses groupes — mais pas en faire entrer une. Tout venait de
l'ingestion Charlemagne, qui arrive une fois l'an. Un élève inscrit un
mardi de novembre, une AESH qui prend son poste le jour même, n'avaient
aucune porte d'entrée : il fallait les créer à la main dans Google, dans
KoXo, et espérer que la prochaine ingestion retombe sur ses pieds.

## Trois gestes, et pas un seul

Créer un compte Google ne se fait pas par l'API ici : la console lit un
CSV. L'arrivée se joue donc en trois temps, et il faut les distinguer,
parce qu'entre le deuxième et le troisième il y a un geste humain.

1. **Retenir** — la personne entre au référentiel avec son identifiant et
   son adresse, calculés par les mêmes règles que pour tout le monde.
2. **Fabriquer** — un CSV d'une ligne pour la console, mot de passe
   compris, rangé au coffre dans le même geste.
3. **Placer** — une fois le compte créé, l'ajouter à son groupe de classe.

L'unité d'organisation, elle, se choisit dès le CSV : la console y range
le compte à la création, et un déplacement de plus serait un aller-retour
pour rien.

## Les deux choix qu'on ne peut pas faire à sa place

**Pré-rentrée ou définitive.** Avant la rentrée, un élève attend dans
l'unité de pré-rentrée, où la classe ne transparaît pas. Après, il va
dans celle de sa classe. Un arrivant de novembre relève du second cas,
un inscrit de fin août du premier — et le programme n'a pas à deviner à
quel moment de la campagne on se trouve.

**Le groupe, maintenant ou plus tard.** Le groupe de classe est une liste
de diffusion : y entrer, c'est apparaître aux yeux des autres. C'est
souvent ce qu'on veut, et parfois non — un élève dont l'inscription
n'est pas encore annoncée.

## L'ID unique

KoXo reconnaît un compte par son ID unique, dérivé de l'identifiant
Charlemagne. Une arrivée qui n'en a pas encore ne pourra pas être
reconnue par la synchronisation : le programme l'accepte — une AESH n'est
pas toujours dans Charlemagne — mais le dit.
"""
from __future__ import annotations

from dataclasses import dataclass, field

from sqlalchemy.orm import Session

from backend.models import (
    AnneeScolaire,
    Personne,
    Site,
    Snapshot,
    TableCorrespondance,
)


class ArriveeImpossible(Exception):
    """Ce qui empêche l'arrivée, dit avant d'écrire quoi que ce soit."""


@dataclass
class PropositionArrivee:
    """Ce que le programme propose, avant d'écrire."""

    nom: str
    prenom: str
    site_nom: str
    type_personne: str
    classe: str | None
    login_propose: str
    email_propose: str
    badge: int | None
    ou_pre_rentree: str | None = None
    ou_definitive: str | None = None
    groupe_google: str | None = None
    personne_existante_id: int | None = None
    """Quelqu'un porte déjà cet identifiant Charlemagne — on ne crée pas un
    doublon, on complète."""

    avertissements: list[str] = field(default_factory=list)

    @property
    def peut_etre_enregistree(self) -> bool:
        return bool(self.login_propose and self.email_propose)


def proposer_arrivee(
    session: Session,
    *,
    site_id: int,
    type_personne: str,
    nom: str,
    prenom: str,
    annee_id: int,
    classe: str | None = None,
    id_charlemagne: int | None = None,
) -> PropositionArrivee:
    """Ce que deviendrait cette personne, sans rien écrire.

    L'identifiant et l'adresse sortent des règles ordinaires : celles qui
    ont nommé les 1 820 autres. Une arrivée nommée à part serait une
    exception à maintenir.
    """
    from backend.services.regles_metier import calculer_email, proposer_login_pour

    if type_personne not in ("eleve", "adulte"):
        raise ArriveeImpossible(f"type_personne invalide : {type_personne!r}")
    nom, prenom = (nom or "").strip(), (prenom or "").strip()
    if not nom or not prenom:
        raise ArriveeImpossible("Le nom et le prénom sont l'un et l'autre requis.")

    site = session.query(Site).filter_by(id=site_id).one_or_none()
    if site is None:
        raise ArriveeImpossible(f"Site introuvable : {site_id}")
    annee = session.query(AnneeScolaire).filter_by(id=annee_id).one_or_none()
    if annee is None:
        raise ArriveeImpossible(f"Année introuvable : {annee_id}")

    classe = (classe or "").strip() or None
    prop = PropositionArrivee(
        nom=nom, prenom=prenom, site_nom=site.nom, type_personne=type_personne,
        classe=classe, login_propose="", email_propose="", badge=None,
    )

    # Déjà là ? Une réinscription, ou une saisie faite deux fois.
    existante = None
    if id_charlemagne is not None:
        existante = (
            session.query(Personne)
            .filter_by(type=type_personne, id_charlemagne=id_charlemagne)
            .one_or_none()
        )
    if existante is None:
        from backend.services.regles_metier import normaliser_nom

        memes = [
            p
            for p in session.query(Personne).filter_by(type=type_personne).all()
            if normaliser_nom(p.nom) == normaliser_nom(nom)
            and normaliser_nom(p.prenom) == normaliser_nom(prenom)
        ]
        if memes:
            prop.avertissements.append(
                f"{len(memes)} personne(s) portent déjà ce nom au référentiel — "
                + ", ".join(
                    f"{p.prenom} {p.nom} (badge {p.badge}, {p.login})" for p in memes[:3]
                )
                + ". Vérifie qu'il ne s'agit pas de la même."
            )
    else:
        prop.personne_existante_id = existante.id
        prop.avertissements.append(
            f"{existante.prenom} {existante.nom} est déjà au référentiel sous cet "
            "identifiant Charlemagne. Son compte ne sera pas recréé : seule la "
            "photographie de l'année sera ajoutée."
        )

    if id_charlemagne is None:
        prop.avertissements.append(
            "Sans identifiant Charlemagne, ce compte n'aura pas d'ID unique. "
            "La synchronisation KoXo ne saura pas le reconnaître — il faudra "
            "l'y créer à la main."
        )
    else:
        prop.badge = Personne.calculer_badge(type_personne, id_charlemagne)

    if existante is not None:
        prop.login_propose = existante.login or ""
        prop.email_propose = existante.email or ""
    else:
        p = proposer_login_pour(session, prenom, nom)
        if p is None:
            raise ArriveeImpossible(
                "Impossible de calculer un identifiant à partir de ce nom."
            )
        prop.login_propose = p.login_propose
        if p.a_conflit:
            prop.avertissements.append(
                f"L'identifiant « {p.login_base} » est déjà pris : "
                f"« {p.login_propose} » a été retenu."
            )
        prop.email_propose = _adresse_libre(session, prenom, nom, site, prop)

    if type_personne == "eleve":
        if not classe:
            raise ArriveeImpossible("Un élève doit avoir une classe.")
        tc = _correspondance(session, site_id, classe)
        if tc is None:
            raise ArriveeImpossible(
                f"La classe « {classe} » n'a pas de ligne dans la table de "
                f"correspondance du site {site.nom} : ni son unité "
                "d'organisation ni son groupe ne sont connus."
            )
        prop.ou_pre_rentree = tc.ou_pre_rentree
        prop.ou_definitive = tc.ou_definitive
        prop.groupe_google = tc.groupe_google
        if not (tc.groupe_google or "").strip():
            prop.avertissements.append(
                f"La classe « {classe} » ne déclare aucun groupe : "
                "l'arrivant ne pourra être ajouté à aucune liste."
            )
    return prop


def enregistrer_arrivee(
    session: Session,
    proposition: PropositionArrivee,
    *,
    site_id: int,
    annee_id: int,
    id_charlemagne: int | None = None,
    mode: str = "simulation",
) -> Personne:
    """Fait entrer la personne au référentiel. Rien dans Google encore.

    Le référentiel d'abord, comme pour un changement de classe : sans lui,
    la composition des groupes et la bascule ignoreraient l'arrivant, et
    la prochaine ingestion Charlemagne le prendrait pour un inconnu.
    """
    if mode not in ("simulation", "reel"):
        raise ValueError(f"mode invalide : {mode!r}")

    personne = None
    if proposition.personne_existante_id is not None:
        personne = (
            session.query(Personne)
            .filter_by(id=proposition.personne_existante_id)
            .one_or_none()
        )

    if personne is None:
        personne = Personne(
            type=proposition.type_personne,
            id_charlemagne=id_charlemagne,
            badge=proposition.badge,
            login=proposition.login_propose,
            nom=proposition.nom,
            prenom=proposition.prenom,
            site_id=site_id,
        )
        # L'adresse est **écrite**, pas laissée au calcul : une homonymie
        # tranchée à la saisie doit tenir, et le calcul redonnerait celle
        # de l'autre.
        personne.email_attribuee = proposition.email_propose
        session.add(personne)
        session.flush()
    else:
        personne.site_id = site_id

    deja = (
        session.query(Snapshot)
        .filter_by(personne_id=personne.id, annee_scolaire_id=annee_id)
        .first()
    )
    if deja is None:
        session.add(
            Snapshot(
                personne_id=personne.id,
                annee_scolaire_id=annee_id,
                nom=proposition.nom,
                prenom=proposition.prenom,
                classe=proposition.classe,
            )
        )
    elif proposition.classe:
        deja.classe = proposition.classe

    # La photographie de l'année ne suffit pas : `Personne.classe` est la
    # classe **courante**, et c'est elle que lisent les écrans et les
    # recherches — Mouvements affichait « sans classe » un élève qu'on
    # venait de placer en terminale. L'ingestion et le changement de classe
    # écrivent les deux ; une arrivée n'a pas à faire autrement.
    if proposition.classe:
        personne.classe = proposition.classe

    if mode == "reel":
        session.commit()
    else:
        session.rollback()
    return personne


# ---------------------------------------------------------------------------
# Détail
# ---------------------------------------------------------------------------


def _code_classe(texte: str | None) -> str:
    """Normalise un code de classe — et garde les chiffres.

    `normaliser_nom` ne conserve que `[a-z]` : c'est ce qu'il faut pour un
    patronyme, et c'est ruineux ici. `2_1` et `9_9` s'y réduisent tous deux
    à la chaîne vide, et n'importe quelle classe répondait à n'importe
    quelle autre — un arrivant serait entré dans l'unité d'organisation
    d'une classe qui n'est pas la sienne.
    """
    import re
    import unicodedata

    s = unicodedata.normalize("NFD", (texte or "").upper())
    s = "".join(c for c in s if not unicodedata.combining(c))
    return re.sub(r"[^A-Z0-9]", "", s)


def _correspondance(
    session: Session, site_id: int, classe: str
) -> TableCorrespondance | None:
    vise = _code_classe(classe)
    if not vise:
        return None
    lignes = session.query(TableCorrespondance).filter_by(site_id=site_id).all()
    for t in lignes:
        if (t.classe_code_court or "").strip() == classe.strip():
            return t
    for t in lignes:
        if _code_classe(t.classe_code_court) == vise:
            return t
    for t in lignes:
        if _code_classe(t.classe_charlemagne_long) == vise:
            return t
    return None


def _adresse_libre(
    session: Session, prenom: str, nom: str, site: Site, prop: PropositionArrivee
) -> str:
    """`prenom.nom@domaine`, suffixé si quelqu'un la porte déjà.

    Deux personnes du même prénom et du même nom calculent la même
    adresse ; Google refuse la seconde. La règle est celle du module des
    homonymies, appliquée ici à une personne qui n'existe pas encore.
    """
    from backend.services.adresses_homonymes import _prochaine_libre
    from backend.services.regles_metier import calculer_email

    base = calculer_email(prenom, nom, site.domaine_mail)
    if not base:
        return ""
    prises = {
        (p.email or "").strip().lower()
        for p in session.query(Personne).all()
        if (p.email or "").strip()
    }
    if base.lower() not in prises:
        return base
    libre = _prochaine_libre(base.lower(), prises)
    prop.avertissements.append(
        f"L'adresse « {base} » est déjà portée : « {libre} » a été retenue."
    )
    return libre


# ---------------------------------------------------------------------------
# Le compte Google
# ---------------------------------------------------------------------------


@dataclass
class RapportCompte:
    """Ce qui a été fabriqué, et ce qu'il reste à faire à la main."""

    email: str
    ou_visee: str
    nom_fichier: str
    mot_de_passe_genere: bool
    groupe: str | None = None
    avertissements: list[str] = field(default_factory=list)


def fabriquer_compte_google(
    session: Session,
    cle: bytes,
    personne: Personne,
    *,
    ou: str,
    mode: str = "simulation",
) -> tuple[bytes, RapportCompte]:
    """Le CSV d'une ligne à importer dans la console, mot de passe compris.

    La création de compte passe par la console : l'API n'est pas utilisée
    ici. Le fichier porte donc l'unité d'organisation visée, pour que le
    compte y naisse plutôt que d'y être déplacé ensuite.

    Le mot de passe est fabriqué à la forme de ceux de KoXo — `Aaaaaa99` —
    et rangé au coffre **dans le même geste**. Un mot de passe fabriqué et
    non rangé serait perdu : personne d'autre ne le connaîtrait, et il
    faudrait réinitialiser le compte.
    """
    import csv
    import io

    from backend.services.coffre import deposer, fabriquer_mot_de_passe
    from backend.services.exports_google import COLONNES_GOOGLE

    if mode not in ("simulation", "reel"):
        raise ValueError(f"mode invalide : {mode!r}")
    if not cle:
        raise ArriveeImpossible(
            "Le coffre doit être ouvert : un mot de passe fabriqué et non "
            "rangé est un mot de passe perdu."
        )
    adresse = (personne.email or "").strip()
    if not adresse:
        raise ArriveeImpossible("Cette personne n'a pas d'adresse.")

    mdp = fabriquer_mot_de_passe()
    site = personne.site.nom if personne.site else None
    deposer(
        session, cle, personne_id=personne.id, mot_de_passe=mdp,
        cible="google", site=site, origine="genere",
    )

    ligne = {c: "" for c in COLONNES_GOOGLE}
    ligne["First Name [Required]"] = personne.prenom or ""
    ligne["Last Name [Required]"] = personne.nom or ""
    ligne["Email Address [Required]"] = adresse
    ligne["Password [Required]"] = mdp
    ligne["Org Unit Path [Required]"] = ou
    ligne["Employee ID"] = str(personne.id_charlemagne or "")
    ligne["Employee Type"] = "Student" if personne.type == "eleve" else "Staff"
    # Le mot de passe est celui du coffre et celui de la fiche remise : le
    # faire changer à la première connexion le ferait diverger des deux.
    ligne["Change Password at Next Sign-In"] = "False"

    buf = io.StringIO(newline="")
    w = csv.DictWriter(buf, fieldnames=COLONNES_GOOGLE, quoting=csv.QUOTE_MINIMAL)
    w.writeheader()
    w.writerow(ligne)
    contenu = buf.getvalue().encode("utf-8-sig")

    rapport = RapportCompte(
        email=adresse,
        ou_visee=ou,
        nom_fichier=f"Google_arrivee_{personne.login or personne.id}.csv",
        mot_de_passe_genere=True,
    )
    if not personne.id_charlemagne:
        rapport.avertissements.append(
            "Aucun identifiant Charlemagne : la colonne Employee ID reste "
            "vide, et la synchronisation KoXo ne reconnaîtra pas ce compte."
        )

    if mode == "reel":
        session.commit()
    else:
        session.rollback()
    return contenu, rapport


def ajouter_au_groupe(
    session: Session, personne: Personne, client, groupe: str
) -> str:
    """Fait entrer l'arrivant dans le groupe de sa classe.

    Séparé de la fabrication du compte, parce qu'entre les deux il y a un
    geste humain : l'import dans la console. Ajouter un membre qui n'existe
    pas encore échoue.

    Un groupe de classe est une liste de diffusion : y entrer, c'est
    apparaître aux yeux des autres. C'est pour ça que le choix reste
    ouvert, et que rien ne le fait d'office.
    """
    adresse = (personne.email or "").strip()
    if not adresse:
        raise ArriveeImpossible("Cette personne n'a pas d'adresse.")
    if not (groupe or "").strip():
        raise ArriveeImpossible("Aucun groupe à rejoindre.")

    deja = {m.lower() for m in client.lister_membres(groupe)}
    if adresse.lower() in deja:
        return f"{adresse} est déjà membre de {groupe}."
    client.ajouter_membre(groupe, adresse)
    return f"{adresse} a rejoint {groupe}."


def inscrire_au_tableau_chromebooks(
    session: Session,
    personne: Personne,
    *,
    annee_id: int,
    discipline: str | None = None,
    mode: str = "simulation",
) -> str:
    """Fait apparaître un adulte dans l'écran Chromebooks.

    Cet écran lit le tableau des enseignants, tenu à la main dans un
    classeur et importé une fois l'an. Une AESH qui prend son poste en
    novembre n'y figure pas, et l'écran ne peut donc pas lui attribuer de
    machine — alors que c'est précisément le moment où elle en a besoin.

    On l'y ajoute avec le code `arrivant`, celui-là même que l'import
    donne aux lignes bleues du classeur : l'écran la rangera parmi les
    personnes à équiper.
    """
    from backend.models import MouvementProf

    if mode not in ("simulation", "reel"):
        raise ValueError(f"mode invalide : {mode!r}")
    if personne.type != "adulte":
        raise ArriveeImpossible(
            "Le tableau des Chromebooks ne concerne que les adultes."
        )

    deja = (
        session.query(MouvementProf)
        .filter_by(annee_scolaire_id=annee_id, nom=personne.nom, prenom=personne.prenom)
        .first()
    )
    if deja is not None:
        message = f"{personne.prenom} {personne.nom} figure déjà au tableau."
    else:
        session.add(
            MouvementProf(
                annee_scolaire_id=annee_id,
                nom=personne.nom or "",
                prenom=personne.prenom or "",
                discipline=discipline or None,
                code="arrivant",
                libelle="Ajouté à la main — arrivée en cours d'année",
            )
        )
        message = (
            f"{personne.prenom} {personne.nom} est ajouté au tableau des "
            "Chromebooks, en attente d'une machine."
        )

    if mode == "reel":
        session.commit()
    else:
        session.rollback()
    return message
