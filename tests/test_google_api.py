"""Tests du mode API Google.

Seule la partie **hors ligne** est testable : construction des payloads,
validation de configuration, calcul du plan. Les appels HTTP réels ne
peuvent être validés qu'avec de vraies credentials — ils sont isolés dans
`ClientGoogle`, qui n'est pas instancié ici.
"""
from __future__ import annotations

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

    def _creer(site_id, code_court):
        tc = TableCorrespondance(
            site_id=site_id,
            classe_charlemagne_long=f"CLASSE {code_court}",
            classe_code_court=code_court,
            ou_pre_rentree="/3. NDK/NDK2026",
            ou_definitive=f"/3. NDK/NDK2026/{code_court}",
        )
        session.add(tc)
        session.commit()
        return tc

    return _creer


# ---------------------------------------------------------------------------
# Payloads
# ---------------------------------------------------------------------------


def test_payload_creation_structure():
    from backend.services.google_api import payload_creation_utilisateur

    p = payload_creation_utilisateur(
        prenom="Jean", nom="DUPONT",
        email="jdupont@lekreisker.fr",
        org_unit_path="/3. NDK/NDK2026",
        mot_de_passe="Sateku68",
        id_charlemagne=5824,
    )

    assert p["primaryEmail"] == "jdupont@lekreisker.fr"
    assert p["name"]["givenName"] == "Jean"
    assert p["name"]["familyName"] == "DUPONT"
    assert p["orgUnitPath"] == "/3. NDK/NDK2026"
    assert p["changePasswordAtNextLogin"] is True
    assert p["externalIds"][0]["value"] == "5824"


def test_payload_creation_sans_id_charlemagne():
    from backend.services.google_api import payload_creation_utilisateur

    p = payload_creation_utilisateur(
        prenom="A", nom="B", email="ab@x.fr",
        org_unit_path="/x", mot_de_passe="pwd",
    )
    assert "externalIds" not in p


def test_payload_deplacement_ne_touche_que_lou():
    from backend.services.google_api import payload_deplacement_ou

    p = payload_deplacement_ou(org_unit_path="/3. NDK/NDK2026/2NDE1")
    assert p == {"orgUnitPath": "/3. NDK/NDK2026/2NDE1"}


def test_payload_suspension_nest_pas_une_suppression():
    """La suspension préserve le compte et ses données."""
    from backend.services.google_api import payload_suspension

    assert payload_suspension() == {"suspended": True}
    assert payload_suspension(suspendu=False) == {"suspended": False}


def test_payload_membre_groupe():
    from backend.services.google_api import payload_membre_groupe

    p = payload_membre_groupe(email="jdupont@lekreisker.fr")
    assert p["email"] == "jdupont@lekreisker.fr"
    assert p["role"] == "MEMBER"
    assert p["type"] == "USER"


def test_scopes_nincluent_pas_les_donnees_utilisateur():
    """Les scopes restent minimaux : annuaire seulement, pas Drive ni Gmail."""
    from backend.services.google_api import SCOPES

    joint = " ".join(SCOPES)
    assert "drive" not in joint
    assert "gmail" not in joint
    assert all("admin.directory" in s for s in SCOPES)


# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------


def test_config_absente_est_invalide(session):
    from backend.services.google_api import charger_config

    config = charger_config(session)
    problemes = config.valider()
    assert config.est_complete is False
    assert len(problemes) >= 1


def test_config_signale_fichier_introuvable(session):
    from backend.services.configuration import set_param
    from backend.services.google_api import charger_config

    set_param(session, "google.api_active", True)
    set_param(session, "google.chemin_credentials", "Z:/nexiste/pas.json")
    set_param(session, "google.admin_impersonation", "admin@lekreisker.fr")
    session.commit()

    problemes = charger_config(session).valider()
    assert any("introuvable" in p for p in problemes)


