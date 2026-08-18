"""Tests du Lot 8b — boucle de retour KoXo → Google."""
from __future__ import annotations

import csv
import io

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


def _mini_csv_koxo(lignes: list[dict], sep=",") -> bytes:
    """Fabrique un CSV KoXo minimal (colonnes canoniques)."""
    entetes = ["Identifiant", "Nom", "Prénom", "Mot de passe"]
    contenu = sep.join(entetes) + "\r\n"
    for l in lignes:
        contenu += sep.join(str(l.get(h, "")) for h in entetes) + "\r\n"
    return contenu.encode("cp1252")


def _lire_google(bytes_):
    if bytes_.startswith(b"\xef\xbb\xbf"):
        bytes_ = bytes_[3:]
    return list(csv.DictReader(io.StringIO(bytes_.decode("utf-8"))))


def test_extraction_mdp_koxo():
    from backend.services.exports_google import _extraire_mdp_depuis_csv_koxo

    csv_bytes = _mini_csv_koxo([
        {"Identifiant": "jdupont", "Nom": "DUPONT", "Prénom": "Jean", "Mot de passe": "Abc123"},
        {"Identifiant": "mmartin", "Nom": "MARTIN", "Prénom": "Marie", "Mot de passe": "Xyz789"},
    ])

    mdp = _extraire_mdp_depuis_csv_koxo(csv_bytes)
    assert mdp == {"jdupont": "Abc123", "mmartin": "Xyz789"}


def test_extraction_mdp_ignore_lignes_sans_mdp():
    from backend.services.exports_google import _extraire_mdp_depuis_csv_koxo

    csv_bytes = _mini_csv_koxo([
        {"Identifiant": "avec", "Mot de passe": "Present"},
        {"Identifiant": "sans", "Mot de passe": ""},
    ])
    mdp = _extraire_mdp_depuis_csv_koxo(csv_bytes)
    assert mdp == {"avec": "Present"}


def test_extraction_mdp_supporte_utf8_et_pv():
    from backend.services.exports_google import _extraire_mdp_depuis_csv_koxo

    contenu = "Identifiant;Mot de passe\r\njdupont;Zeta42\r\n".encode("utf-8")
    mdp = _extraire_mdp_depuis_csv_koxo(contenu)
    assert mdp == {"jdupont": "Zeta42"}


def test_google_avec_mdp_enrichit_les_lignes_correspondantes(
    session, site_factory, annee_factory, personne_factory, snap_factory
):
    from backend.services.exports_google import generer_csv_google_avec_mdp

    site = site_factory("NDK")
    an_prec = annee_factory("2024-2025")
    an_cour = annee_factory("2025-2026")

    p = personne_factory(site_id=site.id, nom="DUPONT", prenom="Jean", login="jdupont")
    snap_factory(p.id, an_cour.id, classe="3B")

    csv_koxo = _mini_csv_koxo([
        {"Identifiant": "jdupont", "Nom": "DUPONT", "Prénom": "Jean", "Mot de passe": "Sateku68"},
    ])

    contenu, rapport = generer_csv_google_avec_mdp(
        session=session,
        csv_koxo_bytes=csv_koxo,
        site_id=site.id,
        type_personne="eleve",
        categorie="nouveaux",
        annee_cible_id=an_cour.id,
        annee_source_id=an_prec.id,
    )

    rows = _lire_google(contenu)
    assert len(rows) == 1
    assert rows[0]["Password [Required]"] == "Sateku68"
    assert rapport.nb_lignes_avec_mdp == 1


