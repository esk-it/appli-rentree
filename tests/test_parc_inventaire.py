"""Tests de l'inventaire du parc : la lecture de la console, et l'échange.

Les appareils sont fabriqués à la main, sur le modèle de ce que la console
de l'établissement contient (relevé du 16/11/2026). Google n'est jamais
appelé : l'écriture passe par un faux client qui note ce qu'on lui demande.
"""
from __future__ import annotations

from datetime import date

import pytest

PERSONNEL = "/1. Chromebooks/1. Personnel éducatif"
ELEVES_NDK = "/1. Chromebooks/2. Elèves/Lycée du Kreisker"
NDE_B100 = "/2. NDE/Appareils/B100"
NDE_HS = "/2. NDE/Appareils/Déclassé"


def _appareil(serie, ou=PERSONNEL, etiquette="", emplacement="", statut="ACTIVE", **autres):
    return {
        "serie": serie,
        "device_id": f"id-{serie}",
        "modele": "Lenovo 300e",
        "ou": ou,
        "statut": statut,
        "etiquette": etiquette,
        "emplacement": emplacement,
        "derniers_utilisateurs": [],
        "derniere_synchro": "2026-11-10T08:00:00Z",
        "fin_maj": autres.get("fin_maj"),
    }


FLOTTE = [
    _appareil("SN-PROF", etiquette="jean.martin@lekreisker.fr"),
    _appareil("SN-STOCK1", etiquette="Prof_08"),
    _appareil("SN-STOCK2", etiquette="Stagiaire 9"),
    _appareil("SN-VS", etiquette="VS Ste Ursule"),
    _appareil("SN-K08", ou=ELEVES_NDK, etiquette="K-B5-13-08", emplacement="K-B5-13"),
    _appareil("SN-LAB", ou=NDE_B100, etiquette="LAB03"),
    _appareil("SN-MORT", ou=NDE_HS, etiquette="TAB01HS"),
    _appareil("SN-DESACT", statut="DEPROVISIONED", etiquette="old@lekreisker.fr"),
]


class FauxGoogle:
    """Note les écritures demandées, sans rien envoyer."""

    def __init__(self, refuser=False):
        self.annotations = []
        self.deplacements = []
        self.refuser = refuser

    def annoter_appareil(self, device_id, *, etiquette=None, emplacement=None):
        if self.refuser:
            from backend.services.google_api import DroitManquant

            raise DroitManquant("droit d'écriture non accordé")
        self.annotations.append((device_id, etiquette, emplacement))

    def deplacer_appareil(self, device_id, ou):
        self.deplacements.append((device_id, ou))


@pytest.fixture()
def flotte(session):
    from backend.services.parc_inventaire import enregistrer_releve

    enregistrer_releve(session, FLOTTE)
    return session


def _postes(session):
    from backend.services.parc_inventaire import inventaire

    return {p.serie: p for p in inventaire(session, aujourd_hui=date(2026, 11, 16)).postes}


# ---------------------------------------------------------------------------
# Lire la console
# ---------------------------------------------------------------------------


def test_la_console_se_lit_comme_l_etablissement_la_range(flotte):
    p = _postes(flotte)
    assert (p["SN-PROF"].etat, p["SN-PROF"].porteur) == ("en_service", "jean.martin@lekreisker.fr")
    assert p["SN-STOCK1"].etat == "en_stock", "Prof_08 : le parc de prêt est le stock"
    assert p["SN-STOCK2"].etat == "en_stock"
    assert (p["SN-VS"].etat, p["SN-VS"].tenue_par) == ("en_service", "VS Ste Ursule")
    assert (p["SN-K08"].lieu, p["SN-K08"].site) == ("K-B5-13", "NDK")
    assert (p["SN-LAB"].lieu, p["SN-LAB"].site) == ("B100", "NDE")
    assert p["SN-MORT"].etat == "hs", "la branche Déclassé range les machines mortes"
    assert p["SN-DESACT"].etat == "desactivee"


