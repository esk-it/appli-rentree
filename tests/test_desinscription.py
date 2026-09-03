"""Retirer d'une année quelqu'un qui n'y était finalement pas.

Ingéré le 18 août, disparu de l'export de septembre : il ne s'est pas
présenté. Le référentiel ne supprime jamais personne — c'est ce qui protège
les logins — mais il ne savait pas non plus désinscrire, et dix élèves
restaient dans leur dernière classe connue, compte Google actif.
"""
from __future__ import annotations

import pytest


@pytest.fixture()
def eleve_inscrit(session, site_factory, annee_factory, personne_factory):
    from backend.models import Snapshot

    site = site_factory("NDK")
    an = annee_factory("2026-2027")
    p = personne_factory(
        type="eleve", site_id=site.id, nom="GUEGUEN", prenom="Justine",
        login="jgueguen", classe="1_G4",
    )
    session.add(Snapshot(personne_id=p.id, annee_scolaire_id=an.id,
                         nom=p.nom, prenom=p.prenom, classe="1_G4"))
    session.commit()
    return p, an, site


def test_le_snapshot_de_lannee_est_supprime(session, eleve_inscrit):
    from backend.models import Snapshot
    from backend.services.desinscription import retirer_de_lannee

    p, an, _ = eleve_inscrit
    r = retirer_de_lannee(session, [p.id], annee_id=an.id, mode="reel")

    assert r.nb_retires == 1
    assert r.retires[0].classe_avant == "1_G4"
    assert session.query(Snapshot).filter_by(
        personne_id=p.id, annee_scolaire_id=an.id).count() == 0


def test_la_classe_courante_tombe_avec_l_inscription(session, eleve_inscrit):
    """C'est elle qui gonflait l'effectif de 1_G4 : 34 au lieu de 33."""
    from backend.services.desinscription import retirer_de_lannee

    p, an, _ = eleve_inscrit
    retirer_de_lannee(session, [p.id], annee_id=an.id, mode="reel")
    session.refresh(p)
    assert p.classe is None


def test_la_personne_et_son_login_survivent(session, eleve_inscrit):
    """Supprimer la personne rendrait son login réattribuable, et le
    prochain à le recevoir écraserait un compte existant."""
    from backend.models import Personne
    from backend.services.desinscription import retirer_de_lannee

    p, an, _ = eleve_inscrit
    pid, login = p.id, p.login
    retirer_de_lannee(session, [p.id], annee_id=an.id, mode="reel")

    encore = session.query(Personne).filter_by(id=pid).one_or_none()
    assert encore is not None
    assert encore.login == login
    assert encore.site_id is not None, "le site dit d'où elle vient"


def test_les_autres_annees_ne_bougent_pas(
    session, eleve_inscrit, annee_factory
):
    from backend.models import Snapshot
    from backend.services.desinscription import retirer_de_lannee

    p, an, _ = eleve_inscrit
    precedente = annee_factory("2025-2026")
    session.add(Snapshot(personne_id=p.id, annee_scolaire_id=precedente.id,
                         nom=p.nom, prenom=p.prenom, classe="2_5"))
    session.commit()

    retirer_de_lannee(session, [p.id], annee_id=an.id, mode="reel")
    restants = session.query(Snapshot).filter_by(personne_id=p.id).all()
    assert [s.annee_scolaire_id for s in restants] == [precedente.id]


def test_la_simulation_n_ecrit_rien(session, eleve_inscrit):
    from backend.models import Snapshot
    from backend.services.desinscription import retirer_de_lannee

    p, an, _ = eleve_inscrit
    r = retirer_de_lannee(session, [p.id], annee_id=an.id, mode="simulation")
    assert r.nb_retires == 1
    session.refresh(p)
    assert p.classe == "1_G4"
    assert session.query(Snapshot).filter_by(
        personne_id=p.id, annee_scolaire_id=an.id).count() == 1


def test_quelqu_un_qui_n_etait_pas_inscrit_est_signale_pas_compte(
    session, site_factory, annee_factory, personne_factory
):
    from backend.services.desinscription import retirer_de_lannee

    site = site_factory("NDK")
    an = annee_factory("2026-2027")
    p = personne_factory(type="eleve", site_id=site.id, nom="X", prenom="Y")
    r = retirer_de_lannee(session, [p.id], annee_id=an.id, mode="reel")
    assert r.nb_retires == 0
    assert "n'a pas de snapshot" in r.ignores[0]


def test_une_annee_inconnue_est_refusee(session, eleve_inscrit):
    from backend.services.desinscription import retirer_de_lannee

    p, _, _ = eleve_inscrit
    with pytest.raises(ValueError, match="Année introuvable"):
        retirer_de_lannee(session, [p.id], annee_id=9999, mode="reel")


def test_une_fois_retiree_la_reconciliation_la_voit_sortante(
    session, eleve_inscrit, annee_factory
):
    """C'est tout l'intérêt : le chemin normal du programme reprend la
    main, et « Traiter les sortants » met son compte en quarantaine."""
    from backend.models import Snapshot
    from backend.services.desinscription import retirer_de_lannee
    from backend.services.reconciliation import reconcilier

    p, cible, _ = eleve_inscrit
    source = annee_factory("2025-2026")
    session.add(Snapshot(personne_id=p.id, annee_scolaire_id=source.id,
                         nom=p.nom, prenom=p.prenom, classe="2_5"))
    session.commit()

    avant = reconcilier(session, source.id, cible.id, type_personne="eleve")
    assert not any(e.personne_id == p.id for e in avant.sortants), (
        "tant qu'elle a un snapshot cible, elle passe pour présente"
    )

    retirer_de_lannee(session, [p.id], annee_id=cible.id, mode="reel")
    apres = reconcilier(session, source.id, cible.id, type_personne="eleve")
    assert any(e.personne_id == p.id for e in apres.sortants)
