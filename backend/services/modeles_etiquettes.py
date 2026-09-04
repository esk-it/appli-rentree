"""Les présentations d'étiquette, au choix de celui qui imprime.

## Pourquoi plusieurs

Une étiquette n'a pas le même usage selon la classe. En sixième, la
difficulté est de recopier le mot de passe sans se tromper ; en terminale,
c'est de retrouver son adresse. Distribuer une pile de trente demande de
lire la classe d'un coup d'œil ; en coller une dans un carnet demande un
talon détachable.

Imposer une présentation revenait à trancher à la place de l'utilisateur.
Il les choisit donc dans une liste, et voit ce qu'il choisit.

## Ce qui ne change jamais

**La géométrie.** Trois colonnes, six rangées, cartes de 173,55 × 125,34
points : c'est le gabarit des planches de KoXo, et les feuilles pré-
découpées de l'établissement sont à ce format. Un modèle qui s'en écarterait
imprimerait de travers.

**Le contenu.** Nom, classe, identifiant, mot de passe, adresse. Un modèle
qui tairait l'un des cinq ferait revenir l'élève au bureau.

## Le logo et la couleur

Le logo se lit dans `backend/assets/logos/<site>.png` et s'encode **une fois
par document** : une planche de six cent quatre-vingt-dix élèves ne grossit
que d'une quarantaine de kilo-octets. Le fichier reste autonome — il
s'imprime sans réseau, des mois plus tard.

La couleur est celle du losange du site dans le logo de l'ensemble. Un site
inconnu retombe sur un gris neutre plutôt que de refuser de s'imprimer.
"""
from __future__ import annotations

import base64
import sys
from dataclasses import dataclass
from functools import lru_cache
from html import escape
from pathlib import Path
from typing import Callable

# A4, en points typographiques.
A4_L, A4_H = 595.28, 841.89
MARGE_G, MARGE_H = 24.0, 24.0
GOUTTIERE_H, GOUTTIERE_V = 13.65, 8.0
COLONNES = 3

PAR_PAGE = {15: 5, 18: 6}
"""Combien d'étiquettes par feuille, et le nombre de rangées que cela fait.

Dix-huit tombe sur les cotes des planches KoXo (173,55 × 125,34 pt) ;
quinze donne des cartes plus hautes, plus faciles à découper.
"""
PAR_PAGE_DEFAUT = 18


def geometrie(par_page: int = PAR_PAGE_DEFAUT) -> tuple[int, float, float]:
    """Rangées, largeur et hauteur de carte, pour que la page **tombe juste**.

    Les cotes étaient reprises telles quelles d'un PDF de KoXo, sans
    vérifier qu'elles entraient dans une A4 : six rangées demandaient
    786,34 points pour 782,37 disponibles, et la sixième partait à la page
    suivante. On calcule donc la carte à partir de la page, au lieu de
    l'inverse.
    """
    rangees = PAR_PAGE.get(par_page, PAR_PAGE[PAR_PAGE_DEFAUT])
    largeur = (A4_L - 2 * MARGE_G - (COLONNES - 1) * GOUTTIERE_H) / COLONNES
    hauteur = (A4_H - 2 * MARGE_H - (rangees - 1) * GOUTTIERE_V) / rangees
    return rangees, largeur, hauteur


CARTE_L, CARTE_H = geometrie()[1:]

def _dossier_logos() -> Path:
    """Où trouver les logos, en développement comme une fois empaqueté.

    PyInstaller déballe les données dans un dossier temporaire qu'il
    désigne par `sys._MEIPASS` : le chemin relatif au source, lui, n'existe
    plus. Sans ce détour, les étiquettes sortaient sans logo une fois
    l'application installée — et jamais pendant les essais.
    """
    base = getattr(sys, "_MEIPASS", None)
    if base:
        embarque = Path(base) / "backend" / "assets" / "logos"
        if embarque.is_dir():
            return embarque
    return Path(__file__).resolve().parent.parent / "assets" / "logos"


DOSSIER_LOGOS = _dossier_logos()

COULEURS = {"NDK": "#009ABF", "SU": "#B42274", "NDE": "#762057"}
"""La couleur du losange de chaque site dans le logo de l'ensemble."""
COULEUR_PAR_DEFAUT = "#57534e"