def test_un_emplacement_qui_porte_le_code_de_la_place_garde_le_chariot(session):
    from backend.services.parc_inventaire import enregistrer_releve

    enregistrer_releve(session, [
        _appareil("SN-A", ou=ELEVES_NDK, etiquette="K-B5-17-11", emplacement="K-B5-17-11"),
        _appareil("SN-B", ou=ELEVES_NDK, etiquette="K-B7-CDI-03", emplacement="K-B7-CDI-03"),
        _appareil("SN-C", ou=ELEVES_NDK, etiquette="", emplacement="K-B5-16-02 New 01112024"),
        _appareil("SN-D", ou="/2. NDE/Appareils", etiquette="CDI-02"),
        _appareil("SN-E", etiquette="CHB-PROF-004"),
        _appareil("SN-F", etiquette="Maintenance 6"),
    ])
    p = _postes(session)
    assert [p[s].lieu for s in ("SN-A", "SN-B", "SN-C")] == ["K-B5-17", "K-B7-CDI", "K-B5-16"]
    assert p["SN-A"].a_verifier
    assert p["SN-D"].lieu is None, "la racine de NDE ne nomme pas une salle"
    # Johann, 16/11/2026 : les CHB-PROF sont déjà données ; les Maintenance,
    # personne ne sait plus où elles sont.
    assert (p["SN-E"].etat, p["SN-E"].tenue_par) == ("en_service", "CHB-PROF-004")
    assert "à qui" in p["SN-E"].a_verifier
    assert p["SN-F"].etat == "a_localiser"


def test_le_suivi_de_la_rentree_garde_son_sens(flotte):
    """Les machines rendues ou confiées dans « La flotte Google » avant la refonte."""
    from backend.models import SuiviChromebook

    flotte.add(SuiviChromebook(serie="SN-PROF", recupere_le=date(2026, 9, 1),
                               recupere_de="jean.martin@lekreisker.fr"))
    flotte.add(SuiviChromebook(serie="SN-STOCK1", attribue_a="ana.roux@lekreisker.fr",
                               attribue_le=date(2026, 9, 2)))
    flotte.commit()

    p = _postes(flotte)
    assert p["SN-PROF"].etat == "en_stock"
    assert p["SN-PROF"].a_verifier, "au stock, mais l'étiquette porte encore une adresse"
    assert p["SN-STOCK1"].porteur == "ana.roux@lekreisker.fr"
    assert p["SN-STOCK1"].a_reporter == ["étiquette"]


def test_une_machine_au_nom_d_un_parti_est_signalee(flotte, personne_factory, annee_factory):
    from backend.models import Snapshot
    from backend.services.parc_inventaire import inventaire

    annee_factory("2025-2026")
    courante = annee_factory("2026-2027")
    personne_factory(type="adulte", nom="MARTIN", prenom="Jean",
                     email_constate="jean.martin@lekreisker.fr")
    restee = personne_factory(type="adulte", nom="ROUX", prenom="Ana",
                              email_constate="ana.roux@lekreisker.fr")
    flotte.add(Snapshot(personne_id=restee.id, annee_scolaire_id=courante.id,
                        nom="ROUX", prenom="Ana"))
    flotte.commit()

    p = _postes(flotte)["SN-PROF"]
    assert p.porteur_nom == "Jean MARTIN"
    assert p.porteur_parti is True
    assert any("plus inscrit" in a for a in inventaire(flotte).alertes)


# ---------------------------------------------------------------------------
# Échanger
# ---------------------------------------------------------------------------


def test_echanger_la_machine_d_un_prof(flotte):
    from backend.services.parc_inventaire import echanger, journal

    recu = echanger(flotte, ancienne="SN-PROF", nouvelle="SN-STOCK1", raison="panne",
                    precision="ne charge plus", devenir="stock")

    p = _postes(flotte)
    assert (p["SN-STOCK1"].etat, p["SN-STOCK1"].porteur) == ("en_service", "jean.martin@lekreisker.fr")
    assert p["SN-PROF"].etat == "en_stock"
    assert p["SN-PROF"].etiquette_voulue == "Prof_08", "l'ancienne prend l'étiquette libérée"
    assert p["SN-STOCK1"].a_reporter == ["étiquette"]
    assert recu.a_ecrire == ["SN-STOCK1", "SN-PROF"]

    lignes = journal(flotte, serie="SN-STOCK1")
    assert {(m.serie, m.geste) for m in lignes} == {("SN-STOCK1", "echange"), ("SN-PROF", "echange")}
    arrivee = next(m for m in lignes if m.serie == "SN-STOCK1")
    assert (arrivee.raison, arrivee.precision, arrivee.autre_serie) == ("panne", "ne charge plus", "SN-PROF")


