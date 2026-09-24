"""Deux fiches, une seule personne : la fusion.

Les cas viennent de la base réelle, septembre 2026 : les vingt-neuf
adresses « visées par plusieurs personnes » étaient toutes une seule
personne en deux fiches — vingt-huit élèves passés de NDE à NDK ou SU, que
la seconde base Charlemagne a renumérotés, et une réinscription.
"""
from __future__ import annotations

import json
from datetime import datetime, timedelta

import pandas as pd
import pytest
from fastapi.testclient import TestClient


@pytest.fixture()
def bases(session, site_factory, annee_factory):
    """NDE, NDK et SU sur le même domaine, deux années, et leurs classes."""
    from backend.models import Personne, Snapshot, TableCorrespondance

    sites = {
        "NDE": site_factory("NDE", domaine_mail="lekreisker.fr"),
        "NDK": site_factory("NDK"),
        "SU": site_factory("SU"),
    }
    annees = {x: annee_factory(x) for x in ("2025-2026", "2026-2027")}
    for site, code in (
        ("NDE", "5L"), ("NDE", "4J"), ("NDE", "3F"), ("NDE", "6V"),
        ("NDK", "3_PM"), ("NDK", "2_2"), ("NDK", "BTS_2"),
        ("SU", "46"), ("SU", "34"), ("SU", "52"),
    ):
        session.add(
            TableCorrespondance(
                site_id=sites[site].id, classe_charlemagne_long=f"{site} {code}",
                classe_code_court=code, ou_pre_rentree=f"/{site}",
                ou_definitive=f"/{site}/{code}",
            )
        )
    session.commit()
    horloge = {"t": datetime(2026, 1, 1)}

    def eleve(site, id_ch, nom, prenom, login, parcours, **kw):
        """Une fiche, et une classe par année vécue."""
        p = Personne(
            type="eleve", id_charlemagne=id_ch,
            badge=Personne.calculer_badge("eleve", id_ch), login=login,
            nom=nom, prenom=prenom, site_id=sites[site].id,
            classe=parcours[-1][1], **kw,
        )
        session.add(p)
        session.flush()
        for annee, classe in parcours:
            horloge["t"] += timedelta(days=1)
            session.add(
                Snapshot(
                    personne_id=p.id, annee_scolaire_id=annees[annee].id,
                    nom=nom, prenom=prenom, classe=classe,
                    date_ingestion=horloge["t"],
                )
            )
        session.commit()
        return p

    class Bases:
        pass

    b = Bases()
    b.sites, b.annees, b.eleve = sites, annees, eleve
    return b


def _aaron(bases):
    """Le cas vécu : 4J à NDE en 2025-2026, 3e prépa-métiers à NDK."""
    ancien = bases.eleve("NDE", 717, "SAILLOUR", "Aaron", "asaillour1", [("2025-2026", "4J")])
    actuel = bases.eleve(
        "NDK", 8761, "SAILLOUR", "Aaron", "asaillour2", [("2026-2027", "3_PM")],
        email_constate="aaron.saillour@lekreisker.fr",
    )
    return ancien.id, actuel.id


def _classes(session, personne_id):
    from backend.models import AnneeScolaire, Snapshot

    return sorted(
        (a.libelle, s.classe)
        for s, a in session.query(Snapshot, AnneeScolaire)
        .join(AnneeScolaire, AnneeScolaire.id == Snapshot.annee_scolaire_id)
        .filter(Snapshot.personne_id == personne_id)
    )


# ---------------------------------------------------------------------------
# La fusion
# ---------------------------------------------------------------------------


def test_la_fiche_de_cette_annee_reste_et_l_ancienne_la_rejoint(session, bases):
    from backend.models import FicheFusionnee, Personne
    from backend.services.fusion import fusionner

    ancien, actuel = _aaron(bases)
    # L'ordre des deux fiches ne décide de rien : c'est la règle qui choisit.
    r = fusionner(session, ancien, actuel, mode="reel")

    assert (r.garde.cle_pivot, r.absorbee.cle_pivot) == ("E8761", "E717")
    assert r.annees_rattachees == ["2025-2026 · 4J (NDE)"]
    session.expire_all()
    assert session.get(Personne, ancien) is None
    garde = session.get(Personne, actuel)
    assert _classes(session, actuel) == [("2025-2026", "4J"), ("2026-2027", "3_PM")]
    # Ce qui décrit l'inscription d'aujourd'hui ne bouge pas.
    assert (garde.classe, garde.site.nom, garde.login, garde.badge) == (
        "3_PM", "NDK", "asaillour2", 97610,
    )
    f = session.query(FicheFusionnee).one()
    assert (f.cle_pivot, f.personne_id, f.login, f.badge, f.site) == (
        "E717", actuel, "asaillour1", 17170, "NDE",
    )


