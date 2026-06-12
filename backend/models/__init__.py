"""Modèles SQLAlchemy de l'application."""
from backend.models.annee_scolaire import AnneeScolaire
from backend.models.eleve_snapshot import EleveSnapshot
from backend.models.etablissement import Etablissement
from backend.models.parametre import Parametre

__all__ = ["AnneeScolaire", "EleveSnapshot", "Etablissement", "Parametre"]
