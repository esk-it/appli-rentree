"""Faire entrer quelqu'un en cours d'année.

Tout venait de l'ingestion Charlemagne, qui arrive une fois l'an. Un élève
inscrit un mardi de novembre, une AESH qui prend son poste le jour même,
n'avaient aucune porte d'entrée.
"""
from __future__ import annotations

import csv
import io

import pytest

MAITRE = "sardine-clavier-molybdene-1789"


@pytest.fixture()
def tc_factory(session):
    from backend.models import TableCorrespondance

    def _creer(site_id, code):
        t = TableCorrespondance(
            site_id=site_id, classe_charlemagne_long=f"CLASSE {code}",
            classe_code_court=code,
            ou_pre_rentree="/3. NDK/NDK2027",
            ou_definitive=f"/3. NDK/NDK2027/{code}",
            groupe_google=f"{code.lower()}@lekreisker.fr",
        )
        session.add(t)
        session.commit()
        return t

    return _creer


@pytest.fixture()
def etab(session, site_factory, annee_factory, tc_factory):
    site = site_factory("NDK")
    an = annee_factory("2026-2027")
    tc_factory(site.id, "2_1")
    return site, an


# ---------------------------------------------------------------------------
# La proposition
# ---------------------------------------------------------------------------


def test_l_arrivant_recoit_identifiant_et_adresse_des_regles_ordinaires(
    session, etab
):
    """Une arrivée nommée à part serait une exception à maintenir."""
    from backend.services.arrivees import proposer_arrivee

    site, an = etab
    p = proposer_arrivee(
        session, site_id=site.id, type_personne="eleve", nom="MARTIN",
        prenom="Louise", classe="2_1", annee_id=an.id, id_charlemagne=99001,
    )
    assert p.login_propose == "lmartin"
    assert p.email_propose == "louise.martin@lekreisker.fr"
    assert p.ou_pre_rentree == "/3. NDK/NDK2027"
    assert p.ou_definitive == "/3. NDK/NDK2027/2_1"
    assert p.groupe_google == "2_1@lekreisker.fr"


def test_l_identifiant_deja_pris_est_suffixe(session, etab, personne_factory):
    from backend.services.arrivees import proposer_arrivee

    site, an = etab
    personne_factory(type="eleve", site_id=site.id, id_charlemagne=5001,
                     nom="MARTIN", prenom="Lucas", login="lmartin")
    p = proposer_arrivee(
        session, site_id=site.id, type_personne="eleve", nom="MARTIN",
        prenom="Louise", classe="2_1", annee_id=an.id, id_charlemagne=99002,
    )
    assert p.login_propose != "lmartin"
    assert any("déjà pris" in a for a in p.avertissements)


def test_l_adresse_d_un_homonyme_est_suffixee(session, etab, personne_factory):
    """Google refuse une adresse déjà prise — et parfois le fichier entier."""
    from backend.services.arrivees import proposer_arrivee

    site, an = etab
    personne_factory(type="eleve", site_id=site.id, id_charlemagne=5002,
                     nom="MARTIN", prenom="Louise", login="lmartin",
                     email_constate="louise.martin@lekreisker.fr")
    p = proposer_arrivee(
        session, site_id=site.id, type_personne="eleve", nom="MARTIN",
        prenom="Louise", classe="2_1", annee_id=an.id, id_charlemagne=99003,
    )
    assert p.email_propose == "louise.martin1@lekreisker.fr"
    assert any("déjà portée" in a for a in p.avertissements)


def test_une_classe_hors_table_est_refusee(session, etab):
    """Ni son unité d'organisation ni son groupe ne seraient connus."""
    from backend.services.arrivees import ArriveeImpossible, proposer_arrivee

    site, an = etab
    with pytest.raises(ArriveeImpossible, match="table de correspondance"):
        proposer_arrivee(
            session, site_id=site.id, type_personne="eleve", nom="MARTIN",
            prenom="Louise", classe="9_9", annee_id=an.id, id_charlemagne=99004,
        )


