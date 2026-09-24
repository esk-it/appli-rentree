"""Ingestion unifiée des exports Charlemagne (élèves + adultes).

Un seul chemin, paramétré par le `type` de population. À chaque ligne :

1. Lit et normalise les champs.
2. Détecte les homonymes intra-export.
3. Résout le site via `TableCorrespondance` (élèves uniquement).
4. Refuse si des classes sont absentes de la table (§8 du prompt).
5. Rapproche par clé pivot `(type, id_charlemagne)`.
6. Crée ou met à jour la `Personne` (login figé si déjà présent).
7. Crée un `Snapshot` si l'état constaté diffère du dernier snapshot.

Deux modes :

- **simulation** : lit, évalue, produit le rapport, ne commit rien.
- **reel** : idem + commit.

Le rapport est le même dans les deux cas — la seule différence est la
persistance. C'est aussi le socle du garde-fou "simulation par défaut"
qu'exige le prompt §8.
"""
from __future__ import annotations

import hashlib
from dataclasses import dataclass, field
from datetime import date, datetime
from pathlib import Path
from typing import Any

import pandas as pd
from sqlalchemy.orm import Session

from backend.models import (
    AnneeScolaire,
    Personne,
    Site,
    Snapshot,
    TableCorrespondance,
)
from backend.services.arbitrage import (
    cle_collision_login,
    cle_homonymie_ingestion,
    creer_ou_reprendre as creer_arbitrage,
)
from backend.services.parser_charlemagne import lire_htm, lire_xlsx
from backend.services.regles_metier import (
    calculer_login_base,
    collision_reelle,
    detecter_homonymes_ingestion,
    proposer_suffixe,
)

# ---------------------------------------------------------------------------
# Vocabulaire
# ---------------------------------------------------------------------------

TYPES_PERSONNE = ("eleve", "adulte")


# ---------------------------------------------------------------------------
# Résumés retournés au caller
# ---------------------------------------------------------------------------


@dataclass
class HomonymeDansExport:
    """Un groupe de lignes du même export qui partagent (nom, prénom)."""

    nom_normalise: str
    prenom_normalise: str
    ids_charlemagne: list[int]
    distincts_par: str | None = None
    """`l'INE` ou `la date de naissance` quand elle suffit à les départager :
    chacun porte la sienne, et aucune ne se répète. Deux homonymes ainsi
    distingués n'ont rien à demander à personne."""


@dataclass
class CollisionLoginIngestion:
    """Un login déjà pris a nécessité un suffixe pour une nouvelle personne."""

    id_charlemagne: int
    nom: str
    prenom: str
    login_base: str
    login_attribue: str
    """login effectivement attribué à la nouvelle personne (avec suffixe)."""
    personnes_deja_presentes: list[dict]
    """Personnes qui portent déjà des variantes du login (pour arbitrage §5)."""


@dataclass
class PersonneDisparue:
    """Quelqu'un que le référentiel inscrit à l'année, et que l'export ignore."""

    personne_id: int
    badge: int | None
    nom: str
    prenom: str
    classe: str | None
    site: str | None


@dataclass
class RapportIngestion:
    type_personne: str
    annee_libelle: str
    mode: str  # "simulation" | "reel"

    nb_lignes_lues: int = 0
    nb_lignes_ingerees: int = 0
    nb_lignes_ignorees: int = 0
    """Lignes sans nom+prénom ou sans id_charlemagne exploitable."""

    nb_lignes_sans_classe: int = 0
    """Élèves sans classe pour l'année exportée — donc absents de cette
    année-là. Typiquement des sortants d'une année antérieure, remontés par
    l'option « inclure les sortants » de Charlemagne."""

    nb_personnes_creees: int = 0
    nb_personnes_mises_a_jour: int = 0
    nb_snapshots_crees: int = 0
    nb_snapshots_identiques: int = 0
    """Personnes dont l'état n'a pas bougé depuis le dernier snapshot."""

    classes_inconnues: list[str] = field(default_factory=list)
    """Codes classes présents dans l'export mais absents de TableCorrespondance
    (élèves uniquement)."""

    disparus: list[PersonneDisparue] = field(default_factory=list)
    """Inscrits à cette année dans le référentiel, absents de cet export.

    Charlemagne ne les porte plus — ni avec une classe, ni sans. Le
    référentiel, lui, ne supprime jamais : sans ce relevé, ils resteraient
    indéfiniment dans leur dernière classe connue, à gonfler les effectifs
    et à garder un compte Google actif."""

    homonymes_intra_export: list[HomonymeDansExport] = field(default_factory=list)
    collisions_login: list[CollisionLoginIngestion] = field(default_factory=list)
    erreurs: list[str] = field(default_factory=list)
    avertissements: list[str] = field(default_factory=list)
    """Remarques sur le déroulement, sans empêcher l'ingestion."""

    est_bloquee: bool = False
    """True si l'ingestion s'est arrêtée avant commit à cause de classes
    inconnues (mode `reel`). En simulation, `est_bloquee` reste False mais
    `classes_inconnues` est renseignée."""

    appris: list[str] = field(default_factory=list)
    """Ce que l'export a enseigné au-delà de l'identité et de la classe.

    Les codes de classe que CardStudio réclame, les dates d'entrée, les
    photos, les mots de passe. Tout cela s'apprenait d'un second export,
    déposé ailleurs : un export de base qui porte les colonnes suffit."""

    nb_mots_de_passe_lus: int = 0
    nb_mots_de_passe_ranges: int = 0
    coffre_ferme: bool = False
    """Vrai quand l'export porte des mots de passe et que le coffre est
    fermé : ils ne sont pas rangés. L'écran propose de l'ouvrir."""


# ---------------------------------------------------------------------------
# Détection du type d'export
# ---------------------------------------------------------------------------


