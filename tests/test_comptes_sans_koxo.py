"""Créer des comptes Google pour un site qui n'a pas de KoXo.

NDE n'a pas de serveur KoXo : personne ne fabrique les mots de passe de ses
élèves, et personne ne les imprime. Le programme doit donc les fabriquer —
et surtout ne jamais les perdre, puisqu'ils n'existent nulle part ailleurs.
"""
from __future__ import annotations

import csv
import io

import pytest

MAITRE = "sardine-clavier-molybdene-1789"


@pytest.fixture()
def snap_factory(session):
    from backend.models import Snapshot

    def _creer(personne_id, annee_id, classe=None):
        s = Snapshot(personne_id=personne_id, annee_scolaire_id=annee_id,
                     nom="X", prenom="Y", classe=classe)
        session.add(s)
        session.commit()
        return s

    return _creer


@pytest.fixture()
def tc_factory(session):
    from backend.models import TableCorrespondance

    def _creer(site_id, code):
        tc = TableCorrespondance(
            site_id=site_id, classe_charlemagne_long=f"CLASSE {code}",
            classe_code_court=code,
            ou_pre_rentree="/2. NDE/NDE2027",
            ou_definitive=f"/2. NDE/NDE2027/{code}",
            groupe_google=f"{code.lower()}@lekreisker.fr",
        )
        session.add(tc)
        session.commit()
        return tc

    return _creer


@pytest.fixture()
def nde(session, site_factory, annee_factory, personne_factory, snap_factory,
        tc_factory):
    site = site_factory("NDE")
    an_prec = annee_factory("2025-2026")
    an_cour = annee_factory("2026-2027")
    tc_factory(site.id, "6B")
    for i in range(3):
        p = personne_factory(site_id=site.id, login=f"eleve{i}",
                             id_charlemagne=700 + i)
        snap_factory(p.id, an_cour.id, classe="6B")
    return site, an_prec, an_cour


def _lire(contenu: bytes) -> list[dict]:
    return list(csv.DictReader(io.StringIO(contenu.decode("utf-8-sig"))))


# ---------------------------------------------------------------------------
# Le refus qui compte
# ---------------------------------------------------------------------------


def test_sans_coffre_ouvert_la_generation_est_refusee(session, nde):
    """Un mot de passe fabriqué et non rangé est un mot de passe perdu."""
    from backend.services.coffre import chercher, initialiser
    from backend.services.comptes_sans_koxo import (
        GenerationImpossible,
        preparer_comptes,
    )

    site, an_prec, an_cour = nde

    with pytest.raises(GenerationImpossible, match="coffre"):
        preparer_comptes(
            session, b"", site_id=site.id, annee_cible_id=an_cour.id,
            annee_source_id=an_prec.id,
        )


# ---------------------------------------------------------------------------
# La génération
# ---------------------------------------------------------------------------


def test_le_csv_google_sort_avec_ses_mots_de_passe(session, nde):
    from backend.services.coffre import chercher, initialiser
    from backend.services.comptes_sans_koxo import (
        GenerationImpossible,
        preparer_comptes,
    )

    site, an_prec, an_cour = nde
    cle = initialiser(session, MAITRE)

    csv_google, _, rapport = preparer_comptes(
        session, cle, site_id=site.id, annee_cible_id=an_cour.id,
        annee_source_id=an_prec.id,
    )
    session.commit()

    lignes = _lire(csv_google)
    assert len(lignes) == 3
    assert rapport.nb_generes == 3
    for l in lignes:
        mdp = l["Password [Required]"]
        assert len(mdp) == 8 and mdp[0].isupper() and mdp[6:].isdigit()


def test_chaque_mot_de_passe_est_range_au_coffre(session, nde):
    """C'est la garantie du module : générer et ranger sont le même geste."""
    from backend.services.coffre import chercher, initialiser
    from backend.services.comptes_sans_koxo import (
        GenerationImpossible,
        preparer_comptes,
    )

    site, an_prec, an_cour = nde
    cle = initialiser(session, MAITRE)

    csv_google, _, _ = preparer_comptes(
        session, cle, site_id=site.id, annee_cible_id=an_cour.id,
        annee_source_id=an_prec.id,
    )
    session.commit()

    # La recherche porte sur l'identite, pas sur l'adresse : la partie
    # locale vaut `prenom.nom` la ou l'identifiant vaut `initiale+nom`.
    from backend.models import Personne

    for l in _lire(csv_google):
        adresse = l["Email Address [Required]"].lower()
        personne = next(
            p for p in session.query(Personne).all()
            if (p.email or "").lower() == adresse
        )
        trouves = chercher(session, cle, personne.login)
        assert [t.mot_de_passe for t in trouves] == [l["Password [Required]"]]


