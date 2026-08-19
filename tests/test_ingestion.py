"""Tests de l'ingestion unifiée (Lot 3).

Le fichier n'est pas lu depuis un vrai HTM/XLSX — on injecte des lignes
directement pour isoler le comportement d'ingestion du parser.
"""
from __future__ import annotations

import pandas as pd
import pytest

from backend.models import Personne, Snapshot, TableCorrespondance
from backend.services.ingestion import (
    RapportIngestion,
    _ingerer_adultes,
    _ingerer_eleves,
    detecter_type_export,
)


@pytest.fixture()
def sites_amorces(session, site_factory):
    """Trois sites amorcés : NDE / NDK / SU."""
    return {
        "NDE": site_factory("NDE"),
        "NDK": site_factory("NDK"),
        "SU": site_factory("SU"),
    }


@pytest.fixture()
def table_corr(session, sites_amorces):
    """Quelques classes dans la table de correspondance."""
    lignes = [
        (sites_amorces["SU"].id, "TROISIEME 1", "31", "/4. SU/SU2026/31"),
        (sites_amorces["SU"].id, "SIXIEME 1", "61", "/4. SU/SU2026/61"),
        (sites_amorces["NDK"].id, "PREMIERE AGORA", "1_BPAGORA", "/3. NDK/NDK2026/1_BPAGORA"),
        (sites_amorces["NDK"].id, "SECONDE 1", "2_1", "/3. NDK/NDK2026/2_1"),
        (sites_amorces["NDE"].id, "TROISIEME FUSHIA", "3F", "/2. NDE/NDE2026/3F"),
    ]
    for site_id, long, code, ou_def in lignes:
        session.add(
            TableCorrespondance(
                site_id=site_id,
                classe_charlemagne_long=long,
                classe_code_court=code,
                ou_pre_rentree=ou_def.rsplit("/", 1)[0],
                ou_definitive=ou_def,
            )
        )
    session.commit()


def _rapport_vide(type_p: str = "eleve") -> RapportIngestion:
    return RapportIngestion(type_personne=type_p, annee_libelle="2025-2026", mode="reel")


def _df_eleves(*lignes: dict) -> pd.DataFrame:
    """Construit un DF avec toutes les colonnes attendues (défauts pandas)."""
    cols = ("id_charlemagne", "num_badge", "nom", "prenom", "code_classe",
            "code_classe_precedente", "code_classe_an_prochain", "email", "code_regime")
    normalisees = []
    for l in lignes:
        normalisees.append({c: l.get(c) for c in cols})
    return pd.DataFrame(normalisees)


class TestDetecterType:
    def test_eleve(self):
        df = pd.DataFrame([{"num_badge": 1, "code_classe": "31", "nom": "X"}])
        assert detecter_type_export(df) == "eleve"

    def test_adulte(self):
        df = pd.DataFrame(
            [{"id_charlemagne": 1, "nom": "X", "poste_occupe": "PROF"}]
        )
        assert detecter_type_export(df) == "adulte"

    def test_inconnu(self):
        df = pd.DataFrame([{"foo": "bar"}])
        assert detecter_type_export(df) is None


