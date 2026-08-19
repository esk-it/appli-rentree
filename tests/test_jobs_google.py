"""Tests du suivi d'exécution des opérations Google.

Le client Google est remplacé par une fonction contrôlée : la mécanique
de suivi se teste entièrement sans credentials ni réseau.
"""
from __future__ import annotations

import time
from dataclasses import dataclass

import pytest


@dataclass
class OpFactice:
    action: str
    email: str
    libelle: str
    personne_id: int | None = None
    ou_visee: str | None = None


def _ops(n: int, prefixe: str = "e"):
    return [
        OpFactice(
            action="deplacer",
            email=f"{prefixe}{i}@lekreisker.fr",
            libelle=f"Déplacer {prefixe}{i} vers /NDK",
            personne_id=i + 1,
            ou_visee="/3. NDK/NDK2026",
        )
        for i in range(n)
    ]


@pytest.fixture(autouse=True)
def registre_propre():
    from backend.services import jobs_google

    jobs_google._JOBS.clear()
    yield
    jobs_google._JOBS.clear()


def test_job_cree_est_en_attente():
    from backend.services.jobs_google import creer_job

    job = creer_job(phase="pre_rentree", libelle="Test", operations=_ops(3))
    assert job.total == 3
    assert job.nb_traitees == 0
    assert job.est_termine is False
    assert [e.statut for e in job.etapes] == ["attente"] * 3
    assert job.etapes[0].email == "e0@lekreisker.fr"


def test_execution_complete_marque_tout_reussi():
    from backend.services.jobs_google import creer_job, executer_job

    ops = _ops(4)
    job = creer_job(phase="definitive", libelle="Test", operations=ops)
    executer_job(job, ops, appliquer=lambda o: None)

    assert job.nb_reussies == 4
    assert job.nb_echecs == 0
    assert job.est_termine is True
    assert job.progression == 1.0


def test_un_echec_narrete_pas_les_suivants():
    """Un compte refusé par Google ne doit pas bloquer les 800 d'après."""
    from backend.services.jobs_google import creer_job, executer_job

    ops = _ops(5)

    def appliquer(o):
        if o.email == "e2@lekreisker.fr":
            raise RuntimeError("User not found")

    job = creer_job(phase="definitive", libelle="Test", operations=ops)
    executer_job(job, ops, appliquer=appliquer)

    assert job.nb_reussies == 4
    assert job.nb_echecs == 1
    echec = next(e for e in job.etapes if e.statut == "echec")
    assert echec.email == "e2@lekreisker.fr"
    assert "User not found" in echec.message
    # Les suivants ont bien été traités
    assert job.etapes[3].statut == "reussi"
    assert job.etapes[4].statut == "reussi"


def test_seuls_les_succes_sont_memorises():
    """Une opération en échec n'a rien changé chez Google : ne pas l'inscrire."""
    from backend.services.jobs_google import creer_job, executer_job

    ops = _ops(3)
    memorises = []

    def appliquer(o):
        if o.email == "e1@lekreisker.fr":
            raise RuntimeError("boom")

    job = creer_job(phase="definitive", libelle="Test", operations=ops)
    executer_job(job, ops, appliquer=appliquer, au_succes=memorises.extend)

    assert [pid for pid, _ in memorises] == [1, 3]


def test_annulation_stoppe_apres_letape_en_cours():
    from backend.services.jobs_google import creer_job, demander_annulation, executer_job

    ops = _ops(10)
    job = creer_job(phase="definitive", libelle="Test", operations=ops)

    def appliquer(o):
        if o.email == "e3@lekreisker.fr":
            demander_annulation(job.id)

    executer_job(job, ops, appliquer=appliquer)

    assert job.annule is True
    assert job.est_termine is True
    # e3 a bien été appliquée avant l'arrêt — on ne coupe pas au milieu
    assert job.etapes[3].statut == "reussi"
    assert job.etapes[4].statut == "attente"
    assert job.nb_traitees == 4


def test_echec_de_memorisation_est_signale():
    """Appliqué chez Google mais non enregistré : le pire des cas, à dire."""
    from backend.services.jobs_google import creer_job, executer_job

    ops = _ops(2)
    job = creer_job(phase="definitive", libelle="Test", operations=ops)

    def au_succes(_):
        raise RuntimeError("base verrouillée")

    executer_job(job, ops, appliquer=lambda o: None, au_succes=au_succes)

    assert job.nb_reussies == 2
    assert "non mémorisées" in job.erreur_fatale


