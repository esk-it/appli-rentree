"""Tests du service d'arbitrage.

Vérifie l'idempotence via `cle_cas`, le tranchage, l'immuabilité d'une
décision prise, et le rappel par `deja_tranche`.

Vérifie aussi l'intégration ingestion → arbitrages (collision, homonymie)
et le branchement du seau ambigu de la réconciliation.
"""
from __future__ import annotations

from pathlib import Path

import pytest


# ---------------------------------------------------------------------------
# Service arbitrage — unitaires
# ---------------------------------------------------------------------------


def test_creer_arbitrage_en_attente(session):
    from backend.services.arbitrage import creer_ou_reprendre

    arb = creer_ou_reprendre(
        session,
        type_cas="collision_login",
        cle_cas="collision_login:jdupont:E5292",
        contexte={"nouveau": "Jean Dupont"},
    )
    session.commit()

    assert arb.id is not None
    assert arb.decision is None
    assert arb.date_decision is None
    assert arb.est_en_attente is True


def test_creer_est_idempotent(session):
    """Deux appels avec la même cle_cas ne créent qu'un enregistrement."""
    from backend.models import Arbitrage
    from backend.services.arbitrage import creer_ou_reprendre

    creer_ou_reprendre(
        session,
        type_cas="collision_login",
        cle_cas="collision_login:pmartin:E100",
        contexte={"v": 1},
    )
    creer_ou_reprendre(
        session,
        type_cas="collision_login",
        cle_cas="collision_login:pmartin:E100",
        contexte={"v": 2},  # contexte mis à jour
    )
    session.commit()

    tous = session.query(Arbitrage).all()
    assert len(tous) == 1
    # Le contexte a été rafraîchi
    import json
    assert json.loads(tous[0].contexte_json)["v"] == 2


def test_type_cas_invalide(session):
    from backend.services.arbitrage import creer_ou_reprendre

    with pytest.raises(ValueError, match="type_cas"):
        creer_ou_reprendre(
            session,
            type_cas="fantaisie",
            cle_cas="x",
            contexte={},
        )


def test_trancher(session):
    from backend.services.arbitrage import creer_ou_reprendre, trancher

    arb = creer_ou_reprendre(
        session,
        type_cas="homonymie_ingestion",
        cle_cas="homonymie_ingestion:martin:jean:E1,E2",
        contexte={"ids": [1, 2]},
    )
    session.commit()

    r = trancher(session, arb.id, "personnes_distinctes", note="frères")
    session.commit()

    assert r.deja_tranche is False
    assert r.arbitrage.decision == "personnes_distinctes"
    assert r.arbitrage.note == "frères"
    assert r.arbitrage.date_decision is not None
    assert r.arbitrage.est_en_attente is False


def test_trancher_deux_fois_reste_immuable(session):
    """Un arbitrage déjà tranché renvoie deja_tranche=True et sa décision ne change pas."""
    from backend.services.arbitrage import creer_ou_reprendre, trancher

    arb = creer_ou_reprendre(
        session,
        type_cas="collision_login",
        cle_cas="collision_login:test:E9",
        contexte={},
    )
    session.commit()

    trancher(session, arb.id, "suffixe:2")
    session.commit()

    r2 = trancher(session, arb.id, "meme_personne")  # tentative de changement
    session.commit()

    assert r2.deja_tranche is True
    assert r2.arbitrage.decision == "suffixe:2"  # inchangé


def test_trancher_inexistant(session):
    from backend.services.arbitrage import trancher

    with pytest.raises(ValueError, match="introuvable"):
        trancher(session, 99999, "peu importe")


def test_en_attente_ne_renvoie_que_les_non_tranches(session):
    from backend.services.arbitrage import creer_ou_reprendre, en_attente, trancher

    a1 = creer_ou_reprendre(session, type_cas="collision_login", cle_cas="a", contexte={})
    a2 = creer_ou_reprendre(session, type_cas="collision_login", cle_cas="b", contexte={})
    a3 = creer_ou_reprendre(session, type_cas="collision_login", cle_cas="c", contexte={})
    session.commit()

    trancher(session, a2.id, "suffixe:2")
    session.commit()

    en_att = en_attente(session)
    ids = [a.id for a in en_att]
    assert a1.id in ids
    assert a3.id in ids
    assert a2.id not in ids


def test_deja_tranche_rappelle_la_decision(session):
    from backend.services.arbitrage import creer_ou_reprendre, deja_tranche, trancher

    arb = creer_ou_reprendre(session, type_cas="homonymie_ingestion", cle_cas="cle-x", contexte={})
    session.commit()

    assert deja_tranche(session, "cle-x") is None  # pas encore tranché

    trancher(session, arb.id, "meme_personne")
    session.commit()

    trouve = deja_tranche(session, "cle-x")
    assert trouve is not None
    assert trouve.decision == "meme_personne"


