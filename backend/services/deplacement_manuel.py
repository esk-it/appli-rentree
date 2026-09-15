"""Déplacement choisi dans Google : une personne, une classe, une sélection.

## Pourquoi un geste manuel à côté de la bascule

La bascule des OU et la synchronisation des groupes ne demandent jamais où
ranger quelqu'un : elles le **calculent**, en lisant la Table de
correspondance à partir de la classe du snapshot. C'est ce qu'il faut pour
une rentrée — deux mille comptes rangés sans avoir à désigner quoi que ce
soit, et sans qu'une main distraite invente une destination.

Mais l'année n'est pas faite que de rentrées. Un élève change de classe en
novembre, un compte a été rangé au mauvais endroit à la console, une classe
entière doit bouger avant que la Table ne soit à jour. Là, la destination
n'est pas déductible : elle est décidée. Le programme n'avait aucune porte
pour cela, et il fallait sortir de l'application pour le faire.

## Ce que ce module ne devine pas

La destination vient de l'appelant, jamais de la Table — c'est toute la
différence avec la bascule. Et la portée est nominative : on traite les
personnes qu'on nomme, sans « et tous ceux qui leur ressemblent ». Une
classe entière se résout en une liste d'identifiants **avant** d'entrer
ici, et cette liste est relisible dans l'aperçu.

## L'état est lu, jamais supposé

`CompteCible.ou_appliquee` retient ce que le programme a appliqué. Ce n'est
pas ce que Google détient : une modification faite à la console ne passe
pas par nous, et un compte peut avoir bougé depuis. L'aperçu part donc de
l'annuaire, et c'est cet état-là qu'il compare et qu'il montre.

## Ne rien annoncer qu'on n'applique

Un compte déjà dans l'OU visée ne produit aucune opération ; une entrée
dans un groupe dont on est déjà membre non plus, ni une sortie d'un groupe
où l'on n'est pas. Sans cette règle, un plan de trente lignes en afficherait
trente là où il n'en applique qu'une, et relire le plan ne servirait plus à
rien — or c'est la seule protection avant l'envoi.

## Une destination absente arrête tout

Écrire dans une OU ou un groupe qui n'existe pas échoue compte par compte,
avec une erreur Google par ligne et aucune vue d'ensemble. Le plan vérifie
donc les destinations d'abord, et se déclare inexécutable tant qu'il en
manque une : mieux vaut un refus lisible que trente échecs.

## Jamais sur une adresse calculée

`Personne.email` sait rendre une adresse même sans compte connu : elle la
calcule. C'est ce qu'il faut pour préparer une création — jamais pour
écrire sur un compte existant. Sur cet annuaire, la formule ne retrouve que
93 % des adresses en place ; une sur quatorze désigne donc quelqu'un
d'autre, et c'est le voisin homonyme qu'on déplacerait. Ce module n'agit
que sur une adresse **constatée** dans Google ou **attribuée** à la main
pour lever une homonymie. Les autres sont écartées en le disant : leur
adresse se constate d'abord, par la Conformité Google.
"""
from __future__ import annotations

from dataclasses import dataclass, field

from sqlalchemy.orm import Session

from backend.models import Personne, Snapshot

ACTIONS = ("deplacer", "ajouter_groupe", "retirer_groupe")


def normaliser_ou(chemin: str | None) -> str | None:
    """Un chemin d'OU comparable : sans espaces parasites ni barre finale.

    Google rend `/3. NDK/NDK2027/2_5` ; un utilisateur qui recopie une OU y
    ajoute volontiers une barre. Comparer sans normaliser ferait croire à un
    déplacement là où il n'y en a pas.
    """
    if chemin is None:
        return None
    c = chemin.strip()
    if not c:
        return None
    if not c.startswith("/"):
        c = "/" + c
    if len(c) > 1:
        c = c.rstrip("/")
    return c


def normaliser_adresse(adresse: str | None) -> str | None:
    """Une adresse comparable. Google n'y distingue pas la casse."""
    a = (adresse or "").strip().lower()
    return a or None


