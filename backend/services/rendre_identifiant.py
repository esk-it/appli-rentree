"""Rendre un identifiant constaté à la personne qui le détient réellement.

## Le seul cas où le programme touche à un identifiant

Un identifiant ne bouge pas. C'est la règle la plus stricte du programme :
tout s'y rattache — le compte KoXo, le dossier personnel, le profil. Le
recalculer d'une année sur l'autre romprait l'ensemble.

Il existe une exception, et une seule : **rendre un identifiant à qui le
détenait déjà**. Ce n'est pas un changement, c'est une correction. Le
programme avait attribué un identifiant qu'il croyait libre, faute de voir
le compte qui le portait ; la personne à qui il l'a donné n'en a jamais
rien fait.

## Ce que la fonction exige

- **Le titulaire est désigné par son badge**, c'est-à-dire par l'ID unique
  que KoXo lui-même utilise pour se reconnaître. Pas par son nom.
- **Le porteur actuel n'a aucun compte** : ni adresse constatée, ni
  identifiant Google. S'il en a un, l'identifiant a servi, et le rendre
  casserait quelque chose — la fonction refuse et le dit.

## L'échange plutôt que l'invention

Quand le titulaire porte la forme suffixée du même identifiant — `llesaout`
contre `llesaout2` — les deux sont simplement échangés. Inventer un
troisième identifiant laisserait un trou et brouillerait la lecture.
"""
from __future__ import annotations

from dataclasses import dataclass

from sqlalchemy.orm import Session

from backend.models import Personne
from backend.services.regles_metier import calculer_login_base, proposer_suffixe


class RenduImpossible(Exception):
    """La correction ne peut pas être faite, et la raison est dans le message."""


@dataclass
class Rendu:
    login: str
    titulaire_id: int
    titulaire: str
    ancien_porteur_id: int
    ancien_porteur: str
    nouveau_login_ancien_porteur: str
    echange: bool
    """Vrai quand les deux identifiants ont été permutés."""


def rendre_identifiant(
    session: Session, *, login: str, badge_titulaire: int, mode: str = "simulation"
) -> Rendu:
    """Rend `login` à la personne portant `badge_titulaire`.

    Args:
        login: l'identifiant constaté dans la source externe.
        badge_titulaire: le badge — l'ID unique KoXo — de son détenteur.
        mode: `simulation` ne commet rien.

    Raises:
        RenduImpossible: titulaire ou porteur introuvable, porteur déjà
            pourvu d'un compte, ou aucun identifiant de repli disponible.
    """
    if mode not in ("simulation", "reel"):
        raise ValueError(f"mode invalide : {mode!r}")

    login = (login or "").strip()
    if not login:
        raise RenduImpossible("Aucun identifiant fourni.")

    titulaire = session.query(Personne).filter_by(badge=badge_titulaire).one_or_none()
    if titulaire is None:
        raise RenduImpossible(
            f"Aucune personne du référentiel ne porte le badge {badge_titulaire}."
        )

    porteur = session.query(Personne).filter_by(login=login).one_or_none()
    if porteur is None:
        raise RenduImpossible(
            f"L'identifiant « {login} » n'est attribué à personne au "
            "référentiel : il n'y a rien à rendre."
        )
    if porteur.id == titulaire.id:
        raise RenduImpossible(
            f"{titulaire.prenom} {titulaire.nom} porte déjà « {login} »."
        )

    # Le garde-fou qui compte : un identifiant qui a servi ne se reprend pas.
    empeche = []
    if porteur.email_constate:
        empeche.append(f"une adresse constatée ({porteur.email_constate})")
    if porteur.google_user_id:
        empeche.append("un compte Google")
    # Un identifiant que sa propre source attribue au porteur actuel n'est
    # pas usurpé : deux bases KoXo peuvent le détenir chacune pour
    # quelqu'un. Le référentiel n'en garde qu'un, et c'est structurel.
    from backend.models import LoginReserve

    constat = (
        session.query(LoginReserve)
        .filter_by(login=login, badge=porteur.badge)
        .one_or_none()
    )
    if constat is not None:
        raise RenduImpossible(
            f"« {login} » est aussi détenu par {porteur.prenom} {porteur.nom} "
            f"dans une source KoXo (badge {porteur.badge}). Deux bases "
            "distinctes peuvent l'attribuer chacune à quelqu'un ; le "
            "référentiel n'en garde qu'un. Ce n'est pas une erreur à "
            "corriger, et le rendre casserait l'autre compte."
        )

    if empeche:
        raise RenduImpossible(
            f"{porteur.prenom} {porteur.nom} a déjà {' et '.join(empeche)} sous "
            f"« {login} ». Le lui retirer romprait ce qui s'y rattache : "
            "l'arbitrage est à faire à la main, pas ici."
        )

    ancien_login_titulaire = titulaire.login or ""
    base = calculer_login_base(porteur.prenom, porteur.nom)
    echange = bool(ancien_login_titulaire) and ancien_login_titulaire.startswith(base)

    if echange:
        nouveau = ancien_login_titulaire
    else:
        proposition = proposer_suffixe(session, base)
        if proposition is None:
            raise RenduImpossible(
                f"Aucun identifiant de repli disponible pour {porteur.prenom} "
                f"{porteur.nom} à partir de « {base} »."
            )
        nouveau = proposition.login_propose

    rendu = Rendu(
        login=login,
        titulaire_id=titulaire.id,
        titulaire=f"{titulaire.prenom} {titulaire.nom}",
        ancien_porteur_id=porteur.id,
        ancien_porteur=f"{porteur.prenom} {porteur.nom}",
        nouveau_login_ancien_porteur=nouveau,
        echange=echange,
    )

    if mode == "reel":
        # L'unicité est contrainte en base : on libère avant d'attribuer.
        # Le passage par une valeur intermédiaire évite que les deux lignes
        # portent le même identifiant l'espace d'un flush.
        provisoire = f"~{porteur.id}~"
        porteur.login = provisoire
        session.flush()
        titulaire.login = login
        session.flush()
        porteur.login = nouveau
        session.flush()

    return rendu
