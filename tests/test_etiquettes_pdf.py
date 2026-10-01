"""Les étiquettes en PDF : la planche par classe, et le format au choix.

« Étiquettes en PDF, une planche par classe » échouait sur `TypeError: data
must be str, not bytes` : les planches sortent en octets depuis la v0.141,
la conversion n'acceptait que du texte, et aucun test ne passait par ce
chemin entier. Ceux-ci le parcourent, de l'export KoXo à l'archive.
"""
from __future__ import annotations

import base64
import io
import zipfile

import pytest
from fastapi.testclient import TestClient


@pytest.fixture()
def client(tmp_db_path):
    from backend.main import app

    with TestClient(app) as c:
        yield c


def _module_impression():
    """Le module tel que l'appli l'importera pendant ce test.

    `from backend.services import impression_pdf` rendrait l'attribut resté
    sur le paquet — le module d'un test précédent, que la conftest a purgé
    de `sys.modules` mais pas du paquet. Le remplacer là laissait le vrai
    Edge imprimer."""
    import importlib

    return importlib.import_module("backend.services.impression_pdf")


@pytest.fixture()
def faux_navigateur(monkeypatch, tmp_path):
    """Edge n'imprime pas pendant les tests : un faux écrit un faux PDF, et
    garde ce qu'on lui a donné à lire."""
    impression_pdf = _module_impression()

    lus: list[bytes] = []

    def imprimer(moteur, source, cible, profil):
        lus.append(source.read_bytes())
        cible.write_bytes(b"%PDF-1.4 faux")

    monkeypatch.setattr(impression_pdf, "trouver_navigateur", lambda: str(tmp_path / "edge.exe"))
    monkeypatch.setattr(impression_pdf, "_imprimer", imprimer)
    return lus


@pytest.fixture()
def export_koxo(session, site_factory, annee_factory, personne_factory):
    """SU, une élève en 61, et l'export KoXo qui porte son mot de passe."""
    from backend.models import Snapshot

    su = site_factory("SU")
    annee = annee_factory("2026-2027")
    p = personne_factory(type="eleve", site_id=su.id, nom="ABGRALL", prenom="Léna", login="labgrall")
    session.add(Snapshot(personne_id=p.id, annee_scolaire_id=annee.id, nom="ABGRALL", prenom="Léna", classe="61"))
    session.commit()
    entetes = ["Groupe primaire", "Groupe secondaire", "Nom", "Prénom",
               "Identifiant", "ID unique", "Mot de passe", "Email"]
    ligne = ["Eleves", "61", "ABGRALL", "Léna", "labgrall", str(p.badge), "Mdp00001", "lena.abgrall@lekreisker.fr"]
    contenu = (";".join(entetes) + "\r\n" + ";".join(ligne) + "\r\n").encode("cp1252")
    return {"site": su, "annee": annee, "b64": base64.b64encode(contenu).decode()}


def _corps(e, **kw):
    return {"koxo_base64": e["b64"], "site_id": e["site"].id, "annee_cible_id": e["annee"].id, **kw}


def test_une_planche_en_octets_se_convertit(faux_navigateur, tmp_path):
    from backend.services.impression_pdf import Planche, rendre

    r = rendre([Planche(nom="61", html="<p>Léna</p>".encode("utf-8"))])
    assert r.pdfs["61"].startswith(b"%PDF") and not r.echecs
    assert faux_navigateur == ["<p>Léna</p>".encode("utf-8")], "les octets passent tels quels"


def test_les_planches_par_classe_sortent_dans_une_archive(client, export_koxo, faux_navigateur):
    r = client.post("/api/exports/etiquettes-par-classe", json=_corps(export_koxo))
    assert r.status_code == 200, r.text
    corps = r.json()
    assert [p["classe"] for p in corps["planches"]] == ["61"]
    archive = zipfile.ZipFile(io.BytesIO(base64.b64decode(corps["zip_base64"])))
    (nom,) = archive.namelist()
    assert nom.endswith(".pdf") and archive.read(nom).startswith(b"%PDF")


def test_les_etiquettes_sortent_en_pdf_par_defaut(client, export_koxo, faux_navigateur):
    r = client.post("/api/exports/listes-koxo", json=_corps(export_koxo)).json()
    assert r["nom_etiquettes_tous"].endswith(".pdf")
    assert base64.b64decode(r["etiquettes_tous_base64"]).startswith(b"%PDF")
    assert r["avertissements"] == []
    assert len(faux_navigateur) == 1, "le faux navigateur a bien imprimé, pas Edge"


def test_le_html_reste_au_choix(client, export_koxo, faux_navigateur):
    r = client.post("/api/exports/listes-koxo", json=_corps(export_koxo, format_etiquettes="html")).json()
    assert r["nom_etiquettes_tous"].endswith(".html")
    assert b"<html" in base64.b64decode(r["etiquettes_tous_base64"]).lower()
    assert faux_navigateur == [], "en HTML, le navigateur n'est pas sollicité"


def test_sans_navigateur_les_etiquettes_restent_en_html_et_c_est_dit(
    client, export_koxo, monkeypatch
):
    monkeypatch.setattr(_module_impression(), "trouver_navigateur", lambda: None)
    r = client.post("/api/exports/listes-koxo", json=_corps(export_koxo)).json()
    assert r["nom_etiquettes_tous"].endswith(".html")
    assert any("PDF impossible" in a for a in r["avertissements"])
