"""Bascule des OU Google — les deux temps de la rentrée.

## Le processus réel

Une rentrée ne se joue pas en une fois côté Google :

1. **Avant la rentrée** — tout le monde (entrants *et* élèves qui montent
   de classe) est rassemblé dans l'**OU de pré-rentrée** du site, une
   seule pour tout l'établissement. Les répartitions ne sont pas figées,
   les listes de classe bougent encore : placer chacun dans sa classe à
   ce stade obligerait à tout refaire.
2. **Le jour de la rentrée** — chacun descend dans l'**OU définitive** de
   sa classe.

Ces deux temps sont des étapes distinctes et rejouables, pas un effet de
bord du choix d'une catégorie d'export.

## Ce que le programme sait, et ne sait pas

Il n'a aucune vue sur l'état réel de Google. Il mémorise donc ce qu'il a
demandé, dans `CompteCible.ou_appliquee`, et compare la cible visée à
cette trace. D'où trois statuts :

| Statut | Sens |
|---|---|
| `a_deplacer` | l'OU visée diffère de la dernière appliquée |
| `deja_en_place` | déjà demandé, rien à refaire |
| `bloque` | classe absente de la Table, ou OU non renseignée |

Un cas `bloque` n'est jamais résolu par un placement par défaut : sans
OU connue, on s'arrête et on l'explique (§8 « jamais d'affectation par
défaut »).

## Périmètre

Élèves uniquement. L'OU des adultes ne se déduit pas d'une classe — la
Table de correspondance ne dit rien de leur rattachement, et deviner
serait exactement ce que le programme s'interdit.
"""
from __future__ import annotations

from dataclasses import dataclass, field

from sqlalchemy.orm import Session

from backend.models import CompteCible, Personne, Site, Snapshot, TableCorrespondance
from backend.services.regles_metier import calculer_email

PHASES = ("pre_rentree", "definitive")

LIBELLE_PHASE = {
    "pre_rentree": "placement en OU de pré-rentrée",
    "definitive": "bascule vers les OU définitives",
}


@dataclass
class MouvementOU:
    """Un élève et le déplacement d'OU qui le concerne."""

    personne_id: int
    cle_pivot: str
    nom: str
    prenom: str
    classe: str | None
    site: str
    email: str | None
    ou_appliquee: str | None
    """Dernière OU demandée par le programme. `None` = jamais placé par nous."""
    ou_visee: str | None
    statut: str  # a_deplacer | deja_en_place | bloque
    motif: str


@dataclass
class RapportBascule:
    phase: str
    annee_libelle: str
    sites: list[str] = field(default_factory=list)

    nb_a_deplacer: int = 0
    nb_deja_en_place: int = 0
    nb_bloques: int = 0

    mouvements: list[MouvementOU] = field(default_factory=list)

    @property
    def nb_total(self) -> int:
        return len(self.mouvements)

    @property
    def est_applicable(self) -> bool:
        """Faux si des élèves sont bloqués : on ne bascule pas à moitié."""
        return self.nb_bloques == 0


def planifier_bascule(
    session: Session,
    *,
    annee_id: int,
    phase: str,
    site_id: int | None = None,
) -> RapportBascule:
    """Calcule les déplacements d'OU sans rien appliquer.

    Args:
        annee_id: année dont on prépare la rentrée.
        phase: `pre_rentree` ou `definitive`.
        site_id: restreint à un site. `None` = les trois.
    """
    from backend.models import AnneeScolaire

    if phase not in PHASES:
        raise ValueError(f"phase invalide : {phase!r}")

    annee = session.query(AnneeScolaire).filter_by(id=annee_id).one_or_none()
    if annee is None:
        raise ValueError(f"Année introuvable : {annee_id}")

    sites = session.query(Site)
    if site_id is not None:
        sites = sites.filter(Site.id == site_id)
    sites_par_id = {s.id: s for s in sites.all()}
    if site_id is not None and not sites_par_id:
        raise ValueError(f"Site introuvable : {site_id}")

    rapport = RapportBascule(
        phase=phase,
        annee_libelle=annee.libelle,
        sites=sorted(s.nom for s in sites_par_id.values()),
    )

    ou_par_classe = {
        (tc.site_id, tc.classe_code_court): (tc.ou_pre_rentree, tc.ou_definitive)
        for tc in session.query(TableCorrespondance).all()
    }
    comptes = {
        c.personne_id: c
        for c in session.query(CompteCible).filter(CompteCible.cible == "google").all()
    }

    for personne, snapshot in _derniers_snapshots_eleves(
        session, annee_id, list(sites_par_id)
    ):
        site = sites_par_id[personne.site_id]
        compte = comptes.get(personne.id)
        classe = snapshot.classe or personne.classe

        ous = ou_par_classe.get((site.id, classe or ""))
        if ous is None:
            visee, statut, motif = (
                None,
                "bloque",
                f"classe {classe!r} absente de la Table de correspondance",
            )
        else:
            visee = ous[0] if phase == "pre_rentree" else ous[1]
            if not visee:
                colonne = "OU de pré-rentrée" if phase == "pre_rentree" else "OU définitive"
                visee, statut, motif = None, "bloque", f"{colonne} non renseignée pour {classe}"
            else:
                appliquee = compte.ou_appliquee if compte else None
                if appliquee == visee:
                    statut, motif = "deja_en_place", "déjà placé dans cette OU"
                else:
                    statut = "a_deplacer"
                    motif = (
                        f"depuis {appliquee}" if appliquee else "aucun placement enregistré"
                    )

        email = personne.email_constate
        if not email:
            email = calculer_email(personne.prenom, personne.nom, site.domaine_mail) or None

        rapport.mouvements.append(
            MouvementOU(
                personne_id=personne.id,
                cle_pivot=personne.cle_pivot,
                nom=snapshot.nom or personne.nom,
                prenom=snapshot.prenom or personne.prenom,
                classe=classe,
                site=site.nom,
                email=email,
                ou_appliquee=compte.ou_appliquee if compte else None,
                ou_visee=visee,
                statut=statut,
                motif=motif,
            )
        )

    rapport.mouvements.sort(key=lambda m: (m.site, m.classe or "", m.nom, m.prenom))
    rapport.nb_a_deplacer = sum(1 for m in rapport.mouvements if m.statut == "a_deplacer")
    rapport.nb_deja_en_place = sum(
        1 for m in rapport.mouvements if m.statut == "deja_en_place"
    )
    rapport.nb_bloques = sum(1 for m in rapport.mouvements if m.statut == "bloque")
    return rapport


