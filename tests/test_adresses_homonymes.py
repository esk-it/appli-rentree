"""Deux personnes, une seule adresse.

L'adresse se calcule `prenom.nom@domaine`. Deux personnes du même prénom et
du même nom produisent donc la même. La règle des identifiants sait
suffixer depuis toujours ; celle des adresses ne le savait pas, et l'export
Google d'un entrant portait l'adresse d'un autre élève.
"""
from __future__ import annotations

import pytest


@pytest.fixture()
def snap_factory(session):
    from backend.models import Snapshot

    def _creer(personne_id, annee_id, **kw):
        s = Snapshot(
            personne_id=personne_id, annee_scolaire_id=annee_id,
            nom=kw.pop("nom", "X"), prenom=kw.pop("prenom", "Y"), **kw,
        )
        session.add(s)
        session.commit()
        return s

    return _creer


@pytest.fixture()
def deux_hugo(session, site_factory, annee_factory, personne_factory, snap_factory):
    """Deux Hugo GUILLOU sans lien : un lycéen en place, un entrant."""
    ndk = site_factory("NDK")
    su = site_factory("SU")
    an = annee_factory("2026-2027")
    ancien = personne_factory(
        type="eleve", site_id=ndk.id, id_charlemagne=9148,
        nom="GUILLOU", prenom="Hugo", login="hguillou",
        email_constate="hugo.guillou@lekreisker.fr",
    )
    entrant = personne_factory(
        type="eleve", site_id=su.id, id_charlemagne=9695,
        nom="GUILLOU", prenom="Hugo", login="hguillou2",
    )
    snap_factory(ancien.id, an.id, classe="1_G1")
    snap_factory(entrant.id, an.id, classe="65")
    return an, ancien, entrant


def test_l_homonymie_est_reperee(session, deux_hugo):
    from backend.services.adresses_homonymes import detecter_homonymies

    an, ancien, entrant = deux_hugo
    r = detecter_homonymies(session, annee_id=an.id)
    assert len(r.homonymies) == 1
    h = r.homonymies[0]
    assert h.adresse == "hugo.guillou@lekreisker.fr"
    assert [x.personne_id for x in h.a_trancher] == [entrant.id]


def test_celui_dont_le_compte_existe_garde_son_adresse(session, deux_hugo):
    """C'est là qu'il se connecte : on ne la lui change pas."""
    from backend.services.adresses_homonymes import (
        appliquer_attributions,
        detecter_homonymies,
    )

    an, ancien, entrant = deux_hugo
    r = detecter_homonymies(session, annee_id=an.id)
    assert "compte existe" in r.homonymies[0].motif_du_choix
    appliquer_attributions(session, r, mode="reel")

    session.refresh(ancien)
    session.refresh(entrant)
    assert ancien.email == "hugo.guillou@lekreisker.fr"
    assert entrant.email == "hugo.guillou1@lekreisker.fr"
    assert ancien.email_attribuee is None


def test_le_suffixe_saute_ce_que_google_detient_deja(session, deux_hugo):
    """Un suffixe libre au référentiel mais ouvert dans Google ne sert à rien."""
    from backend.services.adresses_homonymes import detecter_homonymies

    an, _, entrant = deux_hugo
    r = detecter_homonymies(
        session, annee_id=an.id,
        adresses_google={"hugo.guillou1@lekreisker.fr",
                         "hugo.guillou2@lekreisker.fr"},
    )
    assert r.homonymies[0].a_trancher[0].adresse_proposee == (
        "hugo.guillou3@lekreisker.fr"
    )


def test_la_decision_ne_bouge_plus(session, deux_hugo):
    """Un suffixe qui changerait créerait un second compte au lieu du premier."""
    from backend.services.adresses_homonymes import (
        appliquer_attributions,
        detecter_homonymies,
    )

    an, _, entrant = deux_hugo
    appliquer_attributions(
        session, detecter_homonymies(session, annee_id=an.id), mode="reel"
    )
    session.refresh(entrant)
    premier = entrant.email

    # Deuxième passage : plus rien à trancher, et l'adresse tient.
    r = detecter_homonymies(session, annee_id=an.id)
    assert r.nb_a_trancher == 0
    session.refresh(entrant)
    assert entrant.email == premier


