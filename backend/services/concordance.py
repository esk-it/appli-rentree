"""Ce que chaque source dit de la classe d'un élève, mis côte à côte.

## Pourquoi cet écran existe

Quatre systèmes portent la classe d'un élève, et chacun l'apprend à un
moment différent :

| Source | Comment elle apprend | Ce qui la met en retard |
|---|---|---|
| **Charlemagne** | la vie scolaire l'y saisit | rien — c'est l'origine |
| **Référentiel** | une ingestion | tant qu'on n'a pas ré-ingéré |
| **Google** | une bascule d'OU et une synchro de groupes | tant qu'on ne les relance pas |
| **KoXo** | une synchronisation depuis un fichier | idem |

À la rentrée 2026, quarante-quatre élèves avaient changé de classe dans
Charlemagne après le premier import. Le référentiel a suivi à la
ré-ingestion ; Google et KoXo, jamais. Personne ne l'a vu pendant deux
semaines, parce qu'aucun écran ne montrait les quatre valeurs ensemble :
le bilan comparait le référentiel à Google, le contrôle KoXo comparait
KoXo au référentiel, et Charlemagne n'entrait que par l'ingestion.

## Ce que ce service fait, et ne fait pas

Il **lit** et il **aligne les colonnes**. Il ne corrige rien : la
correction passe par le changement de classe, qui existe déjà et qui sait
déplacer l'unité et échanger les groupes en une fois.

Charlemagne fait foi par défaut — c'est la source administrative, celle où
la vie scolaire saisit. Mais « par défaut » veut dire *proposé*, pas
*imposé* : l'écran coche, l'utilisateur décoche. Vécu le 3 septembre 2026,
une élève que Charlemagne plaçait en 2_4 était en réalité en 2_5, et
personne d'autre que l'utilisateur ne pouvait le savoir.

## La classe que Google porte

Google ne stocke pas de classe : il porte une **unité d'organisation** et
des **appartenances de groupe**. La classe s'en déduit par la table de
correspondance, à l'envers. Quand l'unité n'y correspond à rien — une
unité d'attente, un dossier de sortants — la classe Google est `None`, et
ce n'est pas une divergence : c'est une absence.
"""
from __future__ import annotations

from dataclasses import dataclass, field

from sqlalchemy.orm import Session

from backend.models import AnneeScolaire, Personne, Site, TableCorrespondance
from backend.services.csv_charlemagne import champs, decoder, lignes_du_fichier, lire

COLONNES_REQUISES = ("Num Badge", "Code classe")


class ConcordanceImpossible(Exception):
    """Le croisement est refusé, et le message dit pourquoi."""


@dataclass
class LigneConcordance:
    """Un élève, et ce que chaque source dit de sa classe."""

    personne_id: int | None
    badge: str
    nom: str
    prenom: str
    site: str | None

    charlemagne: str | None
    referentiel: str | None
    google_classe: str | None
    google_ou: str | None
    koxo: str | None
    koxo_consulte: bool = False
    """Faux quand l'export déposé ne parle pas de l'établissement de
    l'élève : sa colonne se tait plutôt que d'accuser."""

    genres: list[str] = field(default_factory=list)
    """Ce qui diverge : `referentiel`, `google`, `koxo`, `sans_compte`…"""

    propose: str | None = None
    """La classe retenue par défaut — celle de Charlemagne."""

    @property
    def a_corriger(self) -> bool:
        return bool(self.genres)


@dataclass
class RapportConcordance:
    annee_libelle: str
    google_consulte: bool = False
    koxo_fourni: bool = False
    koxo_sites: list[str] = field(default_factory=list)
    """Les établissements dont l'export KoXo déposé parle.

    KoXo a une base par établissement : un export ne peut en couvrir qu'un.
    Les élèves des autres ne sont pas « absents de KoXo », ils sont hors du
    champ de ce fichier."""

    nb_lignes_lues: int = 0
    nb_accord: int = 0
    lignes: list[LigneConcordance] = field(default_factory=list)
    """Seulement celles qui divergent : l'accord n'a rien à montrer."""

    @property
    def nb_a_corriger(self) -> int:
        return len(self.lignes)

    @property
    def classes_concernees(self) -> list[str]:
        """Les classes à passer en bascule — celles d'arrivée, pas de départ.

        C'est la liste que l'écran des OU et celui des groupes attendent.
        """
        return sorted({l.propose for l in self.lignes if l.propose})

    def par_genre(self) -> dict[str, int]:
        compte: dict[str, int] = {}
        for l in self.lignes:
            for g in l.genres:
                compte[g] = compte.get(g, 0) + 1
        return compte


