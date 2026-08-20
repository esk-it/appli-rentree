"""Inspection d'une branche d'OU Google, recoupée avec le référentiel.

## À quoi ça sert

Une arborescence d'OU accumule les restes : un élève parti que personne
n'a déplacé, une classe entière oubliée lors d'une rotation, un compte
créé à la main hors de tout processus. Rien dans Google ne dit *pourquoi*
un compte est là — il faut confronter la liste à ce que l'on sait des
personnes.

Ce service répond à « qui sont ces gens ? » : pour chaque compte trouvé
dans une branche, il cherche la personne au référentiel et rend son
histoire — sa dernière année connue, sa classe d'alors, et si elle est
encore inscrite aujourd'hui.

## Ce qu'il ne fait pas

Rien d'autre que lire. Aucun déplacement, aucune suspension : constater
d'abord, décider ensuite.
"""
from __future__ import annotations

from dataclasses import dataclass, field

from sqlalchemy.orm import Session

from backend.models import AnneeScolaire, Personne, Site, Snapshot
from backend.services.regles_metier import calculer_email, normaliser_nom

# Ce qu'on peut dire d'un compte trouvé dans une branche
INCONNU = "inconnu"
"""Aucune personne au référentiel ne porte cette adresse."""
ENCORE_INSCRIT = "encore_inscrit"
"""Présent dans l'année la plus récente : sa place est normale."""
SORTI = "sorti"
"""Connu, mais absent de l'année la plus récente : reste d'une promotion."""


@dataclass
class CompteTrouve:
    email: str
    ou: str
    suspendu: bool
    nom_google: str
    prenom_google: str
    derniere_connexion: str | None

    statut: str
    personne_id: int | None = None
    """Sans lui, un déplacement réussi ne peut être reporté au référentiel."""
    cle_pivot: str | None = None
    nom: str | None = None
    prenom: str | None = None
    derniere_annee: str | None = None
    """Dernière année scolaire où la personne apparaît dans un export."""
    derniere_classe: str | None = None
    apparie_par: str | None = None
    """`adresse`, `nom`, ou `None` si la personne n'a pas été retrouvée.
    Un rapprochement par nom est moins sûr : il mérite un œil humain."""


@dataclass
class RapportInspection:
    prefixe_ou: str
    annee_reference: str | None = None

    nb_total: int = 0
    comptes: list[CompteTrouve] = field(default_factory=list)

    @property
    def nb_sortis(self) -> int:
        return sum(1 for c in self.comptes if c.statut == SORTI)

    @property
    def nb_encore_inscrits(self) -> int:
        return sum(1 for c in self.comptes if c.statut == ENCORE_INSCRIT)

    @property
    def nb_inconnus(self) -> int:
        return sum(1 for c in self.comptes if c.statut == INCONNU)


def recouper_avec_referentiel(
    session: Session, comptes: list[dict], *, prefixe_ou: str
) -> RapportInspection:
    """Attribue une identité et une histoire à chaque compte trouvé.

    `comptes` vient de `ClientGoogle.lister_utilisateurs` : des dicts avec
    `email`, `ou`, `suspendu`, `nom`, `prenom`, `derniere_connexion`.
    """
    annees = session.query(AnneeScolaire).all()
    if not annees:
        recente = None
    else:
        recente = max(annees, key=lambda a: a.libelle)

    rapport = RapportInspection(
        prefixe_ou=prefixe_ou,
        annee_reference=recente.libelle if recente else None,
    )

    # Trois passes de rapprochement, de la plus sûre à la plus faible.
    #
    # L'adresse seule ne suffit pas : sur l'instance réelle, quatre élèves
    # inscrits portent dans Charlemagne une adresse qui n'existe pas dans
    # Google — `louis.legall@` contre `louis.le.gall@`, une faute de frappe
    # sur `ralavao`, un suffixe d'homonymie qui diffère. L'un d'eux se
    # trouvait dans une branche à vider : s'en tenir à l'adresse l'aurait
    # fait suspendre alors qu'il fait sa rentrée.
    par_email: dict[str, Personne] = {}
    par_nom: dict[tuple[str, str], list[Personne]] = {}
    domaines = [s.domaine_mail for s in session.query(Site).all() if s.domaine_mail]

    calcules: dict[str, list[Personne]] = {}
    for p in session.query(Personne).all():
        if p.email_constate:
            par_email[p.email_constate.strip().lower()] = p
        for d in domaines:
            calcule = calculer_email(p.prenom, p.nom, d)
            if calcule:
                calcules.setdefault(calcule.lower(), []).append(p)
        par_nom.setdefault(
            (normaliser_nom(p.nom), normaliser_nom(p.prenom)), []
        ).append(p)

    # Une adresse calculée ne vaut que si elle ne désigne qu'une personne :
    # deux homonymes produisent la même, et en retenir une au hasard
    # attribuerait un compte à la mauvaise. Elle ne prime jamais sur une
    # adresse constatée.
    for adresse, candidats in calcules.items():
        if len(candidats) == 1:
            par_email.setdefault(adresse, candidats[0])

    libelles = {a.id: a.libelle for a in annees}
    ids_recents: set[int] = set()
    if recente is not None:
        ids_recents = {
            pid
            for (pid,) in session.query(Snapshot.personne_id)
            .filter(Snapshot.annee_scolaire_id == recente.id)
            .distinct()
            .all()
        }

    # Dernière année vue par personne, en une passe plutôt qu'une requête
    # par compte : la branche peut contenir plusieurs centaines de lignes.
    derniere_par_personne: dict[int, tuple[str, str | None]] = {}
    for pid, annee_id, classe in session.query(
        Snapshot.personne_id, Snapshot.annee_scolaire_id, Snapshot.classe
    ).all():
        libelle = libelles.get(annee_id, "")
        precedent = derniere_par_personne.get(pid)
        if precedent is None or libelle > precedent[0]:
            derniere_par_personne[pid] = (libelle, classe)

    for c in comptes:
        email = (c.get("email") or "").strip().lower()
        personne = par_email.get(email)
        apparie_par = "adresse" if personne else None
        if personne is None:
            # Repli sur le nom, et seulement s'il ne désigne qu'une personne :
            # deux homonymes rendraient l'attribution arbitraire.
            candidats = par_nom.get(
                (normaliser_nom(c.get("nom")), normaliser_nom(c.get("prenom"))), []
            )
            if len(candidats) == 1:
                personne = candidats[0]
                apparie_par = "nom"

        if personne is None:
            statut = INCONNU
        elif personne.id in ids_recents:
            statut = ENCORE_INSCRIT
        else:
            statut = SORTI

        derniere = derniere_par_personne.get(personne.id) if personne else None
        rapport.comptes.append(
            CompteTrouve(
                email=email,
                ou=c.get("ou") or "",
                suspendu=bool(c.get("suspendu")),
                nom_google=c.get("nom") or "",
                prenom_google=c.get("prenom") or "",
                derniere_connexion=c.get("derniere_connexion"),
                statut=statut,
                personne_id=personne.id if personne else None,
                cle_pivot=personne.cle_pivot if personne else None,
                nom=personne.nom if personne else None,
                prenom=personne.prenom if personne else None,
                derniere_annee=derniere[0] if derniere else None,
                derniere_classe=derniere[1] if derniere else None,
                apparie_par=apparie_par,
            )
        )

    rapport.comptes.sort(key=lambda c: (c.ou, c.nom_google, c.prenom_google))
    rapport.nb_total = len(rapport.comptes)
    return rapport