def test_la_sortie_promise_a_l_ancienne_fiche_est_abandonnee(session, bases):
    """Le cas vécu : Maël PRONOST, réinscrit à NDK sous un nouveau numéro.

    Son ancienne fiche, absente de 2026-2027, passait pour un sortant : le
    compte `mael.pronost@` — le sien, toujours en service — était promis au
    dossier des comptes à supprimer.
    """
    from backend.models import CompteCible
    from backend.services.fusion import fusionner

    ancien = bases.eleve(
        "NDK", 7913, "PRONOST", "Mael", "mpronost", [("2025-2026", "BTS_2")],
        email_constate="mael.pronost@lekreisker.fr",
    )
    actuel = bases.eleve(
        "NDK", 8966, "PRONOST", "Maël", "mpronost3", [("2026-2027", "BTS_2")],
        email_constate="mael.pronost@lekreisker.fr",
    )
    session.add_all([
        CompteCible(
            personne_id=ancien.id, cible="google", etat="quarantaine",
            ou_appliquee="/7. Sortis/Comptes à supprimer au 31-12-2026",
        ),
        CompteCible(
            personne_id=actuel.id, cible="google", etat="actif",
            ou_appliquee="/3. NDK/NDK2027/BTS_2",
        ),
    ])
    session.commit()
    actuel_id = actuel.id

    r = fusionner(session, ancien.id, actuel_id, mode="reel")

    assert [(c.personne_id, c.etat) for c in session.query(CompteCible)] == [
        (actuel_id, "actif")
    ]
    assert any("Sortis" in a for a in r.abandonnes)
    assert not r.avertissements, "une seule adresse : un seul compte"
    assert "réinscription" in r.motif_du_choix or "E8966" in r.motif_du_choix


def test_une_sortie_n_est_pas_reprise_sur_une_personne_inscrite(session, bases):
    """Même sans compte suivi du côté de la fiche gardée."""
    from backend.models import CompteCible
    from backend.services.fusion import fusionner

    ancien, actuel = _aaron(bases)
    session.add(CompteCible(personne_id=ancien, cible="google", etat="quarantaine"))
    session.commit()

    r = fusionner(session, ancien, actuel, mode="reel")
    assert session.query(CompteCible).count() == 0
    assert any("inscrite en 2026-2027" in a for a in r.abandonnes)


def test_un_compte_suivi_passe_a_la_fiche_gardee(session, bases):
    from backend.models import CompteCible
    from backend.services.fusion import fusionner

    ancien, actuel = _aaron(bases)
    session.add(CompteCible(personne_id=ancien, cible="google", etat="actif"))
    session.commit()

    r = fusionner(session, ancien, actuel, mode="reel")
    assert [(c.personne_id, c.etat) for c in session.query(CompteCible)] == [
        (actuel, "actif")
    ]
    assert any("Google" in x for x in r.repris)


def test_le_compte_suit_la_personne(session, bases):
    """Anna QUÉMÉNEUR : l'adresse de son compte est sur l'ancienne fiche.

    La fiche de SU, qui ne la connaissait pas, la reprend — et l'adresse
    attribuée faute de mieux s'efface devant le constat.
    """
    from backend.models import Personne
    from backend.services.fusion import fusionner

    ancien = bases.eleve(
        "NDE", 795, "QUEMENEUR", "Anna", "aquemeneu1", [("2025-2026", "6V")],
        email_constate="anna.quemeneur@lekreisker.fr",
    )
    actuel = bases.eleve(
        "SU", 8933, "QUÉMÉNEUR", "Anna", "aquemeneur", [("2026-2027", "52")],
        email_attribuee="anna.quemeneur2@lekreisker.fr",
    )
    actuel_id = actuel.id

    r = fusionner(session, actuel_id, ancien.id, mode="reel")

    garde = session.get(Personne, actuel_id)
    assert garde.email_constate == "anna.quemeneur@lekreisker.fr"
    assert garde.email_attribuee is None
    assert garde.email == "anna.quemeneur@lekreisker.fr"
    assert any("adresse du compte Google" in x for x in r.repris)


