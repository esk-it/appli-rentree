"""Basculer et composer par paquets, plutôt que tout d'un bloc.

Mille sept cents élèves d'un coup supposent d'avoir tout vérifié d'un
coup. En pratique on veut avancer classe par classe — et surtout pouvoir
relire un paquet de taille humaine avant de le lancer.

Le déplacement d'une unité d'organisation est indépendant d'un élève à
l'autre : le découpage ne coûte rien. Ce n'est pas vrai des groupes, où
changer de classe est deux gestes.
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
            ou_pre_rentree="/3. NDK/NDK2027",
            ou_definitive=f"/3. NDK/NDK2027/{code}",
            groupe_google=f"{code.lower()}@lekreisker.fr",
        )
        session.add(t)
        session.commit()
        return t

    return _creer


@pytest.fixture()
def promo(session, site_factory, annee_factory, personne_factory, tc_factory):
    """Deux sixièmes, deux secondes, un élève dans chacune."""
    from backend.models import Snapshot

    site = site_factory("NDK")
    an = annee_factory("2026-2027")
    gens = {}
    for i, code in enumerate(("61", "62", "2_1", "2_2")):
        tc_factory(site.id, code)
        p = personne_factory(
            type="eleve", site_id=site.id, id_charlemagne=7000 + i,
            nom=f"ELEVE{i}", prenom="Test", login=f"televe{i}",
        )
        session.add(
            Snapshot(personne_id=p.id, annee_scolaire_id=an.id,
                     nom=p.nom, prenom=p.prenom, classe=code)
        )
        gens[code] = p
    session.commit()
    return site, an, gens


# ---------------------------------------------------------------------------
# La bascule
# ---------------------------------------------------------------------------


def test_la_bascule_se_limite_aux_classes_choisies(session, promo):
    from backend.services.bascule import planifier_bascule

    site, an, gens = promo
    r = planifier_bascule(
        session, annee_id=an.id, phase="definitive", classes=["61", "2_1"],
    )
    assert {m.classe for m in r.mouvements} == {"61", "2_1"}
    assert r.classes == ["2_1", "61"]


def test_sans_filtre_toutes_les_classes_sont_la(session, promo):
    from backend.services.bascule import planifier_bascule

    site, an, gens = promo
    r = planifier_bascule(session, annee_id=an.id, phase="definitive")
    assert {m.classe for m in r.mouvements} == {"61", "62", "2_1", "2_2"}
    assert r.classes == []


def test_un_filtre_vide_vaut_pas_de_filtre(session, promo):
    """Une liste vide venue de l'interface ne doit pas tout écarter."""
    from backend.services.bascule import planifier_bascule

    site, an, gens = promo
    r = planifier_bascule(
        session, annee_id=an.id, phase="definitive", classes=[],
    )
    assert len(r.mouvements) == 4


def test_le_plan_google_porte_le_meme_filtre_que_l_apercu(session, promo):
    """Ce qu'on a relu est exactement ce qui part."""
    from backend.services.google_api import construire_plan

    site, an, gens = promo
    plan = construire_plan(
        session, site_id=site.id, type_personne="eleve",
        annee_cible_id=an.id, phase="definitive", classes=["61"],
    )
    vises = {op.ou_visee for op in plan.operations if op.ou_visee}
    assert vises == {"/3. NDK/NDK2027/61"}


# ---------------------------------------------------------------------------
# Les groupes
# ---------------------------------------------------------------------------


def test_les_groupes_se_limitent_aux_classes_choisies(session, promo):
    from backend.services.groupes_google import calculer_diff_groupes

    site, an, gens = promo
    membres = {f"{c}@lekreisker.fr": [] for c in ("61", "62", "2_1", "2_2")}
    r = calculer_diff_groupes(
        session, membres, annee_id=an.id, classes=["61", "2_1"],
    )
    assert {d.classe for d in r.diffs} == {"61", "2_1"}
    assert r.classes == ["2_1", "61"]


def test_un_eleve_laisse_dans_deux_listes_est_signale(session, promo):
    """Changer de classe est deux gestes ; un filtre peut n'en retenir qu'un."""
    from backend.services.groupes_google import calculer_diff_groupes

    site, an, gens = promo
    monte = gens["61"]
    # Il est encore membre de 62, sa classe de l'an dernier.
    membres = {
        "61@lekreisker.fr": [],
        "62@lekreisker.fr": [monte.email],
        "2_1@lekreisker.fr": [],
        "2_2@lekreisker.fr": [],
    }
    r = calculer_diff_groupes(session, membres, annee_id=an.id, classes=["61"])
    assert any("deux listes" in a for a in r.avertissements)
    assert any("62" in a for a in r.avertissements)


def test_sans_filtre_les_deux_gestes_se_font(session, promo):
    """Le cas normal : l'ajout et le retrait tombent dans le même passage."""
    from backend.services.groupes_google import calculer_diff_groupes

    site, an, gens = promo
    monte = gens["61"]
    membres = {
        "61@lekreisker.fr": [],
        "62@lekreisker.fr": [monte.email],
        "2_1@lekreisker.fr": [],
        "2_2@lekreisker.fr": [],
    }
    r = calculer_diff_groupes(session, membres, annee_id=an.id)
    ajout = next(d for d in r.diffs if d.classe == "61")
    retrait = next(d for d in r.diffs if d.classe == "62")
    assert monte.email in ajout.a_ajouter
    assert monte.email in retrait.a_retirer
    assert not any("deux listes" in a for a in r.avertissements)


