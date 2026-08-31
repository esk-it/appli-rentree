"""Tests des exports KoXo (Tous / Nouveaux / Anciens).

Vérifie le format CSV (colonnes officielles, encodage cp1252, MDP vide) et
la logique métier de chaque catégorie via snapshots + réconciliation.
"""
from __future__ import annotations

import csv
import io

import pytest
from fastapi.testclient import TestClient


@pytest.fixture()
def client(tmp_db_path):
    from backend.main import app

    with TestClient(app) as c:
        yield c


@pytest.fixture()
def snap_factory(session):
    """Crée un Snapshot minimal."""
    from backend.models import Snapshot

    def _creer(personne_id, annee_id, **kwargs):
        defaults = {"nom": "MARTIN", "prenom": "Jean", "classe": "3B"}
        defaults.update(kwargs)
        s = Snapshot(personne_id=personne_id, annee_scolaire_id=annee_id, **defaults)
        session.add(s)
        session.commit()
        return s

    return _creer


def _lire_csv_koxo(contenu: bytes) -> list[dict]:
    """Décode un CSV KoXo (cp1252) et retourne la liste des rows."""
    texte = contenu.decode("cp1252")
    reader = csv.DictReader(io.StringIO(texte))
    return list(reader)


# ---------------------------------------------------------------------------
# Format
# ---------------------------------------------------------------------------


def test_export_a_les_colonnes_officielles_koxo(session, site_factory, annee_factory, personne_factory, snap_factory):
    from backend.services.exports_koxo import COLONNES_KOXO, generer_csv_koxo

    site = site_factory("NDK")
    annee = annee_factory("2025-2026")
    p = personne_factory(site_id=site.id, nom="DUPONT", prenom="Jean", login="jdupont")
    snap_factory(p.id, annee.id)

    contenu, _ = generer_csv_koxo(
        session=session, site_id=site.id, type_personne="eleve",
        categorie="tous", annee_cible_id=annee.id,
    )
    rows = _lire_csv_koxo(contenu)

    assert len(rows) == 1
    assert list(rows[0].keys()) == COLONNES_KOXO


def test_export_mdp_toujours_vide(session, site_factory, annee_factory, personne_factory, snap_factory):
    """Principe : KoXo est l'autorité qui génère les MDP, pas nous."""
    from backend.services.exports_koxo import generer_csv_koxo

    site = site_factory("NDK")
    annee = annee_factory()
    p = personne_factory(site_id=site.id, login="test1")
    snap_factory(p.id, annee.id)

    contenu, _ = generer_csv_koxo(
        session=session, site_id=site.id, type_personne="eleve",
        categorie="tous", annee_cible_id=annee.id,
    )
    rows = _lire_csv_koxo(contenu)

    for r in rows:
        assert r["Mot de passe"] == ""


def test_export_encodage_cp1252(session, site_factory, annee_factory, personne_factory, snap_factory):
    """Les caractères accentués doivent être encodés en cp1252 (attendu par KoXo)."""
    from backend.services.exports_koxo import generer_csv_koxo

    site = site_factory("NDK")
    annee = annee_factory()
    p = personne_factory(site_id=site.id, nom="LEGOFF", prenom="Hélène", login="hlegoff")
    snap_factory(p.id, annee.id)

    contenu, _ = generer_csv_koxo(
        session=session, site_id=site.id, type_personne="eleve",
        categorie="tous", annee_cible_id=annee.id,
    )
    # Doit se décoder proprement en cp1252
    texte = contenu.decode("cp1252")
    assert "Hélène" in texte


def test_export_email_calcule_depuis_nom_prenom_et_domaine(session, site_factory, annee_factory, personne_factory, snap_factory):
    from backend.services.exports_koxo import generer_csv_koxo

    site = site_factory("NDK")  # domaine lekreisker.fr par défaut
    annee = annee_factory()
    p = personne_factory(site_id=site.id, nom="DUPONT", prenom="Jean", login="jdupont")
    snap_factory(p.id, annee.id)

    contenu, _ = generer_csv_koxo(
        session=session, site_id=site.id, type_personne="eleve",
        categorie="tous", annee_cible_id=annee.id,
    )
    rows = _lire_csv_koxo(contenu)
    # Le login reste `jdupont`, l'adresse est `jean.dupont` : deux règles distinctes
    assert rows[0]["Identifiant"] == "jdupont"
    assert rows[0]["Email"] == "jean.dupont@lekreisker.fr"


def test_export_groupe_primaire_eleve_vs_adulte(session, site_factory, annee_factory, personne_factory, snap_factory):
    from backend.services.exports_koxo import generer_csv_koxo

    site = site_factory("NDK")
    annee = annee_factory()
    p_eleve = personne_factory(type="eleve", site_id=site.id, login="e1")
    p_adulte = personne_factory(type="adulte", site_id=site.id, login="a1")
    snap_factory(p_eleve.id, annee.id, classe="3B")
    snap_factory(p_adulte.id, annee.id, poste_occupe="ENSEIGNEMENT", matieres="MATHEMATIQUES")

    c_e, _ = generer_csv_koxo(session=session, site_id=site.id, type_personne="eleve",
                              categorie="tous", annee_cible_id=annee.id)
    c_a, _ = generer_csv_koxo(session=session, site_id=site.id, type_personne="adulte",
                              categorie="tous", annee_cible_id=annee.id)

    assert _lire_csv_koxo(c_e)[0]["Groupe primaire"] == "Elèves"
    assert _lire_csv_koxo(c_a)[0]["Groupe primaire"] == "Professeurs"


