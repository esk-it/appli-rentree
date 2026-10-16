"""Est-on en répétition ? — une seule réponse pour tout le processus.

Voir `services/repetition.py`. L'état vit ici, hors des services, parce
que deux copies d'un même service peuvent coexister — les tests les
rechargent à chaque fois. Deux interrupteurs se contrediraient : l'un dit
« répétition », la garde Google consulte l'autre et laisse tout passer
(constaté en CI sur la v0.193.0).
"""
from __future__ import annotations

active: bool = False
"""Le programme travaille sur la copie, Google en lecture seule."""

reel: tuple | None = None
"""`(_engine, _SessionLocal)` de la vraie base, le temps de la répétition."""