@dataclass
class EtatCompte:
    """Ce que Google détient aujourd'hui pour une personne du référentiel."""

    personne_id: int
    nom: str
    prenom: str
    classe: str | None = None
    email: str | None = None

    existe: bool = False
    suspendu: bool = False
    ou_actuelle: str | None = None
    groupes_actuels: list[str] = field(default_factory=list)

    groupes_complets: bool = False
    """Vrai si `groupes_actuels` est l'inventaire complet des appartenances.

    Savoir si un élève est dans le groupe qu'on vise demande la composition
    de ce groupe — une requête. Savoir dans quels groupes il est demande une
    requête par personne. Sur une classe entière, la seconde forme coûte
    trente fois plus pour une information qu'on n'utilise pas. L'aperçu lit
    donc l'un ou l'autre selon la taille de la sélection, et ce drapeau dit
    lequel — pour que l'écran n'annonce pas « ses groupes » quand il ne
    montre que ceux qui étaient en question."""

    motif: str | None = None
    """Renseigné quand la personne ne peut pas être traitée. Elle est alors
    écartée du plan — mais nommée, jamais retirée en silence."""

    @property
    def libelle(self) -> str:
        return f"{self.nom} {self.prenom}".strip()


@dataclass
class MouvementManuel:
    """Une opération unitaire, telle qu'elle sera envoyée et affichée."""

    action: str
    personne_id: int
    email: str
    libelle: str
    ou_visee: str | None = None
    groupe: str | None = None


@dataclass
class PlanManuel:
    ou_destination: str | None = None
    groupes_ajouter: list[str] = field(default_factory=list)
    groupes_retirer: list[str] = field(default_factory=list)

    etats: list[EtatCompte] = field(default_factory=list)
    """Toutes les personnes demandées, traitables ou non — c'est la liste
    que l'utilisateur relit avant de confirmer."""

    mouvements: list[MouvementManuel] = field(default_factory=list)
    ecartes: list[EtatCompte] = field(default_factory=list)
    destinations_absentes: list[str] = field(default_factory=list)
    avertissements: list[str] = field(default_factory=list)

    nb_deja_en_place: int = 0
    """Comptes déjà dans l'OU visée. Ils ne produisent rien, mais les compter
    évite de croire que le plan a oublié quelqu'un."""

    @property
    def nb_deplacements(self) -> int:
        return sum(1 for m in self.mouvements if m.action == "deplacer")

    @property
    def nb_entrees_groupe(self) -> int:
        return sum(1 for m in self.mouvements if m.action == "ajouter_groupe")

    @property
    def nb_sorties_groupe(self) -> int:
        return sum(1 for m in self.mouvements if m.action == "retirer_groupe")

    @property
    def nb_total(self) -> int:
        return len(self.mouvements)

    @property
    def nb_concernes(self) -> int:
        """Personnes touchées par au moins une opération."""
        return len({m.personne_id for m in self.mouvements})

    @property
    def est_executable(self) -> bool:
        return not self.destinations_absentes and bool(self.mouvements)


def personnes_de_classes(
    session: Session,
    *,
    annee_id: int,
    classes: list[str],
    site_id: int | None = None,
    type_personne: str = "eleve",
) -> list[int]:
    """Les identifiants des personnes rangées dans ces classes.

    Résoudre « la 2nde 5 » en une liste nominative avant de construire le
    plan, plutôt que de porter un filtre jusqu'à l'envoi : l'aperçu montre
    alors des noms, et ce sont ces noms-là qui partent. Un élève inscrit
    deux fois la même année — export rejoué — n'est compté qu'une fois, sur
    son snapshot le plus récent.
    """
    retenues = {c.strip() for c in classes if c and c.strip()}
    if not retenues:
        return []

    q = (
        session.query(Personne, Snapshot)
        .join(Snapshot, Snapshot.personne_id == Personne.id)
        .filter(
            Snapshot.annee_scolaire_id == annee_id,
            Personne.type == type_personne,
        )
    )
    if site_id is not None:
        q = q.filter(Personne.site_id == site_id)

    derniers: dict[int, Snapshot] = {}
    for p, sn in q.all():
        prec = derniers.get(p.id)
        if prec is None or _plus_recent(sn, prec):
            derniers[p.id] = sn
    return sorted(
        pid for pid, sn in derniers.items() if (sn.classe or "").strip() in retenues
    )


