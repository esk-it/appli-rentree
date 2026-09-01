"""Ce que la rentrée a réellement produit, confronté à ce qu'elle visait.

## Pourquoi cet écran existe

Chaque étape rend son propre compte rendu, et chacun est vrai dans son
coin : « 595 déplacements appliqués », « 596 appartenances posées », « 238
créations réussies ». Aucun ne répond à la question qu'on se pose une fois
tout lancé — **est-ce que tout le monde est en place ?**

La réponse ne s'obtient qu'en confrontant l'ensemble du référentiel à
l'ensemble de Google. Sur l'instance réelle, faire ce rapprochement à la
main a révélé, le jour de la rentrée : trois élèves sans aucun compte, un
compte de lycéen écrasé par l'import d'un homonyme collégien, un élève
sans classe, et quatre cent cinquante-huit sortants encore rangés dans
l'arbre de l'année révolue. Aucun écran ne les montrait.

## Ce que chaque contrôle regarde

| Contrôle | Ce qu'il signale |
|---|---|
| `compte_absent` | Élève inscrit sans compte Google — il ne pourra pas se connecter |
| `compte_suspendu` | Compte suspendu alors que l'élève est inscrit |
| `ou_inattendue` | Compte rangé ailleurs que dans l'unité de sa classe ou celle d'attente |
| `groupe_manquant` | Absent du groupe de sa classe — il ne reçoit pas les messages |
| `groupe_en_trop` | Membre du groupe d'une autre classe — il lit ce qui ne le regarde pas |
| `identifiant_discordant` | L'identifiant Charlemagne du compte désigne quelqu'un d'autre |
| `sortant_dans_arbre_actif` | Parti, mais toujours rangé avec les inscrits |
| `sans_classe` | Inscrit sans classe — ni unité ni groupe calculables |

## Ce qu'il ne fait pas

Il ne corrige rien. Chaque constat porte le geste à faire et l'écran où le
faire ; c'est délibéré. Un bilan qui répare est un bilan qu'on ne relit
plus, et les corrections d'ici touchent Google, KoXo ou Charlemagne selon
les cas — trois systèmes dont un seul a une API.

## Deux sources, pas une

Les comptes et les appartenances sont **passés en paramètre** plutôt que
lus ici. C'est ce qui rend le bilan testable sans Google, et c'est la même
convention que `calculer_diff_groupes` — un service qui va chercher ses
données lui-même ne se vérifie que sur l'instance réelle.
"""
from __future__ import annotations

from dataclasses import dataclass, field

from sqlalchemy.orm import Session

from backend.models import (
    AnneeScolaire,
    Personne,
    Site,
    Snapshot,
    TableCorrespondance,
)

GRAVITES = ("bloquant", "attention", "information")

GESTES = {
    "compte_absent": (
        "bloquant",
        "Crée le compte depuis l'écran Arrivée, ou reprends sa ligne dans "
        "l'export des nouveaux.",
    ),
    "compte_suspendu": (
        "bloquant",
        "Réactive le compte dans la console Google : l'élève est inscrit "
        "cette année.",
    ),
    "ou_inattendue": (
        "attention",
        "Relance la bascule des OU pour cette classe — filtre dessus pour "
        "n'emporter qu'elle.",
    ),
    "groupe_manquant": (
        "attention",
        "Relance la composition des groupes pour cette classe.",
    ),
    "groupe_en_trop": (
        "attention",
        "Coche « Retirer aussi les anciens » et relance la composition des "
        "deux classes concernées.",
    ),
    "identifiant_discordant": (
        "bloquant",
        "Corrige l'identifiant Charlemagne du compte dans la console : tel "
        "quel, il désigne quelqu'un d'autre, et le prochain import écrasera "
        "le mauvais compte.",
    ),
    "sortant_dans_arbre_actif": (
        "attention",
        "Passe par Vider l'arbre de l'année révolue pour les déplacer en "
        "unité de sortie.",
    ),
    "sans_classe": (
        "bloquant",
        "Complète sa classe dans Charlemagne, ou donne-la depuis l'écran "
        "Mouvements.",
    ),
}


