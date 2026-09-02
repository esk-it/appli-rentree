# -*- coding: utf-8 -*-
"""Fabrique la page qui cale les photos de la séance sur les listes de classes.

## Pourquoi ce n'est pas dans le programme

Le programme gère un flux qui se répète à l'identique chaque année :
Charlemagne entre, KoXo, Google, PMB et JPM sortent. La séance photo, non.
Elle dépend d'un appareil, d'un ordre de passage, d'un photographe, et de
ce qui a raté ce jour-là. En 2026 : des doublons supprimés qui ont troué la
numérotation, et une élève reprise en fin de séance dont la photo porte le
dernier numéro de sa classe alors qu'elle est sixième sur la liste.

Rien de tout cela ne se modélise à l'avance. Un module du programme
figerait des règles qui changeront ; ce script, lui, se relit et se
modifie en dix minutes.

Il vit quand même **dans le dépôt** plutôt que dans un dossier temporaire :
sans ça, refaire la page l'an prochain voudrait dire tout réinventer.

## Ce qu'il fait

1. Redresse les photos selon l'EXIF et en tire des vignettes légères —
   trois cent soixante-huit photos pleine taille dans une page, c'est deux
   cent soixante mégaoctets ; en vignettes, deux.
2. Constitue les listes de classes. **Charlemagne fait foi** : c'est lui
   qui dit qui était dans la salle. Le référentiel du programme porte des
   changements de classe pas encore redescendus — vingt-quatre classes
   divergeaient en 2026 — et sert seulement de repli pour les classes
   absentes de l'export (NDE).
3. Écrit la page dans le dossier des photos, données comprises.

## Utilisation

    python scripts/trombinoscope_photos.py "D:\\Photos rentrée" \\
        --export "C:\\...\\Export_PMB_NDK-SU_2027.csv"

L'export attendu est celui que Charlemagne produit pour PMB : il porte
`Num Badge`, `Nom`, `Prénom` et `Code classe`. Sans `--export`, les listes
viennent entièrement du référentiel, ce que le script signale.

La page produite s'ouvre en double-cliquant dessus. Elle n'écrit rien :
c'est `_renommer_les_photos.py`, à côté d'elle, qui copie les fichiers
sous leur nouveau nom dans un dossier voisin.
"""
from __future__ import annotations

import argparse
import csv
import io
import json
import os
import re
import sqlite3
import sys
import unicodedata
from pathlib import Path

RACINE = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RACINE))

GABARIT = Path(__file__).resolve().parent / "trombinoscope_photos.html"
TAILLE_VIGNETTE = (260, 260)


# ---------------------------------------------------------------------------
# Les photos
# ---------------------------------------------------------------------------


def numero(nom_fichier: str) -> int:
    m = re.search(r"(\d+)", nom_fichier)
    if not m:
        raise ValueError(f"Pas de numéro dans « {nom_fichier} »")
    return int(m.group(1))


def fabriquer_vignettes(dossier: Path) -> list[str]:
    """Des vignettes redressées, une par photo, dans `_vignettes`.

    La rotation EXIF est **cuite dans la vignette** : le navigateur n'a plus
    à l'appliquer, et un visage couché ne se reconnaît pas.
    """
    from PIL import Image, ImageOps

    sortie = dossier / "_vignettes"
    sortie.mkdir(exist_ok=True)

    fichiers = sorted(
        (f.name for f in dossier.iterdir()
         if f.is_file() and f.suffix.lower() in (".jpg", ".jpeg")),
        key=numero,
    )
    if not fichiers:
        raise SystemExit(f"Aucune photo .jpg dans {dossier}")

    faites = 0
    for f in fichiers:
        cible = sortie / f
        if cible.exists():
            continue
        with Image.open(dossier / f) as im:
            im = ImageOps.exif_transpose(im)
            im.thumbnail(TAILLE_VIGNETTE)
            im.convert("RGB").save(cible, "JPEG", quality=72)
        faites += 1
        if faites % 80 == 0:
            print(f"   {faites} vignette(s)…")

    poids = sum((sortie / f).stat().st_size for f in fichiers) / 1e6
    print(f"{len(fichiers)} photo(s), {faites} vignette(s) fabriquée(s), {poids:.1f} Mo")
    return fichiers