def test_export_groupe_secondaire_eleve_est_classe(session, site_factory, annee_factory, personne_factory, snap_factory):
    from backend.services.exports_koxo import generer_csv_koxo

    site = site_factory("NDK")
    annee = annee_factory()
    p = personne_factory(site_id=site.id, login="test1")
    snap_factory(p.id, annee.id, classe="1_G2")

    contenu, _ = generer_csv_koxo(
        session=session, site_id=site.id, type_personne="eleve",
        categorie="tous", annee_cible_id=annee.id,
    )
    assert _lire_csv_koxo(contenu)[0]["Groupe secondaire"] == "1_G2"


def test_export_groupe_secondaire_adulte_est_matiere(session, site_factory, annee_factory, personne_factory, snap_factory):
    from backend.services.exports_koxo import generer_csv_koxo

    site = site_factory("NDK")
    annee = annee_factory()
    p = personne_factory(type="adulte", site_id=site.id, login="prof1")
    snap_factory(p.id, annee.id, matieres="MATHEMATIQUES;PHYSIQUE-CHIMIE", poste_occupe="ENSEIGNEMENT")

    contenu, _ = generer_csv_koxo(
        session=session, site_id=site.id, type_personne="adulte",
        categorie="tous", annee_cible_id=annee.id,
    )
    # Première matière du séparateur ;
    assert _lire_csv_koxo(contenu)[0]["Groupe secondaire"] == "MATHEMATIQUES"


# ---------------------------------------------------------------------------
# Catégories : Tous / Nouveaux / Anciens
# ---------------------------------------------------------------------------


def test_export_tous_liste_toutes_les_personnes_de_lannee(
    session, site_factory, annee_factory, personne_factory, snap_factory
):
    from backend.services.exports_koxo import generer_csv_koxo

    site = site_factory("NDK")
    annee = annee_factory()
    for i in range(1, 4):
        p = personne_factory(site_id=site.id, nom=f"P{i}", prenom=f"P{i}", login=f"p{i}")
        snap_factory(p.id, annee.id, classe="3B")

    contenu, rapport = generer_csv_koxo(
        session=session, site_id=site.id, type_personne="eleve",
        categorie="tous", annee_cible_id=annee.id,
    )
    assert rapport.nb_lignes == 3
    assert len(_lire_csv_koxo(contenu)) == 3


def test_export_nouveaux_seulement_les_entrants(
    session, site_factory, annee_factory, personne_factory, snap_factory
):
    """Un nouvel élève = présent dans annee_cible, absent d'annee_source."""
    from backend.services.exports_koxo import generer_csv_koxo

    site = site_factory("NDK")
    an_prec = annee_factory("2024-2025")
    an_cour = annee_factory("2025-2026")

    p_reste = personne_factory(site_id=site.id, nom="RESTE", login="reste")
    snap_factory(p_reste.id, an_prec.id, classe="3B")
    snap_factory(p_reste.id, an_cour.id, classe="2NDE")

    p_nouveau = personne_factory(site_id=site.id, nom="NEUF", login="neuf")
    snap_factory(p_nouveau.id, an_cour.id, classe="6A")

    contenu, rapport = generer_csv_koxo(
        session=session, site_id=site.id, type_personne="eleve",
        categorie="nouveaux", annee_cible_id=an_cour.id, annee_source_id=an_prec.id,
    )

    assert rapport.nb_lignes == 1
    assert _lire_csv_koxo(contenu)[0]["Nom"] == "NEUF"


def test_export_anciens_seulement_les_sortants(
    session, site_factory, annee_factory, personne_factory, snap_factory
):
    """Un ancien = présent dans annee_source, absent d'annee_cible."""
    from backend.services.exports_koxo import generer_csv_koxo

    site = site_factory("NDK")
    an_prec = annee_factory("2024-2025")
    an_cour = annee_factory("2025-2026")

    p_reste = personne_factory(site_id=site.id, nom="RESTE", login="reste")
    snap_factory(p_reste.id, an_prec.id, classe="3B")
    snap_factory(p_reste.id, an_cour.id, classe="2NDE")

    p_sortant = personne_factory(site_id=site.id, nom="SORT", login="sort")
    snap_factory(p_sortant.id, an_prec.id, classe="TALE")

    contenu, rapport = generer_csv_koxo(
        session=session, site_id=site.id, type_personne="eleve",
        categorie="anciens", annee_cible_id=an_cour.id, annee_source_id=an_prec.id,
    )

    assert rapport.nb_lignes == 1
    assert _lire_csv_koxo(contenu)[0]["Nom"] == "SORT"


