"""L'INE et la date de naissance : relevés, puis mis au travail.

Ni l'un ni l'autre ne fait l'identité — la fiche Charlemagne la fait. Mais
l'INE suit l'élève d'une base Charlemagne à l'autre, et la date de
naissance départage deux fiches du même nom. Ce sont les deux preuves qui
manquaient pour dire « même personne » ou « deux personnes » sans deviner.
"""
from __future__ import annotations

from datetime import date

import pandas as pd
import pytest
from fastapi.testclient import TestClient


# ---------------------------------------------------------------------------
# La lecture
# ---------------------------------------------------------------------------


def test_une_date_francaise_se_lit_le_jour_d_abord():
    """pandas devinait le format sur la première valeur : `03/04/2012`
    devenait le 4 mars, et `25/12/2011` devenait illisible."""
    from backend.services.parser_charlemagne import date_francaise

    assert date_francaise("03/04/2012") == date(2012, 4, 3)
    assert date_francaise("25/12/2011") == date(2011, 12, 25)
    assert date_francaise("2012-03-12") == date(2012, 3, 12)
    assert date_francaise("20120312") == date(2012, 3, 12)
    assert date_francaise(pd.Timestamp("2012-03-12")) == date(2012, 3, 12)
    assert date_francaise("01/02/65") == date(1965, 2, 1), "un professeur, pas 2065"
    assert date_francaise("") is None and date_francaise("n/a") is None


def test_l_export_porte_l_ine_et_la_naissance(tmp_path):
    from backend.services.parser_charlemagne import lire_htm

    f = tmp_path / "export.htm"
    f.write_text(
        "<table><tr><th>Identifiant élève</th><th>Nom</th><th>Prénom</th>"
        "<th>Code classe</th><th>N° INE</th><th>Date de naissance</th></tr>"
        "<tr><td>8761</td><td>SAILLOUR</td><td>Aaron</td><td>3_PM</td>"
        "<td>0123456789A</td><td>03/04/2011</td></tr>"
        "<tr><td>8762</td><td>MARTIN</td><td>Léa</td><td>2_1</td>"
        "<td>0987654321B</td><td>25/12/2010</td></tr></table>",
        encoding="cp1252",
    )
    df = lire_htm(f)
    assert list(df["ine"]) == ["0123456789A", "0987654321B"]
    assert list(df["date_naissance"]) == [date(2011, 4, 3), date(2010, 12, 25)]


def test_l_ine_se_lit_sous_le_nom_que_charlemagne_lui_donne(tmp_path):
    """Dans Charlemagne, l'INE s'appelle « Id. National ». « Ancien INE ou
    INA » est un autre numéro : le prendre pour l'INE ferait conclure à deux
    personnes là où il n'y en a qu'une."""
    from backend.services.parser_charlemagne import lire_htm

    f = tmp_path / "export.htm"
    f.write_text(
        "<table><tr><th>Identifiant élève</th><th>Nom</th><th>Prénom</th>"
        "<th>Code classe</th><th>Id. National</th><th>Ancien INE ou INA</th></tr>"
        "<tr><td>8761</td><td>SAILLOUR</td><td>Aaron</td><td>3_PM</td>"
        "<td>0123456789A</td><td>0999999999Z</td></tr></table>",
        encoding="cp1252",
    )
    df = lire_htm(f)
    assert list(df["ine"]) == ["0123456789A"]
    assert list(df["ancien_ine_ou_ina"]) == ["0999999999Z"], "gardé à part, jamais pris pour l'INE"


def test_un_export_eleves_avec_la_naissance_reste_un_export_eleves():
    """La date de naissance comptait parmi les indices « adultes » : l'ajouter
    pour KoXo faisait ingérer deux mille élèves comme des professeurs."""
    from backend.services.ingestion import detecter_type_export

    eleves = pd.DataFrame([{
        "id_charlemagne": 1, "nom": "X", "prenom": "Y", "code_classe": "31",
        "date_naissance": date(2012, 1, 1), "ine": "0123456789A",
    }])
    adultes = pd.DataFrame([{
        "id_charlemagne": 1, "nom": "X", "prenom": "Y", "poste_occupe": "PROF",
        "date_naissance": date(1980, 1, 1),
    }])
    assert detecter_type_export(eleves) == "eleve"
    assert detecter_type_export(adultes) == "adulte"