# ---------------------------------------------------------------------------
# Les listes de classes
# ---------------------------------------------------------------------------


def sans_accent(s: str) -> str:
    s = unicodedata.normalize("NFD", s or "")
    return "".join(c for c in s if unicodedata.category(c) != "Mn")


def cle_identite(s: str) -> str:
    return " ".join(sans_accent(s).upper().replace("-", " ").replace("'", " ").split())


def photos_deja_au_serveur(chemin: str | None) -> set[str]:
    """Qui a déjà une photo — pour le signaler, pas pour l'exclure.

    Une séance rephotographie souvent des élèves qui en avaient déjà une.
    """
    if not chemin:
        return set()
    try:
        return {cle_identite(Path(f).stem) for f in os.listdir(chemin)}
    except OSError as e:
        print(f"   (dossier serveur illisible, on continue sans : {e})")
        return set()


def listes_de_classes(export: Path | None, base: Path, serveur: str | None):
    """Les classes et leurs élèves, dans l'ordre de l'appel.

    L'ordre du fichier de Charlemagne est **conservé tel quel** : il est
    déjà alphabétique, et les rares classes qui semblent y déroger ne
    diffèrent que par la place des apostrophes (`LABOURIER` avant
    `L'ERROL`). Retrier avec une autre collation introduirait un décalage
    là où il n'y en avait pas.
    """
    deja = photos_deja_au_serveur(serveur)
    classes: dict[str, list[dict]] = {}
    source: dict[str, str] = {}
    candidats: dict[str, list[dict]] = {}

    if export:
        with io.open(export, encoding="utf-8-sig", newline="") as f:
            lignes = list(csv.reader(f, delimiter=";"))
        entete = lignes[0]
        for col in ("Num Badge", "Nom", "Prénom", "Code classe"):
            if col not in entete:
                raise SystemExit(
                    f"L'export ne porte pas la colonne « {col} ». "
                    f"Colonnes lues : {', '.join(entete[:6])}…"
                )
        ib, inom = entete.index("Num Badge"), entete.index("Nom")
        ipre, icl = entete.index("Prénom"), entete.index("Code classe")
        for l in lignes[1:]:
            if len(l) <= icl or not l[icl].strip():
                continue
            cl = l[icl].strip()
            classes.setdefault(cl, []).append({
                "nom": l[inom].strip(), "prenom": l[ipre].strip(),
                "badge": l[ib].strip(),
                "photo": cle_identite(f"{l[inom]} {l[ipre]}") in deja,
            })
            source[cl] = "Charlemagne"

    # Le repli se décide sur l'ensemble des classes déjà tenues, pas au fil
    # de la boucle : sinon le premier élève crée la classe et les suivants
    # sont écartés comme si elle venait de l'export.
    tenues = set(classes)
    badges_export = {e["badge"] for gens in classes.values() for e in gens}

    con = sqlite3.connect(str(base))
    con.row_factory = sqlite3.Row
    annee = con.execute(
        "SELECT id FROM annee_scolaire ORDER BY libelle DESC LIMIT 1").fetchone()
    if annee is None:
        raise SystemExit("Aucune année scolaire dans la base.")
    hors_export = 0
    for x in con.execute(
        "SELECT DISTINCT p.badge, p.nom, p.prenom, p.classe FROM personne p "
        "WHERE p.type='eleve' AND COALESCE(p.classe,'')<>'' "
        "AND EXISTS (SELECT 1 FROM snapshot s "
        "            WHERE s.personne_id=p.id AND s.annee_scolaire_id=?)",
        (annee["id"],),
    ):
        cl, badge = x["classe"], str(x["badge"])
        eleve = {
            "nom": x["nom"], "prenom": x["prenom"], "badge": badge,
            "photo": cle_identite(f"{x['nom']} {x['prenom']}") in deja,
        }
        if cl not in tenues:
            classes.setdefault(cl, []).append(eleve)
            source[cl] = "référentiel"
        elif badge not in badges_export:
            # Le référentiel le place ici, l'export du jour l'ignore. Il n'est
            # **pas** inscrit d'office : sur les onze relevés en 2026, un seul
            # était dans la salle, et les mettre tous dans les listes cassait
            # trois classes qui tombaient juste pour en réparer une. La page
            # les propose classe par classe, et c'est l'écart de comptage qui
            # dit s'il faut les prendre.
            candidats.setdefault(cl, []).append(eleve)
            hors_export += 1
    con.close()

    for cl, gens in classes.items():
        if source[cl] == "référentiel":
            gens.sort(key=lambda g: (sans_accent(g["nom"]).upper().replace("'", ""),
                                     sans_accent(g["prenom"]).upper()))

    if hors_export:
        print(f"   {hors_export} élève(s) connus du référentiel mais absents "
              f"de l'export — proposés dans la page, pas inscrits d'office")

    venant = sum(1 for s in source.values() if s == "Charlemagne")
    print(f"{len(classes)} classe(s) — {venant} de Charlemagne, "
          f"{len(classes) - venant} du référentiel — "
          f"{sum(len(v) for v in classes.values())} élève(s)")
    return classes, source, candidats


