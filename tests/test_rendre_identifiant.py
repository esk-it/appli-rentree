"""Rendre un identifiant constaté à la personne qui le détient.

Un identifiant ne bouge pas — c'est la règle la plus stricte du
programme. L'exception unique : le rendre à qui le portait déjà, quand
celui à qui il avait été attribué n'en a jamais rien fait.
"""
from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from backend.models import Personne


@pytest.fixture()
def client(tmp_db_path):
    from backend.main import app

    with TestClient(app) as c:
        yield c


def _personne(session, nom, prenom, login, badge, **extra):
    p = Personne(
        type="eleve", nom=nom, prenom=prenom, login=login, badge=badge,
        id_charlemagne=badge, **extra,
    )
    session.add(p)
    session.commit()
    return p


def test_le_cas_lena_et_lana(session):
    """Le cas réel : l'identifiant part à l'entrante, la titulaire est suffixée.

    Lana détenait `llesaout` dans KoXo. Son ID unique cassé a empêché
    l'amorçage de la reconnaître ; l'identifiant a paru libre et il est
    parti à Léna, entrante en 6e. Rendre l'un revient à échanger les deux.
    """
    from backend.services.rendre_identifiant import rendre_identifiant

    lena = _personne(session, "LE SAOUT", "Lena", "llesaout", 97820)
    lana = _personne(
        session, "LE SAOUT", "Lana", "llesaout2", 81010,
        email_constate="lana.lesaout@lekreisker.fr",
    )

    r = rendre_identifiant(
        session, login="llesaout", badge_titulaire=81010, mode="reel"
    )
    assert r.echange is True
    assert r.nouveau_login_ancien_porteur == "llesaout2"

    session.refresh(lana)
    session.refresh(lena)
    assert lana.login == "llesaout"
    assert lena.login == "llesaout2"


def test_la_simulation_ne_change_rien(session):
    from backend.services.rendre_identifiant import rendre_identifiant

    lena = _personne(session, "LE SAOUT", "Lena", "llesaout", 97820)
    _personne(session, "LE SAOUT", "Lana", "llesaout2", 81010)

    r = rendre_identifiant(session, login="llesaout", badge_titulaire=81010)
    assert r.nouveau_login_ancien_porteur == "llesaout2"
    session.rollback()
    session.refresh(lena)
    assert lena.login == "llesaout", "rien n'a été écrit"


def test_un_porteur_avec_adresse_constatee_est_protege(session):
    """Un identifiant qui a servi ne se reprend pas : tout s'y rattache."""
    from backend.services.rendre_identifiant import (
        RenduImpossible,
        rendre_identifiant,
    )

    _personne(
        session, "MARTIN", "Paul", "pmartin", 100,
        email_constate="paul.martin@lekreisker.fr",
    )
    _personne(session, "MARTIN", "Pierre", "pmartin2", 200)

    with pytest.raises(RenduImpossible, match="adresse constatée"):
        rendre_identifiant(
            session, login="pmartin", badge_titulaire=200, mode="reel"
        )


def test_un_porteur_avec_compte_google_est_protege(session):
    from backend.services.rendre_identifiant import (
        RenduImpossible,
        rendre_identifiant,
    )

    _personne(session, "MARTIN", "Paul", "pmartin", 100, google_user_id="123456")
    _personne(session, "MARTIN", "Pierre", "pmartin2", 200)

    with pytest.raises(RenduImpossible, match="compte Google"):
        rendre_identifiant(
            session, login="pmartin", badge_titulaire=200, mode="reel"
        )


def test_sans_lien_de_base_un_nouveau_suffixe_est_propose(session):
    """Le titulaire ne porte pas la forme suffixée : on n'échange pas."""
    from backend.services.rendre_identifiant import rendre_identifiant

    _personne(session, "DUPONT", "Jean", "cible", 100)
    _personne(session, "MARTIN", "Paul", "autre", 200)

    r = rendre_identifiant(
        session, login="cible", badge_titulaire=200, mode="reel"
    )
    assert r.echange is False
    assert r.nouveau_login_ancien_porteur == "jdupont"


def test_un_titulaire_inconnu_est_refuse(session):
    from backend.services.rendre_identifiant import (
        RenduImpossible,
        rendre_identifiant,
    )

    _personne(session, "MARTIN", "Paul", "pmartin", 100)
    with pytest.raises(RenduImpossible, match="badge 999"):
        rendre_identifiant(session, login="pmartin", badge_titulaire=999)


def test_un_identifiant_libre_na_rien_a_rendre(session):
    from backend.services.rendre_identifiant import (
        RenduImpossible,
        rendre_identifiant,
    )

    _personne(session, "MARTIN", "Paul", "pmartin", 100)
    with pytest.raises(RenduImpossible, match="rien à rendre"):
        rendre_identifiant(session, login="inconnu", badge_titulaire=100)


def test_rendre_a_qui_le_porte_deja_est_refuse(session):
    from backend.services.rendre_identifiant import (
        RenduImpossible,
        rendre_identifiant,
    )

    _personne(session, "MARTIN", "Paul", "pmartin", 100)
    with pytest.raises(RenduImpossible, match="porte déjà"):
        rendre_identifiant(session, login="pmartin", badge_titulaire=100)


def test_lendpoint_simule_puis_applique(session, client):
    _personne(session, "LE SAOUT", "Lena", "llesaout", 97820)
    _personne(session, "LE SAOUT", "Lana", "llesaout2", 81010)

    r = client.post("/api/koxo/rendre-identifiant", json={
        "login": "llesaout", "badge_titulaire": 81010,
    })
    assert r.status_code == 200, r.text
    assert "serait rendu" in r.json()["phrase"]

    r = client.post("/api/koxo/rendre-identifiant", json={
        "login": "llesaout", "badge_titulaire": 81010, "mode": "reel",
    })
    assert r.status_code == 200, r.text
    assert r.json()["echange"] is True

    p = session.query(Personne).filter_by(badge=81010).one()
    session.refresh(p)
    assert p.login == "llesaout"


def test_lendpoint_refuse_avec_409_et_explique(session, client):
    _personne(
        session, "MARTIN", "Paul", "pmartin", 100,
        email_constate="paul.martin@lekreisker.fr",
    )
    _personne(session, "MARTIN", "Pierre", "pmartin2", 200)

    r = client.post("/api/koxo/rendre-identifiant", json={
        "login": "pmartin", "badge_titulaire": 200, "mode": "reel",
    })
    assert r.status_code == 409
    assert "adresse constatée" in r.json()["detail"]
