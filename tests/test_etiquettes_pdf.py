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


# ---------------------------------------------------------------------------
# Sans fichier : le coffre
# ---------------------------------------------------------------------------


@pytest.fixture()
def coffre_ouvert(client, session, export_koxo):
    """Le coffre ouvert par l'API, et le mot de passe de Léna rangé dedans
    comme l'ingestion de l'export Charlemagne enrichi l'y range."""
    import importlib

    from backend.services.coffre import deposer

    routeur = importlib.import_module("backend.routers.coffre")
    client.post("/api/coffre/verrouiller")
    assert client.post(
        "/api/coffre/initialiser", json={"mot_de_passe": "maitre-essai-longue-phrase"}
    ).status_code == 200
    eleve = session.query(importlib.import_module("backend.models").Personne).one()
    deposer(session, routeur._CLE, personne_id=eleve.id, mot_de_passe="Coffre11",
            cible="charlemagne", origine="charlemagne", identifiant="labgrall")
    session.commit()
    yield
    client.post("/api/coffre/verrouiller")


def _sans_fichier(e, **kw):
    return {"site_id": e["site"].id, "annee_cible_id": e["annee"].id, **kw}


def test_sans_fichier_et_coffre_ferme_le_refus_le_dit(client, export_koxo):
    client.post("/api/coffre/verrouiller")
    r = client.post("/api/exports/listes-koxo", json=_sans_fichier(export_koxo))
    assert r.status_code == 401 and "coffre est fermé" in r.json()["detail"]


def test_sans_fichier_les_listes_partent_du_coffre(client, export_koxo, coffre_ouvert):
    r = client.post(
        "/api/exports/listes-koxo", json=_sans_fichier(export_koxo, format_etiquettes="html")
    )
    assert r.status_code == 200, r.text
    corps = r.json()
    assert (corps["source"], corps["nb_tous"], corps["absents_de_la_source"]) == ("coffre", 1, [])
    assert b"Coffre11" in base64.b64decode(corps["etiquettes_tous_base64"])


def test_sans_fichier_la_planche_par_classe_part_du_coffre(
    client, export_koxo, coffre_ouvert, faux_navigateur
):
    r = client.post("/api/exports/etiquettes-par-classe", json=_sans_fichier(export_koxo))
    assert r.status_code == 200, r.text
    assert [p["classe"] for p in r.json()["planches"]] == ["61"]
    assert b"Coffre11" in faux_navigateur[0]


def test_un_profil_encore_verrouille_n_emporte_pas_les_pdf(faux_navigateur, monkeypatch):
    """Edge garde son profil ouvert un instant après le PDF : « WinError 32 »
    faisait finir la planche par classe en erreur interne, PDF rendus. Le
    nettoyage réessaie, et n'échoue jamais un rendu réussi."""
    impression_pdf = _module_impression()
    vrai = impression_pdf.shutil.rmtree
    appels: list[bool] = []

    def rmtree(chemin, ignore_errors=False):
        appels.append(ignore_errors)
        if not ignore_errors and len(appels) < 3:
            raise PermissionError(32, "fichier utilisé par un autre processus")
        return vrai(chemin, ignore_errors=ignore_errors)

    monkeypatch.setattr(impression_pdf.shutil, "rmtree", rmtree)
    monkeypatch.setattr(impression_pdf.time, "sleep", lambda s: None)
    r = impression_pdf.rendre([impression_pdf.Planche(nom="61", html="<p>Léna</p>")])
    assert r.pdfs["61"].startswith(b"%PDF") and not r.echecs
    assert appels == [False, False, False], "deux refus, puis le dossier part"


def test_un_profil_qui_reste_verrouille_est_laisse_a_windows(faux_navigateur, monkeypatch):
    impression_pdf = _module_impression()
    vrai = impression_pdf.shutil.rmtree
    laisses = []

    def rmtree(chemin, ignore_errors=False):
        if not ignore_errors:
            raise PermissionError(32, "fichier utilisé par un autre processus")
        laisses.append(chemin)

    monkeypatch.setattr(impression_pdf.shutil, "rmtree", rmtree)
    monkeypatch.setattr(impression_pdf.time, "sleep", lambda s: None)
    r = impression_pdf.rendre([impression_pdf.Planche(nom="61", html="<p>Léna</p>")])
    assert r.pdfs["61"].startswith(b"%PDF") and len(laisses) == 1
    vrai(laisses[0])  # le test ne laisse rien derrière lui
