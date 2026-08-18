"""Tests de l'amorçage depuis les exports KoXo.

Vérifie :
- Création de Personnes avec login figé pris du fichier
- Idempotence : deuxième amorçage ne recrée rien
- Conflit de login : la base l'emporte, le fichier est signalé
- Mot de passe présent dans le fichier n'est jamais stocké
- Formule badge → id_charlemagne (élève et adulte)
- Rejets propres (colonnes manquantes, badge invalide)
"""
from __future__ import annotations

from pathlib import Path

import pytest


def _ecrire_csv_koxo(chemin: Path, lignes: list[dict], sep: str = ",") -> None:
    """Fabrique un mini CSV KoXo (première ligne = en-tête)."""
    entetes = list(lignes[0].keys())
    contenu = sep.join(entetes) + "\n"
    for l in lignes:
        contenu += sep.join(str(l.get(h, "")) for h in entetes) + "\n"
    chemin.write_text(contenu, encoding="utf-8")


def _ligne_koxo_eleve(nom, prenom, login, badge, classe="3B", mdp=""):
    return {
        "badge": badge,
        "Groupe primaire": "Elèves",
        "Groupe secondaire": classe,
        "Titre": "",
        "Nom": nom,
        "Prénom": prenom,
        "Identifiant": login,
        "ID unique": badge,
        "Mot de passe": mdp,
        "Date de naissance": "",
        "Email": f"{prenom.lower()}.{nom.lower()}@lekreisker.fr",
    }


# ---------------------------------------------------------------------------
# Parser KoXo
# ---------------------------------------------------------------------------


def test_parser_koxo_lit_csv_virgule(tmp_path):
    from backend.services.parser_koxo import lire_csv_koxo

    fic = tmp_path / "koxo.csv"
    _ecrire_csv_koxo(fic, [_ligne_koxo_eleve("DUPONT", "Jean", "jdupont", 68240)])

    df = lire_csv_koxo(fic)
    assert "login" in df.columns
    assert "num_badge" in df.columns
    assert df.loc[0, "login"] == "jdupont"
    assert df.loc[0, "num_badge"] == 68240


def test_parser_koxo_lit_csv_point_virgule(tmp_path):
    from backend.services.parser_koxo import lire_csv_koxo

    fic = tmp_path / "pv.csv"
    _ecrire_csv_koxo(fic, [_ligne_koxo_eleve("MARTIN", "Marie", "mmartin", 62920)], sep=";")

    df = lire_csv_koxo(fic)
    assert df.loc[0, "login"] == "mmartin"


def test_deduire_id_charlemagne_eleve():
    from backend.services.parser_koxo import deduire_id_charlemagne

    # badge=68240 → id=5824 (formule confirmée sur le vrai export)
    assert deduire_id_charlemagne(68240, "eleve") == 5824
    assert deduire_id_charlemagne(62920, "eleve") == 5292
    assert deduire_id_charlemagne(10000, "eleve") == 0


def test_deduire_id_charlemagne_adulte():
    from backend.services.parser_koxo import deduire_id_charlemagne

    # Adulte : badge = id directement
    assert deduire_id_charlemagne(313, "adulte") == 313
    assert deduire_id_charlemagne(60, "adulte") == 60


def test_deduire_id_charlemagne_badge_invalide():
    from backend.services.parser_koxo import deduire_id_charlemagne

    # Badge non conforme à la formule élève (pas multiple de 10 + 10000)
    assert deduire_id_charlemagne(12345, "eleve") is None
    assert deduire_id_charlemagne(5000, "eleve") is None  # < 10000
    assert deduire_id_charlemagne(None, "eleve") is None


# ---------------------------------------------------------------------------
# Service d'amorçage
# ---------------------------------------------------------------------------


