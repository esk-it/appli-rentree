"""Tests du journal des opérations et de la détection d'anomalies."""
from __future__ import annotations

import json
from datetime import date, datetime, timedelta

import pytest


@pytest.fixture()
def snap_factory(session):
    from backend.models import Snapshot

    def _creer(personne_id, annee_id, **kwargs):
        defaults = {"nom": "MARTIN", "prenom": "Jean", "classe": "3B"}
        defaults.update(kwargs)
        s = Snapshot(personne_id=personne_id, annee_scolaire_id=annee_id, **defaults)
        session.add(s)
        session.commit()
        return s

    return _creer


@pytest.fixture()
def tc_factory(session):
    from backend.models import TableCorrespondance

    def _creer(site_id, code_court, groupe_google="g@lekreisker.fr"):
        tc = TableCorrespondance(
            site_id=site_id,
            classe_charlemagne_long=f"CLASSE {code_court}",
            classe_code_court=code_court,
            groupe_google=groupe_google,
            ou_pre_rentree="/3. NDK/NDK2026",
            ou_definitive=f"/3. NDK/NDK2026/{code_court}",
        )
        session.add(tc)
        session.commit()
        return tc

    return _creer


# ---------------------------------------------------------------------------
# Journal
# ---------------------------------------------------------------------------


def test_journaliser_enregistre_lopration(session):
    from backend.models import Generation
    from backend.services.journal import journaliser

    journaliser(
        session,
        type_operation="ingestion",
        cible="eleve",
        mode="reel",
        annee_libelle="2025-2026",
        parametres={"fichier": "export.htm"},
        resultat={"nb_lignes_lues": 1657},
    )
    session.commit()

    g = session.query(Generation).one()
    assert g.type_operation == "ingestion"
    assert g.parametres["fichier"] == "export.htm"
    assert g.resultat["nb_lignes_lues"] == 1657


def test_journaliser_refuse_type_inconnu(session):
    from backend.services.journal import journaliser

    with pytest.raises(ValueError, match="type_operation"):
        journaliser(session, type_operation="fantaisie")


def test_journal_ne_stocke_jamais_de_secret(session):
    """Toute clé évoquant un secret est retirée avant écriture."""
    from backend.models import Generation
    from backend.services.journal import journaliser

    journaliser(
        session,
        type_operation="export",
        cible="koxo",
        parametres={
            "site": "NDK",
            "mot_de_passe": "Sateku68",
            "csv_koxo_base64": "AAAA",
            "token": "abc",
        },
        resultat={"nb_lignes": 10, "mdp_genere": "Xyz"},
    )
    session.commit()

    g = session.query(Generation).one()
    brut = g.parametres_json + g.resultat_json
    assert "Sateku68" not in brut
    assert "AAAA" not in brut
    assert "abc" not in brut
    assert "Xyz" not in brut
    # Les clés légitimes sont conservées
    assert g.parametres["site"] == "NDK"
    assert g.resultat["nb_lignes"] == 10


def test_journal_serialise_les_valeurs_exotiques(session):
    """Une valeur non sérialisable est convertie en texte plutôt que de planter."""
    from backend.models import Generation
    from backend.services.journal import journaliser

    journaliser(
        session,
        type_operation="export",
        parametres={"quand": date(2026, 1, 1)},
    )
    session.commit()

    g = session.query(Generation).one()
    assert "2026-01-01" in g.parametres_json


def test_lister_filtre_et_ordonne(session):
    from backend.services.journal import journaliser, lister

    journaliser(session, type_operation="ingestion", cible="eleve")
    journaliser(session, type_operation="export", cible="koxo")
    journaliser(session, type_operation="export", cible="google")
    session.commit()

    tous = lister(session)
    assert len(tous) == 3

    exports = lister(session, type_operation="export")
    assert len(exports) == 2

    koxo = lister(session, type_operation="export", cible="koxo")
    assert len(koxo) == 1


# ---------------------------------------------------------------------------
# Comparaison inter-années
# ---------------------------------------------------------------------------


def test_comparaison_sans_reference(session):
    from backend.services.journal import comparer_avec_precedent

    c = comparer_avec_precedent(
        session, type_operation="export", cible="koxo",
        annee_libelle="2025-2026", resultat_courant={"nb_lignes": 100},
    )
    assert c.trouvee is False
    assert c.ecarts == []


