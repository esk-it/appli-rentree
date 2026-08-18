"""Tests des exports KoXo (Tous / Nouveaux / Anciens).

Vérifie le format CSV (colonnes officielles, encodage cp1252, MDP vide) et
la logique métier de chaque catégorie via snapshots + réconciliation.
"""
from __future__ import annotations

import csv
import io

import pytest


@pytest.fixture()
def snap_factory(session):
    """Crée un Snapshot minimal."""
    from backend.models import Snapshot

    def _creer(personne_id, annee_id, **kwargs):
        defaults = {"nom": "MARTIN", "prenom": "Jean", "classe": "3B"}
        defaults.update(kwargs)
        s = Snapshot(personne_id=personne_id, annee_scolaire_id=annee_id, **defaults)
        session.add(s)
        session.commit()
        return s

    return _creer


def _lire_csv_koxo(contenu: bytes) -> list[dict]:
    """Décode un CSV KoXo (cp1252) et retourne la liste des rows."""
    texte = contenu.decode("cp1252")
    reader = csv.DictReader(io.StringIO(texte))
    return list(reader)


# ---------------------------------------------------------------------------
# Format
# ---------------------------------------------------------------------------


def test_export_a_les_colonnes_officielles_koxo(session, site_factory, annee_factory, personne_factory, snap_factory):
    from backend.services.exports_koxo import COLONNES_KOXO, generer_csv_koxo

    site = site_factory("NDK")
    annee = annee_factory("2025-2026")
    p = personne_factory(site_id=site.id, nom="DUPONT", prenom="Jean", login="jdupont")
    snap_factory(p.id, annee.id)

    contenu, _ = generer_csv_koxo(
        session=session, site_id=site.id, type_personne="eleve",
        categorie="tous", annee_cible_id=annee.id,
    )
    rows = _lire_csv_koxo(contenu)

    assert len(rows) == 1
    assert list(rows[0].keys()) == COLONNES_KOXO


def test_export_mdp_toujours_vide(session, site_factory, annee_factory, personne_factory, snap_factory):
    """Principe : KoXo est l'autorité qui génère les MDP, pas nous."""
    from backend.services.exports_koxo import generer_csv_koxo

    site = site_factory("NDK")
    annee = annee_factory()
    p = personne_factory(site_id=site.id, login="test1")
    snap_factory(p.id, annee.id)

    contenu, _ = generer_csv_koxo(
        session=session, site_id=site.id, type_personne="eleve",
        categorie="tous", annee_cible_id=annee.id,
    )
    rows = _lire_csv_koxo(contenu)

    for r in rows:
        assert r["Mot de passe"] == ""


def test_export_encodage_cp1252(session, site_factory, annee_factory, personne_factory, snap_factory):
    """Les caractères accentués doivent être encodés en cp1252 (attendu par KoXo)."""
    from backend.services.exports_koxo import generer_csv_koxo

    site = site_factory("NDK")
    annee = annee_factory()
    p = personne_factory(site_id=site.id, nom="LEGOFF", prenom="Hélène", login="hlegoff")
    snap_factory(p.id, annee.id)

    contenu, _ = generer_csv_koxo(
        session=session, site_id=site.id, type_personne="eleve",
        categorie="tous", annee_cible_id=annee.id,
    )
    # Doit se décoder proprement en cp1252
    texte = contenu.decode("cp1252")
    assert "Hélène" in texte


def test_export_email_calcule_depuis_nom_prenom_et_domaine(session, site_factory, annee_factory, personne_factory, snap_factory):
    from backend.services.exports_koxo import generer_csv_koxo

    site = site_factory("NDK")  # domaine lekreisker.fr par défaut
    annee = annee_factory()
    p = personne_factory(site_id=site.id, nom="DUPONT", prenom="Jean", login="jdupont")
    snap_factory(p.id, annee.id)

    contenu, _ = generer_csv_koxo(
        session=session, site_id=site.id, type_personne="eleve",
        categorie="tous", annee_cible_id=annee.id,
    )
    rows = _lire_csv_koxo(contenu)
    # Le login reste `jdupont`, l'adresse est `jean.dupont` : deux règles distinctes
    assert rows[0]["Identifiant"] == "jdupont"
    assert rows[0]["Email"] == "jean.dupont@lekreisker.fr"


