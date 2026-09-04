"""Créer des comptes Google pour un site qui n'a pas de KoXo.

## Le cas

Deux sites sur trois ont un serveur KoXo : il fabrique les mots de passe,
les imprime sur une fiche, et le programme n'a qu'à les recopier vers
Google. Le troisième — NDE — n'en a pas. Ses élèves n'ont qu'un compte
Google, et personne ne fabrique leur mot de passe.

La règle « le programme n'invente aucun mot de passe » vaut parce que KoXo
en est l'autorité. Là où il n'y a pas de KoXo, il n'y a pas d'autorité à
respecter, et refuser d'inventer reviendrait à refuser de créer les comptes.

## Ce que ce module garantit

**Un mot de passe généré ne doit jamais être perdu.** Il n'existe nulle
part ailleurs : le perdre oblige à réinitialiser le compte, élève par
élève. La génération et le dépôt au coffre sont donc **le même geste** —
on ne peut pas obtenir le fichier sans que les mots de passe soient rangés.

C'est pourquoi la fonction exige la clé du coffre. Sans coffre ouvert, elle
refuse plutôt que de produire un fichier dont les secrets s'évaporeraient à
la fermeture de la fenêtre.

## La forme

Celle de KoXo : `Aaaaaa99`. Mesurée sur 1665 mots de passe réels de
l'établissement, 1663 la suivent. Reprendre la même forme n'est pas de
l'imitation : les élèves des deux autres sites ont déjà celle-là, les
fiches se ressemblent, et les règles de complexité de l'annuaire sont déjà
satisfaites par elle.
"""
from __future__ import annotations

import csv as _csv
import io as _io
from dataclasses import dataclass, field

from sqlalchemy.orm import Session

# Les modèles et les services voisins sont importés dans les fonctions :
# le module est chargé avant que la base de test soit reconstruite, et un
# import de haut niveau fige des classes qui ne sont plus les bonnes.


class GenerationImpossible(Exception):
    """La génération est refusée, et le message dit pourquoi."""


@dataclass
class RapportGeneration:
    site_nom: str = ""
    nb_lignes: int = 0
    nb_generes: int = 0
    nb_deja_au_coffre: int = 0
    """Comptes dont le mot de passe était déjà rangé : on le reprend au lieu
    d'en fabriquer un nouveau, sinon relancer l'export changerait les mots
    de passe déjà distribués."""
    avertissements: list[str] = field(default_factory=list)
    nom_fichier_csv: str = ""
    nom_fichier_fiches: str = ""


