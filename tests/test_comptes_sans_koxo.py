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


def test_les_etiquettes_portent_identite_identifiant_et_mot_de_passe(session, nde):
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

    page = fiches.decode("utf-8")
    assert page.count('class="etiquette"') == 3
    assert "Elèves / 6B" in page

    # Les deux fichiers disent la même chose : une étiquette qui ne
    # correspondrait pas au compte créé serait pire que pas d'étiquette.
    for mdp in (l["Password [Required]"] for l in _lire(csv_google)):
        assert mdp in page


def test_une_planche_par_classe(session, site_factory, annee_factory,
                                personne_factory, snap_factory, tc_factory):
    """Mélanger deux classes obligerait à découper puis retrier."""
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

    page = fiches.decode("utf-8")
    assert page.count('class="planche"') == 2, "une planche par classe"
    assert page.count('class="etiquette"') == 3
    # 6V vient après 6B : les planches sont dans l'ordre des classes.
    assert page.index("Elèves / 6B") < page.index("Elèves / 6V")


def test_un_site_sans_eleve_ne_produit_rien_et_le_dit(session, site_factory,
                                                      annee_factory):
    """Refuser, plutôt que rendre deux fichiers vides.

    L'ancienne version renvoyait un CSV et une planche vides avec un
    avertissement. En pratique on enregistre les deux fichiers, on les
    ouvre, et on cherche ce qui a raté — l'avertissement passe inaperçu
    entre deux boîtes de dialogue d'enregistrement.
    """
    from backend.services.coffre import initialiser
    from backend.services.comptes_sans_koxo import (
        GenerationImpossible,
        preparer_comptes,
    )

    site = site_factory("NDE")
    an_cour = annee_factory("2026-2027")
    cle = initialiser(session, MAITRE)

    with pytest.raises(GenerationImpossible, match="Aucun compte à fabriquer"):
        preparer_comptes(
            session, cle, site_id=site.id, annee_cible_id=an_cour.id,
            categorie="tous",
        )


def test_la_planche_reprend_les_cotes_relevees_chez_koxo(session):
    """Un élève de NDE doit recevoir la même étiquette que celui de NDK.

    Les cotes viennent d'un PDF d'étiquettes produit par KoXo. Les
    gouttières, elles, ne se voyaient pas sur une étiquette seule : il a
    fallu une planche complète pour relever le pas d'une carte à l'autre —
    187.2 pt en largeur pour une carte de 173.55, 132.2 en hauteur pour
    125.34.
    """
    from backend.services.comptes_sans_koxo import (
        CARTE_H,
        CARTE_L,
        COLONNES,
        GOUTTIERE_H,
        GOUTTIERE_V,
        fiches_html,
    )

    assert (CARTE_L, CARTE_H) == (173.55, 125.34)
    assert round(GOUTTIERE_H, 2) == 13.65
    assert round(GOUTTIERE_V, 2) == 6.86
    assert COLONNES == 3

    page = fiches_html(
        [{"nom": "CORVEZ", "prenom": "Noë", "classe": "6B",
          "groupe": "Elèves / 6B", "login": "ncorvez",
          "mot_de_passe": "Vikuge90"}],
        organisation="OGEC PAUL AURELIEN",
        annee="2026-2027",
    ).decode("utf-8")

    assert "gap: 6.86pt 13.65pt" in page
    assert "size: A4" in page
    for attendu in ("OGEC PAUL AURELIEN", "Noë CORVEZ", "Elèves / 6B",
                    "ncorvez", "Vikuge90", "Année 2026-2027"):
        assert attendu in page, attendu


def test_une_etiquette_ne_se_coupe_pas_entre_deux_pages(session):
    """Coupée en deux, elle serait inutilisable."""
    from backend.services.comptes_sans_koxo import fiches_html

    page = fiches_html(
        [{"nom": "X", "prenom": "Y", "classe": "6B", "groupe": "Elèves / 6B",
          "login": "x", "mot_de_passe": "Z"}],
        organisation="O", annee="2026-2027",
    ).decode("utf-8")
    assert "break-inside: avoid" in page


