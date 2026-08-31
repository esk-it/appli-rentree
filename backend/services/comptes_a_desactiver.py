"""Les comptes qu'une synchronisation KoXo désactiverait, et lesquels garder.

## Ce que l'absence veut dire

Un export « tous » vaut **état complet** : KoXo désactive tout compte du
groupe primaire qui n'y figure pas. C'est exactement ce qu'on veut d'un
professeur parti, et pas du tout ce qu'on veut de quelqu'un que
Charlemagne ne porte pas.

Or les deux se ressemblent parfaitement vus du programme : dans les deux
cas, la personne n'a pas de photographie pour l'année visée. Le
remplaçant qui revient, le membre de la vie scolaire que l'export
Charlemagne ne décrit pas, la personne rattachée à aucun site — tous
tombent du même côté, et le programme n'avait aucun moyen de dire
« celui-là, on le garde ».

Le dialogue de synchronisation, lui, annonce un nombre : « Désactiver
7 ». Sept qui ? Il fallait exporter la base, ouvrir les deux fichiers et
les comparer à la main pour le savoir. Sur l'instance réelle, la liste
contenait un remplaçant attendu pour la rentrée.

## Ce que ce module fait

Il nomme ces comptes **avant** la synchronisation, dit pourquoi chacun
manque, et permet d'en conserver certains. Un compte conservé est
reconduit dans l'export tel que la base le détient — même identifiant,
même groupe secondaire, même adresse — de sorte que la synchronisation
le voie et n'y touche pas.

## Ce qu'il ne fait pas

Il ne réactive rien et ne crée rien : conserver, c'est empêcher une
désactivation, pas ressusciter un compte déjà désactivé. Et la décision
vaut **par base** : un professeur peut mériter d'être gardé sur le
serveur du lycée et pas sur celui du collège.

## Il faut avoir passé l'export au contrôle

Le programme ne sait ce que la base détient que par le dernier export
qu'on lui a montré. Sans contrôle préalable pour ce site, la liste est
vide — non parce que rien ne serait désactivé, mais parce que rien n'est
connu.
"""
from __future__ import annotations

import csv
import io
from dataclasses import dataclass, field

from sqlalchemy.orm import Session

from backend.models import LoginReserve, Personne, Site, Snapshot

GROUPES_PRIMAIRES = {"eleve": "Elèves", "adulte": "Professeurs"}


@dataclass
class CompteMenace:
    """Un compte de la base que l'export ne reconduit pas."""

    badge: int
    login: str
    nom: str
    prenom: str
    groupe_secondaire: str | None
    email: str | None
    conserver: bool
    motif: str
    """Pourquoi il manque à l'export — c'est ce qui permet de trancher."""

    personne_id: int | None = None


@dataclass
class RapportDesactivations:
    site_nom: str
    base: str
    type_personne: str
    nb_dans_la_base: int = 0
    nb_dans_l_export: int = 0
    comptes: list[CompteMenace] = field(default_factory=list)
    avertissements: list[str] = field(default_factory=list)

    @property
    def nb_menaces(self) -> int:
        return sum(1 for c in self.comptes if not c.conserver)

    @property
    def nb_conserves(self) -> int:
        return sum(1 for c in self.comptes if c.conserver)


def comptes_a_desactiver(
    session: Session,
    *,
    site_id: int,
    type_personne: str,
    annee_cible_id: int,
    base_koxo: str | None = None,
) -> RapportDesactivations:
    """Ce que la synchronisation désactiverait, nommément.

    L'export est **réellement généré** pour établir la liste, plutôt que
    d'en rejouer les règles. C'est la seule façon de garantir que la
    réponse porte sur le fichier qui sera chargé : une règle recopiée
    diverge tôt ou tard de celle qu'elle imite, et cette divergence-là se
    paierait en comptes désactivés à tort.
    """
    from backend.services.exports_koxo import ENCODAGE_KOXO, generer_csv_koxo

    if type_personne not in GROUPES_PRIMAIRES:
        raise ValueError(f"type_personne invalide : {type_personne!r}")

    site = session.query(Site).filter_by(id=site_id).one_or_none()
    if site is None:
        raise ValueError(f"Site introuvable : {site_id}")
    base = (base_koxo or "").strip() or site.nom

    contenu, rapport_export = generer_csv_koxo(
        session,
        site_id=site_id,
        type_personne=type_personne,
        categorie="tous",
        annee_cible_id=annee_cible_id,
        base_koxo=base_koxo,
    )
    lignes = list(
        csv.DictReader(io.StringIO(contenu.decode(ENCODAGE_KOXO, "replace")))
    )
    badges_export = {
        int(l["ID unique"]) for l in lignes if (l.get("ID unique") or "").isdigit()
    }
    # Un compte conservé figure dans l'export **parce qu'** il est conservé.
    # L'écarter à ce titre le faisait disparaître de la liste dès qu'on le
    # cochait, et il n'y avait plus moyen de revenir sur la décision.
    reconduits = set(rapport_export.badges_conserves)
    badges_export -= reconduits

    constats = _constats_de_la_base(session, base, type_personne)
    rapport = RapportDesactivations(
        site_nom=site.nom,
        base=base,
        type_personne=type_personne,
        nb_dans_la_base=len(constats),
        nb_dans_l_export=len(badges_export),
    )
    if not constats:
        rapport.avertissements.append(
            f"Aucun compte connu dans la base {base} : passe d'abord l'export "
            f"de ce serveur au Contrôle KoXo, site {base}. Sans ça, le "
            "programme ne peut pas dire ce que la synchronisation "
            "désactiverait."
        )
        return rapport

    personnes = _personnes_par_badge(session, [c.badge for c in constats])
    avec_snapshot = _badges_avec_snapshot(session, annee_cible_id)

    for c in constats:
        if c.badge in badges_export:
            continue
        p = personnes.get(c.badge)
        rapport.comptes.append(
            CompteMenace(
                badge=c.badge,
                login=c.login,
                nom=(c.nom or (p.nom if p else "")) or "",
                prenom=(c.prenom or (p.prenom if p else "")) or "",
                groupe_secondaire=c.groupe_secondaire,
                email=c.email or (p.email_constate if p else None),
                conserver=bool(c.conserver),
                motif=_motif(
                    session, p, c.badge in avec_snapshot, site,
                    conserve=bool(c.conserver),
                ),
                personne_id=p.id if p else None,
            )
        )

    rapport.comptes.sort(key=lambda c: (not c.conserver, c.nom, c.prenom))
    return rapport