# ---------------------------------------------------------------------------
# L'ingestion
# ---------------------------------------------------------------------------


@pytest.fixture()
def bases(session, site_factory, annee_factory):
    from backend.models import TableCorrespondance

    sites = {n: site_factory(n, domaine_mail="lekreisker.fr") for n in ("NDE", "NDK", "SU")}
    for nom, code in (("NDE", "4J"), ("NDE", "3F"), ("NDK", "3_PM"), ("NDK", "2_2"), ("SU", "52")):
        session.add(TableCorrespondance(
            site_id=sites[nom].id, classe_charlemagne_long=code,
            classe_code_court=code, ou_pre_rentree=f"/{nom}",
            ou_definitive=f"/{nom}/{code}",
        ))
    session.commit()
    return sites


def _ligne(id_ch, nom, prenom, classe, **kw):
    return {"id_charlemagne": id_ch, "nom": nom, "prenom": prenom,
            "code_classe": classe, **kw}


def _ingerer(session, libelle, *lignes, mode="reel"):
    from backend.services.ingestion import RapportIngestion, _ingerer_eleves

    rapport = RapportIngestion(type_personne="eleve", annee_libelle=libelle, mode=mode)
    return _ingerer_eleves(session, pd.DataFrame(list(lignes)), libelle, mode, rapport)


def test_l_ingestion_releve_l_ine_et_la_naissance(session, bases):
    from backend.models import Personne

    _ingerer(session, "2026-2027", _ligne(
        8761, "SAILLOUR", "Aaron", "3_PM",
        ine=" 0123456789a ", date_naissance=date(2011, 4, 3),
    ))
    p = session.query(Personne).one()
    assert (p.ine, p.date_naissance) == ("0123456789A", date(2011, 4, 3))


def test_une_annee_passee_complete_sans_reecrire(session, bases):
    from backend.models import Personne

    _ingerer(session, "2026-2027", _ligne(8761, "SAILLOUR", "Aaron", "3_PM"))
    _ingerer(session, "2025-2026", _ligne(
        8761, "SAILLOUR", "Aaron", "3_PM", ine="0123456789A",
        date_naissance=date(2011, 4, 3),
    ))
    _ingerer(session, "2025-2026", _ligne(
        8761, "SAILLOUR", "Aaron", "3_PM", ine="9999999999Z",
        date_naissance=date(1999, 1, 1),
    ))
    session.expire_all()
    p = session.query(Personne).one()
    assert (p.ine, p.date_naissance) == ("0123456789A", date(2011, 4, 3))


def test_un_eleve_deja_connu_sous_un_autre_numero_est_signale(session, bases):
    """Le cas d'Aaron, l'an prochain : l'export NDK porte l'INE que l'export
    NDE avait donné à sa première fiche."""
    _ingerer(session, "2025-2026", _ligne(717, "SAILLOUR", "Aaron", "4J", ine="0123456789A"))
    r = _ingerer(session, "2026-2027", _ligne(8761, "SAILLOUR", "Aaron", "3_PM", ine="0123456789A"))
    assert any("E717 = E8761" in a or "E8761 = E717" in a for a in r.avertissements)
    assert any("Départager" in a for a in r.avertissements)


def test_des_homonymes_que_la_naissance_distingue_ne_demandent_rien(session, bases):
    """Deux Hugo GUILLOU dans le même export, nés à deux dates : deux
    personnes, et c'est un fait. L'arbitrage se tranche seul."""
    from backend.models import Arbitrage

    _ingerer(
        session, "2026-2027",
        _ligne(8000, "GUILLOU", "Hugo", "2_2", date_naissance=date(2010, 5, 1)),
        _ligne(8100, "GUILLOU", "Hugo", "52", date_naissance=date(2014, 9, 12)),
    )
    a = session.query(Arbitrage).filter_by(type_cas="homonymie_ingestion").one()
    assert a.decision == "personnes_distinctes" and a.date_decision is not None
    assert "naissance" in a.note