def test_export_filtre_par_site(session, site_factory, annee_factory, personne_factory, snap_factory):
    """Un export NDK ne contient pas les élèves SU."""
    from backend.services.exports_koxo import generer_csv_koxo

    ndk = site_factory("NDK")
    su = site_factory("SU")
    annee = annee_factory()

    p_ndk = personne_factory(site_id=ndk.id, nom="NDK1", login="ndk1")
    snap_factory(p_ndk.id, annee.id)
    p_su = personne_factory(site_id=su.id, nom="SU1", login="su1")
    snap_factory(p_su.id, annee.id)

    contenu, rapport = generer_csv_koxo(
        session=session, site_id=ndk.id, type_personne="eleve",
        categorie="tous", annee_cible_id=annee.id,
    )
    assert rapport.nb_lignes == 1
    assert _lire_csv_koxo(contenu)[0]["Nom"] == "NDK1"


def test_export_filtre_par_type_personne(
    session, site_factory, annee_factory, personne_factory, snap_factory
):
    from backend.services.exports_koxo import generer_csv_koxo

    site = site_factory("NDK")
    annee = annee_factory()
    p_e = personne_factory(type="eleve", site_id=site.id, login="e1")
    p_a = personne_factory(type="adulte", site_id=site.id, login="a1")
    snap_factory(p_e.id, annee.id)
    snap_factory(p_a.id, annee.id)

    c_e, r_e = generer_csv_koxo(session=session, site_id=site.id, type_personne="eleve",
                                categorie="tous", annee_cible_id=annee.id)
    c_a, r_a = generer_csv_koxo(session=session, site_id=site.id, type_personne="adulte",
                                categorie="tous", annee_cible_id=annee.id)

    assert r_e.nb_lignes == 1 and r_a.nb_lignes == 1


# ---------------------------------------------------------------------------
# Validation des paramètres
# ---------------------------------------------------------------------------


def test_export_categorie_nouveaux_sans_annee_source_leve_erreur(session, site_factory, annee_factory):
    from backend.services.exports_koxo import generer_csv_koxo

    site = site_factory("NDK")
    annee = annee_factory()
    with pytest.raises(ValueError, match="annee_source_id"):
        generer_csv_koxo(
            session=session, site_id=site.id, type_personne="eleve",
            categorie="nouveaux", annee_cible_id=annee.id, annee_source_id=None,
        )


def test_export_categorie_anciens_sans_annee_source_leve_erreur(session, site_factory, annee_factory):
    from backend.services.exports_koxo import generer_csv_koxo

    site = site_factory("NDK")
    annee = annee_factory()
    with pytest.raises(ValueError, match="annee_source_id"):
        generer_csv_koxo(
            session=session, site_id=site.id, type_personne="eleve",
            categorie="anciens", annee_cible_id=annee.id, annee_source_id=None,
        )


def test_export_type_invalide(session, site_factory, annee_factory):
    from backend.services.exports_koxo import generer_csv_koxo

    site = site_factory("NDK")
    annee = annee_factory()
    with pytest.raises(ValueError, match="type_personne"):
        generer_csv_koxo(session=session, site_id=site.id, type_personne="prof",
                         categorie="tous", annee_cible_id=annee.id)


def test_export_categorie_invalide(session, site_factory, annee_factory):
    from backend.services.exports_koxo import generer_csv_koxo

    site = site_factory("NDK")
    annee = annee_factory()
    with pytest.raises(ValueError, match="categorie"):
        generer_csv_koxo(session=session, site_id=site.id, type_personne="eleve",
                         categorie="autre", annee_cible_id=annee.id)


def test_export_site_introuvable(session, annee_factory):
    from backend.services.exports_koxo import generer_csv_koxo

    annee = annee_factory()
    with pytest.raises(ValueError, match="Site introuvable"):
        generer_csv_koxo(session=session, site_id=99999, type_personne="eleve",
                         categorie="tous", annee_cible_id=annee.id)


def test_nom_fichier_suggere(session, site_factory, annee_factory):
    from backend.services.exports_koxo import generer_csv_koxo

    site = site_factory("NDK")
    annee = annee_factory()
    _, rapport = generer_csv_koxo(
        session=session, site_id=site.id, type_personne="eleve",
        categorie="tous", annee_cible_id=annee.id,
    )
    assert rapport.nom_fichier_suggere == "KoXo_NDK_eleves_tous.csv"


def test_multi_snapshots_retient_le_dernier(session, site_factory, annee_factory, personne_factory):
    """Si plusieurs ingestions dans une même année, on prend le dernier snapshot."""
    from datetime import datetime, timedelta
    from backend.models import Snapshot
    from backend.services.exports_koxo import generer_csv_koxo

    site = site_factory("NDK")
    annee = annee_factory()
    p = personne_factory(site_id=site.id, login="test1")

    ancien = Snapshot(personne_id=p.id, annee_scolaire_id=annee.id,
                      nom="P", prenom="P", classe="OBSOLETE",
                      date_ingestion=datetime.utcnow() - timedelta(days=10))
    session.add(ancien)
    recent = Snapshot(personne_id=p.id, annee_scolaire_id=annee.id,
                      nom="P", prenom="P", classe="COURANT")
    session.add(recent)
    session.commit()

    contenu, _ = generer_csv_koxo(
        session=session, site_id=site.id, type_personne="eleve",
        categorie="tous", annee_cible_id=annee.id,
    )
    rows = _lire_csv_koxo(contenu)
    assert len(rows) == 1
    assert rows[0]["Groupe secondaire"] == "COURANT"


# ---------------------------------------------------------------------------
# Groupe de destination des sortants
# ---------------------------------------------------------------------------