def test_sans_identifiant_charlemagne_le_programme_le_dit(session, etab):
    """KoXo reconnaît par l'ID unique : sans lui, rien ne le reconnaîtra."""
    from backend.services.arrivees import proposer_arrivee

    site, an = etab
    p = proposer_arrivee(
        session, site_id=site.id, type_personne="adulte", nom="LAGADEC",
        prenom="Sophie", annee_id=an.id,
    )
    assert p.badge is None
    assert any("ID unique" in a for a in p.avertissements)


def test_un_homonyme_du_referentiel_est_signale(session, etab, personne_factory):
    """Deux saisies de la même personne se ressemblent beaucoup."""
    from backend.services.arrivees import proposer_arrivee

    site, an = etab
    personne_factory(type="eleve", site_id=site.id, id_charlemagne=5003,
                     nom="MARTIN", prenom="Louise", login="lmartin")
    p = proposer_arrivee(
        session, site_id=site.id, type_personne="eleve", nom="Martin",
        prenom="louise", classe="2_1", annee_id=an.id, id_charlemagne=99005,
    )
    assert any("portent déjà ce nom" in a for a in p.avertissements)


# ---------------------------------------------------------------------------
# L'enregistrement
# ---------------------------------------------------------------------------


def test_l_arrivant_entre_au_referentiel_avec_sa_photographie(session, etab):
    """Le référentiel d'abord : sinon les groupes et la bascule l'ignorent."""
    from backend.models import Personne, Snapshot
    from backend.services.arrivees import enregistrer_arrivee, proposer_arrivee

    site, an = etab
    p = proposer_arrivee(
        session, site_id=site.id, type_personne="eleve", nom="MARTIN",
        prenom="Louise", classe="2_1", annee_id=an.id, id_charlemagne=99006,
    )
    personne = enregistrer_arrivee(
        session, p, site_id=site.id, annee_id=an.id,
        id_charlemagne=99006, mode="reel",
    )
    assert personne.login == "lmartin"
    assert personne.badge == Personne.calculer_badge("eleve", 99006)
    sn = session.query(Snapshot).filter_by(personne_id=personne.id).one()
    assert sn.classe == "2_1"


def test_l_adresse_choisie_est_ecrite_et_ne_se_recalcule_pas(
    session, etab, personne_factory
):
    """Le calcul redonnerait celle de l'homonyme."""
    from backend.services.arrivees import enregistrer_arrivee, proposer_arrivee

    site, an = etab
    personne_factory(type="eleve", site_id=site.id, id_charlemagne=5004,
                     nom="MARTIN", prenom="Louise", login="lmartin",
                     email_constate="louise.martin@lekreisker.fr")
    p = proposer_arrivee(
        session, site_id=site.id, type_personne="eleve", nom="MARTIN",
        prenom="Louise", classe="2_1", annee_id=an.id, id_charlemagne=99007,
    )
    nouvelle = enregistrer_arrivee(
        session, p, site_id=site.id, annee_id=an.id,
        id_charlemagne=99007, mode="reel",
    )
    assert nouvelle.email == "louise.martin1@lekreisker.fr"


def test_la_simulation_n_ecrit_rien(session, etab):
    from backend.models import Personne
    from backend.services.arrivees import enregistrer_arrivee, proposer_arrivee

    site, an = etab
    avant = session.query(Personne).count()
    p = proposer_arrivee(
        session, site_id=site.id, type_personne="eleve", nom="MARTIN",
        prenom="Louise", classe="2_1", annee_id=an.id, id_charlemagne=99008,
    )
    enregistrer_arrivee(session, p, site_id=site.id, annee_id=an.id,
                        id_charlemagne=99008, mode="simulation")
    assert session.query(Personne).count() == avant