LOGO_GOOGLE = (
    '<svg viewBox="0 0 48 48" aria-label="Google"><path fill="#4285F4" d="M45.12 '
    '24.5c0-1.56-.14-3.06-.4-4.5H24v8.51h11.84c-.51 2.75-2.06 5.08-4.39 '
    '6.64v5.52h7.11c4.16-3.83 6.56-9.47 6.56-16.17z"/><path fill="#34A853" '
    'd="M24 46c5.94 0 10.92-1.97 14.56-5.33l-7.11-5.52c-1.97 1.32-4.49 2.1-7.45 '
    '2.1-5.73 0-10.58-3.87-12.31-9.07H4.34v5.7C7.96 41.07 15.4 46 24 '
    '46z"/><path fill="#FBBC05" d="M11.69 28.18C11.25 26.86 11 25.45 11 '
    '24s.25-2.86.69-4.18v-5.7H4.34C2.85 17.09 2 20.45 2 24s.85 6.91 2.34 '
    '9.88l7.35-5.7z"/><path fill="#EA4335" d="M24 10.75c3.23 0 6.13 1.11 8.41 '
    '3.29l6.31-6.31C34.91 4.18 29.93 2 24 2 15.4 2 7.96 6.93 4.34 14.12l7.35 '
    '5.7c1.73-5.2 6.58-9.07 12.31-9.07z"/></svg>'
)
LOGO_RESEAU = (
    '<svg viewBox="0 0 48 48" aria-label="Réseau"><circle cx="24" cy="11" r="6" '
    'fill="#0078D4"/><circle cx="10" cy="36" r="6" fill="#50B0E8"/><circle '
    'cx="38" cy="36" r="6" fill="#50B0E8"/><path d="M24 17v7M24 24l-11 8M24 '
    '24l11 8" stroke="#0078D4" stroke-width="2.6" stroke-linecap="round" '
    'fill="none"/></svg>'
)


@lru_cache(maxsize=8)
def logo_du_site(nom: str) -> str:
    """Le logo du site en `data:` URI, ou une chaîne vide s'il n'y en a pas.

    Encodé une fois et gardé en mémoire : la même planche le réclame une
    fois par élève, et le relire six cent quatre-vingt-dix fois coûterait
    plus cher que tout le reste de la génération.
    """
    chemin = DOSSIER_LOGOS / f"{nom}.png"
    if not chemin.is_file():
        return ""
    octets = chemin.read_bytes()
    return "data:image/png;base64," + base64.b64encode(octets).decode("ascii")


def couleur_du_site(nom: str) -> str:
    return COULEURS.get(nom, COULEUR_PAR_DEFAUT)


@dataclass(frozen=True)
class Modele:
    id: str
    libelle: str
    description: str
    css: str
    carte: Callable[[dict, str, bool], str]


def _e(v) -> str:
    """Échappe le texte, sans toucher aux apostrophes.

    `escape` les remplace par `&#x27;` — utile dans un attribut, mais ici
    tout passe dans du texte, et « Notre-Dame d&#x27;Espérance » se serait
    imprimé tel quel sur les étiquettes de NDE.
    """
    return escape(str(v or ""), quote=False)


def _services(avec_reseau: bool) -> str:
    """Les logos des services que ces identifiants ouvrent.

    Dans le bandeau plutôt qu'en bas de carte : posés en bas à droite, la
    seconde ligne d'une adresse longue leur passait dessous.
    """
    return (
        '<span class="srv">'
        + LOGO_GOOGLE
        + (LOGO_RESEAU if avec_reseau else "")
        + "</span>"
    )


def taille_classe(code: str) -> str:
    """La classe écrite en gros doit tenir dans sa colonne.

    Le collège code en deux caractères (`3_1`), le lycée jusqu'à sept
    (`T_STMG1`). À taille fixe, le second débordait et sortait tronqué en
    « STMG ». On donne donc au gabarit de quoi l'ajuster.
    """
    n = len(code or "")
    if n <= 3:
        return "c-court"
    return "c-moyen" if n <= 5 else "c-long"


def _bandeau(e: dict, avec_reseau: bool) -> str:
    return (
        '<div class="bd"><span class="lg"></span><span class="bt">'
        f'<span class="etab">{_e(e.get("organisation"))}</span>'
        f'<span class="cls">{_e(e.get("groupe"))}</span></span>'
        + _services(avec_reseau)
        + "</div>"
    )


