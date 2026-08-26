"""Contrôle d'un export KoXo avant la synchronisation annuelle.

La synchronisation reconnaît un compte par son ID unique. Tout ce qui
empêche cette reconnaissance — champ vide, valeur qui n'est pas un
numéro, même valeur sur deux comptes — devient un compte recréé sous un
autre login, ou supprimé si la synchronisation est destructive.
"""
from __future__ import annotations

import io

import pytest


def _export(tmp_path, lignes, *, sep=";", encodage="cp1252", entetes=None, nom="k.csv"):
    """Écrit un export de la même forme que celui de l'établissement."""
    entetes = entetes or [
        "Groupe primaire", "Groupe secondaire", "Nom", "Prénom",
        "Identifiant", "ID unique", "Mot de passe", "Email",
    ]
    chemin = tmp_path / nom
    with io.open(chemin, "w", encoding=encodage, newline="") as f:
        f.write(sep.join(entetes) + "\r\n")
        for l in lignes:
            f.write(sep.join(str(c) for c in l) + "\r\n")
    return chemin


def _prof(nom, prenom, login, badge):
    return ["Professeurs", "MATHS", nom, prenom, login, badge, "Xxxxxx11",
            f"{prenom.lower()}.{nom.lower()}@lekreisker.fr"]


@pytest.fixture
def peupler(session):
    """Crée des Personnes et renvoie de quoi les retrouver."""
    from backend.models import Personne

    def _faire(gens):
        objets = []
        for type_, nom, prenom, login, badge in gens:
            p = Personne(
                type=type_, nom=nom, prenom=prenom, login=login, badge=badge,
                id_charlemagne=badge,
            )
            session.add(p)
            objets.append(p)
        session.commit()
        return objets

    return _faire


def test_un_export_conforme_ne_signale_rien(session, tmp_path, peupler):
    from backend.services.controle_koxo import controler_export_koxo

    peupler([("adulte", "BOTHOREL", "Tony", "tbothorel", 651)])
    f = _export(tmp_path, [_prof("BOTHOREL", "Tony", "tbothorel", 651)])

    r = controler_export_koxo(session, f, type_personne="adulte")
    assert r.nb_lignes == 1
    assert r.nb_concordants == 1
    assert r.est_sain


def test_un_id_unique_non_numerique_est_signale(session, tmp_path, peupler):
    """Cas réel : KoXo stockait « vdurand » là où le badge est 6."""
    from backend.services.controle_koxo import controler_export_koxo

    peupler([("adulte", "DURAND", "Veronique", "vdurand", 6)])
    f = _export(tmp_path, [_prof("DURAND", "Veronique", "vdurand", "vdurand")])

    r = controler_export_koxo(session, f, type_personne="adulte")
    ecart = [e for e in r.ecarts if e.genre == "id_non_numerique"]
    assert len(ecart) == 1
    assert ecart[0].id_unique == "vdurand"
    assert ecart[0].badge_referentiel == "6", "le badge attendu est nommé"
    assert not r.est_sain


def test_deux_comptes_pour_un_meme_id_unique(session, tmp_path, peupler):
    """Cas réel : Camille GUIVARCH tenait deux comptes sur l'ID 453."""
    from backend.services.controle_koxo import controler_export_koxo

    peupler([("adulte", "GUIVARCH", "Camille", "cguivarch", 453)])
    f = _export(tmp_path, [
        _prof("GUIVARCH", "Camille", "cguivarch", 453),
        _prof("GUIVARCH", "Camille", "cguivarch1", 453),
    ])

    r = controler_export_koxo(session, f, type_personne="adulte")
    doubles = [e for e in r.ecarts if e.genre == "id_en_double"]
    assert len(doubles) == 1
    assert doubles[0].id_unique == "453"
    assert doubles[0].lignes == [2, 3]


