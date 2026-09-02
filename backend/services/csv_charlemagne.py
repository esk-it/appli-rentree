"""Lire un CSV sorti de Charlemagne, sans en abîmer le contenu.

Deux services s'appuient dessus — la répartition PMB et le retour des
adresses — et tous deux ont la même exigence : **relire les lignes sans
les réécrire**. L'un les redistribue telles quelles dans deux fichiers,
l'autre n'en extrait que deux colonnes ; ni l'un ni l'autre n'a le droit
de normaliser un guillemetage ou de changer un encodage au passage.

Ces fonctions étaient d'abord privées dans la répartition PMB. Les
importer depuis l'autre service revenait à s'appuyer sur son intimité :
elles vivent ici, et les deux les appellent.
"""
from __future__ import annotations

import csv

BOM_UTF8 = b"\xef\xbb\xbf"


def decoder(contenu: bytes) -> str:
    """Charlemagne écrit tantôt en UTF-8 avec BOM, tantôt en Windows-1252."""
    for encodage in ("utf-8-sig", "cp1252"):
        try:
            return contenu.decode(encodage)
        except UnicodeDecodeError:
            continue
    return contenu.decode("utf-8", errors="replace")


def lignes_du_fichier(texte: str) -> list[str]:
    """Découpe sur les seules fins de ligne.

    `str.splitlines` coupe aussi sur la tabulation verticale et le saut de
    page, qu'une adresse mal saisie peut contenir : une ligne se
    retrouverait scindée en deux, et l'élève écarté pour « 3 colonnes au
    lieu de 13 ».
    """
    return texte.replace("\r\n", "\n").replace("\r", "\n").split("\n")


def champs(ligne: str) -> list[str]:
    """Les champs d'une ligne, guillemetage compris."""
    return next(csv.reader([ligne], delimiter=";"), [])


def lire(champs_de_la_ligne: list[str], indice: int | None) -> str:
    """Le champ à cet indice, ou une chaîne vide s'il n'existe pas.

    Les colonnes d'identité sont facultatives : seules celles dont un
    service a besoin pour travailler sont contrôlées dans l'en-tête.
    """
    if indice is None or indice >= len(champs_de_la_ligne):
        return ""
    return champs_de_la_ligne[indice].strip()