def test_une_reinscription_ne_cree_pas_de_doublon(session, etab, personne_factory):
    """Le même identifiant Charlemagne désigne la même personne."""
    from backend.models import Personne
    from backend.services.arrivees import enregistrer_arrivee, proposer_arrivee

    site, an = etab
    deja = personne_factory(type="eleve", site_id=site.id, id_charlemagne=5005,
                            nom="MARTIN", prenom="Louise", login="lmartin")
    avant = session.query(Personne).count()
    p = proposer_arrivee(
        session, site_id=site.id, type_personne="eleve", nom="MARTIN",
        prenom="Louise", classe="2_1", annee_id=an.id, id_charlemagne=5005,
    )
    assert p.personne_existante_id == deja.id
    personne = enregistrer_arrivee(
        session, p, site_id=site.id, annee_id=an.id,
        id_charlemagne=5005, mode="reel",
    )
    assert personne.id == deja.id
    assert session.query(Personne).count() == avant


# ---------------------------------------------------------------------------
# Le compte Google
# ---------------------------------------------------------------------------


def test_le_csv_porte_l_unite_choisie_et_un_mot_de_passe(session, etab):
    """La console range le compte à la création : un déplacement de plus
    serait un aller-retour pour rien."""
    from backend.services.arrivees import (
        enregistrer_arrivee,
        fabriquer_compte_google,
        proposer_arrivee,
    )
    from backend.services.coffre import initialiser

    site, an = etab
    cle = initialiser(session, MAITRE)
    p = proposer_arrivee(
        session, site_id=site.id, type_personne="eleve", nom="MARTIN",
        prenom="Louise", classe="2_1", annee_id=an.id, id_charlemagne=99009,
    )
    personne = enregistrer_arrivee(session, p, site_id=site.id, annee_id=an.id,
                                   id_charlemagne=99009, mode="reel")
    contenu, rapport = fabriquer_compte_google(
        session, cle, personne, ou=p.ou_definitive, mode="reel",
    )
    ligne = list(csv.DictReader(io.StringIO(contenu.decode("utf-8-sig"))))[0]
    assert ligne["Org Unit Path [Required]"] == "/3. NDK/NDK2027/2_1"
    assert ligne["Email Address [Required]"] == "louise.martin@lekreisker.fr"
    assert ligne["Change Password at Next Sign-In"] == "False"
    mdp = ligne["Password [Required]"]
    assert len(mdp) == 8 and mdp[0].isupper() and mdp[6:].isdigit()
    assert rapport.ou_visee == "/3. NDK/NDK2027/2_1"


def test_le_mot_de_passe_est_range_au_coffre(session, etab):
    """Fabriqué et non rangé, il serait perdu — personne d'autre ne le sait."""
    from backend.services.arrivees import (
        enregistrer_arrivee,
        fabriquer_compte_google,
        proposer_arrivee,
    )
    from backend.services.coffre import chercher, initialiser

    site, an = etab
    cle = initialiser(session, MAITRE)
    p = proposer_arrivee(
        session, site_id=site.id, type_personne="eleve", nom="MARTIN",
        prenom="Louise", classe="2_1", annee_id=an.id, id_charlemagne=99010,
    )
    personne = enregistrer_arrivee(session, p, site_id=site.id, annee_id=an.id,
                                   id_charlemagne=99010, mode="reel")
    contenu, _ = fabriquer_compte_google(
        session, cle, personne, ou=p.ou_definitive, mode="reel",
    )
    ligne = list(csv.DictReader(io.StringIO(contenu.decode("utf-8-sig"))))[0]
    trouves = chercher(session, cle, "lmartin")
    assert [t.mot_de_passe for t in trouves] == [ligne["Password [Required]"]]


def test_sans_coffre_ouvert_aucun_compte_n_est_fabrique(session, etab):
    from backend.services.arrivees import (
        ArriveeImpossible,
        enregistrer_arrivee,
        fabriquer_compte_google,
        proposer_arrivee,
    )

    site, an = etab
    p = proposer_arrivee(
        session, site_id=site.id, type_personne="eleve", nom="MARTIN",
        prenom="Louise", classe="2_1", annee_id=an.id, id_charlemagne=99011,
    )
    personne = enregistrer_arrivee(session, p, site_id=site.id, annee_id=an.id,
                                   id_charlemagne=99011, mode="reel")
    with pytest.raises(ArriveeImpossible, match="coffre"):
        fabriquer_compte_google(session, b"", personne, ou=p.ou_definitive)