def preparer_comptes(
    session: Session,
    cle: bytes,
    *,
    site_id: int,
    annee_cible_id: int,
    annee_source_id: int | None = None,
    categorie: str = "nouveaux",
    organisation: str | None = None,
) -> tuple[bytes, bytes, RapportGeneration]:
    """Fabrique les mots de passe, les range, et rend les deux fichiers.

    Args:
        cle: la clé du coffre. Obligatoire — un mot de passe généré qui
            n'est pas rangé est un mot de passe perdu.

    Returns:
        `(csv_google, etiquettes_html, rapport)`. Le premier s'importe dans
        la console d'administration ; le second s'imprime et se distribue,
        à la présentation des étiquettes que KoXo produit pour les deux
        autres sites — un élève de NDE reçoit la même chose que celui de
        NDK.

    Raises:
        GenerationImpossible: site inconnu, ou site qui a déjà un KoXo.
    """
    from backend.models import AnneeScolaire, Site
    from backend.services.exports_google import BOM_UTF8, generer_csv_google
    from backend.services.regles_metier import classe_lisible

    if not cle:
        raise GenerationImpossible(
            "Le coffre doit être ouvert : un mot de passe fabriqué et non "
            "rangé serait perdu à la fermeture de la fenêtre, et il faudrait "
            "réinitialiser chaque compte."
        )

    site = session.query(Site).filter_by(id=site_id).one_or_none()
    if site is None:
        raise GenerationImpossible(f"Site introuvable : {site_id}")

    contenu, rapport_base = generer_csv_google(
        session=session,
        site_id=site_id,
        type_personne="eleve",
        categorie=categorie,
        annee_cible_id=annee_cible_id,
        annee_source_id=annee_source_id,
    )

    rapport = RapportGeneration(
        site_nom=site.nom,
        nb_lignes=rapport_base.nb_lignes,
        nom_fichier_csv=f"Google_{site.nom}_eleves_avec_mdp.csv",
        nom_fichier_fiches=f"Etiquettes_{site.nom}_par_classe.html",
    )
    if not rapport_base.nb_lignes:
        # Rendre deux fichiers vides est pire que refuser : on les
        # enregistre, on les ouvre, et on cherche ce qui a raté. La cause
        # est presque toujours la même — l'année source réglée sur l'année
        # cible, auquel cas « nouveaux » ne désigne personne.
        raise GenerationImpossible(
            f"Aucun compte à fabriquer pour {site.nom} en catégorie "
            f"« {categorie} ». Vérifie l'année source : si elle vaut l'année "
            "cible, « nouveaux » ne peut désigner personne. En « tous », "
            "l'export reprend tout le site."
        )

    par_email = _personnes_par_email(session, site_id)
    classes = _classes(session, annee_cible_id)
    deja = _secrets_existants(session, cle, site.nom)

    texte = contenu[len(BOM_UTF8):].decode("utf-8") if contenu.startswith(BOM_UTF8) else contenu.decode("utf-8")
    lecteur = _csv.DictReader(_io.StringIO(texte))
    lignes = list(lecteur)
    colonnes = list(lecteur.fieldnames or (lignes[0] if lignes else {}))

    fiches: list[dict] = []
    for ligne in lignes:
        email = (ligne.get("Email Address [Required]") or "").strip().lower()
        personne = par_email.get(email)
        if personne is None:
            rapport.avertissements.append(
                f"{email} : aucune personne du référentiel ne porte cette "
                "adresse, mot de passe non généré."
            )
            continue

        # Relancer l'export ne doit pas changer un mot de passe déjà
        # distribué : on reprend celui du coffre s'il y en a un.
        mdp = deja.get(personne.id)
        if mdp:
            rapport.nb_deja_au_coffre += 1
        else:
            from backend.services.coffre import deposer, fabriquer_mot_de_passe

            mdp = fabriquer_mot_de_passe()
            deposer(
                session,
                cle,
                personne_id=personne.id,
                mot_de_passe=mdp,
                cible="google",
                site=site.nom,
                origine="genere",
            )
            rapport.nb_generes += 1

        ligne["Password [Required]"] = mdp
        classe = classes.get(personne.id) or ""
        fiches.append(
            {
                "classe": classe_lisible(classe),
                "nom": personne.nom or "",
                "prenom": personne.prenom or "",
                # KoXo affiche « groupe primaire / groupe secondaire »,
                # mais « Elèves / 3F » n'apprend rien de plus à l'élève que
                # « 3_F » : le groupe primaire est le même pour tous.
                "groupe": classe_lisible(classe),
                "login": personne.login or "",
                "mot_de_passe": mdp,
                # L'identifiant réseau ne suffit pas : c'est l'adresse que
                # l'élève saisit pour se connecter à Google, et elle ne se
                # devine pas à partir du login — `alezia.acquitter.le.velly@`
                # pour `aacquitter`.
                "adresse": personne.email or "",
            }
        )

    annee = session.query(AnneeScolaire).filter_by(id=annee_cible_id).one_or_none()
    return (
        _encoder(colonnes, lignes),
        fiches_html(
            fiches,
            # Le bandeau nomme l'établissement — « Collège Notre Dame
            # d'Esperance » — et non l'OGEC qui le gère : c'est un papier
            # remis à l'élève, qui reconnaît son collège, pas son
            # organisme gestionnaire. `organisation_etiquettes` reste un
            # remplacement explicite quand on en veut un autre.
            organisation=(
                organisation
                or site.nom_complet
                or site.organisation_etiquettes
                or site.nom
            ),
            annee=annee.libelle if annee else "",
            # NDE n'a pas de serveur : promettre un accès réseau qui
            # n'existe pas serait pire que de ne rien afficher.
            avec_reseau=bool(site.base_koxo),
        ),
        rapport,
    )