def test_les_sortants_peuvent_etre_ranges_dans_un_groupe_dedie(
    session, site_factory, annee_factory, personne_factory, snap_factory
):
    """Sans destination, un sortant porte sa dernière classe.

    Synchronisé tel quel, KoXo le remettrait dans cette classe, au milieu
    de la promotion suivante. Le rassembler dans un groupe dédié est ce que
    recommande la documentation KoXo pour la bascule annuelle.
    """
    from backend.services.exports_koxo import generer_csv_koxo

    site = site_factory("NDK")
    prec = annee_factory("2024-2025")
    cour = annee_factory("2025-2026")
    p = personne_factory(site_id=site.id, nom="SORT", login="sort")
    snap_factory(p.id, prec.id, classe="TALE")

    contenu, _ = generer_csv_koxo(
        session=session, site_id=site.id, type_personne="eleve",
        categorie="anciens", annee_cible_id=cour.id, annee_source_id=prec.id,
    )
    assert _lire_csv_koxo(contenu)[0]["Groupe secondaire"] == "TALE"

    contenu, rapport = generer_csv_koxo(
        session=session, site_id=site.id, type_personne="eleve",
        categorie="anciens", annee_cible_id=cour.id, annee_source_id=prec.id,
        groupe_secondaire_force="Anciens élèves",
    )
    assert _lire_csv_koxo(contenu)[0]["Groupe secondaire"] == "Anciens élèves"
    assert rapport.groupe_secondaire_force == "Anciens élèves"
    assert any("NON destructif" in a for a in rapport.avertissements)


@pytest.mark.parametrize("categorie", ["tous", "nouveaux"])
def test_forcer_le_groupe_est_refuse_hors_des_sortants(
    session, site_factory, annee_factory, categorie
):
    """Sur « tous », ce serait ranger toute une population dans une classe."""
    from backend.services.exports_koxo import generer_csv_koxo

    site = site_factory("NDK")
    prec = annee_factory("2024-2025")
    cour = annee_factory("2025-2026")
    with pytest.raises(ValueError, match="anciens"):
        generer_csv_koxo(
            session=session, site_id=site.id, type_personne="eleve",
            categorie=categorie, annee_cible_id=cour.id,
            annee_source_id=prec.id, groupe_secondaire_force="Anciens élèves",
        )


def test_un_groupe_de_destination_vide_ne_force_rien(
    session, site_factory, annee_factory, personne_factory, snap_factory
):
    """Le champ laissé vide dans l'écran ne doit pas vider le groupe."""
    from backend.services.exports_koxo import generer_csv_koxo

    site = site_factory("NDK")
    prec = annee_factory("2024-2025")
    cour = annee_factory("2025-2026")
    p = personne_factory(site_id=site.id, nom="SORT", login="sort")
    snap_factory(p.id, prec.id, classe="TALE")

    contenu, rapport = generer_csv_koxo(
        session=session, site_id=site.id, type_personne="eleve",
        categorie="anciens", annee_cible_id=cour.id, annee_source_id=prec.id,
        groupe_secondaire_force="   ",
    )
    assert _lire_csv_koxo(contenu)[0]["Groupe secondaire"] == "TALE"
    assert rapport.groupe_secondaire_force is None


def test_le_rapport_signale_une_ligne_sans_id_unique(
    session, site_factory, annee_factory, personne_factory, snap_factory
):
    """Sans ID unique, la synchronisation ne reconnaîtra pas le compte."""
    from backend.services.exports_koxo import generer_csv_koxo

    site = site_factory("NDK")
    annee = annee_factory("2025-2026")
    p = personne_factory(site_id=site.id, nom="SANSBADGE", login="sb")
    p.badge = 0  # `badge` est NOT NULL ; zéro est le seul falsy possible
    session.commit()
    snap_factory(p.id, annee.id, classe="3B")

    _, rapport = generer_csv_koxo(
        session=session, site_id=site.id, type_personne="eleve",
        categorie="tous", annee_cible_id=annee.id,
    )
    assert any("sans ID unique" in a for a in rapport.avertissements)


def test_lendpoint_koxo_repond(session, site_factory, annee_factory, client):
    """Garde-fou : le routeur lisait un champ absent du rapport.

    `avertissements=rapport.avertissements` avait été ajouté au routeur
    sans le champ correspondant sur `RapportExportKoxo` — l'endpoint
    répondait 500 à chaque appel, et aucun test ne s'en apercevait parce
    que tous appelaient le service en direct.
    """
    site = site_factory("NDK")
    annee = annee_factory("2025-2026")

    r = client.post("/api/exports/koxo", json={
        "site_id": site.id, "type_personne": "eleve", "categorie": "tous",
        "annee_cible_id": annee.id,
    })
    assert r.status_code == 200, r.text
    d = r.json()
    assert "avertissements" in d
    assert "groupe_secondaire_force" in d


