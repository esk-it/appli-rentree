"""Tests des écarts entre adresse enregistrée et compte Google réel."""
from __future__ import annotations

import pytest


def _u(email, nom, prenom, ou="/3. NDK/NDK2026/2_1"):
    return {"email": email, "ou": ou, "suspendu": False,
            "nom": nom, "prenom": prenom, "derniere_connexion": None}


@pytest.fixture()
def inscrit(session, site_factory, annee_factory, personne_factory):
    from backend.models import Snapshot

    site = site_factory("NDK")
    annee = annee_factory("2026-2027")

    def _creer(nom, prenom, login, email):
        p = personne_factory(nom=nom, prenom=prenom, login=login,
                             site_id=site.id, email_constate=email)
        session.add(Snapshot(personne_id=p.id, annee_scolaire_id=annee.id,
                             nom=nom, prenom=prenom, classe="2_1"))
        session.commit()
        return p

    return _creer


def test_adresse_correcte_nest_pas_signalee(session, inscrit):
    from backend.services.adresses_divergentes import detecter_divergences

    inscrit("DUPONT", "Jean", "jdupont", "jean.dupont@lekreisker.fr")
    r = detecter_divergences(session, [_u("jean.dupont@lekreisker.fr", "DUPONT", "Jean")])
    assert r.divergences == []


def test_ecart_resolvable_par_le_nom(session, inscrit):
    """Cas réel : louis.legall@ enregistré, louis.le.gall@ dans Google."""
    from backend.services.adresses_divergentes import detecter_divergences

    inscrit("LE GALL", "Louis", "llegall", "louis.legall@lekreisker.fr")
    r = detecter_divergences(
        session, [_u("louis.le.gall@lekreisker.fr", "LE GALL", "Louis")]
    )
    assert r.nb_resolvables == 1
    d = r.divergences[0]
    assert d.adresse_enregistree == "louis.legall@lekreisker.fr"
    assert d.adresse_google == "louis.le.gall@lekreisker.fr"


def test_aucun_compte_a_ce_nom(session, inscrit):
    """Un nouvel élève : son compte reste à créer, ce n'est pas un écart."""
    from backend.services.adresses_divergentes import detecter_divergences

    inscrit("NEUF", "Ana", "aneuf", "ana.neuf@lekreisker.fr")
    r = detecter_divergences(session, [_u("autre@lekreisker.fr", "AUTRE", "Bob")])
    assert r.nb_resolvables == 0
    assert "reste à créer" in r.divergences[0].motif


def test_homonymes_google_ne_sont_pas_tranches(session, inscrit):
    from backend.services.adresses_divergentes import detecter_divergences

    inscrit("GUILLOU", "Hugo", "hguillou", "hugo.guillou0@lekreisker.fr")
    r = detecter_divergences(
        session,
        [
            _u("hugo.guillou@lekreisker.fr", "GUILLOU", "Hugo"),
            _u("hugo.guillou2@lekreisker.fr", "GUILLOU", "Hugo"),
        ],
    )
    assert r.nb_resolvables == 0
    assert "plusieurs comptes" in r.divergences[0].motif


def test_homonymes_du_referentiel_ne_sont_pas_tranches(session, inscrit):
    """Un seul compte Google, mais deux personnes du même nom : on s'abstient."""
    from backend.services.adresses_divergentes import detecter_divergences

    inscrit("GUILLOU", "Hugo", "hguillou1", "hugo.guillou1@lekreisker.fr")
    inscrit("GUILLOU", "Hugo", "hguillou2", "hugo.guillou2@lekreisker.fr")
    r = detecter_divergences(
        session, [_u("hugo.guillou@lekreisker.fr", "GUILLOU", "Hugo")]
    )
    assert r.nb_resolvables == 0


def test_correction_aligne_sur_google(session, inscrit):
    """Ce que Google contient fait foi : c'est là que l'élève se connecte."""
    from backend.models import Personne
    from backend.services.adresses_divergentes import (
        appliquer_corrections,
        detecter_divergences,
    )

    p = inscrit("LE GALL", "Louis", "llegall", "louis.legall@lekreisker.fr")
    r = detecter_divergences(
        session, [_u("louis.le.gall@lekreisker.fr", "LE GALL", "Louis")]
    )
    assert appliquer_corrections(session, r, mode="reel") == 1
    assert session.get(Personne, p.id).email_constate == "louis.le.gall@lekreisker.fr"


def test_simulation_ne_corrige_rien(session, inscrit):
    from backend.models import Personne
    from backend.services.adresses_divergentes import (
        appliquer_corrections,
        detecter_divergences,
    )

    p = inscrit("LE GALL", "Louis", "llegall", "louis.legall@lekreisker.fr")
    r = detecter_divergences(
        session, [_u("louis.le.gall@lekreisker.fr", "LE GALL", "Louis")]
    )
    appliquer_corrections(session, r, mode="simulation")
    assert session.get(Personne, p.id).email_constate == "louis.legall@lekreisker.fr"


def test_les_ambigus_ne_sont_jamais_corriges(session, inscrit):
    from backend.services.adresses_divergentes import (
        appliquer_corrections,
        detecter_divergences,
    )

    inscrit("GUILLOU", "Hugo", "hguillou", "hugo.guillou0@lekreisker.fr")
    r = detecter_divergences(
        session,
        [
            _u("hugo.guillou@lekreisker.fr", "GUILLOU", "Hugo"),
            _u("hugo.guillou2@lekreisker.fr", "GUILLOU", "Hugo"),
        ],
    )
    assert appliquer_corrections(session, r, mode="reel") == 0


