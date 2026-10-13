"""Le coffre ne garde que des relevés datés.

Vécu le 13 octobre 2026 : un professeur signale que le mot de passe d'Eléanor
BRETON ne marche pas. Le coffre avait relu KoXo NDK le 31 août ; le
15 septembre, les 140 montants de SU y avaient retrouvé leur mot de passe du
collège. Charlemagne, relu le 12 octobre, portait le bon. Le coffre préférait
KoXo sans regarder la date — et l'étiquette a porté un mot de passe qui
n'existait plus nulle part.
"""
from __future__ import annotations

import base64
from datetime import datetime

import pytest

AOUT = datetime(2026, 8, 31, 11, 27)
OCTOBRE = datetime(2026, 10, 12, 9, 6)


@pytest.fixture()
def ecole(session, site_factory, annee_factory, personne_factory):
    from backend.models import Snapshot

    ndk = site_factory("NDK")
    ndk.base_koxo = "NDK"
    su = site_factory("SU")
    su.base_koxo = "SU"
    an = annee_factory("2026-2027")
    session.commit()

    def eleve(nom, prenom, site, classe, **kw):
        p = personne_factory(type="eleve", nom=nom, prenom=prenom, site_id=site.id,
                             classe=classe, **kw)
        session.add(Snapshot(personne_id=p.id, annee_scolaire_id=an.id, nom=nom,
                             prenom=prenom, classe=classe, date_ingestion=OCTOBRE))
        session.commit()
        return p

    return {"ndk": ndk, "su": su, "an": an, "eleve": eleve}


@pytest.fixture()
def cle(session):
    from backend.services.coffre import initialiser

    return initialiser(session, "maitre-essai-longue-phrase")


def _deposer(session, cle, p, mdp, *, cible, site=None, quand=None, identifiant=None):
    from backend.services.coffre import deposer

    s = deposer(session, cle, personne_id=p.id, mot_de_passe=mdp, cible=cible, site=site,
                origine="genere" if cible == "google" else cible, identifiant=identifiant)
    if quand is not None:
        s.date_maj = quand
    session.commit()
    return s


def _export_koxo(*lignes):
    entetes = ["Groupe primaire", "Groupe secondaire", "Nom", "Prénom",
               "Identifiant", "ID unique", "Mot de passe", "Email"]
    texte = ";".join(entetes) + "\r\n" + "".join(
        ";".join(["Eleves", classe, p.nom, p.prenom, p.login, str(p.badge), mdp, ""]) + "\r\n"
        for p, classe, mdp in lignes
    )
    return texte.encode("cp1252")


# ---------------------------------------------------------------------------
# Lequel imprimer
# ---------------------------------------------------------------------------


def test_koxo_passe_devant_mais_un_releve_plus_recent_qui_le_contredit_l_arrete(
    session, ecole, cle
):
    """KoXo est LE mot de passe (Johann, 13 octobre 2026). Mais son relevé du
    31 août, contredit par Charlemagne lu le 12 octobre, n'est plus sûr."""
    from backend.models import SecretConserve
    from backend.services.coffre import releve_contredit, secrets_a_remettre

    eleanor = ecole["eleve"]("BRETON", "Eléanor", ecole["ndk"], "2_BPMRC2")
    _deposer(session, cle, eleanor, "Ancien11", cible="koxo", site="NDK", quand=AOUT)
    _deposer(session, cle, eleanor, "Collège2", cible="charlemagne", quand=OCTOBRE)

    siens = session.query(SecretConserve).filter_by(personne_id=eleanor.id).all()
    recevables = secrets_a_remettre(siens, ecole["ndk"])
    assert [s.cible for s in recevables] == ["koxo", "charlemagne"]
    assert releve_contredit(recevables, cle).cible == "charlemagne"


def test_koxo_relu_le_meme_jour_ou_apres_fait_foi(session, ecole, cle):
    """Un écart dit alors une faute de copie dans Charlemagne : c'est lui
    qu'on corrige."""
    from backend.models import SecretConserve
    from backend.services.coffre import lire_secret, releve_contredit, secrets_a_remettre

    lea = ecole["eleve"]("ROUE", "Léa", ecole["ndk"], "2_1")
    _deposer(session, cle, lea, "Copie111", cible="charlemagne", quand=datetime(2026, 10, 12, 8))
    _deposer(session, cle, lea, "Koxo2222", cible="koxo", site="NDK", quand=datetime(2026, 10, 12, 7))
    recevables = secrets_a_remettre(
        session.query(SecretConserve).filter_by(personne_id=lea.id).all(), ecole["ndk"]
    )
    assert lire_secret(cle, recevables[0]) == "Koxo2222"
    assert releve_contredit(recevables, cle) is None


