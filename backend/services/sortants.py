"""Vue des sortants : où ils devraient être, où ils sont vraiment.

## Le besoin

Une fois les sortants suspendus et archivés, il faut pouvoir le
**vérifier**. Le programme n'agit pas sur Google : il produit des
fichiers et mémorise ce qu'on lui dit avoir fait. Entre les deux, un
import oublié, une ligne refusée ou un déplacement manuel, et sa
mémoire diverge du réel sans que rien ne l'indique.

Ce service répond à deux questions distinctes :

1. **Qui devrait être sorti ?** — depuis la réconciliation et les
   comptes déjà en quarantaine. Aucune connexion nécessaire.
2. **Où est-il vraiment ?** — en interrogeant Google, quand l'API est
   configurée. C'est la seule façon de vérifier au lieu de croire.

Vérifier veut dire relever un écart, pas le corriger : rien n'est
modifié ici. La correction reste une action délibérée.

## Échéance de purge

Elle vient de `CompteCible.date_prevue_purge`, posée à la mise en
quarantaine. Le nom de l'OU d'archivage la porte aussi, ce qui rend le
ménage lisible depuis la console Google seule — mais c'est la base qui
fait foi pour l'alerte.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date

from sqlalchemy.orm import Session

from backend.models import CompteCible, Personne, Site

# Statuts de vérification face à Google
NON_VERIFIE = "non_verifie"
CONFORME = "conforme"
ECART = "ecart"
INTROUVABLE = "introuvable"


@dataclass
class Sortant:
    """Une personne sortie, et l'état de son compte Google."""

    personne_id: int
    cle_pivot: str
    nom: str
    prenom: str
    email: str | None
    site: str | None
    derniere_classe: str | None

    etat: str
    """État du CompteCible : `quarantaine`, `purge`…"""
    date_prevue_purge: date | None
    ou_attendue: str | None
    note: str | None = None

    # Renseignés seulement après vérification auprès de Google
    verification: str = NON_VERIFIE
    ou_reelle: str | None = None
    suspendu_reellement: bool | None = None
    detail_verification: str | None = None
    verifie_le: date | None = None
    """Quand la dernière confrontation a eu lieu."""

    @property
    def echeance_depassee(self) -> bool:
        return bool(self.date_prevue_purge and self.date_prevue_purge <= date.today())


@dataclass
class RapportSortants:
    nb_total: int = 0
    nb_echeance_depassee: int = 0
    sortants: list[Sortant] = field(default_factory=list)

    @property
    def nb_conformes(self) -> int:
        return sum(1 for s in self.sortants if s.verification == CONFORME)

    @property
    def nb_ecarts(self) -> int:
        return sum(1 for s in self.sortants if s.verification in (ECART, INTROUVABLE))


