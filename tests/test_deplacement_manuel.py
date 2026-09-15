"""Tests du déplacement choisi : une personne, une classe, une sélection.

Ce qui distingue ce module de la bascule, c'est que la destination vient de
l'utilisateur. Les tests portent donc surtout sur ce qui protège d'une
destination mal choisie, et sur le fait qu'un plan n'annonce que ce qu'il
applique vraiment.
"""
from __future__ import annotations

import pytest


@pytest.fixture()
def contexte(session, site_factory, annee_factory, personne_factory):
    """Un site, une année, et de quoi fabriquer des élèves adressés."""
    from backend.models import Snapshot

    site = site_factory("NDK")
    annee = annee_factory("2026-2027")

    def _eleve(nom, prenom, classe="2_5", **kw):
        p = personne_factory(
            nom=nom,
            prenom=prenom,
            site_id=site.id,
            email_constate=kw.pop(
                "email", f"{prenom.lower()}.{nom.lower()}@lekreisker.fr"
            ),
            **kw,
        )
        session.add(
            Snapshot(
                personne_id=p.id,
                annee_scolaire_id=annee.id,
                nom=nom,
                prenom=prenom,
                classe=classe,
            )
        )
        session.commit()
        return p

    return {"site": site, "annee": annee, "eleve": _eleve}


def _google(*comptes):
    """`{adresse: description}` à la façon de `lire_utilisateurs`."""
    return {
        a: {"ou": ou, "suspendu": susp}
        for a, ou, susp in ((c[0], c[1], c[2] if len(c) > 2 else False) for c in comptes)
    }


# ---------------------------------------------------------------------------
# Déplacement d'OU
# ---------------------------------------------------------------------------


def test_deplace_vers_lou_demandee(session, contexte):
    """La destination vient de l'appelant, pas de la Table."""
    from backend.services.deplacement_manuel import construire_plan_manuel

    p = contexte["eleve"]("DUPONT", "Jean")
    plan = construire_plan_manuel(
        session,
        personne_ids=[p.id],
        etat_google=_google(("jean.dupont@lekreisker.fr", "/3. NDK/NDK2027/2_5")),
        ou_destination="/3. NDK/NDK2027/2_8",
        annee_id=contexte["annee"].id,
    )

    assert plan.nb_deplacements == 1
    m = plan.mouvements[0]
    assert m.action == "deplacer"
    assert m.ou_visee == "/3. NDK/NDK2027/2_8"
    assert "2_5 → /3. NDK/NDK2027/2_8" in m.libelle
    assert plan.est_executable


def test_deja_en_place_ne_produit_rien(session, contexte):
    """Un plan qui annonce plus qu'il n'applique ne se relit plus."""
    from backend.services.deplacement_manuel import construire_plan_manuel

    reste = contexte["eleve"]("RESTE", "Lea")
    bouge = contexte["eleve"]("BOUGE", "Tom")
    plan = construire_plan_manuel(
        session,
        personne_ids=[reste.id, bouge.id],
        etat_google=_google(
            ("lea.reste@lekreisker.fr", "/3. NDK/NDK2027/2_8"),
            ("tom.bouge@lekreisker.fr", "/3. NDK/NDK2027/2_5"),
        ),
        ou_destination="/3. NDK/NDK2027/2_8",
    )

    assert plan.nb_deplacements == 1
    assert plan.nb_deja_en_place == 1
    assert plan.mouvements[0].personne_id == bouge.id


def test_la_barre_finale_ne_fabrique_pas_un_deplacement(session, contexte):
    """`/…/2_8/` et `/…/2_8` sont la même OU. Sinon on déplace pour rien."""
    from backend.services.deplacement_manuel import construire_plan_manuel

    p = contexte["eleve"]("DUPONT", "Jean")
    plan = construire_plan_manuel(
        session,
        personne_ids=[p.id],
        etat_google=_google(("jean.dupont@lekreisker.fr", "/3. NDK/NDK2027/2_8")),
        ou_destination="  /3. NDK/NDK2027/2_8/  ",
    )
    assert plan.nb_total == 0
    assert plan.nb_deja_en_place == 1


# ---------------------------------------------------------------------------
# Groupes
# ---------------------------------------------------------------------------