def definir_conservation(
    session: Session, *, badges: list[int], base: str, conserver: bool
) -> int:
    """Marque ou démarque des comptes de cette base. Renvoie le nombre touché.

    La décision porte sur `(badge, base)` : le même professeur peut
    mériter d'être gardé sur un serveur et pas sur l'autre.
    """
    if not badges:
        return 0
    lignes = (
        session.query(LoginReserve)
        .filter(LoginReserve.badge.in_(badges), LoginReserve.site == base)
        .all()
    )
    for l in lignes:
        l.conserver = conserver
    session.flush()
    return len(lignes)


# ---------------------------------------------------------------------------
# Détail
# ---------------------------------------------------------------------------


def _constats_de_la_base(
    session: Session, base: str, type_personne: str
) -> list[LoginReserve]:
    """Les comptes que cette base détient, pour cette population.

    Le tri se fait sur le **groupe primaire** quand la base l'a donné :
    c'est la portée exacte d'une synchronisation, qui se lance sur un
    groupe primaire et ne touche à rien d'autre.

    À défaut — un constat pris avant que le programme ne retienne cette
    colonne — on retombe sur le type de la personne au référentiel. C'est
    moins sûr, et justement inopérant pour les comptes que le référentiel
    ignore : ceux-là sont alors écartés plutôt que rangés au hasard.
    """
    attendu = GROUPES_PRIMAIRES[type_personne].lower()
    toutes = (
        session.query(LoginReserve)
        .filter(LoginReserve.site == base, LoginReserve.badge.isnot(None))
        .all()
    )
    # Un badge peut porter plusieurs constats dans une même base au fil des
    # contrôles : le plus récent dit l'état courant.
    par_badge: dict[int, LoginReserve] = {}
    for c in toutes:
        prec = par_badge.get(c.badge)
        if prec is None or c.date_constat > prec.date_constat:
            par_badge[c.badge] = c

    types = {
        p.badge: p.type
        for p in session.query(Personne)
        .filter(Personne.badge.in_(list(par_badge)))
        .all()
        if p.badge is not None
    }
    retenus = []
    for badge, c in par_badge.items():
        gp = (c.groupe_primaire or "").strip().lower()
        if gp:
            if gp == attendu:
                retenus.append(c)
            continue
        if types.get(badge) == type_personne:
            retenus.append(c)
    return retenus


def _personnes_par_badge(
    session: Session, badges: list[int]
) -> dict[int, Personne]:
    if not badges:
        return {}
    return {
        p.badge: p
        for p in session.query(Personne).filter(Personne.badge.in_(badges)).all()
        if p.badge is not None
    }


def _badges_avec_snapshot(session: Session, annee_id: int) -> set[int]:
    return {
        b
        for (b,) in session.query(Personne.badge)
        .join(Snapshot, Snapshot.personne_id == Personne.id)
        .filter(Snapshot.annee_scolaire_id == annee_id, Personne.badge.isnot(None))
        .distinct()
        .all()
    }


def _motif(
    session: Session,
    p: Personne | None,
    a_un_snapshot: bool,
    site: Site,
    *,
    conserve: bool = False,
) -> str:
    """Pourquoi ce compte manque à l'export.

    C'est ce que la décision demande : un sortant et un remplaçant ne se
    distinguent que là.

    Le cas d'un conservé revenu à Charlemagne mérite d'être dit : la
    décision ne sert plus à rien, et la laisser en place ferait porter à
    l'export une ligne recopiée d'un vieux constat plutôt que la ligne à
    jour.
    """
    if conserve and p is not None and a_un_snapshot and p.site_id == site.id:
        return (
            "revenu dans l'export Charlemagne : la conservation ne sert plus, "
            "tu peux la relâcher"
        )
    if p is None:
        return "inconnu du référentiel — aucune ingestion ne l'a jamais porté"
    if p.site_id is None:
        return "rattaché à aucun site : aucun export ne peut le contenir"
    if p.site_id != site.id:
        autre = session.query(Site).filter_by(id=p.site_id).one_or_none()
        return f"rattaché au site {autre.nom if autre else p.site_id}"
    if not a_un_snapshot:
        return "absent de l'export Charlemagne de l'année visée"
    return "présent au référentiel mais écarté de l'export"
