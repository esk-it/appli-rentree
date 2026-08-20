"""Tests de la rotation annuelle des OU."""
from __future__ import annotations

import pytest


@pytest.fixture()
def client(tmp_db_path):
    from fastapi.testclient import TestClient

    from backend.main import app

    with TestClient(app) as c:
        yield c


@pytest.fixture()
def table(session, site_factory):
    """Trois classes visant l'arbre 2026, comme la table réelle."""
    from backend.models import TableCorrespondance

    ndk = site_factory("NDK")
    su = site_factory("SU")
    session.add_all([
        TableCorrespondance(
            site_id=ndk.id, classe_charlemagne_long="SECONDE 1", classe_code_court="2_1",
            ou_pre_rentree="/3. NDK/NDK2026", ou_definitive="/3. NDK/NDK2026/2_1",
            groupe_google="2nde-1@lekreisker.fr",
        ),
        TableCorrespondance(
            site_id=ndk.id, classe_charlemagne_long="TERMINALE G1A", classe_code_court="T_G1A",
            ou_pre_rentree="/3. NDK/NDK2026", ou_definitive="/3. NDK/NDK2026/T_G1A",
        ),
        TableCorrespondance(
            site_id=su.id, classe_charlemagne_long="SIXIEME 1", classe_code_court="61",
            ou_pre_rentree="/4. SU/SU2026", ou_definitive="/4. SU/SU2026/61",
        ),
    ])
    session.commit()
    return {"ndk": ndk, "su": su}


def test_simulation_ne_touche_rien(session, table):
    from backend.models import TableCorrespondance
    from backend.services.rotation_ou import renommer_dans_les_ou

    r = renommer_dans_les_ou(session, chercher="2026", remplacer="2027")
    assert r.nb_lignes_modifiees == 3
    assert r.mode == "simulation"

    inchange = session.query(TableCorrespondance).filter_by(classe_code_court="2_1").one()
    assert inchange.ou_definitive == "/3. NDK/NDK2026/2_1"


def test_mode_reel_applique_les_deux_colonnes(session, table):
    from backend.models import TableCorrespondance
    from backend.services.rotation_ou import renommer_dans_les_ou

    r = renommer_dans_les_ou(session, chercher="2026", remplacer="2027", mode="reel")
    assert r.nb_lignes_modifiees == 3

    tc = session.query(TableCorrespondance).filter_by(classe_code_court="2_1").one()
    assert tc.ou_pre_rentree == "/3. NDK/NDK2027"
    assert tc.ou_definitive == "/3. NDK/NDK2027/2_1"


def test_les_groupes_ne_bougent_pas(session, table):
    """Les adresses de groupe ne portent pas d'année : y toucher les casserait."""
    from backend.models import TableCorrespondance
    from backend.services.rotation_ou import renommer_dans_les_ou

    renommer_dans_les_ou(session, chercher="2026", remplacer="2027", mode="reel")
    tc = session.query(TableCorrespondance).filter_by(classe_code_court="2_1").one()
    assert tc.groupe_google == "2nde-1@lekreisker.fr"


def test_tous_les_sites_sont_traites(session, table):
    from backend.services.rotation_ou import renommer_dans_les_ou

    r = renommer_dans_les_ou(session, chercher="2026", remplacer="2027", mode="reel")
    prefixes = {l.apres_pre_rentree for l in r.lignes}
    assert prefixes == {"/3. NDK/NDK2027", "/4. SU/SU2027"}


def test_filtre_par_site(session, table):
    from backend.services.rotation_ou import renommer_dans_les_ou

    r = renommer_dans_les_ou(
        session, chercher="2026", remplacer="2027", site_id=table["su"].id, mode="reel"
    )
    assert r.nb_lignes_modifiees == 1
    assert r.lignes[0].site == "SU"


def test_ligne_epargnee_est_signalee(session, table, site_factory):
    """Une classe oubliée enverrait toute sa cohorte dans l'arbre précédent."""
    from backend.models import TableCorrespondance
    from backend.services.rotation_ou import renommer_dans_les_ou

    session.add(
        TableCorrespondance(
            site_id=table["ndk"].id, classe_charlemagne_long="A PART",
            classe_code_court="APART",
            ou_pre_rentree="/3. NDK/Divers", ou_definitive="/3. NDK/Divers/APART",
        )
    )
    session.commit()

    r = renommer_dans_les_ou(session, chercher="2026", remplacer="2027")
    assert r.nb_lignes_modifiees == 3
    assert r.nb_inchangees == 1
    assert len(r.avertissements) == 1
    assert "arbre précédent" in r.avertissements[0]


def test_aucun_avertissement_quand_tout_bascule(session, table):
    from backend.services.rotation_ou import renommer_dans_les_ou

    r = renommer_dans_les_ou(session, chercher="2026", remplacer="2027")
    assert r.nb_inchangees == 0
    assert r.avertissements == []


def test_fragment_vide_refuse(session, table):
    from backend.services.rotation_ou import renommer_dans_les_ou

    with pytest.raises(ValueError, match="vide"):
        renommer_dans_les_ou(session, chercher="", remplacer="2027")


def test_remplacement_identique_refuse(session, table):
    from backend.services.rotation_ou import renommer_dans_les_ou

    with pytest.raises(ValueError, match="identiques"):
        renommer_dans_les_ou(session, chercher="2026", remplacer="2026")


def test_api_simulation_puis_reel(client, session, table):
    r = client.post(
        "/api/table-correspondance/rotation-ou",
        json={"chercher": "2026", "remplacer": "2027"},
    )
    assert r.status_code == 200
    corps = r.json()
    assert corps["nb_lignes_modifiees"] == 3
    assert corps["lignes"][0]["apres_definitive"].count("2027") == 1

    r2 = client.post(
        "/api/table-correspondance/rotation-ou",
        json={"chercher": "2026", "remplacer": "2027", "mode": "reel"},
    )
    assert r2.json()["nb_lignes_modifiees"] == 3

    # Rejouer ne trouve plus rien : l'opération n'est pas cumulative
    r3 = client.post(
        "/api/table-correspondance/rotation-ou",
        json={"chercher": "2026", "remplacer": "2027", "mode": "reel"},
    )
    assert r3.json()["nb_lignes_modifiees"] == 0


def test_api_refuse_un_fragment_vide(client, table):
    r = client.post(
        "/api/table-correspondance/rotation-ou",
        json={"chercher": "", "remplacer": "2027"},
    )
    assert r.status_code == 422
