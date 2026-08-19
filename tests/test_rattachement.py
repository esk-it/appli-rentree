"""Tests du rattachement site ↔ classe, pour une année donnée."""
from __future__ import annotations

import csv
import io

import pytest


@pytest.fixture()
def snap_factory(session):
    from backend.models import Snapshot

    def _creer(personne_id, annee_id, **kwargs):
        defaults = {"nom": "MARTIN", "prenom": "Jean", "classe": "31"}
        defaults.update(kwargs)
        s = Snapshot(personne_id=personne_id, annee_scolaire_id=annee_id, **defaults)
        session.add(s)
        session.commit()
        return s

    return _creer


@pytest.fixture()
def deux_sites(session, site_factory):
    """SU (collège) et NDK (lycée), avec une classe déclarée pour chacun."""
    from backend.models import TableCorrespondance

    su = site_factory("SU")
    ndk = site_factory("NDK")
    session.add_all([
        TableCorrespondance(
            site_id=su.id, classe_charlemagne_long="TROISIEME 6",
            classe_code_court="36",
            ou_pre_rentree="/4. SU/SU2026", ou_definitive="/4. SU/SU2026/36",
        ),
        TableCorrespondance(
            site_id=ndk.id, classe_charlemagne_long="SECONDE 1",
            classe_code_court="2_1",
            ou_pre_rentree="/3. NDK/NDK2026", ou_definitive="/3. NDK/NDK2026/2_1",
        ),
    ])
    session.commit()
    return {"su": su, "ndk": ndk}


def test_eleve_suit_le_site_de_sa_classe(
    session, deux_sites, annee_factory, personne_factory, snap_factory
):
    """La 3e de SU qui monte en 2nde compte pour NDK, pas pour SU."""
    from backend.services.rattachement import ids_personnes_du_site

    annee = annee_factory("2026-2027")
    p = personne_factory(
        nom="BERTEVAS", prenom="Zoé", login="zbertevas",
        site_id=deux_sites["su"].id,  # état courant : encore au collège
    )
    snap_factory(p.id, annee.id, classe="2_1")

    ndk = ids_personnes_du_site(
        session, site_id=deux_sites["ndk"].id, annee_id=annee.id, type_personne="eleve"
    )
    su = ids_personnes_du_site(
        session, site_id=deux_sites["su"].id, annee_id=annee.id, type_personne="eleve"
    )
    assert p.id in ndk
    assert p.id not in su


def test_annee_precedente_donne_lancien_site(
    session, deux_sites, annee_factory, personne_factory, snap_factory
):
    """Le rattachement dépend de l'année : la même élève était à SU avant."""
    from backend.services.rattachement import ids_personnes_du_site

    prec = annee_factory("2025-2026")
    cour = annee_factory("2026-2027")
    p = personne_factory(nom="B", prenom="Z", login="zb", site_id=deux_sites["su"].id)
    snap_factory(p.id, prec.id, classe="36")
    snap_factory(p.id, cour.id, classe="2_1")

    assert p.id in ids_personnes_du_site(
        session, site_id=deux_sites["su"].id, annee_id=prec.id, type_personne="eleve"
    )
    assert p.id in ids_personnes_du_site(
        session, site_id=deux_sites["ndk"].id, annee_id=cour.id, type_personne="eleve"
    )


def test_classe_inconnue_retombe_sur_le_site_enregistre(
    session, deux_sites, annee_factory, personne_factory, snap_factory
):
    """Mieux vaut un export imparfait qu'une disparition silencieuse."""
    from backend.services.rattachement import ids_personnes_du_site

    annee = annee_factory("2026-2027")
    p = personne_factory(nom="X", prenom="Y", login="xy", site_id=deux_sites["su"].id)
    snap_factory(p.id, annee.id, classe="4Z")  # hors table

    assert p.id in ids_personnes_du_site(
        session, site_id=deux_sites["su"].id, annee_id=annee.id, type_personne="eleve"
    )


