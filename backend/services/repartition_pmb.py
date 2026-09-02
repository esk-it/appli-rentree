"""L'export PMB : répartir le fichier de Charlemagne, pas le fabriquer.

## Pourquoi le programme ne fabrique pas ce fichier

PMB veut treize colonnes :

    Num Badge ; Nom ; Prénom ; Adresse 1 ; Adresse 2 ; CP ; Ville ;
    Tél. domicile (avec LR) ; Année de naissance ; Code classe ; Sexe ;
    Email ; Prof. Princ.

Sept d'entre elles — adresse, complément, code postal, ville, téléphone,
année de naissance, sexe — ne sont **nulle part** dans le référentiel, et
pas davantage dans l'export Charlemagne que le programme ingère (douze
colonnes : établissement, niveau, classe, badge, régime, nom, prénom,
photo, drapeau « nouvel élève », date d'entrée). Le programme ne peut donc
pas les produire.

La version précédente essayait quand même, avec six colonnes de son cru
(`login;nom;prenom;classe;email;statut`). PMB n'en voulait pas. Un export
qui rend un fichier refusé est pire que pas d'export : on croit avoir
avancé.

Charlemagne, lui, sait écrire ce fichier — c'est un export dédié. C'est de
là qu'il doit venir.

## Ce que le programme apporte, et que Charlemagne ne sait pas

**Quel code classe appartient à quel établissement.** L'export de
Charlemagne porte les trois sites en vrac ; PMB a une instance par
établissement. Importer le fichier entier dans l'instance du lycée y fait
entrer les classes du collège — c'est arrivé, et la documentaliste a vu
ses effectifs doubler.

La table de correspondance sait, elle, que « 35 » est au collège et
« T_STMG2 » au lycée. Toute la répartition tient à cela.

## Ce que la répartition ne touche pas

Rien du contenu. Chaque ligne est réémise **telle quelle** — mêmes
colonnes, même ordre, mêmes valeurs, même la colonne `Prof. Princ.` dont
PMB fait ce qu'il veut. Le seul geste est de choisir dans quel fichier la
ligne tombe. C'est ce qui rend le résultat vérifiable : la somme des
fichiers produits vaut le fichier d'origine, aux lignes écartées près.

## Les deux listes que la répartition rend en plus

- **Écartées** : les lignes dont le code classe n'est dans aucune table.
  Elles ne sont dans aucun fichier, et il faut le savoir — sans quoi un
  élève disparaît sans bruit.
- **Inconnus du référentiel** : présents dans Charlemagne, jamais ingérés
  ici. Ils entreront bien dans PMB, mais n'ont ni compte Google ni compte
  KoXo, et aucun écran ne les montre. C'est ce contrôle qui en a trouvé
  quatre à la rentrée 2026.
"""
from __future__ import annotations

from dataclasses import dataclass, field

from sqlalchemy.orm import Session

from backend.models import Personne, Site, TableCorrespondance
from backend.services.csv_charlemagne import (
    BOM_UTF8,
    champs as _champs,
    decoder as _decoder,
    lignes_du_fichier as _lignes,
    lire,
)

COLONNES_REQUISES = ("Num Badge", "Code classe")
"""Le strict nécessaire pour répartir. Les onze autres passent sans être lues."""


class RepartitionImpossible(Exception):
    """La répartition est refusée, et le message dit pourquoi."""


@dataclass
class LigneEcartee:
    """Une ligne qu'aucun fichier n'a prise, ou qui mérite un mot."""

    badge: str
    nom: str
    prenom: str
    code_classe: str
    motif: str


@dataclass
class PaquetSite:
    """Le fichier d'une instance PMB."""

    site_nom: str
    nom_fichier: str
    nb_eleves: int
    classes: list[str]
    contenu_csv: bytes = b""


@dataclass
class _Reperes:
    """Où lire, dans une ligne, ce qu'il faut pour la ranger et la nommer.

    Seules `badge` et `classe` sont sûres d'exister : l'en-tête est
    contrôlé pour elles. `nom` et `prenom` ne servent qu'à rendre les
    listes lisibles, et le fichier peut à la rigueur s'en passer.
    """

    badge: int
    classe: int
    nom: int | None
    prenom: int | None


@dataclass
class RapportRepartition:
    nb_lignes_lues: int = 0
    paquets: list[PaquetSite] = field(default_factory=list)
    ecartees: list[LigneEcartee] = field(default_factory=list)
    inconnus_du_referentiel: list[LigneEcartee] = field(default_factory=list)

    @property
    def nb_reparties(self) -> int:
        return sum(p.nb_eleves for p in self.paquets)

    @property
    def tout_est_place(self) -> bool:
        return not self.ecartees


