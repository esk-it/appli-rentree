"""Créer des comptes Google pour un site qui n'a pas de KoXo.

## Le cas

Deux sites sur trois ont un serveur KoXo : il fabrique les mots de passe,
les imprime sur une fiche, et le programme n'a qu'à les recopier vers
Google. Le troisième — NDE — n'en a pas. Ses élèves n'ont qu'un compte
Google, et personne ne fabrique leur mot de passe.

La règle « le programme n'invente aucun mot de passe » vaut parce que KoXo
en est l'autorité. Là où il n'y a pas de KoXo, il n'y a pas d'autorité à
respecter, et refuser d'inventer reviendrait à refuser de créer les comptes.

## Ce que ce module garantit

**Un mot de passe généré ne doit jamais être perdu.** Il n'existe nulle
part ailleurs : le perdre oblige à réinitialiser le compte, élève par
élève. La génération et le dépôt au coffre sont donc **le même geste** —
on ne peut pas obtenir le fichier sans que les mots de passe soient rangés.

C'est pourquoi la fonction exige la clé du coffre. Sans coffre ouvert, elle
refuse plutôt que de produire un fichier dont les secrets s'évaporeraient à
la fermeture de la fenêtre.

## La forme

Celle de KoXo : `Aaaaaa99`. Mesurée sur 1665 mots de passe réels de
l'établissement, 1663 la suivent. Reprendre la même forme n'est pas de
l'imitation : les élèves des deux autres sites ont déjà celle-là, les
fiches se ressemblent, et les règles de complexité de l'annuaire sont déjà
satisfaites par elle.
"""
from __future__ import annotations

import csv as _csv
import io as _io
from dataclasses import dataclass, field

from sqlalchemy.orm import Session

# Les modèles et les services voisins sont importés dans les fonctions :
# le module est chargé avant que la base de test soit reconstruite, et un
# import de haut niveau fige des classes qui ne sont plus les bonnes.


class GenerationImpossible(Exception):
    """La génération est refusée, et le message dit pourquoi."""


@dataclass
class RapportGeneration:
    site_nom: str = ""
    nb_lignes: int = 0
    nb_generes: int = 0
    nb_deja_au_coffre: int = 0
    """Comptes dont le mot de passe était déjà rangé : on le reprend au lieu
    d'en fabriquer un nouveau, sinon relancer l'export changerait les mots
    de passe déjà distribués."""
    avertissements: list[str] = field(default_factory=list)
    nom_fichier_csv: str = ""
    nom_fichier_fiches: str = ""


