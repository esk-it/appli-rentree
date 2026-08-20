"""Tests de la vidange d'une branche d'OU."""
from __future__ import annotations

from datetime import date

import pytest


def _compte(email, ou, nom="X", prenom="Y", suspendu=False):
    return {
        "email": email, "ou": ou, "suspendu": suspendu,
        "nom": nom, "prenom": prenom, "derniere_connexion": None,
    }


def test_annee_lue_dans_le_nom_de_la_branche():
    from backend.services.vidange_ou import annee_depuis_ou

    assert annee_depuis_ou("/3. NDK/NDK2025") == 2025
    assert annee_depuis_ou("/4. SU/SU2025/T_G1A") == 2025
    assert annee_depuis_ou("/2. NDE/Sortie") is None


def test_echeance_court_depuis_le_depart_pas_depuis_aujourdhui(session, site_factory):
    """Un compte oublié trois ans ne mérite pas 18 mois de plus.

    Les compter depuis le traitement reviendrait à récompenser l'oubli.
    """
    from backend.services.vidange_ou import planifier_vidange

    site_factory("NDK")
    r = planifier_vidange(
        session,
        [_compte("a@lekreisker.fr", "/3. NDK/NDK2025/T_G1A")],
        ou_source="/3. NDK/NDK2025",
        aujourd_hui=date(2026, 8, 20),
    )
    assert r.date_depart == date(2025, 8, 31)
    assert r.date_echeance == date(2027, 2, 28)
    assert "28-02-2027" in r.ou_archivage


def test_un_eleve_encore_inscrit_est_epargne(
    session, site_factory, annee_factory, personne_factory
):
    """Le suspendre le priverait de son compte le jour de la rentrée."""
    from backend.models import Snapshot
    from backend.services.vidange_ou import planifier_vidange

    site = site_factory("NDK")
    annee = annee_factory("2026-2027")
    p = personne_factory(
        nom="REDOUBLE", prenom="Luc", login="lredouble", site_id=site.id,
        email_constate="luc.redouble@lekreisker.fr",
    )
    session.add(Snapshot(personne_id=p.id, annee_scolaire_id=annee.id,
                         nom="REDOUBLE", prenom="Luc", classe="T_G1A"))
    session.commit()

    r = planifier_vidange(
        session,
        [
            _compte("luc.redouble@lekreisker.fr", "/3. NDK/NDK2025/T_G1A"),
            _compte("parti@lekreisker.fr", "/3. NDK/NDK2025/T_G1A"),
        ],
        ou_source="/3. NDK/NDK2025",
    )
    assert r.nb_a_archiver == 1
    assert r.mouvements[0].email == "parti@lekreisker.fr"
    assert len(r.epargnes) == 1
    assert r.epargnes[0].email == "luc.redouble@lekreisker.fr"
    assert any("encore inscrite" in a or "année en cours" in a for a in r.avertissements)


def test_compte_deja_suspendu_est_deplace_sans_re_suspension(session, site_factory):
    from backend.services.vidange_ou import planifier_vidange

    site_factory("NDK")
    r = planifier_vidange(
        session,
        [_compte("a@lekreisker.fr", "/3. NDK/NDK2025/T_G1A", suspendu=True)],
        ou_source="/3. NDK/NDK2025",
    )
    assert r.nb_deja_suspendus == 1
    assert r.mouvements[0].suspendre is False
    assert r.mouvements[0].ou_visee.startswith("/7. Sortis")


def test_site_avec_sa_propre_ou_de_sortie(session, site_factory):
    """NDE range ses partants dans son OU à elle, sans date."""
    from backend.services.vidange_ou import planifier_vidange

    nde = site_factory("NDE")
    nde.prefixe_annee_ou = "NDE"
    nde.ou_sortants = "/2. NDE/Sortie"
    session.commit()

    r = planifier_vidange(
        session,
        [_compte("a@lekreisker.fr", "/2. NDE/NDE2025/3F")],
        ou_source="/2. NDE/NDE2025",
    )
    assert r.ou_archivage == "/2. NDE/Sortie"


def test_echeance_deja_depassee_est_signalee(session, site_factory):
    from backend.services.vidange_ou import planifier_vidange

    site_factory("NDK")
    r = planifier_vidange(
        session,
        [_compte("a@lekreisker.fr", "/3. NDK/NDK2020/T_G1A")],
        ou_source="/3. NDK/NDK2020",
        aujourd_hui=date(2026, 8, 20),
    )
    assert any("dépassée" in a for a in r.avertissements)


def test_annee_indeduisible_est_refusee(session, site_factory):
    from backend.services.vidange_ou import planifier_vidange

    site_factory("NDK")
    with pytest.raises(ValueError, match="année de départ"):
        planifier_vidange(session, [], ou_source="/2. NDE/Sortie")


