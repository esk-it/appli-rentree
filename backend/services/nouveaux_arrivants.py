"""Liste des nouveaux arrivants — destinée à une relecture humaine.

## Pourquoi un service à part

`reconciliation` sait déjà classer une personne en « nouveau », mais en
comparant **deux années ingérées**. La première année, cette comparaison
n'a pas d'année de référence et ne peut rien produire — alors que c'est
précisément l'année où l'on a le plus besoin de vérifier les entrants.

Les exports KoXo/Google savent aussi filtrer sur `nouveaux`, mais ils
produisent des fichiers machine : colonnes techniques, ordre imposé par
la cible. Illisible pour un collègue à qui l'on demande « est-ce que ces
données sont bonnes ? ».

## Comment un nouvel arrivant est reconnu

Deux signaux **indépendants**, croisés :

1. **Aucun compte constaté** (`Personne.email_constate` vide) — personne
   ne lui a jamais ouvert d'adresse.
2. **Aucune classe précédente** (`Snapshot.classe_precedente` vide) —
   Charlemagne ne lui connaît pas de scolarité l'an dernier.

Un troisième signal s'ajoute quand une année de référence est fournie :
absence de snapshot dans cette année.

Sur l'export réel de la rentrée 2026, les deux premiers signaux
concordent sur 405 élèves et divergent sur 3. Cette poignée de
divergences n'est pas du bruit : ce sont les cas intéressants — un élève
qui poursuit sa scolarité sans compte, un élève réinscrit après une
absence. Ils sont donc listés eux aussi, marqués `a_verifier` avec le
motif, plutôt que tranchés par une règle arbitraire (§ « un cas ambigu
n'est jamais résolu par une heuristique »).

Le service est en **lecture seule**.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date

from sqlalchemy.orm import Session

from backend.models import AnneeScolaire, Personne, Site, Snapshot
from backend.services.regles_metier import calculer_email

STATUTS = ("nouveau", "a_verifier")


@dataclass
class NouvelArrivant:
    """Une personne à relire, avec de quoi la reconnaître sur papier."""

    personne_id: int
    cle_pivot: str
    type: str
    badge: int
    nom: str
    prenom: str
    classe: str | None
    niveau: str | None
    site: str | None
    regime: str | None
    login: str
    email: str | None
    """Adresse qui sera créée (ou celle déjà constatée, si le cas est ambigu)."""
    date_entree: date | None
    classe_precedente: str | None

    statut: str
    """`nouveau` (signaux concordants) ou `a_verifier` (signaux divergents)."""
    motif: str
    """Phrase courte expliquant le classement — imprimée telle quelle."""


@dataclass
class RapportNouveaux:
    annee_libelle: str
    annee_source_libelle: str | None = None

    nb_nouveaux: int = 0
    nb_a_verifier: int = 0

    arrivants: list[NouvelArrivant] = field(default_factory=list)

    @property
    def nb_total(self) -> int:
        return len(self.arrivants)


def lister_nouveaux_arrivants(
    session: Session,
    *,
    annee_id: int,
    site_id: int | None = None,
    type_personne: str | None = None,
    annee_source_id: int | None = None,
    inclure_a_verifier: bool = True,
) -> RapportNouveaux:
    """Liste les personnes à créer pour l'année `annee_id`.

    Args:
        annee_id: année de rentrée à préparer.
        site_id: restreint à un site. `None` = tous.
        type_personne: `eleve` / `adulte`. `None` = les deux.
        annee_source_id: année de référence, quand elle existe. Ajoute un
            troisième signal (absence de snapshot l'an dernier).
        inclure_a_verifier: garde les cas aux signaux divergents. Les
            exclure donne une liste plus courte mais fait disparaître
            précisément ceux qui méritent une relecture.
    """
    annee = session.query(AnneeScolaire).filter_by(id=annee_id).one_or_none()
    if annee is None:
        raise ValueError(f"Année introuvable : {annee_id}")

    source = None
    if annee_source_id is not None:
        source = session.query(AnneeScolaire).filter_by(id=annee_source_id).one_or_none()
        if source is None:
            raise ValueError(f"Année source introuvable : {annee_source_id}")

    rapport = RapportNouveaux(
        annee_libelle=annee.libelle,
        annee_source_libelle=source.libelle if source else None,
    )

    ids_annee_source: set[int] = set()
    if source is not None:
        ids_annee_source = {
            pid
            for (pid,) in session.query(Snapshot.personne_id)
            .filter(Snapshot.annee_scolaire_id == annee_source_id)
            .distinct()
            .all()
        }

    noms_sites = {s.id: s.nom for s in session.query(Site).all()}
    domaines = {s.id: s.domaine_mail for s in session.query(Site).all()}

    for personne, snapshot in _derniers_snapshots(
        session, annee_id, site_id, type_personne
    ):
        arrivant = _classer(
            personne,
            snapshot,
            noms_sites=noms_sites,
            domaines=domaines,
            source_connue=source is not None,
            present_annee_source=personne.id in ids_annee_source,
        )
        if arrivant is None:
            continue
        if arrivant.statut == "a_verifier" and not inclure_a_verifier:
            continue
        rapport.arrivants.append(arrivant)

    rapport.arrivants.sort(
        key=lambda a: (a.site or "", a.classe or "", a.nom, a.prenom)
    )
    rapport.nb_nouveaux = sum(1 for a in rapport.arrivants if a.statut == "nouveau")
    rapport.nb_a_verifier = sum(1 for a in rapport.arrivants if a.statut == "a_verifier")
    return rapport


# ---------------------------------------------------------------------------
# Interne
# ---------------------------------------------------------------------------


def _derniers_snapshots(
    session: Session,
    annee_id: int,
    site_id: int | None,
    type_personne: str | None,
) -> list[tuple[Personne, Snapshot]]:
    """Le snapshot le plus récent de chaque personne pour l'année donnée.

    Une réingestion crée un second snapshot : sans ce filtrage, la même
    personne apparaîtrait deux fois sur la liste imprimée.
    """
    q = (
        session.query(Personne, Snapshot)
        .join(Snapshot, Snapshot.personne_id == Personne.id)
        .filter(Snapshot.annee_scolaire_id == annee_id)
    )
    if site_id is not None:
        q = q.filter(Personne.site_id == site_id)
    if type_personne is not None:
        q = q.filter(Personne.type == type_personne)

    retenus: dict[int, tuple[Personne, Snapshot]] = {}
    for p, s in q.all():
        precedent = retenus.get(p.id)
        if precedent is None or s.date_ingestion > precedent[1].date_ingestion:
            retenus[p.id] = (p, s)
    return list(retenus.values())


def _classer(
    personne: Personne,
    snapshot: Snapshot,
    *,
    noms_sites: dict[int, str],
    domaines: dict[int, str],
    source_connue: bool,
    present_annee_source: bool,
) -> NouvelArrivant | None:
    """Retourne l'arrivant, ou `None` si la personne n'est pas concernée."""
    sans_compte = not personne.email_constate
    sans_classe_prec = not (snapshot.classe_precedente or "").strip()

    if source_connue:
        # L'année de référence tranche : elle dit factuellement qui était
        # déjà là. Les deux autres signaux servent alors à qualifier.
        if present_annee_source:
            return None
        statut = "nouveau" if sans_compte else "a_verifier"
        motif = (
            f"absent de l'année précédente"
            if sans_compte
            else "absent de l'année précédente, mais possède déjà un compte"
        )
    elif sans_compte and sans_classe_prec:
        statut, motif = "nouveau", "aucun compte, aucune classe l'an dernier"
    elif sans_compte:
        statut = "a_verifier"
        motif = (
            f"aucun compte, mais Charlemagne lui connaît une classe l'an "
            f"dernier ({snapshot.classe_precedente})"
        )
    elif sans_classe_prec:
        statut = "a_verifier"
        motif = "aucune classe l'an dernier, mais possède déjà un compte"
    else:
        return None  # élève qui poursuit, avec son compte : rien à faire

    site_nom = noms_sites.get(personne.site_id) if personne.site_id else None
    email = personne.email_constate
    if not email and personne.site_id in domaines:
        email = calculer_email(
            personne.prenom, personne.nom, domaines[personne.site_id]
        ) or None

    return NouvelArrivant(
        personne_id=personne.id,
        cle_pivot=personne.cle_pivot,
        type=personne.type,
        badge=personne.badge,
        nom=snapshot.nom or personne.nom,
        prenom=snapshot.prenom or personne.prenom,
        classe=snapshot.classe or personne.classe,
        niveau=snapshot.niveau or personne.niveau,
        site=site_nom,
        regime=snapshot.regime or personne.regime,
        login=personne.login,
        email=email,
        date_entree=snapshot.date_entree or personne.date_entree,
        classe_precedente=snapshot.classe_precedente,
        statut=statut,
        motif=motif,
    )


# ---------------------------------------------------------------------------
# Export CSV — destiné à Excel, pas à un système cible
# ---------------------------------------------------------------------------

COLONNES_CSV = [
    "Clé pivot",
    "Type",
    "Badge",
    "Nom",
    "Prénom",
    "Classe",
    "Classe précédente",
    "Niveau",
    "Site",
    "Régime",
    "Identifiant",
    "Adresse mail",
    "Date d'entrée",
    "Statut",
    "Motif",
]

BOM_UTF8 = b"\xef\xbb\xbf"


def generer_csv_nouveaux(rapport: RapportNouveaux) -> bytes:
    """CSV point-virgule + BOM UTF-8 : s'ouvre directement dans Excel FR.

    Séparateur `;` et BOM sont ce qu'attend un Excel configuré en français.
    Une virgule enverrait tout dans une seule colonne, et l'absence de BOM
    casserait les accents.
    """
    import csv as _csv
    import io as _io

    buf = _io.StringIO(newline="")
    w = _csv.writer(buf, delimiter=";", quoting=_csv.QUOTE_MINIMAL)
    w.writerow(COLONNES_CSV)
    for a in rapport.arrivants:
        w.writerow([
            a.cle_pivot,
            "Élève" if a.type == "eleve" else "Adulte",
            a.badge,
            a.nom,
            a.prenom,
            a.classe or "",
            a.classe_precedente or "",
            a.niveau or "",
            a.site or "",
            a.regime or "",
            a.login,
            a.email or "",
            a.date_entree.strftime("%d/%m/%Y") if a.date_entree else "",
            "Nouveau" if a.statut == "nouveau" else "À vérifier",
            a.motif,
        ])
    return BOM_UTF8 + buf.getvalue().encode("utf-8", errors="replace")