def test_lancement_en_tache_de_fond():
    from backend.services.jobs_google import creer_job, lancer_en_tache_de_fond, obtenir_job

    ops = _ops(3)
    job = creer_job(phase="definitive", libelle="Test", operations=ops)
    lancer_en_tache_de_fond(job, ops, appliquer=lambda o: time.sleep(0.01))

    for _ in range(200):
        if obtenir_job(job.id).est_termine:
            break
        time.sleep(0.01)

    assert obtenir_job(job.id).nb_reussies == 3


def test_purge_garde_les_plus_recents():
    from backend.services.jobs_google import (
        creer_job,
        executer_job,
        lister_jobs,
        purger_jobs_termines,
    )

    for i in range(5):
        ops = _ops(1, prefixe=f"j{i}_")
        j = creer_job(phase="definitive", libelle=f"Job {i}", operations=ops)
        executer_job(j, ops, appliquer=lambda o: None)

    assert purger_jobs_termines(garder=2) == 3
    assert len(lister_jobs()) == 2


def test_annulation_dun_job_termine_est_refusee():
    from backend.services.jobs_google import creer_job, demander_annulation, executer_job

    ops = _ops(1)
    job = creer_job(phase="definitive", libelle="Test", operations=ops)
    executer_job(job, ops, appliquer=lambda o: None)
    assert demander_annulation(job.id) is False


def test_job_inconnu():
    from backend.services.jobs_google import demander_annulation, obtenir_job

    assert obtenir_job("nexistepas") is None
    assert demander_annulation("nexistepas") is False


# ---------------------------------------------------------------------------
# API : cycle complet vu depuis l'interface
# ---------------------------------------------------------------------------


@pytest.fixture()
def client(tmp_db_path):
    from fastapi.testclient import TestClient

    from backend.main import app

    with TestClient(app) as c:
        yield c


def test_api_suit_un_job_et_rejoue_les_echecs(client):
    """Le parcours que fait l'écran : lancer, suivre, rejouer."""
    from backend.services.jobs_google import creer_job, executer_job

    ops = _ops(4)
    job = creer_job(phase="definitive", libelle="Bascule", operations=ops)

    r = client.get(f"/api/google/jobs/{job.id}")
    assert r.status_code == 200
    assert r.json()["nb_traitees"] == 0
    assert r.json()["etapes"][0]["statut"] == "attente"

    executer_job(
        job, ops,
        appliquer=lambda o: (_ for _ in ()).throw(RuntimeError("quota"))
        if o.email == "e1@lekreisker.fr" else None,
    )

    corps = client.get(f"/api/google/jobs/{job.id}").json()
    assert corps["est_termine"] is True
    assert corps["nb_reussies"] == 3
    assert corps["nb_echecs"] == 1
    echec = next(e for e in corps["etapes"] if e["statut"] == "echec")
    assert "quota" in echec["message"]
    # Le payload Google n'est jamais exposé à l'interface
    assert "payload" not in echec


def test_api_job_inconnu(client):
    assert client.get("/api/google/jobs/nexistepas").status_code == 404


def test_api_annuler_un_job_termine(client):
    from backend.services.jobs_google import creer_job, executer_job

    ops = _ops(1)
    job = creer_job(phase="definitive", libelle="X", operations=ops)
    executer_job(job, ops, appliquer=lambda o: None)
    r = client.post(f"/api/google/jobs/{job.id}/annuler")
    assert r.status_code == 409


def test_api_rejouer_sans_echec_est_refuse(client):
    from backend.services.jobs_google import creer_job, executer_job

    ops = _ops(2)
    job = creer_job(phase="definitive", libelle="X", operations=ops)
    executer_job(job, ops, appliquer=lambda o: None)
    r = client.post(f"/api/google/jobs/{job.id}/rejouer-echecs")
    assert r.status_code == 400
    assert "Aucun échec" in r.json()["detail"]


def test_rejouer_ne_reprend_que_les_echecs():
    from backend.services.jobs_google import creer_job, executer_job, operations_en_echec

    ops = _ops(5)
    job = creer_job(phase="definitive", libelle="X", operations=ops)
    executer_job(
        job, ops,
        appliquer=lambda o: (_ for _ in ()).throw(RuntimeError("boom"))
        if o.email in ("e1@lekreisker.fr", "e4@lekreisker.fr") else None,
    )

    a_rejouer = operations_en_echec(job.id)
    assert [o.email for o in a_rejouer] == ["e1@lekreisker.fr", "e4@lekreisker.fr"]