def detecter_type_export(df: pd.DataFrame) -> str | None:
    """Détermine si l'export ressemble à un fichier élèves ou adultes.

    Ce qui n'existe que chez les adultes — le poste, les matières —
    l'emporte. Puis ce qui n'existe que chez les élèves — la classe, le
    régime, le badge. Ce que les deux peuvent porter ne tranche qu'en
    dernier.

    La date de naissance a longtemps compté parmi les indices « adultes » :
    seul leur export la portait. Un export élèves qui l'ajoute pour KoXo
    aurait été ingéré comme un export de professeurs — deux mille élèves
    créés en adultes. Elle ne tranche plus rien.
    """
    cols = set(df.columns)
    if cols & {"poste_occupe", "matieres", "classes_prof_principal"}:
        return "adulte"
    if cols & {"code_classe", "code_regime", "num_badge"}:
        return "eleve"
    if cols & {"civilite", "adresse_1", "email_personnel"}:
        return "adulte"
    return None


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _lire_dataframe(chemin: Path) -> pd.DataFrame:
    suffix = chemin.suffix.lower()
    if suffix in (".htm", ".html"):
        return lire_htm(chemin)
    if suffix in (".xlsx", ".xls"):
        return lire_xlsx(chemin)
    raise ValueError(f"Format non supporté : {suffix}")


def _s(v: Any) -> str | None:
    """Convertit en str strippée, ou None si vide/NaN."""
    if v is None or (isinstance(v, float) and pd.isna(v)) or pd.isna(v):
        return None
    s = str(v).strip()
    return s or None


def _date(v: Any) -> date | None:
    if v is None or pd.isna(v):
        return None
    if isinstance(v, date):
        return v
    if hasattr(v, "date"):
        return v.date()
    try:
        return pd.to_datetime(v).date()
    except Exception:
        return None


def _int(v: Any) -> int | None:
    if v is None or pd.isna(v):
        return None
    try:
        return int(float(v))
    except (TypeError, ValueError):
        return None


def _domaines_ecole(session: Session) -> set[str]:
    """Domaines déclarés sur les Sites, en minuscules.

    L'export Charlemagne mêle les deux natures d'adresse : celles de
    l'établissement (1251 sur l'export réel) et des adresses personnelles
    (gmail, orange, icloud... — 40 environ). Seules les premières désignent un
    compte Workspace ; retenir une adresse personnelle comme identifiant de
    compte serait une faute.

    Mis en cache sur `session.info` : la liste des sites ne bouge pas pendant
    une ingestion, et la relire par ligne ferait un millier de requêtes.
    """
    cache = session.info.get("_domaines_ecole")
    if cache is None:
        cache = {
            s.domaine_mail.strip().lower()
            for s in session.query(Site).all()
            if s.domaine_mail
        }
        session.info["_domaines_ecole"] = cache
    return cache


def _capturer_email_constate(
    session: Session,
    personne: Personne,
    ligne: dict,
    cles: tuple[str, ...] = ("email",),
) -> None:
    """Mémorise l'adresse d'un compte **existant** si l'export en donne une.

    `cles` liste les colonnes candidates, par ordre de préférence : les
    adultes portent leur adresse d'établissement dans `email_professionnel`.

    Jamais réécrite une fois posée : c'est l'identifiant d'un compte en place,
    au même titre que le login.
    """
    if personne.email_constate:
        return
    for cle in cles:
        brut = _s(ligne.get(cle))
        if not brut or "@" not in brut:
            continue
        adresse = brut.strip().lower()
        if adresse.rsplit("@", 1)[-1] in _domaines_ecole(session):
            personne.email_constate = adresse
            return


def _hash_etat_snapshot(**champs: Any) -> str:
    """Empreinte stable des champs constatés d'un snapshot — sert l'idempotence."""
    parts = []
    for k in sorted(champs):
        v = champs[k]
        if isinstance(v, date):
            v = v.isoformat()
        parts.append(f"{k}={v!r}")
    return hashlib.sha256("|".join(parts).encode("utf-8")).hexdigest()[:32]


def _etat_snapshot_actuel(personne: Personne, annee_id: int, session: Session) -> str | None:
    """Hash du dernier snapshot connu pour (personne, année). None si aucun."""
    dernier = (
        session.query(Snapshot)
        .filter_by(personne_id=personne.id, annee_scolaire_id=annee_id)
        .order_by(Snapshot.date_ingestion.desc())
        .first()
    )
    if dernier is None:
        return None
    return _hash_etat_snapshot(
        nom=dernier.nom,
        prenom=dernier.prenom,
        nom_usage=dernier.nom_usage,
        classe=dernier.classe,
        niveau=dernier.niveau,
        code_etablissement=dernier.code_etablissement,
        regime=dernier.regime,
        chemin_photo=dernier.chemin_photo,
        date_entree=dernier.date_entree,
        poste_occupe=dernier.poste_occupe,
        matieres=dernier.matieres,
        classes_prof_principal=dernier.classes_prof_principal,
        classe_precedente=dernier.classe_precedente,
        classe_an_prochain=dernier.classe_an_prochain,
    )


# ---------------------------------------------------------------------------
# Point d'entrée
# ---------------------------------------------------------------------------


def ingerer_export(
    session: Session,
    chemin_fichier: Path,
    type_personne: str,
    libelle_annee: str,
    mode: str = "simulation",
    cle_coffre: bytes | None = None,
) -> RapportIngestion:
    """Ingère un export Charlemagne dans le référentiel.

    Args:
        session: SQLAlchemy session.
        chemin_fichier: fichier HTM/XLSX à lire.
        type_personne: `eleve` ou `adulte`.
        libelle_annee: année scolaire cible, ex. `2025-2026`.
        mode: `simulation` (défaut, ne commit rien) ou `reel`.
        cle_coffre: la clé du coffre s'il est ouvert. Les mots de passe
            que l'export porte n'y sont rangés qu'à cette condition.

    Returns:
        Un `RapportIngestion` détaillé, sans aucun secret persisté.
    """
    if type_personne not in TYPES_PERSONNE:
        raise ValueError(f"type_personne doit être {TYPES_PERSONNE}, reçu : {type_personne!r}")
    if mode not in ("simulation", "reel"):
        raise ValueError(f"mode doit être 'simulation' ou 'reel', reçu : {mode!r}")

    rapport = RapportIngestion(
        type_personne=type_personne, annee_libelle=libelle_annee, mode=mode
    )

    # Invalide le cache des domaines : un site a pu être déclaré depuis la
    # dernière ingestion sur cette même session.
    session.info.pop("_domaines_ecole", None)

    # 1. Parse
    try:
        df = _lire_dataframe(chemin_fichier)
    except Exception as e:
        rapport.erreurs.append(f"Lecture impossible : {e}")
        rapport.est_bloquee = True
        return rapport

    rapport.nb_lignes_lues = int(len(df))

    if type_personne == "eleve":
        return _ingerer_eleves(
            session, df, libelle_annee, mode, rapport, cle_coffre=cle_coffre
        )
    return _ingerer_adultes(
        session, df, libelle_annee, mode, rapport, cle_coffre=cle_coffre
    )