def test_seule_une_machine_du_stock_peut_etre_remise(flotte):
    from backend.services.parc_materiel import GesteImpossible
    from backend.services.parc_inventaire import echanger

    with pytest.raises(GesteImpossible, match="n'est pas au stock"):
        echanger(flotte, ancienne="SN-STOCK1", nouvelle="SN-VS", raison="panne")


def test_confier_sans_ancienne_demande_a_qui(flotte):
    from backend.services.parc_materiel import GesteImpossible
    from backend.services.parc_inventaire import echanger

    with pytest.raises(GesteImpossible, match="À qui"):
        echanger(flotte, nouvelle="SN-STOCK1", raison="arrivee")

    echanger(flotte, nouvelle="SN-STOCK1", porteur="Lea.Nouvelle@lekreisker.fr", raison="arrivee")
    assert _postes(flotte)["SN-STOCK1"].porteur == "lea.nouvelle@lekreisker.fr"


def test_la_machine_d_un_chariot_transmet_sa_place(flotte):
    """La n°8 du chariot K-B5-13 casse : celle du stock prend sa place."""
    from backend.services.parc_inventaire import echanger

    echanger(flotte, ancienne="SN-K08", nouvelle="SN-STOCK2", raison="casse",
             devenir="hs", organes=["ecran", "charniere"])

    p = _postes(flotte)
    arrivee, partie = p["SN-STOCK2"], p["SN-K08"]
    assert (arrivee.etat, arrivee.lieu, arrivee.etiquette_voulue) == ("en_service", "K-B5-13", "K-B5-13-08")
    assert arrivee.ou_voulue == ELEVES_NDK, "elle quitte la branche du personnel"
    assert partie.etat == "hs"
    assert partie.pannes == ["charniere", "ecran"]
    assert (partie.emplacement_voulu, partie.ou_voulue) == ("", PERSONNEL)
    assert set(arrivee.a_reporter) == {"étiquette", "emplacement", "unité"}


def test_reprendre_une_machine_seule(flotte):
    from backend.services.parc_inventaire import echanger

    echanger(flotte, ancienne="SN-PROF", raison="depart")
    p = _postes(flotte)["SN-PROF"]
    assert p.etat == "en_stock"
    assert p.etiquette_voulue == "Stock"


# ---------------------------------------------------------------------------
# Écrire dans Google
# ---------------------------------------------------------------------------


def test_l_echange_s_ecrit_dans_google(flotte):
    from backend.services.parc_inventaire import echanger, ecrire_dans_google

    recu = echanger(flotte, ancienne="SN-K08", nouvelle="SN-STOCK2", raison="casse", devenir="hs")
    faux = FauxGoogle()
    resultats = ecrire_dans_google(flotte, faux, recu.a_ecrire)

    assert all(r.ok for r in resultats)
    assert ("id-SN-STOCK2", "K-B5-13-08", "K-B5-13") in faux.annotations
    assert ("id-SN-K08", "Stagiaire 9", "") in faux.annotations
    assert set(faux.deplacements) == {("id-SN-STOCK2", ELEVES_NDK), ("id-SN-K08", PERSONNEL)}
    p = _postes(flotte)
    assert p["SN-STOCK2"].a_reporter == [] and p["SN-K08"].a_reporter == []


def test_un_refus_de_google_n_annule_rien(flotte):
    from backend.services.parc_inventaire import echanger, ecrire_dans_google

    recu = echanger(flotte, ancienne="SN-PROF", nouvelle="SN-STOCK1", raison="panne")
    resultats = ecrire_dans_google(flotte, FauxGoogle(refuser=True), recu.a_ecrire)

    assert not any(r.ok for r in resultats)
    p = _postes(flotte)
    assert p["SN-STOCK1"].porteur == "jean.martin@lekreisker.fr", "le geste reste noté"
    assert p["SN-STOCK1"].a_reporter == ["étiquette"], "et l'étiquette reste à reporter"