def test_comparaison_calcule_les_ecarts(session):
    from backend.services.journal import comparer_avec_precedent, journaliser

    journaliser(
        session, type_operation="export", cible="koxo",
        annee_libelle="2024-2025", resultat={"nb_lignes": 100, "nb_sortants": 160},
    )
    session.commit()

    c = comparer_avec_precedent(
        session, type_operation="export", cible="koxo",
        annee_libelle="2025-2026",
        resultat_courant={"nb_lignes": 110, "nb_sortants": 400},
    )

    assert c.trouvee is True
    assert c.reference_annee == "2024-2025"
    par_compteur = {e.compteur: e for e in c.ecarts}
    assert par_compteur["nb_lignes"].ecart == 10
    assert par_compteur["nb_sortants"].ecart == 240


def test_comparaison_detecte_laberration(session):
    """400 sortants au lieu de 160 : le cas décrit dans le cahier des charges."""
    from backend.services.journal import comparer_avec_precedent, journaliser

    journaliser(
        session, type_operation="export", cible="koxo",
        annee_libelle="2024-2025", resultat={"nb_sortants": 160, "nb_lignes": 1000},
    )
    session.commit()

    c = comparer_avec_precedent(
        session, type_operation="export", cible="koxo",
        annee_libelle="2025-2026",
        resultat_courant={"nb_sortants": 400, "nb_lignes": 1010},
    )

    aberrants = {e.compteur for e in c.aberrations}
    assert "nb_sortants" in aberrants  # +150 %
    assert "nb_lignes" not in aberrants  # +1 %, normal


def test_comparaison_ignore_les_petits_nombres(session):
    """Passer de 2 à 4 n'est pas une aberration malgré les +100 %."""
    from backend.services.journal import comparer_avec_precedent, journaliser

    journaliser(
        session, type_operation="export", cible="koxo",
        annee_libelle="2024-2025", resultat={"nb_conflits": 2},
    )
    session.commit()

    c = comparer_avec_precedent(
        session, type_operation="export", cible="koxo",
        annee_libelle="2025-2026", resultat_courant={"nb_conflits": 4},
    )
    assert c.aberrations == []


def test_ecart_relatif_none_si_reference_nulle(session):
    from backend.services.journal import comparer_avec_precedent, journaliser

    journaliser(
        session, type_operation="export", cible="koxo",
        annee_libelle="2024-2025", resultat={"nb_erreurs": 0},
    )
    session.commit()

    c = comparer_avec_precedent(
        session, type_operation="export", cible="koxo",
        annee_libelle="2025-2026", resultat_courant={"nb_erreurs": 12},
    )
    ecart = c.ecarts[0]
    assert ecart.ecart_relatif is None
    assert ecart.est_aberrant is False  # pas de taux → pas d'alerte


# ---------------------------------------------------------------------------
# Anomalies
# ---------------------------------------------------------------------------


def test_referentiel_sain(session, site_factory, annee_factory):
    from backend.services.anomalies import detecter_anomalies

    site_factory("NDK")
    annee = annee_factory()
    r = detecter_anomalies(session, annee_id=annee.id)
    assert r.est_sain is True
    assert r.nb_bloquants == 0


def test_anomalie_classe_hors_table(
    session, site_factory, annee_factory, personne_factory, snap_factory
):
    from backend.services.anomalies import detecter_anomalies

    site = site_factory("NDK")
    annee = annee_factory()
    p = personne_factory(site_id=site.id, login="test1")
    snap_factory(p.id, annee.id, classe="XX_INCONNUE")

    r = detecter_anomalies(session, annee_id=annee.id)
    types = {a.type for a in r.anomalies}
    assert "classe_hors_table" in types
    assert r.est_sain is False

    a = next(a for a in r.anomalies if a.type == "classe_hors_table")
    assert a.gravite == "bloquant"
    assert "XX_INCONNUE" in a.details


def test_anomalie_arbitrages_en_attente(session, site_factory, annee_factory):
    from backend.services.anomalies import detecter_anomalies
    from backend.services.arbitrage import creer_ou_reprendre

    site_factory("NDK")
    annee = annee_factory()
    creer_ou_reprendre(session, type_cas="collision_login", cle_cas="k1", contexte={})
    creer_ou_reprendre(session, type_cas="homonymie_ingestion", cle_cas="k2", contexte={})
    session.commit()

    r = detecter_anomalies(session, annee_id=annee.id)
    a = next(a for a in r.anomalies if a.type == "arbitrage_en_attente")
    assert a.nb_concernes == 2
    assert a.gravite == "bloquant"