# ---------------------------------------------------------------------------
# Ingestion élèves
# ---------------------------------------------------------------------------


def _ingerer_eleves(
    session: Session,
    df: pd.DataFrame,
    libelle_annee: str,
    mode: str,
    rapport: RapportIngestion,
    cle_coffre: bytes | None = None,
) -> RapportIngestion:
    # Initialisation du compteur (aussi appelé par la fonction publique mais
    # utile quand _ingerer_eleves est appelé directement — cf. tests unitaires).
    rapport.nb_lignes_lues = int(len(df))

    # a. Vérifie que les colonnes essentielles sont présentes
    for col in ("id_charlemagne", "nom", "prenom", "code_classe"):
        if col not in df.columns:
            rapport.erreurs.append(f"Colonne obligatoire manquante : {col}")
    if rapport.erreurs:
        rapport.est_bloquee = True
        return rapport

    # b. Détecte les homonymes intra-export (pré-check, ne bloque pas)
    lignes = df.to_dict(orient="records")
    for grp in detecter_homonymes_ingestion(lignes, "nom", "prenom"):
        rapport.homonymes_intra_export.append(
            HomonymeDansExport(
                nom_normalise=grp.cle_normalisee[0],
                prenom_normalise=grp.cle_normalisee[1],
                ids_charlemagne=[
                    _int(l.get("id_charlemagne"))
                    for l in grp.lignes
                    if _int(l.get("id_charlemagne")) is not None
                ],
                distincts_par=_ce_qui_les_distingue(grp.lignes),
            )
        )

    # c. Précharge le mapping classe → site depuis TableCorrespondance
    correspondances = session.query(TableCorrespondance).all()
    classe_vers_site: dict[str, int] = {
        c.classe_code_court: c.site_id for c in correspondances
    }
    classes_utilisees = {
        _s(l.get("code_classe")) for l in lignes if _s(l.get("code_classe"))
    }
    classes_inconnues = sorted(
        c for c in classes_utilisees if c and c not in classe_vers_site
    )
    rapport.classes_inconnues = classes_inconnues

    # d. En mode `reel`, blocage si classes inconnues (§8 du prompt).
    #    En simulation, on continue pour donner un rapport complet.
    if classes_inconnues and mode == "reel":
        rapport.est_bloquee = True
        return rapport

    # e. Récupère ou crée l'AnneeScolaire (même en simulation on la crée pour
    #    la relation dans Snapshot — annulée si simulation via rollback final).
    annee = _resoudre_annee(session, libelle_annee)

    # e-bis. Persiste les homonymies détectées comme Arbitrage en attente.
    _persister_arbitrages_homonymies(session, rapport, "eleve")

    maj_etat_courant = _est_annee_la_plus_recente(session, annee)
    if not maj_etat_courant:
        rapport.avertissements.append(
            f"{annee.libelle} n'est pas l'année la plus récente : les snapshots "
            "sont créés, mais la situation courante des personnes (classe, site) "
            "n'est pas réécrite."
        )

    if nb_sans_classe := sum(1 for l in lignes if not _s(l.get("code_classe"))):
        rapport.avertissements.append(
            f"{nb_sans_classe} ligne(s) sans classe pour {annee.libelle} : ces "
            "personnes n'étaient pas inscrites cette année-là — sorties "
            "précédemment, elles ne figurent dans l'export que parce qu'il "
            "inclut les sortants. Elles sont écartées — leur compte se traite "
            "par l'action « Traiter les sortants », pas par un import."
        )

    # f. Boucle d'ingestion
    #
    # On note qui le fichier porte — y compris les lignes sans classe, que
    # Charlemagne connaît encore. Ce que ce relevé ne contient pas à la fin
    # de la boucle, l'export ne le connaît plus.
    ids_vus: set[int] = set()
    sites_vus: set[int] = set()
    table_par_classe = {(c.site_id, c.classe_code_court): c for c in correspondances}
    codes = _CodesDeClasse(ecraser=maj_etat_courant)
    comptes: list[tuple[int, str | None, str]] = []
    for ligne in lignes:
        id_ch = _int(ligne.get("id_charlemagne"))
        nom = _s(ligne.get("nom"))
        prenom = _s(ligne.get("prenom"))
        if id_ch is None or not nom or not prenom:
            rapport.nb_lignes_ignorees += 1
            continue

        code_classe = _s(ligne.get("code_classe"))

        # Aucune classe pour l'année exportée : la personne n'y était pas.
        #
        # Le cas vient des exports « avec les sortants », qui remontent aussi
        # les élèves partis les années d'avant : ils n'ont qu'une classe
        # précédente. Les ingérer les inscrirait dans une année qu'ils n'ont
        # pas faite, sans classe ni site — et les ferait passer pour des
        # sortants de cette rentrée-ci alors qu'ils sont partis avant.
        if not code_classe:
            _noter_vu(session, id_ch, ids_vus)
            # Le compte de ces personnes n'est pas touché ici. Mettre en
            # quarantaine depuis une ingestion serait un effet de bord : sur
            # l'export 2026-2027, ces lignes sont les sortants de la rentrée
            # en cours, dont le traitement passe par une action délibérée et
            # confirmée. Un import charge des données, il ne décide pas du
            # sort des comptes.
            rapport.nb_lignes_sans_classe += 1
            continue

        # Résolution site — si classe inconnue, on saute la personne
        site_id = classe_vers_site.get(code_classe)
        if site_id is None:
            # Déjà comptabilisé dans classes_inconnues
            rapport.nb_lignes_ignorees += 1
            continue

        sites_vus.add(site_id)

        traitee = _traiter_ligne_eleve(
            session=session,
            ligne=ligne,
            id_ch=id_ch,
            nom=nom,
            prenom=prenom,
            code_classe=code_classe,
            site_id=site_id,
            annee=annee,
            rapport=rapport,
            maj_etat_courant=maj_etat_courant,
        )
        codes.apprendre(ligne, table_par_classe.get((site_id, code_classe)))
        if traitee is not None:
            _noter_compte(ligne, *traitee, comptes)
        # Après le traitement, pas avant : un entrant que cette ligne vient
        # de créer n'existait pas encore, et serait sorti porté disparu de
        # l'export qui l'amène.
        _noter_vu(session, id_ch, ids_vus)

    # g. Qui le référentiel inscrit encore et que l'export ne porte plus
    rapport.disparus = _relever_disparus(
        session, annee=annee, type_personne="eleve",
        ids_vus=ids_vus, sites_vus=sites_vus,
    )

    # g-bis. Ce que l'export enseigne en plus : codes de classe, dates
    # d'entrée, photos — et les mots de passe, si le coffre est ouvert.
    codes.conclure(df, lignes, rapport)
    _ranger_mots_de_passe(session, comptes, cle_coffre, mode, rapport)
    _signaler_autres_fiches(session, ids_vus, rapport)

    # h. Commit ou rollback selon le mode
    if mode == "reel" and not rapport.est_bloquee:
        session.commit()
    else:
        session.rollback()

    return rapport