# ---------------------------------------------------------------------------
# La page
# ---------------------------------------------------------------------------


def ecrire_page(dossier: Path, photos: list[str], classes: dict, source: dict,
                candidats: dict) -> Path:
    if not GABARIT.exists():
        raise SystemExit(f"Gabarit introuvable : {GABARIT}")
    gabarit = io.open(GABARIT, encoding="utf-8").read()
    donnees = (
        "<script>\n"
        f"window.__PHOTOS__ = {json.dumps(photos, ensure_ascii=False)};\n"
        f"window.__CLASSES__ = {json.dumps(classes, ensure_ascii=False)};\n"
        f"window.__SOURCE__ = {json.dumps(source, ensure_ascii=False)};\n"
        f"window.__HORS_EXPORT__ = {json.dumps(candidats, ensure_ascii=False)};\n"
        "</script>\n<script>"
    )
    page = gabarit.replace("<script>\nconst PHOTOS", donnees + "\nconst PHOTOS", 1)
    if "window.__PHOTOS__" not in page:
        raise SystemExit("Le gabarit a changé : le point d'injection est introuvable.")
    cible = dossier / "_caler_les_photos.html"
    io.open(cible, "w", encoding="utf-8").write(page)
    print(f"Page écrite : {cible}  ({len(page.encode('utf-8')) / 1e6:.1f} Mo)")
    return cible


def main() -> None:
    p = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    p.add_argument("dossier", help="dossier contenant les photos de la séance")
    p.add_argument("--export", help="export PMB de Charlemagne (.csv)")
    p.add_argument("--base", default=None, help="base du programme (défaut : celle de %APPDATA%)")
    p.add_argument("--serveur", default=None,
                   help="dossier photos du serveur, pour signaler qui en a déjà une")
    a = p.parse_args()

    dossier = Path(a.dossier)
    if not dossier.is_dir():
        raise SystemExit(f"Dossier introuvable : {dossier}")

    base = Path(a.base) if a.base else (
        Path(os.environ.get("APPDATA", Path.home())) / "appli-rentree" / "appli_rentree.db")
    if not base.exists():
        raise SystemExit(f"Base introuvable : {base}")

    export = Path(a.export) if a.export else None
    if export and not export.exists():
        raise SystemExit(f"Export introuvable : {export}")
    if not export:
        print("Sans --export : les listes viennent du référentiel, qui peut "
              "porter des changements de classe que Charlemagne ignore encore.")

    photos = fabriquer_vignettes(dossier)
    classes, source, candidats = listes_de_classes(export, base, a.serveur)
    ecrire_page(dossier, photos, classes, source, candidats)

    # Le renommeur se repère sur son propre dossier pour trouver les photos :
    # il doit donc vivre à côté d'elles, pas dans le dépôt.
    import shutil

    renommeur = Path(__file__).resolve().parent / "renommer_photos.py"
    if renommeur.exists():
        shutil.copy2(renommeur, dossier / "_renommer_les_photos.py")
        print(f"Renommeur posé : {dossier / '_renommer_les_photos.py'}")

    print("\nOuvre la page, saisis les bornes de chaque classe, puis lance "
          "_renommer_les_photos.py.")


if __name__ == "__main__":
    main()
