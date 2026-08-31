"""Le coffre à mots de passe.

Retrouver le mot de passe d'un élève obligeait à ouvrir KoXo. Et pour NDE,
qui n'a pas de serveur KoXo, le mot de passe n'existe nulle part : perdre
la feuille imprimée voulait dire réinitialiser le compte.

Ce que ces tests décrivent, c'est surtout ce que le coffre refuse de faire.
"""
from __future__ import annotations

import pytest

from backend.services.coffre import (
    CoffreDejaInitialise,
    CoffreVerrouille,
    chercher,
    deposer,
    est_initialise,
    fabriquer_mot_de_passe,
    initialiser,
    ouvrir,
    verser_export_koxo,
)

MAITRE = "sardine-clavier-molybdene-1789"


@pytest.fixture()
def coffre(session):
    return initialiser(session, MAITRE)


# ---------------------------------------------------------------------------
# Le mot de passe maître
# ---------------------------------------------------------------------------


def test_un_coffre_neuf_nest_pas_initialise(session):
    assert est_initialise(session) is False


def test_initialiser_puis_ouvrir_rend_la_meme_cle(session):
    cle = initialiser(session, MAITRE)
    assert est_initialise(session) is True
    assert ouvrir(session, MAITRE) == cle


def test_un_mauvais_mot_de_passe_est_refuse(session, coffre):
    with pytest.raises(CoffreVerrouille, match="incorrect"):
        ouvrir(session, "ce n'est pas le bon")


def test_un_mot_de_passe_trop_court_est_refuse(session):
    """Dix caractères au minimum : il protège deux mille secrets."""
    with pytest.raises(CoffreVerrouille, match="dix"):
        initialiser(session, "court")


def test_on_ninitialise_pas_deux_fois(session, coffre):
    """Changer le mot de passe maître suppose de tout rechiffrer."""
    with pytest.raises(CoffreDejaInitialise):
        initialiser(session, "une autre phrase de passe")


def test_ouvrir_un_coffre_inexistant_le_dit(session):
    with pytest.raises(CoffreVerrouille, match="pas encore"):
        ouvrir(session, MAITRE)


def test_le_mot_de_passe_maitre_nest_stocke_nulle_part(session, coffre):
    """La seule garantie qui compte : la base ne le contient pas.

    Ni en entier, ni par morceaux. Les fragments courts sont écartés — sur
    de l'hexadécimal, « de » se rencontre par hasard et ne prouve rien.
    """
    from backend.models import Parametre

    valeurs = " ".join(p.valeur_json for p in session.query(Parametre).all())
    assert MAITRE not in valeurs
    for morceau in MAITRE.split("-"):
        if len(morceau) >= 5:
            assert morceau not in valeurs, morceau


# ---------------------------------------------------------------------------
# Déposer et relire
# ---------------------------------------------------------------------------


def test_un_secret_depose_se_relit(session, coffre, personne_factory):
    p = personne_factory(nom="GUEGAN", prenom="Maya", login="mguegan")
    deposer(session, coffre, personne_id=p.id, mot_de_passe="Vikuge90")
    session.commit()

    trouves = chercher(session, coffre, "guegan")
    assert len(trouves) == 1
    assert trouves[0].mot_de_passe == "Vikuge90"
    assert trouves[0].login == "mguegan"


def test_le_secret_nest_pas_en_clair_dans_la_base(session, coffre,
                                                  personne_factory):
    from backend.models import SecretConserve

    p = personne_factory(login="mguegan")
    deposer(session, coffre, personne_id=p.id, mot_de_passe="Vikuge90")
    session.commit()

    s = session.query(SecretConserve).one()
    assert b"Vikuge90" not in s.chiffre
    assert s.chiffre != b"Vikuge90"


def test_une_autre_cle_nouvre_pas_le_secret(session, coffre, personne_factory):
    """C'est ce qui rend le fichier de base inutile, copié seul."""
    p = personne_factory(login="mguegan")
    deposer(session, coffre, personne_id=p.id, mot_de_passe="Vikuge90")
    session.commit()

    autre = b"\x00" * 32
    with pytest.raises(CoffreVerrouille, match="autre mot de passe maître"):
        chercher(session, autre, "mguegan")


def test_deposer_deux_fois_remplace(session, coffre, personne_factory):
    from backend.models import SecretConserve

    p = personne_factory(login="mguegan")
    deposer(session, coffre, personne_id=p.id, mot_de_passe="Vikuge90")
    deposer(session, coffre, personne_id=p.id, mot_de_passe="Zidpes09")
    session.commit()

    assert session.query(SecretConserve).count() == 1
    assert chercher(session, coffre, "mguegan")[0].mot_de_passe == "Zidpes09"


def test_deux_bases_koxo_tiennent_chacune_leur_secret(session, coffre,
                                                      personne_factory):
    """Un professeur peut avoir un mot de passe différent par serveur."""
    from backend.models import SecretConserve

    p = personne_factory(login="pdupont")
    deposer(session, coffre, personne_id=p.id, mot_de_passe="Aaa111", site="NDK")
    deposer(session, coffre, personne_id=p.id, mot_de_passe="Bbb222", site="SU")
    session.commit()

    assert session.query(SecretConserve).count() == 2
    par_site = {s.site: s.mot_de_passe for s in chercher(session, coffre, "pdupont")}
    assert par_site == {"NDK": "Aaa111", "SU": "Bbb222"}


# ---------------------------------------------------------------------------
# La recherche
# ---------------------------------------------------------------------------


