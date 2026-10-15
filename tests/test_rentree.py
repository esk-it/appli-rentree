"""La rentrée guidée : un tutoriel qui ne laisse passer que ce qui est constaté.

Demandé par Johann le 15 octobre 2026 : qu'une personne qui n'a jamais fait
de rentrée la réussisse en suivant les écrans — chaque étape avec son
avant / après, validée sur ce qui a réellement été fait.
"""
from __future__ import annotations

from datetime import date

import pytest

LIB = "2027-2028"
EN_AOUT = date(2027, 8, 20)


def _ctx(session, **kw):
    from backend.services.rentree import contexte

    return contexte(session, LIB, **kw)


def _valider_jusqu_a(session, etape_id, libelle=LIB):
    """Valide de force toutes les étapes qui précèdent `etape_id`."""
    from backend.services.rentree import ETAPES, contexte, valider

    for e in ETAPES:
        if e.id == etape_id:
            return
        valider(session, contexte(session, libelle), e.id, forcer=True, note="essai")


def _photographier(session, annee, personne):
    from backend.models import Snapshot

    session.add(Snapshot(personne_id=personne.id, annee_scolaire_id=annee.id,
                         nom=personne.nom, prenom=personne.prenom, classe=personne.classe))
    session.commit()


# ---------------------------------------------------------------------------
# Le catalogue
# ---------------------------------------------------------------------------


def test_six_chapitres_dix_huit_etapes_et_des_mesures_qui_existent():
    from backend.services.rentree import CHAPITRES, ETAPES, MESURES

    assert len(CHAPITRES) == 6 and len(ETAPES) == 18
    assert len({e.id for e in ETAPES}) == 18
    chapitres = [c.id for c in CHAPITRES]
    assert [e.chapitre for e in ETAPES] == sorted(
        (e.chapitre for e in ETAPES), key=chapitres.index
    ), "les étapes suivent l'ordre des chapitres"
    assert all(m in MESURES for e in ETAPES for m in e.mesures)


# ---------------------------------------------------------------------------
# L'ordre
# ---------------------------------------------------------------------------


def test_une_campagne_neuve_n_ouvre_que_la_premiere_etape(session):
    from backend.services.rentree import etat

    e = etat(session, annee=LIB)
    assert e.courante == "mise_en_place" and e.annee_id is None
    assert [x.statut for x in e.etapes[:3]] == ["a_faire", "fermee", "fermee"]


def test_une_etape_fermee_refuse_de_s_ouvrir_et_dit_laquelle_attendre(session):
    from backend.services.rentree import RentreeImpossible, ouvrir

    with pytest.raises(RentreeImpossible, match="Vérifier la mise en place"):
        ouvrir(session, _ctx(session), "eleves")


def test_une_etape_reportable_laisse_passer_la_suite(session):
    from backend.services.rentree import RentreeImpossible, etat, reporter

    _valider_jusqu_a(session, "professeurs")
    reporter(session, LIB, "professeurs", note="avant le 1er septembre")
    e = etat(session, annee=LIB)
    assert e.courante == "koxo"
    assert next(x for x in e.etapes if x.id == "professeurs").statut == "reportee"
    with pytest.raises(RentreeImpossible, match="ne se reporte pas"):
        reporter(session, LIB, "koxo")


def test_rouvrir_une_etape_y_ramene(session):
    from backend.services.rentree import etat, rouvrir

    _valider_jusqu_a(session, "departager")
    rouvrir(session, LIB, "annee")
    e = etat(session, annee=LIB)
    assert e.courante == "annee"
    assert next(x for x in e.etapes if x.id == "eleves").statut == "validee"


def test_deux_rentrees_ne_se_melent_pas(session):
    from backend.services.rentree import etat

    _valider_jusqu_a(session, "eleves")
    assert etat(session, annee="2028-2029").courante == "mise_en_place"
    assert etat(session, annee=LIB).courante == "eleves"


# ---------------------------------------------------------------------------
# Valider sur ce qui est constaté
# ---------------------------------------------------------------------------


def test_une_mesure_bloquante_refuse_la_validation_et_dit_pourquoi(session):
    from backend.services.rentree import RentreeImpossible, valider

    with pytest.raises(RentreeImpossible, match="Réglages qui manquent"):
        valider(session, _ctx(session), "mise_en_place")
    with pytest.raises(RentreeImpossible, match="la raison"):
        valider(session, _ctx(session), "mise_en_place", forcer=True)
    e = valider(session, _ctx(session), "mise_en_place", forcer=True,
                note="Google se règle plus tard")
    assert e.statut == "validee" and e.note == "Google se règle plus tard"