def test_les_fonds_sont_imposes_a_limpression(session):
    """Sans cela, la planche sort en noir et blanc.

    Les navigateurs suppriment les fonds à l'impression pour économiser
    l'encre. Sur une étiquette, le bandeau bleu et le fond bleu pâle sont
    l'essentiel de la présentation — elle ne ressemblerait plus à celles
    que KoXo produit pour les deux autres sites.
    """
    from backend.services.comptes_sans_koxo import fiches_html

    page = fiches_html(
        [{"nom": "X", "prenom": "Y", "classe": "6B", "groupe": "Elèves / 6B",
          "login": "x", "mot_de_passe": "Z"}],
        organisation="O", annee="2026-2027",
    ).decode("utf-8")

    assert page.count("print-color-adjust: exact") >= 3
    assert "-webkit-print-color-adjust: exact" in page
    # Le fond gris de l'écran, lui, ne doit pas partir à l'impression.
    assert "@media print" in page


def test_le_bandeau_se_reduit_pour_un_nom_long(session):
    """Tronquer un nom d'organisation le rendrait méconnaissable.

    « OGEC PAUL AURELIEN » tient tout juste à 11.91 pt, la taille de KoXo.
    « OGEC NOTRE DAME D ESPERANCE » en fait neuf de plus et débordait.
    """
    from backend.services.comptes_sans_koxo import fiches_html

    e = [{"nom": "X", "prenom": "Y", "classe": "6B", "groupe": "Elèves / 6B",
          "login": "x", "mot_de_passe": "Z"}]

    court = fiches_html(e, organisation="OGEC PAUL AURELIEN",
                        annee="2026-2027").decode("utf-8")
    long = fiches_html(e, organisation="OGEC NOTRE DAME D ESPERANCE",
                       annee="2026-2027").decode("utf-8")

    assert "font-size: 11.91pt" in court
    assert "font-size: 7.94pt" in long
    # Le nom entier figure dans les deux : on réduit, on ne coupe pas.
    assert "OGEC NOTRE DAME D ESPERANCE" in long


def test_letiquette_porte_le_logo_du_service(session):
    """L'élève de NDE n'a que ce compte : autant dire lequel."""
    from backend.services.comptes_sans_koxo import fiches_html

    page = fiches_html(
        [{"nom": "X", "prenom": "Y", "classe": "6B", "groupe": "Elèves / 6B",
          "login": "x", "mot_de_passe": "Z"}],
        organisation="O", annee="2026-2027",
    ).decode("utf-8")

    assert 'aria-label="Google"' in page
    # Dessiné, pas chargé : le fichier doit s'imprimer sans réseau.
    assert "<svg" in page and "http" not in page.split("<svg")[1].split("</svg>")[0]
    for couleur in ("#4285F4", "#34A853", "#FBBC05", "#EA4335"):
        assert couleur in page


def test_lorganisation_du_site_est_reprise(session, site_factory, annee_factory,
                                           personne_factory, snap_factory,
                                           tc_factory):
    """Elle vit dans les données, pas dans un script."""
    from backend.services.comptes_sans_koxo import preparer_comptes
    from backend.services.coffre import initialiser

    site = site_factory("NDE", domaine_mail="lekreisker.fr")
    site.organisation_etiquettes = "OGEC NOTRE DAME D ESPERANCE"
    annee = annee_factory("2026-2027")
    tc_factory(site.id, "6B")
    p = personne_factory(site_id=site.id, login="eleve1", id_charlemagne=701)
    snap_factory(p.id, annee.id, classe="6B")
    session.commit()

    cle = initialiser(session, "sardine-clavier-molybdene-1789")
    _, etiquettes, _ = preparer_comptes(
        session, cle, site_id=site.id, annee_cible_id=annee.id, categorie="tous",
    )
    assert "OGEC NOTRE DAME D ESPERANCE" in etiquettes.decode("utf-8")