def test_lexport_porte_lidentifiant_que_la_base_detient(
    session, site_factory, annee_factory, personne_factory, snap_factory, tmp_path
):
    """`Personne.login` est unique globalement ; les identifiants, non.

    L'établissement tient une base KoXo par population — profs, élèves NDK,
    élèves SU. `ccueff` y désigne légitimement un adulte dans l'une et une
    élève dans l'autre. Le référentiel n'en garde qu'un et suffixe l'autre ;
    écrire ce suffixe présenterait à KoXo un identifiant qu'il ne connaît
    pas, et il renommerait le compte en le reconnaissant par son ID unique.
    Sur l'instance réelle, 28 lignes de l'export SU étaient dans ce cas.
    """
    import io as _io

    from backend.services.controle_koxo import retenir_identifiants_constates
    from backend.services.exports_koxo import generer_csv_koxo

    site = site_factory("SU")
    annee = annee_factory("2025-2026")
    p = personne_factory(
        site_id=site.id, nom="CUEFF", prenom="Clémence", login="ccueff3"
    )
    p.badge = 82840
    session.commit()
    snap_factory(p.id, annee.id, classe="31")

    # La base des élèves SU la connaît sous « ccueff ».
    f = tmp_path / "su.csv"
    with _io.open(f, "w", encoding="cp1252", newline="") as fh:
        fh.write("Groupe primaire;Nom;Prénom;Identifiant;ID unique\r\n")
        fh.write("Elèves;CUEFF;Clémence;ccueff;82840\r\n")
    retenir_identifiants_constates(session, f, site="SU")

    contenu, _ = generer_csv_koxo(
        session=session, site_id=site.id, type_personne="eleve",
        categorie="tous", annee_cible_id=annee.id,
    )
    ligne = _lire_csv_koxo(contenu)[0]
    assert ligne["Identifiant"] == "ccueff", (
        "l'identifiant constaté fait autorité, pas le suffixe du référentiel"
    )
    assert ligne["ID unique"] == "82840"


def test_sans_constat_lexport_garde_le_login_du_referentiel(
    session, site_factory, annee_factory, personne_factory, snap_factory
):
    """Tant qu'aucune base n'a été lue, le référentiel reste la seule source."""
    from backend.services.exports_koxo import generer_csv_koxo

    site = site_factory("SU")
    annee = annee_factory("2025-2026")
    p = personne_factory(
        site_id=site.id, nom="CUEFF", prenom="Clémence", login="ccueff3"
    )
    p.badge = 82840
    session.commit()
    snap_factory(p.id, annee.id, classe="31")

    contenu, _ = generer_csv_koxo(
        session=session, site_id=site.id, type_personne="eleve",
        categorie="tous", annee_cible_id=annee.id,
    )
    assert _lire_csv_koxo(contenu)[0]["Identifiant"] == "ccueff3"


def test_un_identifiant_constate_dans_une_autre_base_nest_pas_repris(
    session, site_factory, annee_factory, personne_factory, snap_factory, tmp_path
):
    """L'erreur qui a fait échouer sept créations dans l'annuaire.

    Lou-Ann BERNARD tient « lbernard » dans la base de SU. Montée au lycée,
    elle figure dans l'export de NDK — où « lbernard » appartient à Liam
    BERNARD. Reprendre son identifiant SU faisait refuser la création par
    Active Directory. Hors de sa base, c'est l'identifiant du référentiel
    qui vaut : il est unique, donc libre partout.
    """
    import io as _io

    from backend.services.controle_koxo import retenir_identifiants_constates
    from backend.services.exports_koxo import generer_csv_koxo

    site_factory("SU")
    ndk = site_factory("NDK")
    annee = annee_factory("2025-2026")

    lou_ann = personne_factory(
        site_id=ndk.id, nom="BERNARD", prenom="Lou-Ann", login="lbernard2"
    )
    lou_ann.badge = 73650
    session.commit()
    snap_factory(lou_ann.id, annee.id, classe="2_1")

    # La base de SU la connaît sous « lbernard ».
    f = tmp_path / "su.csv"
    with _io.open(f, "w", encoding="cp1252", newline="") as fh:
        fh.write("Groupe primaire;Nom;Prénom;Identifiant;ID unique\r\n")
        fh.write("Elèves;BERNARD;Lou-Ann;lbernard;73650\r\n")
    retenir_identifiants_constates(session, f, site="SU")

    contenu, _ = generer_csv_koxo(
        session=session, site_id=ndk.id, type_personne="eleve",
        categorie="tous", annee_cible_id=annee.id,
    )
    ligne = _lire_csv_koxo(contenu)[0]
    assert ligne["Identifiant"] == "lbernard2", (
        "l'export de NDK ne reprend pas un identifiant constaté sur SU"
    )


def test_un_adulte_sans_site_est_nomme_plutot_que_tu(session, site_factory):
    """Il ne sort dans aucun export : autant que l'écran le dise.

    L'ingestion Charlemagne déduit le site de la classe, et un adulte n'en
    a pas. Quinze professeurs entrants sont arrivés ainsi, absents de tous
    les exports, et rien ne l'annonçait — la synchronisation KoXo affichait
    « Créer 0 » sans expliquer pourquoi.
    """
    from backend.models import AnneeScolaire, Personne, Snapshot
    from backend.services.exports_koxo import generer_csv_koxo

    ndk = site_factory("NDK")
    annee = AnneeScolaire(libelle="2026-2027")
    session.add(annee)
    session.commit()

    for prenom, badge, site_id in (("Rattachee", 1001, ndk.id),
                                   ("Orpheline", 1002, None)):
        p = Personne(
            type="adulte", nom="MARTIN", prenom=prenom, login=prenom.lower(),
            badge=badge, id_charlemagne=badge, site_id=site_id,
        )
        session.add(p)
        session.flush()
        session.add(Snapshot(
            personne_id=p.id, annee_scolaire_id=annee.id,
            nom="MARTIN", prenom=prenom, matieres="ANGLAIS",
        ))
    session.commit()

    _, rapport = generer_csv_koxo(
        session, site_id=ndk.id, type_personne="adulte",
        categorie="tous", annee_cible_id=annee.id,
    )
    assert rapport.nb_lignes == 1, "l'orpheline ne sort pas"
    assert any("aucun site" in a and "Orpheline MARTIN" in a
               for a in rapport.avertissements)