def test_groupes_entree_et_sortie_sans_les_gestes_inutiles(session, contexte):
    """On n'ajoute pas un membre déjà là, on ne sort pas un absent."""
    from backend.services.deplacement_manuel import construire_plan_manuel

    p = contexte["eleve"]("DUPONT", "Jean")
    plan = construire_plan_manuel(
        session,
        personne_ids=[p.id],
        etat_google=_google(("jean.dupont@lekreisker.fr", "/3. NDK/NDK2027/2_5")),
        groupes_par_email={
            "jean.dupont@lekreisker.fr": ["2nde-5@lekreisker.fr", "deja@lekreisker.fr"]
        },
        groupes_ajouter=["2nde-8@lekreisker.fr", "deja@lekreisker.fr"],
        groupes_retirer=["2nde-5@lekreisker.fr", "jamais@lekreisker.fr"],
    )

    assert plan.nb_entrees_groupe == 1
    assert plan.nb_sorties_groupe == 1
    assert {m.groupe for m in plan.mouvements} == {
        "2nde-8@lekreisker.fr",
        "2nde-5@lekreisker.fr",
    }


def test_un_groupe_des_deux_cotes_est_ecarte(session, contexte):
    """Entrer et sortir du même groupe : l'ordre déciderait du résultat."""
    from backend.services.deplacement_manuel import construire_plan_manuel

    p = contexte["eleve"]("DUPONT", "Jean")
    plan = construire_plan_manuel(
        session,
        personne_ids=[p.id],
        etat_google=_google(("jean.dupont@lekreisker.fr", "/3. NDK")),
        groupes_par_email={"jean.dupont@lekreisker.fr": []},
        groupes_ajouter=["x@lekreisker.fr"],
        groupes_retirer=["X@lekreisker.fr"],
    )

    assert plan.nb_total == 0
    assert any("entrée et en sortie" in a for a in plan.avertissements)


def test_ou_et_groupes_dans_le_meme_plan(session, contexte):
    """Changer de classe, c'est les deux à la fois — un seul aperçu."""
    from backend.services.deplacement_manuel import construire_plan_manuel

    p = contexte["eleve"]("DUPONT", "Jean")
    plan = construire_plan_manuel(
        session,
        personne_ids=[p.id],
        etat_google=_google(("jean.dupont@lekreisker.fr", "/3. NDK/NDK2027/2_5")),
        groupes_par_email={"jean.dupont@lekreisker.fr": ["2nde-5@lekreisker.fr"]},
        ou_destination="/3. NDK/NDK2027/2_8",
        groupes_ajouter=["2nde-8@lekreisker.fr"],
        groupes_retirer=["2nde-5@lekreisker.fr"],
    )

    assert (plan.nb_deplacements, plan.nb_entrees_groupe, plan.nb_sorties_groupe) == (1, 1, 1)
    assert plan.nb_concernes == 1


# ---------------------------------------------------------------------------
# Ce qui ne peut pas être traité
# ---------------------------------------------------------------------------


def test_sans_adresse_ou_sans_compte_on_ecarte_en_nommant(session, contexte):
    """Disparaître en silence est le pire résultat possible."""
    from backend.services.deplacement_manuel import construire_plan_manuel

    muet = contexte["eleve"]("MUET", "Zoe", email="")
    absent = contexte["eleve"]("ABSENT", "Luc")
    ok = contexte["eleve"]("PRESENT", "Ana")

    plan = construire_plan_manuel(
        session,
        personne_ids=[muet.id, absent.id, ok.id],
        etat_google={
            "luc.absent@lekreisker.fr": None,
            "ana.present@lekreisker.fr": {"ou": "/3. NDK", "suspendu": False},
        },
        ou_destination="/3. NDK/NDK2027/2_8",
    )

    assert plan.nb_deplacements == 1
    motifs = {e.libelle: e.motif for e in plan.ecartes}
    assert motifs == {
        "MUET Zoe": "Adresse non constatée dans Google",
        "ABSENT Luc": "Aucun compte Google à cette adresse",
    }


