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

## Le site vient de la classe, pas de la personne

`Personne.site_id` est un **état courant** : il reflète la dernière année
ingérée, qui n'est pas forcément celle qu'on prépare. Une élève de 3e à
Sainte-Ursule qui passe en 2nde au Kreisker reste enregistrée à SU tant
qu'on n'a pas réingéré l'année suivante — et si l'on réingère l'année
précédente après, elle y revient.

S'appuyer sur ce champ ferait dépendre le résultat de l'ordre des
ingestions. Le rattachement est donc résolu par la **Table de
correspondance**, qui dit à quel site appartient une classe : c'est déjà
elle qui fait autorité au moment de l'ingestion.

Conséquence pour le filtre par site : il porte sur le site **de
destination** (celui de la classe visée), pas sur celui où la personne
était l'an dernier.

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

    sites_par_id = {s.id: s for s in session.query(Site).all()}
    if site_id is not None and site_id not in sites_par_id:
        raise ValueError(f"Site introuvable : {site_id}")

    rapport = RapportBascule(
        phase=phase,
        annee_libelle=annee.libelle,
        sites=(
            [sites_par_id[site_id].nom]
            if site_id is not None
            else sorted(s.nom for s in sites_par_id.values())
        ),
    )

    # Rattachement classe -> site, sans presumer du site de la personne.
    par_classe: dict[str, list[TableCorrespondance]] = {}
    for tc in session.query(TableCorrespondance).all():
        par_classe.setdefault(tc.classe_code_court, []).append(tc)

    comptes = {
        c.personne_id: c
        for c in session.query(CompteCible).filter(CompteCible.cible == "google").all()
    }

    for personne, snapshot in _derniers_snapshots_eleves(session, annee_id):
        compte = comptes.get(personne.id)
        classe = snapshot.classe or personne.classe
        lignes = par_classe.get(classe or "", [])

        site = None
        visee = statut = motif = None

        if not lignes:
            statut = "bloque"
            motif = f"classe {classe!r} absente de la Table de correspondance"
        elif len(lignes) > 1:
            noms = ", ".join(
                sorted(sites_par_id[t.site_id].nom for t in lignes if t.site_id in sites_par_id)
            )
            statut = "bloque"
            motif = (
                f"classe {classe!r} declaree pour plusieurs sites ({noms}) — "
                "impossible de choisir sans arbitrage"
            )
        else:
            tc = lignes[0]
            site = sites_par_id.get(tc.site_id)
            visee = tc.ou_pre_rentree if phase == "pre_rentree" else tc.ou_definitive
            if not visee:
                colonne = "OU de pré-rentrée" if phase == "pre_rentree" else "OU définitive"
                statut, motif = "bloque", f"{colonne} non renseignée pour {classe}"
                visee = None
            else:
                appliquee = compte.ou_appliquee if compte else None
                if appliquee == visee:
                    statut, motif = "deja_en_place", "déjà placé dans cette OU"
                else:
                    statut = "a_deplacer"
                    motif = (
                        f"depuis {appliquee}" if appliquee else "aucun placement enregistré"
                    )

        # Classe inconnue : le site de destination n'est pas determinable. On
        # retombe sur celui enregistre pour la personne, pour l'affichage
        # seulement — et sans jamais masquer un bloquant, filtre ou pas.
        site_affiche = site or sites_par_id.get(personne.site_id)
        if site_id is not None and statut != "bloque":
            if site is None or site.id != site_id:
                continue

        domaine = site_affiche.domaine_mail if site_affiche else ""
        email = personne.email_constate
        if not email and domaine:
            email = calculer_email(personne.prenom, personne.nom, domaine) or None

        rapport.mouvements.append(
            MouvementOU(
                personne_id=personne.id,
                cle_pivot=personne.cle_pivot,
                nom=snapshot.nom or personne.nom,
                prenom=snapshot.prenom or personne.prenom,
                classe=classe,
                site=site_affiche.nom if site_affiche else "sans site",
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
    session: Session, annee_id: int
) -> list[tuple[Personne, Snapshot]]:
    """Snapshot le plus récent de chaque élève pour l'année donnée.

    Pas de filtre par site ici : le rattachement se décide à partir de la
    classe du snapshot, pas du site enregistré sur la personne.
    """
    q = (
        session.query(Personne, Snapshot)
        .join(Snapshot, Snapshot.personne_id == Personne.id)
        .filter(
            Snapshot.annee_scolaire_id == annee_id,
            Personne.type == "eleve",
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