def _noter_vu(session: Session, id_charlemagne: int, ids_vus: set[int]) -> None:
    """Retient la personne du référentiel que cette ligne désigne.

    L'appariement se fait sur l'identifiant Charlemagne : c'est la clé que
    l'export porte, et la seule que le référentiel garde figée. Une ligne
    qui ne correspond à personne — un entrant que l'ingestion va créer —
    n'a rien à noter : elle ne peut pas être portée disparue.
    """
    from backend.services.fusion import personne_par_cle

    p, _ = personne_par_cle(session, "eleve", id_charlemagne)
    if p is not None:
        ids_vus.add(p.id)


def _relever_disparus(
    session: Session,
    *,
    annee,
    type_personne: str,
    ids_vus: set[int],
    sites_vus: set[int],
) -> list[PersonneDisparue]:
    """Les inscrits de l'année que cet export ne porte plus.

    ## Pourquoi ça ne peut se voir qu'ici

    Une ingestion ne réécrit un snapshot que si l'état a changé : sur
    l'export de septembre 2026, mille six cent soixante-trois personnes ont
    été mises à jour pour quatre-vingt-deux snapshots créés. La date du
    dernier snapshot ne dit donc pas si quelqu'un était dans le fichier — il
    faut le fichier en main, c'est-à-dire ici.

    ## Le garde-fou

    Un export NDK+SU ne parle pas de NDE : sans restriction, ses cent
    vingt-sept élèves passeraient pour disparus. Le relevé se limite donc
    aux **sites que cet export couvre**, et au type de population ingéré.

    Il reste une limite, dite à l'écran : un export partiel — une seule
    classe, un seul niveau — fera passer tous les autres pour disparus. Le
    relevé informe, il n'agit pas.
    """
    if not sites_vus:
        return []

    lignes = (
        session.query(Personne, Site.nom)
        .outerjoin(Site, Site.id == Personne.site_id)
        .filter(
            Personne.type == type_personne,
            Personne.site_id.in_(sites_vus),
            Personne.id.notin_(ids_vus or {0}),
            Personne.id.in_(
                session.query(Snapshot.personne_id).filter(
                    Snapshot.annee_scolaire_id == annee.id
                )
            ),
        )
        .order_by(Personne.classe, Personne.nom, Personne.prenom)
        .all()
    )
    return [
        PersonneDisparue(
            personne_id=p.id, badge=p.badge, nom=p.nom, prenom=p.prenom,
            classe=p.classe, site=nom_site,
        )
        for p, nom_site in lignes
    ]


def _traiter_ligne_eleve(
    *,
    session: Session,
    ligne: dict,
    id_ch: int,
    nom: str,
    prenom: str,
    code_classe: str | None,
    site_id: int | None,
    annee: AnneeScolaire,
    rapport: RapportIngestion,
    maj_etat_courant: bool = True,
) -> tuple[Personne, bool] | None:
    """Traite une ligne d'export élève : Personne + Snapshot.

    Rend la personne et si elle a été reconnue par un ancien numéro, ou
    `None` quand la ligne n'a pu être traitée.
    """
    from backend.services.fusion import personne_par_cle

    personne, par_ancienne_fiche = personne_par_cle(session, "eleve", id_ch)
    est_nouveau = personne is None

    if est_nouveau:
        # Attribution du login — via proposer_suffixe pour gérer collisions
        base = calculer_login_base(prenom, nom)
        proposition = proposer_suffixe(session, base)
        if proposition is None:
            rapport.erreurs.append(
                f"Impossible d'attribuer un login pour {nom} {prenom} (id={id_ch})"
            )
            return
        # Un identifiant identique dans deux annuaires distincts n'est pas
        # un conflit : personne ne se marche dessus. Le référentiel suffixe
        # quand même — sa colonne est unique — mais on ne réclame pas un
        # arbitrage pour un problème qui n'existe pas.
        conflits = (
            collision_reelle(
                session,
                type_personne="eleve",
                site_id=site_id,
                personnes_en_conflit=proposition.personnes_en_conflit,
            )
            if proposition.a_conflit
            else []
        )
        if conflits:
            collision = CollisionLoginIngestion(
                id_charlemagne=id_ch,
                nom=nom,
                prenom=prenom,
                login_base=base,
                login_attribue=proposition.login_propose,
                personnes_deja_presentes=[
                    {
                        "personne_id": c.personne_id,
                        "cle_pivot": c.cle_pivot,
                        "login": c.login,
                        "type": c.type,
                        "nom": c.nom,
                        "prenom": c.prenom,
                    }
                    for c in conflits
                ],
            )
            rapport.collisions_login.append(collision)
            _persister_arbitrage_collision(session, collision, "eleve", annee.libelle)
        personne = Personne(
            type="eleve",
            id_charlemagne=id_ch,
            badge=Personne.calculer_badge("eleve", id_ch),
            login=proposition.login_propose,
            nom=nom,
            prenom=prenom,
            classe=code_classe,
            niveau=_s(ligne.get("code_niveau")),
            site_id=site_id,
            regime=_s(ligne.get("code_regime")),
            code_etablissement=_s(ligne.get("code_etablissement")),
            date_entree=_date(ligne.get("date_entree")),
            chemin_photo_constate=_s(ligne.get("photo_chemin")),
            ine=_ine(ligne.get("ine")),
            date_naissance=_date(ligne.get("date_naissance")),
        )
        session.add(personne)
        session.flush()  # pour obtenir personne.id
        rapport.nb_personnes_creees += 1
    else:
        # Mise à jour de l'état courant — le login est FIGÉ, on ne touche pas
        # Une ingestion d'année ancienne crée bien son snapshot, mais ne
        # réécrit pas la situation présente de la personne.
        #
        # Un ancien numéro non plus : la fiche qu'il désignait a été réunie
        # à celle-ci, qui décrit seule la personne. L'export NDE de l'an
        # dernier ramènerait sinon à NDE, en 4e, un élève passé en 3e à NDK.
        if maj_etat_courant and not par_ancienne_fiche:
            _maj_champs_courants_eleve(personne, ligne, code_classe, site_id)
        _relever_identite(
            personne, ligne, ecraser=maj_etat_courant and not par_ancienne_fiche
        )
        rapport.nb_personnes_mises_a_jour += 1

    # Adresse du compte existant — posée aussi sur une personne déjà connue,
    # qui peut avoir été amorcée depuis KoXo sans que son adresse soit relevée.
    # Celle d'une ancienne fiche aussi : le compte suit la personne.
    _capturer_email_constate(session, personne, ligne)

    # Snapshot : ne crée qu'un nouveau si l'état diffère
    if not par_ancienne_fiche or not _inscrite_cette_annee(session, personne, annee):
        _peut_etre_creer_snapshot(
            session=session,
            personne=personne,
            annee=annee,
            ligne=ligne,
            type_personne="eleve",
            rapport=rapport,
        )

    rapport.nb_lignes_ingerees += 1
    return personne, par_ancienne_fiche


