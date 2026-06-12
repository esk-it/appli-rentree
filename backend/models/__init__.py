"""Modèles SQLAlchemy de l'application."""
from backend.models.adulte_snapshot import AdulteSnapshot
from backend.models.annee_scolaire import AnneeScolaire
from backend.models.chambre import AffectationChambre, Chambre
from backend.models.eleve_snapshot import EleveSnapshot
from backend.models.etablissement import Etablissement
from backend.models.generation import Generation
from backend.models.parametre import Parametre

__all__ = [
    "AdulteSnapshot",
    "AffectationChambre",
    "AnneeScolaire",
    "Chambre",
    "EleveSnapshot",
    "Etablissement",
    "Generation",
    "Parametre",
]