def croiser(
    session: Session,
    contenu_charlemagne: bytes,
    *,
    annee_id: int,
    comptes_google: list[dict] | None = None,
    membres_par_groupe: dict[str, list[str] | None] | None = None,
    lignes_koxo: list | None = None,
) -> RapportConcordance:
    """Met côte à côte Charlemagne, le référentiel, Google et KoXo.

    Args:
        contenu_charlemagne: l'export portant `Num Badge` et `Code classe`.
        comptes_google: retour de `ClientGoogle.lister_utilisateurs`. Sans
            lui, la colonne Google reste vide plutôt que fausse.
        lignes_koxo: retour de `lire_export_brut`, si l'on a déposé un
            export KoXo.

    Raises:
        ConcordanceImpossible: fichier vide ou sans les colonnes voulues.
    """
    annee = session.query(AnneeScolaire).filter_by(id=annee_id).one_or_none()
    if annee is None:
        raise ConcordanceImpossible(f"Année introuvable : {annee_id}")

    source = _lire_source(contenu_charlemagne)

    par_badge = {
        str(p.badge): p
        for p in session.query(Personne).filter(Personne.type == "eleve").all()
        if p.badge is not None
    }
    sites = {s.id: s.nom for s in session.query(Site).all()}
    classe_par_ou, groupe_vers_classe = _index_table(session)
    ou_par_adresse, groupes_par_adresse = _index_google(
        comptes_google, membres_par_groupe
    )
    koxo_par_id = _index_koxo(lignes_koxo)
    koxo_sites = _sites_couverts_par_koxo(session, lignes_koxo, par_badge)

    rapport = RapportConcordance(
        annee_libelle=annee.libelle,
        google_consulte=comptes_google is not None,
        koxo_fourni=lignes_koxo is not None,
        koxo_sites=sorted(koxo_sites),
    )

    for enr in source:
        classe_ch = enr["classe"]
        if not classe_ch:
            # Sans classe chez Charlemagne, l'élève n'est pas inscrit cette
            # année : c'est un sortant, et il se traite ailleurs.
            continue
        rapport.nb_lignes_lues += 1

        badge = enr["badge"]
        p = par_badge.get(badge)
        adresse = (p.email or "").strip().lower() if p is not None else ""

        ligne = LigneConcordance(
            personne_id=p.id if p is not None else None,
            badge=badge,
            nom=enr["nom"] or (p.nom if p else ""),
            prenom=enr["prenom"] or (p.prenom if p else ""),
            site=sites.get(p.site_id) if p is not None else None,
            charlemagne=classe_ch,
            referentiel=(p.classe or None) if p is not None else None,
            google_ou=ou_par_adresse.get(adresse),
            google_classe=classe_par_ou.get((ou_par_adresse.get(adresse) or "").lower()),
            koxo=koxo_par_id.get(badge),
            koxo_consulte=(
                p is not None and sites.get(p.site_id) in koxo_sites
            ),
            propose=classe_ch,
        )
        _classer(ligne, groupes_par_adresse.get(adresse, set()), groupe_vers_classe,
                 rapport)
        if ligne.a_corriger:
            rapport.lignes.append(ligne)
        else:
            rapport.nb_accord += 1

    rapport.lignes.sort(key=lambda l: (l.propose or "", l.nom, l.prenom))
    return rapport


def _lire_source(contenu: bytes) -> list[dict]:
    """Les lignes de Charlemagne, quel que soit le format qu'il a produit.

    Charlemagne exporte en **HTML** pour « Gestion de bases », en XLSX
    ailleurs, et le CDI en CSV. L'écran acceptait les trois ; le service ne
    lisait que le CSV, et répondait « l'en-tête lu commence par : <HTML> »
    — un message juste, sur un fichier parfaitement valide.

    Le format se reconnaît au contenu, pas à l'extension : un `.htm`
    renommé reste du HTML, et c'est la première chose qu'on fait avec un
    export qu'on range.
    """
    debut = contenu[:512].lstrip(b"\xef\xbb\xbf \t\r\n")[:16].lower()
    if debut.startswith(b"pk"):
        return _via_pandas(contenu, ".xlsx")
    if debut.startswith(b"<") or b"<html" in debut or b"<table" in debut:
        return _via_pandas(contenu, ".htm")
    return _via_csv(contenu)