def test_le_coffre_marque_ces_secrets_comme_generes(session, nde):
    """Un mot de passe généré n'existe nulle part ailleurs : ça se signale."""
    from backend.services.coffre import chercher, initialiser
    from backend.services.comptes_sans_koxo import (
        GenerationImpossible,
        preparer_comptes,
    )

    from backend.models import SecretConserve

    site, an_prec, an_cour = nde
    cle = initialiser(session, MAITRE)
    preparer_comptes(session, cle, site_id=site.id, annee_cible_id=an_cour.id,
                     annee_source_id=an_prec.id)
    session.commit()

    secrets = session.query(SecretConserve).all()
    assert secrets
    assert all(s.origine == "genere" and s.site == "NDE" for s in secrets)


def test_relancer_ne_change_pas_les_mots_de_passe_distribues(session, nde):
    """Sinon la deuxième génération invaliderait les fiches déjà remises."""
    from backend.services.coffre import chercher, initialiser
    from backend.services.comptes_sans_koxo import (
        GenerationImpossible,
        preparer_comptes,
    )

    site, an_prec, an_cour = nde
    cle = initialiser(session, MAITRE)

    premier, _, r1 = preparer_comptes(
        session, cle, site_id=site.id, annee_cible_id=an_cour.id,
        annee_source_id=an_prec.id,
    )
    session.commit()
    second, _, r2 = preparer_comptes(
        session, cle, site_id=site.id, annee_cible_id=an_cour.id,
        annee_source_id=an_prec.id,
    )
    session.commit()

    assert r1.nb_generes == 3 and r1.nb_deja_au_coffre == 0
    assert r2.nb_generes == 0 and r2.nb_deja_au_coffre == 3

    avant = {l["Email Address [Required]"]: l["Password [Required]"] for l in _lire(premier)}
    apres = {l["Email Address [Required]"]: l["Password [Required]"] for l in _lire(second)}
    assert avant == apres


# ---------------------------------------------------------------------------
# Les fiches à imprimer
# ---------------------------------------------------------------------------


def test_les_fiches_portent_classe_identite_et_mot_de_passe(session, nde):
    """C'est le seul endroit où l'élève lira son mot de passe."""
    from backend.services.coffre import chercher, initialiser
    from backend.services.comptes_sans_koxo import (
        GenerationImpossible,
        preparer_comptes,
    )

    site, an_prec, an_cour = nde
    cle = initialiser(session, MAITRE)

    csv_google, fiches, _ = preparer_comptes(
        session, cle, site_id=site.id, annee_cible_id=an_cour.id,
        annee_source_id=an_prec.id,
    )
    session.commit()

    lignes = _lire(fiches)
    assert len(lignes) == 3
    assert set(lignes[0]) == {"Classe", "Nom", "Prénom", "Adresse", "Mot de passe"}
    assert all(l["Classe"] == "6B" for l in lignes)

    # Les deux fichiers disent la même chose : une fiche qui ne
    # correspondrait pas au compte créé serait pire que pas de fiche.
    par_adresse = {l["Email Address [Required]"]: l["Password [Required]"]
                   for l in _lire(csv_google)}
    for l in lignes:
        assert par_adresse[l["Adresse"]] == l["Mot de passe"]


def test_les_fiches_sont_rangees_par_classe(session, site_factory,
                                            annee_factory, personne_factory,
                                            snap_factory, tc_factory):
    """On les imprime pour les distribuer classe par classe."""
    from backend.services.coffre import chercher, initialiser
    from backend.services.comptes_sans_koxo import (
        GenerationImpossible,
        preparer_comptes,
    )

    site = site_factory("NDE")
    an_prec = annee_factory("2025-2026")
    an_cour = annee_factory("2026-2027")
    for code in ("6V", "6B"):
        tc_factory(site.id, code)
    for i, code in enumerate(("6V", "6B", "6V")):
        p = personne_factory(site_id=site.id, login=f"e{i}", id_charlemagne=800 + i)
        snap_factory(p.id, an_cour.id, classe=code)

    cle = initialiser(session, MAITRE)
    _, fiches, _ = preparer_comptes(
        session, cle, site_id=site.id, annee_cible_id=an_cour.id,
        annee_source_id=an_prec.id,
    )
    session.commit()

    classes = [l["Classe"] for l in _lire(fiches)]
    assert classes == sorted(classes)


def test_un_site_sans_eleve_ne_produit_rien_et_le_dit(session, site_factory,
                                                      annee_factory):
    from backend.services.coffre import chercher, initialiser
    from backend.services.comptes_sans_koxo import (
        GenerationImpossible,
        preparer_comptes,
    )

    site = site_factory("NDE")
    an_cour = annee_factory("2026-2027")
    cle = initialiser(session, MAITRE)

    _, _, rapport = preparer_comptes(
        session, cle, site_id=site.id, annee_cible_id=an_cour.id,
        categorie="tous",
    )
    assert rapport.nb_generes == 0
    assert any("Aucune ligne" in a for a in rapport.avertissements)