def _encoder(colonnes: list[str], lignes: list[dict]) -> bytes:
    from backend.services.exports_google import BOM_UTF8

    tampon = _io.StringIO()
    ecrivain = _csv.DictWriter(tampon, fieldnames=colonnes, quoting=_csv.QUOTE_MINIMAL)
    ecrivain.writeheader()
    for l in lignes:
        ecrivain.writerow(l)
    return BOM_UTF8 + tampon.getvalue().encode("utf-8", errors="replace")


def _personnes_par_email(session: Session, site_id: int) -> dict:
    from backend.models import Personne

    par_email: dict = {}
    for p in session.query(Personne).filter_by(site_id=site_id, type="eleve").all():
        for champ in (p.email, p.email_constate):
            if champ:
                par_email[champ.strip().lower()] = p
    return par_email


def _classes(session: Session, annee_id: int) -> dict[int, str | None]:
    from backend.models import Snapshot

    derniers: dict[int, str | None] = {}
    for s in (
        session.query(Snapshot)
        .filter_by(annee_scolaire_id=annee_id)
        .order_by(Snapshot.date_ingestion, Snapshot.id)
        .all()
    ):
        derniers[s.personne_id] = s.classe
    return derniers


def _secrets_existants(session: Session, cle: bytes, site_nom: str) -> dict[int, str]:
    """Les mots de passe déjà rangés pour ce site, par personne."""
    from backend.models import SecretConserve
    from backend.services.coffre import _dechiffrer

    trouves: dict[int, str] = {}
    for s in (
        session.query(SecretConserve)
        .filter_by(cible="google", site=site_nom, origine="genere")
        .all()
    ):
        trouves[s.personne_id] = _dechiffrer(cle, s)
    return trouves


# ---------------------------------------------------------------------------
# Les étiquettes, à la présentation de KoXo
# ---------------------------------------------------------------------------

# Cotes relevées dans un PDF d'étiquettes produit par KoXo, en points
# PostScript. Les reprendre telles quelles n'est pas du zèle : l'élève de
# NDE recevra la même étiquette que celui de NDK, et le professeur qui les
# distribue n'a pas à apprendre deux présentations.
CARTE_L, CARTE_H = 173.55, 125.34
BANDEAU_H = 18.72
CHAMP_L, CHAMP_H = 92.44, 18.72
MARGE_G, MARGE_H = 23.25, 29.76
COLONNES, RANGEES = 3, 6
# Les gouttières se déduisent des pas relevés entre étiquettes voisines :
# 187.2 pt d'une colonne à la suivante pour une carte de 173.55, et 132.2 pt
# d'une rangée à l'autre pour une carte de 125.34. Une seule étiquette ne
# les révélait pas — il a fallu une planche complète pour les voir.
GOUTTIERE_H = 187.2 - CARTE_L
GOUTTIERE_V = 132.2 - CARTE_H

BLEU = "#1e8ce0"
FOND = "#d9e8f7"


