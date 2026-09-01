"""Ce que la rentrée a produit, confronté à ce qu'elle visait.

Chaque étape rend son compte rendu, et chacun est vrai dans son coin.
Aucun ne répond à la question qu'on se pose une fois tout lancé : est-ce
que tout le monde est en place ?
"""
from __future__ import annotations

import pytest


@pytest.fixture()
def tc_factory(session):
    from backend.models import TableCorrespondance

    def _creer(site_id, code):
        t = TableCorrespondance(
            site_id=site_id, classe_charlemagne_long=f"CLASSE {code}",
            classe_code_court=code,
            ou_pre_rentree="/NDK/attente",
            ou_definitive=f"/NDK/{code}",
            groupe_google=f"{code.lower()}@lekreisker.fr",
        )
        session.add(t)
        session.commit()
        return t

    return _creer


@pytest.fixture()
def eleve_factory(session, personne_factory):
    from backend.models import Snapshot

    compteur = {"n": 0}

    def _creer(site_id, annee_id, classe, **kw):
        compteur["n"] += 1
        p = personne_factory(
            type="eleve", site_id=site_id,
            id_charlemagne=kw.pop("id_charlemagne", 9000 + compteur["n"]),
            nom=kw.pop("nom", f"NOM{compteur['n']}"),
            prenom=kw.pop("prenom", "Test"),
            login=kw.pop("login", f"t{compteur['n']}"),
            **kw,
        )
        session.add(
            Snapshot(personne_id=p.id, annee_scolaire_id=annee_id,
                     nom=p.nom, prenom=p.prenom, classe=classe)
        )
        p.classe = classe
        session.commit()
        return p

    return _creer


@pytest.fixture()
def etab(session, site_factory, annee_factory, tc_factory):
    site = site_factory("NDK")
    an = annee_factory("2026-2027")
    tc_factory(site.id, "61")
    tc_factory(site.id, "62")
    return site, an


def _compte(p, ou, **kw):
    return {
        "email": (p.email or "").lower(), "alias": [], "ou": ou,
        "suspendu": kw.get("suspendu", False),
        "nom": p.nom, "prenom": p.prenom,
        "id_externe": kw.get("id_externe", str(p.id_charlemagne)),
    }


# ---------------------------------------------------------------------------
# Le cas où tout va bien
# ---------------------------------------------------------------------------


def test_une_rentree_complete_ne_signale_rien(session, etab, eleve_factory):
    from backend.services.bilan_rentree import dresser_bilan

    site, an = etab
    p = eleve_factory(site.id, an.id, "61")
    bilan = dresser_bilan(
        session, [_compte(p, "/NDK/61")],
        {"61@lekreisker.fr": [p.email], "62@lekreisker.fr": []},
        annee_id=an.id,
    )
    assert bilan.tout_est_en_place
    assert bilan.chiffres.inscrits == 1
    assert bilan.chiffres.avec_compte == 1
    assert bilan.chiffres.en_ou_definitive == 1
    assert bilan.chiffres.dans_leur_groupe == 1


def test_un_eleve_encore_en_attente_n_est_pas_un_ecart(
    session, etab, eleve_factory
):
    """Il n'est pas mal rangé : il n'est pas encore basculé."""
    from backend.services.bilan_rentree import dresser_bilan

    site, an = etab
    p = eleve_factory(site.id, an.id, "61")
    bilan = dresser_bilan(
        session, [_compte(p, "/NDK/attente")],
        {"61@lekreisker.fr": [p.email]}, annee_id=an.id,
    )
    assert not any(c.genre == "ou_inattendue" for c in bilan.constats)
    assert bilan.chiffres.en_ou_attente == 1


# ---------------------------------------------------------------------------
# Les écarts
# ---------------------------------------------------------------------------


