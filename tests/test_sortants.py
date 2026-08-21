"""Tests du suivi des sortants et de leur confrontation à Google."""
from __future__ import annotations

from datetime import date, timedelta

import pytest


@pytest.fixture()
def client(tmp_db_path):
    from fastapi.testclient import TestClient

    from backend.main import app

    with TestClient(app) as c:
        yield c


@pytest.fixture()
def sorti(session, site_factory, personne_factory):
    """Une élève partie, son compte Google en quarantaine."""
    from backend.models import CompteCible

    site = site_factory("NDK")
    p = personne_factory(
        nom="TERMINALE", prenom="Luc", login="lterminale", site_id=site.id,
        classe="T_G1A", email_constate="luc.terminale@lekreisker.fr",
    )
    session.add(
        CompteCible(
            personne_id=p.id, cible="google", etat="quarantaine",
            identifiant_externe="luc.terminale@lekreisker.fr",
            date_prevue_purge=date.today() + timedelta(days=300),
        )
    )
    session.commit()
    return {"site": site, "personne": p}


# ---------------------------------------------------------------------------
# Liste
# ---------------------------------------------------------------------------


def test_liste_les_comptes_en_sortie(session, sorti):
    from backend.services.sortants import NON_VERIFIE, lister_sortants

    r = lister_sortants(session)
    assert r.nb_total == 1
    s = r.sortants[0]
    assert s.nom == "TERMINALE"
    assert s.email == "luc.terminale@lekreisker.fr"
    assert s.etat == "quarantaine"
    assert s.verification == NON_VERIFIE
    assert s.echeance_depassee is False
    assert s.ou_attendue.startswith("/7. Sortis")


def test_un_compte_actif_nest_pas_un_sortant(session, site_factory, personne_factory):
    from backend.models import CompteCible
    from backend.services.sortants import lister_sortants

    site = site_factory("NDK")
    p = personne_factory(nom="ICI", prenom="Ana", login="aici", site_id=site.id)
    session.add(CompteCible(personne_id=p.id, cible="google", etat="actif"))
    session.commit()

    assert lister_sortants(session).nb_total == 0


def test_filtre_sur_les_echeances_depassees(
    session, site_factory, personne_factory
):
    from backend.models import CompteCible
    from backend.services.sortants import lister_sortants

    site = site_factory("NDK")
    tard = personne_factory(nom="TARD", prenom="A", login="atard", site_id=site.id)
    tot = personne_factory(nom="ECHU", prenom="B", login="bechu", site_id=site.id)
    session.add_all([
        CompteCible(personne_id=tard.id, cible="google", etat="quarantaine",
                    date_prevue_purge=date.today() + timedelta(days=100)),
        CompteCible(personne_id=tot.id, cible="google", etat="quarantaine",
                    date_prevue_purge=date.today() - timedelta(days=1)),
    ])
    session.commit()

    tous = lister_sortants(session)
    assert tous.nb_total == 2
    assert tous.nb_echeance_depassee == 1
    # Les échéances les plus proches en tête : c'est ce qu'on traite d'abord
    assert tous.sortants[0].nom == "ECHU"

    echus = lister_sortants(session, seulement_echus=True)
    assert [s.nom for s in echus.sortants] == ["ECHU"]


# ---------------------------------------------------------------------------
# Confrontation à Google
# ---------------------------------------------------------------------------


def _sortant(ou_attendue="/7. Sortis/Comptes à supprimer au 31-12-2027"):
    from backend.services.sortants import Sortant

    return Sortant(
        personne_id=1, cle_pivot="E1", nom="X", prenom="Y",
        email="x@lekreisker.fr", site="NDK", derniere_classe="T_G1A",
        etat="quarantaine", date_prevue_purge=date.today(),
        ou_attendue=ou_attendue,
    )


def test_compte_bien_archive_est_conforme():
    from backend.services.sortants import CONFORME, ConstatGoogle, comparer_au_constat

    s = _sortant()
    comparer_au_constat(
        s,
        ConstatGoogle(existe=True, ou="/7. Sortis/Comptes à supprimer au 31-12-2027",
                      suspendu=True),
    )
    assert s.verification == CONFORME
    assert s.detail_verification is None


def test_annee_decheance_differente_reste_conforme():
    """Un sortant d'une campagne passée est dans un autre sous-dossier.

    Exiger l'égalité stricte signalerait à tort tous les anciens.
    """
    from backend.services.sortants import CONFORME, ConstatGoogle, comparer_au_constat

    s = _sortant()
    comparer_au_constat(
        s,
        ConstatGoogle(existe=True, ou="/7. Sortis/Comptes à supprimer au 31-12-2026",
                      suspendu=True),
    )
    assert s.verification == CONFORME


def test_compte_reste_dans_sa_classe_est_un_ecart():
    from backend.services.sortants import ECART, ConstatGoogle, comparer_au_constat

    s = _sortant()
    comparer_au_constat(
        s, ConstatGoogle(existe=True, ou="/3. NDK/NDK2026/T_G1A", suspendu=True)
    )
    assert s.verification == ECART
    assert "encore dans /3. NDK" in s.detail_verification