def test_un_rapprochement_ambigu_est_signale_sans_etre_resolu(
    session, tmp_path, peupler
):
    """Le défaut que ce contrôle existe pour ne plus commettre.

    Une première version, écrite à la main, rapprochait par login seul
    puis comparait les badges — et rapprochait la professeure
    `cguivarch1` de l'élève `cguivarch1`, annonçant un écart de badge qui
    n'existait pas. Le défaut n'était pas dans les données : il était
    dans le rapprochement silencieux.
    """
    from backend.services.controle_koxo import controler_export_koxo

    peupler([
        ("adulte", "GUIVARCH", "Camille", "cguivarch", 453),
        ("eleve", "GUIVARCH", "Corentin", "cguivarch1", 93520),
    ])
    # La ligne KoXo porte le badge de Camille et le login de Corentin.
    f = _export(tmp_path, [_prof("GUIVARCH", "Camille", "cguivarch1", 453)])

    r = controler_export_koxo(session, f, type_personne="adulte")
    ambigus = [e for e in r.ecarts if e.genre == "rapprochement_ambigu"]
    assert len(ambigus) == 1
    assert "Camille" in ambigus[0].explication
    assert "Corentin" in ambigus[0].explication
    assert not [e for e in r.ecarts if e.genre == "login_divergent"], (
        "un cas ambigu n'est pas requalifié en simple divergence"
    )


def test_un_login_divergent_est_signale(session, tmp_path, peupler):
    from backend.services.controle_koxo import controler_export_koxo

    peupler([("adulte", "MARTIN", "Paul", "pmartin", 100)])
    f = _export(tmp_path, [_prof("MARTIN", "Paul", "pmartin2", 100)])

    r = controler_export_koxo(session, f, type_personne="adulte")
    div = [e for e in r.ecarts if e.genre == "login_divergent"]
    assert len(div) == 1
    assert div[0].login == "pmartin2"
    assert div[0].login_referentiel == "pmartin"


def test_un_badge_inconnu_du_referentiel_est_signale(session, tmp_path, peupler):
    from backend.services.controle_koxo import controler_export_koxo

    peupler([("adulte", "MARTIN", "Paul", "pmartin", 100)])
    f = _export(tmp_path, [_prof("FANTOME", "Jean", "jfantome", 999)])

    r = controler_export_koxo(session, f, type_personne="adulte")
    inconnus = [e for e in r.ecarts if e.genre == "badge_inconnu"]
    assert len(inconnus) == 1
    assert "destructif" in inconnus[0].consequence


def test_une_personne_absente_de_koxo_est_annoncee_comme_creation(
    session, tmp_path, peupler
):
    """Ce n'est pas un défaut : c'est le déroulement normal d'une rentrée."""
    from backend.services.controle_koxo import controler_export_koxo

    peupler([
        ("adulte", "MARTIN", "Paul", "pmartin", 100),
        ("adulte", "NOUVELLE", "Zoe", "znouvelle", 101),
    ])
    f = _export(tmp_path, [_prof("MARTIN", "Paul", "pmartin", 100)])

    r = controler_export_koxo(session, f, type_personne="adulte")
    creations = [e for e in r.ecarts if e.genre == "absent_de_koxo"]
    assert [e.qui for e in creations] == ["Zoe NOUVELLE"]
    assert r.est_sain, "une création à venir ne rend pas l'export malsain"


def test_les_eleves_ne_sont_pas_compares_a_un_export_dadultes(
    session, tmp_path, peupler
):
    from backend.services.controle_koxo import controler_export_koxo

    peupler([
        ("adulte", "MARTIN", "Paul", "pmartin", 100),
        ("eleve", "ELEVE", "Tim", "televe", 20100),
    ])
    f = _export(tmp_path, [_prof("MARTIN", "Paul", "pmartin", 100)])

    r = controler_export_koxo(session, f, type_personne="adulte")
    assert not [e for e in r.ecarts if e.genre == "absent_de_koxo"]