def _identifiants(e: dict) -> str:
    """Les trois valeurs, à la même taille — l'adresse comprise.

    Mesuré sur 1758 adresses réelles : médiane 27 caractères, maximum 45.
    Une taille unique qui logerait les 45 sur une ligne rendrait l'adresse
    deux fois plus petite que le mot de passe. Elle garde donc la taille des
    autres et passe à la ligne, la place des deux lignes étant réservée
    pour que la planche reste alignée.
    """
    return (
        f'<div class="ch"><span class="k">Identifiant</span>'
        f'<b>{_e(e.get("login"))}</b></div>'
        f'<div class="ch"><span class="k">Mot de passe</span>'
        f'<b>{_e(e.get("mot_de_passe"))}</b></div>'
        f'<div class="ch adr"><span class="k">Email</span>'
        f'<b>{_e(e.get("adresse"))}</b></div>'
    )


def _corps(e: dict) -> str:
    return (
        f'<div class="cp"><p class="nom">{_e(e.get("prenom"))} '
        f'{_e(e.get("nom"))}</p>{_identifiants(e)}</div>'
    )


# ---------------------------------------------------------------------------
# Le socle commun — géométrie, impression, éléments partagés
# ---------------------------------------------------------------------------

def css_socle(par_page: int = PAR_PAGE_DEFAUT) -> str:
    rangees, carte_l, carte_h = geometrie(par_page)
    return f"""
  @page {{ size: A4; margin: {MARGE_H}pt {MARGE_G}pt; }}
  /* À l'impression, les navigateurs suppriment les fonds pour économiser
     l'encre. Ici le bandeau coloré et le filigrane sont l'essentiel de la
     présentation : sans eux la planche sort blanche. On les impose. */
  * {{ box-sizing: border-box; -webkit-print-color-adjust: exact;
       print-color-adjust: exact; }}
  body {{ margin: 0; background: #fff; color: #1c1917;
          font-family: "Segoe UI", Arial, sans-serif; }}
  .planche {{ display: grid;
    grid-template-columns: repeat({COLONNES}, {carte_l:.2f}pt);
    grid-auto-rows: {carte_h:.2f}pt;
    gap: {GOUTTIERE_V:.2f}pt {GOUTTIERE_H:.2f}pt; }}
  /* Une classe par planche : mélanger deux classes obligerait à découper
     puis retrier. */
  .planche + .planche {{ break-before: page; }}
  .et {{ width: {carte_l:.2f}pt; height: {carte_h:.2f}pt; position: relative;
    overflow: hidden; background: #fff; border: .4pt solid #d6d3d1;
    border-radius: 6pt; break-inside: avoid; }}
  .lg {{ background-image: var(--logo); background-repeat: no-repeat;
    background-position: center; background-size: contain; display: block; }}
  .srv {{ margin-left: auto; display: flex; gap: 2pt; background: #fff;
    border-radius: 10pt; padding: 1pt 2.5pt; flex: 0 0 auto; }}
  .srv svg {{ width: 9pt; height: 9pt; }}
  b {{ font-family: Consolas, "Courier New", monospace; }}
  .k {{ color: #78716c; font-size: 5.6pt; text-transform: uppercase;
    letter-spacing: .04em; display: block; line-height: 1.3; }}
  .ch {{ margin-bottom: 1.4pt; }}
  .ch b {{ font-size: 8.2pt; line-height: 1.25; display: block; }}
  .adr b {{ word-break: break-all; min-height: 18pt; }}
  .cp {{ position: relative; z-index: 1; padding: 4pt 8pt; }}
  .nom {{ font-size: 9pt; font-weight: 650; margin: 0 0 3pt;
    line-height: 1.12; max-height: 20pt; overflow: hidden; }}
  .bd {{ background: var(--c); color: #fff; padding: 3.5pt 7pt;
    border-radius: 5.6pt 5.6pt 0 0; display: flex; align-items: center;
    gap: 5pt; position: relative; z-index: 2; }}
  .bd .lg {{ width: 20pt; height: 18.5pt; flex: 0 0 20pt; background-color: #fff;
    border-radius: 3.5pt; padding: .7pt; }}
  .bt {{ min-width: 0; }}
  .etab {{ font-size: 5.3pt; letter-spacing: .03em; text-transform: uppercase;
    line-height: 1.2; max-height: 13pt; overflow: hidden; display: block; }}
  .cls {{ font-size: 8.6pt; font-weight: 750; line-height: 1.15; display: block; }}
  .fg {{ position: absolute; background-image: var(--logo);
    background-repeat: no-repeat; background-size: contain;
    background-position: center; z-index: 0; }}
"""