def test_classe_ambigue_retombe_sur_le_site_enregistre(
    session, deux_sites, annee_factory, personne_factory, snap_factory
):
    from backend.models import TableCorrespondance
    from backend.services.rattachement import ids_personnes_du_site, site_par_classe

    for s in (deux_sites["su"], deux_sites["ndk"]):
        session.add(
            TableCorrespondance(
                site_id=s.id, classe_charlemagne_long="AMBIGU",
                classe_code_court="AMB",
                ou_pre_rentree=f"/{s.nom}", ou_definitive=f"/{s.nom}/AMB",
            )
        )
    session.commit()
    assert "AMB" not in site_par_classe(session)

    annee = annee_factory("2026-2027")
    p = personne_factory(nom="X", prenom="Y", login="xy", site_id=deux_sites["su"].id)
    snap_factory(p.id, annee.id, classe="AMB")
    assert p.id in ids_personnes_du_site(
        session, site_id=deux_sites["su"].id, annee_id=annee.id, type_personne="eleve"
    )


def test_adulte_garde_son_site_enregistre(
    session, deux_sites, annee_factory, personne_factory, snap_factory
):
    """Aucune classe, donc rien à déduire — le champ reste l'autorité."""
    from backend.services.rattachement import ids_personnes_du_site

    annee = annee_factory("2026-2027")
    a = personne_factory(
        type="adulte", nom="PROF", prenom="Luc", login="lprof",
        site_id=deux_sites["ndk"].id,
    )
    snap_factory(a.id, annee.id, classe=None)

    assert a.id in ids_personnes_du_site(
        session, site_id=deux_sites["ndk"].id, annee_id=annee.id, type_personne="adulte"
    )
    assert a.id not in ids_personnes_du_site(
        session, site_id=deux_sites["su"].id, annee_id=annee.id, type_personne="adulte"
    )


# ---------------------------------------------------------------------------
# Conséquence sur les exports
# ---------------------------------------------------------------------------


def test_export_koxo_route_selon_la_classe(
    session, deux_sites, annee_factory, personne_factory, snap_factory
):
    """Régression : 143 lycéens partaient sur le serveur KoXo du collège."""
    from backend.services.exports_koxo import generer_csv_koxo

    annee = annee_factory("2026-2027")
    montant = personne_factory(
        nom="BERTEVAS", prenom="Zoé", login="zbertevas", site_id=deux_sites["su"].id
    )
    snap_factory(montant.id, annee.id, nom="BERTEVAS", classe="2_1")
    reste = personne_factory(
        nom="COLLEGE", prenom="Ana", login="acollege", site_id=deux_sites["su"].id
    )
    snap_factory(reste.id, annee.id, nom="COLLEGE", classe="36")

    def logins(site_id):
        contenu, _ = generer_csv_koxo(
            session=session, site_id=site_id, type_personne="eleve",
            categorie="tous", annee_cible_id=annee.id,
        )
        # KoXo attend du cp1252, pas de l'UTF-8
        texte = contenu.decode("cp1252")
        return {r["Identifiant"] for r in csv.DictReader(io.StringIO(texte))}

    assert logins(deux_sites["ndk"].id) == {"zbertevas"}
    assert logins(deux_sites["su"].id) == {"acollege"}


def test_export_google_ou_suit_la_classe(
    session, deux_sites, annee_factory, personne_factory, snap_factory
):
    from backend.services.exports_google import generer_csv_google

    annee = annee_factory("2026-2027")
    p = personne_factory(
        nom="BERTEVAS", prenom="Zoé", login="zbertevas", site_id=deux_sites["su"].id
    )
    snap_factory(p.id, annee.id, nom="BERTEVAS", prenom="Zoé", classe="2_1")

    contenu, rapport = generer_csv_google(
        session=session, site_id=deux_sites["ndk"].id, type_personne="eleve",
        categorie="tous", annee_cible_id=annee.id,
    )
    texte = contenu[3:].decode("utf-8")
    rows = list(csv.DictReader(io.StringIO(texte)))
    assert len(rows) == 1
    assert rows[0]["Org Unit Path [Required]"] == "/3. NDK/NDK2026/2_1"
    assert rapport.nb_sans_ou == 0