def test_amorcage_cree_personnes_avec_login_du_fichier(tmp_path, session, site_factory):
    from backend.models import Personne
    from backend.services.amorcage import amorcer_depuis_koxo

    ndk = site_factory("NDK")
    fic = tmp_path / "eleves_ndk.csv"
    _ecrire_csv_koxo(fic, [
        _ligne_koxo_eleve("DUPONT", "Jean", "jdupont", 68240),
        _ligne_koxo_eleve("MARTIN", "Marie", "mmartin", 62920),
    ])

    r = amorcer_depuis_koxo(session, fic, site_id=ndk.id, type_personne="eleve", mode="reel")

    assert r.nb_creations == 2
    assert r.nb_deja_presentes == 0
    assert r.est_bloque is False

    p1 = session.query(Personne).filter_by(id_charlemagne=5824).one()
    assert p1.login == "jdupont"  # login pris du fichier, pas régénéré
    assert p1.badge == 68240
    assert p1.type == "eleve"
    assert p1.site_id == ndk.id


def test_amorcage_ne_regenere_pas_les_logins_qui_devraient_collisionner(
    tmp_path, session, site_factory
):
    """Deux Dupont dans le fichier avec des logins déjà distincts (dupont-père a
    hérité de jdupont, dupont-fils a jdupont2) → l'amorçage préserve les deux."""
    from backend.models import Personne
    from backend.services.amorcage import amorcer_depuis_koxo

    ndk = site_factory("NDK")
    fic = tmp_path / "collision.csv"
    _ecrire_csv_koxo(fic, [
        _ligne_koxo_eleve("DUPONT", "Jean", "jdupont", 68240),
        _ligne_koxo_eleve("DUPONT", "Julien", "jdupont2", 68250),
    ])

    r = amorcer_depuis_koxo(session, fic, site_id=ndk.id, type_personne="eleve", mode="reel")

    assert r.nb_creations == 2
    assert r.nb_rejets == 0

    logins = {p.login for p in session.query(Personne).all()}
    assert logins == {"jdupont", "jdupont2"}


def test_amorcage_simulation_ne_persiste_rien(tmp_path, session, site_factory):
    from backend.models import Personne
    from backend.services.amorcage import amorcer_depuis_koxo

    ndk = site_factory("NDK")
    fic = tmp_path / "sim.csv"
    _ecrire_csv_koxo(fic, [_ligne_koxo_eleve("DUPONT", "Jean", "jdupont", 68240)])

    r = amorcer_depuis_koxo(session, fic, site_id=ndk.id, type_personne="eleve", mode="simulation")

    assert r.nb_creations == 1
    assert session.query(Personne).count() == 0  # rien en base


def test_amorcage_est_idempotent(tmp_path, session, site_factory):
    """Deuxième amorçage du même fichier : les personnes sont déjà là."""
    from backend.models import Personne
    from backend.services.amorcage import amorcer_depuis_koxo

    ndk = site_factory("NDK")
    fic = tmp_path / "idem.csv"
    _ecrire_csv_koxo(fic, [_ligne_koxo_eleve("DUPONT", "Jean", "jdupont", 68240)])

    r1 = amorcer_depuis_koxo(session, fic, site_id=ndk.id, type_personne="eleve", mode="reel")
    r2 = amorcer_depuis_koxo(session, fic, site_id=ndk.id, type_personne="eleve", mode="reel")

    assert r1.nb_creations == 1
    assert r2.nb_creations == 0
    assert r2.nb_deja_presentes == 1
    assert session.query(Personne).count() == 1


def test_amorcage_conflit_login_garde_la_base(tmp_path, session, site_factory, personne_factory):
    """Si le login du fichier diffère de celui déjà en base, on garde la base."""
    from backend.models import Personne
    from backend.services.amorcage import amorcer_depuis_koxo

    ndk = site_factory("NDK")
    # Personne déjà en base avec login "jdupont2"
    personne_factory(type="eleve", id_charlemagne=5824, nom="DUPONT", prenom="Jean",
                     login="jdupont2", site_id=ndk.id)

    fic = tmp_path / "conflit.csv"
    _ecrire_csv_koxo(fic, [_ligne_koxo_eleve("DUPONT", "Jean", "jdupont", 68240)])

    r = amorcer_depuis_koxo(session, fic, site_id=ndk.id, type_personne="eleve", mode="reel")

    assert r.nb_conflits_login == 1
    assert r.nb_creations == 0

    p = session.query(Personne).filter_by(id_charlemagne=5824).one()
    assert p.login == "jdupont2"  # inchangé, la base prime