def test_labsence_de_date_de_naissance_est_dite(session, tmp_path, peupler):
    from backend.services.controle_koxo import controler_export_koxo

    peupler([("adulte", "MARTIN", "Paul", "pmartin", 100)])
    f = _export(tmp_path, [_prof("MARTIN", "Paul", "pmartin", 100)])

    r = controler_export_koxo(session, f, type_personne="adulte")
    assert r.date_naissance_renseignee == 0
    assert any("date de naissance" in a for a in r.avertissements)


def test_le_mot_de_passe_est_signale_mais_jamais_lu(session, tmp_path, peupler):
    from backend.services.controle_koxo import controler_export_koxo, lire_export_brut

    peupler([("adulte", "MARTIN", "Paul", "pmartin", 100)])
    f = _export(tmp_path, [_prof("MARTIN", "Paul", "pmartin", 100)])

    lignes, colonnes, _, _, mdp = lire_export_brut(f)
    assert mdp is True
    assert "_motdepasse" not in colonnes
    assert not any("Xxxxxx11" in str(vars(l).values()) for l in lignes)

    r = controler_export_koxo(session, f, type_personne="adulte")
    assert r.contient_mots_de_passe
    assert any("mots de passe" in a for a in r.avertissements)


@pytest.mark.parametrize("sep", [";", ",", "\t"])
def test_les_separateurs_usuels_sont_reconnus(session, tmp_path, peupler, sep):
    from backend.services.controle_koxo import controler_export_koxo

    peupler([("adulte", "MARTIN", "Paul", "pmartin", 100)])
    f = _export(tmp_path, [_prof("MARTIN", "Paul", "pmartin", 100)], sep=sep,
                nom=f"k{ord(sep)}.csv")

    r = controler_export_koxo(session, f, type_personne="adulte")
    assert r.separateur == sep
    assert r.nb_concordants == 1


@pytest.mark.parametrize("encodage", ["cp1252", "utf-8"])
def test_les_deux_encodages_sont_reconnus(session, tmp_path, peupler, encodage):
    from backend.services.controle_koxo import controler_export_koxo

    peupler([("adulte", "LEGOFF", "Hélène", "hlegoff", 100)])
    f = _export(tmp_path, [_prof("LEGOFF", "Hélène", "hlegoff", 100)],
                encodage=encodage, nom=f"k_{encodage}.csv")

    r = controler_export_koxo(session, f, type_personne="adulte")
    assert r.nb_concordants == 1


def test_un_fichier_qui_nest_pas_un_export_koxo_est_refuse(session, tmp_path):
    from backend.services.controle_koxo import controler_export_koxo

    f = tmp_path / "autre.csv"
    f.write_text("colonne1;colonne2\na;b\n", encoding="utf-8")
    with pytest.raises(ValueError, match="Format non reconnu"):
        controler_export_koxo(session, f, type_personne="adulte")


def test_un_fichier_vide_est_refuse(session, tmp_path):
    from backend.services.controle_koxo import controler_export_koxo

    f = tmp_path / "vide.csv"
    f.write_text("", encoding="utf-8")
    with pytest.raises(ValueError, match="vide"):
        controler_export_koxo(session, f, type_personne="adulte")


def test_le_controle_nécrit_rien(session, tmp_path, peupler):
    """Il lit un export et raconte. Corriger reste un geste humain."""
    from backend.models import Personne
    from backend.services.controle_koxo import controler_export_koxo

    peupler([("adulte", "DURAND", "Veronique", "vdurand", 6)])
    f = _export(tmp_path, [_prof("DURAND", "Veronique", "vdurand", "vdurand")])

    controler_export_koxo(session, f, type_personne="adulte")
    p = session.query(Personne).filter_by(login="vdurand").one()
    assert p.badge == 6, "le référentiel n'est pas aligné sur KoXo en douce"


