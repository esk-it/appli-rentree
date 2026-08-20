"""Synchronisation des groupes de classe Google.

## Ce que l'export CSV ne fait pas

Le fichier de groupes **ajoute** des membres. Il n'en retire aucun. Un
groupe de 3e conserve donc ses élèves année après année : ceux de l'an
dernier, ceux d'avant, et les partis. Au fil des rentrées, écrire au
« groupe des 3e » touche des promotions entières qui ont quitté
l'établissement.

L'API permet la seule opération qui vaille ici : une **différence** —
qui doit entrer, qui doit sortir — appliquée aux deux sens.

## Ce que le programme considère comme la vérité

L'appartenance découle de la classe du snapshot de l'année préparée, via
l'adresse de groupe déclarée dans la Table de correspondance. Un élève
sans adresse de groupe pour sa classe n'est pas synchronisé : la Table
est incomplète, et l'inventer serait pire que de ne rien faire.

## Prudence sur les retraits

Un membre présent dans le groupe mais absent de l'année préparée est
proposé au retrait. Cela recouvre les partants, mais aussi tout compte
ajouté à la main hors du référentiel — un professeur, une adresse de
service. Ceux-là sont listés à part et ne sont **jamais** retirés
d'office : le programme ne connaît pas la raison de leur présence.

## Groupe déclaré mais inexistant

Une adresse peut figurer dans la Table sans qu'aucun groupe ne porte ce
nom dans Google — faute de frappe, groupe jamais créé, groupe supprimé.
Un groupe **vide** et un groupe **absent** se ressemblent : tous deux
n'ont aucun membre. Ils n'appellent pourtant pas la même chose. Remplir
un groupe vide fonctionne ; écrire dans un groupe absent échoue élève
par élève, sans que rien ne l'ait annoncé.

Le programme distingue donc les deux et retient les ajouts destinés à un
groupe absent : il les annonce au lieu de les tenter. Créer le groupe, ou
corriger l'adresse dans la Table, est une décision qui revient à
l'utilisateur — le nom et les réglages d'un groupe ne se devinent pas.

## Site sans aucun élève

Une classe vide est banale : elle a fermé. Un **site entier** sans élève
pour l'année préparée ne l'est pas — il signale un export Charlemagne qui
n'a pas été chargé. Sans avertissement, la synchronisation le traverse
sans rien faire et sans rien dire, et l'oubli ne se découvre qu'à la
rentrée, quand les groupes de ce site sont restés vides.
"""
from __future__ import annotations

from dataclasses import dataclass, field

from sqlalchemy.orm import Session

from backend.models import Personne, Site, Snapshot, TableCorrespondance
from backend.services.regles_metier import calculer_email


@dataclass
class DiffGroupe:
    groupe: str
    classe: str
    site: str | None

    a_ajouter: list[str] = field(default_factory=list)
    a_retirer: list[str] = field(default_factory=list)
    """Membres connus du référentiel, absents de l'année préparée."""
    inconnus: list[str] = field(default_factory=list)
    """Membres qu'aucune personne du référentiel ne porte : profs, adresses
    de service, ajouts manuels. Jamais retirés d'office."""
    deja_membres: int = 0
    existe: bool = True
    """Faux si Google ne connaît pas ce groupe. Ses ajouts sont retenus."""
    retenus: list[str] = field(default_factory=list)
    """Ajouts qui auraient eu lieu si le groupe existait."""

    @property
    def nb_mouvements(self) -> int:
        return len(self.a_ajouter) + len(self.a_retirer)


@dataclass
class GroupeACreer:
    adresse: str
    nom: str
    description: str
    classe: str
    site: str | None
    nb_membres_attendus: int


@dataclass
class RapportGroupes:
    annee_libelle: str
    diffs: list[DiffGroupe] = field(default_factory=list)
    classes_sans_groupe: list[str] = field(default_factory=list)
    sites_sans_eleve: list[str] = field(default_factory=list)
    avertissements: list[str] = field(default_factory=list)

    @property
    def nb_a_ajouter(self) -> int:
        return sum(len(d.a_ajouter) for d in self.diffs)

    @property
    def nb_a_retirer(self) -> int:
        return sum(len(d.a_retirer) for d in self.diffs)

    @property
    def nb_inconnus(self) -> int:
        return sum(len(d.inconnus) for d in self.diffs)

    @property
    def groupes_absents(self) -> list[str]:
        return [d.groupe for d in self.diffs if not d.existe]

    @property
    def nb_retenus(self) -> int:
        """Ajouts empêchés par l'absence du groupe dans Google."""
        return sum(len(d.retenus) for d in self.diffs)