def test_un_eleve_sans_compte_est_bloquant(session, etab, eleve_factory):
    """Il ne pourra pas se connecter : rien n'est plus urgent."""
    from backend.services.bilan_rentree import dresser_bilan

    site, an = etab
    p = eleve_factory(site.id, an.id, "61")
    bilan = dresser_bilan(session, [], {}, annee_id=an.id)
    c = next(c for c in bilan.constats if c.genre == "compte_absent")
    assert c.gravite == "bloquant"
    assert "Arrivée" in c.geste
    assert bilan.chiffres.sans_compte == 1


def test_un_compte_suspendu_est_signale(session, etab, eleve_factory):
    from backend.services.bilan_rentree import dresser_bilan

    site, an = etab
    p = eleve_factory(site.id, an.id, "61")
    bilan = dresser_bilan(
        session, [_compte(p, "/NDK/61", suspendu=True)],
        {"61@lekreisker.fr": [p.email]}, annee_id=an.id,
    )
    assert any(c.genre == "compte_suspendu" for c in bilan.constats)


def test_une_unite_inattendue_est_signalee(session, etab, eleve_factory):
    from backend.services.bilan_rentree import dresser_bilan

    site, an = etab
    p = eleve_factory(site.id, an.id, "61")
    bilan = dresser_bilan(
        session, [_compte(p, "/NDK/62")],
        {"61@lekreisker.fr": [p.email]}, annee_id=an.id,
    )
    c = next(c for c in bilan.constats if c.genre == "ou_inattendue")
    assert "/NDK/62" in c.detail


def test_l_absence_du_groupe_de_sa_classe_est_signalee(
    session, etab, eleve_factory
):
    from backend.services.bilan_rentree import dresser_bilan

    site, an = etab
    p = eleve_factory(site.id, an.id, "61")
    bilan = dresser_bilan(
        session, [_compte(p, "/NDK/61")],
        {"61@lekreisker.fr": [], "62@lekreisker.fr": []}, annee_id=an.id,
    )
    assert any(c.genre == "groupe_manquant" for c in bilan.constats)


def test_le_groupe_d_une_autre_classe_est_signale(session, etab, eleve_factory):
    """Il lit ce qui ne le regarde pas — et l'ancienne classe le croit encore."""
    from backend.services.bilan_rentree import dresser_bilan

    site, an = etab
    p = eleve_factory(site.id, an.id, "61")
    bilan = dresser_bilan(
        session, [_compte(p, "/NDK/61")],
        {"61@lekreisker.fr": [p.email], "62@lekreisker.fr": [p.email]},
        annee_id=an.id,
    )
    c = next(c for c in bilan.constats if c.genre == "groupe_en_trop")
    assert "62@lekreisker.fr" in c.detail


def test_un_identifiant_charlemagne_discordant_est_bloquant(
    session, etab, eleve_factory
):
    """C'est ce qui a trahi le compte écrasé par l'import d'un homonyme."""
    from backend.services.bilan_rentree import dresser_bilan

    site, an = etab
    p = eleve_factory(site.id, an.id, "61", id_charlemagne=8148)
    bilan = dresser_bilan(
        session, [_compte(p, "/NDK/61", id_externe="8695")],
        {"61@lekreisker.fr": [p.email]}, annee_id=an.id,
    )
    c = next(c for c in bilan.constats if c.genre == "identifiant_discordant")
    assert c.gravite == "bloquant"
    assert "8695" in c.detail and "8148" in c.detail


def test_un_compte_sans_identifiant_externe_ne_declenche_rien(
    session, etab, eleve_factory
):
    """Beaucoup de comptes anciens n'en portent pas : ce n'est pas un écart."""
    from backend.services.bilan_rentree import dresser_bilan

    site, an = etab
    p = eleve_factory(site.id, an.id, "61")
    bilan = dresser_bilan(
        session, [_compte(p, "/NDK/61", id_externe=None)],
        {"61@lekreisker.fr": [p.email]}, annee_id=an.id,
    )
    assert not any(c.genre == "identifiant_discordant" for c in bilan.constats)