def _plus_recent(candidat: Snapshot, tenant: Snapshot) -> bool:
    """Le candidat est-il postérieur ? Une date absente ne détrône rien."""
    if candidat.date_ingestion is None:
        return False
    if tenant.date_ingestion is None:
        return True
    return candidat.date_ingestion > tenant.date_ingestion


def _classe_courante(
    session: Session, personne_ids: list[int], annee_id: int | None
) -> dict[int, str | None]:
    if annee_id is None or not personne_ids:
        return {}
    derniers: dict[int, Snapshot] = {}
    for sn in (
        session.query(Snapshot)
        .filter(
            Snapshot.annee_scolaire_id == annee_id,
            Snapshot.personne_id.in_(personne_ids),
        )
        .all()
    ):
        prec = derniers.get(sn.personne_id)
        if prec is None or _plus_recent(sn, prec):
            derniers[sn.personne_id] = sn
    return {pid: sn.classe for pid, sn in derniers.items()}


def relever_etats(
    session: Session,
    personne_ids: list[int],
    *,
    etat_google: dict[str, dict | None],
    groupes_par_email: dict[str, list[str]] | None = None,
    groupes_complets: bool = False,
    annee_id: int | None = None,
) -> list[EtatCompte]:
    """Croise le référentiel et ce que Google rend, pour chaque personne.

    Args:
        etat_google: `{adresse: description | None}`, tel que
            `ClientGoogle.lire_utilisateurs` le rend. `None` signale un
            compte que Google ne connaît pas — un résultat, pas une panne.
        groupes_par_email: appartenances relevées compte par compte. Absent
            quand l'appel ne porte que sur les OU : lister les groupes de
            trente élèves coûte trente requêtes, inutiles si l'on ne touche
            pas aux groupes.
    """
    groupes_par_email = groupes_par_email or {}
    classes = _classe_courante(session, personne_ids, annee_id)

    connues = (
        {
            p.id: p
            for p in session.query(Personne).filter(Personne.id.in_(personne_ids)).all()
        }
        if personne_ids
        else {}
    )

    etats: list[EtatCompte] = []
    for pid in personne_ids:
        p = connues.get(pid)
        if p is None:
            etats.append(
                EtatCompte(
                    personne_id=pid,
                    nom="(inconnu)",
                    prenom="",
                    motif="Absent du référentiel",
                )
            )
            continue

        # Constatée ou attribuée, jamais calculée : voir l'en-tête du module.
        adresse = normaliser_adresse(p.email_constate or p.email_attribuee)
        etat = EtatCompte(
            personne_id=pid,
            nom=p.nom or "",
            prenom=p.prenom or "",
            classe=classes.get(pid),
            email=adresse,
        )
        if adresse is None:
            etat.motif = "Adresse non constatée dans Google"
            etats.append(etat)
            continue

        decrit = etat_google.get(adresse)
        if decrit is None:
            etat.motif = "Aucun compte Google à cette adresse"
            etats.append(etat)
            continue

        etat.existe = True
        etat.suspendu = bool(decrit.get("suspendu"))
        etat.ou_actuelle = normaliser_ou(decrit.get("ou"))
        etat.groupes_actuels = sorted(
            a
            for a in (
                normaliser_adresse(g) for g in groupes_par_email.get(adresse, [])
            )
            if a
        )
        etat.groupes_complets = groupes_complets
        etats.append(etat)
    return etats


