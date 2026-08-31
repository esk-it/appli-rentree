"""Contrôle d'un export KoXo avant la synchronisation annuelle.

## Pourquoi ce contrôle existe

La synchronisation KoXo — la « bascule » — déplace les comptes existants
vers leur nouveau groupe secondaire et crée ceux qui manquent, en une
passe. Elle reconnaît un compte existant par son **ID unique** ; ce n'est
que si ce champ est vide qu'elle retombe sur la chaîne
`Nom + Prénom + Date de naissance`.

Or l'établissement ne renseigne pas la date de naissance. Le repli ne
distingue donc rien : un compte non reconnu par son ID unique est un
compte que la synchronisation peut recréer sous un autre login — ou, en
mode destructif, **supprimer**.

Le programme écrit toujours le badge Charlemagne dans l'`ID unique` de ses
exports, et sur ce point il est juste. Mais il n'avait jamais relu ce que
KoXo détient pour le confronter au référentiel. Les divergences
antérieures au programme lui restaient invisibles — celles-là mêmes qui
feront échouer la reconnaissance.

## Ce que le contrôle n'est pas

Il **n'écrit rien**. Ni dans le référentiel, ni dans KoXo. Il lit un export
et raconte ce qu'il voit. Aucun écart n'est corrigé automatiquement : un
`ID unique` erroné dans KoXo se répare dans KoXo, et le programme n'a
aucun moyen de savoir laquelle des deux valeurs fait foi.

## Le rapprochement, et pourquoi il refuse de trancher

Une ligne KoXo se rattache à une Personne de deux façons : par son
`ID unique` (= le badge) et par son `Identifiant` (= le login). Quand les
deux désignent la même personne, tout va bien. Quand ils désignent deux
personnes différentes, **le contrôle ne choisit pas** : il signale
l'ambiguïté.

Ce n'est pas de la prudence de principe. Une première version de ce
contrôle, écrite à la main, rapprochait par login seul et comparait
ensuite les badges. Elle a rapproché la ligne KoXo `cguivarch1`
(Camille GUIVARCH, professeure) de la Personne `cguivarch1` (Corentin
GUIVARCH, élève) et annoncé un écart de badge qui n'existait pas. Le
défaut n'était pas dans les données : il était dans le rapprochement
silencieux.
"""
from __future__ import annotations

import csv
import io
import unicodedata
from collections import defaultdict
from dataclasses import dataclass, field
from pathlib import Path

from sqlalchemy.orm import Session

from backend.models import Personne, Snapshot

# Libellés de colonnes acceptés, une fois normalisés (minuscules, sans accent).
COLONNES = {
    "groupe primaire": "groupe_primaire",
    "groupe secondaire": "groupe_secondaire",
    "nom": "nom",
    "prenom": "prenom",
    "identifiant": "login",
    "id unique": "id_unique",
    "badge": "id_unique",
    "email": "email",
    "titre": "titre",
    "mot de passe": "_motdepasse",
    "date de naissance": "date_naissance",
}

ENCODAGES = ("utf-8-sig", "utf-8", "cp1252")
SEPARATEURS = (";", ",", "\t")


def _plat(texte: str | None) -> str:
    """Minuscules, sans accent — pour comparer des libellés de colonnes."""
    decompose = unicodedata.normalize("NFD", (texte or "").strip().lower())
    return "".join(c for c in decompose if unicodedata.category(c) != "Mn")


def _cle_nom(prenom: str | None, nom: str | None) -> str:
    """Clé de rapprochement par identité, insensible aux espaces et accents.

    « LE SAOUT » et « LESAOUT » désignent la même famille selon la source :
    KoXo garde l'espace, les adresses le suppriment.
    """
    return _plat(prenom).replace(" ", "") + "|" + _plat(nom).replace(" ", "")