def test_config_complete_ne_signale_rien(tmp_path, session):
    from backend.services.configuration import set_param
    from backend.services.google_api import charger_config

    faux_json = tmp_path / "credentials.json"
    faux_json.write_text("{}")

    set_param(session, "google.api_active", True)
    set_param(session, "google.chemin_credentials", str(faux_json))
    set_param(session, "google.admin_impersonation", "admin@lekreisker.fr")
    session.commit()

    config = charger_config(session)
    assert config.valider() == []
    assert config.est_complete is True


def test_config_inactive_est_signalee(tmp_path, session):
    from backend.services.configuration import set_param
    from backend.services.google_api import charger_config

    faux_json = tmp_path / "c.json"
    faux_json.write_text("{}")
    set_param(session, "google.api_active", False)
    set_param(session, "google.chemin_credentials", str(faux_json))
    set_param(session, "google.admin_impersonation", "a@b.fr")
    session.commit()

    problemes = charger_config(session).valider()
    assert any("désactivé" in p for p in problemes)


# ---------------------------------------------------------------------------
# Construction du plan
# ---------------------------------------------------------------------------


def test_plan_creation_avec_mot_de_passe(
    session, site_factory, annee_factory, personne_factory, snap_factory, tc_factory
):
    from backend.services.google_api import construire_plan

    site = site_factory("NDK")
    an_prec = annee_factory("2024-2025")
    an_cour = annee_factory("2025-2026")
    tc_factory(site.id, "3B")

    p = personne_factory(site_id=site.id, nom="NEUF", prenom="Jean", login="jneuf")
    snap_factory(p.id, an_cour.id, classe="3B")

    plan = construire_plan(
        session, site_id=site.id, type_personne="eleve",
        annee_cible_id=an_cour.id, annee_source_id=an_prec.id,
        mots_de_passe={"jneuf": "Sateku68"},
    )

    assert plan.nb_creations == 1
    op = plan.operations[0]
    assert op.action == "creer"
    assert op.email == "jneuf@lekreisker.fr"
    assert op.payload["orgUnitPath"] == "/3. NDK/NDK2026"  # OU pré-rentrée


def test_plan_exclut_les_nouveaux_sans_mot_de_passe(
    session, site_factory, annee_factory, personne_factory, snap_factory, tc_factory
):
    """Créer un compte sans mot de passe n'aurait pas de sens : on l'écarte."""
    from backend.services.google_api import construire_plan

    site = site_factory("NDK")
    an_prec = annee_factory("2024-2025")
    an_cour = annee_factory("2025-2026")
    tc_factory(site.id, "3B")
    p = personne_factory(site_id=site.id, nom="NEUF", login="jneuf")
    snap_factory(p.id, an_cour.id, classe="3B")

    plan = construire_plan(
        session, site_id=site.id, type_personne="eleve",
        annee_cible_id=an_cour.id, annee_source_id=an_prec.id,
        mots_de_passe={},  # boucle KoXo non faite
    )

    assert plan.nb_creations == 0
    assert any("mot de passe" in a for a in plan.avertissements)


def test_plan_deplacement_si_classe_change(
    session, site_factory, annee_factory, personne_factory, snap_factory, tc_factory
):
    from backend.services.google_api import construire_plan

    site = site_factory("NDK")
    an_prec = annee_factory("2024-2025")
    an_cour = annee_factory("2025-2026")
    tc_factory(site.id, "3B")
    tc_factory(site.id, "2NDE1")

    p = personne_factory(site_id=site.id, nom="MOD", login="mod")
    snap_factory(p.id, an_prec.id, classe="3B")
    snap_factory(p.id, an_cour.id, classe="2NDE1")

    plan = construire_plan(
        session, site_id=site.id, type_personne="eleve",
        annee_cible_id=an_cour.id, annee_source_id=an_prec.id,
    )

    assert plan.nb_deplacements == 1
    assert plan.operations[0].payload["orgUnitPath"] == "/3. NDK/NDK2026/2NDE1"