def test_l_etiquette_d_eleanor_ne_sort_pas_tant_que_koxo_n_est_pas_relu(session, ecole, cle):
    from backend.services.listes_depuis_koxo import listes_depuis_le_coffre

    eleanor = ecole["eleve"]("BRETON", "Eléanor", ecole["ndk"], "2_BPMRC2")
    _deposer(session, cle, eleanor, "Ancien11", cible="koxo", site="NDK", quand=AOUT)
    _deposer(session, cle, eleanor, "Collège2", cible="charlemagne", quand=OCTOBRE,
             identifiant="ebreton")
    tom = ecole["eleve"]("BIHAN", "Tom", ecole["ndk"], "2_1")
    _deposer(session, cle, tom, "Pareil22", cible="koxo", site="NDK", quand=AOUT)

    r = listes_depuis_le_coffre(session, cle, site_id=ecole["ndk"].id,
                                annee_cible_id=ecole["an"].id)
    page = r.etiquettes_tous.decode("utf-8")
    assert "BIHAN" in page and "BRETON" not in page
    assert r.absents_de_la_source == [], "elle a deux mots de passe, pas aucun"
    (a,) = r.avertissements
    assert "Eléanor BRETON (KoXo NDK lu le 31/08 ≠ Charlemagne lu le 12/10)" in a
    assert "relevé KoXo est contredit" in a
    assert "Ancien11" not in a and "Collège2" not in a


def test_seule_eleanor_retenue_le_refus_dit_de_relire_koxo(session, ecole, cle):
    from backend.services.listes_depuis_koxo import ListesImpossibles, listes_depuis_le_coffre

    eleanor = ecole["eleve"]("BRETON", "Eléanor", ecole["ndk"], "2_BPMRC2")
    _deposer(session, cle, eleanor, "Ancien11", cible="koxo", site="NDK", quand=AOUT)
    _deposer(session, cle, eleanor, "Collège2", cible="charlemagne", quand=OCTOBRE)
    with pytest.raises(ListesImpossibles, match="relevé KoXo est contredit"):
        listes_depuis_le_coffre(session, cle, site_id=ecole["ndk"].id,
                                annee_cible_id=ecole["an"].id, personne_ids=[eleanor.id])


# ---------------------------------------------------------------------------
# Relire KoXo
# ---------------------------------------------------------------------------


def test_reverser_koxo_dit_qui_a_change_depuis_le_releve_precedent(session, ecole, cle):
    from backend.services.coffre import verser_export_koxo

    eleanor = ecole["eleve"]("BRETON", "Eléanor", ecole["ndk"], "2_BPMRC2")
    tom = ecole["eleve"]("BIHAN", "Tom", ecole["ndk"], "2_1")
    verser_export_koxo(session, cle, _export_koxo((eleanor, "2_BPMRC2", "Ancien11"),
                                                  (tom, "2_1", "Pareil22")), site="NDK")
    session.commit()

    r = verser_export_koxo(session, cle, _export_koxo((eleanor, "2_BPMRC2", "Collège2"),
                                                      (tom, "2_1", "Pareil22")), site="NDK")
    assert r.changes == ["Eléanor BRETON"]
    assert "dont 1 changé(s) depuis le relevé du" in r.resume
    assert "Collège2" not in r.resume


def test_un_export_sans_mot_de_passe_ne_vide_pas_le_coffre(session, ecole, cle):
    """Pris sans cocher « inclure les mots de passe », il ne dit rien du
    coffre : il le vidait."""
    from backend.models import SecretConserve
    from backend.services.coffre import verser_export_koxo

    eleanor = ecole["eleve"]("BRETON", "Eléanor", ecole["ndk"], "2_BPMRC2")
    _deposer(session, cle, eleanor, "Collège2", cible="koxo", site="NDK")
    r = verser_export_koxo(session, cle, _export_koxo((eleanor, "2_BPMRC2", "")), site="NDK")
    session.commit()
    assert r.nb_retires == 0
    assert session.query(SecretConserve).filter_by(cible="koxo").count() == 1