def _badge_propose(
    ligne: "LigneKoxo",
    par_nom: dict[str, list],
    par_login: dict[str, list],
) -> tuple[str, str]:
    """Quel badge devrait porter cette ligne KoXo, et ce qu'il faut en dire.

    **Le rapprochement se fait sur l'identité, jamais sur le login.** Une
    première version proposait le badge de la personne portant le même
    login au référentiel : pour Lana LE SAOUT, dont le login `llesaout`
    avait été réattribué à une homonyme entrante, elle proposait le badge
    de l'homonyme. Écrire ce numéro dans KoXo aurait fait répondre le
    compte de Lana au nom d'une autre.

    Renvoie `(badge, note)`. Badge vide quand plusieurs personnes portent
    ce nom : la note dit alors lesquelles.
    """
    candidats = par_nom.get(_cle_nom(ligne.prenom, ligne.nom)) or []
    if not candidats:
        return "", ""
    if len(candidats) > 1:
        qui = ", ".join(
            f"{p.prenom} {p.nom} (badge {p.badge})" for p in candidats[:4]
        )
        return "", (
            f"{len(candidats)} personnes portent ce nom au référentiel — "
            f"{qui}. Choisis toi-même le badge : le programme ne devine pas."
        )

    personne = candidats[0]
    badge = str(personne.badge) if personne.badge is not None else ""

    # Le login que KoXo donne à cette personne appartient-il à quelqu'un
    # d'autre au référentiel ? C'est le cas qui coûte le plus cher.
    note = ""
    autres = [p for p in (par_login.get(ligne.login) or []) if p.id != personne.id]
    if autres:
        a = autres[0]
        note = (
            f"Attention : le référentiel attribue l'identifiant "
            f"« {ligne.login} » à {a.prenom} {a.nom} (badge {a.badge}). "
            "Une fois l'ID unique corrigé, ré-amorce depuis KoXo pour que "
            "ce conflit d'identifiant soit tranché."
        )
    return badge, note


@dataclass
class LigneKoxo:
    """Une ligne de l'export, telle qu'elle est écrite.

    `id_unique` reste une **chaîne**. Le convertir en nombre dès la lecture
    ferait disparaître le cas qui compte le plus : un `ID unique` qui n'est
    pas un nombre du tout.
    """

    ligne: int
    nom: str = ""
    prenom: str = ""
    login: str = ""
    id_unique: str = ""
    groupe_primaire: str = ""
    groupe_secondaire: str = ""
    email: str = ""
    date_naissance: str = ""

    @property
    def nom_complet(self) -> str:
        return f"{self.prenom} {self.nom}".strip()


GENRES = (
    "id_absent",
    "id_non_numerique",
    "id_en_double",
    "login_en_double",
    "badge_inconnu",
    "login_divergent",
    "rapprochement_ambigu",
    "homonyme_autre_base",
    "absent_de_koxo",
)


@dataclass
class Ecart:
    genre: str
    """L'un des `GENRES`."""
    qui: str
    """Le nom, tel qu'il est écrit dans la source où l'écart apparaît."""
    login: str = ""
    id_unique: str = ""
    badge_referentiel: str = ""
    login_referentiel: str = ""
    lignes: list[int] = field(default_factory=list)
    explication: str = ""
    correction: str = ""
    """Le geste exact à faire dans KoXo, valeur comprise — « Mettre 81010
    dans l'ID unique », « Supprimer le compte llesaout2 ».

    Vide quand le programme ne peut pas désigner une correction sans
    deviner : deux homonymes, aucun rapprochement possible. La
    `consequence` dit alors quoi regarder.
    """
    consequence: str = ""
    """Ce que la synchronisation en fera si rien n'est corrigé."""


@dataclass
class RapportControle:
    fichier: str = ""
    type_personne: str = ""
    nb_lignes: int = 0
    nb_concordants: int = 0
    """Lignes dont l'ID unique et le login désignent la même Personne."""
    colonnes_lues: list[str] = field(default_factory=list)
    separateur: str = ""
    encodage: str = ""
    date_naissance_renseignee: int = 0
    """Combien de lignes portent une date de naissance. Zéro signifie que
    le repli de reconnaissance ne distinguera rien."""
    contient_mots_de_passe: bool = False
    """Un export KoXo peut contenir les mots de passe en clair. Le contrôle
    ne les lit pas et n'en garde rien ; il le signale pour que le fichier
    ne traîne pas."""
    ecarts: list[Ecart] = field(default_factory=list)
    avertissements: list[str] = field(default_factory=list)

    @property
    def nb_par_genre(self) -> dict[str, int]:
        compte: dict[str, int] = {}
        for e in self.ecarts:
            compte[e.genre] = compte.get(e.genre, 0) + 1
        return compte

    @property
    def est_sain(self) -> bool:
        """Aucun écart pouvant faire échouer une reconnaissance.

        Ni `absent_de_koxo` — un compte à créer est le déroulement normal
        d'une rentrée — ni `homonyme_autre_base`, qui constate une
        cohabitation légitime entre deux serveurs KoXo.
        """
        sans_objet = ("absent_de_koxo", "homonyme_autre_base")
        return not [e for e in self.ecarts if e.genre not in sans_objet]