class TestIngestionEleves:
    def test_creation_personne_et_snapshot(
        self, session, table_corr
    ):
        df = _df_eleves(
            {
                "id_charlemagne": 5292,
                "nom": "ABIVEN",
                "prenom": "Nathan",
                "code_classe": "1_BPAGORA",
                "code_regime": "E",
            }
        )
        r = _ingerer_eleves(session, df, "2025-2026", "reel", _rapport_vide())
        assert r.nb_lignes_lues == 1
        assert r.nb_lignes_ingerees == 1
        assert r.nb_personnes_creees == 1
        assert r.nb_snapshots_crees == 1
        assert not r.est_bloquee
        # Personne persistée
        p = session.query(Personne).filter_by(id_charlemagne=5292).one()
        assert p.type == "eleve"
        assert p.badge == 62920
        assert p.login == "nabiven"
        assert p.classe == "1_BPAGORA"
        assert p.regime == "E"

    def test_classe_inconnue_bloque_en_reel(
        self, session, table_corr
    ):
        df = _df_eleves(
            {
                "id_charlemagne": 1,
                "nom": "X",
                "prenom": "Y",
                "code_classe": "CLASSE_INEXISTANTE",
            }
        )
        r = _ingerer_eleves(session, df, "2025-2026", "reel", _rapport_vide())
        assert r.est_bloquee
        assert "CLASSE_INEXISTANTE" in r.classes_inconnues
        # Rien n'a été écrit
        assert session.query(Personne).count() == 0

    def test_classe_inconnue_pas_bloquante_en_simulation(
        self, session, table_corr
    ):
        df = _df_eleves(
            {
                "id_charlemagne": 1,
                "nom": "X",
                "prenom": "Y",
                "code_classe": "CLASSE_INCONNUE",
            }
        )
        r = _ingerer_eleves(
            session,
            df,
            "2025-2026",
            "simulation",
            _rapport_vide(),
        )
        # Simulation : le rapport rapporte la classe manquante mais n'est pas bloqué
        assert not r.est_bloquee
        assert "CLASSE_INCONNUE" in r.classes_inconnues
        # Rien n'a été committé
        assert session.query(Personne).count() == 0

    def test_idempotence_pas_de_nouveau_snapshot_si_etat_identique(
        self, session, table_corr
    ):
        df = _df_eleves(
            {
                "id_charlemagne": 5292,
                "nom": "ABIVEN",
                "prenom": "Nathan",
                "code_classe": "1_BPAGORA",
                "code_regime": "E",
            }
        )
        _ingerer_eleves(session, df, "2025-2026", "reel", _rapport_vide())
        r2 = _ingerer_eleves(session, df, "2025-2026", "reel", _rapport_vide())
        assert r2.nb_personnes_creees == 0
        assert r2.nb_personnes_mises_a_jour == 1
        assert r2.nb_snapshots_crees == 0
        assert r2.nb_snapshots_identiques == 1
        # Un seul snapshot en base
        assert session.query(Snapshot).count() == 1

    def test_changement_de_classe_cree_nouveau_snapshot(
        self, session, table_corr
    ):
        df1 = _df_eleves(
            {
                "id_charlemagne": 5292,
                "nom": "ABIVEN",
                "prenom": "Nathan",
                "code_classe": "1_BPAGORA",
                "code_regime": "E",
            }
        )
        _ingerer_eleves(session, df1, "2025-2026", "reel", _rapport_vide())
        # Nathan change de classe
        df2 = _df_eleves(
            {
                "id_charlemagne": 5292,
                "nom": "ABIVEN",
                "prenom": "Nathan",
                "code_classe": "2_1",
                "code_regime": "E",
            }
        )
        r = _ingerer_eleves(session, df2, "2025-2026", "reel", _rapport_vide())
        assert r.nb_snapshots_crees == 1
        assert session.query(Snapshot).count() == 2
        # Sa classe a été mise à jour côté Personne
        p = session.query(Personne).filter_by(id_charlemagne=5292).one()
        assert p.classe == "2_1"

    def test_changement_de_nom_conserve_login(
        self, session, table_corr
    ):
        df = _df_eleves(
            {
                "id_charlemagne": 100,
                "nom": "MARTIN",
                "prenom": "Léa",
                "code_classe": "31",
            }
        )
        _ingerer_eleves(session, df, "2025-2026", "reel", _rapport_vide())
        # Léa se marie et change de nom
        df2 = _df_eleves(
            {
                "id_charlemagne": 100,
                "nom": "MARTIN-LE GALL",
                "prenom": "Léa",
                "code_classe": "31",
            }
        )
        r = _ingerer_eleves(session, df2, "2025-2026", "reel", _rapport_vide())
        assert r.nb_personnes_creees == 0
        assert r.nb_snapshots_crees == 1
        p = session.query(Personne).filter_by(id_charlemagne=100).one()
        assert p.nom == "MARTIN-LE GALL"
        assert p.login == "lmartin"  # login figé — pas recalculé

    def test_collision_login_donne_suffixe_et_rapport(
        self, session, table_corr, personne_factory
    ):
        # Un adulte 'jbars' existe déjà
        personne_factory(
            type="adulte", id_charlemagne=1, nom="BARS", prenom="Jean", login="jbars"
        )
        # Un élève 'Julien BARS' arrive → collision, suffixe attribué
        df = _df_eleves(
            {
                "id_charlemagne": 500,
                "nom": "BARS",
                "prenom": "Julien",
                "code_classe": "31",
            }
        )
        r = _ingerer_eleves(session, df, "2025-2026", "reel", _rapport_vide())
        assert r.nb_personnes_creees == 1
        assert len(r.collisions_login) == 1
        collision = r.collisions_login[0]
        assert collision.login_base == "jbars"
        assert collision.login_attribue == "jbars2"
        assert collision.personnes_deja_presentes[0]["cle_pivot"] == "A1"

    def test_homonymes_intra_export_detectes(
        self, session, table_corr
    ):
        df = _df_eleves(
            {
                "id_charlemagne": 100,
                "nom": "DUPONT",
                "prenom": "Pierre",
                "code_classe": "31",
            },
            {
                "id_charlemagne": 200,
                "nom": "DUPONT",
                "prenom": "Pierre",
                "code_classe": "61",
            },
        )
        r = _ingerer_eleves(session, df, "2025-2026", "reel", _rapport_vide())
        assert len(r.homonymes_intra_export) == 1
        grp = r.homonymes_intra_export[0]
        assert grp.nom_normalise == "DUPONT"
        assert grp.prenom_normalise == "PIERRE"
        assert set(grp.ids_charlemagne) == {100, 200}
        # Les deux Pierre DUPONT sont créés quand même (clés pivot distinctes)
        assert session.query(Personne).filter_by(nom="DUPONT").count() == 2

    def test_ligne_sans_id_charlemagne_ignoree(
        self, session, table_corr
    ):
        df = _df_eleves(
            {
                "id_charlemagne": None,
                "nom": "X",
                "prenom": "Y",
                "code_classe": "31",
            }
        )
        r = _ingerer_eleves(session, df, "2025-2026", "reel", _rapport_vide())
        assert r.nb_lignes_ignorees == 1
        assert r.nb_personnes_creees == 0

    def test_simulation_ne_persiste_rien(
        self, session, table_corr
    ):
        df = _df_eleves(
            {
                "id_charlemagne": 42,
                "nom": "X",
                "prenom": "Y",
                "code_classe": "31",
            }
        )
        r = _ingerer_eleves(
            session, df, "2025-2026", "simulation", _rapport_vide()
        )
        # Le rapport DIT qu'on créerait 1 personne + 1 snapshot
        assert r.nb_personnes_creees == 1
        assert r.nb_snapshots_crees == 1
        # Mais rien n'est en base
        assert session.query(Personne).count() == 0
        assert session.query(Snapshot).count() == 0