def test_les_eleves_ne_declenchent_pas_cet_avertissement(session, site_factory):
    from backend.models import AnneeScolaire, Personne, Snapshot
    from backend.services.exports_koxo import generer_csv_koxo

    ndk = site_factory("NDK")
    annee = AnneeScolaire(libelle="2026-2027")
    session.add(annee)
    session.commit()
    p = Personne(type="eleve", nom="DUPONT", prenom="Jean", login="jdupont",
                 badge=4242, id_charlemagne=4242, site_id=None)
    session.add(p)
    session.flush()
    session.add(Snapshot(personne_id=p.id, annee_scolaire_id=annee.id,
                         nom="DUPONT", prenom="Jean", classe="6A"))
    session.commit()

    _, rapport = generer_csv_koxo(
        session, site_id=ndk.id, type_personne="eleve",
        categorie="tous", annee_cible_id=annee.id,
    )
    assert not any("aucun site" in a for a in rapport.avertissements)


# ---------------------------------------------------------------------------
# Le groupe secondaire d'un adulte appartient à la base, pas à Charlemagne
# ---------------------------------------------------------------------------


def _base_koxo(tmp_path, lignes, nom="koxo.csv"):
    import io as _io

    chemin = tmp_path / nom
    with _io.open(chemin, "w", encoding="cp1252", newline="") as f:
        f.write("Groupe primaire;Groupe secondaire;Nom;Prénom;Identifiant;"
                "ID unique\r\n")
        for l in lignes:
            f.write(";".join(str(c) for c in l) + "\r\n")
    return chemin


def _adulte(session, site, nom, prenom, login, badge, matieres, poste=None):
    from backend.models import Personne

    p = Personne(
        type="adulte", nom=nom, prenom=prenom, login=login, badge=badge,
        id_charlemagne=badge, site_id=site.id, matieres=matieres,
        poste_occupe=poste,
    )
    session.add(p)
    session.flush()
    return p


def _annee_et_snapshot(session, personne, libelle, matieres, poste=None):
    from backend.models import AnneeScolaire, Snapshot

    annee = session.query(AnneeScolaire).filter_by(libelle=libelle).one_or_none()
    if annee is None:
        annee = AnneeScolaire(libelle=libelle)
        session.add(annee)
        session.flush()
    session.add(Snapshot(
        personne_id=personne.id, annee_scolaire_id=annee.id,
        nom=personne.nom, prenom=personne.prenom,
        matieres=matieres, poste_occupe=poste,
    ))
    session.commit()
    return annee


def test_un_prof_deja_en_place_garde_le_groupe_que_koxo_lui_donne(
    session, site_factory, tmp_path
):
    """Le cas réel : trois directrices adjointes rangées sous leur fonction.

    Charlemagne les décrit par la matière qu'elles enseignent aussi. Écrire
    cette matière les sortait de `DIRECTRICE ADJOINTE` — vingt-trois comptes
    déplacés sans qu'aucun n'ait changé de poste, et autant d'accès au
    répertoire partagé de la discipline remis en jeu.
    """
    from backend.services.controle_koxo import retenir_identifiants_constates
    from backend.services.exports_koxo import generer_csv_koxo

    ndk = site_factory("NDK")
    p = _adulte(session, ndk, "GUIVARCH", "Katell", "kguivarc", 54, "ANGLAIS")
    annee = _annee_et_snapshot(session, p, "2026-2027", "ANGLAIS")

    f = _base_koxo(tmp_path, [
        ["Professeurs", "DIRECTRICE ADJOINTE", "GUIVARCH", "Katell",
         "kguivarc", 54],
    ])
    retenir_identifiants_constates(session, f, site="NDK")
    session.commit()

    contenu, _ = generer_csv_koxo(
        session, site_id=ndk.id, type_personne="adulte",
        categorie="tous", annee_cible_id=annee.id,
    )
    ligne = _lire_csv_koxo(contenu)[0]
    assert ligne["Groupe secondaire"] == "DIRECTRICE ADJOINTE"