# ---------------------------------------------------------------------------
# Les modèles
# ---------------------------------------------------------------------------

_MODELES: list[Modele] = [
    Modele(
        id="filigrane",
        libelle="Bandeau et filigrane",
        description=(
            "Le bandeau coloré porte le logo et la classe ; le logo se répète "
            "en filigrane pâle derrière les identifiants. Le plus complet."
        ),
        css="""
  .m-filigrane .fg { left: 0; right: 0; top: 26pt; bottom: 0; opacity: .05;
    background-size: 100pt; }
""",
        carte=lambda e, cls, r: (
            f'{_bandeau(e, r)}<span class="fg"></span>{_corps(e)}'
        ),
    ),
    Modele(
        id="bandeau",
        libelle="Bandeau seul",
        description=(
            "Le même bandeau, sans filigrane. Le logo n'apparaît qu'une fois : "
            "la carte respire, et l'impression consomme moins."
        ),
        css="",
        carte=lambda e, cls, r: f"{_bandeau(e, r)}{_corps(e)}",
    ),
    Modele(
        id="colonne",
        libelle="Colonne latérale",
        description=(
            "Logo en haut d'une colonne colorée, classe en gros en bas. La "
            "classe se repère sans lire l'étiquette quand on distribue une pile."
        ),
        css="""
  .m-colonne .et { display: flex; }
  .m-colonne .col { width: 46pt; flex: 0 0 46pt; background: var(--c);
    border-radius: 5.6pt 0 0 5.6pt; padding: 6pt 4pt; display: flex;
    flex-direction: column; align-items: center; justify-content: space-between; }
  .m-colonne .col .lg { width: 33pt; height: 30pt; background-color: #fff;
    border-radius: 4pt; padding: 1.4pt; }
  .m-colonne .col .cls { color: #fff; text-align: center; line-height: 1.05;
    word-break: break-all; }
  .m-colonne .c-court { font-size: 14pt; }
  .m-colonne .c-moyen { font-size: 10.5pt; }
  .m-colonne .c-long  { font-size: 8pt; }
  .m-colonne .cp { flex: 1; min-width: 0; padding: 5pt 7pt; }
  .m-colonne .etab { color: #78716c; font-size: 5pt; margin-bottom: 1pt; }
  .m-colonne .srv { position: absolute; right: 5pt; bottom: 4pt; }
""",
        carte=lambda e, cls, r: (
            f'<div class="col"><span class="lg"></span>'
            f'<span class="cls {taille_classe(e.get("groupe"))}">'
            f'{_e(e.get("groupe"))}</span></div>'
            f'<div class="cp"><span class="etab">{_e(e.get("organisation"))}</span>'
            f'<p class="nom">{_e(e.get("prenom"))} {_e(e.get("nom"))}</p>'
            f"{_identifiants(e)}</div>{_services(r)}"
        ),
    ),
    Modele(
        id="mdp",
        libelle="Mot de passe en vedette",
        description=(
            "Le mot de passe isolé en gros dans un bloc coloré. Pour les "
            "petites classes, où la saisie est la première difficulté."
        ),
        css="""
  /* Le bloc du mot de passe mange la hauteur : avec un nom sur deux
     lignes et une adresse sur deux, l'étiquette débordait et l'adresse
     sortait coupée. On resserre plutôt que de rogner l'un des deux. */
  .m-mdp .geant { background: var(--c); color: #fff; text-align: center;
    padding: 2.5pt 3pt; margin: 2pt 8pt 0; border-radius: 4.5pt; }
  .m-mdp .geant .k { color: #fff; opacity: .85; line-height: 1.1; }
  .m-mdp .geant b { font-size: 12.5pt; letter-spacing: .04em; }
  .m-mdp .reste { padding: 2pt 8pt 0; }
  .m-mdp .nom { max-height: 11pt; margin-bottom: 0; }
  .m-mdp .cp { padding-top: 3pt; }
""",
        carte=lambda e, cls, r: (
            f'{_bandeau(e, r)}'
            f'<div class="cp" style="padding-bottom:0">'
            f'<p class="nom">{_e(e.get("prenom"))} {_e(e.get("nom"))}</p></div>'
            f'<div class="geant"><span class="k">Mot de passe</span>'
            f'<b>{_e(e.get("mot_de_passe"))}</b></div>'
            f'<div class="reste">'
            f'<div class="ch"><span class="k">Identifiant</span>'
            f'<b>{_e(e.get("login"))}</b></div>'
            f'<div class="ch adr"><span class="k">Email</span>'
            f'<b>{_e(e.get("adresse"))}</b></div></div>'
        ),
    ),
    Modele(
        id="epuree",
        libelle="Épurée",
        description=(
            "Pas de bandeau : un filet de couleur à gauche, le logo discret "
            "en haut. La plus sobre, et la seule lisible photocopiée en noir "
            "et blanc."
        ),
        css="""
  .m-epuree .et { border-left: 4.5pt solid var(--c); }
  .m-epuree .haut { display: flex; align-items: flex-start; gap: 5pt;
    padding: 5pt 7pt 0; }
  .m-epuree .haut .lg { width: 24pt; height: 22pt; flex: 0 0 24pt; }
  .m-epuree .etab { color: #78716c; font-size: 5pt; }
  .m-epuree .cls { color: var(--c); font-size: 8pt; }
  .m-epuree .cp { padding-top: 2pt; }
  .m-epuree .srv { position: absolute; right: 5pt; top: 5pt; padding: 0;
    background: none; }
""",
        carte=lambda e, cls, r: (
            f'<div class="haut"><span class="lg"></span><span class="bt">'
            f'<span class="etab">{_e(e.get("organisation"))}</span>'
            f'<span class="cls">{_e(e.get("groupe"))}</span></span>'
            f"{_services(r)}</div>{_corps(e)}"
        ),
    ),
    Modele(
        id="talon",
        libelle="Talon détachable",
        description=(
            "L'identité en haut, les identifiants sous un pointillé. L'élève "
            "détache le talon et le colle dans son carnet de liaison."
        ),
        css="""
  .m-talon .tete { display: flex; align-items: flex-start; gap: 5pt;
    padding: 4pt 7pt 3pt; }
  .m-talon .tete .lg { width: 22pt; height: 20pt; flex: 0 0 22pt; }
  .m-talon .etab { color: #78716c; font-size: 5pt; }
  /* « Joséphine URIEN MOREAU DE LIZOREUX » prend trois lignes : à
     vingt-deux points, le pointillé lui coupait la dernière. */
  .m-talon .nom { font-size: 8pt; margin: .5pt 0 0; max-height: 29pt; }
  .m-talon .puce { margin-left: auto; background: var(--c); color: #fff;
    border-radius: 10pt; padding: .6pt 5pt; font-size: 7.4pt; font-weight: 700;
    flex: 0 0 auto; }
  /* Le pointillé dit où couper : plein cadre, sinon on hésite. */
  .m-talon .coupe { border-top: 1pt dashed #a8a29e; margin: 0 6pt; }
  .m-talon .cp { padding: 4pt 7pt 0; }
  .m-talon .srv { position: absolute; right: 5pt; bottom: 4pt; }
""",
        carte=lambda e, cls, r: (
            f'<div class="tete"><span class="lg"></span><span class="bt">'
            f'<span class="etab">{_e(e.get("organisation"))}</span>'
            f'<p class="nom">{_e(e.get("prenom"))} {_e(e.get("nom"))}</p></span>'
            f'<span class="puce">{_e(e.get("groupe"))}</span></div>'
            f'<div class="coupe"></div>'
            f'<div class="cp">{_identifiants(e)}</div>{_services(r)}'
        ),
    ),
    Modele(
        id="centree",
        libelle="Carte centrée",
        description=(
            "Logo en haut, tout centré, beaucoup de blanc. La plus soignée à "
            "regarder ; c'est aussi la moins dense."
        ),
        css="""
  .m-centree .et { text-align: center; padding: 4pt 7pt; }
  .m-centree .lg { width: 22pt; height: 20pt; margin: 0 auto; }
  .m-centree .etab { color: #78716c; font-size: 5pt; margin-top: 1pt;
    display: block; }
  /* Le centrage coûte de la hauteur : sans ce resserrement, un nom long
     et une adresse sur deux lignes débordaient sous le bord. */
  .m-centree .nom { font-size: 8.2pt; margin: .5pt 0 0; max-height: 19pt; }
  .m-centree .cls { color: var(--c); font-size: 7.4pt; display: block;
    margin-bottom: 1.5pt; }
  .m-centree .cp { padding: 0; }
  .m-centree .ch { margin-bottom: 1pt; }
  .m-centree .ch b { font-size: 7.8pt; }
  .m-centree .adr b { min-height: 15pt; }
  .m-centree .k { font-size: 5.2pt; line-height: 1.15; }
  .m-centree .srv { position: absolute; right: 5pt; bottom: 4pt; }
""",
        carte=lambda e, cls, r: (
            f'<span class="lg"></span>'
            f'<span class="etab">{_e(e.get("organisation"))}</span>'
            f'<p class="nom">{_e(e.get("prenom"))} {_e(e.get("nom"))}</p>'
            f'<span class="cls">{_e(e.get("groupe"))}</span>'
            f'<div class="cp">{_identifiants(e)}</div>{_services(r)}'
        ),
    ),
]