# ---------------------------------------------------------------------------
# Le groupe
# ---------------------------------------------------------------------------


class ClientFactice:
    def __init__(self, membres=None):
        self.membres = list(membres or [])
        self.ajouts = []

    def lister_membres(self, groupe):
        return list(self.membres)

    def ajouter_membre(self, groupe, adresse):
        self.ajouts.append((groupe, adresse))
        self.membres.append(adresse)


def test_rejoindre_le_groupe_est_un_geste_a_part(session, etab):
    """Entre la fabrication et lui, il y a l'import dans la console."""
    from backend.services.arrivees import (
        ajouter_au_groupe,
        enregistrer_arrivee,
        proposer_arrivee,
    )

    site, an = etab
    p = proposer_arrivee(
        session, site_id=site.id, type_personne="eleve", nom="MARTIN",
        prenom="Louise", classe="2_1", annee_id=an.id, id_charlemagne=99012,
    )
    personne = enregistrer_arrivee(session, p, site_id=site.id, annee_id=an.id,
                                   id_charlemagne=99012, mode="reel")
    client = ClientFactice()
    ajouter_au_groupe(session, personne, client, p.groupe_google)
    assert client.ajouts == [
        ("2_1@lekreisker.fr", "louise.martin@lekreisker.fr")
    ]


def test_un_membre_deja_present_n_est_pas_rajoute(session, etab):
    from backend.services.arrivees import (
        ajouter_au_groupe,
        enregistrer_arrivee,
        proposer_arrivee,
    )

    site, an = etab
    p = proposer_arrivee(
        session, site_id=site.id, type_personne="eleve", nom="MARTIN",
        prenom="Louise", classe="2_1", annee_id=an.id, id_charlemagne=99013,
    )
    personne = enregistrer_arrivee(session, p, site_id=site.id, annee_id=an.id,
                                   id_charlemagne=99013, mode="reel")
    client = ClientFactice(["louise.martin@lekreisker.fr"])
    message = ajouter_au_groupe(session, personne, client, p.groupe_google)
    assert client.ajouts == []
    assert "déjà membre" in message


# ---------------------------------------------------------------------------
# Le tableau des Chromebooks
# ---------------------------------------------------------------------------


def test_une_aesh_ajoutee_au_tableau_attend_une_machine(session, etab):
    """L'écran lit un classeur importé une fois l'an : une arrivée de
    novembre n'y figure pas, et c'est le moment où elle en a besoin."""
    from backend.models import MouvementProf
    from backend.services.arrivees import (
        enregistrer_arrivee,
        inscrire_au_tableau_chromebooks,
        proposer_arrivee,
    )

    site, an = etab
    p = proposer_arrivee(
        session, site_id=site.id, type_personne="adulte", nom="LAGADEC",
        prenom="Sophie", annee_id=an.id, id_charlemagne=700,
    )
    personne = enregistrer_arrivee(session, p, site_id=site.id, annee_id=an.id,
                                   id_charlemagne=700, mode="reel")
    inscrire_au_tableau_chromebooks(
        session, personne, annee_id=an.id, discipline="AESH", mode="reel",
    )
    ligne = session.query(MouvementProf).filter_by(nom="LAGADEC").one()
    assert ligne.code == "arrivant"
    assert ligne.discipline == "AESH"


def test_un_eleve_n_entre_pas_au_tableau_des_chromebooks(session, etab):
    from backend.services.arrivees import (
        ArriveeImpossible,
        enregistrer_arrivee,
        inscrire_au_tableau_chromebooks,
        proposer_arrivee,
    )

    site, an = etab
    p = proposer_arrivee(
        session, site_id=site.id, type_personne="eleve", nom="MARTIN",
        prenom="Louise", classe="2_1", annee_id=an.id, id_charlemagne=99014,
    )
    personne = enregistrer_arrivee(session, p, site_id=site.id, annee_id=an.id,
                                   id_charlemagne=99014, mode="reel")
    with pytest.raises(ArriveeImpossible, match="adultes"):
        inscrire_au_tableau_chromebooks(session, personne, annee_id=an.id)