class _CodesDeClasse:
    """Le code niveau et le code établissement, appris au fil des lignes.

    Ce sont des attributs de la **classe** : `2_1` est en `1-2NDES-LY` et
    `03-LY` pour tous ses élèves. CardStudio les réclame, et rien d'autre
    ne les donne : ils s'apprenaient d'un export CardStudio déposé sur
    l'écran des cartes. Un export de base qui porte les deux colonnes les
    enseigne maintenant au passage, et l'écran des cartes n'a plus rien à
    demander.

    Un export d'une année passée complète ce qui manque sans rien réécrire :
    une classe peut changer de niveau d'une année à l'autre. Deux élèves
    d'une même classe qui disent deux codes différents ne tranchent rien —
    le premier lu est gardé, et le désaccord est dit.
    """

    CHAMPS = (("code_niveau", "code_niveau"), ("code_etablissement", "code_etablissement"))

    def __init__(self, *, ecraser: bool) -> None:
        self.ecraser = ecraser
        self.premiers: dict[tuple[int, str], str] = {}
        self.apprises: set[str] = set()
        self.desaccords: set[str] = set()
        self.vues: dict[int, TableCorrespondance] = {}

    def apprendre(self, ligne: dict, correspondance) -> None:
        if correspondance is None:
            return
        self.vues[correspondance.id] = correspondance
        for champ, colonne in self.CHAMPS:
            valeur = _s(ligne.get(colonne))
            if not valeur:
                continue
            premier = self.premiers.setdefault((correspondance.id, champ), valeur)
            if premier != valeur:
                self.desaccords.add(correspondance.classe_code_court)
                continue
            actuelle = getattr(correspondance, champ)
            if actuelle == valeur or (actuelle and not self.ecraser):
                continue
            setattr(correspondance, champ, valeur)
            self.apprises.add(correspondance.classe_code_court)

    def conclure(self, df: pd.DataFrame, lignes: list[dict], rapport) -> None:
        colonnes = set(df.columns)
        if {"code_niveau", "code_etablissement"} & colonnes:
            completes = sum(
                1 for t in self.vues.values() if t.code_niveau and t.code_etablissement
            )
            texte = (
                f"Codes niveau et établissement : {len(self.apprises)} classe(s) "
                "apprise(s)"
                if self.apprises
                else "Codes niveau et établissement : rien de nouveau"
            )
            rapport.appris.append(
                f"{texte} — {completes} classe(s) sur {len(self.vues)} les ont "
                "tous les deux, CardStudio n'a rien à redemander pour elles."
            )
        else:
            sans = sorted(
                t.classe_code_court
                for t in self.vues.values()
                if not (t.code_niveau and t.code_etablissement)
            )
            # Dit parmi ce que l'export apprend, pas en avertissement : rien
            # n'est faux dans cette ingestion, il manque juste deux colonnes.
            if sans:
                rapport.appris.append(
                    f"Codes niveau et établissement : absents de l'export, et "
                    f"{len(sans)} classe(s) n'en ont pas encore. Ajoute « Code "
                    "niveau » et « Code établissement » à l'export Charlemagne "
                    "pour que les cartes CardStudio les trouvent."
                )
        if self.desaccords:
            rapport.avertissements.append(
                "Deux codes différents pour une même classe dans l'export : "
                + ", ".join(sorted(self.desaccords))
                + ". Le premier lu est gardé."
            )
        for colonne, libelle in (
            ("date_entree", "Date d'entrée"),
            ("photo_chemin", "Chemin de photo"),
        ):
            if colonne in colonnes:
                n = sum(
                    1
                    for l in lignes
                    if _s(l.get("code_classe")) and not _vide(l.get(colonne))
                )
                rapport.appris.append(f"{libelle} : {n} élève(s).")


def _ine(v: Any) -> str | None:
    """L'INE sans espace, en capitales : `1234567890A`. Tel quel sinon."""
    s = _s(v)
    return "".join(s.split()).upper() if s else None


def _relever_identite(personne: Personne, ligne: dict, *, ecraser: bool) -> None:
    """L'INE et la date de naissance, complétés toujours, réécrits rarement.

    Ce sont des attributs de la personne, pas de l'année. Un export d'une
    année passée — ou l'ancien numéro d'une fiche réunie — les complète
    quand ils manquent ; seul l'export de l'année la plus récente les
    réécrit, pour ne pas défaire une correction faite depuis dans
    Charlemagne.
    """
    ine = _ine(ligne.get("ine"))
    if ine and (ecraser or not personne.ine):
        personne.ine = ine
    naissance = _date(ligne.get("date_naissance"))
    if naissance and (ecraser or not personne.date_naissance):
        personne.date_naissance = naissance