def test_une_adresse_seulement_calculee_ne_sert_jamais_a_ecrire(session, contexte):
    """93 % de justesse : une sur quatorze désignerait l'homonyme.

    Le compte existe bien à l'adresse que la formule produit — et c'est
    précisément le piège : rien ne dit qu'il appartient à cet élève-là.
    """
    from backend.services.deplacement_manuel import construire_plan_manuel

    calcule = contexte["eleve"]("CALCULE", "Eve", email="")
    attribue = contexte["eleve"]("ATTRIBUE", "Max", email="")
    attribue.email_attribuee = "max.attribue2@lekreisker.fr"
    session.commit()

    plan = construire_plan_manuel(
        session,
        personne_ids=[calcule.id, attribue.id],
        etat_google={
            "eve.calcule@lekreisker.fr": {"ou": "/3. NDK", "suspendu": False},
            "max.attribue2@lekreisker.fr": {"ou": "/3. NDK", "suspendu": False},
        },
        ou_destination="/3. NDK/NDK2027/2_8",
    )

    assert [e.libelle for e in plan.ecartes] == ["CALCULE Eve"]
    assert plan.nb_deplacements == 1
    assert plan.mouvements[0].email == "max.attribue2@lekreisker.fr"


def test_un_compte_suspendu_est_deplace_mais_signale(session, contexte):
    """Le déplacement aboutit ; l'utilisateur doit savoir qu'il ne suffit pas."""
    from backend.services.deplacement_manuel import construire_plan_manuel

    p = contexte["eleve"]("DORMANT", "Ivan")
    plan = construire_plan_manuel(
        session,
        personne_ids=[p.id],
        etat_google=_google(("ivan.dormant@lekreisker.fr", "/7. Sortis", True)),
        ou_destination="/3. NDK/NDK2027/2_8",
    )

    assert plan.nb_deplacements == 1
    assert any("suspendu" in a for a in plan.avertissements)


def test_destination_absente_rend_le_plan_inexecutable(session, contexte):
    """Trente échecs Google valent moins qu'un refus lisible."""
    from backend.services.deplacement_manuel import construire_plan_manuel

    p = contexte["eleve"]("DUPONT", "Jean")
    plan = construire_plan_manuel(
        session,
        personne_ids=[p.id],
        etat_google=_google(("jean.dupont@lekreisker.fr", "/3. NDK")),
        ou_destination="/3. NDK/NDK2027/INEXISTANTE",
        groupes_ajouter=["fantome@lekreisker.fr"],
        groupes_par_email={"jean.dupont@lekreisker.fr": []},
        ou_existantes={"/3. NDK", "/3. NDK/NDK2027/2_8"},
        groupes_existants={"2nde-8@lekreisker.fr"},
    )

    assert plan.destinations_absentes == [
        "/3. NDK/NDK2027/INEXISTANTE",
        "fantome@lekreisker.fr",
    ]
    assert not plan.est_executable
    # Le plan reste calculé : on voit ce qui se passerait une fois l'OU créée.
    assert plan.nb_total == 2


def test_sans_destination_le_plan_se_refuse(session, contexte):
    from backend.services.deplacement_manuel import construire_plan_manuel

    p = contexte["eleve"]("DUPONT", "Jean")
    plan = construire_plan_manuel(
        session, personne_ids=[p.id], etat_google={}
    )
    assert plan.nb_total == 0
    assert not plan.est_executable
    assert "Aucune destination" in plan.avertissements[0]


def test_sans_destination_letat_est_quand_meme_rendu(session, contexte):
    """Ouvrir une fiche, c'est d'abord demander où quelqu'un est rangé.

    Répondre « donnez-moi une destination » à cette question-là obligerait à
    en inventer une pour obtenir le renseignement.
    """
    from backend.services.deplacement_manuel import construire_plan_manuel

    p = contexte["eleve"]("DUPONT", "Jean")
    plan = construire_plan_manuel(
        session,
        personne_ids=[p.id],
        etat_google=_google(("jean.dupont@lekreisker.fr", "/3. NDK/NDK2027/2_5")),
        groupes_par_email={"jean.dupont@lekreisker.fr": ["2nde-5@lekreisker.fr"]},
        groupes_complets=True,
        annee_id=contexte["annee"].id,
    )

    assert plan.nb_total == 0
    assert len(plan.etats) == 1
    etat = plan.etats[0]
    assert etat.ou_actuelle == "/3. NDK/NDK2027/2_5"
    assert etat.groupes_actuels == ["2nde-5@lekreisker.fr"]
    assert etat.groupes_complets
    assert etat.classe == "2_5"


