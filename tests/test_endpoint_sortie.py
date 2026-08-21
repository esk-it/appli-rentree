"""L'endpoint qui sort les comptes d'une branche, traversé de bout en bout.

## Pourquoi ce test existe

C'est le traitement qui déplace le plus de comptes réels d'un coup — 437
à la rentrée 2026. Il n'était pourtant traversé par aucun test : le
service était couvert, l'endpoint ne l'était pas, et il levait
`NameError` sur un import oublié. L'écran affichait « Failed to fetch »,
sans rapport avec la cause.

Google n'est jamais joint : le client est remplacé par un double qui note
ce qu'on lui demande d'envoyer.
"""
from __future__ import annotations

import pytest


class _FauxClient:
    """Double du client Google : ne sort pas du processus."""

    comptes: list[dict] = []
    envoyees: list = []
    ou: list[str] = []
    creees: list[str] = []
    creation_impossible: bool = False

    def __init__(self, config):
        self.config = config

    def lister_ou(self):
        return list(_FauxClient.ou)

    def creer_ou(self, chemin):
        if _FauxClient.creation_impossible:
            raise RuntimeError("Google refuse")
        _FauxClient.creees.append(chemin)
        _FauxClient.ou.append(chemin)

    def lister_utilisateurs(self, prefixe_ou=None):
        return [
            c for c in _FauxClient.comptes
            if not prefixe_ou or (c.get("ou") or "").startswith(prefixe_ou)
        ]

    def appliquer_operation(self, operation):
        _FauxClient.envoyees.append(operation)


def _compte(email, ou, nom="X", prenom="Y", suspendu=False):
    return {
        "email": email, "ou": ou, "suspendu": suspendu,
        "nom": nom, "prenom": prenom, "derniere_connexion": None,
    }


CIBLE = "/7. Sortis/Comptes à supprimer au 31-12-2027"


@pytest.fixture()
def client(tmp_db_path, monkeypatch):
    from fastapi.testclient import TestClient

    from backend.database import get_session
    from backend.main import app
    from backend.services.configuration import set_param

    with get_session() as s:
        set_param(s, "google.api_active", True)
        set_param(s, "google.chemin_credentials", "C:/faux/cle.json")
        set_param(s, "google.admin_impersonation", "admin@lekreisker.fr")
        s.commit()

    monkeypatch.setattr("backend.routers.google_api.ClientGoogle", _FauxClient)
    _FauxClient.envoyees = []
    _FauxClient.creees = []
    _FauxClient.creation_impossible = False
    _FauxClient.ou = ["/3. NDK", "/3. NDK/NDK2025", "/7. Sortis", CIBLE]
    _FauxClient.comptes = [
        _compte("a@lekreisker.fr", "/3. NDK/NDK2025/T_G1A"),
        _compte("b@lekreisker.fr", "/3. NDK/NDK2025/BTS_2"),
        _compte("ailleurs@lekreisker.fr", "/3. NDK/NDK2026/2_1"),
    ]
    with TestClient(app) as c:
        yield c


def test_le_plan_repond_sans_rien_envoyer(client):
    r = client.get(
        "/api/google/vidange-ou/plan",
        params={"ou": "/3. NDK/NDK2025", "ou_archivage": CIBLE},
    )
    assert r.status_code == 200, r.text
    d = r.json()

    assert d["nb_trouves"] == 2, "le compte de NDK2026 n'est pas concerné"
    assert d["nb_a_archiver"] == 2
    assert d["ou_archivage"] == CIBLE
    assert d["date_prevenance"] == "2027-12-31"
    assert d["date_echeance"] == "2028-04-30"
    assert all(m["suspendre"] is False for m in d["mouvements"])
    assert _FauxClient.envoyees == []


def test_le_deplacement_traverse_tout_le_chemin(client):
    """Le test qui manquait : c'est ici que `NameError` se serait vu."""
    r = client.post(
        "/api/google/vidange-ou",
        json={"ou": "/3. NDK/NDK2025", "ou_archivage": CIBLE, "confirmation": True},
    )
    assert r.status_code == 200, r.text
    job = r.json()
    assert job["total"] == 2

    # Le job tourne dans un fil : on attend qu'il ait fini.
    for _ in range(100):
        suivi = client.get(f"/api/google/jobs/{job['id']}").json()
        if suivi["est_termine"]:
            break
    assert suivi["est_termine"], "le job ne s'est pas terminé"
    assert suivi["nb_echecs"] == 0, suivi
    assert suivi["nb_reussies"] == 2

    assert len(_FauxClient.envoyees) == 2
    for op in _FauxClient.envoyees:
        assert op.payload == {"orgUnitPath": CIBLE}, (
            "sans suspension demandée, le corps ne porte que le déplacement"
        )


def test_la_suspension_ajoute_son_drapeau(client):
    r = client.post(
        "/api/google/vidange-ou",
        json={
            "ou": "/3. NDK/NDK2025", "ou_archivage": CIBLE,
            "suspendre": True, "confirmation": True,
        },
    )
    assert r.status_code == 200, r.text
    for _ in range(100):
        if client.get(f"/api/google/jobs/{r.json()['id']}").json()["est_termine"]:
            break

    assert all(op.payload.get("suspended") is True for op in _FauxClient.envoyees)


def test_sans_confirmation_rien_ne_part(client):
    r = client.post(
        "/api/google/vidange-ou",
        json={"ou": "/3. NDK/NDK2025", "ou_archivage": CIBLE},
    )
    assert r.status_code == 400
    assert _FauxClient.envoyees == []