def _ce_qui_les_distingue(lignes: list[dict]) -> str | None:
    """Ce qui suffit à départager des homonymes du même export, s'il y a.

    Il faut que **chacun** porte la valeur et qu'aucune ne se répète : une
    seule date manquante, et rien ne dit que cette ligne n'est pas le
    double d'une autre.
    """
    for champ, lecture, libelle in (
        ("ine", _ine, "l'INE"),
        ("date_naissance", _date, "la date de naissance"),
    ):
        valeurs = [lecture(l.get(champ)) for l in lignes]
        if all(valeurs) and len(set(valeurs)) == len(valeurs):
            return libelle
    return None


def _signaler_autres_fiches(
    session: Session, ids_vus: set[int], rapport: RapportIngestion
) -> None:
    """Les élèves de cet export que le référentiel connaît sous un autre numéro.

    Même INE, deux fiches : un seul élève, que l'autre base Charlemagne a
    numéroté à sa façon — le passage de NDE à NDK. L'ingestion ne les
    réunit pas, le programme ne tranche jamais seul ; mais elle le dit
    tout de suite, plutôt qu'au jour où les deux fiches se disputent une
    adresse.
    """
    if not ids_vus:
        return
    par_ine: dict[str, list[Personne]] = {}
    for p in session.query(Personne).filter(Personne.ine.isnot(None)):
        par_ine.setdefault(p.ine, []).append(p)
    doubles = [
        ps for ps in par_ine.values()
        if len(ps) > 1 and any(p.id in ids_vus for p in ps)
    ]
    if not doubles:
        return
    exemples = ", ".join(
        " = ".join(p.cle_pivot for p in ps) + f" ({ps[0].prenom} {ps[0].nom})"
        for ps in doubles[:5]
    )
    rapport.avertissements.append(
        f"{len(doubles)} élève(s) de cet export ont déjà une autre fiche sous "
        f"le même INE — {exemples}{', …' if len(doubles) > 5 else ''}. Un "
        "seul élève à chaque fois : réunis ses fiches dans « Départager »."
    )


def _vide(v: Any) -> bool:
    return v is None or (not isinstance(v, str) and pd.isna(v)) or not str(v).strip()


def _noter_compte(
    ligne: dict,
    personne: Personne,
    par_ancienne_fiche: bool,
    comptes: list[tuple[int, str | None, str]],
) -> None:
    """Retient le compte réseau que Charlemagne garde pour cette personne.

    Pas celui d'un ancien numéro : c'était le compte de l'ancienne fiche,
    et il ne doit pas remplacer celui que porte la fiche gardée.
    """
    if par_ancienne_fiche:
        return
    mdp = _s(ligne.get("mdp_charlemagne"))
    if mdp:
        comptes.append((personne.id, _s(ligne.get("login_charlemagne")), mdp))


def _ranger_mots_de_passe(
    session: Session,
    comptes: list[tuple[int, str | None, str]],
    cle: bytes | None,
    mode: str,
    rapport: RapportIngestion,
) -> None:
    """Range au coffre les mots de passe que Charlemagne garde.

    Ce sont ceux de « MDP Réseau Péda », que la direction lit dans
    Charlemagne. Ils vont au coffre à côté de ceux relevés dans KoXo, sous
    la cible `charlemagne` : jamais à leur place — KoXo tient le compte et
    fait foi —, et avec l'identifiant que Charlemagne leur associe.

    Coffre fermé, rien n'est rangé, et le rapport le dit : réappliquer
    l'ingestion coffre ouvert suffit, elle ne refait que ce qui manque.
    Aucun mot de passe ne quitte cette fonction — le rapport ne porte que
    des comptes.
    """
    rapport.nb_mots_de_passe_lus = len(comptes)
    if not comptes:
        return
    if cle is None:
        # L'écran propose d'ouvrir le coffre sur la foi de `coffre_ferme` :
        # un avertissement de plus redirait la même chose deux fois.
        rapport.coffre_ferme = True
        rapport.appris.append(
            f"Mots de passe réseau : {len(comptes)} dans l'export, coffre "
            "fermé — rien n'est rangé."
        )
        return
    if mode != "reel":
        rapport.appris.append(
            f"Mots de passe réseau : {len(comptes)} seront rangés au coffre."
        )
        return

    from backend.services.coffre import deposer

    for personne_id, identifiant, mdp in comptes:
        deposer(
            session, cle, personne_id=personne_id, mot_de_passe=mdp,
            cible="charlemagne", site=None, origine="charlemagne",
            identifiant=identifiant,
        )
    rapport.nb_mots_de_passe_ranges = len(comptes)
    rapport.appris.append(
        f"Mots de passe réseau : {len(comptes)} rangés au coffre, avec "
        "l'identifiant que Charlemagne leur associe."
    )


def _inscrite_cette_annee(
    session: Session, personne: Personne, annee: AnneeScolaire
) -> bool:
    """La personne a-t-elle déjà une classe pour cette année ?

    Sert aux anciens numéros : ils complètent le parcours d'une année
    qu'il ne connaît pas, jamais une année que la fiche gardée décrit — sa
    classe fait foi, comme lors de la fusion.
    """
    return (
        session.query(Snapshot.id)
        .filter_by(personne_id=personne.id, annee_scolaire_id=annee.id)
        .first()
        is not None
    )


def _maj_champs_courants_eleve(
    personne: Personne, ligne: dict, code_classe: str | None, site_id: int | None
) -> None:
    """Met à jour uniquement les champs d'état courant (login figé)."""
    personne.nom = _s(ligne.get("nom")) or personne.nom
    personne.prenom = _s(ligne.get("prenom")) or personne.prenom
    personne.classe = code_classe
    personne.site_id = site_id
    personne.niveau = _s(ligne.get("code_niveau")) or personne.niveau
    personne.regime = _s(ligne.get("code_regime")) or personne.regime
    personne.code_etablissement = _s(ligne.get("code_etablissement")) or personne.code_etablissement
    de = _date(ligne.get("date_entree"))
    if de is not None:
        personne.date_entree = de
    photo = _s(ligne.get("photo_chemin"))
    if photo is not None:
        personne.chemin_photo_constate = photo