def test_lannee_borne_la_population_comparee(session, tmp_path, peupler, annee_factory):
    """Sans cela, les sortants des années passées seraient dits « absents »."""
    from backend.models import Snapshot
    from backend.services.controle_koxo import controler_export_koxo

    annee = annee_factory("2026-2027")
    gens = peupler([
        ("adulte", "PRESENT", "Anne", "apresent", 100),
        ("adulte", "PARTI", "Jean", "jparti", 101),
    ])
    session.add(Snapshot(
        personne_id=gens[0].id, annee_scolaire_id=annee.id,
        nom="PRESENT", prenom="Anne",
    ))
    session.commit()

    f = _export(tmp_path, [_prof("AUTRE", "Bob", "bautre", 999)])
    r = controler_export_koxo(
        session, f, type_personne="adulte", annee_id=annee.id
    )
    assert [e.qui for e in r.ecarts if e.genre == "absent_de_koxo"] == ["Anne PRESENT"]


def test_une_population_vide_le_dit_au_lieu_dafficher_zero(
    session, tmp_path, peupler, annee_factory
):
    """« 0 compte à créer » se lit « rien ne manque », pas « je n'ai rien comparé ».

    Les adultes n'ont pas de photographie annuelle : borner par année vide
    leur population, et le contrôle devient muet dans ce sens sans le dire.
    """
    from backend.services.controle_koxo import controler_export_koxo

    annee = annee_factory("2026-2027")
    peupler([("adulte", "MARTIN", "Paul", "pmartin", 100)])
    f = _export(tmp_path, [_prof("MARTIN", "Paul", "pmartin", 100)])

    r = controler_export_koxo(
        session, f, type_personne="adulte", annee_id=annee.id
    )
    assert not [e for e in r.ecarts if e.genre == "absent_de_koxo"]
    assert any("rien ne peut être dit" in a for a in r.avertissements)
    assert r.nb_concordants == 1, "l'autre moitié du contrôle fonctionne"


def test_le_badge_propose_vient_du_nom_jamais_du_login(session, tmp_path, peupler):
    """Cas réel Lana LE SAOUT, et le plus coûteux du lot.

    Son ID unique était cassé, donc l'amorçage ne l'avait pas reconnue et
    le programme avait donné son identifiant `llesaout` à une homonyme
    entrante. Proposer le badge de la personne portant ce login — 97820,
    celui de Léna — aurait fait répondre le compte de Lana au nom d'une
    autre. C'est l'identité qui rapproche, pas l'identifiant.
    """
    from backend.services.controle_koxo import controler_export_koxo

    peupler([
        ("eleve", "LE SAOUT", "Lana", "llesaout2", 81010),
        ("eleve", "LE SAOUT", "Lena", "llesaout", 97820),
    ])
    f = _export(tmp_path, [
        ["Elèves", "T_G3B", "", "LE SAOUT", "Lana", "llesaout", "llesaout2",
         "Xxxxxx11", "lana.lesaout@lekreisker.fr"],
    ], entetes=[
        "Groupe primaire", "Groupe secondaire", "Titre", "Nom", "Prénom",
        "Identifiant", "ID unique", "Mot de passe", "Email",
    ])

    r = controler_export_koxo(session, f, type_personne="eleve")
    e = [x for x in r.ecarts if x.genre == "id_non_numerique"][0]
    assert e.badge_referentiel == "81010", "le badge de Lana, pas celui de Léna"
    assert "81010" in e.correction
    assert "97820" not in e.correction
    assert "Lena LE SAOUT" in e.consequence, "le conflit d'identifiant est dit"


