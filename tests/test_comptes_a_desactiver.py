"""Ce qu'une synchronisation KoXo effacerait, et le droit de dire non.

Un export « tous » vaut état complet : KoXo désactive tout compte du
groupe primaire qui n'y figure pas. Vu du programme, un professeur parti
et un remplaçant que Charlemagne ne porte pas encore sont indiscernables
— tous deux sans photographie pour l'année visée. La différence est
pourtant celle entre un compte fermé à propos et un accès coupé un matin
de rentrée.
"""
from __future__ import annotations

import csv
import io

import pytest


def _lire(contenu: bytes) -> list[dict]:
    return list(csv.DictReader(io.StringIO(contenu.decode("cp1252", "replace"))))


@pytest.fixture()
def snap_factory(session):
    from backend.models import Snapshot

    def _creer(personne_id, annee_id, **kw):
        s = Snapshot(
            personne_id=personne_id, annee_scolaire_id=annee_id,
            nom=kw.pop("nom", "X"), prenom=kw.pop("prenom", "Y"), **kw,
        )
        session.add(s)
        session.commit()
        return s

    return _creer


@pytest.fixture()
def constat_factory(session):
    from backend.models import LoginReserve

    def _creer(login, badge, site="NDK", **kw):
        c = LoginReserve(
            login=login, badge=badge, site=site, source="controle_koxo",
            nom=kw.pop("nom", "SORTANT"), prenom=kw.pop("prenom", "Jean"),
            groupe_primaire=kw.pop("groupe_primaire", "Professeurs"),
            **kw,
        )
        session.add(c)
        session.commit()
        return c

    return _creer


@pytest.fixture()
def base(session, site_factory, annee_factory, personne_factory, snap_factory):
    """Un site, une année, deux professeurs que Charlemagne porte."""
    site = site_factory("NDK")
    an = annee_factory("2026-2027")
    restants = []
    for i in range(2):
        p = personne_factory(
            type="adulte", site_id=site.id, id_charlemagne=200 + i,
            nom=f"RESTE{i}", prenom="Marie", login=f"mreste{i}",
        )
        snap_factory(p.id, an.id, matieres="Mathematiques")
        restants.append(p)
    return site, an, restants


# ---------------------------------------------------------------------------
# Nommer avant de désactiver
# ---------------------------------------------------------------------------


def test_le_compte_absent_de_l_export_est_nomme(
    session, base, constat_factory
):
    """KoXo annonce « Désactiver 7 » sans dire lesquels. Le programme, si."""
    from backend.services.comptes_a_desactiver import comptes_a_desactiver

    site, an, restants = base
    for p in restants:
        constat_factory(p.login, p.badge)
    constat_factory("esenabre", 606, nom="SENABRE", prenom="Eric",
                    groupe_secondaire="LETTRES MODERNES")

    r = comptes_a_desactiver(
        session, site_id=site.id, type_personne="adulte", annee_cible_id=an.id,
    )
    assert [c.login for c in r.comptes] == ["esenabre"]
    assert r.nb_menaces == 1
    assert r.comptes[0].groupe_secondaire == "LETTRES MODERNES"


def test_le_motif_distingue_le_sortant_de_l_inconnu(
    session, base, constat_factory, personne_factory
):
    """C'est là-dessus que la décision se prend, et nulle part ailleurs."""
    from backend.services.comptes_a_desactiver import comptes_a_desactiver

    site, an, _ = base
    # Connu du référentiel, mais absent de l'export Charlemagne de l'année.
    connu = personne_factory(
        type="adulte", site_id=site.id, id_charlemagne=300,
        nom="PARTI", prenom="Luc", login="lparti",
    )
    constat_factory("lparti", connu.badge, nom="PARTI", prenom="Luc")
    # Jamais ingéré : aucune Personne ne le porte.
    constat_factory("tglpi", 999, nom="GLPI", prenom="Test")

    r = comptes_a_desactiver(
        session, site_id=site.id, type_personne="adulte", annee_cible_id=an.id,
    )
    motifs = {c.login: c.motif for c in r.comptes}
    assert "Charlemagne" in motifs["lparti"]
    assert "inconnu du référentiel" in motifs["tglpi"]


