"""Les mots de passe de service : le portail Sodexo, rangé dans le coffre.

Johann, 19 octobre 2026 : retrouver le mot de passe du portail sur
l'ancienne procédure à chaque import. Il se range au coffre, chiffré, et
ne se lit que coffre ouvert. Les valeurs ici sont inventées.
"""
from __future__ import annotations

import pytest

MAITRE = "sardine-clavier-molybdene-1789"
FAUX = "Essai-Portail-42"


def test_le_mot_de_passe_se_range_chiffre_et_se_relit(session):
    from backend.models import Parametre
    from backend.services.coffre import (
        CoffreVerrouille,
        deposer_service,
        initialiser,
        lire_service,
        service_range,
    )

    cle = initialiser(session, MAITRE)
    assert lire_service(session, cle, "sodexo_portail") is None
    deposer_service(session, cle, "sodexo_portail", FAUX)
    session.commit()

    assert lire_service(session, cle, "sodexo_portail") == FAUX
    assert service_range(session, "sodexo_portail")
    brut = session.query(Parametre).filter_by(cle="coffre.service.sodexo_portail").one().valeur_json
    assert FAUX not in brut, "jamais en clair dans la base"
    with pytest.raises(CoffreVerrouille):
        lire_service(session, b"\x00" * 32, "sodexo_portail")


def test_un_service_inconnu_est_refuse(session):
    from backend.services.coffre import deposer_service, initialiser

    cle = initialiser(session, MAITRE)
    with pytest.raises(KeyError):
        deposer_service(session, cle, "banque", FAUX)


@pytest.fixture()
def client(tmp_db_path):
    from fastapi.testclient import TestClient

    from backend.main import app
    from backend.routers.coffre import verrouiller_maintenant

    verrouiller_maintenant()
    with TestClient(app) as c:
        yield c
    verrouiller_maintenant()


def test_par_l_api_coffre_ouvert_seulement(client):
    url = "/api/coffre/services/sodexo_portail"
    client.post("/api/coffre/initialiser", json={"mot_de_passe": MAITRE})
    client.post("/api/coffre/verrouiller")

    r = client.get(url).json()
    assert (r["range"], r["ouvert"], r["mot_de_passe"]) == (False, False, None)
    assert client.put(url, json={"mot_de_passe": FAUX}).status_code == 401, "coffre fermé"

    client.post("/api/coffre/ouvrir", json={"mot_de_passe": MAITRE})
    assert client.put(url, json={"mot_de_passe": ""}).status_code == 400
    r = client.put(url, json={"mot_de_passe": FAUX}).json()
    assert (r["range"], r["mot_de_passe"], r["libelle"]) == (True, FAUX, "Portail Sodexo")

    client.post("/api/coffre/verrouiller")
    r = client.get(url).json()
    assert r["range"] and r["mis_a_jour_le"] and r["mot_de_passe"] is None, "fermé : il existe, sans plus"

    assert client.get("/api/coffre/services/banque").status_code == 404

    client.post("/api/coffre/ouvrir", json={"mot_de_passe": MAITRE})
    assert not client.delete(url).json()["range"]
