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
