"""L'état des liens entre le référentiel et les autres systèmes.

Le référentiel est au centre. Chaque autre système en est un satellite, et
le lien qui les joint vaut ce que vaut la dernière comparaison : *cohérent*
si elle n'a rien trouvé, *en écart* si elle a trouvé quelque chose, *pas
encore vérifié* si elle n'a jamais tourné.

Ce module ne compare rien. Il **range** ce que la Concordance a constaté,
et le rend sous deux formes :

- par système, pour l'écran Cohérence, qui dessine les liens ;
- par personne, pour la colonne « Cohérent » du référentiel.

## Les trois systèmes sans source

PMB, Sodexo et CardStudio reçoivent des fichiers du programme et n'en
rendent aucun. Leur lien ne peut pas être vérifié — pas parce que
personne n'a pris le temps, mais parce qu'il n'y a rien à lire. L'écran
les montre quand même, en pointillé : un lien qu'on ne sait pas vérifier
reste un lien, et le cacher ferait croire que l'école tient en quatre
systèmes.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime

from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from backend.models import Personne, VerdictCoherence
from backend.models.verdict_coherence import SYSTEMES_COMPARES

# ---------------------------------------------------------------------------
# Ce qu'un genre d'écart dit, et de quel lien il parle
# ---------------------------------------------------------------------------

GENRE_VERS_SYSTEME: dict[str, tuple[str, str]] = {
    # genre                     -> (système, état)
    "referentiel": ("charlemagne", "ecart"),
    "google": ("google", "ecart"),
    "groupe": ("google", "ecart"),
    "hors_arbre_de_classe": ("google", "ecart"),
    "sans_compte": ("google", "absent"),
    "koxo": ("koxo", "ecart"),
    "absent_koxo": ("koxo", "absent"),
}
"""`absent_referentiel` n'y figure pas : la personne n'a pas d'identité
dans le référentiel, donc aucune ligne à rattacher. Elle se règle par une
ingestion, pas par un verdict."""

LIBELLE_SYSTEME = {
    "charlemagne": "Charlemagne",
    "google": "Google Workspace",
    "koxo": "KoXo",
    "pmb": "PMB",
    "sodexo": "Sodexo",
    "cardstudio": "CardStudio",
}

SANS_SOURCE = ("pmb", "sodexo", "cardstudio")
"""Le programme leur écrit ; ils ne lui répondent pas. Voir l'en-tête."""

POURQUOI_SANS_SOURCE = {
    "pmb": "Le programme produit le fichier d'import PMB. PMB n'exporte "
           "rien qui revienne ici : le lien ne peut pas être vérifié.",
    "sodexo": "Les comptes partent par le classeur SoHappy. Rien n'en "
              "revient : la comparaison demanderait un export Sodexo.",
    "cardstudio": "Les cartes sont produites depuis un fichier. CardStudio "
                  "ne rend pas la liste de ce qu'il a imprimé.",
}


@dataclass
class EtatLien:
    """Un lien du schéma : le référentiel vers un système."""

    systeme: str
    libelle: str
    etat: str
    """`coherent` · `ecarts` · `non_verifie` · `sans_source`."""
    nb_ecarts: int = 0
    nb_absents: int = 0
    nb_verifies: int = 0
    verifie_le: datetime | None = None
    pourquoi: str | None = None
    """Pour les liens sans source, ce qui empêche de les vérifier."""
    details: list[dict] = field(default_factory=list)
    """Les écarts regroupés par genre, du plus nombreux au moins."""


# ---------------------------------------------------------------------------
# Écrire
# ---------------------------------------------------------------------------