# ---------------------------------------------------------------------------
# Lecture
# ---------------------------------------------------------------------------


def lire_export_brut(
    chemin: str | Path,
) -> tuple[list[LigneKoxo], list[str], str, str, bool]:
    """Lit l'export sans rien convertir.

    Renvoie les lignes, les colonnes reconnues, le séparateur, l'encodage
    retenus — ces trois derniers pour que l'écran puisse montrer comment le
    fichier a été compris, plutôt que de le laisser deviner — et si une
    colonne de mots de passe était présente.
    """
    chemin = Path(chemin)
    if not chemin.exists():
        raise ValueError(f"Fichier introuvable : {chemin}")

    brut = chemin.read_bytes()
    if not brut.strip():
        raise ValueError("Le fichier est vide.")

    meilleur: tuple[int, list[dict], list[str], str, str] | None = None
    for encodage in ENCODAGES:
        try:
            texte = brut.decode(encodage)
        except UnicodeDecodeError:
            continue
        for sep in SEPARATEURS:
            lecteur = csv.DictReader(io.StringIO(texte), delimiter=sep)
            entetes = lecteur.fieldnames or []
            reconnues = [c for c in entetes if _plat(c) in COLONNES]
            # Le bon séparateur est celui qui fait apparaître le plus de
            # colonnes connues : avec le mauvais, tout tient en une seule.
            if len(reconnues) < 3:
                continue
            lignes = list(lecteur)
            score = len(reconnues)
            if meilleur is None or score > meilleur[0]:
                meilleur = (score, lignes, entetes, sep, encodage)
        if meilleur is not None:
            break

    if meilleur is None:
        raise ValueError(
            "Format non reconnu. Un export KoXo doit porter au moins les "
            "colonnes Nom, Prénom, Identifiant et ID unique."
        )

    _, brutes, entetes, sep, encodage = meilleur
    correspondance = {c: COLONNES[_plat(c)] for c in entetes if _plat(c) in COLONNES}

    lignes: list[LigneKoxo] = []
    for i, ligne in enumerate(brutes, start=2):  # 1 = en-tête
        valeurs = {}
        for colonne, champ in correspondance.items():
            if champ.startswith("_"):
                continue
            valeurs[champ] = (ligne.get(colonne) or "").strip()
        if not valeurs.get("nom") and not valeurs.get("login"):
            continue  # ligne vide, ou pied de tableau
        valeurs.pop("titre", None)
        lignes.append(LigneKoxo(ligne=i, **valeurs))

    # Les colonnes internes (préfixe `_`) ne sont pas montrées : elles ne
    # sont pas lues. Le mot de passe est de celles-là.
    lues = sorted(v for v in set(correspondance.values()) if not v.startswith("_"))
    mots_de_passe = "_motdepasse" in correspondance.values()
    return lignes, lues, sep, encodage, mots_de_passe


# ---------------------------------------------------------------------------
# Contrôle
# ---------------------------------------------------------------------------


