"""Modèles SQLAlchemy de l'application.

Depuis la refonte identité (v0.22.0), le modèle repose sur `Personne` +
`Snapshot` + `CompteCible` — plus de séparation élèves/adultes au niveau
du stockage.
"""
from backend.models.annee_scolaire import AnneeScolaire
from backend.models.arbitrage import Arbitrage
from backend.models.compte_cible import CompteCible
from backend.models.etablissement import Etablissement
from backend.models.generation import Generation
from backend.models.parametre import Parametre
from backend.models.personne import Personne
from backend.models.site import Site
from backend.models.snapshot import Snapshot
from backend.models.suivi_chromebook import SuiviChromebook
from backend.models.table_correspondance import TableCorrespondance

__all__ = [
    "AnneeScolaire",
    "Arbitrage",
    "CompteCible",
    "Etablissement",
    "Generation",
    "Parametre",
    "Personne",
    "Site",
    "Snapshot",
    "SuiviChromebook",
    "TableCorrespondance",
]