def test_l_etiquette_porte_l_adresse_de_connexion(session, nde):
    """L'identifiant réseau ne suffit pas : c'est l'adresse que l'élève
    saisit pour entrer dans Google, et elle ne se devine pas à partir du
    login — `alezia.acquitter.le.velly@` pour `aacquitter`.
    """
    from backend.services.coffre import initialiser
    from backend.services.comptes_sans_koxo import preparer_comptes

    site, an_prec, an_cour = nde
    cle = initialiser(session, MAITRE)
    csv_google, fiches, _ = preparer_comptes(
        session, cle, site_id=site.id, annee_cible_id=an_cour.id,
        annee_source_id=an_prec.id,
    )
    session.commit()

    page = fiches.decode("utf-8")
    for l in _lire(csv_google):
        assert l["Email Address [Required]"] in page
    assert page.count('Email :') == 3
    assert page.count('Url :') == 3


def test_l_adresse_est_plus_petite_que_l_identifiant(session, nde):
    """Une adresse fait jusqu'à quarante-deux caractères ; l'identifiant
    et le mot de passe doivent rester lisibles de loin."""
    from backend.services.coffre import initialiser
    from backend.services.comptes_sans_koxo import preparer_comptes

    site, an_prec, an_cour = nde
    cle = initialiser(session, MAITRE)
    _, fiches, _ = preparer_comptes(
        session, cle, site_id=site.id, annee_cible_id=an_cour.id,
        annee_source_id=an_prec.id,
    )
    session.commit()

    page = fiches.decode("utf-8")
    # L'adresse et l'URL sont plus petites que l'identifiant et le mot de
    # passe : une adresse fait jusqu'à quarante-deux caractères.
    assert 'class="ligne petite"' in page
    bloc = page[page.index(".ligne.petite {") : page.index(".ligne.petite {") + 420]
    assert "font-size: 7pt" in bloc
    # Avec son libellé, la plus longue adresse fait quarante-neuf
    # caractères : elle est condensée plutôt que tronquée.
    assert "scaleX" in bloc


def test_une_selection_vide_est_refusee_plutot_que_rendue(session, nde):
    """Rendre deux fichiers vides est pire que refuser : on les enregistre,
    on les ouvre, et on cherche ce qui a raté.

    La cause est presque toujours la même — l'année source réglée sur
    l'année cible, auquel cas « nouveaux » ne désigne personne.
    """
    from backend.services.coffre import initialiser
    from backend.services.comptes_sans_koxo import (
        GenerationImpossible,
        preparer_comptes,
    )

    site, an_prec, an_cour = nde
    cle = initialiser(session, MAITRE)
    with pytest.raises(GenerationImpossible, match="année source"):
        preparer_comptes(
            session, cle, site_id=site.id, annee_cible_id=an_cour.id,
            annee_source_id=an_cour.id, categorie="nouveaux",
        )


def test_le_logo_ne_rogne_pas_le_nom(session, nde):
    """En haut à droite, il obligeait à réserver quarante points, et
    « Warren ACQUITTER LE VELLY » s'y trouvait coupé au milieu.

    En bas, il ne longe que « Url : google.fr », la plus courte des quatre
    lignes — et le nom reprend toute la largeur de la carte.
    """
    from backend.services.coffre import initialiser
    from backend.services.comptes_sans_koxo import preparer_comptes

    site, an_prec, an_cour = nde
    cle = initialiser(session, MAITRE)
    _, fiches, _ = preparer_comptes(
        session, cle, site_id=site.id, annee_cible_id=an_cour.id,
        annee_source_id=an_prec.id,
    )
    session.commit()

    page = fiches.decode("utf-8")
    bloc = page[page.index(".logo {") : page.index(".logo {") + 200]
    assert "bottom: 10pt" in bloc
    assert "top:" not in bloc
    # Plus aucune réserve à droite du nom ni du groupe.
    for selecteur in (".identite {", ".groupe {"):
        style = page[page.index(selecteur) : page.index(selecteur) + 220]
        assert "padding-right" not in style