def controler_export_koxo(
    session: Session,
    chemin: str | Path,
    *,
    type_personne: str,
    site_id: int | None = None,
    annee_id: int | None = None,
) -> RapportControle:
    """Confronte un export KoXo au référentiel. N'écrit rien.

    Args:
        chemin: le fichier .csv exporté depuis KoXo.
        type_personne: `eleve` ou `adulte` — délimite la population du
            référentiel à laquelle l'export est comparé.
        site_id: restreint cette population à un site, si fourni.
        annee_id: restreint aux personnes présentes cette année-là. Sans
            cela, les sortants des années passées seraient comptés comme
            « absents de KoXo », ce qu'ils sont sans que ce soit un défaut.
    """
    if type_personne not in ("eleve", "adulte"):
        raise ValueError(f"type_personne invalide : {type_personne!r}")

    lignes, colonnes, sep, encodage, mots_de_passe = lire_export_brut(chemin)
    rapport = RapportControle(
        fichier=Path(chemin).name,
        type_personne=type_personne,
        nb_lignes=len(lignes),
        colonnes_lues=colonnes,
        separateur=sep,
        encodage=encodage,
        date_naissance_renseignee=sum(1 for l in lignes if l.date_naissance),
        contient_mots_de_passe=mots_de_passe,
    )

    if mots_de_passe:
        rapport.avertissements.append(
            "Ce fichier contient une colonne de mots de passe. Le contrôle ne "
            "la lit pas et n'en conserve rien — mais le fichier, lui, les "
            "porte en clair : efface-le une fois le contrôle passé."
        )

    if rapport.date_naissance_renseignee == 0:
        rapport.avertissements.append(
            "Aucune date de naissance n'est renseignée dans cet export. La "
            "reconnaissance ne peut donc reposer que sur l'ID unique : un "
            "compte dont l'ID unique est absent, erroné ou en double ne sera "
            "pas reconnu, et une synchronisation en mode destructif le "
            "supprimerait."
        )

    # --- La population du référentiel à laquelle on compare -----------------
    requete = session.query(Personne).filter(Personne.type == type_personne)
    if site_id is not None:
        requete = requete.filter(Personne.site_id == site_id)
    population = requete.all()
    if annee_id is not None:
        presents = {
            x.personne_id
            for x in session.query(Snapshot.personne_id).filter(
                Snapshot.annee_scolaire_id == annee_id
            )
        }
        population = [p for p in population if p.id in presents]

    if not population:
        # Un zéro tranquille se lit « rien ne manque à KoXo », alors qu'il
        # signifie « je n'ai comparé à rien ». Les adultes, par exemple,
        # n'ont pas de photographie annuelle : borner par année vide la
        # population et rend le contrôle muet dans ce sens.
        borne = []
        if site_id is not None:
            borne.append("ce site")
        if annee_id is not None:
            borne.append("cette année")
        rapport.avertissements.append(
            "Aucune personne du référentiel ne correspond à la population "
            f"demandée ({type_personne}"
            + (" / " + " / ".join(borne) if borne else "")
            + "). Les comptes KoXo restent contrôlés, mais rien ne peut être "
            "dit de ce qui manque à KoXo — élargis l'année ou le site pour "
            "obtenir cette moitié du contrôle."
        )

    # Les index de rapprochement portent sur **tout** le référentiel, pas sur
    # la seule population comparée : une ligne KoXo qui tombe sur un élève
    # d'un autre site doit être reconnue comme telle, pas déclarée inconnue.
    tous = session.query(Personne).all()
    par_badge: dict[int, list[Personne]] = defaultdict(list)
    par_login: dict[str, list[Personne]] = defaultdict(list)
    par_nom: dict[str, list[Personne]] = defaultdict(list)
    # Ce que les bases KoXo déjà lues détiennent : (identifiant, badge).
    # C'est ce qui distingue un homonyme légitime d'une usurpation.
    from backend.models import LoginReserve

    constats = {
        (r.login, r.badge)
        for r in session.query(LoginReserve).all()
        if r.badge is not None
    }
    for p in tous:
        if p.badge is not None:
            par_badge[p.badge].append(p)
        if p.login:
            par_login[p.login].append(p)
        par_nom[_cle_nom(p.prenom, p.nom)].append(p)

    # --- Doublons internes à l'export ---------------------------------------
    lignes_par_id: dict[str, list[LigneKoxo]] = defaultdict(list)
    lignes_par_login: dict[str, list[LigneKoxo]] = defaultdict(list)
    for l in lignes:
        if l.id_unique:
            lignes_par_id[l.id_unique].append(l)
        if l.login:
            lignes_par_login[l.login].append(l)

    ids_en_double = {k for k, v in lignes_par_id.items() if len(v) > 1}
    for ident in sorted(ids_en_double):
        groupe = lignes_par_id[ident]

        # Lequel garder ? Celui dont l'identifiant est aussi celui que le
        # référentiel connaît pour ce badge : c'est le compte historique,
        # et un identifiant constaté ne se remplace pas.
        correction = ""
        titulaire = None
        if ident.isdigit():
            candidats = par_badge.get(int(ident)) or []
            titulaire = candidats[0] if len(candidats) == 1 else None
        if titulaire is not None and titulaire.login:
            a_garder = [l for l in groupe if l.login == titulaire.login]
            a_supprimer = [l for l in groupe if l.login != titulaire.login]
            if a_garder and a_supprimer:
                # Désactiver plutôt que supprimer garde les données, et
                # suffit quand l'export KoXo exclut les comptes désactivés —
                # c'est le réglage en place ici. Un compte désactivé porte
                # toujours son ID unique : ce qui lève l'ambiguïté n'est pas
                # la désactivation, c'est son absence de l'export. D'où la
                # vérification, qui ne coûte qu'un aller-retour.
                correction = (
                    "Désactiver "
                    + ", ".join(f"« {l.login} »" for l in a_supprimer)
                    + f", et garder « {titulaire.login} ». Puis ré-exporter en "
                    "excluant les comptes désactivés et repasser ce contrôle : "
                    "l'écart doit avoir disparu."
                )

        rapport.ecarts.append(
            Ecart(
                genre="id_en_double",
                qui=" / ".join(sorted({l.nom_complet for l in groupe})),
                id_unique=ident,
                login=", ".join(l.login for l in groupe),
                login_referentiel=(titulaire.login if titulaire else ""),
                lignes=[l.ligne for l in groupe],
                explication=(
                    f"{len(groupe)} comptes KoXo portent l'ID unique {ident} : "
                    + ", ".join(l.login for l in groupe)
                ),
                correction=correction,
                consequence=(
                    "La synchronisation ne peut pas savoir lequel mettre à jour."
                    if correction
                    else (
                        "La synchronisation ne peut pas savoir lequel mettre à "
                        "jour. Aucun de ces identifiants n'est celui que le "
                        "référentiel connaît pour ce badge : regarde dans KoXo "
                        "lequel est réellement utilisé."
                    )
                ),
            )
        )

    for login, groupe in sorted(lignes_par_login.items()):
        if len(groupe) > 1:
            rapport.ecarts.append(
                Ecart(
                    genre="login_en_double",
                    qui=" / ".join(sorted({l.nom_complet for l in groupe})),
                    login=login,
                    lignes=[l.ligne for l in groupe],
                    explication=f"L'identifiant {login} apparaît {len(groupe)} fois.",
                    consequence="Deux comptes ne peuvent pas porter le même identifiant.",
                )
            )

    # --- Ligne à ligne -------------------------------------------------------
    badges_vus: set[int] = set()
    for l in lignes:
        if not l.id_unique:
            badge, note = _badge_propose(l, par_nom, par_login)
            rapport.ecarts.append(
                Ecart(
                    genre="id_absent",
                    qui=l.nom_complet,
                    login=l.login,
                    badge_referentiel=badge,
                    lignes=[l.ligne],
                    explication="Ce compte KoXo n'a pas d'ID unique.",
                    correction=(
                        f"Mettre {badge} dans l'ID unique du compte "
                        f"« {l.login} »."
                        if badge
                        else ""
                    ),
                    consequence=(
                        note
                        or "La reconnaissance retombera sur Nom + Prénom + date "
                        "de naissance. Sans date, elle ne distingue pas les "
                        "homonymes."
                    ),
                )
            )
            continue

        if not l.id_unique.isdigit():
            badge, note = _badge_propose(l, par_nom, par_login)
            rapport.ecarts.append(
                Ecart(
                    genre="id_non_numerique",
                    qui=l.nom_complet,
                    login=l.login,
                    id_unique=l.id_unique,
                    badge_referentiel=badge,
                    lignes=[l.ligne],
                    explication=(
                        f"L'ID unique vaut « {l.id_unique} », qui n'est pas un "
                        "numéro de badge."
                    ),
                    correction=(
                        f"Remplacer « {l.id_unique} » par {badge} dans l'ID "
                        f"unique du compte « {l.login} »."
                        if badge
                        else ""
                    ),
                    consequence=(
                        note
                        or "Ce compte ne sera pas reconnu par son ID unique. "
                        "Corrige-le dans KoXo avant la synchronisation."
                    ),
                )
            )
            continue

        badge = int(l.id_unique)
        badges_vus.add(badge)
        par_id = par_badge.get(badge) or []
        par_ident = par_login.get(l.login) or []

        if not par_id:
            rapport.ecarts.append(
                Ecart(
                    genre="badge_inconnu",
                    qui=l.nom_complet,
                    login=l.login,
                    id_unique=l.id_unique,
                    lignes=[l.ligne],
                    explication=(
                        f"Aucune personne du référentiel ne porte le badge {badge}."
                    ),
                    consequence=(
                        "Aucune ligne de l'export ne s'adressera à ce compte. "
                        "En mode destructif, il serait supprimé."
                    ),
                )
            )
            continue

        personne = par_id[0]

        # Le badge désigne quelqu'un, le login quelqu'un d'autre : on ne
        # tranche pas — c'est exactement l'erreur que ce contrôle existe
        # pour ne plus commettre.
        if par_ident and all(p.id != personne.id for p in par_ident):
            autre = par_ident[0]

            # L'établissement tient un serveur KoXo par site. Quand une
            # autre base attribue déjà cet identifiant à la personne que le
            # référentiel désigne, les deux sont légitimes chacun chez soi :
            # ce sont des homonymes, souvent des fratries. Le référentiel
            # n'en garde qu'un et suffixe l'autre. Rien à corriger — et
            # l'afficher en rouge noierait le seul cas qui, lui, en demande.
            if (l.login, autre.badge) in constats:
                rapport.ecarts.append(
                    Ecart(
                        genre="homonyme_autre_base",
                        qui=l.nom_complet,
                        login=l.login,
                        id_unique=l.id_unique,
                        badge_referentiel=str(personne.badge),
                        login_referentiel=personne.login or "",
                        lignes=[l.ligne],
                        explication=(
                            f"« {l.login} » est aussi détenu par {autre.prenom} "
                            f"{autre.nom} (badge {autre.badge}) dans une autre "
                            "base KoXo. Les deux sont légitimes, chacun chez "
                            "soi."
                        ),
                        consequence=(
                            "Le référentiel ne garde qu'un identifiant par "
                            f"personne : il a suffixé celui de {personne.prenom} "
                            f"{personne.nom} en « {personne.login} ». La "
                            "synchronisation reconnaîtra ce compte par son ID "
                            "unique — rien à faire."
                        ),
                    )
                )
                rapport.nb_concordants += 1
                continue

            rapport.ecarts.append(
                Ecart(
                    genre="rapprochement_ambigu",
                    qui=l.nom_complet,
                    login=l.login,
                    id_unique=l.id_unique,
                    badge_referentiel=str(personne.badge),
                    login_referentiel=personne.login or "",
                    lignes=[l.ligne],
                    explication=(
                        f"KoXo détient l'identifiant « {l.login} » pour ce "
                        f"compte, dont l'ID unique {badge} désigne "
                        f"{personne.prenom} {personne.nom} au référentiel. Or "
                        f"le référentiel attribue « {l.login} » à "
                        f"{autre.prenom} {autre.nom} ({autre.type})."
                    ),
                    consequence=(
                        # La formulation compte : présentés symétriquement, les
                        # deux côtés donnent à croire que le programme sait
                        # quelque chose de l'autre personne. Il ne sait rien
                        # d'elle — il lui a calculé cet identifiant parce
                        # qu'aucune Personne ne le portait encore.
                        "Un identifiant détenu dans KoXo a été constaté ; celui "
                        "du référentiel a pu être calculé faute de mieux. Le "
                        "programme ne tranche pas de lui-même : vérifie de qui "
                        f"ce compte est celui, et si c'est {personne.prenom} "
                        f"{personne.nom}, c'est l'attribution à "
                        f"{autre.prenom} {autre.nom} qui est à revoir."
                    ),
                )
            )
            continue

        if personne.login and personne.login != l.login:
            rapport.ecarts.append(
                Ecart(
                    genre="login_divergent",
                    qui=l.nom_complet,
                    login=l.login,
                    id_unique=l.id_unique,
                    badge_referentiel=str(personne.badge),
                    login_referentiel=personne.login,
                    lignes=[l.ligne],
                    explication=(
                        f"KoXo connaît ce badge sous l'identifiant {l.login}, "
                        f"le référentiel sous {personne.login}."
                    ),
                    consequence=(
                        "L'export écrirait un identifiant que KoXo ne porte "
                        "pas. Un identifiant constaté fait autorité : c'est "
                        "le référentiel qu'il faut aligner."
                    ),
                )
            )
            continue

        rapport.nb_concordants += 1

    # --- L'autre sens : qui manque à KoXo ------------------------------------
    for p in population:
        if p.badge is not None and p.badge not in badges_vus:
            rapport.ecarts.append(
                Ecart(
                    genre="absent_de_koxo",
                    qui=f"{p.prenom} {p.nom}",
                    login=p.login or "",
                    badge_referentiel=str(p.badge),
                    explication="Aucun compte KoXo ne porte ce badge.",
                    consequence="La synchronisation créera le compte.",
                )
            )

    return rapport