def test_un_inscrit_sans_classe_est_bloquant(session, etab, eleve_factory):
    """Ni unité ni groupe ne sont calculables pour lui."""
    from backend.services.bilan_rentree import dresser_bilan

    site, an = etab
    p = eleve_factory(site.id, an.id, None)
    bilan = dresser_bilan(session, [_compte(p, "/NDK/attente")], {}, annee_id=an.id)
    c = next(c for c in bilan.constats if c.genre == "sans_classe")
    assert c.gravite == "bloquant"


# ---------------------------------------------------------------------------
# Les sortants
# ---------------------------------------------------------------------------


def test_un_sortant_encore_range_avec_les_inscrits_est_signale(
    session, site_factory, annee_factory, tc_factory, eleve_factory
):
    from backend.models import Snapshot
    from backend.services.bilan_rentree import dresser_bilan

    site = site_factory("NDK")
    passee = annee_factory("2025-2026")
    an = annee_factory("2026-2027")
    tc_factory(site.id, "61")
    parti = eleve_factory(site.id, passee.id, "61", nom="PARTI")

    bilan = dresser_bilan(
        session, [_compte(parti, "/NDK/61")], {},
        annee_id=an.id, annee_source_id=passee.id,
    )
    # Une tâche, pas un problème par personne : ils relèvent tous du même
    # geste, et les énumérer écraserait le reste du bilan.
    r = next(x for x in bilan.restes if x.genre == "sortants_a_ranger")
    assert r.nombre == 1
    assert "PARTI" in r.exemples[0]
    assert not any(c.genre == "sortant_dans_arbre_actif" for c in bilan.constats)


def test_un_sortant_deja_en_unite_de_sortie_ne_l_est_pas(
    session, site_factory, annee_factory, tc_factory, eleve_factory
):
    from backend.services.bilan_rentree import dresser_bilan

    site = site_factory("NDK")
    passee = annee_factory("2025-2026")
    an = annee_factory("2026-2027")
    tc_factory(site.id, "61")
    parti = eleve_factory(site.id, passee.id, "61", nom="PARTI")

    bilan = dresser_bilan(
        session, [_compte(parti, "/7. Sortis/Comptes à supprimer")], {},
        annee_id=an.id, annee_source_id=passee.id,
    )
    assert not any(x.genre == "sortants_a_ranger" for x in bilan.restes)


def test_sans_annee_source_le_controle_des_sortants_est_omis(
    session, site_factory, annee_factory, tc_factory, eleve_factory
):
    """Omis plutôt que rendu faux : sans référent, personne n'est « parti »."""
    from backend.services.bilan_rentree import dresser_bilan

    site = site_factory("NDK")
    passee = annee_factory("2025-2026")
    an = annee_factory("2026-2027")
    tc_factory(site.id, "61")
    parti = eleve_factory(site.id, passee.id, "61", nom="PARTI")

    bilan = dresser_bilan(session, [_compte(parti, "/NDK/61")], {}, annee_id=an.id)
    assert bilan.restes == []


# ---------------------------------------------------------------------------
# La lecture du bilan
# ---------------------------------------------------------------------------


def test_les_bloquants_viennent_en_tete(session, etab, eleve_factory):
    """On lit d'abord ce qui empêche quelqu'un de se connecter."""
    from backend.services.bilan_rentree import dresser_bilan

    site, an = etab
    absent = eleve_factory(site.id, an.id, "61", nom="ABSENT")
    mal_range = eleve_factory(site.id, an.id, "61", nom="RANGE")
    bilan = dresser_bilan(
        session, [_compte(mal_range, "/NDK/62")],
        {"61@lekreisker.fr": [mal_range.email]}, annee_id=an.id,
    )
    assert bilan.constats[0].gravite == "bloquant"
    assert bilan.nb_bloquants >= 1 and bilan.nb_attention >= 1