MODELES: dict[str, Modele] = {m.id: m for m in _MODELES}
MODELE_PAR_DEFAUT = "filigrane"


def catalogue() -> list[dict]:
    """Ce que l'écran affiche dans sa liste de choix."""
    return [
        {"id": m.id, "libelle": m.libelle, "description": m.description}
        for m in _MODELES
    ]


def page_etiquettes(
    etiquettes: list[dict],
    *,
    annee: str,
    site_nom: str = "",
    modele: str = MODELE_PAR_DEFAUT,
    avec_reseau: bool = False,
    par_page: int = PAR_PAGE_DEFAUT,
) -> bytes:
    """La planche complète, une classe par page.

    Args:
        etiquettes: dicts portant `nom`, `prenom`, `classe`, `groupe`,
            `login`, `mot_de_passe`, `adresse` et `organisation`.
        site_nom: sert à retrouver le logo et la couleur du site.
        modele: un identifiant de `MODELES`. Inconnu, on prend celui par
            défaut plutôt que de refuser d'imprimer.
        avec_reseau: faux là où il n'y a pas de serveur — promettre un accès
            qui n'existe pas serait pire que se taire.
        par_page: 15 ou 18. La carte se calcule à partir de la page, pour
            que la dernière rangée n'en déborde pas.
    """
    m = MODELES.get(modele) or MODELES[MODELE_PAR_DEFAUT]
    logo = logo_du_site(site_nom)
    couleur = couleur_du_site(site_nom)

    par_classe: dict[str, list[dict]] = {}
    for e in etiquettes:
        par_classe.setdefault(e.get("classe") or "", []).append(e)

    planches = []
    for classe in sorted(par_classe):
        gens = sorted(
            par_classe[classe],
            key=lambda x: ((x.get("nom") or ""), (x.get("prenom") or "")),
        )
        cartes = "\n".join(
            f'<div class="et">{m.carte(e, classe, avec_reseau)}</div>' for e in gens
        )
        planches.append(f'<div class="planche">\n{cartes}\n</div>')

    # Les variables vont dans la feuille de style, pas dans un attribut
    # `style` : le `data:` URI du logo contient des guillemets qui
    # refermaient l'attribut, et `--logo` restait vide. Les étiquettes
    # sortaient sans logo, sans qu'aucune erreur ne le signale.
    racine = (
        f"  :root {{ --c: {couleur};"
        + (f" --logo: url({logo});" if logo else " --logo: none;")
        + " }\n"
    )
    return f"""<!doctype html>
<html lang="fr">
<head>
<meta charset="utf-8">
<title>Étiquettes de comptes — {_e(annee)}</title>
<style>
{racine}{css_socle(par_page)}{m.css}</style>
</head>
<body class="m-{m.id}">
{chr(10).join(planches)}
</body>
</html>
""".encode("utf-8")