def test_des_homonymes_sans_preuve_restent_a_trancher(session, bases):
    from backend.models import Arbitrage

    _ingerer(
        session, "2026-2027",
        _ligne(8000, "GUILLOU", "Hugo", "2_2", date_naissance=date(2010, 5, 1)),
        _ligne(8100, "GUILLOU", "Hugo", "52"),
    )
    a = session.query(Arbitrage).filter_by(type_cas="homonymie_ingestion").one()
    assert a.date_decision is None, "une date manquante ne prouve rien"


# ---------------------------------------------------------------------------
# Même personne, ou deux
# ---------------------------------------------------------------------------


def _fiche(personne_factory, bases, id_ch, nom, prenom, site, **kw):
    return personne_factory(
        id_charlemagne=id_ch, nom=nom, prenom=prenom, site_id=bases[site].id,
        login=f"{prenom[0].lower()}{nom.lower()}{id_ch}", **kw,
    )


def test_le_meme_ine_suffit_quel_que_soit_le_nom(session, bases, personne_factory):
    from backend.services.fusion import evaluer_lien

    a = _fiche(personne_factory, bases, 717, "LE MOING", "Lili", "NDE", ine="0123456789A")
    b = _fiche(personne_factory, bases, 8761, "LE MOING PORHEL", "Lili", "SU", ine="0123456789A")
    lien = evaluer_lien(a, b, set())
    assert (lien.probable, lien.preuve) == (True, "ine")


def test_deux_ine_ou_deux_naissances_font_deux_personnes(session, bases, personne_factory):
    """Même quand tout le reste dirait « même personne » : une seule des deux
    inscrite cette année, même nom."""
    from backend.services.fusion import evaluer_lien

    a = _fiche(personne_factory, bases, 717, "SAILLOUR", "Aaron", "NDE", ine="0123456789A")
    b = _fiche(personne_factory, bases, 8761, "SAILLOUR", "Aaron", "NDK", ine="0987654321B")
    lien = evaluer_lien(a, b, {b.id})
    assert not lien.probable and "Deux INE" in lien.contradiction

    c = _fiche(personne_factory, bases, 718, "GUILLOU", "Hugo", "NDE", date_naissance=date(2010, 5, 1))
    d = _fiche(personne_factory, bases, 8762, "GUILLOU", "Hugo", "NDK", date_naissance=date(2014, 9, 12))
    lien = evaluer_lien(c, d, {d.id})
    assert not lien.probable and "01/05/2010" in lien.contradiction


def test_meme_nom_meme_naissance_meme_si_les_deux_sont_inscrites(
    session, bases, personne_factory
):
    """Une réinscription sous un nouveau numéro, en cours d'année : les deux
    fiches sont inscrites, la naissance tranche."""
    from backend.services.fusion import evaluer_lien

    a = _fiche(personne_factory, bases, 8000, "GUEGUEN", "Justine", "NDK", date_naissance=date(2009, 2, 3))
    b = _fiche(personne_factory, bases, 8900, "GUEGUEN", "Justine", "NDK", date_naissance=date(2009, 2, 3))
    lien = evaluer_lien(a, b, {a.id, b.id})
    assert (lien.probable, lien.preuve) == (True, "naissance")


def test_la_fusion_reprend_l_ine_et_la_naissance(session, bases, personne_factory):
    from backend.models import Personne
    from backend.services.fusion import fusionner

    ancien = _fiche(
        personne_factory, bases, 717, "SAILLOUR", "Aaron", "NDE",
        ine="0123456789A", date_naissance=date(2011, 4, 3),
    )
    actuel = _fiche(personne_factory, bases, 8761, "SAILLOUR", "Aaron", "NDK")
    actuel_id = actuel.id
    r = fusionner(session, ancien.id, actuel_id, mode="reel")

    p = session.get(Personne, actuel_id)
    assert (p.ine, p.date_naissance) == ("0123456789A", date(2011, 4, 3))
    assert "la date de naissance : 03/04/2011" in r.repris


