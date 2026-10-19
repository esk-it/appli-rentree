"""Le fichier élèves du portail Sodexo, fabriqué par le programme.

Le 19 octobre 2026, le classeur Google qui le fabriquait n'a jamais
transmis les réductions : son script exportait l'onglet Import au lieu de
l'onglet Export. Ce qui compte ici : la règle « PassageS d'abord », et un
fichier qui s'arrête avant le portail quand il importerait mal.
"""
from __future__ import annotations

import base64
import io

import pytest

ENTETE = ("Code établissement;Code niveau;Code classe;Num Badge;Nom et prénom;Nom;Prénom;"
          "Photo;Code Régime;Date Entrée pour tri;PassageS;Code Régime")


def _edition(*lignes: str) -> bytes:
    """L'édition « Export vers SoHappy », telle que l'onglet Import la porte."""
    return "\n".join((ENTETE, *lignes)).encode("utf-8")


def _ligne(badge, nom, prenom, regime="D", passage="", classe="2_1", regime2=None):
    regime2 = regime if regime2 is None else regime2
    return (f"03-LY;1-2NDES-LY;{classe};{badge};{nom} {prenom};{nom};{prenom};"
            f"\\\\photos\\{badge}.jpg;{regime};20260901;{passage};{regime2}")


def test_le_code_particulier_passe_avant_le_regime():
    from backend.services.sodexo_fichier import fabriquer

    r = fabriquer(None, _edition(
        _ligne(90010, "FICTIF", "Alice", "D"),
        _ligne(90020, "EXEMPLE", "Bruno", "D", passage="10POGEC"),
        _ligne(90030, "MODELE", "Chloé", "E", passage="10P"),
    ), "edition.csv")

    assert r.pret
    assert [(e.badge, e.code) for e in r.eleves] == [
        ("90010", "D"), ("90020", "10POGEC"), ("90030", "10P")]
    assert [e.badge for e in r.particuliers] == ["90030", "90020"]
    assert r.par_code == {"D": 1, "10POGEC": 1, "10P": 1}


def test_le_regime_se_prend_dans_la_premiere_colonne_remplie():
    from backend.services.sodexo_fichier import fabriquer

    r = fabriquer(None, _edition(_ligne(90010, "FICTIF", "Alice", regime="", regime2="P")),
                  "edition.csv")
    assert r.eleves[0].code == "P"


def test_un_code_que_le_portail_ne_connait_pas_arrete_le_fichier():
    """75P figurait dans la procédure d'origine ; le portail n'a pas ce profil."""
    from backend.services.sodexo_fichier import fabriquer

    r = fabriquer(None, _edition(
        _ligne(90010, "FICTIF", "Alice"),
        _ligne(90020, "EXEMPLE", "Bruno", passage="75P"),
    ), "edition.csv")
    assert not r.pret
    assert "« 75P » n'existe pas comme profil" in r.erreurs[0]

    r = fabriquer(None, _edition(_ligne(90020, "EXEMPLE", "Bruno", passage="75P")),
                  "edition.csv", profils=["D", "E", "P", "75P"])
    assert r.pret, "un profil créé chez Sodexo s'ajoute aux paramètres"


def test_un_code_tape_a_la_main_prend_l_orthographe_du_portail():
    """Charlemagne se remplit à la main : « Gratuité » est GRATUITE."""
    from backend.services.sodexo_fichier import en_csv, fabriquer

    r = fabriquer(None, _edition(
        _ligne(90010, "FICTIF", "Alice", passage="Gratuité"),
        _ligne(90020, "EXEMPLE", "Bruno", passage="gratuite"),
        _ligne(90030, "MODELE", "Chloé", passage="10 POGEC"),
    ), "edition.csv")
    assert r.pret
    assert [e.code for e in r.eleves] == ["GRATUITE", "GRATUITE", "10POGEC"]
    assert any("« Gratuité » (1 élève) : envoyé « GRATUITE »" in a for a in r.avertissements)
    assert b";GRATUITE;" in en_csv(r) and "Gratuit" not in en_csv(r).decode()


def test_les_doublons():
    from backend.services.sodexo_fichier import fabriquer

    r = fabriquer(None, _edition(
        _ligne(90010, "FICTIF", "Alice"),
        _ligne(90010, "FICTIF", "Alice"),
    ), "edition.csv")
    assert r.pret and len(r.eleves) == 1
    assert "1 ligne(s) en double" in r.avertissements[0]

    r = fabriquer(None, _edition(
        _ligne(90010, "FICTIF", "Alice"),
        _ligne(90010, "EXEMPLE", "Bruno"),
    ), "edition.csv")
    assert not r.pret and "porte deux élèves différents" in r.erreurs[0]


def test_les_badges():
    from backend.services.sodexo_fichier import fabriquer

    r = fabriquer(None, _edition(_ligne("90010.0", "FICTIF", "Alice")), "edition.csv")
    assert r.eleves[0].badge == "90010", "un badge lu comme nombre par Excel"
    r = fabriquer(None, _edition(_ligne("", "FICTIF", "Alice"), _ligne("A12", "EXEMPLE", "Bruno")),
                  "edition.csv")
    assert not r.pret and len(r.erreurs) == 2