def test_export_groupe_primaire_eleve_vs_adulte(session, site_factory, annee_factory, personne_factory, snap_factory):
    from backend.services.exports_koxo import generer_csv_koxo

    site = site_factory("NDK")
    annee = annee_factory()
    p_eleve = personne_factory(type="eleve", site_id=site.id, login="e1")
    p_adulte = personne_factory(type="adulte", site_id=site.id, login="a1")
    snap_factory(p_eleve.id, annee.id, classe="3B")
    snap_factory(p_adulte.id, annee.id, poste_occupe="ENSEIGNEMENT", matieres="MATHEMATIQUES")

    c_e, _ = generer_csv_koxo(session=session, site_id=site.id, type_personne="eleve",
                              categorie="tous", annee_cible_id=annee.id)
    c_a, _ = generer_csv_koxo(session=session, site_id=site.id, type_personne="adulte",
                              categorie="tous", annee_cible_id=annee.id)

    assert _lire_csv_koxo(c_e)[0]["Groupe primaire"] == "Elèves"
    assert _lire_csv_koxo(c_a)[0]["Groupe primaire"] == "Professeurs"


def test_export_groupe_secondaire_eleve_est_classe(session, site_factory, annee_factory, personne_factory, snap_factory):
    from backend.services.exports_koxo import generer_csv_koxo

    site = site_factory("NDK")
    annee = annee_factory()
    p = personne_factory(site_id=site.id, login="test1")
    snap_factory(p.id, annee.id, classe="1_G2")

    contenu, _ = generer_csv_koxo(
        session=session, site_id=site.id, type_personne="eleve",
        categorie="tous", annee_cible_id=annee.id,
    )
    assert _lire_csv_koxo(contenu)[0]["Groupe secondaire"] == "1_G2"


def test_export_groupe_secondaire_adulte_est_matiere(session, site_factory, annee_factory, personne_factory, snap_factory):
    from backend.services.exports_koxo import generer_csv_koxo

    site = site_factory("NDK")
    annee = annee_factory()
    p = personne_factory(type="adulte", site_id=site.id, login="prof1")
    snap_factory(p.id, annee.id, matieres="MATHEMATIQUES;PHYSIQUE-CHIMIE", poste_occupe="ENSEIGNEMENT")

    contenu, _ = generer_csv_koxo(
        session=session, site_id=site.id, type_personne="adulte",
        categorie="tous", annee_cible_id=annee.id,
    )
    # Première matière du séparateur ;
    assert _lire_csv_koxo(contenu)[0]["Groupe secondaire"] == "MATHEMATIQUES"


# ---------------------------------------------------------------------------
# Catégories : Tous / Nouveaux / Anciens
# ---------------------------------------------------------------------------


def test_export_tous_liste_toutes_les_personnes_de_lannee(
    session, site_factory, annee_factory, personne_factory, snap_factory
):
    from backend.services.exports_koxo import generer_csv_koxo

    site = site_factory("NDK")
    annee = annee_factory()
    for i in range(1, 4):
        p = personne_factory(site_id=site.id, nom=f"P{i}", prenom=f"P{i}", login=f"p{i}")
        snap_factory(p.id, annee.id, classe="3B")

    contenu, rapport = generer_csv_koxo(
        session=session, site_id=site.id, type_personne="eleve",
        categorie="tous", annee_cible_id=annee.id,
    )
    assert rapport.nb_lignes == 3
    assert len(_lire_csv_koxo(contenu)) == 3