@dataclass
class Constat:
    """Une personne, ce qui cloche, et le geste à faire."""

    genre: str
    gravite: str
    personne_id: int | None
    nom: str
    prenom: str
    classe: str | None
    site: str | None
    email: str | None
    detail: str
    geste: str


@dataclass
class Reste:
    """Ce qui n'est pas fait, et qui n'est pas une erreur pour autant.

    Un élève encore en unité d'attente n'est pas mal rangé : il n'est pas
    encore basculé. Le compter parmi les écarts noyait les cinq vrais
    problèmes sous seize cents lignes — et un bilan illisible ne se lit
    pas.
    """

    genre: str
    nombre: int
    libelle: str
    geste: str
    exemples: list[str] = field(default_factory=list)


@dataclass
class Chiffres:
    """Ce qui est en place, pour situer les écarts."""

    inscrits: int = 0
    avec_compte: int = 0
    en_ou_definitive: int = 0
    en_ou_attente: int = 0
    dans_leur_groupe: int = 0

    @property
    def sans_compte(self) -> int:
        return self.inscrits - self.avec_compte


@dataclass
class BilanRentree:
    annee_libelle: str
    chiffres: Chiffres = field(default_factory=Chiffres)
    par_site: dict[str, Chiffres] = field(default_factory=dict)
    constats: list[Constat] = field(default_factory=list)
    """Les écarts : ce qui a mal tourné."""
    restes: list[Reste] = field(default_factory=list)
    """Ce qui n'est pas encore fait, et qu'on a choisi de ne pas faire."""

    @property
    def nb_bloquants(self) -> int:
        return sum(1 for c in self.constats if c.gravite == "bloquant")

    @property
    def nb_attention(self) -> int:
        return sum(1 for c in self.constats if c.gravite == "attention")

    @property
    def par_genre(self) -> dict[str, int]:
        compte: dict[str, int] = {}
        for c in self.constats:
            compte[c.genre] = compte.get(c.genre, 0) + 1
        return compte

    @property
    def tout_est_en_place(self) -> bool:
        return not self.constats


def dresser_bilan(
    session: Session,
    comptes_google: list[dict],
    membres_par_groupe: dict[str, list[str] | None],
    *,
    annee_id: int,
    annee_source_id: int | None = None,
    site_id: int | None = None,
) -> BilanRentree:
    """Confronte l'ensemble du référentiel à l'ensemble de Google.

    Args:
        comptes_google: retour de `ClientGoogle.lister_utilisateurs`.
        membres_par_groupe: `{adresse: [membres]}`, `None` pour un groupe
            que Google ne connaît pas.
        annee_source_id: année précédente — sans elle, les sortants ne
            peuvent pas être repérés, et ce contrôle est simplement omis
            plutôt que rendu faux.
    """
    annee = session.query(AnneeScolaire).filter_by(id=annee_id).one_or_none()
    if annee is None:
        raise ValueError(f"Année introuvable : {annee_id}")

    bilan = BilanRentree(annee_libelle=annee.libelle)
    sites = {s.id: s for s in session.query(Site).all()}
    tcs = _table_par_classe(session)

    par_adresse: dict[str, dict] = {}
    for u in comptes_google:
        a = (u.get("email") or "").lower()
        if a:
            par_adresse[a] = u
        for alias in u.get("alias") or []:
            par_adresse.setdefault(alias.lower(), u)

    inscrits = _inscrits(session, annee_id, site_id)
    groupes_des_inscrits = _groupes_par_adresse(membres_par_groupe)
    en_attente: list[str] = []

    for personne, snapshot in inscrits:
        nom_site = sites[personne.site_id].nom if personne.site_id in sites else None
        classe = snapshot.classe or personne.classe
        chiffres = bilan.par_site.setdefault(nom_site or "sans site", Chiffres())
        bilan.chiffres.inscrits += 1
        chiffres.inscrits += 1

        if not classe:
            bilan.constats.append(
                _constat("sans_classe", personne, classe, nom_site,
                         "aucune classe pour l'année préparée")
            )
            continue

        tc = tcs.get((personne.site_id, classe))
        adresse = (personne.email or "").strip().lower()
        compte = par_adresse.get(adresse)

        if compte is None:
            bilan.constats.append(
                _constat("compte_absent", personne, classe, nom_site,
                         f"aucun compte Google pour {adresse or '(pas d’adresse)'}")
            )
            continue

        bilan.chiffres.avec_compte += 1
        chiffres.avec_compte += 1

        if compte.get("suspendu"):
            bilan.constats.append(
                _constat("compte_suspendu", personne, classe, nom_site,
                         "le compte est suspendu")
            )

        bascule = _controler_ou(
            bilan, chiffres, personne, classe, nom_site, compte, tc
        )
        if not bascule:
            en_attente.append(f"{personne.prenom} {personne.nom} ({classe})")
        _controler_groupes(
            bilan, chiffres, personne, classe, nom_site, tc,
            groupes_des_inscrits.get(adresse, set()), tcs, bascule,
        )
        _controler_identifiant(bilan, personne, classe, nom_site, compte)

    if en_attente:
        bilan.restes.append(
            Reste(
                genre="a_basculer",
                nombre=len(en_attente),
                libelle="élève(s) encore en unité d'attente, hors de leur "
                        "classe et hors de leur groupe",
                geste="Bascule des OU, phase « Bascule de rentrée », puis "
                      "composition des groupes — filtre sur les classes que "
                      "tu veux emporter.",
                exemples=sorted(en_attente)[:8],
            )
        )

    if annee_source_id is not None:
        _controler_sortants(
            bilan, session, annee_id, annee_source_id, par_adresse, sites, site_id
        )

    ordre = {"bloquant": 0, "attention": 1, "information": 2}
    bilan.constats.sort(key=lambda c: (ordre[c.gravite], c.genre, c.nom, c.prenom))
    return bilan