def test_une_annee_que_la_fiche_gardee_decrit_deja_fait_foi(session, bases):
    """Le cas vécu : Matthieu RAVARD, passé de NDE à SU en cours d'année.

    Les deux fiches ont une classe en 2025-2026 : 4J à NDE, 46 à SU. C'est
    celle de la fiche gardée qui reste ; l'autre est dite, et gardée dans
    la trace de la fusion.
    """
    from backend.models import FicheFusionnee
    from backend.services.fusion import fusionner

    ancien = bases.eleve("NDE", 712, "RAVARD", "Matthieu", "mravard1", [("2025-2026", "4J")])
    actuel = bases.eleve(
        "SU", 8476, "RAVARD", "Matthieu", "mravard",
        [("2025-2026", "46"), ("2026-2027", "34")],
    )
    actuel_id = actuel.id

    r = fusionner(session, ancien.id, actuel_id, mode="reel")

    assert r.annees_rattachees == []
    assert len(r.annees_ecartees) == 1 and "46" in r.annees_ecartees[0]
    assert _classes(session, actuel_id) == [("2025-2026", "46"), ("2026-2027", "34")]
    trace = json.loads(session.query(FicheFusionnee).one().etat_json)
    assert [x["classe"] for x in trace["snapshots_ecartes"]] == ["4J"]


def test_la_simulation_n_ecrit_rien(session, bases):
    from backend.models import FicheFusionnee, Generation, Personne
    from backend.services.fusion import fusionner

    ancien, actuel = _aaron(bases)
    r = fusionner(session, ancien, actuel)

    assert r.mode == "simulation" and r.garde.cle_pivot == "E8761"
    session.expire_all()
    assert session.query(Personne).count() == 2
    assert session.query(FicheFusionnee).count() == 0
    assert session.query(Generation).count() == 0
    assert _classes(session, ancien) == [("2025-2026", "4J")]


def test_la_fusion_est_journalisee(session, bases):
    from backend.models import Generation
    from backend.services.fusion import fusionner

    ancien, actuel = _aaron(bases)
    fusionner(session, ancien, actuel, mode="reel")

    g = session.query(Generation).one()
    assert g.type_operation == "fusion"
    assert json.loads(g.parametres_json) == {"garde": "E8761", "absorbee": "E717"}


def test_refus(session, bases, personne_factory):
    from backend.services.fusion import FusionImpossible, fusionner

    ancien, _ = _aaron(bases)
    adulte = personne_factory(type="adulte", id_charlemagne=717, login="aadulte")
    with pytest.raises(FusionImpossible, match="elle-même"):
        fusionner(session, ancien, ancien)
    with pytest.raises(FusionImpossible, match="adulte"):
        fusionner(session, ancien, adulte.id)


def test_deux_fiches_inscrites_cette_annee_font_hesiter(session, bases):
    """Deux Hugo GUILLOU, un en 1re à NDK, un en 6e à SU : deux personnes.

    La fusion reste possible — une réinscription sous un nouveau numéro
    ressemble à ça — mais elle le dit, et rien ne la suggère.
    """
    from backend.models import Personne, Snapshot
    from backend.services.fusion import fusionner, meme_personne_probable

    a = bases.eleve("NDK", 8000, "GUILLOU", "Hugo", "hguillou", [("2026-2027", "2_2")])
    b = bases.eleve("SU", 8100, "GUILLOU", "Hugo", "hguillou2", [("2026-2027", "52")])
    inscrits = {s.personne_id for s in session.query(Snapshot)}

    assert not meme_personne_probable(a, b, inscrits)
    r = fusionner(session, a.id, b.id)
    assert any("homonymes" in x for x in r.avertissements)
    assert session.query(Personne).count() == 2


def test_un_accent_ne_fait_pas_deux_personnes(session, bases):
    from backend.models import Snapshot
    from backend.services.fusion import meme_personne_probable

    a = bases.eleve("NDE", 795, "QUEMENEUR", "Anna", "aquemeneu1", [("2025-2026", "6V")])
    b = bases.eleve("SU", 8933, "QUÉMÉNEUR", "Anna", "aquemeneur", [("2026-2027", "52")])
    inscrits = {
        s.personne_id
        for s in session.query(Snapshot).filter_by(
            annee_scolaire_id=bases.annees["2026-2027"].id
        )
    }
    assert meme_personne_probable(a, b, inscrits)


def test_une_fiche_deja_reunie_suit_le_mouvement(session, bases):
    """Trois fiches pour une personne : l'ancien numéro mène à la dernière."""
    from backend.models import FicheFusionnee
    from backend.services.fusion import fusionner, personne_par_cle

    ancien, actuel = _aaron(bases)
    fusionner(session, ancien, actuel, mode="reel")
    # Une troisième fiche, plus récente encore : une réinscription en cours
    # d'année, sous un numéro de plus.
    derniere = bases.eleve(
        "NDK", 9001, "SAILLOUR", "Aaron", "asaillour3", [("2026-2027", "3_PM")]
    )
    derniere_id = derniere.id
    fusionner(session, actuel, derniere_id, mode="reel")

    assert {f.personne_id for f in session.query(FicheFusionnee)} == {derniere_id}
    assert personne_par_cle(session, "eleve", 717)[0].id == derniere_id