def preparer_comptes(
    session: Session,
    cle: bytes,
    *,
    site_id: int,
    annee_cible_id: int,
    annee_source_id: int | None = None,
    categorie: str = "nouveaux",
    organisation: str | None = None,
    modele: str | None = None,
) -> tuple[bytes, bytes, RapportGeneration]:
    """Fabrique les mots de passe, les range, et rend les deux fichiers.

    Args:
        cle: la clé du coffre. Obligatoire — un mot de passe généré qui
            n'est pas rangé est un mot de passe perdu.

    Returns:
        `(csv_google, etiquettes_html, rapport)`. Le premier s'importe dans
        la console d'administration ; le second s'imprime et se distribue,
        à la présentation des étiquettes que KoXo produit pour les deux
        autres sites — un élève de NDE reçoit la même chose que celui de
        NDK.

    Raises:
        GenerationImpossible: site inconnu, ou site qui a déjà un KoXo.
    """
    from backend.models import AnneeScolaire, Site
    from backend.services.exports_google import BOM_UTF8, generer_csv_google
    from backend.services.regles_metier import classe_lisible

    if not cle:
        raise GenerationImpossible(
            "Le coffre doit être ouvert : un mot de passe fabriqué et non "
            "rangé serait perdu à la fermeture de la fenêtre, et il faudrait "
            "réinitialiser chaque compte."
        )

    site = session.query(Site).filter_by(id=site_id).one_or_none()
    if site is None:
        raise GenerationImpossible(f"Site introuvable : {site_id}")

    contenu, rapport_base = generer_csv_google(
        session=session,
        site_id=site_id,
        type_personne="eleve",
        categorie=categorie,
        annee_cible_id=annee_cible_id,
        annee_source_id=annee_source_id,
    )

    rapport = RapportGeneration(
        site_nom=site.nom,
        nb_lignes=rapport_base.nb_lignes,
        nom_fichier_csv=f"Google_{site.nom}_eleves_avec_mdp.csv",
        nom_fichier_fiches=f"Etiquettes_{site.nom}_par_classe.html",
    )
    if not rapport_base.nb_lignes:
        # Rendre deux fichiers vides est pire que refuser : on les
        # enregistre, on les ouvre, et on cherche ce qui a raté. La cause
        # est presque toujours la même — l'année source réglée sur l'année
        # cible, auquel cas « nouveaux » ne désigne personne.
        raise GenerationImpossible(
            f"Aucun compte à fabriquer pour {site.nom} en catégorie "
            f"« {categorie} ». Vérifie l'année source : si elle vaut l'année "
            "cible, « nouveaux » ne peut désigner personne. En « tous », "
            "l'export reprend tout le site."
        )

    par_email = _personnes_par_email(session, site_id)
    classes = _classes(session, annee_cible_id)
    deja = _secrets_existants(session, cle, site.nom)

    texte = contenu[len(BOM_UTF8):].decode("utf-8") if contenu.startswith(BOM_UTF8) else contenu.decode("utf-8")
    lecteur = _csv.DictReader(_io.StringIO(texte))
    lignes = list(lecteur)
    colonnes = list(lecteur.fieldnames or (lignes[0] if lignes else {}))

    fiches: list[dict] = []
    for ligne in lignes:
        email = (ligne.get("Email Address [Required]") or "").strip().lower()
        personne = par_email.get(email)
        if personne is None:
            rapport.avertissements.append(
                f"{email} : aucune personne du référentiel ne porte cette "
                "adresse, mot de passe non généré."
            )
            continue

        # Relancer l'export ne doit pas changer un mot de passe déjà
        # distribué : on reprend celui du coffre s'il y en a un.
        mdp = deja.get(personne.id)
        if mdp:
            rapport.nb_deja_au_coffre += 1
        else:
            from backend.services.coffre import deposer, fabriquer_mot_de_passe

            mdp = fabriquer_mot_de_passe()
            deposer(
                session,
                cle,
                personne_id=personne.id,
                mot_de_passe=mdp,
                cible="google",
                site=site.nom,
                origine="genere",
            )
            rapport.nb_generes += 1

        ligne["Password [Required]"] = mdp
        classe = classes.get(personne.id) or ""
        fiches.append(
            {
                "classe": classe_lisible(classe),
                "nom": personne.nom or "",
                "prenom": personne.prenom or "",
                # KoXo affiche « groupe primaire / groupe secondaire »,
                # mais « Elèves / 3F » n'apprend rien de plus à l'élève que
                # « 3_F » : le groupe primaire est le même pour tous.
                "groupe": classe_lisible(classe),
                "login": personne.login or "",
                "mot_de_passe": mdp,
                # L'identifiant réseau ne suffit pas : c'est l'adresse que
                # l'élève saisit pour se connecter à Google, et elle ne se
                # devine pas à partir du login — `alezia.acquitter.le.velly@`
                # pour `aacquitter`.
                "adresse": personne.email or "",
            }
        )

    annee = session.query(AnneeScolaire).filter_by(id=annee_cible_id).one_or_none()
    return (
        _encoder(colonnes, lignes),
        fiches_html(
            fiches,
            # Le bandeau nomme l'établissement — « Collège Notre Dame
            # d'Esperance » — et non l'OGEC qui le gère : c'est un papier
            # remis à l'élève, qui reconnaît son collège, pas son
            # organisme gestionnaire. `organisation_etiquettes` reste un
            # remplacement explicite quand on en veut un autre.
            organisation=(
                organisation
                or site.nom_complet
                or site.organisation_etiquettes
                or site.nom
            ),
            annee=annee.libelle if annee else "",
            # NDE n'a pas de serveur : promettre un accès réseau qui
            # n'existe pas serait pire que de ne rien afficher.
            avec_reseau=bool(site.base_koxo),
            site_nom=site.nom,
            modele=modele,
        ),
        rapport,
    )


