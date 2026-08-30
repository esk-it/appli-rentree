"""Les mouvements d'un seul élève, en cours d'année.

## Ce que ce module couvre

Toute la chaîne de rentrée suppose une campagne : on ingère, on exporte, on
synchronise, en bloc. La vie scolaire, elle, se fait à l'unité — un
changement de classe en octobre, une inscription en janvier, un départ en
mars. Rien n'était prévu pour ça, et le faire à la main dans chaque système
revenait à espérer n'en oublier aucun.

## Pourquoi ce n'est pas qu'un appel à Google

Changer la classe d'un élève uniquement dans Google serait pire que de ne
rien faire : la bascule du jour J le renverrait dans son ancienne classe,
la synchronisation des groupes l'y remettrait, et l'an prochain il
compterait comme montant de la mauvaise. **Le référentiel bouge d'abord**,
et Google suit.

## Ce que le programme ne peut pas faire, et qu'il dit

KoXo n'a pas d'API. Le groupe secondaire d'un élève y est sa classe, et
aucun appel ne peut le changer. Le plan porte donc, à côté de ce qu'il
applique, **la liste de ce qui reste à faire ailleurs** — KoXo, PMB, JPM.
Un écran qui ferait 60 % du travail sans nommer les 40 % restants serait
plus dangereux qu'un écran qui n'en ferait rien.

## Simulation d'abord, comme partout

Le plan se relit avant d'être appliqué. Il nomme l'élève, l'ancienne et la
nouvelle classe, l'unité d'organisation visée et les deux groupes
concernés.
"""
from __future__ import annotations

from dataclasses import dataclass, field

from sqlalchemy.orm import Session

from backend.models import (
    AnneeScolaire,
    CompteCible,
    Personne,
    Snapshot,
    TableCorrespondance,
)


class MouvementImpossible(Exception):
    """Le mouvement ne peut pas être planifié, et le message dit pourquoi."""


@dataclass
class ResteAFaire:
    """Un système que le programme ne sait pas modifier, et le geste attendu."""

    systeme: str
    geste: str


@dataclass
class PlanMouvement:
    personne_id: int
    cle_pivot: str
    nom: str
    prenom: str
    email: str | None

    classe_avant: str | None = None
    classe_apres: str | None = None

    ou_avant: str | None = None
    ou_apres: str | None = None
    deplacement_utile: bool = False
    """Faux quand l'OU ne change pas — en pré-rentrée, tout le monde partage
    l'unité d'attente de son site, quelle que soit la classe."""

    groupe_quitte: str | None = None
    groupe_rejoint: str | None = None

    reste_a_faire: list[ResteAFaire] = field(default_factory=list)
    avertissements: list[str] = field(default_factory=list)
    applique: bool = False

    @property
    def a_un_effet(self) -> bool:
        return bool(
            self.classe_avant != self.classe_apres
            or self.deplacement_utile
            or self.groupe_quitte
            or self.groupe_rejoint
        )


def _dernier_snapshot(session: Session, personne_id: int, annee_id: int):
    return (
        session.query(Snapshot)
        .filter_by(personne_id=personne_id, annee_scolaire_id=annee_id)
        .order_by(Snapshot.date_ingestion.desc(), Snapshot.id.desc())
        .first()
    )