# ---------------------------------------------------------------------------
# Après la fusion : l'ancien numéro reconnu, l'identifiant pris
# ---------------------------------------------------------------------------


def _ligne(id_ch, nom, prenom, classe, precedente=None):
    return {
        "id_charlemagne": id_ch, "num_badge": None, "nom": nom, "prenom": prenom,
        "code_classe": classe, "code_classe_precedente": precedente,
        "code_classe_an_prochain": None, "email": None, "code_regime": None,
    }


def _ingerer(session, libelle, *lignes):
    from backend.services.ingestion import RapportIngestion, _ingerer_eleves

    rapport = RapportIngestion(type_personne="eleve", annee_libelle=libelle, mode="reel")
    return _ingerer_eleves(session, pd.DataFrame(list(lignes)), libelle, "reel", rapport)


def test_reingerer_l_export_nde_ne_recree_pas_la_fiche(session, bases):
    """L'export NDE de l'an dernier porte toujours E717."""
    from backend.models import Personne
    from backend.services.fusion import fusionner

    ancien, actuel = _aaron(bases)
    fusionner(session, ancien, actuel, mode="reel")

    r = _ingerer(session, "2025-2026", _ligne(717, "SAILLOUR", "Aaron", "4J", "5L"))

    assert not r.est_bloquee and r.nb_personnes_creees == 0
    assert session.query(Personne).count() == 1
    assert _classes(session, actuel) == [("2025-2026", "4J"), ("2026-2027", "3_PM")]


def test_un_ancien_numero_ne_reecrit_pas_la_situation_d_aujourd_hui(session, bases):
    """Un export NDE de cette année qui le porterait encore — une
    désinscription en retard — ne ramène pas Aaron à NDE. Il complète en
    revanche une année que le parcours ne connaissait pas."""
    from backend.models import Personne
    from backend.services.fusion import fusionner

    ancien, actuel = _aaron(bases)
    fusionner(session, ancien, actuel, mode="reel")

    _ingerer(session, "2026-2027", _ligne(717, "SAILLOUR", "Aaron", "3F", "4J"))
    _ingerer(session, "2024-2025", _ligne(717, "SAILLOUR", "Aaron", "5L"))

    session.expire_all()
    garde = session.get(Personne, actuel)
    assert (garde.classe, garde.site.nom) == ("3_PM", "NDK")
    assert _classes(session, actuel) == [
        ("2024-2025", "5L"), ("2025-2026", "4J"), ("2026-2027", "3_PM"),
    ]


def test_l_identifiant_de_l_ancienne_fiche_reste_pris(session, bases):
    from backend.services.fusion import fusionner
    from backend.services.regles_metier import login_est_libre, motif_de_reservation

    ancien, actuel = _aaron(bases)
    fusionner(session, ancien, actuel, mode="reel")

    assert not login_est_libre(session, "asaillour1")
    assert "E717" in motif_de_reservation(session, "asaillour1")


# ---------------------------------------------------------------------------
# L'écran Départager
# ---------------------------------------------------------------------------


@pytest.fixture()
def client(tmp_db_path):
    from backend.main import app

    with TestClient(app) as c:
        yield c


def test_l_ecran_propose_de_reunir_et_la_dispute_disparait(client, session, bases):
    ancien, actuel = _aaron(bases)

    groupes = client.get("/api/personnes/collisions").json()
    assert [g["adresse"] for g in groupes] == ["aaron.saillour@lekreisker.fr"]
    g = groupes[0]
    assert g["meme_personne_probable"] and g["garde_id"] == actuel
    assert g["motif"] == (
        "4J à NDE en 2025-2026, puis 3_PM à NDK en 2026-2027 : un passage "
        "de NDE à NDK, pas deux homonymes."
    )
    inscrits = {v["cle_pivot"]: v["inscrit"] for v in g["visants"]}
    assert inscrits == {"E8761": True, "E717": False}

    r = client.post("/api/personnes/fusion", json={"ids": [ancien, actuel], "mode": "reel"})
    assert r.status_code == 200, r.text
    assert r.json()["garde"]["cle_pivot"] == "E8761"

    assert client.get("/api/personnes/collisions").json() == []
    fiche = client.get(f"/api/personnes/{actuel}/fiche").json()
    assert fiche["anciennes_fiches"] == ["E717 (NDE)"]
    assert [a["annee"] for a in fiche["parcours"]] == ["2026-2027", "2025-2026"]
    assert client.get("/api/personnes/par-cle-pivot/E717").json()["id"] == actuel


def test_une_fusion_refusee_le_dit(client, session, bases):
    ancien, _ = _aaron(bases)
    r = client.post("/api/personnes/fusion", json={"ids": [ancien, ancien]})
    assert r.status_code == 409
    assert "elle-même" in r.json()["detail"]