def test_amorcage_signale_presence_mdp_sans_les_stocker(tmp_path, session, site_factory):
    """La colonne « Mot de passe » est lue pour le mapping mais jamais persistée."""
    from backend.models import Personne
    from backend.services.amorcage import amorcer_depuis_koxo

    ndk = site_factory("NDK")
    fic = tmp_path / "mdp.csv"
    _ecrire_csv_koxo(fic, [_ligne_koxo_eleve("DUPONT", "Jean", "jdupont", 68240, mdp="Sateku68")])

    r = amorcer_depuis_koxo(session, fic, site_id=ndk.id, type_personne="eleve", mode="reel")

    assert r.contient_mots_de_passe is True

    # La Personne n'a AUCUN champ mot de passe
    p = session.query(Personne).filter_by(id_charlemagne=5824).one()
    assert not hasattr(p, "mot_de_passe")
    assert not hasattr(p, "password")

    # Aucune colonne du modèle Personne ne contient "Sateku68"
    for col in ("nom", "prenom", "login"):
        assert getattr(p, col) != "Sateku68"


def test_amorcage_rejette_badge_invalide(tmp_path, session, site_factory):
    from backend.services.amorcage import amorcer_depuis_koxo

    ndk = site_factory("NDK")
    fic = tmp_path / "bad.csv"
    _ecrire_csv_koxo(fic, [_ligne_koxo_eleve("DUPONT", "Jean", "jdupont", 12345)])  # bad badge

    r = amorcer_depuis_koxo(session, fic, site_id=ndk.id, type_personne="eleve", mode="reel")

    assert r.nb_creations == 0
    assert r.nb_rejets == 1
    assert "id_charlemagne" in r.rejets[0].raison


def test_amorcage_unicite_globale_login(tmp_path, session, site_factory, personne_factory):
    """Un login déjà pris par une autre personne (avec un autre id_charlemagne)
    ne peut pas être réattribué."""
    from backend.services.amorcage import amorcer_depuis_koxo

    ndk = site_factory("NDK")
    # Un adulte a déjà "jdupont"
    personne_factory(type="adulte", id_charlemagne=100, login="jdupont", site_id=ndk.id)

    fic = tmp_path / "collision_globale.csv"
    _ecrire_csv_koxo(fic, [_ligne_koxo_eleve("DUPONT", "Julien", "jdupont", 68240)])

    r = amorcer_depuis_koxo(session, fic, site_id=ndk.id, type_personne="eleve", mode="reel")

    # L'élève ne peut pas être créé — collision avec l'adulte
    assert r.nb_creations == 0
    assert r.nb_rejets == 1
    from unidecode import unidecode
    raison = unidecode(r.rejets[0].raison.lower())
    assert "unicite" in raison or "deja pris" in raison


def test_amorcage_site_introuvable(tmp_path, session):
    from backend.services.amorcage import amorcer_depuis_koxo

    fic = tmp_path / "site.csv"
    _ecrire_csv_koxo(fic, [_ligne_koxo_eleve("DUPONT", "Jean", "jdupont", 68240)])

    with pytest.raises(ValueError, match="Site introuvable"):
        amorcer_depuis_koxo(session, fic, site_id=99999, type_personne="eleve", mode="reel")


def test_amorcage_mode_invalide(tmp_path, session, site_factory):
    from backend.services.amorcage import amorcer_depuis_koxo

    ndk = site_factory("NDK")
    fic = tmp_path / "m.csv"
    _ecrire_csv_koxo(fic, [_ligne_koxo_eleve("DUPONT", "Jean", "jdupont", 68240)])

    with pytest.raises(ValueError, match="mode"):
        amorcer_depuis_koxo(session, fic, site_id=ndk.id, type_personne="eleve", mode="fantaisie")


def test_amorcage_type_personne_invalide(tmp_path, session, site_factory):
    from backend.services.amorcage import amorcer_depuis_koxo

    ndk = site_factory("NDK")
    fic = tmp_path / "t.csv"
    _ecrire_csv_koxo(fic, [_ligne_koxo_eleve("DUPONT", "Jean", "jdupont", 68240)])

    with pytest.raises(ValueError, match="type_personne"):
        amorcer_depuis_koxo(session, fic, site_id=ndk.id, type_personne="prof", mode="reel")