def test_sans_controle_prealable_la_liste_le_dit(session, base):
    """Une liste vide doit se distinguer d'une base qu'on n'a pas lue."""
    from backend.services.comptes_a_desactiver import comptes_a_desactiver

    site, an, _ = base
    r = comptes_a_desactiver(
        session, site_id=site.id, type_personne="adulte", annee_cible_id=an.id,
    )
    assert r.comptes == []
    assert any("Contrôle KoXo" in a for a in r.avertissements)


def test_les_eleves_ne_polluent_pas_la_liste_des_professeurs(
    session, base, constat_factory
):
    """Une synchronisation porte sur un groupe primaire, et sur lui seul."""
    from backend.services.comptes_a_desactiver import comptes_a_desactiver

    site, an, _ = base
    constat_factory("edupont", 92330, nom="DUPONT", prenom="Emma",
                    groupe_primaire="Elèves", groupe_secondaire="54")
    constat_factory("esenabre", 606, nom="SENABRE", prenom="Eric")

    r = comptes_a_desactiver(
        session, site_id=site.id, type_personne="adulte", annee_cible_id=an.id,
    )
    assert [c.login for c in r.comptes] == ["esenabre"]


# ---------------------------------------------------------------------------
# Le garder
# ---------------------------------------------------------------------------


def test_un_compte_conserve_revient_dans_l_export(
    session, base, constat_factory
):
    """C'est tout l'objet : le montrer à la synchronisation pour qu'elle
    n'y touche pas."""
    from backend.services.comptes_a_desactiver import definir_conservation
    from backend.services.exports_koxo import generer_csv_koxo

    site, an, _ = base
    constat_factory("esenabre", 606, nom="SENABRE", prenom="Eric",
                    groupe_secondaire="LETTRES MODERNES",
                    email="eric.senabre@lekreisker.fr")

    avant, _ = generer_csv_koxo(
        session, site_id=site.id, type_personne="adulte", categorie="tous",
        annee_cible_id=an.id,
    )
    assert "606" not in {l["ID unique"] for l in _lire(avant)}

    definir_conservation(session, badges=[606], base="NDK", conserver=True)
    session.commit()

    apres = _lire(
        generer_csv_koxo(
            session, site_id=site.id, type_personne="adulte",
            categorie="tous", annee_cible_id=an.id,
        )[0]
    )
    ligne = next(l for l in apres if l["ID unique"] == "606")
    # Recopié du constat, pas recalculé : on ne veut rien changer à ce compte.
    assert ligne["Identifiant"] == "esenabre"
    assert ligne["Groupe secondaire"] == "LETTRES MODERNES"
    assert ligne["Email"] == "eric.senabre@lekreisker.fr"
    assert ligne["Groupe primaire"] == "Professeurs"


def test_conserver_ne_duplique_pas_une_personne_deja_exportee(
    session, base, constat_factory
):
    """Deux lignes pour un même ID unique, et la synchronisation choisit
    sans nous."""
    from backend.services.comptes_a_desactiver import definir_conservation
    from backend.services.exports_koxo import generer_csv_koxo

    site, an, restants = base
    p = restants[0]
    constat_factory(p.login, p.badge, nom=p.nom, prenom=p.prenom)
    definir_conservation(session, badges=[p.badge], base="NDK", conserver=True)
    session.commit()

    lignes = _lire(
        generer_csv_koxo(
            session, site_id=site.id, type_personne="adulte",
            categorie="tous", annee_cible_id=an.id,
        )[0]
    )
    assert [l["ID unique"] for l in lignes].count(str(p.badge)) == 1


def test_la_conservation_vaut_par_base(session, base, constat_factory):
    """Un professeur peut mériter d'être gardé au lycée et pas au collège."""
    from backend.services.comptes_a_desactiver import definir_conservation
    from backend.services.exports_koxo import generer_csv_koxo

    site, an, _ = base
    constat_factory("esenabre", 606, site="NDK", nom="SENABRE", prenom="Eric",
                    groupe_secondaire="LETTRES MODERNES")
    constat_factory("esenabre", 606, site="SU", nom="SENABRE", prenom="Eric",
                    groupe_secondaire="LETTRES")

    definir_conservation(session, badges=[606], base="NDK", conserver=True)
    session.commit()

    vers_ndk = _lire(
        generer_csv_koxo(
            session, site_id=site.id, type_personne="adulte",
            categorie="tous", annee_cible_id=an.id, base_koxo="NDK",
        )[0]
    )
    vers_su = _lire(
        generer_csv_koxo(
            session, site_id=site.id, type_personne="adulte",
            categorie="tous", annee_cible_id=an.id, base_koxo="SU",
        )[0]
    )
    assert "606" in {l["ID unique"] for l in vers_ndk}
    assert "606" not in {l["ID unique"] for l in vers_su}