def _via_csv(contenu: bytes) -> list[dict]:
    lignes = lignes_du_fichier(decoder(contenu))
    if not lignes:
        raise ConcordanceImpossible("Le fichier de Charlemagne est vide.")
    entete = champs(lignes[0])
    manquantes = [c for c in COLONNES_REQUISES if c not in entete]
    if manquantes:
        raise ConcordanceImpossible(
            "Ce fichier ne porte pas les colonnes attendues : il y manque "
            + " et ".join(f"« {c} »" for c in manquantes)
            + ". L'en-tête lu commence par : "
            + ", ".join(entete[:4] or ["(rien)"])
            + "."
        )
    i_badge, i_classe = entete.index("Num Badge"), entete.index("Code classe")
    i_nom = entete.index("Nom") if "Nom" in entete else None
    i_prenom = entete.index("Prénom") if "Prénom" in entete else None

    out = []
    for brute in lignes[1:]:
        if not brute.strip():
            continue
        cellules = champs(brute)
        if len(cellules) <= max(i_badge, i_classe):
            continue
        out.append({
            "badge": lire(cellules, i_badge),
            "nom": lire(cellules, i_nom),
            "prenom": lire(cellules, i_prenom),
            "classe": lire(cellules, i_classe),
        })
    return out


def _via_pandas(contenu: bytes, suffixe: str) -> list[dict]:
    """Le parser Charlemagne du programme, celui de l'ingestion.

    Il normalise les intitulés — « Identifiant Elève », « Num Badge »,
    « Code classe » — et sait déjà lire les tables HTML que Charlemagne
    appelle des `.htm`.
    """
    from pathlib import Path
    from tempfile import NamedTemporaryFile

    from backend.services.parser_charlemagne import lire_htm, lire_xlsx

    with NamedTemporaryFile(suffix=suffixe, delete=False) as tmp:
        tmp.write(contenu)
        chemin = Path(tmp.name)
    try:
        df = lire_htm(chemin) if suffixe == ".htm" else lire_xlsx(chemin)
    except Exception as e:
        raise ConcordanceImpossible(
            f"Fichier illisible ({suffixe}) : {type(e).__name__}: {e}"
        ) from None
    finally:
        try:
            chemin.unlink()
        except OSError:
            pass

    manquantes = [c for c in ("num_badge", "code_classe") if c not in df.columns]
    if manquantes:
        raise ConcordanceImpossible(
            "Ce fichier ne porte pas les colonnes attendues : il y manque "
            + " et ".join(
                {"num_badge": "« Num Badge »", "code_classe": "« Code classe »"}[c]
                for c in manquantes
            )
            + ". Colonnes lues : "
            + ", ".join(list(df.columns)[:6])
            + "."
        )

    def texte(v) -> str:
        import pandas as pd

        return "" if v is None or pd.isna(v) else str(v).strip()

    out = []
    for _, r in df.iterrows():
        badge = texte(r.get("num_badge"))
        if badge.endswith(".0"):
            # pandas rend les entiers en flottants dès qu'une case est vide.
            badge = badge[:-2]
        out.append({
            "badge": badge,
            "nom": texte(r.get("nom")),
            "prenom": texte(r.get("prenom")),
            "classe": texte(r.get("code_classe")),
        })
    return out


def _classer(
    ligne: LigneConcordance,
    ses_groupes: set[str],
    groupe_vers_classe: dict[str, str],
    rapport: RapportConcordance,
) -> None:
    """Ce qui, source par source, ne dit pas comme Charlemagne.

    Une source qu'on n'a pas interrogée ne diverge pas : elle se tait. Sans
    cette distinction, ne pas déposer d'export KoXo ferait passer toute
    l'école pour désynchronisée.
    """
    attendu = ligne.charlemagne

    if ligne.personne_id is None:
        ligne.genres.append("absent_referentiel")
    elif ligne.referentiel != attendu:
        ligne.genres.append("referentiel")

    if rapport.google_consulte and ligne.personne_id is not None:
        if ligne.google_ou is None:
            ligne.genres.append("sans_compte")
        elif ligne.google_classe is None:
            # Unité d'attente ou de sortie : ce n'est pas un désaccord sur
            # la classe, c'est un compte qui n'a pas encore été basculé.
            ligne.genres.append("hors_arbre_de_classe")
        elif ligne.google_classe != attendu:
            ligne.genres.append("google")

        groupes_de_classe = {
            g for g in ses_groupes if g in groupe_vers_classe
        }
        siens = {g for g in groupes_de_classe if groupe_vers_classe[g] == attendu}
        if groupes_de_classe - siens:
            ligne.genres.append("groupe")

    # KoXo a une base par établissement, et un export n'en couvre qu'une.
    # Un élève de l'autre site n'est pas absent de KoXo : il est hors du
    # champ de ce fichier, et le lui reprocher noyait tout le reste sous
    # seize cents écarts.
    if rapport.koxo_fourni and ligne.koxo_consulte:
        if ligne.koxo is None:
            ligne.genres.append("absent_koxo")
        elif ligne.koxo != attendu:
            ligne.genres.append("koxo")