def planifier_changement_de_classe(
    session: Session,
    *,
    personne_id: int,
    nouvelle_classe: str,
    annee_id: int,
    mode: str = "simulation",
    reprise: bool = False,
) -> PlanMouvement:
    """Décrit — et applique, si demandé — le passage dans une autre classe.

    Args:
        nouvelle_classe: le code court, tel que la Table le déclare.
        annee_id: l'année en cours, celle dont la photographie fait foi.
        mode: `simulation` ne commet rien.
        reprise: accepte que l'élève soit déjà dans la classe visée, et ne
            réécrit alors pas le référentiel. Sert au rattrapage : si Google
            a échoué après la mise à jour du référentiel, rejouer le
            mouvement doit rester possible sans être refusé pour la raison
            même qui prouve que la première moitié a réussi.

    Raises:
        MouvementImpossible: personne inconnue, sans photographie pour cette
            année, classe absente de la Table, ou classe inchangée.
    """
    if mode not in ("simulation", "reel"):
        raise ValueError(f"mode invalide : {mode!r}")

    annee = session.query(AnneeScolaire).filter_by(id=annee_id).one_or_none()
    if annee is None:
        raise MouvementImpossible(f"Année introuvable : {annee_id}")

    personne = session.query(Personne).filter_by(id=personne_id).one_or_none()
    if personne is None:
        raise MouvementImpossible(f"Personne introuvable : {personne_id}")

    snap = _dernier_snapshot(session, personne_id, annee_id)
    if snap is None:
        raise MouvementImpossible(
            f"{personne.prenom} {personne.nom} n'a pas de photographie pour "
            f"{annee.libelle} : le changement de classe n'aurait rien à "
            "modifier. Ingère d'abord l'export Charlemagne de l'année."
        )

    nouvelle = (nouvelle_classe or "").strip()
    if not nouvelle:
        raise MouvementImpossible("Aucune classe de destination fournie.")
    deja = nouvelle == (snap.classe or "")
    if deja and not reprise:
        raise MouvementImpossible(
            f"{personne.prenom} {personne.nom} est déjà en {nouvelle}."
        )

    # La Table est la seule autorité sur les destinations : une classe
    # qu'elle ignore ne se devine pas, elle se déclare.
    cible = (
        session.query(TableCorrespondance)
        .filter_by(classe_code_court=nouvelle)
        .first()
    )
    if cible is None:
        raise MouvementImpossible(
            f"La classe {nouvelle!r} n'est pas déclarée dans la Table de "
            "correspondance : ni son unité d'organisation ni son groupe ne "
            "sont connus. Complète la Table, puis reviens."
        )
    classe_avant = snap.classe
    if deja:
        # Rejouer un mouvement déjà écrit : l'origine est dans la
        # photographie qui précède, pas dans la courante.
        classe_avant = snap.classe_precedente or snap.classe
    ancienne = (
        session.query(TableCorrespondance)
        .filter_by(classe_code_court=classe_avant or "")
        .first()
    )

    compte = (
        session.query(CompteCible)
        .filter_by(personne_id=personne_id, cible="google")
        .one_or_none()
    )
    ou_avant = compte.ou_appliquee if compte else None

    # Où l'élève doit atterrir : là où en est la campagne pour lui. S'il
    # attend encore en unité de pré-rentrée, changer de classe ne le
    # déplace pas — c'est le jour J qui répartira.
    if ou_avant and ancienne and ou_avant == ancienne.ou_pre_rentree:
        ou_apres = cible.ou_pre_rentree
    else:
        ou_apres = cible.ou_definitive

    plan = PlanMouvement(
        personne_id=personne.id,
        cle_pivot=personne.cle_pivot,
        nom=personne.nom or "",
        prenom=personne.prenom or "",
        email=personne.email,
        classe_avant=classe_avant,
        classe_apres=nouvelle,
        ou_avant=ou_avant,
        ou_apres=ou_apres,
        deplacement_utile=bool(ou_apres) and ou_apres != ou_avant,
        groupe_quitte=(ancienne.groupe_google if ancienne else None),
        groupe_rejoint=cible.groupe_google,
    )

    if not personne.email:
        plan.avertissements.append(
            "Aucune adresse connue : rien ne peut être appliqué dans Google."
        )
    if ou_avant is None:
        plan.avertissements.append(
            "Le programme n'a jamais placé ce compte : il ne sait pas d'où il "
            "part, et le déplacement pourrait ne rien changer."
        )
    if not cible.groupe_google:
        plan.avertissements.append(
            f"La classe {nouvelle} ne déclare aucune adresse de groupe : "
            "l'élève n'entrera dans aucune liste."
        )

    plan.reste_a_faire = [
        ResteAFaire(
            "KoXo",
            f"Changer le groupe secondaire de {personne.login} de "
            f"{classe_avant or '—'} en {nouvelle}. KoXo n'a pas d'API : "
            "ce geste est manuel.",
        ),
        ResteAFaire(
            "PMB",
            "Régénérer l'export si la classe y sert de rattachement.",
        ),
        ResteAFaire(
            "JPM",
            "Vérifier les droits d'accès si la classe les détermine.",
        ),
    ]

    if mode == "reel" and not deja:
        # Le référentiel d'abord : sans lui, la bascule du jour J et la
        # composition des groupes ramèneraient l'élève dans son ancienne
        # classe, chacune de son côté.
        personne.classe = nouvelle
        session.add(
            Snapshot(
                personne_id=personne.id,
                annee_scolaire_id=annee_id,
                nom=snap.nom,
                prenom=snap.prenom,
                nom_usage=snap.nom_usage,
                classe=nouvelle,
                niveau=snap.niveau,
                code_etablissement=snap.code_etablissement,
                regime=snap.regime,
                chemin_photo=snap.chemin_photo,
                date_entree=snap.date_entree,
                classe_precedente=snap.classe,
            )
        )
        session.flush()
        plan.applique = True
    elif mode == "reel":
        # Reprise : le référentiel porte déjà le changement, seul Google
        # reste à rattraper.
        plan.applique = True
        plan.avertissements.append(
            "Le référentiel portait déjà ce changement : seule la partie "
            "Google a été rejouée."
        )

    return plan