def test_l_avant_est_pris_a_l_ouverture_et_l_apres_a_la_validation(session):
    from backend.models import Arbitrage
    from backend.services.rentree import etat, ouvrir, valider

    _valider_jusqu_a(session, "departager")
    cas = Arbitrage(type_cas="homonyme", cle_cas="a", contexte_json="{}")
    session.add(cas)
    session.commit()

    (m,) = ouvrir(session, _ctx(session), "departager")
    assert (m.valeur, m.bonne) == (1, False)
    cas.decision = "deux personnes"
    session.commit()
    ouvrir(session, _ctx(session), "departager")  # l'avant ne bouge plus
    valider(session, _ctx(session), "departager")

    x = next(e for e in etat(session, annee=LIB).etapes if e.id == "departager")
    assert x.avant["arbitrages_en_attente"]["valeur"] == 1
    assert x.apres["arbitrages_en_attente"]["valeur"] == 0
    assert x.validee_le


def test_avant_l_ingestion_les_eleves_ne_se_comptent_pas(session, annee_factory, personne_factory):
    """L'année n'existe qu'une fois l'export ingéré : les mesures le disent."""
    from backend.services.rentree import ouvrir

    _valider_jusqu_a(session, "eleves")
    inscrits, classes = ouvrir(session, _ctx(session), "eleves")
    assert (inscrits.valeur, inscrits.bonne) == (0, False)
    assert "pas encore ingéré" in inscrits.detail and classes.valeur is None

    annee = annee_factory(LIB)
    _photographier(session, annee, personne_factory(type="eleve", nom="ROUE", prenom="Léa"))
    inscrits, _ = ouvrir(session, _ctx(session), "eleves")
    assert (inscrits.valeur, inscrits.bonne) == (1, True)


def test_une_mesure_google_non_lue_n_est_pas_une_mesure_bonne(session, annee_factory):
    from backend.services.rentree import RentreeImpossible, valider

    annee_factory(LIB)
    _valider_jusqu_a(session, "comptes_google")
    with pytest.raises(RentreeImpossible, match="Relire dans Google"):
        valider(session, _ctx(session), "comptes_google")


def test_les_comptes_google_se_constatent_dans_l_annuaire(
    session, annee_factory, site_factory, personne_factory
):
    from backend.services.rentree import ouvrir

    annee = annee_factory(LIB)
    ndk = site_factory("NDK")
    lea = personne_factory(type="eleve", nom="ROUE", prenom="Léa", site_id=ndk.id, classe="2_1")
    _photographier(session, annee, lea)
    _valider_jusqu_a(session, "comptes_google")

    vide = ouvrir(session, _ctx(session, comptes_google=[]), "comptes_google")
    assert vide[0].valeur == 1 and vide[0].bloquante
    compte = {"email": "lea.roue@lekreisker.fr", "alias": [], "ou": "/NDK", "nom": "ROUE",
              "prenom": "Léa", "id_externe": None}
    plein = ouvrir(session, _ctx(session, comptes_google=[compte]), "comptes_google")
    assert plein[0].valeur == 0 and plein[0].bonne


def test_les_gestes_hors_du_programme_se_declarent(session):
    from backend.services.rentree import declarer_geste, etat

    _valider_jusqu_a(session, "koxo")
    assert declarer_geste(session, LIB, "koxo", "importer_ndk") == ["importer_ndk"]
    assert declarer_geste(session, LIB, "koxo", "importer_ndk", fait=False) == []
    declarer_geste(session, LIB, "koxo", "importer_su")
    assert next(e for e in etat(session, annee=LIB).etapes if e.id == "koxo").gestes == [
        "importer_su"
    ]


# ---------------------------------------------------------------------------
# Quelle rentrée, et à partir de quand
# ---------------------------------------------------------------------------


def test_commencer_ne_cree_pas_l_annee(session):
    """Une année vide ferait viser tous les autres écrans sur elle tout l'été."""
    from backend.models import AnneeScolaire
    from backend.services.rentree import commencer, etat

    commencer(session, LIB, aujourd_hui=EN_AOUT)
    assert session.query(AnneeScolaire).count() == 0
    assert etat(session, annee=LIB).etapes[0].statut == "en_cours"