def test_plan_ignore_les_modifs_hors_classe(
    session, site_factory, annee_factory, personne_factory, snap_factory, tc_factory
):
    """Un changement de régime ne justifie pas un déplacement d'OU."""
    from backend.services.google_api import construire_plan

    site = site_factory("NDK")
    an_prec = annee_factory("2024-2025")
    an_cour = annee_factory("2025-2026")
    tc_factory(site.id, "3B")

    p = personne_factory(site_id=site.id, login="mod")
    snap_factory(p.id, an_prec.id, classe="3B", regime="D")
    snap_factory(p.id, an_cour.id, classe="3B", regime="E")

    plan = construire_plan(
        session, site_id=site.id, type_personne="eleve",
        annee_cible_id=an_cour.id, annee_source_id=an_prec.id,
    )
    assert plan.nb_deplacements == 0


def test_plan_sortant_suspend_sans_supprimer(
    session, site_factory, annee_factory, personne_factory, snap_factory, tc_factory
):
    """Un sortant est suspendu et archivé — jamais effacé (§7.2)."""
    from backend.services.google_api import construire_plan

    site = site_factory("NDK")
    an_prec = annee_factory("2024-2025")
    an_cour = annee_factory("2025-2026")
    tc_factory(site.id, "TALE")

    p = personne_factory(site_id=site.id, nom="SORT", login="sort")
    snap_factory(p.id, an_prec.id, classe="TALE")

    plan = construire_plan(
        session, site_id=site.id, type_personne="eleve",
        annee_cible_id=an_cour.id, annee_source_id=an_prec.id,
    )

    assert plan.nb_suspensions == 1
    op = plan.operations[0]
    assert op.payload["suspended"] is True
    assert op.payload["orgUnitPath"].startswith("/7. Sortis/")
    # Aucune action de suppression dans tout le plan
    assert all(o.action != "supprimer" for o in plan.operations)


def test_plan_avertit_sur_classe_hors_table(
    session, site_factory, annee_factory, personne_factory, snap_factory
):
    from backend.services.google_api import construire_plan

    site = site_factory("NDK")
    an_prec = annee_factory("2024-2025")
    an_cour = annee_factory("2025-2026")
    p = personne_factory(site_id=site.id, nom="NEUF", login="jneuf")
    snap_factory(p.id, an_cour.id, classe="XX_INCONNUE")

    plan = construire_plan(
        session, site_id=site.id, type_personne="eleve",
        annee_cible_id=an_cour.id, annee_source_id=an_prec.id,
        mots_de_passe={"jneuf": "pwd"},
    )
    assert any("hors table" in a for a in plan.avertissements)


def test_plan_filtre_par_site(
    session, site_factory, annee_factory, personne_factory, snap_factory, tc_factory
):
    from backend.services.google_api import construire_plan

    ndk = site_factory("NDK")
    su = site_factory("SU")
    an_prec = annee_factory("2024-2025")
    an_cour = annee_factory("2025-2026")
    tc_factory(ndk.id, "3B")

    p_su = personne_factory(site_id=su.id, login="su1")
    snap_factory(p_su.id, an_cour.id, classe="61")

    plan = construire_plan(
        session, site_id=ndk.id, type_personne="eleve",
        annee_cible_id=an_cour.id, annee_source_id=an_prec.id,
        mots_de_passe={"su1": "pwd"},
    )
    assert plan.nb_total == 0


def test_plan_site_introuvable(session, annee_factory):
    from backend.services.google_api import construire_plan

    an = annee_factory("2025-2026")
    with pytest.raises(ValueError, match="Site introuvable"):
        construire_plan(
            session, site_id=99999, type_personne="eleve",
            annee_cible_id=an.id, annee_source_id=an.id,
        )


def test_client_refuse_config_incomplete(session):
    """L'erreur de configuration est levée à la construction, pas au 1er appel."""
    from backend.services.google_api import ClientGoogle, charger_config

    with pytest.raises(ValueError):
        ClientGoogle(charger_config(session))
