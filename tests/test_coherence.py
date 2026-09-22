# -*- coding: utf-8 -*-
"""Ce qu'un croisement laisse derrière lui, et ce qu'on en relit.

Le constat de la Concordance mourait avec l'écran. Deux endroits le
réclamaient : la colonne « Cohérent » du référentiel, et le schéma de la
Cohérence. Ces tests tiennent les deux promesses qui rendent le rangement
honnête :

- un système **non consulté** n'est pas déclaré d'accord ;
- un système consulté **hier** garde son verdict quand le croisement du
  jour ne l'a pas regardé.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timedelta

import pytest

from backend.models import Personne, VerdictCoherence
from backend.services.coherence import (
    compter,
    enregistrer,
    etat_des_liens,
    verdicts_par_personne,
)


@dataclass
class FausseLigne:
    """Ce que la Concordance rend, réduit à ce que le rangement lit."""

    personne_id: int | None
    charlemagne: str | None = "33"
    referentiel: str | None = "33"
    google_classe: str | None = "33"
    google_ou: str | None = "/4. SU/SU2027/33"
    koxo: str | None = "33"
    koxo_consulte: bool = True
    genres: list[str] = field(default_factory=list)


@dataclass
class FauxRapport:
    lignes: list[FausseLigne]
    google_consulte: bool = True
    koxo_fourni: bool = True


def _personne(session, id_charlemagne: int, **kw) -> Personne:
    p = Personne(
        type="eleve",
        id_charlemagne=id_charlemagne,
        badge=(id_charlemagne + 1000) * 10,
        login=f"eleve{id_charlemagne}",
        nom=f"NOM{id_charlemagne}",
        prenom="Test",
        **kw,
    )
    session.add(p)
    session.commit()
    return p


def test_un_croisement_sans_ecart_rend_trois_liens_coherents(session):
    p = _personne(session, 1)
    enregistrer(session, FauxRapport([FausseLigne(personne_id=p.id)]))

    liens = {l.systeme: l for l in etat_des_liens(session)}
    for systeme in ("charlemagne", "google", "koxo"):
        assert liens[systeme].etat == "coherent", systeme
        assert liens[systeme].nb_verifies == 1


def test_un_ecart_google_ne_salit_pas_les_autres_liens(session):
    p = _personne(session, 2)
    enregistrer(
        session,
        FauxRapport([FausseLigne(personne_id=p.id, genres=["google"])]),
    )

    liens = {l.systeme: l for l in etat_des_liens(session)}
    assert liens["google"].etat == "ecarts"
    assert liens["google"].nb_ecarts == 1
    assert liens["charlemagne"].etat == "coherent"
    assert liens["koxo"].etat == "coherent"


def test_un_systeme_non_consulte_n_est_pas_declare_d_accord(session):
    """La promesse centrale : ne rien affirmer de ce qu'on n'a pas lu."""
    p = _personne(session, 3)
    enregistrer(
        session,
        FauxRapport(
            [FausseLigne(personne_id=p.id)],
            google_consulte=False,
            koxo_fourni=False,
        ),
    )

    liens = {l.systeme: l for l in etat_des_liens(session)}
    assert liens["charlemagne"].etat == "coherent"
    assert liens["google"].etat == "non_verifie"
    assert liens["koxo"].etat == "non_verifie"


def test_un_croisement_sans_koxo_n_efface_pas_le_verdict_koxo_d_hier(session):
    """Un fichier non redéposé n'est pas une information à jeter.

    C'est le cas réel : on recroise Charlemagne et Google plusieurs fois
    dans la journée sans réexporter les deux bases KoXo.
    """
    p = _personne(session, 4)
    enregistrer(session, FauxRapport([FausseLigne(personne_id=p.id, genres=["koxo"])]))
    assert {l.systeme: l.etat for l in etat_des_liens(session)}["koxo"] == "ecarts"

    enregistrer(
        session,
        FauxRapport([FausseLigne(personne_id=p.id)], koxo_fourni=False),
    )

    liens = {l.systeme: l for l in etat_des_liens(session)}
    assert liens["koxo"].etat == "ecarts", "le constat d'hier a été effacé"
    assert liens["charlemagne"].etat == "coherent"


def test_une_base_koxo_absente_laisse_ses_eleves_hors_verdict(session):
    """KoXo a un serveur par établissement : un export n'en couvre qu'un.

    L'élève de l'autre site n'est pas absent de KoXo — il est hors du
    champ du fichier, et le déclarer absent noyait tout le reste.
    """
    ici = _personne(session, 5)
    ailleurs = _personne(session, 6)
    enregistrer(
        session,
        FauxRapport(
            [
                FausseLigne(personne_id=ici.id),
                FausseLigne(personne_id=ailleurs.id, koxo_consulte=False),
            ]
        ),
    )

    par_personne = verdicts_par_personne(session)
    systemes_ailleurs = {s["systeme"] for s in par_personne[ailleurs.id]["systemes"]}
    assert "koxo" not in systemes_ailleurs
    assert {s["systeme"] for s in par_personne[ici.id]["systemes"]} == {
        "charlemagne",
        "google",
        "koxo",
    }


def test_une_ligne_redevenue_coherente_cesse_d_etre_en_ecart(session):
    p = _personne(session, 7)
    enregistrer(session, FauxRapport([FausseLigne(personne_id=p.id, genres=["google"])]))
    enregistrer(session, FauxRapport([FausseLigne(personne_id=p.id)]))

    assert verdicts_par_personne(session)[p.id]["etat"] == "coherent"
    assert (
        session.query(VerdictCoherence)
        .filter(VerdictCoherence.personne_id == p.id)
        .count()
        == 3
    )


def test_sans_compte_l_emporte_sur_un_ecart_de_groupe(session):
    """Une personne sans compte n'a pas une classe fausse : elle n'en a pas."""
    p = _personne(session, 8)
    enregistrer(
        session,
        FauxRapport(
            [FausseLigne(personne_id=p.id, genres=["sans_compte", "groupe"])]
        ),
    )

    v = verdicts_par_personne(session)[p.id]
    google = next(s for s in v["systemes"] if s["systeme"] == "google")
    assert google["etat"] == "absent"


def test_un_inconnu_du_referentiel_n_engendre_aucun_verdict(session):
    """Sans identité, aucune ligne à rattacher — ça se règle par une ingestion."""
    enregistrer(
        session,
        FauxRapport([FausseLigne(personne_id=None, genres=["absent_referentiel"])]),
    )
    assert session.query(VerdictCoherence).count() == 0


def test_les_trois_systemes_sans_source_sont_rendus_et_expliques(session):
    """PMB, Sodexo et CardStudio ne se cachent pas : ils s'expliquent.

    « Pas de source » n'est pas « pas encore fait » : le premier demande
    un export qu'on n'a pas, le second un clic.
    """
    liens = {l.systeme: l for l in etat_des_liens(session)}
    assert len(liens) == 6
    for systeme in ("pmb", "sodexo", "cardstudio"):
        assert liens[systeme].etat == "sans_source"
        assert liens[systeme].pourquoi, systeme


def test_sans_aucun_croisement_les_trois_liens_lisibles_sont_gris(session):
    liens = {l.systeme: l for l in etat_des_liens(session)}
    for systeme in ("charlemagne", "google", "koxo"):
        assert liens[systeme].etat == "non_verifie"
        assert liens[systeme].verifie_le is None


def test_le_verdict_porte_la_classe_de_chaque_cote(session):
    """Deux valeurs côte à côte suffisent à comprendre sans rouvrir."""
    p = _personne(session, 9)
    enregistrer(
        session,
        FauxRapport(
            [
                FausseLigne(
                    personne_id=p.id,
                    referentiel="33",
                    charlemagne="34",
                    genres=["referentiel"],
                )
            ]
        ),
    )

    v = verdicts_par_personne(session)[p.id]
    ch = next(s for s in v["systemes"] if s["systeme"] == "charlemagne")
    assert (ch["attendu"], ch["constate"]) == ("33", "34")
    assert ch["genre"] == "referentiel"


def test_le_detail_d_un_lien_compte_les_genres_du_plus_nombreux(session):
    for i, genres in enumerate(
        [["google"], ["google"], ["groupe"]], start=10
    ):
        p = _personne(session, i)
        enregistrer(
            session,
            FauxRapport([FausseLigne(personne_id=p.id, genres=genres)]),
        )

    google = next(l for l in etat_des_liens(session) if l.systeme == "google")
    assert [d["genre"] for d in google.details] == ["google", "groupe"]
    assert [d["nb"] for d in google.details] == [2, 1]


def test_verdicts_par_personne_filtre_sur_les_identites_demandees(session):
    a = _personne(session, 20)
    b = _personne(session, 21)
    enregistrer(
        session,
        FauxRapport(
            [FausseLigne(personne_id=a.id), FausseLigne(personne_id=b.id)]
        ),
    )

    assert set(verdicts_par_personne(session, [a.id])) == {a.id}
    assert verdicts_par_personne(session, []) == {}


def test_compter_separe_eleves_et_adultes(session):
    _personne(session, 30)
    adulte = Personne(
        type="adulte",
        id_charlemagne=31,
        badge=310,
        login="prof31",
        nom="PROF",
        prenom="Test",
    )
    session.add(adulte)
    session.commit()

    c = compter(session)
    assert (c["nb_personnes"], c["nb_eleves"], c["nb_adultes"]) == (2, 1, 1)
    assert c["nb_verifiees"] == 0


def test_la_date_du_lien_est_celle_du_dernier_croisement(session):
    p = _personne(session, 40)
    enregistrer(session, FauxRapport([FausseLigne(personne_id=p.id)]))
    avant = next(l for l in etat_des_liens(session) if l.systeme == "google")

    # Le rangement horodate à l'écriture : rejouer le croisement rafraîchit.
    session.query(VerdictCoherence).update(
        {VerdictCoherence.verifie_le: datetime.utcnow() - timedelta(days=2)}
    )
    session.commit()
    vieux = next(l for l in etat_des_liens(session) if l.systeme == "google")
    assert vieux.verifie_le < avant.verifie_le

    enregistrer(session, FauxRapport([FausseLigne(personne_id=p.id)]))
    neuf = next(l for l in etat_des_liens(session) if l.systeme == "google")
    assert neuf.verifie_le > vieux.verifie_le