def test_amorcage_fichier_corrompu(tmp_path, session, site_factory):
    from backend.services.amorcage import amorcer_depuis_koxo

    ndk = site_factory("NDK")
    fic = tmp_path / "corrupt.csv"
    fic.write_bytes(b"\x00\x01\x02\x03\x04")

    r = amorcer_depuis_koxo(session, fic, site_id=ndk.id, type_personne="eleve", mode="reel")
    assert r.est_bloque is True
    assert len(r.erreurs) == 1


def test_amorcage_adulte(tmp_path, session, site_factory):
    """Un adulte : badge = id_charlemagne (pas de multiplication)."""
    from backend.models import Personne
    from backend.services.amorcage import amorcer_depuis_koxo

    ndk = site_factory("NDK")
    fic = tmp_path / "adultes.csv"
    _ecrire_csv_koxo(fic, [
        {
            "badge": 313, "Groupe primaire": "Professeurs", "Groupe secondaire": "MATHEMATIQUES",
            "Titre": "M.", "Nom": "BARS", "Prénom": "John", "Identifiant": "jbars",
            "ID unique": 313, "Mot de passe": "", "Date de naissance": "",
            "Email": "john.bars@lekreisker.fr",
        }
    ])

    r = amorcer_depuis_koxo(session, fic, site_id=ndk.id, type_personne="adulte", mode="reel")

    assert r.nb_creations == 1
    p = session.query(Personne).filter_by(type="adulte", id_charlemagne=313).one()
    assert p.login == "jbars"
    assert p.badge == 313


# ---------------------------------------------------------------------------
# Adresse constatée
# ---------------------------------------------------------------------------


def test_amorcage_releve_l_adresse_du_compte(session, site_factory, tmp_path):
    """L'export KoXo porte l'adresse réelle : on la mémorise sans la recalculer."""
    from backend.services.amorcage import amorcer_depuis_koxo

    site = site_factory("NDK")
    fic = tmp_path / "k.csv"
    ligne = _ligne_koxo_eleve("HENOCQ KERAUTRET", "Sarah", "shenocqker", 68240)
    ligne["Email"] = "sarah.henocq@lekreisker.fr"  # hors convention
    _ecrire_csv_koxo(fic, [ligne])

    amorcer_depuis_koxo(
        session, fic, site_id=site.id, type_personne="eleve", mode="reel"
    )

    from backend.models import Personne

    p = session.query(Personne).filter_by(login="shenocqker").one()
    assert p.email_constate == "sarah.henocq@lekreisker.fr"
    assert p.email == "sarah.henocq@lekreisker.fr"


def test_amorcage_ignore_une_adresse_personnelle(session, site_factory, tmp_path):
    from backend.services.amorcage import amorcer_depuis_koxo

    site = site_factory("NDK")
    fic = tmp_path / "k.csv"
    ligne = _ligne_koxo_eleve("CALVEZ", "Shanisse", "scalvez", 68250)
    ligne["Email"] = "shanisse.c11@gmail.com"
    _ecrire_csv_koxo(fic, [ligne])

    amorcer_depuis_koxo(
        session, fic, site_id=site.id, type_personne="eleve", mode="reel"
    )

    from backend.models import Personne

    p = session.query(Personne).filter_by(login="scalvez").one()
    assert p.email_constate is None


def test_amorcage_simulation_ne_persiste_pas_l_adresse(
    session, site_factory, tmp_path
):
    from backend.services.amorcage import amorcer_depuis_koxo

    site = site_factory("NDK")
    fic = tmp_path / "k.csv"
    _ecrire_csv_koxo(fic, [_ligne_koxo_eleve("DUPONT", "Jean", "jdupont", 68240)])

    amorcer_depuis_koxo(
        session, fic, site_id=site.id, type_personne="eleve", mode="simulation"
    )

    from backend.models import Personne

    assert session.query(Personne).count() == 0