class TestIngestionAdultes:
    def test_creation_adulte(self, session, sites_amorces):
        df = pd.DataFrame(
            [
                {
                    "id_charlemagne": 60,
                    "nom": "ALDRIN",
                    "prenom": "Thierry",
                    "civilite": "M.",
                    "poste_occupe": None,
                    "matieres": "TECHNOLOGIE",
                    "email_professionnel": "thierry.aldrin@lekreisker.fr",
                }
            ]
        )
        r = _ingerer_adultes(
            session, df, "2025-2026", "reel", _rapport_vide("adulte")
        )
        assert r.nb_personnes_creees == 1
        p = session.query(Personne).filter_by(id_charlemagne=60, type="adulte").one()
        assert p.badge == 60  # pas de formule pour les adultes
        assert p.login == "taldrin"
        assert p.matieres == "TECHNOLOGIE"
        assert p.civilite == "M."

    def test_coexistence_e60_et_a60(
        self, session, table_corr
    ):
        """Cas critique du prompt : ID Charlemagne 60 pour un élève ET un adulte."""
        df_ad = pd.DataFrame(
            [
                {
                    "id_charlemagne": 60,
                    "nom": "ALDRIN",
                    "prenom": "Thierry",
                    "poste_occupe": "PROF",
                }
            ]
        )
        _ingerer_adultes(session, df_ad, "2025-2026", "reel", _rapport_vide("adulte"))
        df_el = _df_eleves(
            {
                "id_charlemagne": 60,
                "nom": "MARTIN",
                "prenom": "Léa",
                "code_classe": "31",
            }
        )
        _ingerer_eleves(session, df_el, "2025-2026", "reel", _rapport_vide())
        # Deux personnes distinctes, mêmes id_charlemagne
        assert session.query(Personne).filter_by(id_charlemagne=60).count() == 2
        eleve = session.query(Personne).filter_by(type="eleve", id_charlemagne=60).one()
        adulte = session.query(Personne).filter_by(type="adulte", id_charlemagne=60).one()
        assert eleve.cle_pivot == "E60"
        assert adulte.cle_pivot == "A60"
        assert eleve.id != adulte.id