def test_une_branche_vide_est_refusee_avec_un_message(client):
    r = client.post(
        "/api/google/vidange-ou",
        json={"ou": "/4. SU/SU2025", "ou_archivage": CIBLE, "confirmation": True},
    )
    assert r.status_code == 400
    assert "Aucun compte" in r.json()["detail"]
    assert _FauxClient.envoyees == []


def test_une_branche_sans_millesime_dit_pourquoi(client):
    """Sans année dans le nom, aucune échéance ne peut être déduite."""
    r = client.post(
        "/api/google/vidange-ou",
        json={"ou": "/9. Inexistante", "ou_archivage": CIBLE, "confirmation": True},
    )
    assert r.status_code == 400
    assert "année de départ" in r.json()["detail"]
    assert _FauxClient.envoyees == []


def test_les_occupants_dune_ou_de_sortie_se_lisent(client):
    _FauxClient.comptes = [
        _compte("x@lekreisker.fr", CIBLE, nom="DUPONT", prenom="Jean"),
        _compte("y@lekreisker.fr", CIBLE, nom="ALBERT", prenom="Zoé"),
    ]
    r = client.get("/api/google/sortie/occupants", params={"ou": CIBLE})
    assert r.status_code == 200, r.text
    d = r.json()

    assert d["nb"] == 2
    assert d["date_prevenance"] == "2027-12-31"
    assert d["date_suppression"] == "2028-04-30"
    assert [o["nom"] for o in d["occupants"]] == ["ALBERT", "DUPONT"], "triés"


def test_une_erreur_serveur_reste_lisible_par_le_navigateur(client, monkeypatch):
    """Une 500 sans en-tête CORS s'affiche « Failed to fetch » côté écran.

    Le message de réseau envoie alors chercher la panne là où elle n'est
    pas — c'est ce qui s'est produit sur le `NameError` de cet endpoint.
    """
    def _explose(*a, **k):
        raise RuntimeError("panne simulée")

    monkeypatch.setattr(
        "backend.routers.google_api._plan_vidange", _explose, raising=True
    )
    r = client.post(
        "/api/google/vidange-ou",
        json={"ou": "/3. NDK/NDK2025", "ou_archivage": CIBLE, "confirmation": True},
        headers={"Origin": "http://localhost:5173"},
    )

    assert r.status_code == 500
    assert "panne simulée" in r.json()["detail"], "la cause doit remonter"
    assert r.headers.get("access-control-allow-origin"), (
        "sans cet en-tête, le navigateur refuse de lire la réponse"
    )


def test_une_destination_absente_est_creee_avant_de_deplacer(client):
    """Google refuse un déplacement vers une OU inconnue, compte par compte.

    Sans ce contrôle, les 437 opérations échouaient l'une après l'autre
    pour une seule cause, et rien ne la nommait.
    """
    neuve = "/7. Sortis/Comptes à supprimer au 31-12-2026"
    r = client.post(
        "/api/google/vidange-ou",
        json={"ou": "/3. NDK/NDK2025", "ou_archivage": neuve, "confirmation": True},
    )
    assert r.status_code == 200, r.text
    assert _FauxClient.creees == [neuve]

    for _ in range(100):
        if client.get(f"/api/google/jobs/{r.json()['id']}").json()["est_termine"]:
            break
    assert all(op.payload["orgUnitPath"] == neuve for op in _FauxClient.envoyees)


def test_on_peut_refuser_la_creation_et_le_message_est_clair(client):
    r = client.post(
        "/api/google/vidange-ou",
        json={
            "ou": "/3. NDK/NDK2025",
            "ou_archivage": "/7. Sortis/Comptes à supprimer au 31-12-2026",
            "creer_destination": False, "confirmation": True,
        },
    )
    assert r.status_code == 400
    assert "absente de Google" in r.json()["detail"]
    assert _FauxClient.envoyees == [], "rien ne part quand la destination manque"


def test_une_creation_refusee_narrete_rien_a_moitie(client):
    """Mieux vaut ne rien déplacer que déplacer vers un dossier incertain."""
    _FauxClient.creation_impossible = True
    r = client.post(
        "/api/google/vidange-ou",
        json={
            "ou": "/3. NDK/NDK2025",
            "ou_archivage": "/7. Sortis/Comptes à supprimer au 31-12-2026",
            "confirmation": True,
        },
    )
    assert r.status_code == 502
    assert "Rien n'a été déplacé" in r.json()["detail"]
    assert _FauxClient.envoyees == []


def test_les_destinations_portent_leur_etat(client):
    """La liste déroulante doit dire ce qui est dû et ce qui ne l'est pas."""
    _FauxClient.ou = [
        "/7. Sortis",
        "/7. Sortis/Comptes à supprimer au 31-12-2027",
        "/7. Sortis/Profs sortis",
    ]
    r = client.get("/api/google/sortie/destinations",
                   params={"pour_ou": "/3. NDK/NDK2025"})
    assert r.status_code == 200, r.text
    d = r.json()

    par_chemin = {x["chemin"]: x for x in d["destinations"]}
    suggeree = "/7. Sortis/Comptes à supprimer au 31-12-2026"
    assert par_chemin[suggeree]["suggeree"] is True, "règle du 31 décembre"
    assert par_chemin[suggeree]["existe"] is False
    assert par_chemin[suggeree]["date_suppression"] == "2027-04-30"
    assert par_chemin["/7. Sortis/Profs sortis"]["etat"] == "sans_date"
    assert any("n'existe pas encore" in a for a in d["avertissements"])