def test_un_compte_aux_champs_intervertis_est_retrouve(session, personne_factory):
    """Cas réel : 172 comptes d'un site portent nom et prénom à l'envers.

    Ils ont été créés ainsi. Le client lit pourtant `familyName` et
    `givenName` correctement — c'est la donnée qui est inversée, et aucun
    rapprochement par nom ne les retrouvait.
    """
    from backend.services.adresses_divergentes import detecter_divergences

    p = personne_factory(nom="SAILLOUR", prenom="Aaron")
    p.email_constate = "aaron.saillour@ndecleder.fr"
    session.commit()

    comptes = [
        # Champs intervertis, comme dans l'annuaire réel.
        {"email": "aaron.saillour@lekreisker.fr", "nom": "Aaron",
         "prenom": "SAILLOUR", "ou": "/2. NDE/NDE2026/4J"},
    ]
    r = detecter_divergences(session, comptes)
    assert len(r.divergences) == 1
    d = r.divergences[0]
    assert d.resolvable
    assert d.adresse_google == "aaron.saillour@lekreisker.fr"
    assert "intervertis" in d.motif, "le motif dit comment il a été retrouvé"


def test_lordre_inverse_ne_fabrique_pas_de_faux_rapprochement(
    session, personne_factory
):
    """Deux comptes que les deux ordres désignent restent ambigus."""
    from backend.services.adresses_divergentes import detecter_divergences

    p = personne_factory(nom="MARTIN", prenom="PAUL")
    p.email_constate = "introuvable@lekreisker.fr"
    session.commit()

    comptes = [
        {"email": "paul.martin@lekreisker.fr", "nom": "MARTIN", "prenom": "PAUL"},
        {"email": "martin.paul@lekreisker.fr", "nom": "PAUL", "prenom": "MARTIN"},
    ]
    r = detecter_divergences(session, comptes)
    assert r.divergences[0].resolvable is False
    assert "plusieurs comptes possibles" in r.divergences[0].motif


def test_un_nom_egal_au_prenom_nest_pas_indexe_deux_fois(session, personne_factory):
    """« MARTIN Martin » ne doit pas se dédoubler et devenir ambigu."""
    from backend.services.adresses_divergentes import detecter_divergences

    p = personne_factory(nom="MARTIN", prenom="MARTIN")
    p.email_constate = "introuvable@lekreisker.fr"
    session.commit()

    comptes = [
        {"email": "martin.martin@lekreisker.fr", "nom": "MARTIN", "prenom": "MARTIN"},
    ]
    r = detecter_divergences(session, comptes)
    assert r.divergences[0].resolvable is True


# ---------------------------------------------------------------------------
# Les alias
# ---------------------------------------------------------------------------


def test_une_adresse_dalias_ne_diverge_pas(session, inscrit):
    """Un compte répond à ses alias : l'adresse existe, rien à corriger.

    Le contrôle ne regardait que l'adresse principale. Une adresse d'alias
    enregistrée au référentiel paraissait donc introuvable, et l'écran la
    signalait sans qu'aucune correction soit possible — le compte est là.
    """
    from backend.services.adresses_divergentes import detecter_divergences

    inscrit("MARTIN", "Paul", "pmartin", "p.martin@lekreisker.fr")
    compte = _u("paul.martin@lekreisker.fr", "MARTIN", "Paul")
    compte["alias"] = ["p.martin@lekreisker.fr"]

    r = detecter_divergences(session, [compte])
    assert r.divergences == [], "l'alias désigne bien ce compte"


def test_un_alias_dun_autre_compte_ne_couvre_pas_lecart(session, inscrit):
    """Reconnaître les alias ne doit pas rendre le contrôle aveugle."""
    from backend.services.adresses_divergentes import detecter_divergences

    inscrit("LE GALL", "Louis", "llegall", "louis.legall@lekreisker.fr")
    autre = _u("paul.martin@lekreisker.fr", "MARTIN", "Paul")
    autre["alias"] = ["p.martin@lekreisker.fr"]
    vrai = _u("louis.le.gall@lekreisker.fr", "LE GALL", "Louis")

    r = detecter_divergences(session, [autre, vrai])
    assert r.nb_resolvables == 1
    assert r.divergences[0].adresse_google == "louis.le.gall@lekreisker.fr"


def test_la_casse_dun_alias_est_ignoree(session, inscrit):
    from backend.services.adresses_divergentes import detecter_divergences

    inscrit("MARTIN", "Paul", "pmartin", "p.martin@lekreisker.fr")
    compte = _u("paul.martin@lekreisker.fr", "MARTIN", "Paul")
    compte["alias"] = ["P.Martin@LeKreisker.fr"]

    assert detecter_divergences(session, [compte]).divergences == []


def test_un_compte_sans_alias_reste_lu_normalement(session, inscrit):
    """La clé peut être absente : les comptes n'ont pas tous des alias."""
    from backend.services.adresses_divergentes import detecter_divergences

    inscrit("DUPONT", "Jean", "jdupont", "jean.dupont@lekreisker.fr")
    r = detecter_divergences(
        session, [_u("jean.dupont@lekreisker.fr", "DUPONT", "Jean")]
    )
    assert r.divergences == []