def test_l_adresse_attribuee_est_celle_du_groupe(
    session, promo, personne_factory
):
    """Recalculer en sautant l'adresse attribuée ajoutait celle de l'homonyme."""
    from backend.models import Snapshot
    from backend.services.groupes_google import calculer_diff_groupes

    site, an, gens = promo
    homonyme = personne_factory(
        type="eleve", site_id=site.id, id_charlemagne=7100,
        nom="ELEVE0", prenom="Test", login="televe0b",
    )
    homonyme.email_attribuee = "test.eleve01@lekreisker.fr"
    session.add(
        Snapshot(personne_id=homonyme.id, annee_scolaire_id=an.id,
                 nom=homonyme.nom, prenom=homonyme.prenom, classe="61")
    )
    session.commit()

    r = calculer_diff_groupes(
        session, {"61@lekreisker.fr": []}, annee_id=an.id, classes=["61"],
    )
    d = next(x for x in r.diffs if x.classe == "61")
    assert "test.eleve01@lekreisker.fr" in d.a_ajouter


# ---------------------------------------------------------------------------
# Les trois sites d'un coup
# ---------------------------------------------------------------------------


def test_le_plan_google_accepte_les_trois_sites(
    session, site_factory, annee_factory, personne_factory, tc_factory
):
    """L'écran propose « Les trois sites » et envoyait alors `null` sur un
    champ obligatoire : le bouton répondait 422 sans rien expliquer."""
    from backend.models import Snapshot
    from backend.routers.google_api import PlanPayload, _construire

    ndk = site_factory("NDK")
    su = site_factory("SU")
    an = annee_factory("2026-2027")
    for site, code in ((ndk, "2_1"), (su, "61")):
        t = tc_factory(site.id, code)
        t.ou_pre_rentree = f"/{site.nom}/attente"
        t.ou_definitive = f"/{site.nom}/{code}"
        p = personne_factory(
            type="eleve", site_id=site.id, id_charlemagne=8000 + site.id,
            nom=f"X{site.nom}", prenom="Test", login=f"t{site.nom.lower()}",
        )
        session.add(
            Snapshot(personne_id=p.id, annee_scolaire_id=an.id,
                     nom=p.nom, prenom=p.prenom, classe=code)
        )
    session.commit()

    plan = _construire(
        session,
        PlanPayload(
            site_id=None, type_personne="eleve",
            annee_cible_id=an.id, phase="definitive",
        ),
    )
    vises = {op.ou_visee for op in plan.operations if op.ou_visee}
    assert vises == {"/NDK/2_1", "/SU/61"}


def test_le_filtre_de_classes_traverse_les_trois_sites(
    session, site_factory, annee_factory, personne_factory, tc_factory
):
    from backend.models import Snapshot
    from backend.routers.google_api import PlanPayload, _construire

    ndk = site_factory("NDK")
    su = site_factory("SU")
    an = annee_factory("2026-2027")
    for site, code in ((ndk, "2_1"), (su, "61")):
        t = tc_factory(site.id, code)
        t.ou_definitive = f"/{site.nom}/{code}"
        p = personne_factory(
            type="eleve", site_id=site.id, id_charlemagne=8100 + site.id,
            nom=f"Y{site.nom}", prenom="Test", login=f"y{site.nom.lower()}",
        )
        session.add(
            Snapshot(personne_id=p.id, annee_scolaire_id=an.id,
                     nom=p.nom, prenom=p.prenom, classe=code)
        )
    session.commit()

    plan = _construire(
        session,
        PlanPayload(
            site_id=None, type_personne="eleve", annee_cible_id=an.id,
            phase="definitive", classes=["61"],
        ),
    )
    vises = {op.ou_visee for op in plan.operations if op.ou_visee}
    assert vises == {"/SU/61"}


def test_un_avertissement_commun_n_est_pas_repete_par_site(
    session, site_factory, annee_factory, personne_factory, tc_factory
):
    """« Aucune année de référence » sortait trois fois, une par site."""
    from backend.models import Snapshot
    from backend.routers.google_api import PlanPayload, _construire

    for nom in ("NDK", "SU", "NDE"):
        site = site_factory(nom)
        t = tc_factory(site.id, "61")
        t.ou_definitive = f"/{nom}/61"
    an = annee_factory("2026-2027")
    plan = _construire(
        session,
        PlanPayload(site_id=None, type_personne="eleve",
                    annee_cible_id=an.id, phase="definitive"),
    )
    assert len(plan.avertissements) == len(set(plan.avertissements))


def test_la_synchro_des_groupes_accepte_le_filtre_de_classes():
    """Le champ avait été posé sur le mauvais payload.

    `synchroniser_groupes` lisait `payload.classes` sur un modèle qui ne
    le déclarait pas : 500 au clic sur Synchroniser, alors que l'aperçu
    juste au-dessus fonctionnait. Les deux doivent porter le même filtre,
    sans quoi on applique autre chose que ce qu'on a relu.
    """
    import inspect

    from backend.routers import google_api
    from backend.routers.google_api import SyncGroupesPayload

    p = SyncGroupesPayload(annee_id=1, classes=["61", "2_1"])
    assert p.classes == ["61", "2_1"]
    assert SyncGroupesPayload(annee_id=1).classes is None

    # Et le corps de l'endpoint lit bien ce champ-là.
    source = inspect.getsource(google_api.synchroniser_groupes)
    assert "payload.classes" in source