# ---------------------------------------------------------------------------
# Les contrôles
# ---------------------------------------------------------------------------


def _controler_ou(bilan, chiffres, personne, classe, nom_site, compte, tc) -> bool:
    """L'unité d'organisation : celle de la classe, ou celle d'attente.

    Répond « cet élève est-il basculé ? » — ce que la suite des contrôles
    a besoin de savoir pour ne pas prendre une étape non faite pour une
    erreur.

    Les deux sont légitimes selon où en est la campagne — un élève en
    attente n'est pas mal rangé, il n'est pas encore basculé. Seule une
    troisième valeur est un écart.
    """
    if tc is None:
        return False
    ou = (compte.get("ou") or "").strip()
    if ou == (tc.ou_definitive or "").strip():
        bilan.chiffres.en_ou_definitive += 1
        chiffres.en_ou_definitive += 1
        return True
    if ou == (tc.ou_pre_rentree or "").strip():
        bilan.chiffres.en_ou_attente += 1
        chiffres.en_ou_attente += 1
        return False
    bilan.constats.append(
        _constat("ou_inattendue", personne, classe, nom_site,
                 f"rangé dans « {ou or '(racine)'} », attendu « "
                 f"{tc.ou_definitive} » ou « {tc.ou_pre_rentree} »")
    )
    return False


def _controler_groupes(
    bilan, chiffres, personne, classe, nom_site, tc, siens, tcs, bascule
) -> None:
    """Le groupe de sa classe, et aucun autre groupe de classe.

    L'absence ne vaut écart que pour un élève **déjà basculé**. Tant qu'il
    attend en unité de pré-rentrée, ne pas être dans sa liste de classe est
    l'état voulu — c'est même ce qui empêche sa classe de transparaître
    avant l'heure. Les compter comme des erreurs noyait cinq vrais
    problèmes sous seize cents lignes.
    """
    attendu = (tc.groupe_google or "").strip().lower() if tc else ""
    if attendu:
        if attendu in siens:
            bilan.chiffres.dans_leur_groupe += 1
            chiffres.dans_leur_groupe += 1
        elif bascule:
            bilan.constats.append(
                _constat("groupe_manquant", personne, classe, nom_site,
                         f"absent de {attendu}")
            )

    tous_groupes = {
        (t.groupe_google or "").strip().lower()
        for t in tcs.values()
        if (t.groupe_google or "").strip()
    }
    intrus = sorted((siens & tous_groupes) - {attendu})
    if intrus:
        bilan.constats.append(
            _constat("groupe_en_trop", personne, classe, nom_site,
                     "membre de " + ", ".join(intrus))
        )