def retenir_identifiants_constates(
    session: Session, chemin: str | Path, site: str | None = None
) -> int:
    """Retient les identifiants d'un export, avec l'ID unique qui va avec.

    Le contrôle lui-même ne modifie rien. Ceci est autre chose : garder
    trace de ce qu'une source **détient**, pour ne plus attribuer ces
    identifiants à quelqu'un d'autre, et pour reconnaître le cas où deux
    bases KoXo en attribuent un chacune de leur côté.

    L'établissement tient un serveur KoXo par site. Un frère au lycée et
    une sœur au collège portent légitimement `lbernard` chacun dans sa
    base ; le référentiel n'en garde qu'un. Sans cette mémoire, le second
    contrôle prend le premier pour une erreur à corriger — et la
    correction casserait l'autre.

    Renvoie le nombre d'identifiants retenus.
    """
    from backend.models import LoginReserve

    lignes, _, _, _, _ = lire_export_brut(chemin)
    # Un seul aller-retour pour l'existant : interroger ligne par ligne
    # manquerait de toute façon les insertions encore en attente de flush,
    # et deux exports partagent des identifiants.
    # La clé porte le site : les professeurs existent dans les deux bases,
    # et chacune doit pouvoir tenir son propre constat.
    deja = {
        (r.login, r.badge, r.site): r for r in session.query(LoginReserve).all()
    }
    retenus = 0
    for l in lignes:
        if not l.login:
            continue
        badge = int(l.id_unique) if l.id_unique.isdigit() else None
        if badge is None:
            continue  # sans ID unique, la source ne dit pas de qui il s'agit
        # On retient **toutes** les lignes, y compris celles qui concordent :
        # c'est précisément le constat « cet identifiant appartient à ce
        # badge dans cette base » qui permettra, en lisant l'autre base, de
        # reconnaître un homonyme légitime plutôt qu'une usurpation.
        existante = deja.get((l.login, badge, site))
        if existante is None:
            nouvelle = LoginReserve(
                login=l.login, source="controle_koxo", badge=badge,
                site=site, nom=l.nom, prenom=l.prenom,
                groupe_secondaire=l.groupe_secondaire or None,
                groupe_primaire=(l.groupe_primaire or "").strip() or None,
                email=(l.email or "").strip() or None,
                motif="identifiant détenu dans un export KoXo",
            )
            session.add(nouvelle)
            deja[(l.login, badge, site)] = nouvelle
        else:
            existante.nom, existante.prenom = l.nom, l.prenom
            existante.source = "controle_koxo"
            existante.groupe_secondaire = (
                l.groupe_secondaire or existante.groupe_secondaire
            )
            # L'adresse que la base détient est un constat : elle prime sur
            # celle que le programme sait calculer, et il la jetait.
            existante.email = (l.email or "").strip() or existante.email
            existante.groupe_primaire = (
                (l.groupe_primaire or "").strip() or existante.groupe_primaire
            )
        retenus += 1

    session.flush()
    return retenus
