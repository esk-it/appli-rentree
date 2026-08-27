"""Aligner le référentiel sur les identifiants que KoXo a retenus.

Le programme propose, KoXo décide. Il numérote les homonymes à partir de
1, plafonne à dix caractères et raccourcit la base pour faire place au
suffixe. Quand ses règles diffèrent des nôtres, le compte naît sous un nom
que le référentiel ignore — deux élèves dans ce cas à la première
synchronisation réelle.
"""
from __future__ import annotations

import io as _io

import pytest
from fastapi.testclient import TestClient

from backend.models import Personne


@pytest.fixture()
def client(tmp_db_path):
    from backend.main import app

    with TestClient(app) as c:
        yield c


def _personne(session, nom, prenom, login, badge):
    p = Personne(
        type="eleve", nom=nom, prenom=prenom, login=login, badge=badge,
        id_charlemagne=badge,
    )
    session.add(p)
    session.commit()
    return p


def _export(tmp_path, lignes, nom="koxo.csv"):
    chemin = tmp_path / nom
    with _io.open(chemin, "w", encoding="cp1252", newline="") as f:
        f.write("Groupe primaire;Nom;Prénom;Identifiant;ID unique\r\n")
        for l in lignes:
            f.write(";".join(str(c) for c in l) + "\r\n")
    return chemin


def test_le_referentiel_apprend_le_nom_que_koxo_a_choisi(session, tmp_path):
    """Cas réel : `lacquitter2` faisait onze caractères, KoXo a raccourci."""
    from backend.services.aligner_sur_koxo import aligner_sur_koxo

    p = _personne(session, "ACQUITTER--CASTEL", "Lilou", "lacquitter2", 99740)
    f = _export(tmp_path, [
        ["Elèves", "ACQUITTER--CASTEL", "Lilou", "lacquitte1", 99740],
    ])

    r = aligner_sur_koxo(session, f, site="NDK", mode="reel")
    assert r.nb_applicables == 1
    session.refresh(p)
    assert p.login == "lacquitte1"


def test_la_simulation_ne_change_rien(session, tmp_path):
    from backend.services.aligner_sur_koxo import aligner_sur_koxo

    p = _personne(session, "MARTIN", "Paul", "pmartin2", 100)
    f = _export(tmp_path, [["Elèves", "MARTIN", "Paul", "pmartin1", 100]])

    r = aligner_sur_koxo(session, f)
    assert r.nb_applicables == 1
    session.rollback()
    session.refresh(p)
    assert p.login == "pmartin2", "rien n'a été écrit"


def test_un_identifiant_deja_porte_nest_pas_aligne(session, tmp_path):
    """L'aligner créerait un doublon là où on voulait lever une divergence."""
    from backend.services.aligner_sur_koxo import aligner_sur_koxo

    a = _personne(session, "MARTIN", "Paul", "pmartin", 100)
    b = _personne(session, "MARTIN", "Pierre", "pmartin2", 200)
    # KoXo prétend que le badge 200 s'appelle « pmartin » — déjà pris.
    f = _export(tmp_path, [["Elèves", "MARTIN", "Pierre", "pmartin", 200]])

    r = aligner_sur_koxo(session, f, mode="reel")
    assert r.nb_applicables == 0
    assert r.nb_bloques == 1
    assert "doublon" in r.alignements[0].motif
    session.refresh(a)
    session.refresh(b)
    assert a.login == "pmartin" and b.login == "pmartin2", "rien n'a bougé"


def test_le_rapprochement_ne_se_fait_que_par_id_unique(session, tmp_path):
    """Un nom identique ne suffit pas : seul le badge relie les deux mondes."""
    from backend.services.aligner_sur_koxo import aligner_sur_koxo

    p = _personne(session, "MARTIN", "Paul", "pmartin", 100)
    # Même nom, badge inconnu du référentiel.
    f = _export(tmp_path, [["Elèves", "MARTIN", "Paul", "pmartin9", 999]])

    r = aligner_sur_koxo(session, f, mode="reel")
    assert r.alignements == []
    session.refresh(p)
    assert p.login == "pmartin"


def test_les_comptes_concordants_sont_comptes_sans_bruit(session, tmp_path):
    from backend.services.aligner_sur_koxo import aligner_sur_koxo

    _personne(session, "MARTIN", "Paul", "pmartin", 100)
    f = _export(tmp_path, [["Elèves", "MARTIN", "Paul", "pmartin", 100]])

    r = aligner_sur_koxo(session, f)
    assert r.nb_concordants == 1
    assert r.alignements == []


def test_un_echange_croise_est_applique_sans_collision(session, tmp_path):
    """Deux identifiants qui se croisent : la libération précède l'attribution."""
    from backend.services.aligner_sur_koxo import aligner_sur_koxo

    a = _personne(session, "MOAL", "Julia", "jmoal2", 93230)
    b = _personne(session, "MOAL", "Jules", "jmoal", 62930)
    f = _export(tmp_path, [
        ["Elèves", "MOAL", "Julia", "jmoal", 93230],
        ["Elèves", "MOAL", "Jules", "jmoal2", 62930],
    ])

    r = aligner_sur_koxo(session, f, mode="reel")
    assert r.nb_applicables == 2
    session.refresh(a)
    session.refresh(b)
    assert a.login == "jmoal"
    assert b.login == "jmoal2"


def test_lendpoint_simule_puis_applique(session, client, tmp_path):
    import base64

    p = _personne(session, "ACQUITTER--CASTEL", "Lilou", "lacquitter2", 99740)
    f = _export(tmp_path, [
        ["Elèves", "ACQUITTER--CASTEL", "Lilou", "lacquitte1", 99740],
    ])
    b64 = base64.b64encode(f.read_bytes()).decode()

    r = client.post("/api/koxo/aligner", json={
        "fichier_base64": b64, "nom_fichier": "koxo.csv", "site": "NDK",
    })
    assert r.status_code == 200, r.text
    assert r.json()["nb_applicables"] == 1
    session.refresh(p)
    assert p.login == "lacquitter2", "la simulation n'écrit pas"

    r = client.post("/api/koxo/aligner", json={
        "fichier_base64": b64, "nom_fichier": "koxo.csv", "site": "NDK",
        "mode": "reel",
    })
    assert r.status_code == 200, r.text
    session.refresh(p)
    assert p.login == "lacquitte1"