def test_seul_l_export_complet_reconduit_les_conserves(
    session, base, constat_factory, annee_factory
):
    """« Nouveaux » et « anciens » sont des fichiers partiels : y ajouter
    des conservés n'aurait aucun sens."""
    from backend.services.comptes_a_desactiver import definir_conservation
    from backend.services.exports_koxo import generer_csv_koxo

    site, an, _ = base
    source = annee_factory("2025-2026")
    constat_factory("esenabre", 606, nom="SENABRE", prenom="Eric")
    definir_conservation(session, badges=[606], base="NDK", conserver=True)
    session.commit()

    nouveaux = _lire(
        generer_csv_koxo(
            session, site_id=site.id, type_personne="adulte",
            categorie="nouveaux", annee_cible_id=an.id,
            annee_source_id=source.id,
        )[0]
    )
    assert "606" not in {l["ID unique"] for l in nouveaux}


def test_relacher_un_compte_le_remet_dans_la_liste(
    session, base, constat_factory
):
    from backend.services.comptes_a_desactiver import (
        comptes_a_desactiver,
        definir_conservation,
    )

    site, an, _ = base
    constat_factory("esenabre", 606, nom="SENABRE", prenom="Eric")
    definir_conservation(session, badges=[606], base="NDK", conserver=True)
    session.commit()

    r = comptes_a_desactiver(
        session, site_id=site.id, type_personne="adulte", annee_cible_id=an.id,
    )
    assert r.nb_conserves == 1 and r.nb_menaces == 0

    definir_conservation(session, badges=[606], base="NDK", conserver=False)
    session.commit()
    r = comptes_a_desactiver(
        session, site_id=site.id, type_personne="adulte", annee_cible_id=an.id,
    )
    assert r.nb_conserves == 0 and r.nb_menaces == 1


# ---------------------------------------------------------------------------
# L'avertissement de l'export
# ---------------------------------------------------------------------------


def test_l_export_annonce_les_desactivations_par_leur_nom(
    session, base, constat_factory
):
    """Le fichier ne peut pas mentir là-dessus : autant le dire où la
    décision se prend encore."""
    from backend.services.exports_koxo import generer_csv_koxo

    site, an, _ = base
    constat_factory("esenabre", 606, nom="SENABRE", prenom="Eric")

    _, rapport = generer_csv_koxo(
        session, site_id=site.id, type_personne="adulte", categorie="tous",
        annee_cible_id=an.id,
    )
    assert any(
        "désactivera" in a and "SENABRE" in a for a in rapport.avertissements
    )


# ---------------------------------------------------------------------------
# L'adresse : un constat ne se laisse pas écraser par un calcul
# ---------------------------------------------------------------------------


def test_l_adresse_de_la_base_prime_sur_l_adresse_calculee(
    session, base, constat_factory, personne_factory, snap_factory
):
    """La règle des particules ne se devine pas — et la base, elle, la sait.

    Sur l'instance réelle, l'export réécrivait trente-huit adresses de
    professeurs. Interrogé, Google a donné tort au calcul trente-trois
    fois : `isabelle.le.duff@` n'existe pas, `isabelle.leduff@` si.
    """
    from backend.services.exports_koxo import generer_csv_koxo

    site, an, _ = base
    p = personne_factory(
        type="adulte", site_id=site.id, id_charlemagne=400,
        nom="LE DUFF", prenom="Isabelle", login="ileduff",
    )
    snap_factory(p.id, an.id, matieres="Anglais")
    constat_factory("ileduff", p.badge, nom="LE DUFF", prenom="Isabelle",
                    email="isabelle.leduff@lekreisker.fr")

    lignes = _lire(
        generer_csv_koxo(
            session, site_id=site.id, type_personne="adulte",
            categorie="tous", annee_cible_id=an.id,
        )[0]
    )
    ligne = next(l for l in lignes if l["ID unique"] == str(p.badge))
    assert ligne["Email"] == "isabelle.leduff@lekreisker.fr"