def lister_sortants(
    session: Session,
    *,
    site_id: int | None = None,
    seulement_echus: bool = False,
) -> RapportSortants:
    """Les comptes en sortie connus du programme.

    Lecture seule, sans connexion à Google : donne ce que le référentiel
    croit savoir. La confrontation au réel se fait ensuite.
    """
    from backend.services.exports_google import calculer_ou_sortants

    objets_sites = {s.id: s for s in session.query(Site).all()}
    sites = {i: s.nom for i, s in objets_sites.items()}
    # Une OU par site : NDE garde sa convention propre.
    ou_par_site = {
        i: calculer_ou_sortants(session, site=s) for i, s in objets_sites.items()
    }
    ou_defaut = calculer_ou_sortants(session)

    q = (
        session.query(CompteCible, Personne)
        .join(Personne, CompteCible.personne_id == Personne.id)
        .filter(
            CompteCible.cible == "google",
            CompteCible.etat.in_(("quarantaine", "purge")),
        )
    )
    if site_id is not None:
        q = q.filter(Personne.site_id == site_id)

    rapport = RapportSortants()
    for compte, personne in q.all():
        if seulement_echus and not (
            compte.date_prevue_purge and compte.date_prevue_purge <= date.today()
        ):
            continue
        rapport.sortants.append(
            Sortant(
                personne_id=personne.id,
                cle_pivot=personne.cle_pivot,
                nom=personne.nom,
                prenom=personne.prenom,
                email=compte.identifiant_externe or personne.email,
                site=sites.get(personne.site_id) if personne.site_id else None,
                derniere_classe=personne.classe,
                etat=compte.etat,
                date_prevue_purge=compte.date_prevue_purge,
                # L'OU d'archivage est datée : celle d'un compte sorti l'an
                # dernier n'est pas celle calculée aujourd'hui. On ne l'affiche
                # comme attendue que pour les sorties de la campagne en cours.
                ou_attendue=ou_par_site.get(personne.site_id, ou_defaut),
                note=compte.note,
                # Relu plutôt que recalculé : la vérification dure plusieurs
                # minutes, et son résultat doit survivre au rafraîchissement
                # de l'écran.
                verification=compte.verification or NON_VERIFIE,
                ou_reelle=compte.ou_constatee,
                detail_verification=compte.detail_verification,
                verifie_le=compte.verifie_le,
            )
        )

    rapport.sortants.sort(
        key=lambda s: (s.date_prevue_purge or date.max, s.nom, s.prenom)
    )
    rapport.nb_total = len(rapport.sortants)
    rapport.nb_echeance_depassee = sum(1 for s in rapport.sortants if s.echeance_depassee)
    return rapport


# ---------------------------------------------------------------------------
# Confrontation à l'état réel de Google
# ---------------------------------------------------------------------------


@dataclass
class ConstatGoogle:
    """Ce que Google répond pour un compte donné."""

    existe: bool
    ou: str | None = None
    suspendu: bool | None = None
    erreur: str | None = None


def memoriser_constat(session, sortant: Sortant) -> None:
    """Écrit sur le compte le résultat de sa dernière vérification.

    Le rapport des sortants est reconstruit à chaque appel : sans cette
    trace, une vérification de plusieurs minutes serait effacée par le
    premier rafraîchissement de l'écran.
    """
    from backend.models import CompteCible

    compte = (
        session.query(CompteCible)
        .filter_by(personne_id=sortant.personne_id, cible="google")
        .one_or_none()
    )
    if compte is None:
        return
    compte.verification = sortant.verification
    compte.ou_constatee = sortant.ou_reelle
    compte.detail_verification = sortant.detail_verification
    compte.verifie_le = date.today()


def comparer_au_constat(sortant: Sortant, constat: ConstatGoogle) -> None:
    """Renseigne le résultat de vérification sur le sortant, en place.

    Un compte sorti doit être rangé dans une OU d'archivage — et c'est
    tout. Il **reste actif** : la quarantaine tient à sa sortie de l'arbre
    des classes, pas à la privation d'accès, et son titulaire garde sa
    messagerie jusqu'à la lettre de prévenance.

    Exiger la suspension, comme le faisait la première version, signalait
    en écart des comptes parfaitement conformes.

    La racine de l'OU suffit à juger : le sous-dossier porte une année
    d'échéance qui varie d'une campagne à l'autre, et l'égalité stricte
    signalerait à tort tous les sortants des années précédentes.
    """
    if constat.erreur:
        sortant.verification = ECART
        sortant.detail_verification = constat.erreur
        return
    if not constat.existe:
        sortant.verification = INTROUVABLE
        sortant.detail_verification = "Compte absent de Google (déjà supprimé ?)"
        return

    sortant.ou_reelle = constat.ou
    sortant.suspendu_reellement = constat.suspendu

    racine_attendue = (sortant.ou_attendue or "").split("/Comptes")[0].rstrip("/")
    dans_archivage = bool(constat.ou and constat.ou.startswith(racine_attendue))

    problemes = []
    if not dans_archivage:
        problemes.append(f"encore dans {constat.ou}")

    if problemes:
        sortant.verification = ECART
        sortant.detail_verification = ", ".join(problemes)
    else:
        sortant.verification = CONFORME
        sortant.detail_verification = None