def enregistrer(session: Session, rapport) -> int:
    """Range les constats d'un croisement, système par système.

    Seuls les systèmes que ce croisement a **consultés** sont réécrits :
    un croisement sans export KoXo ne sait rien de KoXo, et effacer ce
    que le croisement d'hier en savait remplacerait une information
    datée par rien du tout.

    Rend le nombre de verdicts écrits.
    """
    consultes = ["charlemagne"]
    if getattr(rapport, "google_consulte", False):
        consultes.append("google")
    if getattr(rapport, "koxo_fourni", False):
        consultes.append("koxo")

    quand = datetime.utcnow()
    ecrits = 0

    # Table des lignes à écrire, indexée par (personne, système) : une
    # personne peut porter deux genres pour un même système — l'unité et
    # le groupe, par exemple — et c'est un seul lien en écart.
    a_ecrire: dict[tuple[int, str], dict] = {}

    for ligne in rapport.lignes:
        pid = ligne.personne_id
        if pid is None:
            continue

        # Par défaut, tout système consulté est d'accord. On ne peut le
        # dire que des systèmes réellement regardés pour cette ligne :
        # KoXo a une base par établissement, et `koxo_consulte` dit si
        # celle de cet élève était du lot.
        for systeme in consultes:
            if systeme == "koxo" and not ligne.koxo_consulte:
                continue
            a_ecrire[(pid, systeme)] = {
                "etat": "accord",
                "genre": None,
                "attendu": ligne.referentiel,
                "constate": _constate(ligne, systeme),
            }

        for genre in ligne.genres:
            cible = GENRE_VERS_SYSTEME.get(genre)
            if cible is None:
                continue
            systeme, etat = cible
            if systeme not in consultes:
                continue
            courant = a_ecrire.get((pid, systeme))
            # « absent » l'emporte sur « écart » : une personne sans
            # compte n'a pas une classe fausse, elle n'en a pas.
            if courant and courant["etat"] == "absent":
                continue
            a_ecrire[(pid, systeme)] = {
                "etat": etat,
                "genre": genre,
                "attendu": ligne.referentiel,
                "constate": _constate(ligne, systeme),
            }

    if not a_ecrire:
        return 0

    # Les verdicts de ces personnes pour ces systèmes, remplacés d'un
    # bloc : une ligne devenue cohérente doit cesser d'être en écart.
    ids = {pid for pid, _ in a_ecrire}
    session.execute(
        delete(VerdictCoherence)
        .where(VerdictCoherence.personne_id.in_(ids))
        .where(VerdictCoherence.systeme.in_(consultes))
    )

    for (pid, systeme), v in a_ecrire.items():
        session.add(
            VerdictCoherence(
                personne_id=pid,
                systeme=systeme,
                etat=v["etat"],
                genre=v["genre"],
                attendu=v["attendu"],
                constate=v["constate"],
                verifie_le=quand,
            )
        )
        ecrits += 1

    session.commit()
    return ecrits


def _constate(ligne, systeme: str) -> str | None:
    """Ce que ce système dit de la classe, tel qu'on l'affichera."""
    if systeme == "charlemagne":
        return ligne.charlemagne
    if systeme == "google":
        return ligne.google_classe or (ligne.google_ou and "hors classe") or None
    if systeme == "koxo":
        return ligne.koxo
    return None


# ---------------------------------------------------------------------------
# Lire
# ---------------------------------------------------------------------------


def etat_des_liens(session: Session) -> list[EtatLien]:
    """Un état par système, dans l'ordre du schéma.

    Les six sont rendus, y compris ceux qu'aucun export ne renseigne :
    l'écran doit pouvoir dire *pourquoi* un lien est gris, et « pas de
    source » n'est pas « pas encore fait ».
    """
    liens: list[EtatLien] = []

    for systeme in SYSTEMES_COMPARES:
        lignes = (
            session.execute(
                select(VerdictCoherence).where(VerdictCoherence.systeme == systeme)
            )
            .scalars()
            .all()
        )
        if not lignes:
            liens.append(
                EtatLien(
                    systeme=systeme,
                    libelle=LIBELLE_SYSTEME[systeme],
                    etat="non_verifie",
                    pourquoi="Aucun croisement n'a encore comparé ce système.",
                )
            )
            continue

        par_genre: dict[str, int] = {}
        nb_ecarts = nb_absents = 0
        for v in lignes:
            if v.etat == "ecart":
                nb_ecarts += 1
            elif v.etat == "absent":
                nb_absents += 1
            if v.genre:
                par_genre[v.genre] = par_genre.get(v.genre, 0) + 1

        liens.append(
            EtatLien(
                systeme=systeme,
                libelle=LIBELLE_SYSTEME[systeme],
                etat="ecarts" if (nb_ecarts or nb_absents) else "coherent",
                nb_ecarts=nb_ecarts,
                nb_absents=nb_absents,
                nb_verifies=len(lignes),
                verifie_le=max(v.verifie_le for v in lignes),
                details=[
                    {"genre": g, "nb": n}
                    for g, n in sorted(par_genre.items(), key=lambda x: -x[1])
                ],
            )
        )

    for systeme in SANS_SOURCE:
        liens.append(
            EtatLien(
                systeme=systeme,
                libelle=LIBELLE_SYSTEME[systeme],
                etat="sans_source",
                pourquoi=POURQUOI_SANS_SOURCE[systeme],
            )
        )

    return liens