def test_une_rentree_ne_se_commence_pas_avant_juillet(session):
    from backend.services.rentree import RentreeImpossible, commencer

    with pytest.raises(RentreeImpossible, match="01/07/2027"):
        commencer(session, LIB, aujourd_hui=date(2026, 10, 15))
    assert commencer(session, LIB, aujourd_hui=date(2027, 7, 1)) == LIB


def test_une_rentree_passee_ne_se_commence_pas(session, annee_factory, personne_factory):
    from backend.services.rentree import RentreeImpossible, commencer

    _photographier(session, annee_factory("2027-2028"), personne_factory(type="eleve"))
    with pytest.raises(RentreeImpossible, match="est passée"):
        commencer(session, "2026-2027", aujourd_hui=EN_AOUT)


def test_un_libelle_d_annee_bancal_est_refuse(session):
    from backend.services.rentree import RentreeImpossible, commencer

    for faux in ("2027", "2027-2029", "deux mille"):
        with pytest.raises(RentreeImpossible):
            commencer(session, faux, aujourd_hui=EN_AOUT)


def test_l_annee_a_preparer(session, annee_factory, personne_factory):
    from backend.services.rentree import ETAPES, annee_a_preparer, commencer, reporter

    passee = annee_factory("2026-2027")
    assert annee_a_preparer(session) == ("2026-2027", False), "créée, rien d'ingéré"
    _photographier(session, passee, personne_factory(type="eleve"))
    assert annee_a_preparer(session) == (LIB, False), "faite avant l'assistant"

    commencer(session, LIB, aujourd_hui=EN_AOUT)
    assert annee_a_preparer(session) == (LIB, True)
    _valider_jusqu_a(session, ETAPES[-1].id)
    assert annee_a_preparer(session) == (LIB, True), "le bilan reste à valider"
    _valider_jusqu_a(session, "__fin__")
    assert annee_a_preparer(session) == ("2028-2029", False), "finie : la suivante"


def test_une_campagne_abandonnee_ne_retient_pas_les_annees_suivantes(
    session, annee_factory, personne_factory
):
    from backend.services.rentree import annee_a_preparer, commencer

    commencer(session, LIB, aujourd_hui=EN_AOUT)
    _photographier(session, annee_factory("2028-2029"), personne_factory(type="eleve"))
    assert annee_a_preparer(session) == ("2029-2030", False)


# ---------------------------------------------------------------------------
# Les points d'entrée
# ---------------------------------------------------------------------------


@pytest.fixture()
def client(tmp_db_path):
    from fastapi.testclient import TestClient

    from backend.main import app

    with TestClient(app) as c:
        yield c


def test_le_parcours_par_l_api(client):
    e = client.get("/api/rentree/etat").json()
    assert not e["commencee"] and not e["trop_tot"], "la rentrée de l'année en cours est ouverte"
    lib = e["annee"]

    e = client.post("/api/rentree/commencer", json={"libelle": lib}).json()
    assert (e["annee"], e["courante"], e["commencee"]) == (lib, "mise_en_place", True)

    r = client.post("/api/rentree/etapes/eleves/ouvrir", json={"annee": lib})
    assert r.status_code == 409

    o = client.post("/api/rentree/etapes/mise_en_place/ouvrir", json={"annee": lib}).json()
    assert o["mesures"][0]["id"] == "reglages_manquants" and o["etape"]["statut"] == "en_cours"
    r = client.post("/api/rentree/etapes/mise_en_place/valider", json={"annee": lib})
    assert r.status_code == 409 and "Réglages qui manquent" in r.json()["detail"]
    e = client.post("/api/rentree/etapes/mise_en_place/valider",
                    json={"annee": lib, "forcer": True, "note": "essai"}).json()
    assert e["courante"] == "annee" and e["nb_validees"] == 1


def test_une_rentree_lointaine_est_trop_tot(client):
    e = client.get("/api/rentree/etat", params={"annee": "2099-2100"}).json()
    assert e["trop_tot"] and e["s_ouvre_le"] == "2099-07-01"
    r = client.post("/api/rentree/commencer", json={"libelle": "2099-2100"})
    assert r.status_code == 400 and "01/07/2099" in r.json()["detail"]
