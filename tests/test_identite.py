"""Corriger le nom ou le prénom au référentiel.

Ce que Charlemagne écrit faisait foi, et rien ne permettait de le
contredire. Or il se trompe, ou il est en retard : un professeur inscrit
sous « Efflam » se prénomme « Imhotep », le compte Google a été corrigé le
jour même, et chaque export réécrivait l'ancien.
"""
from __future__ import annotations

import pytest


@pytest.fixture()
def prof(session, site_factory, personne_factory):
    site = site_factory("NDK")
    return personne_factory(
        type="adulte", site_id=site.id, id_charlemagne=686,
        nom="PARMENTIER", prenom="Efflam", login="eparmentie",
    )


def test_le_prenom_corrige_entraine_l_adresse_calculee(session, prof):
    """C'est souvent le but : `imhotep.parmentier@` est l'adresse réelle."""
    from backend.services.identite import modifier_identite

    assert prof.email == "efflam.parmentier@lekreisker.fr"
    r = modifier_identite(session, prof.id, prenom="Imhotep", mode="reel")
    session.refresh(prof)
    assert prof.prenom == "Imhotep"
    assert prof.email == "imhotep.parmentier@lekreisker.fr"
    assert r.email_apres == "imhotep.parmentier@lekreisker.fr"


def test_l_identifiant_ne_bouge_pas(session, prof):
    """Le changer ferait renommer le compte de l'annuaire — profil compris."""
    from backend.services.identite import modifier_identite

    r = modifier_identite(session, prof.id, prenom="Imhotep", mode="reel")
    session.refresh(prof)
    assert prof.login == "eparmentie"
    assert r.login == "eparmentie"
    assert any("ne change pas" in x for x in r.reste_a_faire)


def test_une_adresse_constatee_ne_suit_pas_le_renommage(
    session, site_factory, personne_factory
):
    """Elle a été relevée dans Google : un prénom corrigé ne la défait pas."""
    from backend.services.identite import modifier_identite

    site = site_factory("NDK")
    p = personne_factory(
        type="adulte", site_id=site.id, id_charlemagne=690,
        nom="ROUXEL", prenom="Eve", login="erouxel",
        email_constate="eve.despre@lekreisker.fr",
    )
    r = modifier_identite(session, p.id, nom="DESPRE", mode="reel")
    session.refresh(p)
    assert p.email == "eve.despre@lekreisker.fr"
    assert any("ne suit pas" in x for x in r.reste_a_faire)


def test_la_simulation_montre_sans_ecrire(session, prof):
    from backend.services.identite import modifier_identite

    r = modifier_identite(session, prof.id, prenom="Imhotep", mode="simulation")
    session.refresh(prof)
    assert prof.prenom == "Efflam"
    assert r.email_apres == "imhotep.parmentier@lekreisker.fr"
    assert any("Prénom" in c for c in r.changements)


def test_sans_changement_rien_n_est_signale(session, prof):
    from backend.services.identite import modifier_identite

    r = modifier_identite(session, prof.id, prenom="Efflam", mode="reel")
    assert r.changements == []
    assert not r.a_change


def test_un_nom_vide_est_refuse(session, prof):
    from backend.services.identite import ModificationImpossible, modifier_identite

    with pytest.raises(ModificationImpossible, match="requis"):
        modifier_identite(session, prof.id, prenom="   ", mode="reel")


def test_le_rappel_de_charlemagne_est_toujours_donne(session, prof):
    """Une réingestion réécrira depuis la source : la correction est à refaire."""
    from backend.services.identite import modifier_identite

    r = modifier_identite(session, prof.id, prenom="Imhotep", mode="simulation")
    assert any("Charlemagne" in x for x in r.reste_a_faire)


def test_l_export_koxo_porte_le_nom_corrige(
    session, prof, annee_factory, site_factory
):
    """Les colonnes Nom et Prénom viennent de la personne, pas de la
    photographie : la synchronisation mettra le compte à jour."""
    import csv
    import io

    from backend.models import Snapshot
    from backend.services.exports_koxo import generer_csv_koxo
    from backend.services.identite import modifier_identite

    an = annee_factory("2026-2027")
    session.add(
        Snapshot(personne_id=prof.id, annee_scolaire_id=an.id,
                 nom="PARMENTIER", prenom="Efflam", matieres="SES")
    )
    session.commit()

    modifier_identite(session, prof.id, prenom="Imhotep", mode="reel")
    contenu, _ = generer_csv_koxo(
        session, site_id=prof.site_id, type_personne="adulte",
        categorie="tous", annee_cible_id=an.id,
    )
    lignes = list(csv.DictReader(io.StringIO(contenu.decode("cp1252", "replace"))))
    ligne = next(l for l in lignes if l["Nom"] == "PARMENTIER")
    assert ligne["Prénom"] == "Imhotep"
    # L'identifiant, lui, reste celui que KoXo connaît.
    assert ligne["Identifiant"] == "eparmentie"
