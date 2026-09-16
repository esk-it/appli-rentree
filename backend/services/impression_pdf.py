"""Transformer en PDF ce que le programme met en page en HTML.

## Pourquoi pas une bibliothèque

Les étiquettes sont déjà composées : une feuille A4, une grille, des
sauts de page calculés, une police choisie. Repasser par une bibliothèque
PDF voudrait dire réécrire cette mise en page une seconde fois, dans un
autre langage, et entretenir les deux. La première divergence entre les
deux rendus se découvrirait sur une planche imprimée de travers.

Les bibliothèques HTML→PDF de l'écosystème Python ne sont pas une réponse
plus simple : WeasyPrint réclame GTK sous Windows, ce qui n'a pas sa place
dans un exécutable qu'on installe d'un double-clic, et les moteurs en
Python pur ne rendent pas le CSS de grille dont dépendent ces planches.

## Ce qui imprime, c'est le navigateur déjà installé

Windows 11 livre Edge, et Edge sait imprimer une page en PDF sans ouvrir de
fenêtre. C'est exactement ce que fait le bouton « Imprimer » du navigateur,
en ligne de commande. Le rendu est donc **le même** que celui qu'on voit à
l'écran — pas une approximation.

Chrome fait aussi bien et est cherché ensuite, pour les postes où Edge
aurait été retiré. Si aucun des deux n'est trouvé, la conversion se refuse
en le disant : le HTML reste produit, et il s'imprime à la main.

## Un fichier par classe

Sortir les étiquettes classe par classe est le geste réel — chaque planche
part chez un professeur principal différent. Les produire une à une prenait
une demi-heure par campagne ; elles se demandent maintenant ensemble.
"""
from __future__ import annotations

import shutil
import subprocess
import tempfile
import time
import uuid
from dataclasses import dataclass, field
from pathlib import Path

DELAI_PAR_PAGE = 90
"""Secondes accordées à une conversion. Une planche de trente étiquettes se
rend en deux ou trois ; le plafond n'existe que pour ne pas rester bloqué
sur un navigateur qui attendrait quelque chose."""

CHEMINS_CONNUS = (
    r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe",
    r"C:\Program Files\Microsoft\Edge\Application\msedge.exe",
    r"C:\Program Files\Google\Chrome\Application\chrome.exe",
    r"C:\Program Files (x86)\Google\Chrome\Application\chrome.exe",
)


class ImpressionImpossible(Exception):
    """La conversion est refusée, et le message dit pourquoi."""


@dataclass
class Planche:
    """Un document à rendre, et son nom de fichier."""

    nom: str
    html: str


@dataclass
class RapportImpression:
    pdfs: dict[str, bytes] = field(default_factory=dict)
    echecs: list[tuple[str, str]] = field(default_factory=list)
    moteur: str = ""

    @property
    def nb_rendus(self) -> int:
        return len(self.pdfs)


def trouver_navigateur() -> str | None:
    """Le premier navigateur capable d'imprimer, ou `None`.

    Cherche d'abord dans le `PATH`, puis aux emplacements d'installation
    habituels — un poste géré n'a pas toujours Edge dans son `PATH`.
    """
    for nom in ("msedge", "chrome"):
        chemin = shutil.which(nom)
        if chemin:
            return chemin
    for chemin in CHEMINS_CONNUS:
        if Path(chemin).is_file():
            return chemin
    return None


def html_en_pdf(html: str, *, navigateur: str | None = None) -> bytes:
    """Rend une page telle que le navigateur l'imprimerait.

    Raises:
        ImpressionImpossible: aucun navigateur, ou conversion échouée.
    """
    rapport = rendre([Planche(nom="document", html=html)], navigateur=navigateur)
    if rapport.echecs:
        raise ImpressionImpossible(rapport.echecs[0][1])
    return rapport.pdfs["document"]


def rendre(
    planches: list[Planche], *, navigateur: str | None = None
) -> RapportImpression:
    """Convertit plusieurs documents. Un échec n'arrête pas les suivants.

    Chaque planche part chez quelqu'un de différent : perdre le lot entier
    parce qu'une classe a mal rendu serait disproportionné.
    """
    moteur = navigateur or trouver_navigateur()
    if moteur is None:
        raise ImpressionImpossible(
            "Aucun navigateur trouvé pour imprimer en PDF. Edge ou Chrome "
            "doit être installé — le HTML reste disponible et s'imprime "
            "depuis n'importe quel navigateur."
        )

    rapport = RapportImpression(moteur=Path(moteur).stem)
    with tempfile.TemporaryDirectory(prefix="appli-rentree-pdf-") as dossier:
        base = Path(dossier)
        # Un profil jetable : sans lui, un Edge déjà ouvert récupère la
        # demande et rend la main tout de suite, sans jamais écrire le PDF.
        profil = base / "profil"
        for planche in planches:
            jeton = uuid.uuid4().hex[:8]
            source = base / f"{jeton}.html"
            cible = base / f"{jeton}.pdf"
            source.write_text(planche.html, encoding="utf-8")
            try:
                _imprimer(moteur, source, cible, profil)
                rapport.pdfs[planche.nom] = cible.read_bytes()
            except Exception as e:
                rapport.echecs.append((planche.nom, str(e)))
    return rapport


def _imprimer(moteur: str, source: Path, cible: Path, profil: Path) -> None:
    """Lance la conversion, puis attend le fichier.

    Le processus lancé **se détache** : il rend la main en un dixième de
    seconde, avec le code 0, et le vrai travail se fait ailleurs — le PDF
    apparaît une seconde plus tard. Se fier au code de retour fait donc
    conclure à l'échec d'une conversion qui a réussi.

    On attend le fichier, puis on attend qu'il cesse de grossir : lire un
    PDF à moitié écrit donnerait un document tronqué, plus dommageable
    qu'une erreur franche.
    """
    resultat = subprocess.run(
        [
            moteur,
            "--headless=new",
            "--disable-gpu",
            "--no-first-run",
            "--no-default-browser-check",
            f"--user-data-dir={profil}",
            "--print-to-pdf-no-header",
            f"--print-to-pdf={cible}",
            source.as_uri(),
        ],
        capture_output=True,
        timeout=DELAI_PAR_PAGE,
        creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
    )

    if not _attendre_le_fichier(cible):
        detail = (resultat.stderr or b"").decode("utf-8", "replace").strip()
        raise ImpressionImpossible(
            "Le navigateur n'a pas écrit de PDF"
            + (f" — {detail[:300]}" if detail else ".")
        )


def _attendre_le_fichier(cible: Path, *, limite: float = DELAI_PAR_PAGE) -> bool:
    """Vrai quand le PDF est là et complet."""
    debut = time.monotonic()
    taille = -1
    while time.monotonic() - debut < limite:
        if cible.is_file():
            actuelle = cible.stat().st_size
            if actuelle > 0 and actuelle == taille:
                return True
            taille = actuelle
        time.sleep(0.25)
    return False


def nom_de_fichier(base: str) -> str:
    """Un nom de fichier acceptable sous Windows, sans perdre le sens.

    Les codes classe contiennent des caractères que le système refuse —
    `1/2` dans certains libellés, des espaces en fin de nom. On remplace
    plutôt que de tronquer : `T_G4B` doit rester lisible sur le dossier du
    professeur principal.
    """
    interdits = '<>:"/\\|?*'
    propre = "".join("-" if c in interdits else c for c in base).strip(" .")
    return propre or "document"
