"""Génération des exports CSV pour Google Workspace (bulk-import Admin).

Format officiel : 40 colonnes, séparateur virgule, UTF-8 avec BOM (attendu
par la console Google Admin). L'ordre exact des colonnes est respecté —
Google refuse le CSV sinon.

Catégories, comme pour KoXo :

- **Tous** : état complet visé (surtout utile pour amorcer ou re-synchroniser).
- **Nouveaux** : entrants (créations de comptes) — Password rempli plus tard
  par la boucle de retour KoXo (Lot 8b).
- **Anciens** : sortants — déplacement OU vers `/7. Sortis/...` (à venir
  quand on aura le paramétrage de l'OU de sortie).

## OU (Org Unit Path)

- Catégorie `tous` et `anciens` : `ou_definitive` de la TableCorrespondance
- Catégorie `nouveaux` : `ou_pre_rentree` (OU d'attente en début de rentrée)

## Ce qu'on ne remplit PAS

- **Password** : reste vide au Lot 10a — sera injecté au Lot 8b après
  récupération depuis KoXo (transport en mémoire uniquement, jamais persisté).
- **Manager Email**, **Recovery Email**, **Building ID**, etc. : hors périmètre
  de la première itération. Google acceptera un CSV avec ces cellules vides.

## Ce qu'on remplit

- **First Name**, **Last Name**, **Email Address** : identité de base.
- **Org Unit Path** : arborescence OU (via TableCorrespondance).
- **Employee ID** : `id_charlemagne` — clé stable pour futur rapprochement
  bidirectionnel Google ↔ nous.
- **Change Password at Next Sign-In** : `True` pour les nouveaux (force
  la personnalisation à la première connexion).
"""
from __future__ import annotations

import csv
import io
from dataclasses import dataclass
from typing import Literal

from sqlalchemy.orm import Session

from backend.models import Personne, Site, Snapshot, TableCorrespondance

# ---------------------------------------------------------------------------
# Format Google Admin bulk-import — ordre officiel, 40 colonnes
# ---------------------------------------------------------------------------

COLONNES_GOOGLE = [
    "First Name [Required]",
    "Last Name [Required]",
    "Email Address [Required]",
    "Password [Required]",
    "Password Hash Function [UPLOAD ONLY]",
    "Org Unit Path [Required]",
    "New Primary Email [UPLOAD ONLY]",
    "Status [READ ONLY]",
    "Last Sign In [READ ONLY]",
    "Recovery Email",
    "Home Secondary Email",
    "Work Secondary Email",
    "Recovery Phone [MUST BE IN THE E.164 FORMAT]",
    "Work Phone",
    "Home Phone",
    "Mobile Phone",
    "Work Address",
    "Home Address",
    "Employee ID",
    "Employee Type",
    "Employee Title",
    "Manager Email",
    "Department",
    "Cost Center",
    "Building ID",
    "Floor Name",
    "Floor Section",
    "Change Password at Next Sign-In",
    "New Status [UPLOAD ONLY]",
    "New Licenses [UPLOAD ONLY]",
    "Advanced Protection Program enrollment",
    "Gemini Enterprise",
    "2sv Enrolled [READ ONLY]",
    "2sv Enforced [READ ONLY]",
    "Email Usage [READ ONLY]",
    "Drive Usage [READ ONLY]",
    "Photos Usage [READ ONLY]",
    "Total Storage [READ ONLY]",
    "Licenses [READ ONLY]",
    "Storage Used [READ ONLY]",
]

# UTF-8 BOM — Google Admin exige le BOM pour reconnaître l'encodage
BOM_UTF8 = b"\xef\xbb\xbf"

Categorie = Literal["tous", "nouveaux", "anciens"]


@dataclass
class ContexteExport:
    site: Site
    type_personne: str
    categorie: Categorie
    annee_cible_id: int
    annee_source_id: int | None
    # Résolution OU par code classe
    ou_par_classe: dict[str, tuple[str, str]]  # {code_court: (ou_pre_rentree, ou_definitive)}


@dataclass
class RapportExportGoogle:
    site_nom: str
    type_personne: str
    categorie: str
    nb_lignes: int
    nom_fichier_suggere: str
    nb_sans_ou: int
    """Nombre de personnes exportées sans OU résolue (classe absente de
    la table de correspondance) — signalé pour attirer l'attention."""


# ---------------------------------------------------------------------------
# Point d'entrée
# ---------------------------------------------------------------------------


