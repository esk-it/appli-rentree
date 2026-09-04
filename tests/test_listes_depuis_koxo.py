"""Les listes et les étiquettes d'un site, tirées de son export KoXo.

Le référentiel ne connaît pas les mots de passe — là où KoXo existe, c'est
lui l'autorité. Or les trois documents de la rentrée en ont tous besoin :
la liste du professeur principal, celle des entrants, et les étiquettes.
"""
from __future__ import annotations

import io

import openpyxl
import pytest


class _LigneKoxo:
    def __init__(self, id_unique, login="", mot_de_passe="", nom="", prenom=""):
        self.id_unique = id_unique
        self.login = login
        self.mot_de_passe = mot_de_passe
        self.nom = nom
        self.prenom = prenom


@pytest.fixture()
def snap_factory(session):
    from backend.models import Snapshot

    def _creer(personne_id, annee_id, classe):
        s = Snapshot(personne_id=personne_id, annee_scolaire_id=annee_id,
                     nom="X", prenom="Y", classe=classe)
        session.add(s)
        session.commit()
        return s

    return _creer


@pytest.fixture()
def etab(session, site_factory, annee_factory):
    su = site_factory("SU")
    return su, annee_factory("2025-2026"), annee_factory("2026-2027")


@pytest.fixture()
def deux_eleves(session, etab, personne_factory, snap_factory):
    """Une élève déjà là l'an dernier, un entrant."""
    su, source, cible = etab
    ancienne = personne_factory(
        type="eleve", site_id=su.id, nom="ABGRALL", prenom="Lena", login="labgrall",
    )
    entrant = personne_factory(
        type="eleve", site_id=su.id, nom="BIHAN", prenom="Tom", login="tbihan",
    )
    snap_factory(ancienne.id, source.id, "61")
    snap_factory(ancienne.id, cible.id, "51")
    snap_factory(entrant.id, cible.id, "61")
    return ancienne, entrant


def _lignes(*personnes):
    return [
        _LigneKoxo(str(p.badge), login=p.login, mot_de_passe=f"Mdp{p.id:05d}",
                   nom=p.nom, prenom=p.prenom)
        for p in personnes
    ]


def _lire_xlsx(octets):
    wb = openpyxl.load_workbook(io.BytesIO(octets))
    ws = wb.active
    return [[c.value for c in r] for r in ws.iter_rows()]


# ---------------------------------------------------------------------------
# Les trois documents
# ---------------------------------------------------------------------------


def test_la_liste_porte_tout_le_site_avec_les_mots_de_passe(
    session, etab, deux_eleves
):
    from backend.services.listes_depuis_koxo import COLONNES, listes_depuis_koxo

    su, source, cible = etab
    r = listes_depuis_koxo(
        session, _lignes(*deux_eleves), site_id=su.id,
        annee_cible_id=cible.id, annee_source_id=source.id,
    )
    assert r.nb_tous == 2
    lignes = _lire_xlsx(r.xlsx_tous)
    assert lignes[0] == list(COLONNES)
    mdp = {l[0]: l[4] for l in lignes[1:]}
    assert all(m and m.startswith("Mdp") for m in mdp.values())
    assert r.nom_xlsx_tous == "Comptes_SU_2026-2027_tous.xlsx"


def test_les_nouveaux_sont_ceux_absents_de_l_annee_precedente(
    session, etab, deux_eleves
):
    from backend.services.listes_depuis_koxo import listes_depuis_koxo

    su, source, cible = etab
    ancienne, entrant = deux_eleves
    r = listes_depuis_koxo(
        session, _lignes(*deux_eleves), site_id=su.id,
        annee_cible_id=cible.id, annee_source_id=source.id,
    )
    assert [l.nom for l in r.nouveaux] == ["BIHAN"]
    lignes = _lire_xlsx(r.xlsx_nouveaux)
    assert len(lignes) == 2, "l'en-tête et le seul entrant"


def test_les_etiquettes_ne_portent_que_les_nouveaux(session, etab, deux_eleves):
    from backend.services.listes_depuis_koxo import listes_depuis_koxo

    su, source, cible = etab
    r = listes_depuis_koxo(
        session, _lignes(*deux_eleves), site_id=su.id,
        annee_cible_id=cible.id, annee_source_id=source.id,
    )
    html = r.etiquettes_nouveaux.decode("utf-8")
    assert "BIHAN" in html
    assert "ABGRALL" not in html, "l'ancienne a déjà ses identifiants"


def test_la_classe_du_college_separe_le_niveau_du_rang(session, etab, deux_eleves):
    """« 33 » ne se lit pas comme une troisième. Le lycée sépare déjà les
    siennes (`1_G2`) : sur un document distribué, la même école ne doit
    pas parler deux langues. Le code stocké, lui, ne change pas."""
    from backend.services.listes_depuis_koxo import (
        classe_lisible,
        listes_depuis_koxo,
    )

    assert classe_lisible("33") == "3_3"
    assert classe_lisible("61") == "6_1"
    assert classe_lisible("1_G2") == "1_G2", "le lycée est déjà séparé"
    assert classe_lisible("BTS_1") == "BTS_1"
    assert classe_lisible("") == ""

    su, source, cible = etab
    r = listes_depuis_koxo(
        session, _lignes(*deux_eleves), site_id=su.id,
        annee_cible_id=cible.id, annee_source_id=source.id,
    )
    classes = {l[2] for l in _lire_xlsx(r.xlsx_tous)[1:]}
    assert classes == {"5_1", "6_1"}, "le classeur porte la forme lisible"
    assert {l.classe for l in r.lignes} == {"51", "61"}, "le code reste intact"