# ---------------------------------------------------------------------------
# Résolution d'une classe entière
# ---------------------------------------------------------------------------


def test_personnes_de_classes_rend_la_classe_entiere(session, contexte):
    """Une classe se résout en noms avant le plan, pas au moment de l'envoi."""
    from backend.services.deplacement_manuel import personnes_de_classes

    a = contexte["eleve"]("UN", "Alpha", classe="2_5")
    b = contexte["eleve"]("DEUX", "Beta", classe="2_5")
    contexte["eleve"]("TROIS", "Gamma", classe="2_6")

    ids = personnes_de_classes(
        session, annee_id=contexte["annee"].id, classes=["2_5"]
    )
    assert ids == sorted([a.id, b.id])


def test_personnes_de_classes_ne_compte_pas_deux_fois(session, contexte):
    """Un export rejoué laisse deux snapshots : l'élève reste un."""
    from backend.models import Snapshot
    from backend.services.deplacement_manuel import personnes_de_classes

    p = contexte["eleve"]("UN", "Alpha", classe="2_5")
    session.add(
        Snapshot(
            personne_id=p.id,
            annee_scolaire_id=contexte["annee"].id,
            nom="UN",
            prenom="Alpha",
            classe="2_5",
        )
    )
    session.commit()

    assert personnes_de_classes(
        session, annee_id=contexte["annee"].id, classes=["2_5"]
    ) == [p.id]


def test_personnes_de_classes_suit_le_dernier_snapshot(session, contexte):
    """Réingéré dans une autre classe, l'élève suit sa classe la plus récente."""
    from datetime import datetime, timedelta

    from backend.models import Snapshot
    from backend.services.deplacement_manuel import personnes_de_classes

    p = contexte["eleve"]("UN", "Alpha", classe="2_5")
    session.add(
        Snapshot(
            personne_id=p.id,
            annee_scolaire_id=contexte["annee"].id,
            nom="UN",
            prenom="Alpha",
            classe="2_6",
            date_ingestion=datetime.utcnow() + timedelta(days=1),
        )
    )
    session.commit()

    an = contexte["annee"].id
    assert personnes_de_classes(session, annee_id=an, classes=["2_5"]) == []
    assert personnes_de_classes(session, annee_id=an, classes=["2_6"]) == [p.id]


# ---------------------------------------------------------------------------
# Les garde-fous de l'endpoint, qui jouent avant tout appel à Google
# ---------------------------------------------------------------------------


@pytest.fixture()
def client(tmp_db_path):
    from fastapi.testclient import TestClient

    from backend.main import app

    with TestClient(app) as c:
        yield c


class TestGardeFousEndpoint:
    """Ces refus tombent avant que le client Google ne soit construit.

    C'est voulu : une demande mal formée ne doit pas coûter un aller-retour
    à l'annuaire, ni se présenter à l'utilisateur comme une panne réseau.
    """

    CHEMIN = "/api/google/deplacement/plan"

    def test_selection_vide(self, client):
        r = client.post(self.CHEMIN, json={"ou_destination": "/X"})
        assert r.status_code == 400
        assert "Aucune personne" in r.json()["detail"]

    def test_classes_sans_annee(self, client):
        r = client.post(
            self.CHEMIN, json={"classes": ["2_5"], "ou_destination": "/X"}
        )
        assert r.status_code == 400
        assert "année" in r.json()["detail"]

    def test_au_dela_du_plafond(self, client):
        from backend.routers.google_api import PLAFOND_SELECTION

        r = client.post(
            self.CHEMIN,
            json={
                "personne_ids": list(range(1, PLAFOND_SELECTION + 2)),
                "ou_destination": "/X",
            },
        )
        assert r.status_code == 400
        assert "bascule" in r.json()["detail"]

    def test_execution_sans_confirmation(self, client):
        """Une exécution ne part jamais par défaut."""
        r = client.post(
            "/api/google/deplacement/executer",
            json={"personne_ids": [1], "ou_destination": "/X"},
        )
        assert r.status_code == 400
        assert r.json()["detail"] == "Confirmation requise."