def _peut_etre_creer_snapshot(
    *,
    session: Session,
    personne: Personne,
    annee: AnneeScolaire,
    ligne: dict,
    type_personne: str,
    rapport: RapportIngestion,
) -> None:
    """Crée un Snapshot si les valeurs constatées diffèrent du dernier snapshot.

    Les valeurs viennent de la **ligne**, pas de l'état courant de la
    personne. Ces deux sources coïncidaient tant que la personne était
    systématiquement mise à jour depuis la même ligne juste avant — ce qui
    n'est plus le cas en ingérant une année ancienne. Un snapshot décrit ce
    que disait *ce fichier-là* : le lire ailleurs le rendrait faux.

    Le repli sur la personne ne sert qu'aux colonnes absentes du format.
    """
    champs_snapshot = {
        "nom": _s(ligne.get("nom")) or personne.nom,
        "prenom": _s(ligne.get("prenom")) or personne.prenom,
        "nom_usage": _s(ligne.get("nom_usage")),
        "classe": _s(ligne.get("code_classe")) or personne.classe,
        "niveau": _s(ligne.get("code_niveau")),
        "code_etablissement": (
            _s(ligne.get("code_etablissement")) or personne.code_etablissement
        ),
        "regime": _s(ligne.get("code_regime")) or personne.regime,
        "chemin_photo": _s(ligne.get("photo_chemin")) or personne.chemin_photo_constate,
        "date_entree": _date(ligne.get("date_entree")) or personne.date_entree,
        "poste_occupe": _s(ligne.get("poste_occupe")) or personne.poste_occupe,
        "matieres": _s(ligne.get("matieres")) or personne.matieres,
        "classes_prof_principal": (
            _s(ligne.get("classes_prof_principal")) or personne.classes_prof_principal
        ),
        "classe_precedente": _s(ligne.get("code_classe_precedente")),
        "classe_an_prochain": _s(ligne.get("code_classe_an_prochain")),
    }

    hash_courant = _hash_etat_snapshot(**champs_snapshot)
    hash_dernier = _etat_snapshot_actuel(personne, annee.id, session)

    if hash_dernier == hash_courant:
        rapport.nb_snapshots_identiques += 1
        return

    snap = Snapshot(
        personne_id=personne.id,
        annee_scolaire_id=annee.id,
        **champs_snapshot,
    )
    session.add(snap)
    session.flush()
    rapport.nb_snapshots_crees += 1


# ---------------------------------------------------------------------------
# Ingestion adultes
# ---------------------------------------------------------------------------


def _ingerer_adultes(
    session: Session,
    df: pd.DataFrame,
    libelle_annee: str,
    mode: str,
    rapport: RapportIngestion,
    cle_coffre: bytes | None = None,
) -> RapportIngestion:
    rapport.nb_lignes_lues = int(len(df))
    for col in ("id_charlemagne", "nom", "prenom"):
        if col not in df.columns:
            rapport.erreurs.append(f"Colonne obligatoire manquante : {col}")
    if rapport.erreurs:
        rapport.est_bloquee = True
        return rapport

    lignes = df.to_dict(orient="records")

    # Homonymes intra-export
    for grp in detecter_homonymes_ingestion(lignes, "nom", "prenom"):
        rapport.homonymes_intra_export.append(
            HomonymeDansExport(
                nom_normalise=grp.cle_normalisee[0],
                prenom_normalise=grp.cle_normalisee[1],
                ids_charlemagne=[
                    _int(l.get("id_charlemagne"))
                    for l in grp.lignes
                    if _int(l.get("id_charlemagne")) is not None
                ],
            )
        )

    annee = _resoudre_annee(session, libelle_annee)

    _persister_arbitrages_homonymies(session, rapport, "adulte")

    maj_etat_courant = _est_annee_la_plus_recente(session, annee)
    if not maj_etat_courant:
        rapport.avertissements.append(
            f"{annee.libelle} n'est pas l'année la plus récente : les snapshots "
            "sont créés, mais la situation courante des personnes n'est pas réécrite."
        )

    comptes: list[tuple[int, str | None, str]] = []
    for ligne in lignes:
        id_ch = _int(ligne.get("id_charlemagne"))
        nom = _s(ligne.get("nom"))
        prenom = _s(ligne.get("prenom"))
        if id_ch is None or not nom or not prenom:
            rapport.nb_lignes_ignorees += 1
            continue
        traitee = _traiter_ligne_adulte(
            session=session,
            ligne=ligne,
            id_ch=id_ch,
            nom=nom,
            prenom=prenom,
            annee=annee,
            rapport=rapport,
            maj_etat_courant=maj_etat_courant,
        )
        if traitee is not None:
            _noter_compte(ligne, *traitee, comptes)

    _ranger_mots_de_passe(session, comptes, cle_coffre, mode, rapport)

    if mode == "reel":
        session.commit()
    else:
        session.rollback()
    return rapport


