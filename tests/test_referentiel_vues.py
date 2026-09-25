"""Les trois vues du Référentiel : ce que le serveur leur donne.

La liste a besoin de savoir, pour chacun, si le coffre garde un mot de
passe — sans l'ouvrir. La vue par classe imprime un trombinoscope. Le
relevé « ce qui manque » compte, classe par classe, ce que les fiches
portent.
"""
from __future__ import annotations

import base64
from datetime import date, datetime

import pytest
from fastapi.testclient import TestClient


@pytest.fixture()
def ecole(session, site_factory, annee_factory):
    """NDK et SU, deux classes, une année, des élèves et une professeure."""
    from backend.models import Personne, Snapshot, TableCorrespondance

    ndk, su = site_factory("NDK"), site_factory("SU")
    an = annee_factory("2026-2027")
    session.add_all([
        TableCorrespondance(
            site_id=ndk.id, classe_charlemagne_long="1_G4", classe_code_court="1_G4",
            ou_pre_rentree="/NDK", ou_definitive="/NDK/1_G4",
            code_niveau="1-1ERES-LY", code_etablissement="03-LY",
        ),
        TableCorrespondance(
            site_id=su.id, classe_charlemagne_long="31", classe_code_court="31",
            ou_pre_rentree="/SU", ou_definitive="/SU/31",
        ),
    ])
    session.commit()

    def personne(id_ch, nom, prenom, site, classe=None, type_="eleve", **kw):
        p = Personne(
            type=type_, id_charlemagne=id_ch,
            badge=Personne.calculer_badge(type_, id_ch),
            login=f"{prenom[0].lower()}{nom.lower()}{id_ch}", nom=nom, prenom=prenom,
            site_id=site.id, classe=classe, **kw,
        )
        session.add(p)
        session.flush()
        session.add(Snapshot(
            personne_id=p.id, annee_scolaire_id=an.id, nom=nom, prenom=prenom,
            classe=classe, date_ingestion=datetime(2026, 9, 1),
        ))
        return p

    gens = {
        "lea": personne(9001, "TANGUY", "Léane", ndk, "1_G4",
                        email_constate="leane.tanguy@lekreisker.fr", ine="0123456789A",
                        date_naissance=date(2009, 4, 3)),
        "mat": personne(9002, "LE BRIS", "Mathis", ndk, "1_G4"),
        "cam": personne(9003, "NEDELEC", "Camille", su, "31",
                        email_constate="camille.nedelec@lekreisker.fr"),
        "prof": personne(120, "KERGOAT", "Hélène", ndk, None, "adulte",
                         email_constate="helene.kergoat@lekreisker.fr",
                         classes_prof_principal="1_G4"),
    }
    session.commit()
    return {"an": an, "ndk": ndk, "su": su, **gens}


def _deposer_secret(session, personne_id):
    from backend.models import SecretConserve

    session.add(SecretConserve(
        personne_id=personne_id, cible="koxo", site="NDK", nonce=b"0" * 12,
        chiffre=b"chiffre", origine="koxo",
    ))
    session.commit()


@pytest.fixture()
def client(tmp_db_path):
    from backend.main import app

    with TestClient(app) as c:
        yield c


def test_la_liste_dit_qui_a_un_mot_de_passe_au_coffre_sans_l_ouvrir(client, session, ecole):
    _deposer_secret(session, ecole["lea"].id)

    par_login = {p["login"]: p for p in client.get("/api/personnes").json()}
    lea = par_login[ecole["lea"].login]
    assert lea["au_coffre"] is True
    assert par_login[ecole["mat"].login]["au_coffre"] is False
    assert "mot_de_passe" not in lea and "chiffre" not in str(lea)
    assert par_login[ecole["prof"].login]["classes_prof_principal"] == "1_G4"


def test_le_releve_compte_ce_que_chaque_classe_porte(session, ecole):
    from backend.models import VerdictCoherence
    from backend.services.completude import relever

    _deposer_secret(session, ecole["lea"].id)
    session.add(VerdictCoherence(
        personne_id=ecole["lea"].id, systeme="koxo", etat="accord",
        verifie_le=datetime(2026, 9, 20),
    ))
    session.add(VerdictCoherence(
        personne_id=ecole["mat"].id, systeme="koxo", etat="ecart",
        verifie_le=datetime(2026, 9, 20),
    ))
    session.commit()

    r = relever(session)
    assert (r.annee, r.effectif, r.eleves, r.adultes) == ("2026-2027", 4, 3, 1)
    assert (r.avec_adresse, r.au_coffre, r.avec_ine, r.avec_naissance) == (3, 1, 1, 1)
    assert (r.classes, r.classes_avec_codes) == (2, 1)

    par_classe = {c.classe: c for c in r.par_classe}
    g4 = par_classe["1_G4"]
    assert (g4.site, g4.effectif, g4.avec_adresse, g4.au_coffre, g4.avec_ine) == ("NDK", 2, 1, 1, 1)
    assert (g4.codes_carte, g4.verifies, g4.coherents) == (True, 2, 1)
    assert par_classe["31"].codes_carte is False
    assert [c.classe for c in r.par_classe] == ["1_G4", "31"], "par site, puis par classe"


def test_un_partage_des_photos_injoignable_ne_vaut_pas_zero(session, ecole):
    """« On n'a pas regardé » n'est pas « il n'y en a pas »."""
    from backend.services.completude import relever

    r = relever(session)
    assert r.avec_photo is None
    assert all(c.avec_photo is None for c in r.par_classe)
    assert r.photos_injoignables


def test_le_releve_passe_par_l_ecran(client, session, ecole):
    r = client.get("/api/personnes/completude").json()
    assert r["effectif"] == 4
    assert {c["classe"] for c in r["par_classe"]} == {"1_G4", "31"}