LOGO_GOOGLE = """<svg class="logo" viewBox="0 0 48 48" role="img" aria-label="Google">
<path fill="#4285F4" d="M45.12 24.5c0-1.56-.14-3.06-.4-4.5H24v8.51h11.84c-.51 2.75-2.06 5.08-4.39 6.64v5.52h7.11c4.16-3.83 6.56-9.47 6.56-16.17z"/>
<path fill="#34A853" d="M24 46c5.94 0 10.92-1.97 14.56-5.33l-7.11-5.52c-1.97 1.32-4.49 2.1-7.45 2.1-5.73 0-10.58-3.87-12.31-9.07H4.34v5.7C7.96 41.07 15.4 46 24 46z"/>
<path fill="#FBBC05" d="M11.69 28.18C11.25 26.86 11 25.45 11 24s.25-2.86.69-4.18v-5.7H4.34C2.85 17.09 2 20.45 2 24s.85 6.91 2.34 9.88l7.35-5.7z"/>
<path fill="#EA4335" d="M24 10.75c3.23 0 6.13 1.11 8.41 3.29l6.31-6.31C34.91 4.18 29.93 2 24 2 15.4 2 7.96 6.93 4.34 14.12l7.35 5.7c1.73-5.2 6.58-9.07 12.31-9.07z"/>
</svg>"""
LOGO_RESEAU = """<svg class="logo" viewBox="0 0 48 48" role="img" aria-label="Réseau">
<circle cx="24" cy="11" r="6" fill="#0078D4"/>
<circle cx="10" cy="36" r="6" fill="#50B0E8"/>
<circle cx="38" cy="36" r="6" fill="#50B0E8"/>
<path d="M24 17v7M24 24l-11 8M24 24l11 8" stroke="#0078D4" stroke-width="2.6"
 stroke-linecap="round" fill="none"/>
</svg>"""
"""Le compte du reseau, pour les sites qui en ont un.

L'etiquette ne portait que Google, et l'eleve de NDK ou de SU en a
pourtant deux usages : sa session Windows et sa boite. Un glyphe generique
plutot que la marque exacte de l'editeur : ce qu'il faut dire, c'est
« ces identifiants ouvrent aussi l'ordinateur ».

NDE n'a pas de serveur, et n'affiche donc pas ce logo — promettre un acces
qui n'existe pas serait pire que de ne rien dire.
"""

"""Le logo Google, dessine en SVG plutot que charge.

Le fichier doit rester autonome : une image distante ne s'imprimerait pas
sans reseau, et une image encodee alourdirait chaque etiquette. Il dit a
l'eleve de quel service ces identifiants ouvrent la porte — pour NDE,
c'est le seul compte qu'il possede."""


def _echapper(t: str) -> str:
    return (
        (t or "")
        .replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
    )