class TestCaptureEmailConstate:
    """L'adresse d'un compte existant est relevée depuis l'export.

    Charlemagne porte l'adresse réelle de chaque compte déjà ouvert. La
    mémoriser évite de la recalculer — un calcul ne retrouve qu'environ
    93 % des adresses en place sur l'export réel.
    """

    def test_adresse_ecole_est_memorisee(self, session, table_corr):
        df = _df_eleves(
            {
                "id_charlemagne": 5292,
                "nom": "DANIELOU",
                "prenom": "Ambre",
                "code_classe": "31",
                "email": "ambre.danielou@lekreisker.fr",
            }
        )
        _ingerer_eleves(session, df, "2025-2026", "reel", _rapport_vide())
        p = session.query(Personne).filter_by(type="eleve", id_charlemagne=5292).one()
        assert p.email_constate == "ambre.danielou@lekreisker.fr"
        assert p.email == "ambre.danielou@lekreisker.fr"

    def test_adresse_hors_convention_est_conservee_telle_quelle(
        self, session, table_corr
    ):
        """Nom composé tronqué : le calcul donnerait autre chose."""
        df = _df_eleves(
            {
                "id_charlemagne": 5293,
                "nom": "HENOCQ KERAUTRET",
                "prenom": "Sarah",
                "code_classe": "31",
                "email": "sarah.henocq@lekreisker.fr",
            }
        )
        _ingerer_eleves(session, df, "2025-2026", "reel", _rapport_vide())
        p = session.query(Personne).filter_by(type="eleve", id_charlemagne=5293).one()
        assert p.email == "sarah.henocq@lekreisker.fr"

    def test_adresse_personnelle_est_ignoree(self, session, table_corr):
        """gmail/orange/icloud : adresse de contact, pas un compte de l'ESK."""
        df = _df_eleves(
            {
                "id_charlemagne": 5294,
                "nom": "CALVEZ",
                "prenom": "Shanisse",
                "code_classe": "31",
                "email": "shanisse.c11@gmail.com",
            }
        )
        _ingerer_eleves(session, df, "2025-2026", "reel", _rapport_vide())
        p = session.query(Personne).filter_by(type="eleve", id_charlemagne=5294).one()
        assert p.email_constate is None
        # L'adresse reste calculée sur le domaine du site
        assert p.email == "shanisse.calvez@lekreisker.fr"

    def test_sans_email_l_adresse_est_calculee(self, session, table_corr):
        """Nouvel arrivant : pas encore de compte, donc pas d'adresse constatée."""
        df = _df_eleves(
            {
                "id_charlemagne": 5295,
                "nom": "LE GALL",
                "prenom": "Maël",
                "code_classe": "31",
            }
        )
        _ingerer_eleves(session, df, "2025-2026", "reel", _rapport_vide())
        p = session.query(Personne).filter_by(type="eleve", id_charlemagne=5295).one()
        assert p.email_constate is None
        assert p.email == "mael.le.gall@lekreisker.fr"

    def test_adresse_constatee_n_est_jamais_ecrasee(self, session, table_corr):
        """Une seconde ingestion ne réécrit pas l'adresse d'un compte en place."""
        base = {
            "id_charlemagne": 5296,
            "nom": "MOAL",
            "prenom": "Lena",
            "code_classe": "31",
        }
        _ingerer_eleves(
            session, _df_eleves({**base, "email": "lena.moal@lekreisker.fr"}),
            "2025-2026", "reel", _rapport_vide(),
        )
        # Charlemagne change d'avis l'année suivante
        _ingerer_eleves(
            session, _df_eleves({**base, "email": "lena.moal2@lekreisker.fr"}),
            "2026-2027", "reel", _rapport_vide(),
        )
        p = session.query(Personne).filter_by(type="eleve", id_charlemagne=5296).one()
        assert p.email_constate == "lena.moal@lekreisker.fr"

    def test_adulte_utilise_email_professionnel(self, session, sites_amorces):
        df = pd.DataFrame(
            [
                {
                    "id_charlemagne": 60,
                    "nom": "BARS",
                    "prenom": "Julien",
                    "poste_occupe": "PROF",
                    "email_professionnel": "julien.bars@lekreisker.fr",
                    "email_personnel": "jbars@orange.fr",
                }
            ]
        )
        _ingerer_adultes(session, df, "2025-2026", "reel", _rapport_vide("adulte"))
        p = session.query(Personne).filter_by(type="adulte", id_charlemagne=60).one()
        assert p.email_constate == "julien.bars@lekreisker.fr"