def construire_plan_manuel(
    session: Session,
    *,
    personne_ids: list[int],
    etat_google: dict[str, dict | None],
    groupes_par_email: dict[str, list[str]] | None = None,
    groupes_complets: bool = False,
    ou_destination: str | None = None,
    groupes_ajouter: list[str] | None = None,
    groupes_retirer: list[str] | None = None,
    ou_existantes: set[str] | None = None,
    groupes_existants: set[str] | None = None,
    annee_id: int | None = None,
) -> PlanManuel:
    """Ce qui serait envoyé à Google. N'envoie rien.

    Args:
        ou_existantes: chemins réellement présents dans l'annuaire. Sans eux
            la vérification est sautée — un appelant qui ne peut pas les lire
            n'est pas forcé d'inventer une liste vide, qui déclarerait toutes
            les destinations absentes.
        groupes_existants: même rôle, pour les adresses de groupe.
    """
    destination = normaliser_ou(ou_destination)
    a_ajouter = [a for a in (normaliser_adresse(g) for g in (groupes_ajouter or [])) if a]
    a_retirer = [a for a in (normaliser_adresse(g) for g in (groupes_retirer or [])) if a]

    plan = PlanManuel(
        ou_destination=destination,
        groupes_ajouter=a_ajouter,
        groupes_retirer=a_retirer,
    )

    # Une même adresse des deux côtés s'annulerait elle-même, dans un ordre
    # que rien ne fixe. On l'écarte en le disant, plutôt que de trancher.
    contradictoires = sorted(set(a_ajouter) & set(a_retirer))
    for g in contradictoires:
        plan.avertissements.append(
            f"{g} est demandé à la fois en entrée et en sortie — ignoré."
        )
    a_ajouter = [g for g in a_ajouter if g not in contradictoires]
    a_retirer = [g for g in a_retirer if g not in contradictoires]
    plan.groupes_ajouter, plan.groupes_retirer = a_ajouter, a_retirer

    if destination and ou_existantes is not None:
        connues = {normaliser_ou(o) for o in ou_existantes}
        if destination not in connues:
            plan.destinations_absentes.append(destination)
    if groupes_existants is not None:
        connus = {normaliser_adresse(g) for g in groupes_existants}
        for g in a_ajouter + a_retirer:
            if g not in connus:
                plan.destinations_absentes.append(g)

    plan.etats = relever_etats(
        session,
        personne_ids,
        etat_google=etat_google,
        groupes_par_email=groupes_par_email,
        groupes_complets=groupes_complets,
        annee_id=annee_id,
    )
    plan.ecartes = [e for e in plan.etats if e.motif]

    # Sans destination il n'y a rien à calculer — mais l'état relevé, lui,
    # vaut d'être rendu : ouvrir une fiche, c'est d'abord demander « où
    # est-il rangé, aujourd'hui ? ». Sortir ici les mains vides obligerait
    # à inventer une destination pour obtenir la réponse.
    if destination is None and not a_ajouter and not a_retirer:
        plan.avertissements.append(
            "Aucune destination : ni OU, ni groupe à rejoindre ou à quitter."
        )
        return plan

    # Une destination manquante rend le plan inexécutable, mais on calcule
    # tout de même les mouvements : l'aperçu montre alors ce qui serait fait
    # une fois l'OU ou le groupe créé, au lieu d'une page vide.
    for e in plan.etats:
        if e.motif:
            continue
        if e.suspendu:
            plan.avertissements.append(
                f"{e.libelle} : compte suspendu — le déplacement aboutira, "
                "mais le compte restera inutilisable."
            )
        if destination:
            if e.ou_actuelle == destination:
                plan.nb_deja_en_place += 1
            else:
                depuis = e.ou_actuelle or "(sans OU)"
                plan.mouvements.append(
                    MouvementManuel(
                        action="deplacer",
                        personne_id=e.personne_id,
                        email=e.email,
                        ou_visee=destination,
                        libelle=f"{e.libelle} : {depuis} → {destination}",
                    )
                )
        for g in a_ajouter:
            if g in e.groupes_actuels:
                continue
            plan.mouvements.append(
                MouvementManuel(
                    action="ajouter_groupe",
                    personne_id=e.personne_id,
                    email=e.email,
                    groupe=g,
                    libelle=f"{e.libelle} : entre dans {g}",
                )
            )
        for g in a_retirer:
            # Sans relevé d'appartenance on ne peut pas savoir qui est
            # membre : on tente la sortie, Google refusera sans dommage.
            if groupes_par_email is not None and g not in e.groupes_actuels:
                continue
            plan.mouvements.append(
                MouvementManuel(
                    action="retirer_groupe",
                    personne_id=e.personne_id,
                    email=e.email,
                    groupe=g,
                    libelle=f"{e.libelle} : sort de {g}",
                )
            )

    if plan.ecartes:
        plan.avertissements.append(
            f"{len(plan.ecartes)} personne(s) écartée(s) — voir le détail."
        )
    if not plan.mouvements and not plan.destinations_absentes:
        plan.avertissements.append(
            "Rien à faire : tout le monde est déjà là où vous le demandez."
        )
    return plan