def test_un_sortant_range_et_toujours_actif_est_conforme():
    """C'est l'état voulu : la quarantaine tient à l'OU, pas à la suspension.

    La première version exigeait la suspension et signalait donc en écart
    des comptes parfaitement conformes — quatre d'un coup sur l'instance.
    """
    from backend.services.sortants import CONFORME, ConstatGoogle, comparer_au_constat

    s = _sortant()
    comparer_au_constat(
        s,
        ConstatGoogle(existe=True, ou="/7. Sortis/Comptes à supprimer au 31-12-2027",
                      suspendu=False),
    )
    assert s.verification == CONFORME
    assert s.detail_verification is None
    assert s.suspendu_reellement is False, "l'information reste, sans être un grief"


def test_un_sortant_suspendu_reste_conforme_lui_aussi():
    """Suspendre n'est pas fautif — c'est simplement une décision à part."""
    from backend.services.sortants import CONFORME, ConstatGoogle, comparer_au_constat

    s = _sortant()
    comparer_au_constat(
        s,
        ConstatGoogle(existe=True, ou="/7. Sortis/Comptes à supprimer au 31-12-2027",
                      suspendu=True),
    )
    assert s.verification == CONFORME


def test_le_seul_ecart_est_de_ne_pas_etre_range():
    from backend.services.sortants import ECART, ConstatGoogle, comparer_au_constat

    s = _sortant()
    comparer_au_constat(
        s, ConstatGoogle(existe=True, ou="/3. NDK/NDK2026/T_G1A", suspendu=False)
    )
    assert s.verification == ECART
    assert s.detail_verification == "encore dans /3. NDK/NDK2026/T_G1A"


def test_compte_absent_de_google():
    from backend.services.sortants import INTROUVABLE, ConstatGoogle, comparer_au_constat

    s = _sortant()
    comparer_au_constat(s, ConstatGoogle(existe=False))
    assert s.verification == INTROUVABLE
    assert "déjà supprimé" in s.detail_verification


def test_erreur_dappel_est_un_ecart_pas_une_conformite():
    """Dans le doute, ne jamais conclure que tout va bien."""
    from backend.services.sortants import ECART, ConstatGoogle, comparer_au_constat

    s = _sortant()
    comparer_au_constat(s, ConstatGoogle(existe=False, erreur="HttpError 503"))
    assert s.verification == ECART
    assert "503" in s.detail_verification


def test_comptage_des_ecarts(session, sorti):
    from backend.services.sortants import (
        ConstatGoogle,
        comparer_au_constat,
        lister_sortants,
    )

    r = lister_sortants(session)
    comparer_au_constat(
        r.sortants[0], ConstatGoogle(existe=True, ou="/3. NDK/NDK2026", suspendu=False)
    )
    assert r.nb_ecarts == 1
    assert r.nb_conformes == 0


# ---------------------------------------------------------------------------
# API
# ---------------------------------------------------------------------------


def test_api_liste(client, session, sorti):
    r = client.get("/api/sortants")
    assert r.status_code == 200
    corps = r.json()
    assert corps["nb_total"] == 1
    assert corps["sortants"][0]["email"] == "luc.terminale@lekreisker.fr"
    assert corps["sortants"][0]["verification"] == "non_verifie"


def test_api_verification_sans_configuration(client, session, sorti):
    """Sans credentials, on refuse proprement plutôt que de planter."""
    r = client.post("/api/sortants/verifier")
    assert r.status_code == 400
    assert "API" in r.json()["detail"] or "désactivé" in r.json()["detail"]


def test_api_verification_sans_sortant(client, session):
    r = client.post("/api/sortants/verifier")
    assert r.status_code == 400
    assert "Aucun sortant" in r.json()["detail"]


def test_le_constat_survit_au_rafraichissement(
    session, personne_factory
):
    """Une vérification de plusieurs minutes ne doit pas s'effacer d'un clic.

    Le rapport des sortants est reconstruit à chaque appel : sans trace en
    base, chaque ligne réaffichait « non vérifié » alors que le bandeau
    annonçait des écarts.
    """
    from datetime import date

    from backend.models import CompteCible
    from backend.services.sortants import (
        CONFORME,
        ConstatGoogle,
        comparer_au_constat,
        lister_sortants,
        memoriser_constat,
    )

    p = personne_factory(nom="LE LAY", prenom="Leane", login="llelay")
    session.add(
        CompteCible(
            personne_id=p.id, cible="google", etat="quarantaine",
            date_prevue_purge=date(2027, 4, 30),
            identifiant_externe="leane.le.lay@lekreisker.fr",
        )
    )
    session.commit()

    avant = lister_sortants(session)
    assert avant.sortants[0].verification == "non_verifie"

    sortant = avant.sortants[0]
    comparer_au_constat(
        sortant,
        ConstatGoogle(existe=True, ou="/7. Sortis/Comptes à supprimer au 31-12-2026",
                      suspendu=False),
    )
    assert sortant.verification == CONFORME
    memoriser_constat(session, sortant)
    session.commit()

    apres = lister_sortants(session)
    assert apres.sortants[0].verification == CONFORME
    assert apres.sortants[0].ou_reelle.endswith("31-12-2026")
    assert apres.sortants[0].verifie_le == date.today()
    assert apres.nb_conformes == 1