def _traiter_ligne_adulte(
    *,
    session: Session,
    ligne: dict,
    id_ch: int,
    nom: str,
    prenom: str,
    annee: AnneeScolaire,
    rapport: RapportIngestion,
    maj_etat_courant: bool = True,
) -> None:
    from backend.services.fusion import personne_par_cle

    personne, par_ancienne_fiche = personne_par_cle(session, "adulte", id_ch)
    est_nouveau = personne is None

    if est_nouveau:
        base = calculer_login_base(prenom, nom)
        proposition = proposer_suffixe(session, base)
        if proposition is None:
            rapport.erreurs.append(
                f"Impossible d'attribuer un login pour {nom} {prenom} (id={id_ch})"
            )
            return
        # Un identifiant identique dans deux annuaires distincts n'est pas
        # un conflit : personne ne se marche dessus. Le référentiel suffixe
        # quand même — sa colonne est unique — mais on ne réclame pas un
        # arbitrage pour un problème qui n'existe pas.
        conflits = (
            collision_reelle(
                session,
                type_personne="adulte",
                site_id=None,
                personnes_en_conflit=proposition.personnes_en_conflit,
            )
            if proposition.a_conflit
            else []
        )
        if conflits:
            collision = CollisionLoginIngestion(
                id_charlemagne=id_ch,
                nom=nom,
                prenom=prenom,
                login_base=base,
                login_attribue=proposition.login_propose,
                personnes_deja_presentes=[
                    {
                        "personne_id": c.personne_id,
                        "cle_pivot": c.cle_pivot,
                        "login": c.login,
                        "type": c.type,
                        "nom": c.nom,
                        "prenom": c.prenom,
                    }
                    for c in conflits
                ],
            )
            rapport.collisions_login.append(collision)
            _persister_arbitrage_collision(session, collision, "adulte", annee.libelle)
        personne = Personne(
            type="adulte",
            id_charlemagne=id_ch,
            badge=Personne.calculer_badge("adulte", id_ch),
            login=proposition.login_propose,
            nom=nom,
            prenom=prenom,
            civilite=_s(ligne.get("civilite")),
            poste_occupe=_s(ligne.get("poste_occupe")),
            matieres=_s(ligne.get("matieres")),
            classes_prof_principal=_s(ligne.get("classes_prof_principal")),
            email_professionnel=_s(ligne.get("email_professionnel")),
            email_personnel=_s(ligne.get("email_personnel")),
            ine=_ine(ligne.get("ine")),
            date_naissance=_date(ligne.get("date_naissance")),
        )
        session.add(personne)
        session.flush()
        rapport.nb_personnes_creees += 1
    else:
        if maj_etat_courant and not par_ancienne_fiche:
            _maj_champs_courants_adulte(personne, ligne)
        _relever_identite(
            personne, ligne, ecraser=maj_etat_courant and not par_ancienne_fiche
        )
        rapport.nb_personnes_mises_a_jour += 1

    _capturer_email_constate(session, personne, ligne, ("email", "email_professionnel"))

    if not par_ancienne_fiche or not _inscrite_cette_annee(session, personne, annee):
        _peut_etre_creer_snapshot(
            session=session,
            personne=personne,
            annee=annee,
            ligne=ligne,
            type_personne="adulte",
            rapport=rapport,
        )
    rapport.nb_lignes_ingerees += 1
    return personne, par_ancienne_fiche


def _maj_champs_courants_adulte(personne: Personne, ligne: dict) -> None:
    personne.nom = _s(ligne.get("nom")) or personne.nom
    personne.prenom = _s(ligne.get("prenom")) or personne.prenom
    personne.civilite = _s(ligne.get("civilite")) or personne.civilite
    personne.poste_occupe = _s(ligne.get("poste_occupe")) or personne.poste_occupe
    personne.matieres = _s(ligne.get("matieres")) or personne.matieres
    personne.classes_prof_principal = (
        _s(ligne.get("classes_prof_principal")) or personne.classes_prof_principal
    )
    ep = _s(ligne.get("email_professionnel"))
    if ep is not None:
        personne.email_professionnel = ep
    ei = _s(ligne.get("email_personnel"))
    if ei is not None:
        personne.email_personnel = ei


# ---------------------------------------------------------------------------
# Utilitaires
# ---------------------------------------------------------------------------


def _est_annee_la_plus_recente(session: Session, annee: AnneeScolaire) -> bool:
    """L'année ingérée est-elle la plus récente que l'on connaisse ?

    Les champs d'état courant de `Personne` (classe, site, régime…) décrivent
    la situation d'aujourd'hui. Les laisser écraser par n'importe quelle
    ingestion les rend dépendants de l'**ordre** des imports : réingérer
    2025-2026 après 2026-2027 ferait redescendre tout le monde d'une classe.

    Le cas est concret : pour détecter les sortants, il faut réimporter
    l'année passée avec les élèves partis — donc forcément après l'année
    nouvelle. Sans ce garde-fou, cette manipulation nécessaire abîmerait le
    référentiel.

    Comparaison sur le libellé `AAAA-AAAA`, qui s'ordonne alphabétiquement.
    """
    libelles = [a.libelle for a in session.query(AnneeScolaire).all()]
    return not libelles or annee.libelle >= max(libelles)


def _resoudre_annee(session: Session, libelle: str) -> AnneeScolaire:
    """Récupère ou crée l'AnneeScolaire par libellé."""
    annee = session.query(AnneeScolaire).filter_by(libelle=libelle).one_or_none()
    if annee is None:
        annee = AnneeScolaire(libelle=libelle, est_active=True)
        session.add(annee)
        session.flush()
    return annee


def _persister_arbitrages_homonymies(
    session: Session,
    rapport: RapportIngestion,
    type_personne: str,
) -> None:
    """Crée un Arbitrage en attente par groupe d'homonymes intra-export.

    Idempotent via cle_cas — un même trio (nom, prénom, IDs) ne créera
    qu'un seul arbitrage même si l'ingestion est rejouée.
    """
    from backend.services.arbitrage import trancher

    prefixe = "E" if type_personne == "eleve" else "A"
    for h in rapport.homonymes_intra_export:
        cles = [f"{prefixe}{i}" for i in h.ids_charlemagne]
        arbitrage = creer_arbitrage(
            session,
            type_cas="homonymie_ingestion",
            cle_cas=cle_homonymie_ingestion(h.nom_normalise, h.prenom_normalise, cles),
            contexte={
                "type_personne": type_personne,
                "nom_normalise": h.nom_normalise,
                "prenom_normalise": h.prenom_normalise,
                "ids_charlemagne": h.ids_charlemagne,
                "annee_libelle": rapport.annee_libelle,
            },
        )
        # Chacun sa date de naissance, ou son INE : deux personnes, et
        # c'est un fait, pas une présomption. Demander à un humain de le
        # confirmer serait lui faire recopier ce que l'export dit déjà.
        if h.distincts_par:
            trancher(
                session, arbitrage.id, "personnes_distinctes",
                note=f"Départagés par {h.distincts_par}, relevé dans l'export.",
            )


def _persister_arbitrage_collision(
    session: Session,
    collision: CollisionLoginIngestion,
    type_personne: str,
    annee_libelle: str,
) -> None:
    """Crée un Arbitrage pour une collision de login détectée à l'ingestion."""
    prefixe = "E" if type_personne == "eleve" else "A"
    cle_pivot = f"{prefixe}{collision.id_charlemagne}"
    creer_arbitrage(
        session,
        type_cas="collision_login",
        cle_cas=cle_collision_login(collision.login_base, cle_pivot),
        contexte={
            "type_personne": type_personne,
            "id_charlemagne": collision.id_charlemagne,
            "nom": collision.nom,
            "prenom": collision.prenom,
            "login_base": collision.login_base,
            "login_attribue": collision.login_attribue,
            "personnes_deja_presentes": collision.personnes_deja_presentes,
            "annee_libelle": annee_libelle,
        },
    )