def test_inscrire_deux_fois_ne_duplique_pas(session, etab):
    from backend.models import MouvementProf
    from backend.services.arrivees import (
        enregistrer_arrivee,
        inscrire_au_tableau_chromebooks,
        proposer_arrivee,
    )

    site, an = etab
    p = proposer_arrivee(
        session, site_id=site.id, type_personne="adulte", nom="LAGADEC",
        prenom="Sophie", annee_id=an.id, id_charlemagne=701,
    )
    personne = enregistrer_arrivee(session, p, site_id=site.id, annee_id=an.id,
                                   id_charlemagne=701, mode="reel")
    for _ in range(2):
        inscrire_au_tableau_chromebooks(session, personne, annee_id=an.id,
                                        discipline="AESH", mode="reel")
    assert session.query(MouvementProf).filter_by(nom="LAGADEC").count() == 1


def test_deux_classes_sans_lettre_ne_se_confondent_pas(
    session, etab, tc_factory
):
    """`normaliser_nom` ne garde que les lettres : `2_1` et `9_9` s'y
    réduisent tous deux au vide, et n'importe quelle classe répondait à
    n'importe quelle autre."""
    from backend.services.arrivees import proposer_arrivee

    site, an = etab
    tc_factory(site.id, "6_3")
    p = proposer_arrivee(
        session, site_id=site.id, type_personne="eleve", nom="MARTIN",
        prenom="Louise", classe="6_3", annee_id=an.id, id_charlemagne=99020,
    )
    assert p.ou_definitive == "/3. NDK/NDK2027/6_3"
    assert p.groupe_google == "6_3@lekreisker.fr"


def test_la_classe_courante_est_ecrite_aussi_sur_la_personne(session, etab):
    """`Personne.classe` est ce que lisent les écrans et les recherches.

    L'écran Mouvements affichait « sans classe » un élève qu'on venait de
    placer en terminale : la photographie de l'année portait bien la
    classe, la personne non. L'ingestion et le changement de classe
    écrivent les deux.
    """
    from backend.services.arrivees import enregistrer_arrivee, proposer_arrivee

    site, an = etab
    p = proposer_arrivee(
        session, site_id=site.id, type_personne="eleve", nom="ISSARTIAL",
        prenom="Clement", classe="2_1", annee_id=an.id, id_charlemagne=99800,
    )
    personne = enregistrer_arrivee(
        session, p, site_id=site.id, annee_id=an.id,
        id_charlemagne=99800, mode="reel",
    )
    session.refresh(personne)
    assert personne.classe == "2_1"


def test_une_reinscription_met_aussi_a_jour_la_classe_courante(
    session, etab, personne_factory
):
    from backend.services.arrivees import enregistrer_arrivee, proposer_arrivee

    site, an = etab
    deja = personne_factory(
        type="eleve", site_id=site.id, id_charlemagne=5900,
        nom="ISSARTIAL", prenom="Clement", login="cissartial",
    )
    p = proposer_arrivee(
        session, site_id=site.id, type_personne="eleve", nom="ISSARTIAL",
        prenom="Clement", classe="2_1", annee_id=an.id, id_charlemagne=5900,
    )
    enregistrer_arrivee(session, p, site_id=site.id, annee_id=an.id,
                        id_charlemagne=5900, mode="reel")
    session.refresh(deja)
    assert deja.classe == "2_1"


def test_un_adulte_n_a_pas_de_classe_courante(session, etab):
    from backend.services.arrivees import enregistrer_arrivee, proposer_arrivee

    site, an = etab
    p = proposer_arrivee(
        session, site_id=site.id, type_personne="adulte", nom="LAGADEC",
        prenom="Sophie", annee_id=an.id, id_charlemagne=705,
    )
    personne = enregistrer_arrivee(session, p, site_id=site.id, annee_id=an.id,
                                   id_charlemagne=705, mode="reel")
    session.refresh(personne)
    assert personne.classe is None