def test_letiquette_porte_ladresse_de_leleve(session, etab, deux_eleves):
    """C'est ce que l'élève vient chercher. Le gabarit lit la clé
    `adresse` ; l'oublier ne lève rien et sort « Email : » suivi de rien."""
    from backend.services.listes_depuis_koxo import listes_depuis_koxo

    su, source, cible = etab
    _, entrant = deux_eleves
    entrant.email_constate = "tom.bihan@lekreisker.fr"
    session.commit()

    r = listes_depuis_koxo(
        session, _lignes(*deux_eleves), site_id=su.id,
        annee_cible_id=cible.id, annee_source_id=source.id,
    )
    html = r.etiquettes_nouveaux.decode("utf-8")
    assert "tom.bihan@lekreisker.fr" in html


def test_sans_annee_precedente_aucun_document_d_entrants(
    session, etab, deux_eleves
):
    """« Nouveau » n'a alors pas de sens, et tout le monde le paraîtrait."""
    from backend.services.listes_depuis_koxo import listes_depuis_koxo

    su, _, cible = etab
    r = listes_depuis_koxo(
        session, _lignes(*deux_eleves), site_id=su.id, annee_cible_id=cible.id,
    )
    assert r.nb_tous == 2
    assert r.xlsx_nouveaux == b"" and r.etiquettes_nouveaux == b""


# ---------------------------------------------------------------------------
# Ce que l'export ne donne pas
# ---------------------------------------------------------------------------


def test_un_eleve_absent_de_l_export_est_nomme(session, etab, deux_eleves):
    """Il n'aura pas de mot de passe à distribuer : le taire le ferait
    manquer au moment de la distribution."""
    from backend.services.listes_depuis_koxo import listes_depuis_koxo

    su, source, cible = etab
    ancienne, entrant = deux_eleves
    r = listes_depuis_koxo(
        session, _lignes(ancienne), site_id=su.id,
        annee_cible_id=cible.id, annee_source_id=source.id,
    )
    assert r.sans_ligne_koxo == ["Tom BIHAN"]
    assert r.nb_tous == 1


def test_une_colonne_de_mot_de_passe_vide_est_signalee(session, etab, deux_eleves):
    """L'export a été pris sans cocher « inclure les mots de passe »."""
    from backend.services.listes_depuis_koxo import listes_depuis_koxo

    su, source, cible = etab
    lignes = _lignes(*deux_eleves)
    for l in lignes:
        l.mot_de_passe = ""
    r = listes_depuis_koxo(
        session, lignes, site_id=su.id,
        annee_cible_id=cible.id, annee_source_id=source.id,
    )
    assert len(r.sans_mot_de_passe) == 2


def test_l_export_d_une_autre_base_est_refuse(session, etab, deux_eleves):
    """KoXo a une base par établissement : déposer celle de NDK pour SU ne
    doit pas rendre une liste vide, mais dire pourquoi."""
    from backend.services.listes_depuis_koxo import (
        ListesImpossibles,
        listes_depuis_koxo,
    )

    su, source, cible = etab
    with pytest.raises(ListesImpossibles, match="autre serveur"):
        listes_depuis_koxo(
            session, [_LigneKoxo("999999", login="x", mot_de_passe="Y")],
            site_id=su.id, annee_cible_id=cible.id, annee_source_id=source.id,
        )


def test_comparer_une_annee_a_elle_meme_est_refuse(session, etab, deux_eleves):
    """Vécu : l'écran classait les années par date de création, où
    « 2025-2026 » venait après « 2026-2027 ». La source valait la cible,
    la liste des entrants sortait vide, et rien ne disait pourquoi."""
    from backend.services.listes_depuis_koxo import (
        ListesImpossibles,
        listes_depuis_koxo,
    )

    su, _, cible = etab
    with pytest.raises(ListesImpossibles, match="la même"):
        listes_depuis_koxo(
            session, _lignes(*deux_eleves), site_id=su.id,
            annee_cible_id=cible.id, annee_source_id=cible.id,
        )


def test_un_export_vide_est_refuse(session, etab):
    from backend.services.listes_depuis_koxo import (
        ListesImpossibles,
        listes_depuis_koxo,
    )

    su, _, cible = etab
    with pytest.raises(ListesImpossibles, match="aucune ligne"):
        listes_depuis_koxo(session, [], site_id=su.id, annee_cible_id=cible.id)


def test_le_login_de_koxo_l_emporte_sur_celui_du_referentiel(
    session, etab, deux_eleves
):
    """C'est avec lui que l'élève se connecte au réseau ; il peut différer
    après une reprise manuelle dans KoXo."""
    from backend.services.listes_depuis_koxo import listes_depuis_koxo

    su, source, cible = etab
    ancienne, entrant = deux_eleves
    lignes = _lignes(ancienne, entrant)
    lignes[0].login = "labgrall2"
    r = listes_depuis_koxo(
        session, lignes, site_id=su.id,
        annee_cible_id=cible.id, annee_source_id=source.id,
    )
    assert any(l.login == "labgrall2" for l in r.lignes)


def test_la_classe_vient_de_la_photographie_de_l_annee(
    session, etab, deux_eleves
):
    """Pas de la classe courante : les deux divergent dès qu'un mouvement a
    lieu après l'ingestion, et c'est la photographie qui date le document."""
    from backend.services.listes_depuis_koxo import listes_depuis_koxo

    su, source, cible = etab
    ancienne, _ = deux_eleves
    ancienne.classe = "56"          # déplacée après l'ingestion
    session.commit()

    r = listes_depuis_koxo(
        session, _lignes(*deux_eleves), site_id=su.id,
        annee_cible_id=cible.id, annee_source_id=source.id,
    )
    assert next(l for l in r.lignes if l.nom == "ABGRALL").classe == "51"