def test_annee_explicite_prime(session, site_factory):
    from backend.services.vidange_ou import planifier_vidange

    site_factory("NDE")
    r = planifier_vidange(
        session, [], ou_source="/2. NDE/Sortie", annee_depart=2024
    )
    assert r.date_depart == date(2024, 8, 31)


def test_eleve_dont_ladresse_du_referentiel_est_fausse_est_epargne(
    session, site_factory, annee_factory, personne_factory
):
    """Cas réel : Louis LE GALL, inscrit, sauvé de justesse.

    Charlemagne porte `louis.legall@`, son vrai compte Google est
    `louis.le.gall@`. S'en tenir à l'adresse constatée l'aurait fait
    suspendre alors qu'il fait sa rentrée ; l'adresse calculée depuis son
    nom, elle, tombe juste.
    """
    from backend.models import Snapshot
    from backend.services.vidange_ou import planifier_vidange

    site = site_factory("NDK")
    annee = annee_factory("2026-2027")
    p = personne_factory(
        nom="LE GALL", prenom="Louis", login="llegall", site_id=site.id,
        email_constate="louis.legall@lekreisker.fr",
    )
    session.add(Snapshot(personne_id=p.id, annee_scolaire_id=annee.id,
                         nom="LE GALL", prenom="Louis", classe="1_G2"))
    session.commit()

    r = planifier_vidange(
        session,
        [_compte("louis.le.gall@lekreisker.fr", "/3. NDK/NDK2025/2_8",
                 nom="LE GALL", prenom="Louis")],
        ou_source="/3. NDK/NDK2025",
    )
    assert r.nb_a_archiver == 0
    assert len(r.epargnes) == 1
    assert r.epargnes[0].apparie_par == "adresse"


def test_homonymes_ne_sont_pas_rapproches_au_hasard(
    session, site_factory, annee_factory, personne_factory
):
    """Deux personnes du même nom rendraient l'attribution arbitraire."""
    from backend.services.vidange_ou import planifier_vidange

    site = site_factory("NDK")
    annee_factory("2026-2027")
    for i in range(2):
        personne_factory(
            nom="GUILLOU", prenom="Hugo", login=f"hguillou{i}", site_id=site.id,
            id_charlemagne=8100 + i,
        )
    session.commit()

    r = planifier_vidange(
        session,
        [_compte("hugo.guillou@lekreisker.fr", "/3. NDK/NDK2025/T_G1A",
                 nom="GUILLOU", prenom="Hugo")],
        ou_source="/3. NDK/NDK2025",
    )
    # Aucun des deux n'est inscrit : le compte part, mais sans rapprochement
    assert r.nb_a_archiver == 1
    assert r.mouvements[0].statut_referentiel == "inconnu"


def test_compte_oublie_par_la_bascule_garde_sa_vraie_date(
    session, site_factory, annee_factory, personne_factory
):
    """Le cas réel : quatre comptes restés dans NDK2025 en 2025-2026.

    La branche date leur départ d'août 2025 ; le référentiel sait qu'ils
    étaient encore là un an plus tard. Retenir la date de la branche
    écourterait leur conservation de dix mois.
    """
    from backend.models import Snapshot
    from backend.services.vidange_ou import planifier_vidange

    site = site_factory("NDK")
    annee = annee_factory("2025-2026")
    annee_factory("2026-2027")  # l'année préparée : la personne n'y est plus
    p = personne_factory(
        nom="LE LAY", prenom="Leane", login="llelay", site_id=site.id,
        email_constate="leane.le.lay@lekreisker.fr",
    )
    session.add(Snapshot(personne_id=p.id, annee_scolaire_id=annee.id,
                         nom="LE LAY", prenom="Leane", classe="BTS_2"))
    session.commit()

    r = planifier_vidange(
        session,
        [
            _compte("leane.le.lay@lekreisker.fr", "/3. NDK/NDK2025"),
            _compte("parti@lekreisker.fr", "/3. NDK/NDK2025/T_G1A"),
        ],
        ou_source="/3. NDK/NDK2025",
        aujourd_hui=date(2026, 8, 20),
    )

    assert len(r.retardataires) == 1
    assert any("bascule" in a for a in r.avertissements)

    par_mail = {m.email: m for m in r.mouvements}
    tardif = par_mail["leane.le.lay@lekreisker.fr"]
    normal = par_mail["parti@lekreisker.fr"]

    assert tardif.date_echeance == date(2028, 2, 29), "18 mois après août 2026"
    assert normal.date_echeance == date(2027, 2, 28), "18 mois après août 2025"
    assert tardif.ou_visee != normal.ou_visee
    assert "29-02-2028" in tardif.ou_visee
