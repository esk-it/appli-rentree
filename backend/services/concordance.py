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

    lignes = lignes_du_fichier(decoder(contenu_charlemagne))
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

    rapport = RapportConcordance(
        annee_libelle=annee.libelle,
        google_consulte=comptes_google is not None,
        koxo_fourni=lignes_koxo is not None,
    )

    for brute in lignes[1:]:
        if not brute.strip():
            continue
        cellules = champs(brute)
        if len(cellules) <= max(i_badge, i_classe):
            continue
        classe_ch = lire(cellules, i_classe)
        if not classe_ch:
            # Sans classe chez Charlemagne, l'élève n'est pas inscrit cette
            # année : c'est un sortant, et il se traite ailleurs.
            continue
        rapport.nb_lignes_lues += 1

        badge = lire(cellules, i_badge)
        p = par_badge.get(badge)
        adresse = (p.email or "").strip().lower() if p is not None else ""

        ligne = LigneConcordance(
            personne_id=p.id if p is not None else None,
            badge=badge,
            nom=lire(cellules, i_nom) or (p.nom if p else ""),
            prenom=lire(cellules, i_prenom) or (p.prenom if p else ""),
            site=sites.get(p.site_id) if p is not None else None,
            charlemagne=classe_ch,
            referentiel=(p.classe or None) if p is not None else None,
            google_ou=ou_par_adresse.get(adresse),
            google_classe=classe_par_ou.get((ou_par_adresse.get(adresse) or "").lower()),
            koxo=koxo_par_id.get(badge),
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

    if rapport.koxo_fourni:
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
