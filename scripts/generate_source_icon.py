"""Génère l'icône source 1024×1024 utilisée par `tauri icon` pour décliner
toutes les tailles d'icônes nécessaires.

L'icône est volontairement simple : carré vert sapin avec coins arrondis,
un mortier/toque de remise de diplômes blanc au centre, et un petit liseré
clair en bas. Esprit : rentrée scolaire, calme, sérieux.

Régénération : `python scripts/generate_source_icon.py`
Puis : `npx tauri icon scripts/source_icon.png`
"""
from __future__ import annotations

from pathlib import Path

from PIL import Image, ImageDraw

ICI = Path(__file__).resolve().parent

# Dimensions et palette
TAILLE = 1024
RAYON_COIN = 180
VERT_FOND = (4, 88, 67)  # emerald-800
VERT_FONCE = (2, 64, 49)
BLANC = (255, 255, 255)
BLANC_DOUX = (236, 253, 245)  # emerald-50


def main() -> None:
    img = Image.new("RGBA", (TAILLE, TAILLE), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)

    # Carré arrondi vert
    draw.rounded_rectangle(
        (0, 0, TAILLE, TAILLE),
        radius=RAYON_COIN,
        fill=VERT_FOND,
    )

    # Petit liseré en bas (effet de profondeur)
    draw.rounded_rectangle(
        (0, TAILLE - 50, TAILLE, TAILLE),
        radius=RAYON_COIN,
        fill=VERT_FONCE,
    )

    # Toque (mortarboard) au centre — version stylisée
    cx, cy = TAILLE // 2, TAILLE // 2 - 40

    # Plateforme carrée du dessus (losange en perspective)
    largeur_plat = 540
    hauteur_plat = 130
    plat = [
        (cx - largeur_plat // 2, cy),
        (cx, cy - hauteur_plat),
        (cx + largeur_plat // 2, cy),
        (cx, cy + hauteur_plat),
    ]
    draw.polygon(plat, fill=BLANC)

    # Calotte sous la plateforme
    largeur_cal = 280
    hauteur_cal = 130
    draw.rounded_rectangle(
        (
            cx - largeur_cal // 2,
            cy + hauteur_plat - 30,
            cx + largeur_cal // 2,
            cy + hauteur_plat - 30 + hauteur_cal,
        ),
        radius=30,
        fill=BLANC,
    )

    # Glands (cordon descendant à droite de la toque)
    draw.line(
        [(cx + largeur_plat // 2 - 40, cy + 10), (cx + largeur_plat // 2 + 20, cy + 280)],
        fill=BLANC_DOUX,
        width=14,
    )
    # Petit pompon au bout du cordon
    draw.ellipse(
        (cx + largeur_plat // 2 + 5, cy + 270, cx + largeur_plat // 2 + 65, cy + 330),
        fill=BLANC_DOUX,
    )

    cible = ICI / "source_icon.png"
    img.save(cible, "PNG")
    print(f"Icône générée : {cible} ({TAILLE}×{TAILLE})")


if __name__ == "__main__":
    main()