class TestOrdreDesIngestions:
    """Réimporter une année ancienne ne doit pas faire reculer le référentiel.

    C'est une manipulation nécessaire : pour détecter les sortants, il faut
    réimporter l'année passée en incluant les élèves partis — donc après
    l'année nouvelle.
    """

    def test_annee_ancienne_ne_reecrit_pas_la_classe(self, session, table_corr):
        base = {"id_charlemagne": 5300, "nom": "MONTANT", "prenom": "Zoe"}
        _ingerer_eleves(
            session, _df_eleves({**base, "code_classe": "31"}),
            "2026-2027", "reel", _rapport_vide(),
        )
        rapport = _rapport_vide()
        _ingerer_eleves(
            session, _df_eleves({**base, "code_classe": "61"}),
            "2025-2026", "reel", rapport,
        )

        p = session.query(Personne).filter_by(type="eleve", id_charlemagne=5300).one()
        assert p.classe == "31"  # la situation présente reste celle de 2026-2027
        assert any("plus récente" in a for a in rapport.avertissements)

    def test_le_snapshot_ancien_est_bien_cree(self, session, table_corr):
        base = {"id_charlemagne": 5301, "nom": "MONTANT", "prenom": "Lou"}
        _ingerer_eleves(
            session, _df_eleves({**base, "code_classe": "31"}),
            "2026-2027", "reel", _rapport_vide(),
        )
        _ingerer_eleves(
            session, _df_eleves({**base, "code_classe": "61"}),
            "2025-2026", "reel", _rapport_vide(),
        )

        p = session.query(Personne).filter_by(type="eleve", id_charlemagne=5301).one()
        classes = {
            s.annee_scolaire.libelle: s.classe
            for s in session.query(Snapshot).filter_by(personne_id=p.id).all()
        }
        assert classes == {"2026-2027": "31", "2025-2026": "61"}

    def test_annee_la_plus_recente_met_bien_a_jour(self, session, table_corr):
        base = {"id_charlemagne": 5302, "nom": "MONTANT", "prenom": "Ana"}
        _ingerer_eleves(
            session, _df_eleves({**base, "code_classe": "61"}),
            "2025-2026", "reel", _rapport_vide(),
        )
        rapport = _rapport_vide()
        _ingerer_eleves(
            session, _df_eleves({**base, "code_classe": "31"}),
            "2026-2027", "reel", rapport,
        )

        p = session.query(Personne).filter_by(type="eleve", id_charlemagne=5302).one()
        assert p.classe == "31"
        assert rapport.avertissements == []

    def test_sortant_reapparait_apres_reimport_avec_les_partis(
        self, session, table_corr
    ):
        """Le scénario complet : la case « sortants » cochée sur l'année source."""
        from backend.services.reconciliation import reconcilier

        reste = {"id_charlemagne": 5303, "nom": "RESTE", "prenom": "Ana"}
        parti = {"id_charlemagne": 5304, "nom": "TERMINALE", "prenom": "Luc"}

        # L'année nouvelle : seul celui qui reste
        _ingerer_eleves(
            session, _df_eleves({**reste, "code_classe": "31"}),
            "2026-2027", "reel", _rapport_vide(),
        )
        # L'année passée, réimportée avec les sortants
        _ingerer_eleves(
            session,
            _df_eleves(
                {**reste, "code_classe": "61"},
                {**parti, "code_classe": "61"},
            ),
            "2025-2026", "reel", _rapport_vide(),
        )

        from backend.models import AnneeScolaire
        ids = {a.libelle: a.id for a in session.query(AnneeScolaire).all()}
        r = reconcilier(session, ids["2025-2026"], ids["2026-2027"], type_personne="eleve")
        assert [e.nom for e in r.sortants] == ["TERMINALE"]
        assert r.avertissements == []  # un vrai sortant : plus de garde-fou