# ---------------------------------------------------------------------------
# Le trombinoscope
# ---------------------------------------------------------------------------


def test_la_planche_porte_la_classe_et_ses_eleves(session, ecole):
    from backend.services.trombinoscope import composer

    t = composer(session, classe="1_G4")
    assert (t.classe, t.annee, t.site, t.nb_eleves) == ("1_G4", "2026-2027", "NDK", 2)
    assert t.nb_sans_photo == 2, "sans partage réglé, les initiales tiennent la place"
    assert "LE BRIS" in t.html and "Léane" in t.html
    assert t.html.index("LE BRIS") < t.html.index("TANGUY"), "par ordre alphabétique"
    assert "KERGOAT" not in t.html, "une professeure n'est pas une élève de la classe"


def test_la_planche_porte_le_logo_du_site(session, ecole):
    """Le logo voyage dans la page, comme les photos : la planche s'imprime
    sans rien aller chercher."""
    from backend.services.modeles_etiquettes import logo_du_site
    from backend.services.trombinoscope import composer

    t = composer(session, classe="1_G4")
    assert f'<img class="logo" src="{logo_du_site("NDK")}"' in t.html
    assert "Ensemble Scolaire Le Kreisker" in t.html


def test_une_classe_sans_site_connu_porte_les_losanges_de_l_ensemble(session, ecole):
    from backend.models import Snapshot
    from backend.services.modeles_etiquettes import logo_du_site
    from backend.services.trombinoscope import composer

    # Une classe que la table de correspondance ne connaît pas encore.
    session.query(Snapshot).filter_by(personne_id=ecole["cam"].id).update({"classe": "99"})
    session.commit()

    t = composer(session, classe="99")
    assert t.site is None
    assert logo_du_site("ESK"), "le logo de l'ensemble est livré avec l'application"
    assert f'<img class="logo" src="{logo_du_site("ESK")}"' in t.html


def test_une_photo_voyage_dans_la_page(tmp_path):
    from backend.services.trombinoscope import _photo_en_donnees

    image = tmp_path / "LE BRIS Mathis.jpg"
    image.write_bytes(b"\xff\xd8\xff\xe0 fausse image")
    donnees = _photo_en_donnees(str(image))
    assert donnees.startswith("data:image/jpeg;base64,")
    assert base64.b64decode(donnees.split(",", 1)[1]).startswith(b"\xff\xd8")
    assert _photo_en_donnees(str(tmp_path / "absente.jpg")) is None
    assert _photo_en_donnees(str(tmp_path / "notes.txt")) is None


def test_une_classe_vide_le_dit(session, ecole):
    from backend.services.trombinoscope import TrombinoscopeImpossible, composer

    with pytest.raises(TrombinoscopeImpossible, match="Aucun élève"):
        composer(session, classe="2_9")


def test_le_trombinoscope_sort_en_pdf(client, session, ecole, monkeypatch):
    """Le navigateur du poste imprime ; ici, on le remplace."""
    import backend.services.impression_pdf as impression

    rendus = []
    monkeypatch.setattr(impression, "html_en_pdf", lambda html: rendus.append(html) or b"%PDF-1.7 essai")

    r = client.post("/api/personnes/trombinoscope", json={"classe": "1_G4"})
    assert r.status_code == 200, r.text
    corps = r.json()
    assert corps["nom_fichier"].startswith("Trombinoscope_1_G4_2026-2027")
    assert corps["nom_fichier"].endswith(".pdf")
    assert base64.b64decode(corps["pdf_base64"]) == b"%PDF-1.7 essai"
    assert (corps["nb_eleves"], corps["nb_sans_photo"]) == (2, 2)
    assert "TANGUY" in rendus[0]

    assert client.post("/api/personnes/trombinoscope", json={"classe": "2_9"}).status_code == 404


def test_le_releve_peut_se_passer_des_photos(session, ecole, tmp_path):
    """Sans les photos, le relevé ne regarde pas le partage — et le dit :
    « pas regardé » n'est ni zéro ni « injoignable »."""
    import json

    from backend.models import Parametre
    from backend.services.completude import relever

    session.add(Parametre(cle="chemin_dossier_photos", valeur_json=json.dumps(str(tmp_path))))
    session.commit()
    (tmp_path / "TANGUY Léane.jpg").write_bytes(b"x")

    sans = relever(session, photos=False)
    assert (sans.photos_lues, sans.avec_photo, sans.photos_injoignables) == (False, None, None)
    assert all(c.avec_photo is None for c in sans.par_classe)
    assert sans.effectif == 4, "le reste est compté pareil"

    avec = relever(session, photos=True)
    assert (avec.photos_lues, avec.avec_photo) == (True, 1)


def test_le_releve_sans_photos_passe_par_l_ecran(client, session, ecole):
    r = client.get("/api/personnes/completude", params={"photos": "false"}).json()
    assert r["photos_lues"] is False and r["avec_photo"] is None
    assert r["photos_injoignables"] is None


def test_une_photo_se_garde_une_absence_moins_longtemps(client, session, ecole, tmp_path):
    """Le navigateur garde la photo une heure, et l'absence dix minutes."""
    import json

    from backend.models import Parametre

    session.add(Parametre(cle="chemin_dossier_photos", valeur_json=json.dumps(str(tmp_path))))
    session.commit()
    (tmp_path / "TANGUY Léane.jpg").write_bytes(b"\xff\xd8\xff")

    r = client.get(f"/api/photos/{ecole['lea'].id}")
    assert r.status_code == 200
    assert r.headers["cache-control"] == "private, max-age=3600"

    r = client.get(f"/api/photos/{ecole['mat'].id}")
    assert r.status_code == 404
    assert r.headers["cache-control"] == "private, max-age=600"