def test_un_entrant_prend_bien_sa_matiere_charlemagne(
    session, site_factory, tmp_path
):
    """Un compte qui n'existe pas encore n'a rien à préserver."""
    from backend.services.controle_koxo import retenir_identifiants_constates
    from backend.services.exports_koxo import generer_csv_koxo

    ndk = site_factory("NDK")
    ancien = _adulte(session, ndk, "GUIVARCH", "Katell", "kguivarc", 54, "ANGLAIS")
    annee = _annee_et_snapshot(session, ancien, "2026-2027", "ANGLAIS")
    entrant = _adulte(session, ndk, "TEXIER", "Pierre", "ptexier", 679,
                      "HISTOIRE-GEOGRAPHIE")
    _annee_et_snapshot(session, entrant, "2026-2027", "HISTOIRE-GEOGRAPHIE")

    f = _base_koxo(tmp_path, [
        ["Professeurs", "DIRECTRICE ADJOINTE", "GUIVARCH", "Katell",
         "kguivarc", 54],
    ])
    retenir_identifiants_constates(session, f, site="NDK")
    session.commit()

    contenu, _ = generer_csv_koxo(
        session, site_id=ndk.id, type_personne="adulte",
        categorie="tous", annee_cible_id=annee.id,
    )
    par_nom = {l["Nom"]: l for l in _lire_csv_koxo(contenu)}
    assert par_nom["GUIVARCH"]["Groupe secondaire"] == "DIRECTRICE ADJOINTE"
    assert par_nom["TEXIER"]["Groupe secondaire"] == "HISTOIRE-GEOGRAPHIE"


def test_un_eleve_suit_sa_classe_et_ne_preserve_rien(
    session, site_factory, tmp_path
):
    """La classe change chaque année : c'est tout l'objet de la rentrée."""
    from backend.models import AnneeScolaire, Personne, Snapshot
    from backend.services.controle_koxo import retenir_identifiants_constates
    from backend.services.exports_koxo import generer_csv_koxo

    ndk = site_factory("NDK")
    p = Personne(type="eleve", nom="DUPONT", prenom="Jean", login="jdupont",
                 badge=91000, id_charlemagne=91000, site_id=ndk.id, classe="2NDA")
    session.add(p)
    session.flush()
    annee = AnneeScolaire(libelle="2026-2027")
    session.add(annee)
    session.flush()
    session.add(Snapshot(personne_id=p.id, annee_scolaire_id=annee.id,
                         nom="DUPONT", prenom="Jean", classe="2NDA"))
    session.commit()

    f = _base_koxo(tmp_path, [
        ["Elèves", "3EMEB", "DUPONT", "Jean", "jdupont", 91000],
    ])
    retenir_identifiants_constates(session, f, site="NDK")
    session.commit()

    contenu, _ = generer_csv_koxo(
        session, site_id=ndk.id, type_personne="eleve",
        categorie="tous", annee_cible_id=annee.id,
    )
    assert _lire_csv_koxo(contenu)[0]["Groupe secondaire"] == "2NDA", "la classe suit Charlemagne"


def test_un_constat_dune_autre_base_ne_sapplique_pas(
    session, site_factory, tmp_path
):
    """Le groupe constaté ne vaut que dans la base d'où il vient."""
    from backend.services.controle_koxo import retenir_identifiants_constates
    from backend.services.exports_koxo import generer_csv_koxo

    ndk = site_factory("NDK")
    site_factory("SU")
    p = _adulte(session, ndk, "GUIVARCH", "Katell", "kguivarc", 54, "ANGLAIS")
    annee = _annee_et_snapshot(session, p, "2026-2027", "ANGLAIS")

    f = _base_koxo(tmp_path, [
        ["Professeurs", "DIRECTRICE ADJOINTE", "GUIVARCH", "Katell",
         "kguivarc", 54],
    ])
    retenir_identifiants_constates(session, f, site="SU")
    session.commit()

    contenu, _ = generer_csv_koxo(
        session, site_id=ndk.id, type_personne="adulte",
        categorie="tous", annee_cible_id=annee.id,
    )
    assert _lire_csv_koxo(contenu)[0]["Groupe secondaire"] == "ANGLAIS"


def test_le_fichier_porte_les_groupes_de_la_base_visee(
    session, site_factory, tmp_path
):
    """Le même fichier sert deux serveurs qui ne nomment pas pareil.

    Nicolas GUILLOU est rangé sous `DIRECTEUR` dans la base de NDK et sous
    `PHYSIQUE-CHIMIE` dans celle de SU. Le référentiel ne le rattache qu'à
    NDK : sans désigner la base visée, le fichier servi à SU y déplaçait
    vingt-quatre comptes.
    """
    from backend.services.controle_koxo import retenir_identifiants_constates
    from backend.services.exports_koxo import generer_csv_koxo

    ndk = site_factory("NDK")
    site_factory("SU")
    p = _adulte(session, ndk, "GUILLOU", "Nicolas", "nguillou", 77,
                "PHYSIQUE-CHIMIE")
    annee = _annee_et_snapshot(session, p, "2026-2027", "PHYSIQUE-CHIMIE")

    retenir_identifiants_constates(session, _base_koxo(tmp_path, [
        ["Professeurs", "DIRECTEUR", "GUILLOU", "Nicolas", "nguillou", 77],
    ], nom="ndk.csv"), site="NDK")
    retenir_identifiants_constates(session, _base_koxo(tmp_path, [
        ["Professeurs", "PHYSIQUE-CHIMIE", "GUILLOU", "Nicolas", "nguillou", 77],
    ], nom="su.csv"), site="SU")
    session.commit()

    def groupe(base):
        contenu, _ = generer_csv_koxo(
            session, site_id=ndk.id, type_personne="adulte",
            categorie="tous", annee_cible_id=annee.id, base_koxo=base,
        )
        return _lire_csv_koxo(contenu)[0]["Groupe secondaire"]

    assert groupe(None) == "DIRECTEUR", "par défaut, la base du site"
    assert groupe("NDK") == "DIRECTEUR"
    assert groupe("SU") == "PHYSIQUE-CHIMIE"


