"""Tests des collisions d'adresses, et de l'écran qui les départage.

Ce que ces tests protègent : **une suggestion n'est jamais une décision**.
Les adresses existantes portent tantôt un `1`, tantôt un `2`, sans règle
déductible. Le programme propose ; créer un compte sous une adresse que
personne n'a validée serait exactement l'erreur que cet écran existe pour
éviter.
"""
from __future__ import annotations

import pytest
from fastapi.testclient import TestClient


@pytest.fixture()
def client(tmp_db_path):
    """Client FastAPI sur la base temporaire, comme dans `test_api`."""
    from backend.main import app

    with TestClient(app) as c:
        yield c


@pytest.fixture()
def deux_homonymes(session, site_factory, personne_factory):
    """Deux personnes du même nom, dont une détient déjà l'adresse nue."""
    site = site_factory("NDK")
    titulaire = personne_factory(
        site_id=site.id,
        nom="GUILLOU",
        prenom="Hugo",
        login="hguillou",
        email_constate="hugo.guillou@lekreisker.fr",
    )
    arrivant = personne_factory(
        site_id=site.id, nom="GUILLOU", prenom="Hugo", login="hguillou2"
    )
    return site, titulaire, arrivant


def test_deux_homonymes_visent_la_meme_adresse(session, deux_homonymes):
    from backend.services.anomalies import collisions_email

    _, titulaire, arrivant = deux_homonymes
    conflits = collisions_email(session)

    assert list(conflits) == ["hugo.guillou@lekreisker.fr"]
    assert {p.id for p in conflits["hugo.guillou@lekreisker.fr"]} == {
        titulaire.id,
        arrivant.id,
    }


def test_une_adresse_constatee_distincte_leve_la_collision(session, deux_homonymes):
    """C'est le geste que l'écran enregistre : l'arrivant prend un suffixe."""
    from backend.services.anomalies import collisions_email

    _, _, arrivant = deux_homonymes
    arrivant.email_constate = "hugo.guillou2@lekreisker.fr"
    session.commit()

    assert collisions_email(session) == {}


def test_sans_site_personne_ne_vise_rien(session, personne_factory):
    """Aucune adresse ne se calcule sans domaine : c'est une autre anomalie."""
    from backend.services.anomalies import collisions_email

    personne_factory(nom="SEULE", prenom="Ame", login="aseule")
    personne_factory(nom="SEULE", prenom="Ame", login="aseule2")

    assert collisions_email(session) == {}


def test_l_anomalie_et_l_ecran_comptent_pareil(session, deux_homonymes):
    """Une seule source : deux implémentations finiraient par diverger."""
    from backend.services.anomalies import collisions_email, detecter_anomalies

    rapport = detecter_anomalies(session, annee_id=None)
    collision = next(
        a for a in rapport.anomalies if a.type == "collision_email"
    )

    assert collision.nb_concernes == sum(
        len(ps) for ps in collisions_email(session).values()
    )


def test_l_endpoint_rend_la_liste_nominative(session, deux_homonymes, client):
    """L'écran a besoin de qui vise quoi, pas d'un compteur."""
    _, titulaire, arrivant = deux_homonymes

    r = client.get("/api/personnes/collisions")
    assert r.status_code == 200, r.text
    corps = r.json()

    assert len(corps) == 1
    groupe = corps[0]
    assert groupe["adresse"] == "hugo.guillou@lekreisker.fr"
    assert groupe["plusieurs_comptes"] is False

    par_id = {v["personne_id"]: v for v in groupe["visants"]}
    # Le titulaire garde l'adresse nue ; c'est à l'arrivant de trancher.
    assert par_id[titulaire.id]["a_un_compte"] is True
    assert par_id[titulaire.id]["a_trancher"] is False
    assert par_id[arrivant.id]["a_un_compte"] is False
    assert par_id[arrivant.id]["a_trancher"] is True
    # La suggestion porte un suffixe, et ne touche à rien.
    assert par_id[arrivant.id]["adresse_proposee"] == "hugo.guillou2@lekreisker.fr"
    session.refresh(arrivant)
    assert arrivant.email_constate is None


def test_la_route_collisions_n_est_pas_avalee(session, client):
    """`/collisions` doit être lue comme telle, pas comme un identifiant.

    La route variable `/{personne_id}` est déclarée dans le même routeur ;
    déclarée avant, elle aurait capté « collisions » et répondu 422.
    """
    r = client.get("/api/personnes/collisions")
    assert r.status_code == 200
    assert r.json() == []


def test_deux_titulaires_de_la_meme_adresse_doivent_trancher_tous_les_deux(
    session, site_factory, personne_factory, client
):
    """Cas rencontré sur la base réelle : trois groupes sur vingt-neuf.

    Deux fiches portent le même `email_constate`, héritées d'un amorçage.
    Personne ne peut être présumé garder l'adresse — désigner un titulaire
    au hasard reviendrait à retirer à quelqu'un une adresse en service.
    """
    site = site_factory("NDK")
    a = personne_factory(
        site_id=site.id, nom="QUEMENEUR", prenom="Anna", login="aquemeneur",
        email_constate="anna.quemeneur@lekreisker.fr",
    )
    b = personne_factory(
        site_id=site.id, nom="QUÉMÉNEUR", prenom="Anna", login="aquemeneur2",
        email_constate="anna.quemeneur@lekreisker.fr",
    )

    groupe = client.get("/api/personnes/collisions").json()[0]
    assert groupe["plusieurs_comptes"] is True

    par_id = {v["personne_id"]: v for v in groupe["visants"]}
    assert par_id[a.id]["a_trancher"] is True
    assert par_id[b.id]["a_trancher"] is True
    # Chacune reçoit une suggestion distincte, sinon la saisie recréerait
    # la collision qu'on vient d'ouvrir.
    assert (
        par_id[a.id]["adresse_proposee"] != par_id[b.id]["adresse_proposee"]
    )