def generer_csv_google(
    session: Session,
    *,
    site_id: int,
    type_personne: str,
    categorie: Categorie,
    annee_cible_id: int,
    annee_source_id: int | None = None,
) -> tuple[bytes, RapportExportGoogle]:
    """Génère un CSV Google Admin bulk-import pour une catégorie donnée."""
    if type_personne not in ("eleve", "adulte"):
        raise ValueError(f"type_personne invalide : {type_personne!r}")
    if categorie not in ("tous", "nouveaux", "anciens"):
        raise ValueError(f"categorie invalide : {categorie!r}")
    if categorie in ("nouveaux", "anciens") and annee_source_id is None:
        raise ValueError(f"annee_source_id requis pour categorie={categorie!r}")

    site = session.query(Site).filter_by(id=site_id).one_or_none()
    if site is None:
        raise ValueError(f"Site introuvable : {site_id}")

    # Précharge le mapping classe → OU pour ce site
    ou_par_classe: dict[str, tuple[str, str]] = {}
    for tc in session.query(TableCorrespondance).filter_by(site_id=site.id).all():
        ou_par_classe[tc.classe_code_court] = (tc.ou_pre_rentree, tc.ou_definitive)

    ctx = ContexteExport(
        site=site,
        type_personne=type_personne,
        categorie=categorie,
        annee_cible_id=annee_cible_id,
        annee_source_id=annee_source_id,
        ou_par_classe=ou_par_classe,
    )

    if categorie == "tous":
        lignes = _lignes_tous(session, ctx)
    elif categorie == "nouveaux":
        lignes = _lignes_nouveaux(session, ctx)
    else:
        lignes = _lignes_anciens(session, ctx)

    contenu = _encoder_csv(lignes)
    nb_sans_ou = sum(1 for l in lignes if not l["Org Unit Path [Required]"])
    rapport = RapportExportGoogle(
        site_nom=site.nom,
        type_personne=type_personne,
        categorie=categorie,
        nb_lignes=len(lignes),
        nom_fichier_suggere=_nom_fichier(site.nom, type_personne, categorie),
        nb_sans_ou=nb_sans_ou,
    )
    return contenu, rapport


# ---------------------------------------------------------------------------
# Récupération des lignes selon la catégorie
# ---------------------------------------------------------------------------


def _lignes_tous(session: Session, ctx: ContexteExport) -> list[dict]:
    snapshots = _snapshots_annee_par_personne(session, ctx.annee_cible_id, ctx)
    personnes = _charger_personnes(session, set(snapshots))
    return [
        _formatter_ligne(personnes[pid], snapshots[pid], ctx, ou_pre_rentree=False)
        for pid in snapshots
    ]


def _lignes_nouveaux(session: Session, ctx: ContexteExport) -> list[dict]:
    ids_source = _ids_personnes_annee(session, ctx.annee_source_id, ctx)
    snapshots_cible = _snapshots_annee_par_personne(session, ctx.annee_cible_id, ctx)
    ids_nouveaux = set(snapshots_cible) - ids_source
    personnes = _charger_personnes(session, ids_nouveaux)
    return [
        _formatter_ligne(personnes[pid], snapshots_cible[pid], ctx, ou_pre_rentree=True)
        for pid in ids_nouveaux
        if pid in personnes
    ]


def _lignes_anciens(session: Session, ctx: ContexteExport) -> list[dict]:
    snapshots_source = _snapshots_annee_par_personne(session, ctx.annee_source_id, ctx)
    ids_cible = _ids_personnes_annee(session, ctx.annee_cible_id, ctx)
    ids_anciens = set(snapshots_source) - ids_cible
    personnes = _charger_personnes(session, ids_anciens)
    return [
        _formatter_ligne(personnes[pid], snapshots_source[pid], ctx, ou_pre_rentree=False)
        for pid in ids_anciens
        if pid in personnes
    ]


# ---------------------------------------------------------------------------
# Helpers de requête (identiques à ceux d'exports_koxo — factorisables plus tard)
# ---------------------------------------------------------------------------


def _ids_personnes_annee(session: Session, annee_id: int, ctx: ContexteExport) -> set[int]:
    q = (
        session.query(Snapshot.personne_id)
        .join(Personne, Snapshot.personne_id == Personne.id)
        .filter(
            Snapshot.annee_scolaire_id == annee_id,
            Personne.site_id == ctx.site.id,
            Personne.type == ctx.type_personne,
        )
    )
    return {row[0] for row in q.all()}