def test_les_deux_bases_tiennent_chacune_leur_constat(session, tmp_path):
    """La clé d'unicité porte le site : lire SU n'écrase plus NDK.

    Elle a d'abord été unique sur `(login, badge)`. Sur l'instance réelle,
    176 constats sur 181 se sont retrouvés marqués « SU » après lecture du
    second export, et l'export de NDK ne retrouvait plus rien.
    """
    from backend.models import LoginReserve
    from backend.services.controle_koxo import retenir_identifiants_constates

    for base, groupe in (("NDK", "DIRECTEUR"), ("SU", "PHYSIQUE-CHIMIE")):
        retenir_identifiants_constates(session, _base_koxo(tmp_path, [
            ["Professeurs", groupe, "GUILLOU", "Nicolas", "nguillou", 77],
        ], nom=f"{base}.csv"), site=base)
    session.commit()

    constats = session.query(LoginReserve).filter_by(login="nguillou").all()
    assert {c.site for c in constats} == {"NDK", "SU"}
    assert {c.groupe_secondaire for c in constats} == {
        "DIRECTEUR", "PHYSIQUE-CHIMIE",
    }


# ---------------------------------------------------------------------------
# La graphie des groupes secondaires
# ---------------------------------------------------------------------------


def test_un_entrant_prend_la_graphie_de_la_base(session, site_factory, tmp_path):
    """`MATHEMATIQUES` de Charlemagne contre `Mathematiques` de KoXo.

    Écrire la graphie de Charlemagne ferait naître un second groupe à côté
    du premier, et l'enseignant atterrirait seul dans une discipline où ses
    collègues sont ailleurs — sans accès à leur répertoire partagé.
    """
    from backend.services.controle_koxo import retenir_identifiants_constates
    from backend.services.exports_koxo import generer_csv_koxo

    ndk = site_factory("NDK")
    ancien = _adulte(session, ndk, "TONNARD", "Sylvie", "stonnard", 54,
                     "MATHEMATIQUES")
    annee = _annee_et_snapshot(session, ancien, "2026-2027", "MATHEMATIQUES")
    entrant = _adulte(session, ndk, "BILLANT", "Pierre", "pbillant", 680,
                      "MATHEMATIQUES")
    _annee_et_snapshot(session, entrant, "2026-2027", "MATHEMATIQUES")

    # La base écrit « Mathematiques », en minuscules.
    retenir_identifiants_constates(session, _base_koxo(tmp_path, [
        ["Professeurs", "Mathematiques", "TONNARD", "Sylvie", "stonnard", 54],
    ]), site="NDK")
    session.commit()

    contenu, _ = generer_csv_koxo(
        session, site_id=ndk.id, type_personne="adulte",
        categorie="tous", annee_cible_id=annee.id,
    )
    par_nom = {l["Nom"]: l["Groupe secondaire"] for l in _lire_csv_koxo(contenu)}
    assert par_nom["TONNARD"] == "Mathematiques", "préservé par le constat"
    assert par_nom["BILLANT"] == "Mathematiques", "raccordé à la graphie de la base"


def test_une_matiere_inconnue_de_la_base_est_signalee(session, site_factory,
                                                      tmp_path):
    """`MATH. SCIENCES` est peut-être `Mathematiques` — c'est humain à dire."""
    from backend.services.controle_koxo import retenir_identifiants_constates
    from backend.services.exports_koxo import generer_csv_koxo

    ndk = site_factory("NDK")
    ancien = _adulte(session, ndk, "TONNARD", "Sylvie", "stonnard", 54, "MATHS")
    annee = _annee_et_snapshot(session, ancien, "2026-2027", "MATHS")
    entrant = _adulte(session, ndk, "BILLANT", "Pierre", "pbillant", 680,
                      "MATH. SCIENCES")
    _annee_et_snapshot(session, entrant, "2026-2027", "MATH. SCIENCES")

    retenir_identifiants_constates(session, _base_koxo(tmp_path, [
        ["Professeurs", "Mathematiques", "TONNARD", "Sylvie", "stonnard", 54],
    ]), site="NDK")
    session.commit()

    _, rapport = generer_csv_koxo(
        session, site_id=ndk.id, type_personne="adulte",
        categorie="tous", annee_cible_id=annee.id,
    )
    assert any("MATH. SCIENCES" in a and "Pierre BILLANT" in a
               for a in rapport.avertissements)


def test_sans_controle_de_la_base_le_programme_le_dit(session, site_factory):
    """Il ne peut alors ni préserver les groupes ni annoncer ce qu'il crée."""
    from backend.services.exports_koxo import generer_csv_koxo

    ndk = site_factory("NDK")
    p = _adulte(session, ndk, "TONNARD", "Sylvie", "stonnard", 54, "MATHS")
    annee = _annee_et_snapshot(session, p, "2026-2027", "MATHS")

    _, rapport = generer_csv_koxo(
        session, site_id=ndk.id, type_personne="adulte",
        categorie="tous", annee_cible_id=annee.id,
    )
    assert any("jamais été passée au Contrôle" in a for a in rapport.avertissements)
