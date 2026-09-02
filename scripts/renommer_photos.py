# -*- coding: utf-8 -*-
"""Renomme les photos d'après la correspondance validée dans la page.

## Ce qu'il fait

Lit `correspondance_photos.csv` — celui que le bouton « Enregistrer la
correspondance » a produit — et **copie** chaque photo sous le nom de
l'élève, dans un dossier voisin.

Il copie, il ne déplace pas : le dossier d'origine reste intact, et une
erreur de calage se rattrape en relançant plutôt qu'en recommençant la
séance photo.

## Ce qu'il refuse de faire

- Écraser un fichier déjà présent dans le dossier de sortie.
- Travailler sur une correspondance qui vise deux fois le même nom — deux
  photos pour un élève veut dire que le calage a glissé quelque part.
- Continuer si une photo nommée dans le fichier n'existe pas.

Dans ces trois cas il s'arrête **avant** d'avoir rien écrit, et dit quoi
regarder. Un renommage à moitié fait est plus difficile à défaire qu'un
renommage pas commencé.

## Utilisation

    python _renommer_les_photos.py [chemin\\vers\\correspondance_photos.csv]

Sans argument, il cherche le CSV à côté de lui, puis dans le dossier
Téléchargements.
"""
from __future__ import annotations

import csv
import io
import os
import shutil
import sys
from pathlib import Path

ICI = Path(__file__).resolve().parent
SORTIE = ICI.parent / (ICI.name + " - renommees")
INTERDITS = '<>:"/\\|?*'
EXTENSIONS = (".jpg", ".jpeg", ".png")


def trouver_csv(argv: list[str]) -> Path:
    if len(argv) > 1:
        return Path(argv[1])
    for candidat in (
        ICI / "correspondance_photos.csv",
        Path.home() / "Downloads" / "correspondance_photos.csv",
        Path.home() / "Téléchargements" / "correspondance_photos.csv",
    ):
        if candidat.exists():
            return candidat
    raise SystemExit(
        "Je ne trouve pas correspondance_photos.csv.\n"
        "Donne-moi son chemin :  python _renommer_les_photos.py "
        "C:\\chemin\\correspondance_photos.csv"
    )


def lire(chemin: Path) -> list[dict]:
    with io.open(chemin, encoding="utf-8-sig", newline="") as f:
        lignes = list(csv.DictReader(f, delimiter=";"))
    if not lignes:
        raise SystemExit("Le fichier de correspondance est vide.")
    manquantes = {"fichier", "nom_cible"} - set(lignes[0])
    if manquantes:
        raise SystemExit(
            "Colonnes manquantes dans le CSV : " + ", ".join(sorted(manquantes))
        )
    return lignes


def controler(lignes: list[dict]) -> list[str]:
    """Tout ce qui cloche, d'un coup — pas la première erreur seulement."""
    soucis: list[str] = []

    for l in lignes:
        if not (ICI / l["fichier"]).exists():
            soucis.append(f"photo introuvable : {l['fichier']}")
        mauvais = [c for c in l["nom_cible"] if c in INTERDITS]
        if mauvais:
            soucis.append(
                f"« {l['nom_cible']} » contient un caractère interdit "
                f"par Windows : {' '.join(sorted(set(mauvais)))}"
            )
        # Une ligne ajoutée à la main oublie facilement l'extension, et le
        # fichier produit n'est plus une image pour personne : ni Windows,
        # ni Charlemagne. Vu sur deux lignes de BTS_2 en 2026.
        if not l["nom_cible"].lower().endswith(EXTENSIONS):
            soucis.append(
                f"« {l['nom_cible']} » n'a pas d'extension d'image — "
                "ajoute « .jpg » à la fin"
            )

    vus: dict[str, str] = {}
    for l in lignes:
        cle = l["nom_cible"].casefold()
        if cle in vus:
            soucis.append(
                f"deux photos pour « {l['nom_cible']} » : "
                f"{vus[cle]} et {l['fichier']} — le calage a glissé"
            )
        vus[cle] = l["fichier"]

    if SORTIE.exists():
        for l in lignes:
            if (SORTIE / l["nom_cible"]).exists():
                soucis.append(f"déjà dans le dossier de sortie : {l['nom_cible']}")
    return soucis


def main() -> None:
    chemin = trouver_csv(sys.argv)
    lignes = lire(chemin)
    print(f"Correspondance lue : {chemin}")
    print(f"{len(lignes)} photo(s) à renommer.\n")

    soucis = controler(lignes)
    if soucis:
        print("Rien n'a été écrit. À régler d'abord :")
        for s in soucis[:40]:
            print("   ·", s)
        if len(soucis) > 40:
            print(f"   … et {len(soucis) - 40} autre(s)")
        raise SystemExit(1)

    SORTIE.mkdir(parents=True, exist_ok=True)
    par_classe: dict[str, int] = {}
    for l in lignes:
        shutil.copy2(ICI / l["fichier"], SORTIE / l["nom_cible"])
        cl = l.get("classe") or "?"
        par_classe[cl] = par_classe.get(cl, 0) + 1

    print(f"{len(lignes)} photo(s) copiée(s) dans :\n   {SORTIE}\n")
    for cl in sorted(par_classe):
        print("   %-12s %3d" % (cl, par_classe[cl]))
    print(
        "\nLe dossier d'origine n'a pas bougé. Vérifie quelques noms, puis "
        "verse le contenu dans\n"
        r"   \\ESK-APP01\Charlemagne\Alcuin\Photos\Eleves\KREISKER\2026-2027"
    )


if __name__ == "__main__":
    main()