def test_relire_sans_remplacer_ne_retire_personne(session, ecole, cle):
    """Un export déposé ailleurs que dans le Coffre peut ne pas couvrir toute
    la base — les seuls élèves, sans les professeurs."""
    from backend.models import SecretConserve
    from backend.services.coffre import verser_export_koxo

    eleanor = ecole["eleve"]("BRETON", "Eléanor", ecole["ndk"], "2_BPMRC2")
    tom = ecole["eleve"]("BIHAN", "Tom", ecole["ndk"], "2_1")
    _deposer(session, cle, tom, "Pareil22", cible="koxo", site="NDK")
    verser_export_koxo(session, cle, _export_koxo((eleanor, "2_BPMRC2", "Collège2")),
                       site="NDK", remplacer=False)
    session.commit()
    assert session.query(SecretConserve).filter_by(cible="koxo").count() == 2


# ---------------------------------------------------------------------------
# Les écarts, sans les mots de passe
# ---------------------------------------------------------------------------


def test_les_ecarts_nomment_qui_et_quand_jamais_quoi(session, ecole, cle):
    from dataclasses import asdict

    from backend.services.coffre import ecarts

    eleanor = ecole["eleve"]("BRETON", "Eléanor", ecole["ndk"], "2_BPMRC2")
    _deposer(session, cle, eleanor, "Ancien11", cible="koxo", site="NDK", quand=AOUT)
    _deposer(session, cle, eleanor, "Collège2", cible="charlemagne", quand=OCTOBRE)
    accord = ecole["eleve"]("BIHAN", "Tom", ecole["ndk"], "2_1")
    _deposer(session, cle, accord, "Pareil22", cible="koxo", site="NDK", quand=AOUT)
    _deposer(session, cle, accord, "Pareil22", cible="charlemagne", quand=OCTOBRE)
    # Un élève de SU qui suit la DAO a un autre compte sur le serveur de NDK :
    # un autre mot de passe, et pas un écart.
    dao = ecole["eleve"]("CAZUC", "Axel", ecole["su"], "31")
    _deposer(session, cle, dao, "Dao33333", cible="koxo", site="NDK")
    _deposer(session, cle, dao, "Su444444", cible="koxo", site="SU")
    _deposer(session, cle, dao, "Su444444", cible="charlemagne")

    (e,) = ecarts(session, cle)
    assert (e.personne_id, e.a_relire) == (eleanor.id, True)
    assert [(s.cible, s.retenu) for s in e.sources] == [("koxo", True), ("charlemagne", False)]
    assert "Ancien11" not in str(asdict(e)) and "Collège2" not in str(asdict(e))


def test_la_recherche_dit_que_koxo_est_a_relire(session, ecole, cle):
    from backend.services.coffre import chercher

    eleanor = ecole["eleve"]("BRETON", "Eléanor", ecole["ndk"], "2_BPMRC2")
    _deposer(session, cle, eleanor, "Ancien11", cible="koxo", site="NDK", quand=AOUT)
    _deposer(session, cle, eleanor, "Collège2", cible="charlemagne", quand=OCTOBRE)
    trouves = chercher(session, cle, "breton")
    assert [(s.cible, s.retenu, s.ecart, s.a_relire, str(s.releve_le)) for s in trouves] == [
        ("koxo", True, True, True, "2026-08-31"), ("charlemagne", False, True, True, "2026-10-12"),
    ]


# ---------------------------------------------------------------------------
# La Cohérence relit KoXo au passage
# ---------------------------------------------------------------------------


def test_la_coherence_tient_le_coffre_a_jour(session, ecole, cle, tmp_db_path):
    import importlib

    from fastapi.testclient import TestClient

    from backend.main import app
    from backend.models import SecretConserve
    from backend.services.coffre import lire_secret

    eleanor = ecole["eleve"]("BRETON", "Eléanor", ecole["ndk"], "2_BPMRC2")
    _deposer(session, cle, eleanor, "Ancien11", cible="koxo", site="NDK", quand=AOUT)
    routeur = importlib.import_module("backend.routers.coffre")
    charlemagne = (f"﻿Num Badge;Nom;Prénom;Code classe\r\n"
                   f"{eleanor.badge};BRETON;Eléanor;2_BPMRC2\r\n").encode("utf-8")
    corps = {
        "fichier_base64": base64.b64encode(charlemagne).decode(),
        "annee_id": ecole["an"].id, "interroger_google": False,
        "koxo_base64": [base64.b64encode(_export_koxo((eleanor, "2_BPMRC2", "Collège2"))).decode()],
    }

    with TestClient(app) as client:
        client.post("/api/coffre/verrouiller")
        ferme = client.post("/api/concordance", json=corps).json()
        assert ferme["mots_de_passe"] == ["Coffre fermé : les mots de passe de KoXo n'ont pas été relus."]

        routeur._ouvrir_en_memoire(cle)
        try:
            r = client.post("/api/concordance", json=corps)
        finally:
            client.post("/api/coffre/verrouiller")
    assert r.status_code == 200, r.text
    (ligne,) = r.json()["mots_de_passe"]
    assert "KoXo NDK : 1 mot(s) de passe relus au coffre, dont 1 changé(s)" in ligne
    assert "Eléanor BRETON" in ligne and "Collège2" not in ligne
    session.expire_all()
    (s,) = session.query(SecretConserve).filter_by(personne_id=eleanor.id, cible="koxo").all()
    assert lire_secret(cle, s) == "Collège2"