# ---------------------------------------------------------------------------
# Entrées / sorties : au niveau de l'établissement, pas du site
# ---------------------------------------------------------------------------


@pytest.fixture()
def montante(session, deux_sites, annee_factory, personne_factory, snap_factory):
    """Une 3e de SU qui monte en 2nde à NDK, présente aux deux années."""
    prec = annee_factory("2025-2026")
    cour = annee_factory("2026-2027")
    p = personne_factory(
        nom="BERTEVAS", prenom="Zoé", login="zbertevas", site_id=deux_sites["su"].id
    )
    snap_factory(p.id, prec.id, nom="BERTEVAS", classe="36")
    snap_factory(p.id, cour.id, nom="BERTEVAS", classe="2_1")
    return {"personne": p, "prec": prec, "cour": cour}


def test_montante_nest_pas_une_sortante_de_son_ancien_site(
    session, deux_sites, montante
):
    """Régression : elle aurait été suspendue et archivée le jour de sa rentrée."""
    from backend.services.exports_koxo import generer_csv_koxo

    _, r = generer_csv_koxo(
        session=session, site_id=deux_sites["su"].id, type_personne="eleve",
        categorie="anciens", annee_cible_id=montante["cour"].id,
        annee_source_id=montante["prec"].id,
    )
    assert r.nb_lignes == 0


def test_montante_nest_pas_une_nouvelle_de_son_nouveau_site(
    session, deux_sites, montante
):
    """Elle a déjà un compte Google : le recréer échouerait."""
    from backend.services.exports_google import generer_csv_google

    _, r = generer_csv_google(
        session=session, site_id=deux_sites["ndk"].id, type_personne="eleve",
        categorie="nouveaux", annee_cible_id=montante["cour"].id,
        annee_source_id=montante["prec"].id,
    )
    assert r.nb_lignes == 0


def test_montante_figure_bien_dans_tous_de_son_nouveau_site(
    session, deux_sites, montante
):
    from backend.services.exports_koxo import generer_csv_koxo

    _, ndk = generer_csv_koxo(
        session=session, site_id=deux_sites["ndk"].id, type_personne="eleve",
        categorie="tous", annee_cible_id=montante["cour"].id,
    )
    _, su = generer_csv_koxo(
        session=session, site_id=deux_sites["su"].id, type_personne="eleve",
        categorie="tous", annee_cible_id=montante["cour"].id,
    )
    assert (ndk.nb_lignes, su.nb_lignes) == (1, 0)


def test_vrai_sortant_reste_detecte(
    session, deux_sites, montante, personne_factory, snap_factory
):
    """Le garde-fou ne doit pas masquer un départ réel."""
    from backend.services.exports_koxo import generer_csv_koxo

    parti = personne_factory(
        nom="PARTI", prenom="Luc", login="lparti", site_id=deux_sites["su"].id
    )
    snap_factory(parti.id, montante["prec"].id, nom="PARTI", classe="36")
    # aucun snapshot dans l'année cible

    _, r = generer_csv_koxo(
        session=session, site_id=deux_sites["su"].id, type_personne="eleve",
        categorie="anciens", annee_cible_id=montante["cour"].id,
        annee_source_id=montante["prec"].id,
    )
    assert r.nb_lignes == 1


def test_vrai_entrant_reste_detecte(
    session, deux_sites, montante, personne_factory, snap_factory
):
    from backend.services.exports_koxo import generer_csv_koxo

    entrant = personne_factory(
        nom="ENTRANT", prenom="Ana", login="aentrant", site_id=deux_sites["ndk"].id
    )
    snap_factory(entrant.id, montante["cour"].id, nom="ENTRANT", classe="2_1")

    _, r = generer_csv_koxo(
        session=session, site_id=deux_sites["ndk"].id, type_personne="eleve",
        categorie="nouveaux", annee_cible_id=montante["cour"].id,
        annee_source_id=montante["prec"].id,
    )
    assert r.nb_lignes == 1
