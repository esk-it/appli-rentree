"""Tests de l'enquête sur une personne.

Ce qui compte ici n'est pas ce que l'enquête trouve, mais ce qu'elle refuse
de conclure : trois sources sur cinq n'ont pas d'API, et un écran qui les
laisserait vides ferait prendre une absence de regard pour une absence
d'écart. C'est ce silence-là qui a laissé quarante-quatre élèves dans la
mauvaise classe pendant deux semaines.
"""
from __future__ import annotations

import pytest


@pytest.fixture()
def contexte(session, site_factory, annee_factory, personne_factory):
    from backend.models import Snapshot, TableCorrespondance

    site = site_factory("NDK")
    annee = annee_factory("2026-2027")
    session.add(
        TableCorrespondance(
            site_id=site.id,
            classe_charlemagne_long="SECONDE 5",
            classe_code_court="2_5",
            ou_pre_rentree="/3. NDK/NDK2027",
            ou_definitive="/3. NDK/NDK2027/2_5",
        )
    )
    session.commit()

    def _eleve(nom="DUPONT", prenom="Jean", classe="2_5", **kw):
        p = personne_factory(
            nom=nom, prenom=prenom, site_id=site.id,
            email_constate=kw.pop("email", "jean.dupont@lekreisker.fr"), **kw,
        )
        session.add(
            Snapshot(
                personne_id=p.id, annee_scolaire_id=annee.id,
                nom=nom, prenom=prenom, classe=classe,
            )
        )
        session.commit()
        return p

    return {"site": site, "annee": annee, "eleve": _eleve}


def _dire(enquete, source):
    return next(d for d in enquete.dires if d.source == source)


def test_le_referentiel_dit_la_classe_et_lou_attendue(session, contexte):
    from backend.services.enquete_personne import enqueter

    p = contexte["eleve"]()
    e = enqueter(session, p.id, annee_id=contexte["annee"].id)

    r = _dire(e, "referentiel")
    assert r.consultee
    assert r.valeurs["classe"] == "2_5"
    assert r.valeurs["ou_attendue"] == "/3. NDK/NDK2027/2_5"
    assert e.libelle == "DUPONT Jean"


def test_une_source_non_interrogee_le_dit_au_lieu_de_se_taire(session, contexte):
    """Une case vide se lirait comme « rien à signaler »."""
    from backend.services.enquete_personne import enqueter

    p = contexte["eleve"]()
    e = enqueter(session, p.id)

    for source in ("charlemagne", "koxo", "ts1000"):
        d = _dire(e, source)
        assert not d.consultee
        assert d.motif, f"{source} ne dit pas pourquoi il n'a pas parlé"
        assert "écran" in d.motif

    google = _dire(e, "google")
    assert not google.consultee
    assert google.motif


def test_tout_concorde_exige_deux_sources_consultees(session, contexte):
    """Sans Google, une seule source a parlé : on ne conclut pas."""
    from backend.services.enquete_personne import enqueter

    p = contexte["eleve"]()
    # Le coffre répond toujours, mais il ne dit rien de comparable : deux
    # sources qui ne se recoupent pas ne valident rien de plus qu'une.
    e = enqueter(session, p.id)
    assert e.divergences == []
    assert "google" not in e.sources_consultees


def test_une_ou_differente_de_la_table_est_une_divergence(session, contexte):
    from backend.services.enquete_personne import enqueter

    p = contexte["eleve"]()
    e = enqueter(
        session, p.id, annee_id=contexte["annee"].id,
        etat_google={
            "existe": True, "ou": "/3. NDK/NDK2026/2_5",
            "suspendu": False, "derniere_connexion": "2026-09-16T08:00:00Z",
        },
    )

    assert len(e.divergences) == 1
    d = e.divergences[0]
    assert d.quoi == "Unité d'organisation"
    assert d.valeurs == ("/3. NDK/NDK2027/2_5", "/3. NDK/NDK2026/2_5")
    assert not e.tout_concorde


def test_une_ou_conforme_ne_produit_aucune_divergence(session, contexte):
    from backend.services.enquete_personne import enqueter

    p = contexte["eleve"]()
    e = enqueter(
        session, p.id, annee_id=contexte["annee"].id,
        etat_google={
            "existe": True, "ou": "/3. NDK/NDK2027/2_5",
            "suspendu": False, "derniere_connexion": "2026-09-16T08:00:00Z",
        },
        groupes_google=["2nde-5@lekreisker.fr"],
    )

    assert e.divergences == []
    assert e.tout_concorde
    assert _dire(e, "google").valeurs["groupes"] == "2nde-5@lekreisker.fr"


def test_un_compte_suspendu_pour_un_inscrit_est_bloquant(session, contexte):
    from backend.services.enquete_personne import enqueter

    p = contexte["eleve"]()
    e = enqueter(
        session, p.id, annee_id=contexte["annee"].id,
        etat_google={
            "existe": True, "ou": "/3. NDK/NDK2027/2_5",
            "suspendu": True, "derniere_connexion": "2026-09-16T08:00:00Z",
        },
    )

    assert [d.gravite for d in e.divergences] == ["bloquant"]
    assert "suspendu" in e.divergences[0].quoi


def test_un_compte_absent_se_dit_sans_inventer_de_divergence(session, contexte):
    """Pas de compte n'est pas un écart d'unité : c'est un manque, et il se
    règle autrement."""
    from backend.services.enquete_personne import enqueter

    p = contexte["eleve"]()
    e = enqueter(
        session, p.id, annee_id=contexte["annee"].id,
        etat_google={"existe": False},
    )

    g = _dire(e, "google")
    assert g.consultee
    assert g.valeurs["compte"] is None
    assert "Aucun compte" in g.motif
    assert e.divergences == []


def test_le_coffre_dit_si_le_mot_de_passe_est_connu(session, contexte):
    from backend.models import SecretConserve
    from backend.services.enquete_personne import enqueter

    p = contexte["eleve"]()
    session.add(
        SecretConserve(
            personne_id=p.id, cible="koxo", site="NDK",
            nonce=b"0" * 12, chiffre=b"x", origine="koxo",
        )
    )
    session.commit()

    c = _dire(enqueter(session, p.id), "coffre")
    assert c.valeurs["mot_de_passe_connu"] == "oui"


def test_une_adresse_seulement_calculee_est_signalee(session, contexte):
    """Écrire dessus déplacerait l'homonyme : la fiche doit le montrer."""
    from backend.services.enquete_personne import enqueter

    p = contexte["eleve"](email="")
    e = enqueter(session, p.id)
    assert e.adresse_constatee is False


def test_une_personne_inconnue_se_refuse(session):
    from backend.services.enquete_personne import enqueter

    with pytest.raises(ValueError, match="introuvable"):
        enqueter(session, 999999)


def test_un_compte_jamais_ouvert_est_signale(session, contexte):
    """Bien rangé et jamais utilisé : la personne en a sûrement un autre.

    C'est ainsi qu'on a découvert en septembre 2026 que trois élèves montés
    de NDE travaillaient encore sur leur ancien compte — lequel allait
    partir en unité de sortie.
    """
    from backend.services.enquete_personne import enqueter

    p = contexte["eleve"]()
    e = enqueter(
        session, p.id, annee_id=contexte["annee"].id,
        etat_google={
            "existe": True, "ou": "/3. NDK/NDK2027/2_5",
            "suspendu": False, "derniere_connexion": "1970-01-01T00:00:00Z",
        },
    )

    assert [d.quoi for d in e.divergences] == ["Compte jamais ouvert"]
    assert e.divergences[0].gravite == "information"
