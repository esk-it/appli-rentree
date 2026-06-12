"""Service de logging des générations dans l'historique."""
from __future__ import annotations

from sqlalchemy.orm import Session

from backend.models import Generation


def logger_generation(
    session: Session,
    cible: str,
    annee_n: str,
    fichiers: list,
    annee_n_minus_1: str | None = None,
    notes: str | None = None,
) -> Generation:
    """Crée une entrée d'historique pour une génération.

    Args:
        cible: "koxo", "pmb", "cardstudio", "smartair", "google",
               "koxo-adultes", "google-adultes", "tout".
        fichiers: liste de FichierGenere (ou dict avec champ nb_lignes).
                  On totalise les nb_lignes pour stat.
    """
    nb_lignes = 0
    for f in fichiers:
        # Supporte dataclass ou dict
        nb_l = getattr(f, "nb_lignes", None)
        if nb_l is None and isinstance(f, dict):
            nb_l = f.get("nb_lignes", 0)
        nb_lignes += int(nb_l or 0)

    g = Generation(
        cible=cible,
        annee_n=annee_n,
        annee_n_minus_1=annee_n_minus_1,
        nb_fichiers=len(fichiers),
        nb_lignes_total=nb_lignes,
        notes=notes,
    )
    session.add(g)
    session.commit()
    session.refresh(g)
    return g