def test_l_adresse_verifiee_dans_google_prime_sur_celle_de_la_base(
    session, base, constat_factory, personne_factory, snap_factory
):
    """Google est là où la personne se connecte : c'est le constat le plus fort."""
    from backend.services.exports_koxo import generer_csv_koxo

    site, an, _ = base
    p = personne_factory(
        type="adulte", site_id=site.id, id_charlemagne=401,
        nom="ROUXEL", prenom="Eve", login="erouxel",
        email_constate="eve.despre@lekreisker.fr",
    )
    snap_factory(p.id, an.id, matieres="SVT")
    constat_factory("erouxel", p.badge, nom="ROUXEL", prenom="Eve",
                    email="eve.rouxel@lekreisker.fr")

    lignes = _lire(
        generer_csv_koxo(
            session, site_id=site.id, type_personne="adulte",
            categorie="tous", annee_cible_id=an.id,
        )[0]
    )
    ligne = next(l for l in lignes if l["ID unique"] == str(p.badge))
    assert ligne["Email"] == "eve.despre@lekreisker.fr"


def test_un_entrant_garde_son_adresse_calculee(
    session, base, personne_factory, snap_factory
):
    """Il n'a ni compte Google ni compte KoXo : il faut bien lui en proposer une."""
    from backend.services.exports_koxo import generer_csv_koxo

    site, an, _ = base
    p = personne_factory(
        type="adulte", site_id=site.id, id_charlemagne=402,
        nom="ENTRANT", prenom="Nouvelle", login="nentrant",
    )
    snap_factory(p.id, an.id, matieres="NSI")

    lignes = _lire(
        generer_csv_koxo(
            session, site_id=site.id, type_personne="adulte",
            categorie="tous", annee_cible_id=an.id,
        )[0]
    )
    ligne = next(l for l in lignes if l["ID unique"] == str(p.badge))
    assert ligne["Email"] == "nouvelle.entrant@lekreisker.fr"


def test_l_export_previent_qu_il_va_ecraser_des_adresses_reelles(
    session, base, constat_factory, personne_factory, snap_factory
):
    """Le remplacement était silencieux. C'est ce qui le rendait coûteux."""
    from backend.services.exports_koxo import generer_csv_koxo

    site, an, _ = base
    p = personne_factory(
        type="adulte", site_id=site.id, id_charlemagne=403,
        nom="CREIGNOU", prenom="Anne-Helene", login="acreignou",
        email_constate="anne-helene.creignou@lekreisker.fr",
    )
    snap_factory(p.id, an.id, matieres="Anglais")
    # La base tient une adresse courte, historique, que rien ne recalcule.
    constat_factory("acreignou", p.badge, nom="CREIGNOU", prenom="Anne-Helene",
                    email="ah.creignou@lekreisker.fr")

    _, rapport = generer_csv_koxo(
        session, site_id=site.id, type_personne="adulte", categorie="tous",
        annee_cible_id=an.id,
    )
    assert any(
        "remplaceront celle que la base détient" in a
        for a in rapport.avertissements
    )


def test_un_eleve_conserve_ne_glisse_pas_dans_l_export_des_professeurs(
    session, base, constat_factory
):
    """Un export porte une population, et une seule.

    Le fichier aurait présenté l'élève sous le groupe primaire
    `Professeurs` : la synchronisation l'aurait sorti des élèves.
    """
    from backend.services.comptes_a_desactiver import definir_conservation
    from backend.services.exports_koxo import generer_csv_koxo

    site, an, _ = base
    constat_factory("edupont", 92330, nom="DUPONT", prenom="Emma",
                    groupe_primaire="Elèves", groupe_secondaire="54")
    definir_conservation(session, badges=[92330], base="NDK", conserver=True)
    session.commit()

    lignes = _lire(
        generer_csv_koxo(
            session, site_id=site.id, type_personne="adulte",
            categorie="tous", annee_cible_id=an.id,
        )[0]
    )
    assert "92330" not in {l["ID unique"] for l in lignes}