def test_anomalie_personne_sans_site(session, annee_factory, personne_factory):
    from backend.services.anomalies import detecter_anomalies

    annee = annee_factory()
    personne_factory(login="orphelin", site_id=None)

    r = detecter_anomalies(session, annee_id=annee.id)
    a = next(a for a in r.anomalies if a.type == "personne_sans_site")
    assert a.gravite == "bloquant"
    assert a.nb_concernes == 1


def test_anomalie_compte_purge_echue(session, site_factory, personne_factory):
    from backend.models import CompteCible
    from backend.services.anomalies import detecter_anomalies

    site = site_factory("NDK")
    p = personne_factory(site_id=site.id, login="sorti")
    session.add(CompteCible(
        personne_id=p.id, cible="google", etat="quarantaine",
        date_prevue_purge=date.today() - timedelta(days=1),
    ))
    session.commit()

    r = detecter_anomalies(session)
    a = next(a for a in r.anomalies if a.type == "compte_purge_echue")
    assert a.gravite == "attention"


def test_anomalie_classe_sans_groupe(session, site_factory, tc_factory):
    from backend.services.anomalies import detecter_anomalies

    site = site_factory("NDK")
    tc_factory(site.id, "3B", groupe_google=None)

    r = detecter_anomalies(session)
    a = next(a for a in r.anomalies if a.type == "classe_sans_groupe")
    assert a.gravite == "information"
    assert "3B" in a.details


def test_anomalies_triees_par_gravite(
    session, site_factory, annee_factory, personne_factory, snap_factory, tc_factory
):
    """Les bloquants remontent en tête de liste."""
    from backend.services.anomalies import detecter_anomalies
    from backend.services.arbitrage import creer_ou_reprendre

    site = site_factory("NDK")
    annee = annee_factory()
    tc_factory(site.id, "3B", groupe_google=None)  # information
    p = personne_factory(site_id=site.id, login="test1")
    snap_factory(p.id, annee.id, classe="INCONNUE")  # bloquant
    creer_ou_reprendre(session, type_cas="collision_login", cle_cas="k", contexte={})
    session.commit()

    r = detecter_anomalies(session, annee_id=annee.id)
    gravites = [a.gravite for a in r.anomalies]
    assert gravites[0] == "bloquant"
    assert gravites[-1] == "information"


def test_photos_non_verifiees_par_defaut(session, site_factory, personne_factory):
    """La vérification disque est coûteuse : désactivée sauf demande explicite."""
    from backend.services.anomalies import detecter_anomalies
    from backend.services.configuration import set_param

    site = site_factory("NDK")
    personne_factory(site_id=site.id, login="test1")
    set_param(session, "chemin_dossier_photos", "Z:/dossier/inexistant")
    session.commit()

    r = detecter_anomalies(session)
    assert not any(a.type.startswith("photo") for a in r.anomalies)


def test_photos_dossier_inaccessible_signale(session, site_factory, personne_factory):
    from backend.services.anomalies import detecter_anomalies
    from backend.services.configuration import set_param

    site = site_factory("NDK")
    personne_factory(site_id=site.id, login="test1")
    set_param(session, "chemin_dossier_photos", "Z:/dossier/inexistant")
    session.commit()

    r = detecter_anomalies(session, verifier_photos=True)
    a = next(a for a in r.anomalies if a.type == "photo_dossier_inaccessible")
    assert a.gravite == "attention"


def test_photos_orphelines_detectees(tmp_path, session, site_factory, personne_factory):
    from backend.services.anomalies import detecter_anomalies
    from backend.services.configuration import set_param

    site = site_factory("NDK")
    # Une photo présente, une absente
    (tmp_path / "PRESENT Jean.jpg").write_bytes(b"jpg")
    personne_factory(site_id=site.id, nom="PRESENT", prenom="Jean", login="p1")
    personne_factory(site_id=site.id, nom="ABSENT", prenom="Marie", login="p2")

    set_param(session, "chemin_dossier_photos", str(tmp_path))
    session.commit()

    r = detecter_anomalies(session, verifier_photos=True)
    a = next(a for a in r.anomalies if a.type == "photo_orpheline")
    assert a.nb_concernes == 1
    assert any("ABSENT Marie.jpg" in d for d in a.details)


def test_anomalies_annee_introuvable(session):
    from backend.services.anomalies import detecter_anomalies

    with pytest.raises(ValueError, match="introuvable"):
        detecter_anomalies(session, annee_id=99999)
