"""Aucun nom référencé sans être défini, dans tout le code Python.

## Pourquoi ce test existe

Python ne vérifie l'existence d'un nom qu'à l'exécution. Un symbole oublié
dans une liste d'imports ne se manifeste donc que le jour où la ligne qui
l'utilise est atteinte — et si cette ligne est un endpoint rarement
appelé, le défaut voyage jusqu'en production.

C'est arrivé sur `OperationGoogle` dans l'endpoint de sortie des comptes :
l'import manquait, la fonction levait `NameError`, et l'utilisateur voyait
un « Failed to fetch » sans rapport. Les 566 tests passaient : aucun ne
traversait ce chemin.

Ce contrôle lit le code sans l'exécuter et couvre la famille entière.

Son pendant côté interface est `test_composants_svelte.py`.
"""
from __future__ import annotations

import subprocess
import sys
from pathlib import Path

import pytest

RACINE = Path(__file__).resolve().parent.parent


def _lancer_ruff(*cibles: str) -> subprocess.CompletedProcess:
    return subprocess.run(
        [sys.executable, "-m", "ruff", "check", "--select", "F821",
         "--output-format", "concise", *cibles],
        cwd=RACINE,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
    )


def test_ruff_est_disponible():
    """Sans lui, le contrôle ci-dessous passerait en silence."""
    r = subprocess.run(
        [sys.executable, "-m", "ruff", "--version"],
        capture_output=True, text=True,
    )
    assert r.returncode == 0, (
        "ruff n'est pas installé : `python -m pip install ruff`. "
        "Sans lui, un nom absent d'une liste d'imports ne serait plus détecté."
    )


def test_aucun_nom_indefini_dans_le_backend():
    r = _lancer_ruff("backend")
    assert r.returncode == 0, (
        "Nom(s) référencé(s) sans être défini(s) — la ligne lèvera "
        f"`NameError` le jour où elle sera atteinte :\n{r.stdout}{r.stderr}"
    )


def test_aucun_nom_indefini_dans_les_tests():
    r = _lancer_ruff("tests")
    assert r.returncode == 0, f"{r.stdout}{r.stderr}"


def test_le_controle_detecte_bien_un_oubli(tmp_path: Path):
    """Le garde-fou doit échouer sur le cas qu'il prétend attraper."""
    fichier = tmp_path / "oubli.py"
    fichier.write_text(
        "def endpoint():\n    return OperationGoogle(action='x')\n",
        encoding="utf-8",
    )
    r = _lancer_ruff(str(fichier))
    assert r.returncode != 0
    assert "OperationGoogle" in r.stdout