def test_chaque_constat_porte_le_geste_a_faire(session, etab, eleve_factory):
    """Un bilan qui ne dit pas quoi faire se relit une fois puis s'ignore."""
    from backend.services.bilan_rentree import dresser_bilan

    site, an = etab
    eleve_factory(site.id, an.id, "61")
    bilan = dresser_bilan(session, [], {}, annee_id=an.id)
    assert bilan.constats
    assert all(c.geste.strip() for c in bilan.constats)


def test_un_alias_vaut_l_adresse_du_compte(session, etab, eleve_factory):
    """Un compte répond à ses alias : le référentiel peut porter l'un d'eux."""
    from backend.services.bilan_rentree import dresser_bilan

    site, an = etab
    p = eleve_factory(site.id, an.id, "61")
    compte = _compte(p, "/NDK/61")
    compte["alias"] = [compte["email"]]
    compte["email"] = "autre.forme@lekreisker.fr"
    bilan = dresser_bilan(
        session, [compte], {"61@lekreisker.fr": [p.email]}, annee_id=an.id,
    )
    assert not any(c.genre == "compte_absent" for c in bilan.constats)


def test_le_bilan_se_restreint_a_un_site(
    session, site_factory, annee_factory, tc_factory, eleve_factory
):
    from backend.services.bilan_rentree import dresser_bilan

    ndk = site_factory("NDK")
    su = site_factory("SU")
    an = annee_factory("2026-2027")
    tc_factory(ndk.id, "61")
    tc_factory(su.id, "31")
    eleve_factory(ndk.id, an.id, "61", nom="ANDK")
    eleve_factory(su.id, an.id, "31", nom="ASU")

    bilan = dresser_bilan(session, [], {}, annee_id=an.id, site_id=su.id)
    assert bilan.chiffres.inscrits == 1
    assert {c.nom for c in bilan.constats} == {"ASU"}


# ---------------------------------------------------------------------------
# Une étape non faite n'est pas une erreur
# ---------------------------------------------------------------------------


def test_un_eleve_en_attente_n_est_pas_signale_hors_de_son_groupe(
    session, etab, eleve_factory
):
    """Tant qu'il attend, ne pas être dans sa liste est l'état voulu — c'est
    même ce qui empêche sa classe de transparaître avant l'heure."""
    from backend.services.bilan_rentree import dresser_bilan

    site, an = etab
    p = eleve_factory(site.id, an.id, "61")
    bilan = dresser_bilan(
        session, [_compte(p, "/NDK/attente")],
        {"61@lekreisker.fr": []}, annee_id=an.id,
    )
    assert not any(c.genre == "groupe_manquant" for c in bilan.constats)
    r = next(x for x in bilan.restes if x.genre == "a_basculer")
    assert r.nombre == 1


def test_un_eleve_bascule_hors_de_son_groupe_est_bien_signale(
    session, etab, eleve_factory
):
    """Là, l'étape a été faite et quelqu'un manque : c'est un écart."""
    from backend.services.bilan_rentree import dresser_bilan

    site, an = etab
    p = eleve_factory(site.id, an.id, "61")
    bilan = dresser_bilan(
        session, [_compte(p, "/NDK/61")],
        {"61@lekreisker.fr": []}, annee_id=an.id,
    )
    assert any(c.genre == "groupe_manquant" for c in bilan.constats)
    assert not any(x.genre == "a_basculer" for x in bilan.restes)


def test_les_restes_portent_des_exemples_et_un_geste(session, etab, eleve_factory):
    from backend.services.bilan_rentree import dresser_bilan

    site, an = etab
    for i in range(3):
        p = eleve_factory(site.id, an.id, "61", nom=f"ATTENTE{i}")
        globals().setdefault("_", None)
    comptes = [
        _compte(x, "/NDK/attente")
        for x in session.query(type(p)).filter_by(type="eleve").all()
    ]
    bilan = dresser_bilan(session, comptes, {}, annee_id=an.id)
    r = next(x for x in bilan.restes if x.genre == "a_basculer")
    assert r.nombre == 3
    assert r.exemples and r.geste.strip()
