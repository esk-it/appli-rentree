"""Ce que chaque système dit d'une personne — la concordance à l'unité.

## Pourquoi cet écran manquait

La Concordance croise quatre sources pour toute une population. Mais la
question qu'on se pose vraiment est presque toujours nominative : *« Justine
GUEGUEN a 99840 chez Charlemagne et 97620 dans KoXo, pourquoi ? »*,
*« pourquoi Azilys LAMBLIN a-t-elle deux comptes ? »*, *« où est passé
ABAGIU Ion ? »*. Y répondre demandait d'ouvrir quatre écrans, ou d'écrire
un script.

Ici, on part de la personne et on demande à chaque source ce qu'elle en
sait.

## Deux sources répondent tout de suite, trois demandent un fichier

Le référentiel est local. Google s'interroge en deux appels pour une seule
personne — c'est peu, et la réponse vaut le délai.

Charlemagne, KoXo et TS1000 n'ont pas d'API : leur état ne se lit que dans
un export. Plutôt que d'afficher des cases vides qu'on prendrait pour des
absences, l'enquête **dit explicitement** qu'elle n'a pas regardé, et par
quel écran on va voir.

## Le verdict porte sur ce qu'on a vu

Une divergence ne se prononce qu'entre deux sources réellement lues. Dire
« tout concorde » alors que trois systèmes n'ont pas été interrogés serait
le genre de silence qui a laissé quarante-quatre élèves dans la mauvaise
classe pendant deux semaines.
"""
from __future__ import annotations

from dataclasses import dataclass, field

from sqlalchemy.orm import Session

from backend.models import (
    AnneeScolaire,
    CompteCible,
    Personne,
    SecretConserve,
    Snapshot,
    TableCorrespondance,
)

SOURCES_SUR_FICHIER = {
    "charlemagne": ("Concordance", "un export Charlemagne"),
    "koxo": ("Contrôle KoXo", "un export KoXo"),
    "ts1000": ("Badges et accès", "l'export de la centrale"),
}


@dataclass
class DireDeSource:
    """Ce qu'une source dit — ou pourquoi elle n'a rien dit."""

    source: str
    consultee: bool
    valeurs: dict[str, str | None] = field(default_factory=dict)
    motif: str | None = None
    """Renseigné quand `consultee` est faux. Jamais vide dans ce cas."""


@dataclass
class Divergence:
    quoi: str
    entre: tuple[str, str]
    valeurs: tuple[str | None, str | None]
    gravite: str = "attention"


@dataclass
class Enquete:
    personne_id: int
    libelle: str
    cle_pivot: str | None = None
    badge: int | None = None
    login: str | None = None
    adresse: str | None = None
    adresse_constatee: bool = False

    dires: list[DireDeSource] = field(default_factory=list)
    divergences: list[Divergence] = field(default_factory=list)

    @property
    def sources_consultees(self) -> list[str]:
        return [d.source for d in self.dires if d.consultee]

    @property
    def tout_concorde(self) -> bool:
        """Vrai seulement si deux sources au moins ont parlé sans se contredire."""
        return not self.divergences and len(self.sources_consultees) >= 2


def _classe_de_lannee(
    session: Session, personne_id: int, annee_id: int | None
) -> tuple[str | None, str | None]:
    """`(classe, libellé de l'année)` pour l'année demandée, ou la plus récente."""
    q = session.query(Snapshot, AnneeScolaire).join(
        AnneeScolaire, Snapshot.annee_scolaire_id == AnneeScolaire.id
    ).filter(Snapshot.personne_id == personne_id)
    if annee_id is not None:
        q = q.filter(Snapshot.annee_scolaire_id == annee_id)
    lignes = q.all()
    if not lignes:
        return None, None
    sn, an = max(
        lignes, key=lambda couple: (couple[1].libelle, couple[0].date_ingestion or "")
    )
    return (sn.classe or None), an.libelle


def _ou_attendue(session: Session, personne: Personne, classe: str | None) -> str | None:
    """Là où la Table dit que cette personne devrait être rangée."""
    if not classe or personne.site_id is None:
        return None
    t = (
        session.query(TableCorrespondance)
        .filter_by(site_id=personne.site_id, classe_code_court=classe)
        .one_or_none()
    )
    return t.ou_definitive if t else None