# ---------------------------------------------------------------------------
# Les index
# ---------------------------------------------------------------------------


def _index_table(session: Session) -> tuple[dict[str, str], dict[str, str]]:
    """L'unité vers la classe, et le groupe vers la classe — à l'envers.

    Google ne porte pas de classe : il faut la relire depuis l'unité et le
    groupe, et c'est la table de correspondance qui tient les deux bouts.
    """
    classe_par_ou: dict[str, str] = {}
    groupe_vers_classe: dict[str, str] = {}
    for t in session.query(TableCorrespondance).all():
        code = (t.classe_code_court or "").strip()
        if not code:
            continue
        ou = (t.ou_definitive or "").strip().lower()
        if ou:
            classe_par_ou.setdefault(ou, code)
        groupe = (t.groupe_google or "").strip().lower()
        if groupe:
            groupe_vers_classe.setdefault(groupe, code)
    return classe_par_ou, groupe_vers_classe


def _index_google(
    comptes: list[dict] | None,
    membres_par_groupe: dict[str, list[str] | None] | None,
) -> tuple[dict[str, str], dict[str, set[str]]]:
    ou_par_adresse: dict[str, str] = {}
    for u in comptes or []:
        ou = u.get("ou") or ""
        for a in [(u.get("email") or "")] + list(u.get("alias") or []):
            a = (a or "").strip().lower()
            if a:
                ou_par_adresse.setdefault(a, ou)

    groupes: dict[str, set[str]] = {}
    for adresse_groupe, membres in (membres_par_groupe or {}).items():
        if membres is None:
            continue
        for m in membres:
            groupes.setdefault((m or "").strip().lower(), set()).add(
                adresse_groupe.strip().lower()
            )
    return ou_par_adresse, groupes


def _index_koxo(lignes_koxo: list | None) -> dict[str, str]:
    """Le badge KoXo vers son groupe secondaire.

    KoXo range l'élève par groupe secondaire, et le programme y écrit
    toujours le badge Charlemagne dans l'`ID unique` : c'est par lui que
    l'appariement se fait, jamais par le nom.
    """
    par_id: dict[str, str] = {}
    for l in lignes_koxo or []:
        ident = (getattr(l, "id_unique", "") or "").strip()
        if ident:
            par_id[ident] = (getattr(l, "groupe_secondaire", "") or "").strip()
    return par_id


def _sites_couverts_par_koxo(
    session: Session, lignes_koxo: list | None, par_badge: dict
) -> set[str]:
    """Les sites dont cet export KoXo parle, déduits de ses propres lignes.

    KoXo a **une base par établissement** : NDK et SU sont deux serveurs, et
    on ne peut en exporter qu'un à la fois. Sans cette restriction, déposer
    l'export de NDK faisait passer les six cent quatre-vingt-neuf élèves de
    SU pour absents de KoXo — un écart par élève, sur une base qui n'était
    même pas interrogée.

    Le site se lit sur les personnes que l'export contient, pas sur son nom
    de fichier : `Export_complet_NDK.CSV` peut être renommé, ses lignes non.
    """
    if lignes_koxo is None:
        return set()
    sites = {s.id: s.nom for s in session.query(Site).all()}
    trouves: dict[str, int] = {}
    for l in lignes_koxo:
        ident = (getattr(l, "id_unique", "") or "").strip()
        p = par_badge.get(ident)
        if p is not None and p.site_id in sites:
            nom = sites[p.site_id]
            trouves[nom] = trouves.get(nom, 0) + 1
    # Un site représenté par une poignée de lignes face à des centaines est
    # un accident — un professeur partagé, un compte de service. Le seuil se
    # prend donc **en proportion** du site dominant, pas en valeur absolue :
    # un export de trois lignes reste un export de son établissement.
    if not trouves:
        return set()
    plancher = max(1, max(trouves.values()) // 20)
    return {nom for nom, n in trouves.items() if n >= plancher}