def test_le_fichier_a_la_forme_que_le_portail_accepte():
    """UTF-8 sans BOM, point-virgule, LF : la forme du dernier CSV accepté."""
    from backend.services.sodexo_fichier import COLONNES_SORTIE, en_csv, fabriquer

    r = fabriquer(None, _edition(
        _ligne(90010, "FICTIF;ESSAI", "Alice"),
        _ligne(90020, "EXEMPLE", "Bruno", passage="10POGEC"),
    ), "edition.csv")
    octets = en_csv(r)
    assert not octets.startswith(b"\xef\xbb\xbf") and b"\r" not in octets
    lignes = octets.decode("utf-8").split("\n")
    assert lignes[0].split(";") == COLONNES_SORTIE
    assert all(len(l.split(";")) == 9 for l in lignes), "un ; dans un nom ne décale rien"
    assert lignes[2].split(";")[3:5] == ["90020", "10POGEC"]


def test_l_edition_se_lit_aussi_en_xlsx():
    from openpyxl import Workbook

    from backend.services.sodexo_fichier import fabriquer

    wb = Workbook()
    ws = wb.active
    ws.append(ENTETE.split(";"))
    ws.append(["03-LY", "1-2NDES-LY", "2_1", 90010, "FICTIF Alice", "FICTIF", "Alice", "",
               "D", "20260901", "10P", "D"])
    tampon = io.BytesIO()
    wb.save(tampon)

    r = fabriquer(None, tampon.getvalue(), "Liste des élèves - Export vers SoHappy.xlsx")
    assert [(e.badge, e.code) for e in r.eleves] == [("90010", "10P")]


def test_un_fichier_qui_n_est_pas_l_edition_est_refuse():
    from backend.services.sodexo_fichier import FichierSodexoImpossible, fabriquer

    with pytest.raises(FichierSodexoImpossible, match="Num Badge"):
        fabriquer(None, b"Nom;Prenom\nFICTIF;Alice", "autre.csv")


def test_le_referentiel_en_regard(session, annee_factory, site_factory, personne_factory):
    from backend.models import Snapshot
    from backend.services.sodexo_fichier import fabriquer

    annee = annee_factory("2026-2027")
    ndk = site_factory("NDK")
    present = personne_factory(type="eleve", nom="FICTIF", prenom="Alice", site_id=ndk.id, classe="2_1")
    oublie = personne_factory(type="eleve", nom="OUBLIE", prenom="Damien", site_id=ndk.id, classe="2_1")
    for p in (present, oublie):
        session.add(Snapshot(personne_id=p.id, annee_scolaire_id=annee.id, nom=p.nom,
                             prenom=p.prenom, classe="2_1"))
    session.commit()

    r = fabriquer(session, _edition(
        _ligne(present.badge, "FICTIF", "Alice"),
        _ligne(99990, "INCONNU", "Emma"),
    ), "edition.csv")
    assert r.absents == ["Damien OUBLIE (NDK, 2_1)"]
    assert r.inconnus == ["Emma INCONNU (2_1, badge 99990)"]
    assert r.pret, "des avertissements, pas des erreurs"
    assert r.referentiel_du is not None
    assert any("au référentiel (dernier export lu le" in a for a in r.avertissements)


def test_un_absent_qui_n_est_pas_encore_arrive(session, annee_factory, site_factory,
                                               personne_factory):
    """Charlemagne ne sort un élève qu'à partir de sa date d'entrée."""
    from datetime import date

    from backend.models import Snapshot
    from backend.services.sodexo_fichier import _recouper, fabriquer

    annee = annee_factory("2026-2027")
    ndk = site_factory("NDK")
    present = personne_factory(type="eleve", nom="FICTIF", prenom="Alice", site_id=ndk.id, classe="2_1")
    attendue = personne_factory(type="eleve", nom="FUTURE", prenom="Berthe", site_id=ndk.id,
                                classe="2_3", date_entree=date(2026, 11, 2))
    for p in (present, attendue):
        session.add(Snapshot(personne_id=p.id, annee_scolaire_id=annee.id, nom=p.nom,
                             prenom=p.prenom, classe=p.classe))
    session.commit()

    r = fabriquer(None, _edition(_ligne(present.badge, "FICTIF", "Alice")), "edition.csv")
    _recouper(session, r, None, aujourd_hui=date(2026, 10, 19))
    assert r.absents == ["Berthe FUTURE (NDK, 2_3, entrée le 02/11/2026)"]
    r.absents = []
    _recouper(session, r, None, aujourd_hui=date(2026, 11, 3))
    assert r.absents == ["Berthe FUTURE (NDK, 2_3)"], "arrivée : un absent comme un autre"


@pytest.fixture()
def client(tmp_db_path):
    from fastapi.testclient import TestClient

    from backend.main import app

    with TestClient(app) as c:
        yield c


def test_par_l_api(client):
    def envoyer(contenu):
        return client.post("/api/sodexo/fichier", json={
            "fichier_base64": base64.b64encode(contenu).decode(),
            "nom_fichier": "edition.csv",
        }).json()

    r = envoyer(_edition(_ligne(90010, "FICTIF", "Alice", passage="10POGEC")))
    assert r["pret"] and r["par_code"] == {"10POGEC": 1}
    assert base64.b64decode(r["csv_base64"]).decode().split("\n")[1].split(";")[4] == "10POGEC"
    assert r["nom_fichier"].startswith("Sodexo_eleves_")

    r = envoyer(_edition(_ligne(90010, "FICTIF", "Alice", passage="PREFERENTIEL")))
    assert not r["pret"] and r["csv_base64"] is None

    client.put("/api/parametres/sodexo.profils_eleves", json={"valeur": ["D", "PREFERENTIEL"]})
    r = envoyer(_edition(_ligne(90010, "FICTIF", "Alice", passage="PREFERENTIEL")))
    assert r["pret"], "la liste des profils est un réglage"
