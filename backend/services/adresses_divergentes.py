"""Écarts entre l'adresse enregistrée et le compte Google réel.

## Le problème

Le référentiel tient l'adresse que donne Charlemagne. Rien ne garantit
qu'elle corresponde au compte réellement ouvert : sur l'instance réelle,
quatre élèves inscrits portent une adresse introuvable dans Google —
`louis.legall@` contre `louis.le.gall@`, une faute de frappe sur
`ralavao`, un suffixe d'homonymie qui diffère d'un chiffre.

Les conséquences sont silencieuses et coûteuses :

- **le déplacement d'OU échoue** pour ces élèves, un par un, sans que
  rien ne l'ait annoncé ;
- **l'export des nouveaux tente de créer un compte** qui existe déjà
  sous un autre nom, d'où un doublon ;
- **la vidange d'une branche** ne les reconnaît pas et les traite comme
  des partants — un élève inscrit s'est trouvé à un cheveu d'être
  suspendu.

## L'adresse calculée compte autant que l'adresse constatée

Le contrôle ne regardait que les personnes dont l'adresse avait déjà été
constatée dans Google. C'était l'angle mort : une personne fraîchement
ingérée n'en a pas, son adresse est **déduite d'une règle** — et c'est
justement là que la règle peut se tromper.

Un entrant dont aucun compte ne porte le nom n'est pas un écart pour
autant : son compte reste à créer, et le signaler noierait les vrais
écarts sous les arrivées de l'année.

## Les alias comptent

Un compte Google répond à son adresse principale et à chacun de ses
alias. Une adresse d'alias enregistrée au référentiel désigne donc un
compte qui existe, et n'a rien de divergent — l'écran la signalait
pourtant, sans qu'aucune correction soit possible.

## La règle de rapprochement

Une correction n'est proposée que si le nom et le prénom désignent
**exactement un** compte Google et **exactement une** personne du
référentiel. Deux homonymes rendent l'attribution arbitraire : le cas
est alors signalé sans proposition.

Rien n'est corrigé d'office : la proposition se relit avant d'être
appliquée.
"""
from __future__ import annotations

from dataclasses import dataclass, field

from sqlalchemy.orm import Session

from backend.models import AnneeScolaire, Personne, Snapshot
from backend.services.regles_metier import normaliser_nom


@dataclass
class Divergence:
    personne_id: int
    cle_pivot: str
    nom: str
    prenom: str
    adresse_enregistree: str
    adresse_google: str | None
    ou_google: str | None
    resolvable: bool
    motif: str


@dataclass
class RapportDivergences:
    nb_examines: int = 0
    divergences: list[Divergence] = field(default_factory=list)

    @property
    def nb_resolvables(self) -> int:
        return sum(1 for d in self.divergences if d.resolvable)

    @property
    def nb_ambigus(self) -> int:
        return sum(1 for d in self.divergences if not d.resolvable)