# ---------------------------------------------------------------------------
# Intégration ingestion → arbitrage
# ---------------------------------------------------------------------------


def _ecrire_export_htm(chemin: Path, lignes: list[dict]) -> None:
    """Crée un mini export HTML au format Charlemagne pour les tests."""
    entetes = list(lignes[0].keys())
    rows = ""
    for l in lignes:
        rows += "<tr>" + "".join(f"<td>{l.get(c, '')}</td>" for c in entetes) + "</tr>"
    html = f"""<html><body><table>
        <tr>{''.join(f'<th>{c}</th>' for c in entetes)}</tr>
        {rows}
    </table></body></html>"""
    chemin.write_text(html, encoding="utf-8")


def test_ingestion_reelle_cree_arbitrages_collision(tmp_path, session, site_factory):
    """Une collision login à l'ingestion réelle persiste un Arbitrage."""
    from backend.models import Arbitrage, Personne
    from backend.services.ingestion import ingerer_export

    # Setup : un site + une TableCorrespondance minimale
    site = site_factory("NDK")
    from backend.models import TableCorrespondance
    tc = TableCorrespondance(
        site_id=site.id,
        classe_charlemagne_long="TROISIEME B",
        classe_code_court="3B",
        ou_pre_rentree="/3. NDK/NDK2026",
        ou_definitive="/3. NDK/NDK2026/3B",
    )
    session.add(tc)
    session.commit()

    # 1re ingestion : Jean Dupont
    fic1 = tmp_path / "ingest1.htm"
    _ecrire_export_htm(fic1, [{
        "id_charlemagne": 1001,
        "num_badge": 20010,
        "nom": "DUPONT", "prenom": "Jean",
        "code_classe": "3B", "code_regime": "D",
        "code_etablissement": "02-COL",
    }])
    r1 = ingerer_export(session, fic1, type_personne="eleve", libelle_annee="2025-2026", mode="reel")
    assert r1.nb_personnes_creees == 1

    # 2e ingestion (autre id) : Julie Dupont → même login base "jdupont"
    fic2 = tmp_path / "ingest2.htm"
    _ecrire_export_htm(fic2, [{
        "id_charlemagne": 1002,
        "num_badge": 20020,
        "nom": "DUPONT", "prenom": "Julie",
        "code_classe": "3B", "code_regime": "D",
        "code_etablissement": "02-COL",
    }])
    r2 = ingerer_export(session, fic2, type_personne="eleve", libelle_annee="2025-2026", mode="reel")

    assert len(r2.collisions_login) == 1
    assert r2.collisions_login[0].login_base == "jdupont"

    # Un Arbitrage en attente doit exister pour cette collision
    arbitrages_bd = session.query(Arbitrage).filter_by(type_cas="collision_login").all()
    assert len(arbitrages_bd) == 1
    arb = arbitrages_bd[0]
    assert arb.est_en_attente is True
    assert arb.cle_cas == "collision_login:jdupont:E1002"

    import json
    ctx = json.loads(arb.contexte_json)
    assert ctx["login_attribue"] == "jdupont2"
    assert ctx["type_personne"] == "eleve"


def test_ingestion_reelle_cree_arbitrages_homonymie(tmp_path, session, site_factory):
    """Deux personnes de même nom+prénom dans le même export → un Arbitrage homonymie."""
    from backend.models import Arbitrage, TableCorrespondance
    from backend.services.ingestion import ingerer_export

    site = site_factory("NDK")
    tc = TableCorrespondance(
        site_id=site.id,
        classe_charlemagne_long="QUATRIEME A",
        classe_code_court="4A",
        ou_pre_rentree="/3. NDK/NDK2026",
        ou_definitive="/3. NDK/NDK2026/4A",
    )
    session.add(tc)
    session.commit()

    fic = tmp_path / "homonymes.htm"
    _ecrire_export_htm(fic, [
        {"id_charlemagne": 2001, "num_badge": 30010, "nom": "MARTIN", "prenom": "Jean",
         "code_classe": "4A", "code_regime": "D", "code_etablissement": "02-COL"},
        {"id_charlemagne": 2002, "num_badge": 30020, "nom": "MARTIN", "prenom": "Jean",
         "code_classe": "4A", "code_regime": "D", "code_etablissement": "02-COL"},
    ])
    r = ingerer_export(session, fic, type_personne="eleve", libelle_annee="2025-2026", mode="reel")

    assert len(r.homonymes_intra_export) == 1

    arbitrages_hom = session.query(Arbitrage).filter_by(type_cas="homonymie_ingestion").all()
    assert len(arbitrages_hom) == 1
    arb = arbitrages_hom[0]
    assert arb.est_en_attente is True
    assert "MARTIN" in arb.cle_cas.upper() or "martin" in arb.cle_cas
    assert "E2001" in arb.cle_cas and "E2002" in arb.cle_cas