# ---------------------------------------------------------------------------
# L'application dans Google
# ---------------------------------------------------------------------------


@dataclass
class OperationAppliquee:
    libelle: str
    reussie: bool
    message: str | None = None


def appliquer_dans_google(session: Session, plan: PlanMouvement, client):
    """Déplace l'unité d'organisation, puis échange les deux groupes.

    Le client est **fourni** plutôt que construit ici : c'est ce qui rend
    cette fonction éprouvable sans réseau, et c'est elle qui porte l'ordre
    des gestes et le compte rendu.

    Chaque opération est tentée séparément. Une adhésion refusée n'annule
    pas le déplacement qui a eu lieu, et l'écran doit pouvoir dire laquelle
    reprendre — un « échec » global laisserait deviner.
    """
    from backend.services.google_api import (
        OperationGoogle,
        payload_deplacement_ou,
    )

    operations: list[OperationAppliquee] = []
    if not plan.email:
        return operations

    def tenter(libelle, geste):
        try:
            geste()
        except Exception as e:  # noqa: BLE001 — la raison remonte à l'écran
            operations.append(OperationAppliquee(libelle, False, str(e)))
            return False
        operations.append(OperationAppliquee(libelle, True))
        return True

    if plan.deplacement_utile and plan.ou_apres:
        ok = tenter(
            f"Déplacer {plan.email} vers {plan.ou_apres}",
            lambda: client.appliquer_operation(
                OperationGoogle(
                    action="deplacer",
                    email=plan.email,
                    payload=payload_deplacement_ou(org_unit_path=plan.ou_apres),
                    libelle=f"Déplacer {plan.email}",
                    personne_id=plan.personne_id,
                    ou_visee=plan.ou_apres,
                )
            ),
        )
        if ok:
            _memoriser_ou(session, plan)

    if plan.groupe_quitte:
        tenter(
            f"Retirer {plan.email} de {plan.groupe_quitte}",
            lambda: client.retirer_membre(plan.groupe_quitte, plan.email),
        )

    if plan.groupe_rejoint:
        tenter(
            f"Ajouter {plan.email} à {plan.groupe_rejoint}",
            lambda: client.ajouter_membre(plan.groupe_rejoint, plan.email),
        )

    return operations


def _memoriser_ou(session: Session, plan: PlanMouvement) -> None:
    """Garde l'OU appliquée, comme le fait la bascule.

    Sans cette trace, l'écran de bascule reproposerait le déplacement, et
    l'avancement du parcours compterait l'élève comme non placé.
    """
    compte = (
        session.query(CompteCible)
        .filter_by(personne_id=plan.personne_id, cible="google")
        .one_or_none()
    )
    if compte is None:
        compte = CompteCible(
            personne_id=plan.personne_id, cible="google", etat="cree"
        )
        session.add(compte)
    compte.ou_appliquee = plan.ou_apres
    session.flush()