def detecter_divergences(
    session: Session,
    comptes_google: list[dict],
    *,
    annee_id: int | None = None,
    site_id: int | None = None,
) -> RapportDivergences:
    """Repère les personnes dont l'adresse enregistrée n'existe pas dans Google.

    Args:
        comptes_google: retour de `ClientGoogle.lister_utilisateurs`.
        annee_id: restreint aux personnes présentes cette année-là.
            `None` = l'année la plus récente, celle qu'on prépare.
    """
    # Un compte répond à son adresse principale **et à ses alias**. Une
    # adresse d'alias enregistrée au référentiel désigne donc un compte
    # qui existe : la signaler comme divergente envoyait chercher une
    # correction là où il n'y avait rien à corriger.
    adresses_google = {(u.get("email") or "").lower() for u in comptes_google}
    for u in comptes_google:
        adresses_google.update(a.lower() for a in (u.get("alias") or []) if a)

    # Les comptes sont indexés dans les **deux ordres**. Sur l'instance
    # réelle, 172 des 250 comptes d'un site portent le prénom dans le champ
    # du nom et inversement — ils ont été créés ainsi. Le client lit
    # pourtant `familyName` et `givenName` correctement : c'est la donnée
    # qui est à l'envers, et aucun rapprochement par nom ne les retrouvait.
    #
    # Indexer les deux sens ne fait courir qu'un risque : qu'un compte
    # « Martin Paul » réponde aussi à « Paul Martin ». Le cas est signalé
    # comme ambigu plus bas, jamais tranché — un compte trouvé par l'ordre
    # inverse reste soumis aux mêmes conditions d'unicité.
    par_nom_google: dict[tuple[str, str], list[dict]] = {}
    for u in comptes_google:
        a, b = normaliser_nom(u.get("nom")), normaliser_nom(u.get("prenom"))
        par_nom_google.setdefault((a, b), []).append(u)
        if a != b:
            par_nom_google.setdefault((b, a), []).append(u)

    if annee_id is None:
        annees = session.query(AnneeScolaire).all()
        annee_id = max(annees, key=lambda a: a.libelle).id if annees else None

    # On examine aussi ceux dont l'adresse est **calculée**, et pas
    # seulement constatée. C'était l'angle mort : une personne fraîchement
    # ingérée n'a pas d'adresse constatée, son adresse est déduite d'une
    # règle — et c'est précisément là que la règle peut se tromper. Sur les
    # 127 élèves de NDE, six portaient une adresse calculée qui ne
    # désignait pas leur compte : `alice.le.gall` contre `alice.legall`,
    # `lilou.dubois.cuiec` contre `lilou.dubois-cuiec`. L'écran n'en
    # montrait aucune, et l'export en aurait fait six doublons.
    q = session.query(Personne)
    if site_id is not None:
        q = q.filter(Personne.site_id == site_id)
    if annee_id is not None:
        ids = {
            pid
            for (pid,) in session.query(Snapshot.personne_id)
            .filter(Snapshot.annee_scolaire_id == annee_id)
            .distinct()
            .all()
        }
        q = q.filter(Personne.id.in_(ids))

    # Un nom qui désigne plusieurs personnes du référentiel interdit toute
    # attribution automatique, même si Google n'a qu'un compte.
    homonymes_referentiel: dict[tuple[str, str], int] = {}
    for p in session.query(Personne).all():
        cle = (normaliser_nom(p.nom), normaliser_nom(p.prenom))
        homonymes_referentiel[cle] = homonymes_referentiel.get(cle, 0) + 1

    rapport = RapportDivergences()
    for p in q.all():
        enregistree = (p.email or "").strip().lower()
        if not enregistree:
            continue
        rapport.nb_examines += 1
        if enregistree in adresses_google:
            continue

        cle = (normaliser_nom(p.nom), normaliser_nom(p.prenom))
        candidats = par_nom_google.get(cle, [])

        # Une adresse calculée qui ne désigne aucun compte, pour quelqu'un
        # dont aucun compte ne porte le nom, n'est pas un écart : c'est un
        # entrant, et son compte reste à créer. Le signaler noierait les
        # vrais écarts sous les arrivées de l'année.
        if not candidats and not p.email_constate:
            continue

        if len(candidats) == 1 and homonymes_referentiel.get(cle, 0) == 1:
            u = candidats[0]
            inverse = (
                normaliser_nom(u.get("nom")) == cle[1]
                and normaliser_nom(u.get("prenom")) == cle[0]
                and cle[0] != cle[1]
            )
            rapport.divergences.append(
                Divergence(
                    personne_id=p.id, cle_pivot=p.cle_pivot, nom=p.nom, prenom=p.prenom,
                    adresse_enregistree=enregistree,
                    adresse_google=u["email"], ou_google=u.get("ou"),
                    resolvable=True,
                    motif=(
                        "un seul compte porte ce nom, mais avec le nom et le "
                        "prénom intervertis dans Google"
                        if inverse
                        else "un seul compte porte ce nom"
                    ),
                )
            )
        elif not candidats:
            rapport.divergences.append(
                Divergence(
                    personne_id=p.id, cle_pivot=p.cle_pivot, nom=p.nom, prenom=p.prenom,
                    adresse_enregistree=enregistree,
                    adresse_google=None, ou_google=None,
                    resolvable=False,
                    motif="aucun compte à ce nom : le compte reste à créer",
                )
            )
        else:
            noms = ", ".join(sorted(u["email"] for u in candidats)) or "—"
            rapport.divergences.append(
                Divergence(
                    personne_id=p.id, cle_pivot=p.cle_pivot, nom=p.nom, prenom=p.prenom,
                    adresse_enregistree=enregistree,
                    adresse_google=None, ou_google=None,
                    resolvable=False,
                    motif=f"plusieurs comptes possibles ({noms}) — à trancher à la main",
                )
            )

    rapport.divergences.sort(key=lambda d: (not d.resolvable, d.nom, d.prenom))
    return rapport


def appliquer_corrections(
    session: Session, rapport: RapportDivergences, *, mode: str = "simulation"
) -> int:
    """Aligne l'adresse enregistrée sur le compte Google réel.

    Seules les divergences résolvables sont touchées. Ce que Google
    contient fait foi : c'est là que l'élève se connecte.

    Returns:
        Nombre d'adresses corrigées.
    """
    if mode not in ("simulation", "reel"):
        raise ValueError(f"mode invalide : {mode!r}")

    a_corriger = [d for d in rapport.divergences if d.resolvable and d.adresse_google]
    if not a_corriger:
        return 0

    personnes = {
        p.id: p
        for p in session.query(Personne)
        .filter(Personne.id.in_([d.personne_id for d in a_corriger]))
        .all()
    }
    n = 0
    for d in a_corriger:
        p = personnes.get(d.personne_id)
        if p is None:
            continue
        p.email_constate = d.adresse_google
        n += 1

    if mode == "reel":
        session.commit()
    else:
        session.rollback()
    return n