# ---------------------------------------------------------------------------
# KoXo ↔ Charlemagne, dans la Cohérence
# ---------------------------------------------------------------------------


def test_la_coherence_compare_koxo_et_charlemagne_et_fabrique_la_correction(
    session, ecole, tmp_db_path
):
    """KoXo est LE mot de passe ; Charlemagne en garde une copie. Le fichier
    recopie KoXo dans « ID/MDP Réseau Péda » pour ceux qui diffèrent."""
    from fastapi.testclient import TestClient

    from backend.main import app

    eleanor = ecole["eleve"]("BRETON", "Eléanor", ecole["ndk"], "2_BPMRC2", login="ebreton")
    tom = ecole["eleve"]("BIHAN", "Tom", ecole["ndk"], "2_1", login="tbihan")
    charlemagne = (
        "\ufeffNum Badge;Nom;Prénom;Code classe;ID Réseau Péda;MDP Réseau Péda\r\n"
        f"{eleanor.badge};BRETON;Eléanor;2_BPMRC2;ebreton;Ancien11\r\n"
        f"{tom.badge};BIHAN;Tom;2_1;tbihan;Pareil22\r\n"
    ).encode("utf-8")
    koxo = _export_koxo((eleanor, "2_BPMRC2", "Collège2"), (tom, "2_1", "Pareil22"))

    with TestClient(app) as client:
        client.post("/api/coffre/verrouiller")
        r = client.post("/api/concordance", json={
            "fichier_base64": base64.b64encode(charlemagne).decode(),
            "annee_id": ecole["an"].id, "interroger_google": False,
            "koxo_base64": [base64.b64encode(koxo).decode()],
        })
    assert r.status_code == 200, r.text
    corps = r.json()
    assert corps["mots_de_passe_verifies"] == 2
    assert [(e["nom"], e["quoi"]) for e in corps["ecarts_mots_de_passe"]] == [
        ("BRETON", ["mot de passe différent"]),
    ]
    sans_fichier = {k: v for k, v in corps.items() if k != "corrections_base64"}
    assert "Collège2" not in str(sans_fichier) and "Ancien11" not in str(sans_fichier)

    fichier = base64.b64decode(corps["corrections_base64"])
    assert fichier == (
        f"Identifiant;ID Réseau Péda;MDP Réseau Péda\r\n{eleanor.id_charlemagne};ebreton;Collège2\r\n"
    ).encode("cp1252")
    assert corps["nom_fichier_corrections"] == "Charlemagne_ReseauPeda_depuis_KoXo_2026-2027.csv"


def test_un_export_koxo_sans_mots_de_passe_le_dit(session, ecole, tmp_db_path):
    from fastapi.testclient import TestClient

    from backend.main import app

    tom = ecole["eleve"]("BIHAN", "Tom", ecole["ndk"], "2_1", login="tbihan")
    charlemagne = (
        "\ufeffNum Badge;Nom;Prénom;Code classe;ID Réseau Péda;MDP Réseau Péda\r\n"
        f"{tom.badge};BIHAN;Tom;2_1;tbihan;Pareil22\r\n"
    ).encode("utf-8")
    with TestClient(app) as client:
        r = client.post("/api/concordance", json={
            "fichier_base64": base64.b64encode(charlemagne).decode(),
            "annee_id": ecole["an"].id, "interroger_google": False,
            "koxo_base64": [base64.b64encode(_export_koxo((tom, "2_1", ""))).decode()],
        }).json()
    assert "ne portent pas les mots de passe" in r["mots_de_passe_non_controles"]
    assert r["corrections_base64"] == ""