def test_une_fusion_contredite_le_dit(session, bases, personne_factory):
    from backend.services.fusion import fusionner

    a = _fiche(personne_factory, bases, 717, "SAILLOUR", "Aaron", "NDE", ine="0123456789A")
    b = _fiche(personne_factory, bases, 8761, "SAILLOUR", "Aaron", "NDK", ine="0987654321B")
    r = fusionner(session, a.id, b.id)
    assert any("Deux INE" in x for x in r.avertissements)


# ---------------------------------------------------------------------------
# Les doublons sans adresse disputée
# ---------------------------------------------------------------------------


@pytest.fixture()
def client(tmp_db_path):
    from backend.main import app

    with TestClient(app) as c:
        yield c


def test_un_doublon_sans_adresse_commune_a_sa_place(
    client, session, bases, personne_factory, annee_factory
):
    """Passé de NDE à NDK sous une adresse neuve : aucune adresse disputée,
    et pourtant un seul élève. L'INE le retrouve ; le constat le compte."""
    from backend.models import Snapshot
    from backend.services.anomalies import detecter_anomalies

    an = annee_factory("2026-2027")
    ancien = _fiche(
        personne_factory, bases, 717, "SAILLOUR", "Aaron", "NDE",
        ine="0123456789A", email_constate="aaron.saillour@lekreisker.fr",
    )
    actuel = _fiche(
        personne_factory, bases, 8761, "SAILLOUR", "Aaron", "NDK",
        ine="0123456789A", email_constate="a.saillour@lekreisker.fr",
    )
    session.add(Snapshot(personne_id=actuel.id, annee_scolaire_id=an.id,
                         nom="SAILLOUR", prenom="Aaron", classe="3_PM"))
    session.commit()

    assert client.get("/api/personnes/collisions").json() == []
    doublons = client.get("/api/personnes/doublons").json()
    assert len(doublons) == 1
    d = doublons[0]
    assert (d["preuve"], d["garde_id"]) == ("ine", actuel.id)
    assert d["motif"].startswith("Même INE.")
    assert [v["cle_pivot"] for v in d["visants"]] == ["E8761", "E717"]

    types = {a.type for a in detecter_anomalies(session).anomalies}
    assert "doublon_fiche" in types

    r = client.post("/api/personnes/fusion", json={"ids": [ancien.id, actuel.id], "mode": "reel"})
    assert r.status_code == 200, r.text
    assert client.get("/api/personnes/doublons").json() == []


def test_une_paire_qui_se_dispute_une_adresse_n_apparait_qu_une_fois(
    client, session, bases, personne_factory
):
    _fiche(personne_factory, bases, 717, "SAILLOUR", "Aaron", "NDE", ine="0123456789A")
    _fiche(
        personne_factory, bases, 8761, "SAILLOUR", "Aaron", "NDK",
        ine="0123456789A", email_constate="aaron.saillour@lekreisker.fr",
    )
    collisions = client.get("/api/personnes/collisions").json()
    assert len(collisions) == 1 and collisions[0]["preuve"] == "ine"
    assert client.get("/api/personnes/doublons").json() == []


# ---------------------------------------------------------------------------
# KoXo
# ---------------------------------------------------------------------------


def test_koxo_recoit_la_date_au_seul_format_qu_il_compare(session, bases, personne_factory):
    """Le repli de KoXo compare des chaînes : `01/02/12` n'est pas
    `01/02/2012`. Un seul format, jour d'abord, année sur quatre chiffres."""
    from backend.services.exports_koxo import _date_pour_koxo

    p = _fiche(personne_factory, bases, 8761, "SAILLOUR", "Aaron", "NDK", date_naissance=date(2011, 4, 3))
    q = _fiche(personne_factory, bases, 8762, "MARTIN", "Léa", "NDK")
    assert _date_pour_koxo(p) == "03/04/2011"
    assert _date_pour_koxo(q) == "" and _date_pour_koxo(None) == ""