def enregistrer_bascule(
    session: Session,
    rapport: RapportBascule,
    *,
    mode: str = "simulation",
) -> int:
    """Note que les déplacements ont été appliqués côté Google.

    À n'appeler **qu'après** avoir réellement importé le CSV ou exécuté le
    plan : le programme n'agit pas sur Google, il enregistre ce que tu as
    fait. Les comptes bloqués sont ignorés.

    Returns:
        Nombre de comptes dont l'OU enregistrée a changé.
    """
    if mode not in ("simulation", "reel"):
        raise ValueError(f"mode invalide : {mode!r}")

    a_traiter = [m for m in rapport.mouvements if m.statut == "a_deplacer"]
    if not a_traiter:
        return 0

    comptes = {
        c.personne_id: c
        for c in session.query(CompteCible)
        .filter(
            CompteCible.cible == "google",
            CompteCible.personne_id.in_([m.personne_id for m in a_traiter]),
        )
        .all()
    }

    n = 0
    for m in a_traiter:
        compte = comptes.get(m.personne_id)
        if compte is None:
            # La bascule concerne un compte que le cycle de vie ne suit pas
            # encore (amorçage sans passage par un export « nouveaux ») : on
            # le crée à l'état `actif`, il existe bel et bien côté Google.
            compte = CompteCible(
                personne_id=m.personne_id,
                cible="google",
                etat="actif",
                identifiant_externe=m.email,
            )
            session.add(compte)
        compte.ou_appliquee = m.ou_visee
        n += 1

    if mode == "reel":
        session.commit()
    else:
        session.rollback()
    return n


# ---------------------------------------------------------------------------
# Interne
# ---------------------------------------------------------------------------


def _derniers_snapshots_eleves(
    session: Session, annee_id: int, site_ids: list[int]
) -> list[tuple[Personne, Snapshot]]:
    """Snapshot le plus récent de chaque élève pour l'année et les sites donnés."""
    if not site_ids:
        return []
    q = (
        session.query(Personne, Snapshot)
        .join(Snapshot, Snapshot.personne_id == Personne.id)
        .filter(
            Snapshot.annee_scolaire_id == annee_id,
            Personne.type == "eleve",
            Personne.site_id.in_(site_ids),
        )
    )
    retenus: dict[int, tuple[Personne, Snapshot]] = {}
    for p, s in q.all():
        precedent = retenus.get(p.id)
        if precedent is None or s.date_ingestion > precedent[1].date_ingestion:
            retenus[p.id] = (p, s)
    return list(retenus.values())


# ---------------------------------------------------------------------------
# CSV Google — même gabarit que les autres exports (40 colonnes, BOM)
# ---------------------------------------------------------------------------


def generer_csv_bascule(rapport: RapportBascule) -> bytes:
    """CSV de mise à jour d'OU, au format bulk de la console Google Admin.

    Seuls les mouvements `a_deplacer` y figurent : réimporter des comptes
    déjà en place n'apporterait rien et allongerait le traitement Google.
    Le mot de passe reste vide — c'est une mise à jour, pas une création.
    """
    import csv as _csv
    import io as _io

    from backend.services.exports_google import BOM_UTF8, COLONNES_GOOGLE

    buf = _io.StringIO(newline="")
    w = _csv.DictWriter(buf, fieldnames=COLONNES_GOOGLE, quoting=_csv.QUOTE_MINIMAL)
    w.writeheader()
    for m in rapport.mouvements:
        if m.statut != "a_deplacer" or not m.email or not m.ou_visee:
            continue
        ligne = {c: "" for c in COLONNES_GOOGLE}
        ligne["First Name [Required]"] = m.prenom or ""
        ligne["Last Name [Required]"] = m.nom or ""
        ligne["Email Address [Required]"] = m.email
        ligne["Org Unit Path [Required]"] = m.ou_visee
        ligne["Employee ID"] = m.cle_pivot.lstrip("EA")
        ligne["Employee Type"] = "Student"
        w.writerow(ligne)
    return BOM_UTF8 + buf.getvalue().encode("utf-8", errors="replace")