def test_le_releve_efface_les_voeux_exauces(flotte):
    from backend.services.parc_inventaire import echanger, enregistrer_releve

    echanger(flotte, ancienne="SN-PROF", nouvelle="SN-STOCK1", raison="panne")
    corrigee = [dict(a) for a in FLOTTE]
    for a in corrigee:
        if a["serie"] == "SN-STOCK1":
            a["etiquette"] = "jean.martin@lekreisker.fr"
        if a["serie"] == "SN-PROF":
            a["etiquette"] = "Prof_08"
    r = enregistrer_releve(flotte, corrigee)

    assert r.reconcilies == 2
    p = _postes(flotte)
    assert p["SN-STOCK1"].a_reporter == [] and p["SN-PROF"].a_reporter == []


def test_une_machine_disparue_de_la_console_est_gardee(flotte):
    from backend.services.parc_inventaire import enregistrer_releve

    r = enregistrer_releve(flotte, [a for a in FLOTTE if a["serie"] != "SN-LAB"])
    assert r.disparus == 1
    assert _postes(flotte)["SN-LAB"].present_google is False


def test_les_derniers_utilisateurs_disent_a_qui_l_assigner(session, personne_factory):
    """Johann, 16/11/2026 : « utilisateurs et activité récents » dit à qui elle est."""
    from backend.services.parc_inventaire import enregistrer_releve

    personne_factory(type="adulte", nom="ROUX", prenom="Ana", email_constate="ana.roux@lekreisker.fr")
    personne_factory(type="adulte", nom="MARTIN", prenom="Jean",
                     email_constate="jean.martin@lekreisker.fr")
    personne_factory(type="eleve", nom="PETIT", prenom="Léo", email_constate="leo.petit@lekreisker.fr")
    recents = ["leo.petit@lekreisker.fr", "ana.roux@lekreisker.fr", "admin@lekreisker.fr"]

    def avec(serie, etiquette, synchro="2026-11-10T08:00:00Z"):
        a = _appareil(serie, etiquette=etiquette)
        a["derniers_utilisateurs"] = recents
        a["derniere_synchro"] = synchro
        return a

    enregistrer_releve(session, [
        avec("SN-CHB", "CHB-PROF-003"),
        avec("SN-MAINT", "Maintenance 1"),
        avec("SN-ETIQ", "jean.martin@lekreisker.fr"),
        avec("SN-PRET", "Prof_04"),
        avec("SN-VIEUX", "Maintenance 6", synchro="2024-01-10T08:00:00Z"),
    ])
    p = _postes(session)
    for serie in ("SN-CHB", "SN-MAINT", "SN-ETIQ", "SN-PRET"):
        assert p[serie].porteur_probable == "ana.roux@lekreisker.fr", serie
    assert "Ana ROUX" in p["SN-MAINT"].a_verifier
    assert "mais c'est Ana ROUX" in p["SN-ETIQ"].a_verifier
    assert p["SN-ETIQ"].porteur == "jean.martin@lekreisker.fr", "on propose, on ne change rien"
    assert "au stock, mais" in p["SN-PRET"].a_verifier
    assert p["SN-VIEUX"].porteur_probable is None, "une connexion de 2024 ne dit plus rien"


def test_un_compte_hors_referentiel_est_propose_en_le_disant(session, personne_factory):
    """Les CHB-PROF servent à des personnels que l'export ne contient pas encore."""
    from backend.services.parc_inventaire import enregistrer_releve

    personne_factory(type="eleve", nom="PETIT", prenom="Léo", email_constate="leo.petit@lekreisker.fr")
    a = _appareil("SN-CHB", etiquette="CHB-PROF-002")
    a["derniers_utilisateurs"] = ["admin@lekreisker.fr", "leo.petit@lekreisker.fr",
                                  "marie.nouvelle@lekreisker.fr"]
    enregistrer_releve(session, [a])
    p = _postes(session)["SN-CHB"]
    assert p.porteur_probable == "marie.nouvelle@lekreisker.fr"
    assert "hors référentiel" in p.porteur_probable_nom


# ---------------------------------------------------------------------------
# L'inventaire physique
# ---------------------------------------------------------------------------


