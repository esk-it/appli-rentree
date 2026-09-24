"""Ce que le référentiel sait de chacun, et ce qui lui manque.

## Pourquoi un relevé à part

Chaque écran voyait son morceau : les cartes, les codes de classe ; les
photos, les visages ; le coffre, ses mots de passe. Personne ne voyait
l'ensemble, et c'est pourtant la question qu'on se pose après une
ingestion : « qu'est-ce qui manque encore, et où ? ».

Le relevé compte, pour les inscrits de l'année, ce que chaque fiche porte :
l'adresse d'un compte constaté, un mot de passe au coffre, une photo sur le
partage, l'INE, la date de naissance, et si le dernier croisement l'a
trouvée cohérente. Puis il range les élèves par classe — c'est à ce grain
qu'on corrige.

## Ce qu'il ne fait pas

Il ne devine rien. Une photo se constate sur le partage : injoignable, le
compte des photos vaut `None`, pas zéro — « on n'a pas regardé » n'est pas
« il n'y en a pas ». Une personne jamais croisée n'est ni cohérente ni en
écart : elle n'est pas vérifiée.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field

from sqlalchemy.orm import Session

from backend.models import (
    AnneeScolaire,
    Personne,
    SecretConserve,
    Site,
    Snapshot,
    TableCorrespondance,
)


@dataclass
class CompletudeClasse:
    classe: str
    site: str | None
    effectif: int = 0
    avec_adresse: int = 0
    avec_photo: int | None = 0
    """`None` quand le partage des photos n'a pas pu être lu."""
    avec_ine: int = 0
    avec_naissance: int = 0
    au_coffre: int = 0
    codes_carte: bool = False
    """La classe porte son code niveau et son code établissement."""
    verifies: int = 0
    coherents: int = 0


@dataclass
class Completude:
    annee: str
    effectif: int = 0
    eleves: int = 0
    adultes: int = 0
    avec_adresse: int = 0
    avec_photo: int | None = 0
    """Élèves seulement : les photos d'adultes vivent ailleurs."""
    avec_ine: int = 0
    avec_naissance: int = 0
    au_coffre: int = 0
    classes: int = 0
    classes_avec_codes: int = 0
    photos_injoignables: str | None = None
    par_classe: list[CompletudeClasse] = field(default_factory=list)


def _cle_naturelle(texte: str) -> list:
    """`2_10` après `2_9`, comme on les lit."""
    return [int(x) if x.isdigit() else x for x in re.split(r"(\d+)", texte)]


def relever(session: Session, *, annee_id: int | None = None) -> Completude:
    """Le relevé de l'année demandée — la plus récente par défaut.

    Raises:
        ValueError: l'année demandée n'existe pas.
    """
    from backend.services.coherence import verdicts_par_personne
    from backend.services.inventaire_photos import (
        InventaireImpossible,
        chemins_attribues,
    )

    annees = session.query(AnneeScolaire).all()
    if not annees:
        return Completude(annee="")
    if annee_id is None:
        annee = max(annees, key=lambda a: a.libelle)
    else:
        annee = next((a for a in annees if a.id == annee_id), None)
        if annee is None:
            raise ValueError(f"Année introuvable : {annee_id}")

    # La classe de l'année, c'est celle du dernier snapshot de l'année — la
    # fiche, elle, porte la situation d'aujourd'hui.
    derniers: dict[int, Snapshot] = {}
    for sn in (
        session.query(Snapshot)
        .filter(Snapshot.annee_scolaire_id == annee.id)
        .order_by(Snapshot.date_ingestion, Snapshot.id)
    ):
        derniers[sn.personne_id] = sn
    gens = {
        p.id: p
        for p in session.query(Personne).filter(Personne.id.in_(list(derniers) or [0]))
    }
    au_coffre = {
        pid for (pid,) in session.query(SecretConserve.personne_id).distinct()
    }
    verdicts = verdicts_par_personne(session)
    table = {
        (t.classe_code_court or "").strip(): t
        for t in session.query(TableCorrespondance)
    }
    noms_sites = {s.id: s.nom for s in session.query(Site)}

    releve = Completude(annee=annee.libelle)
    try:
        photos: dict[int, str] | None = chemins_attribues(session, annee_id=annee.id)
    except InventaireImpossible as e:
        photos = None
        releve.photos_injoignables = str(e)

    par_classe: dict[str, CompletudeClasse] = {}
    for pid, sn in derniers.items():
        p = gens.get(pid)
        if p is None:
            continue
        releve.effectif += 1
        adresse = bool(p.email_constate)
        coffre = pid in au_coffre
        releve.avec_adresse += adresse
        releve.au_coffre += coffre
        releve.avec_naissance += bool(p.date_naissance)
        if p.type != "eleve":
            releve.adultes += 1
            continue
        releve.eleves += 1
        releve.avec_ine += bool(p.ine)

        classe = (sn.classe or p.classe or "").strip() or "(sans classe)"
        t = table.get(classe)
        k = par_classe.get(classe)
        if k is None:
            k = par_classe[classe] = CompletudeClasse(
                classe=classe,
                site=noms_sites.get(t.site_id) if t else noms_sites.get(p.site_id),
                avec_photo=0 if photos is not None else None,
                codes_carte=bool(t and t.code_niveau and t.code_etablissement),
            )
        k.effectif += 1
        k.avec_adresse += adresse
        k.au_coffre += coffre
        k.avec_ine += bool(p.ine)
        k.avec_naissance += bool(p.date_naissance)
        if photos is not None and pid in photos:
            k.avec_photo += 1
        v = verdicts.get(pid)
        if v is not None:
            k.verifies += 1
            k.coherents += v["etat"] == "coherent"

    releve.par_classe = sorted(
        par_classe.values(), key=lambda k: (k.site or "~", _cle_naturelle(k.classe))
    )
    releve.classes = len(releve.par_classe)
    releve.classes_avec_codes = sum(k.codes_carte for k in releve.par_classe)
    releve.avec_photo = (
        None if photos is None else sum(k.avec_photo or 0 for k in releve.par_classe)
    )
    return releve