def enqueter(
    session: Session,
    personne_id: int,
    *,
    annee_id: int | None = None,
    etat_google: dict | None = None,
    groupes_google: list[str] | None = None,
    motif_google: str | None = None,
) -> Enquete:
    """Réunit ce que chaque source dit de cette personne.

    Args:
        etat_google: ce que l'annuaire rend, ou `None` s'il n'a pas été
            interrogé. Fourni de l'extérieur : ce module ne va jamais sur
            le réseau lui-même, pour rester testable sans annuaire.
        motif_google: pourquoi Google n'a pas été consulté, le cas échéant.
    """
    personne = session.query(Personne).filter_by(id=personne_id).one_or_none()
    if personne is None:
        raise ValueError(f"Personne {personne_id} introuvable")

    classe, annee_libelle = _classe_de_lannee(session, personne_id, annee_id)
    adresse = (personne.email_constate or personne.email_attribuee or "").strip() or None

    enquete = Enquete(
        personne_id=personne_id,
        libelle=f"{personne.nom} {personne.prenom}".strip(),
        cle_pivot=getattr(personne, "cle_pivot", None),
        badge=personne.badge,
        login=personne.login,
        adresse=adresse or (personne.email or None),
        adresse_constatee=bool(personne.email_constate),
    )

    ou_attendue = _ou_attendue(session, personne, classe)
    enquete.dires.append(
        DireDeSource(
            source="referentiel",
            consultee=True,
            valeurs={
                "classe": classe,
                "annee": annee_libelle,
                "site": personne.site.nom if personne.site else None,
                "login": personne.login,
                "badge": str(personne.badge) if personne.badge else None,
                "adresse": enquete.adresse,
                "ou_attendue": ou_attendue,
            },
        )
    )

    # --- Google ---
    compte = (
        session.query(CompteCible)
        .filter_by(personne_id=personne_id, cible="google")
        .one_or_none()
    )
    if etat_google is None:
        enquete.dires.append(
            DireDeSource(
                source="google",
                consultee=False,
                motif=motif_google or "L'annuaire n'a pas été interrogé.",
                valeurs={
                    "ou_appliquee": compte.ou_appliquee if compte else None,
                    "etat_memorise": compte.etat if compte else None,
                },
            )
        )
    elif not etat_google.get("existe", True):
        enquete.dires.append(
            DireDeSource(
                source="google",
                consultee=True,
                valeurs={"compte": None},
                motif="Aucun compte à cette adresse.",
            )
        )
    else:
        ou_reelle = (etat_google.get("ou") or "").rstrip("/") or None
        enquete.dires.append(
            DireDeSource(
                source="google",
                consultee=True,
                valeurs={
                    "ou": ou_reelle,
                    "suspendu": "oui" if etat_google.get("suspendu") else "non",
                    "derniere_connexion": (etat_google.get("derniere_connexion") or "")[:10]
                    or None,
                    "groupes": ", ".join(groupes_google or []) or None,
                    "ou_appliquee": compte.ou_appliquee if compte else None,
                },
            )
        )
        if ou_attendue and ou_reelle and ou_reelle != ou_attendue.rstrip("/"):
            enquete.divergences.append(
                Divergence(
                    quoi="Unité d'organisation",
                    entre=("referentiel", "google"),
                    valeurs=(ou_attendue, ou_reelle),
                    gravite="attention",
                )
            )
        if etat_google.get("suspendu") and classe:
            enquete.divergences.append(
                Divergence(
                    quoi="Compte suspendu alors que l'élève est inscrit",
                    entre=("referentiel", "google"),
                    valeurs=(classe, "suspendu"),
                    gravite="bloquant",
                )
            )

        # Un compte bien rangé et jamais ouvert veut souvent dire que la
        # personne en utilise un autre. C'est ainsi qu'on a découvert, en
        # septembre 2026, que trois élèves montés de NDE travaillaient encore
        # sur leur ancien compte — lequel allait partir en OU de sortie.
        vu = (etat_google.get("derniere_connexion") or "")[:10]
        if classe and vu in ("", "1970-01-01"):
            enquete.divergences.append(
                Divergence(
                    quoi="Compte jamais ouvert",
                    entre=("referentiel", "google"),
                    valeurs=(classe, "aucune connexion"),
                    gravite="information",
                )
            )

    # --- Le coffre : ce qu'on sait du mot de passe KoXo ---
    secret = (
        session.query(SecretConserve)
        .filter_by(personne_id=personne_id, cible="koxo")
        .order_by(SecretConserve.id.desc())
        .first()
    )
    enquete.dires.append(
        DireDeSource(
            source="coffre",
            consultee=True,
            valeurs={
                "mot_de_passe_connu": "oui" if secret else "non",
                "depose_le": (
                    secret.date_maj.date().isoformat()
                    if secret and getattr(secret, "date_maj", None)
                    else None
                ),
            },
        )
    )

    # --- Ce qui ne se lit que dans un fichier ---
    for source, (ecran, quoi) in SOURCES_SUR_FICHIER.items():
        enquete.dires.append(
            DireDeSource(
                source=source,
                consultee=False,
                motif=f"Ne se constate que depuis {quoi} — écran « {ecran} ».",
            )
        )

    return enquete