def test_la_simulation_n_ecrit_rien(session, deux_hugo):
    from backend.services.adresses_homonymes import (
        appliquer_attributions,
        detecter_homonymies,
    )

    an, _, entrant = deux_hugo
    r = detecter_homonymies(session, annee_id=an.id)
    assert appliquer_attributions(session, r, mode="simulation") == 1
    session.refresh(entrant)
    assert entrant.email_attribuee is None


def test_sans_compte_nulle_part_le_badge_le_plus_ancien_garde_l_adresse(
    session, site_factory, annee_factory, personne_factory, snap_factory
):
    """Il faut une règle ; autant qu'elle soit stable d'une fois sur l'autre."""
    from backend.services.adresses_homonymes import (
        appliquer_attributions,
        detecter_homonymies,
    )

    site = site_factory("NDK")
    an = annee_factory("2026-2027")
    vieux = personne_factory(
        type="eleve", site_id=site.id, id_charlemagne=1000,
        nom="MARTIN", prenom="Louis", login="lmartin",
    )
    jeune = personne_factory(
        type="eleve", site_id=site.id, id_charlemagne=9000,
        nom="MARTIN", prenom="Louis", login="lmartin2",
    )
    snap_factory(vieux.id, an.id, classe="3A")
    snap_factory(jeune.id, an.id, classe="6B")

    r = detecter_homonymies(session, annee_id=an.id)
    appliquer_attributions(session, r, mode="reel")
    session.refresh(vieux)
    session.refresh(jeune)
    assert vieux.email == "louis.martin@lekreisker.fr"
    assert jeune.email == "louis.martin1@lekreisker.fr"


def test_l_export_google_porte_l_adresse_tranchee(session, deux_hugo):
    """C'est là que ça se jouait : Google refuse une adresse déjà prise."""
    import csv
    import io

    from backend.services.adresses_homonymes import (
        appliquer_attributions,
        detecter_homonymies,
    )
    from backend.services.exports_google import generer_csv_google

    an, _, entrant = deux_hugo
    appliquer_attributions(
        session, detecter_homonymies(session, annee_id=an.id), mode="reel"
    )

    contenu, _ = generer_csv_google(
        session, site_id=entrant.site_id, type_personne="eleve",
        categorie="tous", annee_cible_id=an.id,
    )
    lignes = list(csv.DictReader(io.StringIO(contenu.decode("utf-8-sig"))))
    adresses = {l["Email Address [Required]"].lower() for l in lignes}
    assert "hugo.guillou1@lekreisker.fr" in adresses
    assert "hugo.guillou@lekreisker.fr" not in adresses


def test_deux_homonymes_recoivent_des_suffixes_distincts(
    session, site_factory, annee_factory, personne_factory, snap_factory
):
    """Trois du même nom : le second et le troisième ne peuvent pas se
    partager le même numéro."""
    from backend.services.adresses_homonymes import (
        appliquer_attributions,
        detecter_homonymies,
    )

    site = site_factory("NDK")
    an = annee_factory("2026-2027")
    gens = []
    for i, idc in enumerate((1000, 2000, 3000)):
        p = personne_factory(
            type="eleve", site_id=site.id, id_charlemagne=idc,
            nom="MARTIN", prenom="Louis", login=f"lmartin{i or ''}",
        )
        snap_factory(p.id, an.id, classe="3A")
        gens.append(p)

    r = detecter_homonymies(session, annee_id=an.id)
    appliquer_attributions(session, r, mode="reel")
    for p in gens:
        session.refresh(p)
    assert len({p.email for p in gens}) == 3