class TestExportAvecSortants:
    """L'option « inclure les sortants » de Charlemagne remonte aussi les
    élèves partis les années précédentes, sans classe pour l'année exportée.

    Mesuré sur le fichier réel 2025-2026 : 2127 lignes, dont 437 sans classe
    — des sortants de 2024-2025, qui n'ont pas fait 2025-2026.
    """

    def test_ligne_sans_classe_est_ecartee(self, session, table_corr):
        df = _df_eleves(
            {"id_charlemagne": 5400, "nom": "PRESENT", "prenom": "Ana",
             "code_classe": "31", "code_classe_precedente": "41"},
            {"id_charlemagne": 5401, "nom": "PARTI AVANT", "prenom": "Luc",
             "code_classe": None, "code_classe_precedente": "T_G1A"},
        )
        rapport = _rapport_vide()
        _ingerer_eleves(session, df, "2025-2026", "reel", rapport)

        assert rapport.nb_lignes_sans_classe == 1
        assert rapport.nb_lignes_ingerees == 1
        assert session.query(Personne).filter_by(type="eleve", id_charlemagne=5401).first() is None
        assert any("sans classe" in a for a in rapport.avertissements)

    def test_un_parti_avant_ne_devient_pas_sortant_de_cette_rentree(
        self, session, table_corr
    ):
        """Sinon on archiverait un compte disparu il y a deux ans comme s'il
        venait de partir — et il faudrait le chercher dans le mauvais dossier."""
        from backend.models import AnneeScolaire
        from backend.services.reconciliation import reconcilier

        # L'année passée, export avec sortants : un présent, un parti avant
        _ingerer_eleves(
            session,
            _df_eleves(
                {"id_charlemagne": 5402, "nom": "RESTE", "prenom": "Ana", "code_classe": "31"},
                {"id_charlemagne": 5403, "nom": "PARTI AVANT", "prenom": "Luc",
                 "code_classe": None, "code_classe_precedente": "T_G1A"},
            ),
            "2025-2026", "reel", _rapport_vide(),
        )
        # Cette année : seul celui qui reste
        _ingerer_eleves(
            session,
            _df_eleves({"id_charlemagne": 5402, "nom": "RESTE", "prenom": "Ana", "code_classe": "61"}),
            "2026-2027", "reel", _rapport_vide(),
        )

        ids = {a.libelle: a.id for a in session.query(AnneeScolaire).all()}
        r = reconcilier(session, ids["2025-2026"], ids["2026-2027"], type_personne="eleve")
        assert r.sortants == []
        assert [e.nom for e in r.modifies] == ["RESTE"]

    def test_le_parti_avant_ne_touche_aucun_compte(self, session, table_corr):
        """Un import charge des données, il ne décide pas du sort des comptes.

        Sur l'export 2026-2027, ces lignes sont les sortants de la rentrée en
        cours : leur traitement passe par l'action « Traiter les sortants »,
        délibérée et confirmée. Les basculer ici mettrait 428 comptes en
        quarantaine à l'insu de l'utilisateur.
        """
        from backend.models import CompteCible, Personne as P

        site = session.query(__import__("backend.models", fromlist=["Site"]).Site).first()
        session.add(P(type="eleve", id_charlemagne=5410, badge=64100,
                      login="lpartiavant", nom="PARTI AVANT", prenom="Luc",
                      site_id=site.id))
        session.commit()

        rapport = _rapport_vide()
        _ingerer_eleves(
            session,
            _df_eleves({"id_charlemagne": 5410, "nom": "PARTI AVANT", "prenom": "Luc",
                        "code_classe": None, "code_classe_precedente": "T_G1A"}),
            "2025-2026", "reel", rapport,
        )

        assert rapport.nb_lignes_sans_classe == 1
        assert session.query(CompteCible).count() == 0
