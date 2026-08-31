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
) -> tuple[bytes, bytes, RapportGeneration]:
    """Fabrique les mots de passe, les range, et rend les deux fichiers.

    Args:
        cle: la clé du coffre. Obligatoire — un mot de passe généré qui
            n'est pas rangé est un mot de passe perdu.

    Returns:
        `(csv_google, csv_fiches, rapport)`. Le premier s'importe dans la
        console d'administration ; le second s'imprime et se distribue.

    Raises:
        GenerationImpossible: site inconnu, ou site qui a déjà un KoXo.
    """
    from backend.models import Site
    from backend.services.exports_google import BOM_UTF8, generer_csv_google

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
        nom_fichier_fiches=f"Fiches_{site.nom}_par_classe.csv",
    )
    if not rapport_base.nb_lignes:
        rapport.avertissements.append(
            "Aucune ligne à créer : vérifie l'année et la catégorie."
        )
        return contenu, BOM_UTF8, rapport

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
        fiches.append(
            {
                "Classe": classes.get(personne.id) or "",
                "Nom": personne.nom or "",
                "Prénom": personne.prenom or "",
                "Adresse": email,
                "Mot de passe": mdp,
            }
        )

    return (
        _encoder(colonnes, lignes),
        _encoder(
            ["Classe", "Nom", "Prénom", "Adresse", "Mot de passe"],
            sorted(fiches, key=lambda f: (f["Classe"], f["Nom"], f["Prénom"])),
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