def _snapshots_annee_par_personne(
    session: Session, annee_id: int, ctx: ContexteExport
) -> dict[int, Snapshot]:
    q = (
        session.query(Snapshot)
        .join(Personne, Snapshot.personne_id == Personne.id)
        .filter(
            Snapshot.annee_scolaire_id == annee_id,
            Personne.site_id == ctx.site.id,
            Personne.type == ctx.type_personne,
        )
        .order_by(Snapshot.personne_id, Snapshot.date_ingestion.desc())
    )
    derniers: dict[int, Snapshot] = {}
    for s in q.all():
        if s.personne_id not in derniers:
            derniers[s.personne_id] = s
    return derniers


def _charger_personnes(session: Session, ids: set[int]) -> dict[int, Personne]:
    if not ids:
        return {}
    return {p.id: p for p in session.query(Personne).filter(Personne.id.in_(ids)).all()}


# ---------------------------------------------------------------------------
# Formatage d'une ligne Google
# ---------------------------------------------------------------------------


def _formatter_ligne(
    personne: Personne, snapshot: Snapshot, ctx: ContexteExport, *, ou_pre_rentree: bool
) -> dict:
    """Construit une ligne bulk-import Google. La plupart des cellules sont vides."""
    ligne = {col: "" for col in COLONNES_GOOGLE}

    ligne["First Name [Required]"] = personne.prenom or ""
    ligne["Last Name [Required]"] = personne.nom or ""
    ligne["Email Address [Required]"] = personne.email or ""

    # OU : dépend de la catégorie
    ou = _resoudre_ou(snapshot, ctx, ou_pre_rentree=ou_pre_rentree)
    ligne["Org Unit Path [Required]"] = ou

    ligne["Employee ID"] = str(personne.id_charlemagne)
    ligne["Employee Type"] = "Student" if ctx.type_personne == "eleve" else "Staff"

    if ou_pre_rentree:
        # Nouveaux comptes : force changement de MDP à la 1re connexion
        ligne["Change Password at Next Sign-In"] = "True"

    # Password reste vide au Lot 10a — sera injecté par la boucle de retour KoXo
    # (Lot 8b) puis regénéré avant envoi à Google, en mémoire uniquement.

    return ligne


def _resoudre_ou(snapshot: Snapshot, ctx: ContexteExport, *, ou_pre_rentree: bool) -> str:
    """Résout l'OU à partir de la classe du snapshot et du paramétrage TableCorrespondance.

    Retourne "" si la classe n'a pas de mapping — signalé dans le rapport
    via `nb_sans_ou`. L'utilisateur devra soit compléter la Table, soit
    déplacer la personne à la main.
    """
    if ctx.type_personne == "adulte":
        # Adultes : pas de classe, on utilise la racine du site
        return ctx.site.prefixe_racine_ou()

    classe = snapshot.classe or ""
    ous = ctx.ou_par_classe.get(classe)
    if ous is None:
        return ""
    return ous[0] if ou_pre_rentree else ous[1]


# ---------------------------------------------------------------------------
# Sortie
# ---------------------------------------------------------------------------


def _encoder_csv(lignes: list[dict]) -> bytes:
    buf = io.StringIO(newline="")
    writer = csv.DictWriter(buf, fieldnames=COLONNES_GOOGLE, quoting=csv.QUOTE_MINIMAL)
    writer.writeheader()
    for l in lignes:
        writer.writerow(l)
    # BOM UTF-8 : Google Admin l'attend pour détecter l'encodage
    return BOM_UTF8 + buf.getvalue().encode("utf-8", errors="replace")


def _nom_fichier(site_nom: str, type_personne: str, categorie: str) -> str:
    pop = "eleves" if type_personne == "eleve" else "adultes"
    return f"Google_{site_nom}_{pop}_{categorie}.csv"


# ---------------------------------------------------------------------------
# Lot 8b — Boucle de retour KoXo → Google
# ---------------------------------------------------------------------------


def _extraire_mdp_depuis_csv_koxo(contenu_csv: bytes) -> dict[str, str]:
    """Extrait le mapping {login: mot_de_passe} depuis un CSV KoXo enrichi.

    KoXo génère les mots de passe à la création et les fournit dans son
    export. On extrait ici en mémoire uniquement — cette structure n'est
    jamais persistée (§7.1 « le mot de passe n'est jamais persisté »).
    """
    import csv as _csv
    import io as _io

    from unidecode import unidecode as _unidecode

    # Décodage : KoXo peut être en cp1252 (défaut Windows) ou utf-8
    texte = None
    for encodage in ("cp1252", "utf-8"):
        try:
            texte = contenu_csv.decode(encodage)
            break
        except UnicodeDecodeError:
            continue
    if texte is None:
        raise ValueError("Impossible de décoder le CSV KoXo (ni cp1252, ni utf-8)")

    # Détection du séparateur : plus de virgules ou de point-virgules dans la 1re ligne ?
    premiere_ligne = texte.split("\n", 1)[0]
    sep = "," if premiere_ligne.count(",") >= premiere_ligne.count(";") else ";"

    reader = _csv.DictReader(_io.StringIO(texte), delimiter=sep)
    mdp_par_login: dict[str, str] = {}
    for row in reader:
        login = None
        mdp = None
        for key, val in row.items():
            if key is None:
                continue
            k = _unidecode(str(key).strip().lower())
            if k == "identifiant":
                login = (val or "").strip()
            elif k == "mot de passe":
                mdp = (val or "").strip()
        if login and mdp:
            mdp_par_login[login] = mdp
    return mdp_par_login