def test_export_nouveaux_seulement_les_entrants(
    session, site_factory, annee_factory, personne_factory, snap_factory
):
    """Un nouvel élève = présent dans annee_cible, absent d'annee_source."""
    from backend.services.exports_koxo import generer_csv_koxo

    site = site_factory("NDK")
    an_prec = annee_factory("2024-2025")
    an_cour = annee_factory("2025-2026")

    p_reste = personne_factory(site_id=site.id, nom="RESTE", login="reste")
    snap_factory(p_reste.id, an_prec.id, classe="3B")
    snap_factory(p_reste.id, an_cour.id, classe="2NDE")

    p_nouveau = personne_factory(site_id=site.id, nom="NEUF", login="neuf")
    snap_factory(p_nouveau.id, an_cour.id, classe="6A")

    contenu, rapport = generer_csv_koxo(
        session=session, site_id=site.id, type_personne="eleve",
        categorie="nouveaux", annee_cible_id=an_cour.id, annee_source_id=an_prec.id,
    )

    assert rapport.nb_lignes == 1
    assert _lire_csv_koxo(contenu)[0]["Nom"] == "NEUF"


def test_export_anciens_seulement_les_sortants(
    session, site_factory, annee_factory, personne_factory, snap_factory
):
    """Un ancien = présent dans annee_source, absent d'annee_cible."""
    from backend.services.exports_koxo import generer_csv_koxo

    site = site_factory("NDK")
    an_prec = annee_factory("2024-2025")
    an_cour = annee_factory("2025-2026")

    p_reste = personne_factory(site_id=site.id, nom="RESTE", login="reste")
    snap_factory(p_reste.id, an_prec.id, classe="3B")
    snap_factory(p_reste.id, an_cour.id, classe="2NDE")

    p_sortant = personne_factory(site_id=site.id, nom="SORT", login="sort")
    snap_factory(p_sortant.id, an_prec.id, classe="TALE")

    contenu, rapport = generer_csv_koxo(
        session=session, site_id=site.id, type_personne="eleve",
        categorie="anciens", annee_cible_id=an_cour.id, annee_source_id=an_prec.id,
    )

    assert rapport.nb_lignes == 1
    assert _lire_csv_koxo(contenu)[0]["Nom"] == "SORT"


def test_export_filtre_par_site(session, site_factory, annee_factory, personne_factory, snap_factory):
    """Un export NDK ne contient pas les élèves SU."""
    from backend.services.exports_koxo import generer_csv_koxo

    ndk = site_factory("NDK")
    su = site_factory("SU")
    annee = annee_factory()

    p_ndk = personne_factory(site_id=ndk.id, nom="NDK1", login="ndk1")
    snap_factory(p_ndk.id, annee.id)
    p_su = personne_factory(site_id=su.id, nom="SU1", login="su1")
    snap_factory(p_su.id, annee.id)

    contenu, rapport = generer_csv_koxo(
        session=session, site_id=ndk.id, type_personne="eleve",
        categorie="tous", annee_cible_id=annee.id,
    )
    assert rapport.nb_lignes == 1
    assert _lire_csv_koxo(contenu)[0]["Nom"] == "NDK1"


def test_export_filtre_par_type_personne(
    session, site_factory, annee_factory, personne_factory, snap_factory
):
    from backend.services.exports_koxo import generer_csv_koxo

    site = site_factory("NDK")
    annee = annee_factory()
    p_e = personne_factory(type="eleve", site_id=site.id, login="e1")
    p_a = personne_factory(type="adulte", site_id=site.id, login="a1")
    snap_factory(p_e.id, annee.id)
    snap_factory(p_a.id, annee.id)

    c_e, r_e = generer_csv_koxo(session=session, site_id=site.id, type_personne="eleve",
                                categorie="tous", annee_cible_id=annee.id)
    c_a, r_a = generer_csv_koxo(session=session, site_id=site.id, type_personne="adulte",
                                categorie="tous", annee_cible_id=annee.id)

    assert r_e.nb_lignes == 1 and r_a.nb_lignes == 1