def _encoder(colonnes: list[str], lignes: list[dict]) -> bytes:
    from backend.services.exports_google import BOM_UTF8

    tampon = _io.StringIO()
    ecrivain = _csv.DictWriter(tampon, fieldnames=colonnes, quoting=_csv.QUOTE_MINIMAL)
    ecrivain.writeheader()
    for l in lignes:
        ecrivain.writerow(l)
    return BOM_UTF8 + tampon.getvalue().encode("utf-8", errors="replace")


def _personnes_par_email(session: Session, site_id: int) -> dict:
    from backend.models import Personne

    par_email: dict = {}
    for p in session.query(Personne).filter_by(site_id=site_id, type="eleve").all():
        for champ in (p.email, p.email_constate):
            if champ:
                par_email[champ.strip().lower()] = p
    return par_email


def _classes(session: Session, annee_id: int) -> dict[int, str | None]:
    from backend.models import Snapshot

    derniers: dict[int, str | None] = {}
    for s in (
        session.query(Snapshot)
        .filter_by(annee_scolaire_id=annee_id)
        .order_by(Snapshot.date_ingestion, Snapshot.id)
        .all()
    ):
        derniers[s.personne_id] = s.classe
    return derniers


def _secrets_existants(session: Session, cle: bytes, site_nom: str) -> dict[int, str]:
    """Les mots de passe déjà rangés pour ce site, par personne."""
    from backend.models import SecretConserve
    from backend.services.coffre import _dechiffrer

    trouves: dict[int, str] = {}
    for s in (
        session.query(SecretConserve)
        .filter_by(cible="google", site=site_nom, origine="genere")
        .all()
    ):
        trouves[s.personne_id] = _dechiffrer(cle, s)
    return trouves


# ---------------------------------------------------------------------------
# Les étiquettes, à la présentation de KoXo
# ---------------------------------------------------------------------------

# Cotes relevées dans un PDF d'étiquettes produit par KoXo, en points
# PostScript. Les reprendre telles quelles n'est pas du zèle : l'élève de
# NDE recevra la même étiquette que celui de NDK, et le professeur qui les
# distribue n'a pas à apprendre deux présentations.
def fiches_html(
    etiquettes: list[dict],
    *,
    organisation: str,
    annee: str,
    avec_reseau: bool = False,
    site_nom: str = "",
    modele: str | None = None,
    par_page: int = 18,
) -> bytes:
    """Les étiquettes de comptes, à imprimer.

    La présentation vient de `modeles_etiquettes` : elle se choisit, et le
    gabarit n'est plus écrit ici. Ce qui ne change pas, c'est la géométrie
    — trois colonnes, six rangées, au format des planches de KoXo — parce
    que les feuilles pré-découpées de l'établissement sont à ce format.

    Args:
        etiquettes: dicts portant `nom`, `prenom`, `classe`, `groupe`,
            `login`, `mot_de_passe` et `adresse`.
        organisation: ce qu'affiche l'en-tête — le nom de l'établissement,
            que l'élève reconnaît.
        site_nom: le nom court du site (`NDK`), d'où se déduisent son logo
            et sa couleur.
        avec_reseau: faux là où il n'y a pas de serveur — promettre un
            accès qui n'existe pas serait pire que se taire.
    """
    from backend.services.modeles_etiquettes import (
        MODELE_PAR_DEFAUT,
        page_etiquettes,
    )

    avec_organisation = [
        {**e, "organisation": organisation} for e in etiquettes
    ]
    return page_etiquettes(
        avec_organisation,
        annee=annee,
        site_nom=site_nom,
        modele=modele or MODELE_PAR_DEFAUT,
        avec_reseau=avec_reseau,
        par_page=par_page,
    )