def groupes_a_creer(session: Session, rapport: RapportGroupes) -> list[GroupeACreer]:
    """Les groupes absents de Google, avec de quoi les créer.

    Le nom vient du libellé long de la Table : c'est ce qui s'affichera dans
    la console Google, où `2_1` ne dit rien à personne. La description note
    l'origine, pour qu'un administrateur qui tombe dessus dans trois ans sache
    d'où le groupe vient.

    Deux classes partagent parfois un libellé long — `TERMINALE G5` pour les
    groupes `term-g5a` et `term-g5b`. Leur donner le même nom rendrait la
    console illisible, alors que ce sont deux listes distinctes : le code
    court les départage dans ce cas, et dans ce cas seulement.
    """
    if not rapport.groupes_absents:
        return []

    libelles: dict[str, tuple[str, str | None, str]] = {}
    sites = {s.id: s.nom for s in session.query(Site).all()}
    for tc in session.query(TableCorrespondance).all():
        adresse = (tc.groupe_google or "").strip().lower()
        if adresse:
            libelles[adresse] = (
                tc.classe_charlemagne_long or tc.classe_code_court,
                sites.get(tc.site_id),
                tc.classe_code_court,
            )

    # Un nom revendiqué par plusieurs classes doit être désambiguïsé.
    comptes: dict[tuple[str, str | None], int] = {}
    for libelle, site, _ in libelles.values():
        comptes[(libelle, site)] = comptes.get((libelle, site), 0) + 1

    par_adresse = {d.groupe: d for d in rapport.diffs}
    creations: list[GroupeACreer] = []
    for adresse in rapport.groupes_absents:
        libelle, site, code = libelles.get(adresse, (adresse, None, "?"))
        nom = f"{libelle} ({site})" if site else libelle
        if comptes.get((libelle, site), 0) > 1:
            nom = f"{nom} — {code}"
        d = par_adresse.get(adresse)
        creations.append(
            GroupeACreer(
                adresse=adresse,
                nom=nom,
                description=(
                    f"Groupe de la classe {d.classe if d else '?'} — "
                    f"{rapport.annee_libelle}. Créé par Appli Rentrée."
                ),
                classe=d.classe if d else "?",
                site=site,
                nb_membres_attendus=len(d.retenus) if d else 0,
            )
        )
    # Un groupe qui débloque des élèves passe devant : c'est celui dont
    # l'absence coûte quelque chose aujourd'hui.
    creations.sort(key=lambda c: (-c.nb_membres_attendus, c.adresse))
    return creations