def test_mdp_apparie_sur_une_adresse_hors_convention(
    session, site_factory, annee_factory, personne_factory, snap_factory
):
    """L'appariement passe par le référentiel, pas par la forme de l'adresse.

    Régression : la version initiale retrouvait le login en coupant l'adresse
    avant le `@`. Ça ne marchait que sous l'hypothèse fausse
    `email == login@domaine`. Ici l'adresse constatée (`sarah.henocq`) n'a
    aucun rapport avec le login KoXo (`shenocqker`) — couper l'adresse
    laisserait le mot de passe orphelin et le compte créé sans accès.
    """
    from backend.services.exports_google import generer_csv_google_avec_mdp

    site = site_factory("NDK")
    an_prec = annee_factory("2024-2025")
    an_cour = annee_factory("2025-2026")

    p = personne_factory(
        site_id=site.id,
        nom="HENOCQ KERAUTRET",
        prenom="Sarah",
        login="shenocqker",
        email_constate="sarah.henocq@lekreisker.fr",
    )
    snap_factory(p.id, an_cour.id, classe="3B")

    csv_koxo = _mini_csv_koxo([
        {"Identifiant": "shenocqker", "Nom": "HENOCQ KERAUTRET",
         "Prénom": "Sarah", "Mot de passe": "Sateku68"},
    ])

    contenu, rapport = generer_csv_google_avec_mdp(
        session=session, csv_koxo_bytes=csv_koxo, site_id=site.id,
        type_personne="eleve", categorie="tous",
        annee_cible_id=an_cour.id, annee_source_id=an_prec.id,
    )

    rows = _lire_google(contenu)
    assert rows[0]["Email Address [Required]"] == "sarah.henocq@lekreisker.fr"
    assert rows[0]["Password [Required]"] == "Sateku68"
    assert rapport.nb_lignes_avec_mdp == 1
    assert rapport.nb_mdp_orphelins == 0


def test_google_avec_mdp_signale_orphelins(
    session, site_factory, annee_factory, personne_factory, snap_factory
):
    """Un MDP KoXo dont le login n'apparaît pas dans le CSV Google → orphelin."""
    from backend.services.exports_google import generer_csv_google_avec_mdp

    site = site_factory("NDK")
    an_prec = annee_factory("2024-2025")
    an_cour = annee_factory("2025-2026")

    p = personne_factory(site_id=site.id, nom="DUPONT", prenom="Jean", login="jdupont")
    snap_factory(p.id, an_cour.id, classe="3B")

    csv_koxo = _mini_csv_koxo([
        {"Identifiant": "jdupont", "Mot de passe": "Abc123"},
        {"Identifiant": "inconnu", "Mot de passe": "Xyz789"},  # pas dans Google
    ])

    _, rapport = generer_csv_google_avec_mdp(
        session=session, csv_koxo_bytes=csv_koxo,
        site_id=site.id, type_personne="eleve", categorie="nouveaux",
        annee_cible_id=an_cour.id, annee_source_id=an_prec.id,
    )

    assert rapport.nb_lignes_avec_mdp == 1
    assert rapport.nb_mdp_orphelins == 1


def test_mdp_absents_laissent_le_champ_vide(
    session, site_factory, annee_factory, personne_factory, snap_factory
):
    """Personne Google sans MDP dans le CSV KoXo → Password vide (pas de crash)."""
    from backend.services.exports_google import generer_csv_google_avec_mdp

    site = site_factory("NDK")
    an_prec = annee_factory("2024-2025")
    an_cour = annee_factory("2025-2026")
    p = personne_factory(site_id=site.id, login="jdupont")
    snap_factory(p.id, an_cour.id, classe="3B")

    csv_koxo = _mini_csv_koxo([])  # vide

    contenu, _ = generer_csv_google_avec_mdp(
        session=session, csv_koxo_bytes=csv_koxo,
        site_id=site.id, type_personne="eleve", categorie="nouveaux",
        annee_cible_id=an_cour.id, annee_source_id=an_prec.id,
    )
    rows = _lire_google(contenu)
    assert rows[0]["Password [Required]"] == ""


def test_csv_koxo_vide_ne_leve_pas_derreur():
    """Un CSV avec juste des en-têtes est valide (0 MDP extraits)."""
    from backend.services.exports_google import _extraire_mdp_depuis_csv_koxo

    mdp = _extraire_mdp_depuis_csv_koxo(b"Identifiant,Mot de passe\r\n")
    assert mdp == {}


def test_nom_fichier_avec_suffixe_mdp(
    session, site_factory, annee_factory, personne_factory, snap_factory
):
    from backend.services.exports_google import generer_csv_google_avec_mdp

    site = site_factory("NDK")
    an_prec = annee_factory("2024-2025")
    an_cour = annee_factory("2025-2026")
    p = personne_factory(site_id=site.id, login="test")
    snap_factory(p.id, an_cour.id, classe="3B")

    _, rapport = generer_csv_google_avec_mdp(
        session=session, csv_koxo_bytes=_mini_csv_koxo([]),
        site_id=site.id, type_personne="eleve", categorie="nouveaux",
        annee_cible_id=an_cour.id, annee_source_id=an_prec.id,
    )
    assert rapport.nom_fichier_suggere == "Google_NDK_eleves_nouveaux_avec_mdp.csv"