def test_ingestion_simulation_ne_persiste_pas_arbitrages(tmp_path, session, site_factory):
    """En simulation, rien n'est committé — pas d'Arbitrage persisté."""
    from backend.models import Arbitrage, TableCorrespondance
    from backend.services.ingestion import ingerer_export

    site = site_factory("NDK")
    tc = TableCorrespondance(
        site_id=site.id,
        classe_charlemagne_long="TROISIEME B",
        classe_code_court="3B",
        ou_pre_rentree="/3. NDK/NDK2026",
        ou_definitive="/3. NDK/NDK2026/3B",
    )
    session.add(tc)
    session.commit()

    # 1re ingestion réelle (crée jdupont)
    fic1 = tmp_path / "s1.htm"
    _ecrire_export_htm(fic1, [{"id_charlemagne": 3001, "num_badge": 40010, "nom": "DUPONT",
                                "prenom": "Jean", "code_classe": "3B", "code_regime": "D",
                                "code_etablissement": "02-COL"}])
    ingerer_export(session, fic1, type_personne="eleve", libelle_annee="2025-2026", mode="reel")

    # 2e ingestion en SIMULATION (collision jdupont2, mais rollback)
    fic2 = tmp_path / "s2.htm"
    _ecrire_export_htm(fic2, [{"id_charlemagne": 3002, "num_badge": 40020, "nom": "DUPONT",
                                "prenom": "Julie", "code_classe": "3B", "code_regime": "D",
                                "code_etablissement": "02-COL"}])
    r = ingerer_export(session, fic2, type_personne="eleve", libelle_annee="2025-2026", mode="simulation")

    assert len(r.collisions_login) == 1  # détectée dans le rapport
    # Mais pas de trace en base
    n = session.query(Arbitrage).filter_by(type_cas="collision_login").count()
    assert n == 0


# ---------------------------------------------------------------------------
# Réconciliation — seau ambigu branché sur les arbitrages en attente
# ---------------------------------------------------------------------------


def test_seau_ambigu_capte_les_arbitrages(
    session, personne_factory, annee_factory
):
    """Une personne avec un Arbitrage en attente est reclassée dans ambigus."""
    from backend.models import Snapshot
    from backend.services.arbitrage import cle_collision_login, creer_ou_reprendre
    from backend.services.reconciliation import reconcilier

    an_prec = annee_factory("2024-2025")
    an_cour = annee_factory("2025-2026")

    # Cette personne serait un "nouveau" — mais un arbitrage en attente la concerne
    p = personne_factory(nom="AMBIG", prenom="Cas", type="eleve", id_charlemagne=555)
    snap = Snapshot(
        personne_id=p.id, annee_scolaire_id=an_cour.id,
        nom=p.nom, prenom=p.prenom, classe="3A",
    )
    session.add(snap)

    creer_ou_reprendre(
        session,
        type_cas="collision_login",
        cle_cas=cle_collision_login("ccas", "E555"),
        contexte={
            "type_personne": "eleve",
            "id_charlemagne": 555,
            "login_base": "ccas",
            "login_attribue": "ccas2",
        },
    )
    session.commit()

    r = reconcilier(session, an_prec.id, an_cour.id)

    assert r.compteurs["ambigu"] == 1
    assert r.compteurs["nouveau"] == 0  # sortie de nouveau vers ambigu
    assert r.ambigus[0].nom == "AMBIG"
    assert "arbitrage" in r.ambigus[0].motif.lower()


def test_seau_ambigu_ignore_les_arbitrages_tranches(
    session, personne_factory, annee_factory
):
    """Un arbitrage tranché n'a plus aucun effet sur la réconciliation."""
    from backend.models import Snapshot
    from backend.services.arbitrage import cle_collision_login, creer_ou_reprendre, trancher
    from backend.services.reconciliation import reconcilier

    an_prec = annee_factory("2024-2025")
    an_cour = annee_factory("2025-2026")

    p = personne_factory(nom="RESOLU", prenom="R", type="eleve", id_charlemagne=777)
    snap = Snapshot(personne_id=p.id, annee_scolaire_id=an_cour.id,
                    nom=p.nom, prenom=p.prenom, classe="3A")
    session.add(snap)

    arb = creer_ou_reprendre(
        session, type_cas="collision_login",
        cle_cas=cle_collision_login("rrr", "E777"),
        contexte={"type_personne": "eleve", "id_charlemagne": 777, "login_base": "rrr", "login_attribue": "rrr2"},
    )
    trancher(session, arb.id, "suffixe:2")
    session.commit()

    r = reconcilier(session, an_prec.id, an_cour.id)

    assert r.compteurs["ambigu"] == 0
    assert r.compteurs["nouveau"] == 1