def test_l_inventaire_compte_ce_qu_on_a_vu(flotte):
    from backend.services.parc_inventaire import commencer_pointage, inventaire, pointer

    commencer_pointage(flotte, date(2026, 11, 16))
    avant = inventaire(flotte)
    assert avant.pointees == 0
    total = avant.a_pointer

    pointer(flotte, "SN-PROF", constat="conforme", aujourd_hui=date(2026, 11, 17))
    apres = inventaire(flotte)
    assert (apres.pointees, apres.a_pointer) == (1, total - 1)
    assert _postes(flotte)["SN-PROF"].porteur == "jean.martin@lekreisker.fr", "rien n'a bougé"


def test_une_machine_a_localiser_ne_se_dit_pas_conforme(session):
    from backend.services.parc_inventaire import enregistrer_releve, pointer
    from backend.services.parc_materiel import GesteImpossible

    enregistrer_releve(session, [_appareil("SN-M", etiquette="Maintenance 1")])
    with pytest.raises(GesteImpossible, match="ne sait pas où"):
        pointer(session, "SN-M", constat="conforme")

    pointer(session, "SN-M", constat="porteur", porteur="Ana.Roux@lekreisker.fr")
    p = _postes(session)["SN-M"]
    assert (p.etat, p.porteur) == ("en_service", "ana.roux@lekreisker.fr")
    assert p.a_reporter == ["étiquette"], "l'étiquette Google suivra, d'un clic"


def test_l_inventaire_corrige_sans_passer_par_le_stock(flotte):
    """Une machine trouvée dans la pile des pannes, une autre introuvable."""
    from backend.services.parc_inventaire import journal, pointer

    pointer(flotte, "SN-PROF", constat="hs", organes=["batterie"], note="dans le carton")
    pointer(flotte, "SN-VS", constat="introuvable")
    pointer(flotte, "SN-K08", constat="lieu", lieu="K-B5-14")
    pointer(flotte, "SN-STOCK2", constat="stock")

    p = _postes(flotte)
    assert (p["SN-PROF"].etat, p["SN-PROF"].pannes) == ("hs", ["batterie"])
    assert p["SN-VS"].etat == "introuvable"
    assert (p["SN-K08"].lieu, p["SN-K08"].a_reporter) == ("K-B5-14", ["emplacement"])
    assert p["SN-STOCK2"].etat == "en_stock"
    assert p["SN-STOCK2"].a_reporter == [], "Stagiaire 9 est déjà une étiquette de stock"
    ligne = journal(flotte, serie="SN-PROF")[0]
    assert (ligne.geste, ligne.vers) == ("pointage", "hors service (batterie)")


# ---------------------------------------------------------------------------
# Les chargeurs de rechange
# ---------------------------------------------------------------------------


def test_un_carton_de_chargeurs_se_numerote_seul(session):
    from backend.services.parc_materiel import enregistrer_accessoire, enregistrer_lot

    lot = enregistrer_lot(session, nombre=3)
    assert [a.serie for a in lot] == ["CH-001", "CH-002", "CH-003"]
    assert enregistrer_accessoire(session, "", type_accessoire="chargeur").serie == "CH-004"


def test_un_chargeur_donne_avec_l_echange(flotte):
    from backend.services.parc_inventaire import detient, echanger, inventaire
    from backend.services.parc_materiel import enregistrer_lot, etat_du_stock

    enregistrer_lot(flotte, nombre=2)
    echanger(flotte, ancienne="SN-PROF", nouvelle="SN-STOCK1", raison="panne", chargeur="CH-001")

    stock = etat_du_stock(flotte)
    donne = next(a for a in stock.accessoires if a.serie == "CH-001")
    assert (donne.etat, donne.definitif, donne.en_retard) == ("donne", True, False)
    assert inventaire(flotte).chargeurs_en_stock == 1

    d = detient(flotte, "jean.martin@lekreisker.fr")
    assert [m.serie for m in d.machines] == ["SN-STOCK1"]
    assert [a["serie"] for a in d.accessoires] == ["CH-001"]


def test_le_stock_bas_est_signale(flotte):
    from backend.services.parc_inventaire import inventaire, poser_seuils

    poser_seuils(flotte, {"machines": 5, "chargeurs": 0})
    alertes = inventaire(flotte).alertes
    assert any("Plus que 2 machines au stock" in a for a in alertes)
    assert not any("chargeur" in a for a in alertes)