def fiches_html(
    etiquettes: list[dict],
    *,
    organisation: str,
    annee: str,
    avec_reseau: bool = False,
) -> bytes:
    """Les étiquettes de comptes, à imprimer — présentation de KoXo.

    KoXo imprime une étiquette par élève : bandeau bleu à l'en-tête, nom,
    groupe, puis quatre lignes libellées — identifiant, mot de passe,
    adresse et adresse du service. NDE n'a pas de KoXo et n'aurait donc
    rien à distribuer.

    ## Des lignes libellées, pas des cartouches

    Une première version encadrait l'identifiant et le mot de passe dans
    deux cartouches blancs, à l'ancienne. Les étiquettes de KoXo portent
    aujourd'hui `Identifiant : ncorvez` en clair, avec l'adresse et l'URL
    en dessous — et deux jeux d'étiquettes qui ne se ressemblent pas se
    trient mal quand on les distribue le même matin.

    Le format est du HTML plutôt qu'un PDF : aucune dépendance à ajouter,
    et l'impression depuis le navigateur donne le même résultat — avec la
    possibilité d'ajuster, ce qu'un PDF figé n'offre pas.

    ## Une classe par planche

    Les étiquettes se distribuent classe par classe : mélanger deux classes
    sur une même feuille obligerait à découper puis retrier. Chaque classe
    commence donc sur une nouvelle page, et en occupe autant qu'il faut.

    Args:
        etiquettes: dicts portant `nom`, `prenom`, `classe`, `groupe`,
            `login`, `mot_de_passe` et **`adresse`** — c'est cette dernière
            que la ligne « Email » affiche. L'oublier ne fait pas d'erreur :
            l'étiquette sort avec « Email : » suivi de rien.
        organisation: ce qu'affiche le bandeau — chez KoXo, le nom de
            l'organisation de l'annuaire.
    """
    # Le bandeau de KoXo porte « OGEC PAUL AURELIEN », dix-huit caractères,
    # qui tiennent tout juste à 11.91 pt. « OGEC NOTRE DAME D ESPERANCE » en
    # fait vingt-sept et débordait — tronqué, un nom d'organisation ne veut
    # plus rien dire. On réduit le corps à proportion plutôt que de couper.
    REPERE = 18
    taille_bandeau = 11.91
    if len(organisation) > REPERE:
        taille_bandeau = round(11.91 * REPERE / len(organisation), 2)

    par_classe: dict[str, list[dict]] = {}
    for e in etiquettes:
        par_classe.setdefault(e.get("classe") or "", []).append(e)

    logo_reseau = LOGO_RESEAU if avec_reseau else ""

    def carte(e: dict) -> str:
        return (
            f'''<div class="etiquette">
  <div class="bandeau">{_echapper(organisation)}</div>
  <p class="identite">{_echapper(e.get("prenom", ""))} {_echapper(e.get("nom", ""))}</p>
  <p class="groupe">{_echapper(e.get("groupe", ""))}</p>
  <span class="logos">{LOGO_GOOGLE}{logo_reseau}</span>
  <p class="ligne"><span class="etiq">Identifiant :</span><span class="val">{_echapper(e.get("login", ""))}</span></p>
  <p class="ligne"><span class="etiq">Mot de passe :</span><span class="val">{_echapper(e.get("mot_de_passe", ""))}</span></p>
  <p class="ligne petite"><span class="etiq">Email :</span><span class="val">{_echapper(e.get("adresse", ""))}</span></p>
  <p class="ligne petite"><span class="etiq">Url :</span><span class="val">google.fr</span></p>
  <p class="pied"><span>Appli Rentrée</span><span>Année {_echapper(annee)}</span></p>
</div>'''
        )

    planches = []
    for classe in sorted(par_classe):
        eleves = sorted(
            par_classe[classe],
            key=lambda e: (e.get("nom") or "", e.get("prenom") or ""),
        )
        planches.append(
            '<div class="planche">\n'
            + "\n".join(carte(e) for e in eleves)
            + "\n</div>"
        )

    page = f"""<!doctype html>
<html lang="fr">
<head>
<meta charset="utf-8">
<title>Étiquettes de comptes — {_echapper(annee)}</title>
<style>
  @page {{ size: A4; margin: {MARGE_H}pt {MARGE_G}pt; }}
  /* À l'impression, les navigateurs suppriment les fonds pour économiser
     l'encre. Sur une étiquette, le bandeau bleu et le fond bleu pâle sont
     l'essentiel de la présentation : sans eux, la planche sort en noir et
     blanc et ne ressemble plus à celles de KoXo. On les impose. */
  * {{
    box-sizing: border-box;
    -webkit-print-color-adjust: exact;
    print-color-adjust: exact;
  }}
  body {{
    margin: 0;
    font-family: "Segoe UI", Arial, sans-serif;
    color: #000;
    background: #fff;
  }}
  .planche {{
    display: grid;
    grid-template-columns: repeat({COLONNES}, {CARTE_L}pt);
    grid-auto-rows: {CARTE_H}pt;
    gap: {GOUTTIERE_V:.2f}pt {GOUTTIERE_H:.2f}pt;
  }}
  /* Une classe par planche, une planche par feuille — au moins. Mélanger
     deux classes obligerait à découper puis retrier. */
  .planche + .planche {{ break-before: page; }}
  .etiquette {{
    width: {CARTE_L}pt;
    height: {CARTE_H}pt;
    background: {FOND};
    -webkit-print-color-adjust: exact;
    print-color-adjust: exact;
    border: 0.28pt solid #000;
    padding: 0 2.84pt;
    position: relative;
    overflow: hidden;
    /* Une étiquette coupée en deux par un saut de page serait inutilisable. */
    break-inside: avoid;
  }}
  .bandeau {{
    height: {BANDEAU_H}pt;
    margin: 0 -2.84pt 0;
    background: {BLEU};
    -webkit-print-color-adjust: exact;
    print-color-adjust: exact;
    border-bottom: 0.28pt solid #000;
    color: #fff;
    font-size: {taille_bandeau}pt;
    line-height: {BANDEAU_H}pt;
    padding-left: 2.84pt;
    white-space: nowrap;
    overflow: hidden;
  }}
  .identite {{
    margin: 4.5pt 0 0;
    font-size: 11.91pt;
    line-height: 1.1;
    white-space: nowrap;
    overflow: hidden;
  }}
  .groupe {{
    margin: 2pt 0 0;
    font-size: 9.07pt;
    line-height: 1.1;
    /* KoXo condense légèrement cette ligne pour la faire tenir. */
    transform: scaleX(0.975);
    transform-origin: left;
    white-space: nowrap;
    overflow: hidden;
  }}
  /* Quatre lignes libellées, comme sur les étiquettes de KoXo :
     « Identifiant : ncorvez », puis le mot de passe, l'adresse et l'URL.
     Les deux premières portent l'essentiel et restent lisibles de loin ;
     les deux suivantes sont plus petites, parce qu'une adresse fait
     jusqu'à quarante-deux caractères — `baptiste.kerangueven@ndecleder.fr`
     — pour cent soixante-huit points de large. */
  .ligne {{
    margin: 3.6pt 0 0 2.83pt;
    font-family: "Segoe UI", Arial, sans-serif;
    font-size: 9.5pt;
    line-height: 1.15;
    white-space: nowrap;
    overflow: hidden;
  }}
  .ligne.petite {{
    margin-top: 2.6pt;
    font-size: 7pt;
    /* Avec son libellé, la plus longue adresse fait quarante-neuf
       caractères et dépassait la largeur de la carte. On la condense
       légèrement, comme KoXo le fait déjà pour la ligne du groupe —
       plutôt que de la tronquer ou de retirer le libellé. */
    transform: scaleX(0.92);
    transform-origin: left;
  }}
  .etiq {{
    /* Le libellé s'efface devant la valeur : c'est elle qu'on recopie. */
    color: #333;
  }}
  .val {{
    margin-left: 0.35em;
    font-weight: 600;
  }}
  /* Le logo va en bas à droite, à hauteur de la ligne « Url ».
     En haut, il obligeait à réserver quarante points à droite du nom, et
     « Warren ACQUITTER LE VELLY » s'y trouvait coupé au milieu. Ici il ne
     longe que la plus courte des quatre lignes, et le nom reprend toute la
     largeur de la carte. */
  .logos {{
    position: absolute;
    right: 6pt;
    bottom: 10pt;
    display: flex;
    align-items: center;
    gap: 3pt;
  }}
  .logo {{
    width: 22pt;
    height: 22pt;
  }}
  .pied {{
    position: absolute;
    left: 2.84pt;
    right: 2.84pt;
    bottom: 2.2pt;
    margin: 0;
    display: flex;
    justify-content: space-between;
    font-size: 5.1pt;
  }}
  @media print {{
    /* Le fond d'écran de la page ne doit pas être imprimé, lui. */
    body {{ background: #fff; padding: 0; }}
    .planche {{ box-shadow: none; margin: 0; padding: 0; }}
  }}
  @media screen {{
    body {{ background: #eef1f4; padding: 12pt; }}
    .planche {{
      background: #fff;
      padding: {MARGE_H}pt {MARGE_G}pt;
      width: max-content;
      margin-bottom: 12pt;
      box-shadow: 0 1px 4px rgba(0, 0, 0, 0.18);
    }}
  }}
</style>
</head>
<body>
{chr(10).join(planches)}
</body>
</html>
"""
    return page.encode("utf-8")