def _controler_identifiant(bilan, personne, classe, nom_site, compte) -> None:
    """L'identifiant Charlemagne inscrit dans le compte.

    C'est lui qui a trahi le compte écrasé : deux Hugo GUILLOU, un seul
    compte, et l'identifiant du collégien posé sur celui du lycéen par un
    import. Tant qu'il n'est pas corrigé, le prochain import recommencera.
    """
    porte = compte.get("id_externe")
    if porte in (None, ""):
        return
    attendu = personne.id_charlemagne
    if attendu is None:
        return
    if str(porte).strip() != str(attendu):
        bilan.constats.append(
            _constat("identifiant_discordant", personne, classe, nom_site,
                     f"le compte porte l'identifiant {porte}, "
                     f"celui de cette personne est {attendu}")
        )


def _controler_sortants(
    bilan, session, annee_id, annee_source_id, par_adresse, sites, site_id
) -> None:
    """Les partants encore rangés avec les inscrits.

    Une unité de sortie se reconnaît à son nom : c'est la convention de la
    maison, et rien dans l'API ne la désigne autrement.
    """
    presents = _ids_annee(session, annee_id)
    partis = _ids_annee(session, annee_source_id) - presents
    if not partis:
        return
    gens = (
        session.query(Personne)
        .filter(Personne.id.in_(partis), Personne.type == "eleve")
        .all()
    )
    restants = []
    for p in gens:
        if site_id is not None and p.site_id != site_id:
            continue
        compte = par_adresse.get((p.email or "").strip().lower())
        if compte is None:
            continue
        if "sorti" in (compte.get("ou") or "").lower():
            continue
        restants.append(f"{p.prenom} {p.nom}")

    # Une seule tâche, pas quatre cent quatre-vingt-sept problèmes : ils
    # relèvent tous du même geste, et les énumérer un par un écraserait le
    # reste du bilan.
    if restants:
        bilan.restes.append(
            Reste(
                genre="sortants_a_ranger",
                nombre=len(restants),
                libelle="ancien(s) élève(s) encore rangé(s) avec les inscrits",
                geste=GESTES["sortant_dans_arbre_actif"][1],
                exemples=sorted(restants)[:8],
            )
        )


# ---------------------------------------------------------------------------
# Détail
# ---------------------------------------------------------------------------


def _constat(genre, personne, classe, nom_site, detail) -> Constat:
    gravite, geste = GESTES[genre]
    return Constat(
        genre=genre, gravite=gravite, personne_id=personne.id,
        nom=personne.nom or "", prenom=personne.prenom or "",
        classe=classe, site=nom_site, email=personne.email,
        detail=detail, geste=geste,
    )


def _table_par_classe(session: Session) -> dict:
    return {
        (t.site_id, t.classe_code_court): t
        for t in session.query(TableCorrespondance).all()
    }


def _inscrits(session: Session, annee_id: int, site_id: int | None):
    """Chaque élève de l'année, avec sa photographie la plus récente."""
    q = (
        session.query(Personne, Snapshot)
        .join(Snapshot, Snapshot.personne_id == Personne.id)
        .filter(Snapshot.annee_scolaire_id == annee_id, Personne.type == "eleve")
    )
    if site_id is not None:
        q = q.filter(Personne.site_id == site_id)
    derniers: dict[int, tuple] = {}
    for p, sn in q.all():
        prec = derniers.get(p.id)
        if prec is None or sn.date_ingestion > prec[1].date_ingestion:
            derniers[p.id] = (p, sn)
    return sorted(derniers.values(), key=lambda x: (x[0].nom or "", x[0].prenom or ""))


def _groupes_par_adresse(
    membres_par_groupe: dict[str, list[str] | None],
) -> dict[str, set[str]]:
    index: dict[str, set[str]] = {}
    for groupe, membres in membres_par_groupe.items():
        for m in membres or []:
            index.setdefault(m.lower(), set()).add(groupe.lower())
    return index


def _ids_annee(session: Session, annee_id: int) -> set[int]:
    return {
        pid
        for (pid,) in session.query(Snapshot.personne_id)
        .filter(Snapshot.annee_scolaire_id == annee_id)
        .distinct()
        .all()
    }