def calculer_diff_groupes(
    session: Session,
    membres_actuels: dict[str, list[str] | None],
    *,
    annee_id: int,
    site_id: int | None = None,
) -> RapportGroupes:
    """Compare l'appartenance voulue à l'appartenance réelle.

    Args:
        membres_actuels: `{adresse du groupe: [adresses des membres]}`,
            relevé par `ClientGoogle.lister_membres`. La valeur `None`
            signale un groupe que Google ne connaît pas — distinct d'un
            groupe vide, qui vaut `[]`.
        annee_id: année préparée — c'est elle qui définit la composition.
    """
    from backend.models import AnneeScolaire

    annee = session.query(AnneeScolaire).filter_by(id=annee_id).one_or_none()
    if annee is None:
        raise ValueError(f"Année introuvable : {annee_id}")

    rapport = RapportGroupes(annee_libelle=annee.libelle)
    sites = {s.id: s for s in session.query(Site).all()}

    tcs = session.query(TableCorrespondance)
    if site_id is not None:
        tcs = tcs.filter(TableCorrespondance.site_id == site_id)
    tcs = tcs.all()

    # Snapshot le plus récent de chaque élève pour l'année préparée
    derniers: dict[int, Snapshot] = {}
    personnes: dict[int, Personne] = {}
    q = (
        session.query(Personne, Snapshot)
        .join(Snapshot, Snapshot.personne_id == Personne.id)
        .filter(Snapshot.annee_scolaire_id == annee_id, Personne.type == "eleve")
    )
    for p, sn in q.all():
        prec = derniers.get(p.id)
        if prec is None or sn.date_ingestion > prec.date_ingestion:
            derniers[p.id] = sn
            personnes[p.id] = p

    def adresse(p: Personne) -> str | None:
        if p.email_constate:
            return p.email_constate.strip().lower()
        site = sites.get(p.site_id) if p.site_id else None
        if site is None:
            return None
        return (calculer_email(p.prenom, p.nom, site.domaine_mail) or "").lower() or None

    # Toutes les adresses connues du référentiel, pour distinguer un partant
    # d'un compte ajouté à la main.
    connues: set[str] = set()
    for p in session.query(Personne).all():
        a = adresse(p)
        if a:
            connues.add(a)
        if p.email_constate:
            connues.add(p.email_constate.strip().lower())

    par_classe: dict[str, set[str]] = {}
    for pid, sn in derniers.items():
        a = adresse(personnes[pid])
        if a and sn.classe:
            par_classe.setdefault(sn.classe, set()).add(a)

    for tc in tcs:
        groupe = (tc.groupe_google or "").strip().lower()
        if not groupe:
            if tc.classe_code_court in par_classe:
                rapport.classes_sans_groupe.append(tc.classe_code_court)
            continue

        voulus = par_classe.get(tc.classe_code_court, set())
        releve = membres_actuels.get(groupe, [])
        existe = releve is not None
        actuels = {m.lower() for m in (releve or [])}

        a_retirer, inconnus = [], []
        for m in sorted(actuels - voulus):
            (a_retirer if m in connues else inconnus).append(m)

        manquants = sorted(voulus - actuels)
        rapport.diffs.append(
            DiffGroupe(
                groupe=groupe,
                classe=tc.classe_code_court,
                site=sites[tc.site_id].nom if tc.site_id in sites else None,
                a_ajouter=manquants if existe else [],
                a_retirer=a_retirer,
                inconnus=inconnus,
                deja_membres=len(voulus & actuels),
                existe=existe,
                retenus=[] if existe else manquants,
            )
        )

    # Un site dont pas une classe n'a d'élève : l'export manque.
    peuples: dict[str, bool] = {}
    for tc in tcs:
        nom = sites[tc.site_id].nom if tc.site_id in sites else None
        if nom is None:
            continue
        peuples[nom] = peuples.get(nom, False) or bool(
            par_classe.get(tc.classe_code_court)
        )
    rapport.sites_sans_eleve = sorted(n for n, ok in peuples.items() if not ok)

    rapport.diffs.sort(key=lambda d: (d.site or "", d.classe))
    if rapport.sites_sans_eleve:
        rapport.avertissements.append(
            "Aucun élève pour l'année préparée sur : "
            + ", ".join(rapport.sites_sans_eleve)
            + ". Leurs groupes ne seront pas touchés — l'export Charlemagne de "
            "ce ou ces sites n'a probablement pas été chargé."
        )
    if absents := rapport.groupes_absents:
        rapport.avertissements.append(
            f"{len(absents)} groupe(s) déclarés dans la Table n'existent pas "
            f"dans Google : {rapport.nb_retenus} ajout(s) sont retenus. "
            "Créer ces groupes dans la console, ou corriger leur adresse dans "
            "la Table — les tenter échouerait élève par élève."
        )
    if rapport.classes_sans_groupe:
        rapport.avertissements.append(
            f"{len(rapport.classes_sans_groupe)} classe(s) ont des élèves mais "
            "aucune adresse de groupe dans la Table : elles ne sont pas "
            "synchronisées."
        )
    if rapport.nb_inconnus:
        rapport.avertissements.append(
            f"{rapport.nb_inconnus} membre(s) ne correspondent à personne du "
            "référentiel — enseignants, adresses de service, ajouts manuels. "
            "Ils sont laissés en place : le programme ignore pourquoi ils sont là."
        )
    return rapport