def test_un_id_absent_recoit_le_badge_de_la_personne(session, tmp_path, peupler):
    from backend.services.controle_koxo import controler_export_koxo

    peupler([("eleve", "COSTES", "Flore", "fcostes", 94680)])
    f = _export(tmp_path, [
        ["Elèves", "T_STMG1", "", "COSTES", "Flore", "fcostes", "",
         "Xxxxxx11", "flore.costes@lekreisker.fr"],
    ], entetes=[
        "Groupe primaire", "Groupe secondaire", "Titre", "Nom", "Prénom",
        "Identifiant", "ID unique", "Mot de passe", "Email",
    ])

    r = controler_export_koxo(session, f, type_personne="eleve")
    e = [x for x in r.ecarts if x.genre == "id_absent"][0]
    assert e.correction == "Mettre 94680 dans l'ID unique du compte « fcostes »."


def test_deux_homonymes_ne_donnent_aucune_proposition(session, tmp_path, peupler):
    """Choisir serait deviner — et écrire un badge faux dans KoXo."""
    from backend.services.controle_koxo import controler_export_koxo

    peupler([
        ("eleve", "MARTIN", "Paul", "pmartin", 100),
        ("eleve", "MARTIN", "Paul", "pmartin1", 200),
    ])
    f = _export(tmp_path, [
        ["Elèves", "31", "", "MARTIN", "Paul", "pmartin", "", "Xxxxxx11", "x@y.fr"],
    ], entetes=[
        "Groupe primaire", "Groupe secondaire", "Titre", "Nom", "Prénom",
        "Identifiant", "ID unique", "Mot de passe", "Email",
    ])

    r = controler_export_koxo(session, f, type_personne="eleve")
    e = [x for x in r.ecarts if x.genre == "id_absent"][0]
    assert e.correction == "", "aucune correction proposée"
    assert "2 personnes portent ce nom" in e.consequence


def test_un_doublon_nomme_le_compte_a_supprimer(session, tmp_path, peupler):
    """« Supprime le compte en trop » obligeait à revenir demander lequel."""
    from backend.services.controle_koxo import controler_export_koxo

    peupler([("eleve", "PERON", "Lou", "lperon", 87500)])
    f = _export(tmp_path, [
        _prof("PERON", "Lou", "lperon", 87500),
        _prof("PERON", "Lou", "lperon1", 87500),
    ])

    r = controler_export_koxo(session, f, type_personne="eleve")
    e = [x for x in r.ecarts if x.genre == "id_en_double"][0]
    assert "« lperon1 »" in e.correction, "le compte en trop est nommé"
    assert "garder « lperon »" in e.correction
    assert "désactiver" in e.correction, "désactiver est une option, et sa limite est dite"


def test_un_doublon_sans_titulaire_connu_ne_propose_rien(session, tmp_path, peupler):
    from backend.services.controle_koxo import controler_export_koxo

    peupler([("eleve", "AUTRE", "Ann", "aautre", 1)])
    f = _export(tmp_path, [
        _prof("PERON", "Lou", "lperon", 87500),
        _prof("PERON", "Lou", "lperon1", 87500),
    ])

    r = controler_export_koxo(session, f, type_personne="eleve")
    e = [x for x in r.ecarts if x.genre == "id_en_double"][0]
    assert e.correction == ""
    assert "lequel est réellement utilisé" in e.consequence


def test_un_nom_a_espace_se_rapproche_quand_meme(session, tmp_path, peupler):
    """KoXo écrit « LE SAOUT », les adresses « lesaout »."""
    from backend.services.controle_koxo import controler_export_koxo

    peupler([("eleve", "LESAOUT", "Lana", "llesaout", 81010)])
    f = _export(tmp_path, [
        ["Elèves", "T_G3B", "", "LE SAOUT", "Lana", "llesaout", "",
         "Xxxxxx11", "x@y.fr"],
    ], entetes=[
        "Groupe primaire", "Groupe secondaire", "Titre", "Nom", "Prénom",
        "Identifiant", "ID unique", "Mot de passe", "Email",
    ])

    r = controler_export_koxo(session, f, type_personne="eleve")
    e = [x for x in r.ecarts if x.genre == "id_absent"][0]
    assert e.badge_referentiel == "81010"