def repartir_export_pmb(
    session: Session, contenu: bytes, *, annee_libelle: str
) -> RapportRepartition:
    """Coupe l'export PMB de Charlemagne en un fichier par instance PMB.

    Args:
        contenu: le fichier tel que Charlemagne l'a écrit.
        annee_libelle: sert à nommer les fichiers produits.

    Raises:
        RepartitionImpossible: fichier vide, ou dont l'en-tête n'est pas
            celui de l'export PMB.
    """
    lignes = _lignes(_decoder(contenu))
    if not lignes:
        raise RepartitionImpossible("Le fichier est vide.")

    entete = _champs(lignes[0])
    manquantes = [c for c in COLONNES_REQUISES if c not in entete]
    if manquantes:
        raise RepartitionImpossible(
            "Ce n'est pas l'export PMB de Charlemagne : il y manque "
            + " et ".join(f"« {c} »" for c in manquantes)
            + ". L'en-tête lu commence par : "
            + ", ".join(entete[:4] or ["(rien)"])
            + "."
        )

    reperes = _Reperes(
        badge=entete.index("Num Badge"),
        classe=entete.index("Code classe"),
        nom=entete.index("Nom") if "Nom" in entete else None,
        prenom=entete.index("Prénom") if "Prénom" in entete else None,
    )
    sites_par_code = _sites_par_code(session)
    badges_connus = _badges_connus(session)

    rapport = RapportRepartition()
    corps_par_site: dict[str, list[str]] = {}
    classes_par_site: dict[str, set[str]] = {}

    for brute in lignes[1:]:
        if not brute.strip():
            continue
        rapport.nb_lignes_lues += 1
        champs = _champs(brute)

        if len(champs) != len(entete):
            rapport.ecartees.append(
                _ecart(champs, reperes, f"{len(champs)} colonnes au lieu de {len(entete)}")
            )
            continue

        code = champs[reperes.classe].strip()
        site_nom = sites_par_code.get(code.upper())
        if site_nom is None:
            rapport.ecartees.append(
                _ecart(
                    champs, reperes,
                    "aucune classe dans le fichier"
                    if not code
                    else f"classe « {code} » absente de la table de correspondance",
                )
            )
            continue

        corps_par_site.setdefault(site_nom, []).append(brute)
        classes_par_site.setdefault(site_nom, set()).add(code)

        badge = champs[reperes.badge].strip()
        if badge and badge not in badges_connus:
            rapport.inconnus_du_referentiel.append(
                _ecart(champs, reperes, "jamais ingéré ici — ni compte Google, ni compte KoXo")
            )

    for site_nom in sorted(corps_par_site):
        corps = corps_par_site[site_nom]
        rapport.paquets.append(
            PaquetSite(
                site_nom=site_nom,
                nom_fichier=f"PMB_{site_nom}_{annee_libelle}.csv",
                nb_eleves=len(corps),
                classes=sorted(classes_par_site[site_nom]),
                contenu_csv=_encoder([lignes[0], *corps]),
            )
        )
    return rapport


# ---------------------------------------------------------------------------
# Lecture et écriture
# ---------------------------------------------------------------------------


def _ecart(champs: list[str], reperes: _Reperes, motif: str) -> LigneEcartee:
    return LigneEcartee(
        badge=lire(champs, reperes.badge), nom=lire(champs, reperes.nom),
        prenom=lire(champs, reperes.prenom),
        code_classe=lire(champs, reperes.classe), motif=motif,
    )


def _encoder(lignes: list[str]) -> bytes:
    """Réémet les lignes d'origine, intactes, en UTF-8 avec BOM et CRLF.

    C'est exactement ce que Charlemagne produit et ce que PMB accepte. Les
    lignes ne repassent pas par un `csv.writer` : leur guillemetage
    d'origine est ainsi conservé au caractère près.
    """
    return BOM_UTF8 + ("\r\n".join(lignes) + "\r\n").encode("utf-8")


# ---------------------------------------------------------------------------
# Ce que le référentiel apporte
# ---------------------------------------------------------------------------


def _sites_par_code(session: Session) -> dict[str, str]:
    """Le code classe en majuscules, vers le nom du site qui l'héberge."""
    noms = {s.id: s.nom for s in session.query(Site).all()}
    par_code: dict[str, str] = {}
    for t in session.query(TableCorrespondance).all():
        code = (t.classe_code_court or "").strip().upper()
        if code and t.site_id in noms:
            par_code.setdefault(code, noms[t.site_id])
    return par_code


def _badges_connus(session: Session) -> set[str]:
    """Les badges du référentiel, en texte — le CSV ne connaît que ça.

    Sans filtre sur le type : un fichier d'adultes se contrôlerait de la
    même façon, et un élève mal typé ne doit pas être signalé absent.
    """
    return {
        str(b)
        for (b,) in session.query(Personne.badge).all()
        if b is not None
    }