# ---------------------------------------------------------------------------
# Validation des paramètres
# ---------------------------------------------------------------------------


def test_export_categorie_nouveaux_sans_annee_source_leve_erreur(session, site_factory, annee_factory):
    from backend.services.exports_koxo import generer_csv_koxo

    site = site_factory("NDK")
    annee = annee_factory()
    with pytest.raises(ValueError, match="annee_source_id"):
        generer_csv_koxo(
            session=session, site_id=site.id, type_personne="eleve",
            categorie="nouveaux", annee_cible_id=annee.id, annee_source_id=None,
        )


def test_export_categorie_anciens_sans_annee_source_leve_erreur(session, site_factory, annee_factory):
    from backend.services.exports_koxo import generer_csv_koxo

    site = site_factory("NDK")
    annee = annee_factory()
    with pytest.raises(ValueError, match="annee_source_id"):
        generer_csv_koxo(
            session=session, site_id=site.id, type_personne="eleve",
            categorie="anciens", annee_cible_id=annee.id, annee_source_id=None,
        )


def test_export_type_invalide(session, site_factory, annee_factory):
    from backend.services.exports_koxo import generer_csv_koxo

    site = site_factory("NDK")
    annee = annee_factory()
    with pytest.raises(ValueError, match="type_personne"):
        generer_csv_koxo(session=session, site_id=site.id, type_personne="prof",
                         categorie="tous", annee_cible_id=annee.id)


def test_export_categorie_invalide(session, site_factory, annee_factory):
    from backend.services.exports_koxo import generer_csv_koxo

    site = site_factory("NDK")
    annee = annee_factory()
    with pytest.raises(ValueError, match="categorie"):
        generer_csv_koxo(session=session, site_id=site.id, type_personne="eleve",
                         categorie="autre", annee_cible_id=annee.id)


def test_export_site_introuvable(session, annee_factory):
    from backend.services.exports_koxo import generer_csv_koxo

    annee = annee_factory()
    with pytest.raises(ValueError, match="Site introuvable"):
        generer_csv_koxo(session=session, site_id=99999, type_personne="eleve",
                         categorie="tous", annee_cible_id=annee.id)


def test_nom_fichier_suggere(session, site_factory, annee_factory):
    from backend.services.exports_koxo import generer_csv_koxo

    site = site_factory("NDK")
    annee = annee_factory()
    _, rapport = generer_csv_koxo(
        session=session, site_id=site.id, type_personne="eleve",
        categorie="tous", annee_cible_id=annee.id,
    )
    assert rapport.nom_fichier_suggere == "KoXo_NDK_eleves_tous.csv"


def test_multi_snapshots_retient_le_dernier(session, site_factory, annee_factory, personne_factory):
    """Si plusieurs ingestions dans une même année, on prend le dernier snapshot."""
    from datetime import datetime, timedelta
    from backend.models import Snapshot
    from backend.services.exports_koxo import generer_csv_koxo

    site = site_factory("NDK")
    annee = annee_factory()
    p = personne_factory(site_id=site.id, login="test1")

    ancien = Snapshot(personne_id=p.id, annee_scolaire_id=annee.id,
                      nom="P", prenom="P", classe="OBSOLETE",
                      date_ingestion=datetime.utcnow() - timedelta(days=10))
    session.add(ancien)
    recent = Snapshot(personne_id=p.id, annee_scolaire_id=annee.id,
                      nom="P", prenom="P", classe="COURANT")
    session.add(recent)
    session.commit()

    contenu, _ = generer_csv_koxo(
        session=session, site_id=site.id, type_personne="eleve",
        categorie="tous", annee_cible_id=annee.id,
    )
    rows = _lire_csv_koxo(contenu)
    assert len(rows) == 1
    assert rows[0]["Groupe secondaire"] == "COURANT"