@dataclass
class RapportExportGoogleAvecMdp:
    site_nom: str
    type_personne: str
    categorie: str
    nb_lignes: int
    nb_lignes_avec_mdp: int
    """Nb lignes Google pour lesquelles un MDP KoXo correspondant a été trouvé."""
    nb_sans_ou: int
    nb_mdp_orphelins: int
    """Nb entrées KoXo sans correspondance dans Google (logins présents dans
    le CSV KoXo mais absents du CSV Google généré) — signalé pour info."""
    nom_fichier_suggere: str


def generer_csv_google_avec_mdp(
    session: Session,
    *,
    csv_koxo_bytes: bytes,
    site_id: int,
    type_personne: str,
    categorie: Categorie,
    annee_cible_id: int,
    annee_source_id: int | None = None,
) -> tuple[bytes, RapportExportGoogleAvecMdp]:
    """Génère un CSV Google enrichi des mots de passe issus d'un CSV KoXo.

    Le flux : KoXo a créé les nouveaux comptes → l'utilisateur re-exporte
    KoXo (avec MDP) → upload dans notre app → on fabrique le CSV Google
    correspondant avec `Password [Required]` rempli.

    Les MDP transitent **en mémoire uniquement** — jamais stockés en base,
    jamais écrits sur disque en dehors du buffer de réponse HTTP.
    """
    import csv as _csv
    import io as _io

    # 1. Extraire les MDP depuis le CSV KoXo (RAM uniquement)
    mdp_par_login = _extraire_mdp_depuis_csv_koxo(csv_koxo_bytes)

    # 2. Générer le CSV Google standard (sans MDP)
    contenu_google, rapport_base = generer_csv_google(
        session=session,
        site_id=site_id,
        type_personne=type_personne,
        categorie=categorie,
        annee_cible_id=annee_cible_id,
        annee_source_id=annee_source_id,
    )

    # 3. Ré-injecter les MDP par correspondance de login (partie avant @)
    contenu_str = contenu_google
    if contenu_str.startswith(BOM_UTF8):
        contenu_str = contenu_str[3:]
    texte_google = contenu_str.decode("utf-8")

    reader = _csv.DictReader(_io.StringIO(texte_google))
    fieldnames = reader.fieldnames or COLONNES_GOOGLE
    rows = list(reader)

    logins_google = set()
    nb_avec_mdp = 0
    for row in rows:
        email = row.get("Email Address [Required]", "") or ""
        login = email.split("@", 1)[0] if "@" in email else ""
        logins_google.add(login)
        mdp = mdp_par_login.get(login)
        if mdp:
            row["Password [Required]"] = mdp
            nb_avec_mdp += 1

    # 4. Réencoder avec BOM UTF-8
    buf = _io.StringIO(newline="")
    writer = _csv.DictWriter(buf, fieldnames=fieldnames, quoting=_csv.QUOTE_MINIMAL)
    writer.writeheader()
    for row in rows:
        writer.writerow(row)
    contenu_enrichi = BOM_UTF8 + buf.getvalue().encode("utf-8", errors="replace")

    # 5. Rapport enrichi
    orphelins = sum(1 for login in mdp_par_login if login not in logins_google)

    return (
        contenu_enrichi,
        RapportExportGoogleAvecMdp(
            site_nom=rapport_base.site_nom,
            type_personne=rapport_base.type_personne,
            categorie=rapport_base.categorie,
            nb_lignes=rapport_base.nb_lignes,
            nb_lignes_avec_mdp=nb_avec_mdp,
            nb_sans_ou=rapport_base.nb_sans_ou,
            nb_mdp_orphelins=orphelins,
            nom_fichier_suggere=rapport_base.nom_fichier_suggere.replace(
                ".csv", "_avec_mdp.csv"
            ),
        ),
    )
