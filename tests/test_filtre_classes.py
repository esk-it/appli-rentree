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
