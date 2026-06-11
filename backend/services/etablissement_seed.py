"""Catalogue des établissements connus de l'ensemble scolaire.

Fait correspondre les codes Charlemagne ("02-COL", "03-LY", "04-LP") à des
codes courts mémorisables et au type d'établissement. Si un export apporte
un code inconnu (typiquement le futur NDE qui n'a pas encore été inclus),
l'ingestion crée l'Etablissement avec le nom long que Charlemagne fournit
et un type "inconnu" qu'on pourra corriger plus tard via l'UI.
"""
from __future__ import annotations

ETABLISSEMENTS_CONNUS: dict[str, dict[str, str]] = {
    "02-COL": {
        "code_court": "SU",
        "nom_long": "Collège Sainte-Ursule",
        "type": "college",
    },
    "03-LY": {
        "code_court": "NDK_LY",
        "nom_long": "L.E.G.T. Notre-Dame du Kreisker",
        "type": "lycee_general",
    },
    "04-LP": {
        "code_court": "NDK_LP",
        "nom_long": "L.P. Notre-Dame du Kreisker",
        "type": "lycee_pro",
    },
    # NDE (Notre-Dame d'Espérance, collège de Cléder) : à compléter
    # avec le code Charlemagne réel à la première occurrence.
}