def test_la_recherche_ignore_accents_et_casse(session, coffre, personne_factory):
    p = personne_factory(nom="GUÉGAN", prenom="Maya", login="mguegan")
    deposer(session, coffre, personne_id=p.id, mot_de_passe="Vikuge90")
    session.commit()

    assert chercher(session, coffre, "guegan")
    assert chercher(session, coffre, "GUÉGAN")


def test_une_recherche_vide_ne_deballe_pas_le_coffre(session, coffre,
                                                     personne_factory):
    """Sinon un champ laissé vide afficherait deux mille mots de passe."""
    p = personne_factory(login="mguegan")
    deposer(session, coffre, personne_id=p.id, mot_de_passe="Vikuge90")
    session.commit()

    assert chercher(session, coffre, "") == []
    assert chercher(session, coffre, "   ") == []


def test_la_recherche_porte_sur_lidentite_pas_sur_le_secret(
    session, coffre, personne_factory
):
    """On ne cherche jamais « qui a ce mot de passe »."""
    p = personne_factory(nom="GUEGAN", prenom="Maya", login="mguegan")
    deposer(session, coffre, personne_id=p.id, mot_de_passe="Vikuge90")
    session.commit()

    assert chercher(session, coffre, "Vikuge90") == []


# ---------------------------------------------------------------------------
# Verser un export KoXo
# ---------------------------------------------------------------------------


def _export_koxo(lignes):
    entete = "Groupe primaire;Groupe secondaire;Titre;Nom;Prénom;Identifiant;ID unique;Mot de passe;Date de naissance;Email"
    corps = "\r\n".join(";".join(str(c) for c in l) for l in lignes)
    return (entete + "\r\n" + corps + "\r\n").encode("cp1252")


def test_verser_un_export_range_les_mots_de_passe(session, coffre,
                                                  personne_factory):
    p = personne_factory(nom="GUEGAN", prenom="Maya", login="mguegan")
    contenu = _export_koxo([
        ["Elèves", "6A", "", "GUEGAN", "Maya", "mguegan", 100, "Vikuge90", "", ""],
    ])

    r = verser_export_koxo(session, coffre, contenu, site="NDK")
    session.commit()

    assert r.nb_deposes == 1
    assert chercher(session, coffre, "guegan")[0].mot_de_passe == "Vikuge90"


def test_un_login_inconnu_est_compte_pas_ignore(session, coffre):
    """Le rapport doit dire ce qui n'a pas trouvé preneur."""
    contenu = _export_koxo([
        ["Elèves", "6A", "", "INCONNU", "Jean", "jinconnu", 200, "Zidpes09", "", ""],
    ])

    r = verser_export_koxo(session, coffre, contenu, site="NDK")
    assert r.nb_deposes == 0
    assert r.nb_sans_correspondance == 1


# ---------------------------------------------------------------------------
# Fabriquer un mot de passe pour un site sans KoXo
# ---------------------------------------------------------------------------


def test_le_mot_de_passe_fabrique_a_la_forme_de_koxo(session):
    """`Aaaaaa99` — la forme de 1663 des 1665 mots de passe réels."""
    for _ in range(200):
        m = fabriquer_mot_de_passe()
        assert len(m) == 8, m
        assert m[0].isupper(), m
        assert m[1:6].islower() and m[1:6].isalpha(), m
        assert m[6:].isdigit(), m


def test_deux_mots_de_passe_fabriques_different(session):
    assert len({fabriquer_mot_de_passe() for _ in range(200)}) > 190


# ---------------------------------------------------------------------------
# L'endpoint : la clé ne sort jamais du processus
# ---------------------------------------------------------------------------


@pytest.fixture()
def client(tmp_db_path):
    from fastapi.testclient import TestClient

    from backend.main import app
    from backend.routers.coffre import verrouiller_maintenant

    verrouiller_maintenant()
    with TestClient(app) as c:
        yield c
    verrouiller_maintenant()


def test_letat_dit_ce_que_linterface_a_le_droit_de_savoir(client):
    r = client.get("/api/coffre/etat")
    assert r.status_code == 200, r.text
    corps = r.json()
    assert corps == {
        "initialise": False, "ouvert": False, "expire_dans": 0, "nb_secrets": 0,
    }
    assert "cle" not in corps and "mot_de_passe" not in corps


def test_un_coffre_ferme_refuse_la_recherche(client):
    r = client.get("/api/coffre/chercher", params={"q": "guegan"})
    assert r.status_code == 401
    assert "fermé" in r.json()["detail"]


def test_ouvrir_puis_chercher(client):
    r = client.post("/api/coffre/initialiser", json={"mot_de_passe": MAITRE})
    assert r.status_code == 200, r.text
    assert r.json()["ouvert"] is True

    client.post("/api/coffre/verrouiller")
    assert client.get("/api/coffre/etat").json()["ouvert"] is False

    r = client.post("/api/coffre/ouvrir", json={"mot_de_passe": MAITRE})
    assert r.status_code == 200, r.text
    assert r.json()["ouvert"] is True


def test_un_mauvais_mot_de_passe_ne_rouvre_rien(client):
    client.post("/api/coffre/initialiser", json={"mot_de_passe": MAITRE})
    client.post("/api/coffre/verrouiller")

    r = client.post("/api/coffre/ouvrir", json={"mot_de_passe": "faux"})
    assert r.status_code == 401
    assert client.get("/api/coffre/etat").json()["ouvert"] is False


def test_la_reponse_ne_contient_jamais_la_cle(client):
    """Ce que l'interface sait : ouvert ou fermé. Rien d'autre."""
    r = client.post("/api/coffre/initialiser", json={"mot_de_passe": MAITRE})
    assert MAITRE not in r.text
    assert set(r.json()) == {"initialise", "ouvert", "expire_dans", "nb_secrets"}