def verdicts_par_personne(
    session: Session, personne_ids: list[int] | None = None
) -> dict[int, dict]:
    """Pour chaque personne, ce que les croisements ont constaté d'elle.

    Rend `{id: {"etat": …, "systemes": [...], "verifie_le": …}}`, où
    l'état vaut `coherent` quand tous les systèmes vérifiés sont
    d'accord. Une personne absente du dictionnaire n'a jamais été
    croisée — et la liste écrira « Pas vérifié » plutôt que de la
    déclarer cohérente sans l'avoir regardée.
    """
    requete = select(VerdictCoherence)
    if personne_ids is not None:
        if not personne_ids:
            return {}
        requete = requete.where(VerdictCoherence.personne_id.in_(personne_ids))

    par_personne: dict[int, dict] = {}
    for v in session.execute(requete).scalars():
        entree = par_personne.setdefault(
            v.personne_id,
            {"etat": "coherent", "systemes": [], "verifie_le": v.verifie_le},
        )
        entree["systemes"].append(
            {
                "systeme": v.systeme,
                "etat": v.etat,
                "genre": v.genre,
                "attendu": v.attendu,
                "constate": v.constate,
            }
        )
        if v.etat != "accord":
            entree["etat"] = "ecarts"
        if v.verifie_le > entree["verifie_le"]:
            entree["verifie_le"] = v.verifie_le

    return par_personne


def compter(session: Session) -> dict:
    """Le bandeau de l'écran : combien de personnes, combien vérifiées."""
    total = session.query(Personne).count()
    eleves = session.query(Personne).filter(Personne.type == "eleve").count()
    verifiees = (
        session.query(VerdictCoherence.personne_id).distinct().count()
    )
    return {
        "nb_personnes": total,
        "nb_eleves": eleves,
        "nb_adultes": total - eleves,
        "nb_verifiees": verifiees,
    }


# ---------------------------------------------------------------------------
# L'autre source de verdicts : le bilan, qui n'a pas besoin de Charlemagne
# ---------------------------------------------------------------------------

GENRE_BILAN = {
    # genre du bilan         -> état du lien vers Google
    "compte_absent": "absent",
    "compte_suspendu": "ecart",
    "ou_inattendue": "ecart",
    "groupe_manquant": "ecart",
    "groupe_en_trop": "ecart",
    "identifiant_discordant": "ecart",
    "sortant_dans_arbre_actif": "ecart",
}
"""`sans_classe` n'y figure pas : c'est un trou du référentiel, pas un
désaccord avec Google. L'y ranger accuserait Google de ne pas savoir une
chose que personne ne lui a dite."""


def enregistrer_bilan(session: Session, bilan) -> int:
    """Range ce qu'un bilan a constaté du lien vers Google.

    ## Pourquoi une seconde porte

    La Concordance croise quatre sources et demande pour cela un export
    Charlemagne frais. Le bilan, lui, confronte le référentiel à Google
    et **n'a besoin d'aucun fichier** : les deux côtés sont déjà là.

    C'est la question du matin — « est-ce que tout le monde est en
    place » — et elle ne devrait pas attendre qu'on ait exporté
    Charlemagne. Le lien vers Google se vérifie donc des deux façons, et
    la plus récente fait foi.

    Seules les personnes que ce bilan a **regardées** sont réécrites : un
    bilan filtré sur un site n'a rien vu des deux autres, et les déclarer
    cohérents serait le mensonge que ce verdict existe pour empêcher.

    Rend le nombre de verdicts écrits.
    """
    examinees = list(dict.fromkeys(bilan.personnes_examinees))
    if not examinees:
        return 0

    quand = datetime.utcnow()
    etats: dict[int, dict] = {
        pid: {"etat": "accord", "genre": None} for pid in examinees
    }

    for c in bilan.constats:
        etat = GENRE_BILAN.get(c.genre)
        if etat is None or c.personne_id is None:
            continue
        courant = etats.get(c.personne_id)
        if courant is None:
            continue  # un constat sur quelqu'un hors du champ examiné
        # « absent » l'emporte : sans compte, il n'y a pas d'unité fausse.
        if courant["etat"] == "absent":
            continue
        etats[c.personne_id] = {"etat": etat, "genre": c.genre}

    session.execute(
        delete(VerdictCoherence)
        .where(VerdictCoherence.personne_id.in_(examinees))
        .where(VerdictCoherence.systeme == "google")
    )
    for pid, v in etats.items():
        session.add(
            VerdictCoherence(
                personne_id=pid,
                systeme="google",
                etat=v["etat"],
                genre=v["genre"],
                verifie_le=quand,
            )
        )
    session.commit()
    return len(etats)
