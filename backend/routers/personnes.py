"""Endpoints de consultation du référentiel Personne.

La création se fait via l'ingestion (Lot 3) et l'amorçage (Lot 9) — pas
ici. Deux écritures exposées, pour les cas que le programme refuse de
trancher seul : figer l'adresse mail d'une personne (homonymes visant la
même adresse, adresse historique hors convention), et réunir deux fiches
d'une même personne (un passage de NDE à NDK, une réinscription).
"""
from __future__ import annotations

from datetime import date, datetime

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from backend.database import db_session
from backend.models import Personne, Site
from backend.services.regles_metier import calculer_email

router = APIRouter(prefix="/api/personnes", tags=["personnes"])


class PersonneOut(BaseModel):
    id: int
    type: str
    id_charlemagne: int
    cle_pivot: str
    login_constate: str | None = None
    """L'identifiant que KoXo détient réellement pour cette personne.

    `login` est unique dans tout le référentiel ; les identifiants, eux,
    vivent dans une base KoXo par population. Quand deux personnes en
    produisent le même, le référentiel en suffixe une — et affiche alors un
    identifiant que personne ne porte. Celui-ci vient de la source."""
    badge: int
    login: str
    email: str | None
    email_est_constate: bool
    """True si l'adresse vient d'un compte existant, False si elle est calculée."""
    google_user_id: str | None
    nom: str
    prenom: str
    nom_usage: str | None
    classe: str | None
    niveau: str | None
    code_etablissement: str | None
    regime: str | None
    site: str | None
    date_entree: date | None
    ine: str | None = None
    date_naissance: date | None = None
    civilite: str | None
    poste_occupe: str | None
    matieres: str | None
    classes_prof_principal: str | None = None
    au_coffre: bool = False
    """Un mot de passe au moins est gardé au coffre pour elle. Dit sans
    ouvrir le coffre : savoir qu'un secret existe n'en révèle rien."""
    date_creation: datetime
    date_derniere_maj: datetime


def _constats_par_badge(session: Session) -> dict[int, str]:
    """L'identifiant que chaque base KoXo lue détient, par badge."""
    from backend.models import LoginReserve

    return {
        r.badge: r.login
        for r in session.query(LoginReserve).all()
        if r.badge is not None and r.login
    }


def _au_coffre(session: Session) -> set[int]:
    """Les personnes dont le coffre garde au moins un mot de passe."""
    from backend.models import SecretConserve

    return {pid for (pid,) in session.query(SecretConserve.personne_id).distinct()}


def _serialiser(
    p: Personne,
    sites_par_id: dict[int, Site],
    constats: dict[int, str] | None = None,
    coffre: set[int] | None = None,
) -> PersonneOut:
    site = sites_par_id.get(p.site_id) if p.site_id else None
    # Recalcul local plutôt que `p.email` : la relation `p.site` déclencherait
    # une requête par personne alors que les sites sont déjà chargés ici.
    if p.email_constate:
        email = p.email_constate
    elif site:
        email = calculer_email(p.prenom, p.nom, site.domaine_mail) or None
    else:
        email = None
    return PersonneOut(
        id=p.id,
        type=p.type,
        id_charlemagne=p.id_charlemagne,
        cle_pivot=p.cle_pivot,
        login_constate=(constats or {}).get(p.badge),
        badge=p.badge,
        login=p.login,
        email=email,
        email_est_constate=bool(p.email_constate),
        google_user_id=p.google_user_id,
        nom=p.nom,
        prenom=p.prenom,
        nom_usage=p.nom_usage,
        classe=p.classe,
        niveau=p.niveau,
        code_etablissement=p.code_etablissement,
        regime=p.regime,
        site=site.nom if site else None,
        date_entree=p.date_entree,
        ine=p.ine,
        date_naissance=p.date_naissance,
        civilite=p.civilite,
        poste_occupe=p.poste_occupe,
        matieres=p.matieres,
        classes_prof_principal=p.classes_prof_principal,
        au_coffre=p.id in (coffre or ()),
        date_creation=p.date_creation,
        date_derniere_maj=p.date_derniere_maj,
    )


@router.get("", response_model=list[PersonneOut])
def lister_personnes(
    type: str | None = Query(None, description="Filtre : `eleve` ou `adulte`"),
    site: str | None = Query(None, description="Filtre par code site (NDE, NDK, SU)"),
    session: Session = Depends(db_session),
) -> list[PersonneOut]:
    """Liste toutes les personnes du référentiel, avec filtres optionnels."""
    sites_par_id = {s.id: s for s in session.query(Site).all()}
    q = session.query(Personne)
    if type:
        q = q.filter_by(type=type)
    if site:
        site_obj = next((s for s in sites_par_id.values() if s.nom == site), None)
        if site_obj is None:
            return []
        q = q.filter_by(site_id=site_obj.id)
    q = q.order_by(Personne.type, Personne.nom, Personne.prenom)
    constats = _constats_par_badge(session)
    coffre = _au_coffre(session)
    return [_serialiser(p, sites_par_id, constats, coffre) for p in q.all()]


class LigneMouvementOut(BaseModel):
    mouvement: str
    nom: str
    prenom: str
    personne_id: int | None = None
    cle_pivot: str | None = None
    login: str | None = None
    email: str | None = None
    badge: int | None = None
    type: str = ""
    site: str | None = None
    classe: str | None = None
    classe_precedente: str | None = None
    classe_suivante: str | None = None
    discipline: str | None = None
    detail: str = ""
    methode_rapprochement: str | None = None


class MouvementsOut(BaseModel):
    annee: str
    type_personne: str
    source: str
    annee_precedente: str | None
    annee_suivante: str | None
    lignes: list[LigneMouvementOut]
    entrants_connus: bool
    sortants_connus: bool
    raisons: dict[str, str]
    nb_par_mouvement: dict[str, int]


# Déclarée **avant** `/{personne_id}` : cette route-là capture n'importe
# quel segment unique, et avalerait « mouvements » pour le donner à
# manger à un paramètre entier.
@router.get("/mouvements", response_model=MouvementsOut)
def lister_mouvements(
    annee_id: int = Query(..., description="Année observée"),
    type: str = Query("eleve", description="`eleve` ou `adulte`"),
    site: str | None = Query(None, description="Code site (NDE, NDK, SU)"),
    session: Session = Depends(db_session),
) -> MouvementsOut:
    """Qui entre, qui sort, qui reste, pour une année et une population.

    Les deux populations ne se lisent pas dans la même source : les élèves
    dans les photographies annuelles, les adultes dans le tableau des
    professeurs. Ce que la source ne permet pas d'établir est dit plutôt
    que deviné.
    """
    from dataclasses import asdict

    from backend.services.mouvements import mouvements_annee

    try:
        r = mouvements_annee(
            session, annee_id=annee_id, type_personne=type, site=site
        )
    except ValueError as e:
        raise HTTPException(400, str(e)) from None

    return MouvementsOut(
        annee=r.annee,
        type_personne=r.type_personne,
        source=r.source,
        annee_precedente=r.annee_precedente,
        annee_suivante=r.annee_suivante,
        lignes=[LigneMouvementOut(**asdict(l)) for l in r.lignes],
        entrants_connus=r.entrants_connus,
        sortants_connus=r.sortants_connus,
        raisons=r.raisons,
        nb_par_mouvement=r.nb_par_mouvement,
    )


class AnneeFicheOut(BaseModel):
    annee: str
    classe: str | None
    site: str | None


class VisantOut(BaseModel):
    personne_id: int
    cle_pivot: str
    nom: str
    prenom: str
    type: str
    site: str | None
    classe: str | None
    a_un_compte: bool
    """Vrai si l'adresse est **constatée** — le compte existe déjà."""
    a_trancher: bool
    """Vrai si c'est à cette personne de prendre une adresse distincte."""
    adresse_proposee: str
    """Une suggestion à suffixe, jamais appliquée seule."""
    inscrit: bool = False
    """Vrai si la fiche est inscrite l'année la plus récente."""
    annees: list[AnneeFicheOut] = []
    """Les années de la fiche, de la plus récente à la plus ancienne."""
    ine: str | None = None
    date_naissance: date | None = None


class CollisionOut(BaseModel):
    adresse: str
    visants: list[VisantOut]
    plusieurs_comptes: bool
    """Vrai quand **plusieurs** détiennent déjà l'adresse.

    Cas rencontré sur la base réelle — trois groupes sur vingt-neuf : deux
    fiches portent le même `email_constate`. Personne ne peut alors être
    présumé la garder, et l'écran ouvre la saisie sur toutes plutôt que de
    désigner un titulaire au hasard. Les trois étaient en fait une seule
    personne en deux fiches — d'où `meme_personne_probable`."""
    meme_personne_probable: bool = False
    """Deux fiches qui ont tout d'une seule personne inscrite deux fois.

    Sur la base réelle, en septembre 2026, les vingt-neuf adresses
    disputées étaient toutes dans ce cas : vingt-huit élèves passés de NDE
    à NDK ou SU, avec une seconde fiche Charlemagne, et une réinscription.
    Leur proposer une adresse suffixée aurait créé un second compte à des
    élèves qui ont déjà le leur."""
    garde_id: int | None = None
    """La fiche qui resterait si on les réunissait."""
    motif: str | None = None
    """Ce qui fait penser à une seule personne, en une phrase."""
    preuve: str | None = None
    """`ine`, `naissance` ou `passage`."""
    contradiction: str | None = None
    """Ce qui prouve deux personnes : deux INE, deux dates de naissance."""


@router.get("/collisions", response_model=list[CollisionOut])
def lister_collisions(session: Session = Depends(db_session)) -> list[CollisionOut]:
    """Les adresses visées par plusieurs personnes, et qui les vise.

    Google refuse la création d'un doublon : tant qu'une de ces adresses
    reste disputée, l'export s'arrête sur elle. L'écran qui départage a
    besoin de la liste nominative, pas d'un compteur.

    La suggestion à suffixe est **proposée, jamais appliquée** : les
    adresses existantes portent tantôt un `1`, tantôt un `2`, sans règle
    déductible. Choisir à la place de quelqu'un reviendrait à créer un
    compte sous une adresse que personne n'a validée.
    """
    from backend.models import Snapshot
    from backend.services.anomalies import collisions_email
    from backend.services.fusion import (
        annee_la_plus_recente,
        annees_vecues,
        choisir_garde,
        decrire_passage,
        evaluer_lien,
    )

    sites_par_id = {s.id: s for s in session.query(Site).all()}
    sorties: list[CollisionOut] = []

    conflits = collisions_email(session)
    ids = [p.id for ps in conflits.values() for p in ps]
    vecues = annees_vecues(session, ids)
    courante = annee_la_plus_recente(session)
    inscrits: set[int] = set()
    if courante is not None and ids:
        inscrits = {
            pid
            for (pid,) in session.query(Snapshot.personne_id)
            .filter(
                Snapshot.annee_scolaire_id == courante.id,
                Snapshot.personne_id.in_(ids),
            )
            .distinct()
        }

    for adresse, personnes_en_conflit in sorted(conflits.items()):
        locale, _, domaine = adresse.partition("@")
        titulaires = [p for p in personnes_en_conflit if p.email_constate]
        # Un seul titulaire garde l'adresse nue : la lui retirer casserait
        # une adresse en service. Plusieurs, ou aucun, et personne ne peut
        # être présumé : tout le monde doit trancher.
        plusieurs_comptes = len(titulaires) > 1
        garde = titulaires[0].id if len(titulaires) == 1 else None

        visants: list[VisantOut] = []
        rang = 1
        for p in personnes_en_conflit:
            a_trancher = p.id != garde
            if a_trancher:
                rang += 1
                proposee = f"{locale}{rang}@{domaine}"
            else:
                proposee = p.email_constate or adresse
            visants.append(
                VisantOut(
                    personne_id=p.id,
                    cle_pivot=p.cle_pivot,
                    nom=p.nom,
                    prenom=p.prenom,
                    type=p.type,
                    site=sites_par_id[p.site_id].nom if p.site_id in sites_par_id else None,
                    classe=p.classe,
                    a_un_compte=bool(p.email_constate),
                    a_trancher=a_trancher,
                    adresse_proposee=proposee,
                    inscrit=p.id in inscrits,
                    annees=[
                        AnneeFicheOut(annee=v.annee, classe=v.classe, site=v.site)
                        for v in vecues.get(p.id, [])
                    ],
                    ine=p.ine,
                    date_naissance=p.date_naissance,
                )
            )

        probable, garde_id, motif = False, None, None
        preuve = contradiction = None
        if len(personnes_en_conflit) == 2:
            a, b = personnes_en_conflit
            lien = evaluer_lien(a, b, inscrits)
            contradiction = lien.contradiction
            if lien.probable:
                garde, absorbee, _ = choisir_garde(session, a, b)
                probable, garde_id, preuve = True, garde.id, lien.preuve
                motif = decrire_passage(
                    garde, vecues.get(garde.id, []),
                    absorbee, vecues.get(absorbee.id, []),
                    preuve=lien.preuve,
                )
        sorties.append(
            CollisionOut(
                adresse=adresse,
                visants=visants,
                plusieurs_comptes=plusieurs_comptes,
                meme_personne_probable=probable,
                garde_id=garde_id,
                motif=motif,
                preuve=preuve,
                contradiction=contradiction,
            )
        )

    return sorties


class ClasseCompletudeOut(BaseModel):
    classe: str
    site: str | None
    effectif: int
    avec_adresse: int
    avec_photo: int | None
    avec_ine: int
    avec_naissance: int
    au_coffre: int
    codes_carte: bool
    verifies: int
    coherents: int


class CompletudeOut(BaseModel):
    annee: str
    effectif: int
    eleves: int
    adultes: int
    avec_adresse: int
    avec_photo: int | None
    avec_ine: int
    avec_naissance: int
    au_coffre: int
    classes: int
    classes_avec_codes: int
    photos_injoignables: str | None
    par_classe: list[ClasseCompletudeOut]


@router.get("/completude", response_model=CompletudeOut)
def lire_completude(
    annee_id: int | None = None, session: Session = Depends(db_session)
) -> CompletudeOut:
    """Ce que le référentiel sait des inscrits de l'année, et ce qui manque.

    Adresse du compte, mot de passe au coffre, photo, INE, date de
    naissance, cohérence : par classe, pour qu'on sache où corriger. Le
    partage des photos injoignable donne `None`, pas zéro.
    """
    from dataclasses import asdict

    from backend.services.completude import relever

    try:
        return CompletudeOut(**asdict(relever(session, annee_id=annee_id)))
    except ValueError as e:
        raise HTTPException(404, str(e)) from None


class TrombinoscopePayload(BaseModel):
    classe: str = Field(..., min_length=1, max_length=30)
    annee_id: int | None = None


class TrombinoscopeOut(BaseModel):
    nom_fichier: str
    pdf_base64: str
    nb_eleves: int
    nb_sans_photo: int


@router.post("/trombinoscope", response_model=TrombinoscopeOut)
def imprimer_trombinoscope(
    payload: TrombinoscopePayload, session: Session = Depends(db_session)
) -> TrombinoscopeOut:
    """Le trombinoscope d'une classe, en PDF A4, photos comprises.

    Imprimé par le navigateur du poste, comme les étiquettes : Edge ou
    Chrome doit être installé.
    """
    import base64

    from backend.services.impression_pdf import (
        ImpressionImpossible,
        html_en_pdf,
        nom_de_fichier,
    )
    from backend.services.trombinoscope import TrombinoscopeImpossible, composer

    try:
        t = composer(session, classe=payload.classe.strip(), annee_id=payload.annee_id)
    except TrombinoscopeImpossible as e:
        raise HTTPException(404, str(e)) from None
    try:
        pdf = html_en_pdf(t.html)
    except ImpressionImpossible as e:
        raise HTTPException(400, str(e)) from None
    return TrombinoscopeOut(
        nom_fichier=nom_de_fichier(f"Trombinoscope_{t.classe}_{t.annee}") + ".pdf",
        pdf_base64=base64.b64encode(pdf).decode("ascii"),
        nb_eleves=t.nb_eleves,
        nb_sans_photo=t.nb_sans_photo,
    )


class DoublonOut(BaseModel):
    cle: str
    visants: list[VisantOut]
    """La fiche qui reste d'abord, puis celle qui la rejoindrait."""
    garde_id: int
    preuve: str
    """`ine` ou `naissance` : jamais le seul nom, ici."""
    motif: str


@router.get("/doublons", response_model=list[DoublonOut])
def lister_doublons(session: Session = Depends(db_session)) -> list[DoublonOut]:
    """Les personnes en deux fiches que l'INE ou la naissance prouve.

    Seulement celles qui ne se disputent pas déjà une adresse : celles-là,
    `/collisions` les présente, et deux fois la même paire ferait réunir
    deux fois. Un élève passé de NDE à NDK sous une adresse neuve n'avait
    jusqu'ici aucun écran pour le montrer.
    """
    from backend.models import Snapshot
    from backend.services.fusion import (
        annee_la_plus_recente,
        annees_vecues,
        doublons_sans_adresse_disputee,
    )

    trouves = doublons_sans_adresse_disputee(session)
    if not trouves:
        return []

    sites_par_id = {s.id: s for s in session.query(Site).all()}
    ids = [x for d in trouves for x in (d.garde.id, d.absorbee.id)]
    vecues = annees_vecues(session, ids)
    courante = annee_la_plus_recente(session)
    inscrits = set()
    if courante is not None:
        inscrits = {
            pid
            for (pid,) in session.query(Snapshot.personne_id)
            .filter(
                Snapshot.annee_scolaire_id == courante.id,
                Snapshot.personne_id.in_(ids),
            )
            .distinct()
        }

    def visant(p: Personne) -> VisantOut:
        return VisantOut(
            personne_id=p.id, cle_pivot=p.cle_pivot, nom=p.nom, prenom=p.prenom,
            type=p.type,
            site=sites_par_id[p.site_id].nom if p.site_id in sites_par_id else None,
            classe=p.classe, a_un_compte=bool(p.email_constate), a_trancher=False,
            adresse_proposee=p.email_constate or "",
            inscrit=p.id in inscrits,
            annees=[
                AnneeFicheOut(annee=v.annee, classe=v.classe, site=v.site)
                for v in vecues.get(p.id, [])
            ],
            ine=p.ine, date_naissance=p.date_naissance,
        )

    return [
        DoublonOut(
            cle=f"{d.garde.id}-{d.absorbee.id}",
            visants=[visant(d.garde), visant(d.absorbee)],
            garde_id=d.garde.id,
            preuve=d.preuve,
            motif=d.motif,
        )
        for d in trouves
    ]


class FusionPayload(BaseModel):
    ids: list[int] = Field(..., min_length=2, max_length=2)
    """Les deux fiches. Le programme choisit laquelle reste : l'inscription
    la plus récente."""
    mode: str = "simulation"


class FicheResumeeOut(BaseModel):
    personne_id: int
    cle_pivot: str
    nom: str
    prenom: str
    login: str
    badge: int
    site: str | None
    classe: str | None
    email_constate: str | None
    annees: list[AnneeFicheOut]


class FusionOut(BaseModel):
    mode: str
    garde: FicheResumeeOut
    absorbee: FicheResumeeOut
    motif_du_choix: str
    annees_rattachees: list[str]
    annees_ecartees: list[str]
    repris: list[str]
    abandonnes: list[str]
    avertissements: list[str]


@router.post("/fusion", response_model=FusionOut)
def reunir_deux_fiches(
    payload: FusionPayload, session: Session = Depends(db_session)
) -> FusionOut:
    """Réunit deux fiches d'une même personne.

    Un élève passé de NDE à NDK a deux fiches Charlemagne : les deux bases
    ne se parlent pas. En `simulation`, rien n'est écrit — la réponse dit
    quelle fiche reste, quelles années la rejoignent, et ce qui est repris
    ou abandonné. Rien n'est touché dans Google ni dans KoXo.
    """
    from dataclasses import asdict

    from backend.services.fusion import FusionImpossible, fusionner

    try:
        r = fusionner(session, *payload.ids, mode=payload.mode)
    except FusionImpossible as e:
        raise HTTPException(409, str(e)) from None
    except ValueError as e:
        raise HTTPException(400, str(e)) from None
    return FusionOut(**asdict(r))


@router.get("/{personne_id}", response_model=PersonneOut)
def obtenir_personne(
    personne_id: int, session: Session = Depends(db_session)
) -> PersonneOut:
    """Consulte une personne par son id référentiel."""
    p = session.query(Personne).filter_by(id=personne_id).one_or_none()
    if p is None:
        raise HTTPException(404, f"Personne introuvable : {personne_id}")
    sites_par_id = {s.id: s for s in session.query(Site).all()}
    return _serialiser(p, sites_par_id, _constats_par_badge(session))


@router.get("/par-cle-pivot/{cle}", response_model=PersonneOut)
def obtenir_par_cle_pivot(
    cle: str, session: Session = Depends(db_session)
) -> PersonneOut:
    """Consulte une personne par sa clé pivot sérialisée (`E5292`, `A60`)."""
    if not cle or cle[0] not in ("E", "A"):
        raise HTTPException(400, f"Clé pivot invalide : {cle} (format attendu : E<n> ou A<n>)")
    try:
        id_ch = int(cle[1:])
    except ValueError:
        raise HTTPException(400, f"Clé pivot invalide : {cle}") from None
    type_p = "eleve" if cle[0] == "E" else "adulte"
    # Un ancien numéro, réuni à une autre fiche, mène à la personne.
    from backend.services.fusion import personne_par_cle

    p, _ = personne_par_cle(session, type_p, id_ch)
    if p is None:
        raise HTTPException(404, f"Personne introuvable : {cle}")
    sites_par_id = {s.id: s for s in session.query(Site).all()}
    return _serialiser(p, sites_par_id, _constats_par_badge(session))


class EmailPayload(BaseModel):
    email: str | None = Field(
        None,
        description=(
            "Adresse à figer pour cette personne. `null` ou chaîne vide "
            "rétablit l'adresse calculée."
        ),
        max_length=200,
    )


@router.patch("/{personne_id}/email", response_model=PersonneOut)
def definir_email_constate(
    personne_id: int,
    payload: EmailPayload,
    session: Session = Depends(db_session),
) -> PersonneOut:
    """Fige l'adresse mail d'une personne, ou rétablit le calcul.

    Sert aux cas que le programme refuse de trancher seul : deux homonymes
    dont l'un possède déjà `prenom.nom@`, une adresse historique hors
    convention. Une fois saisie, elle fait autorité comme si elle avait été
    relevée dans un export.
    """
    p = session.query(Personne).filter_by(id=personne_id).one_or_none()
    if p is None:
        raise HTTPException(404, f"Personne introuvable : {personne_id}")

    adresse = (payload.email or "").strip().lower()
    if adresse:
        if "@" not in adresse or adresse.startswith("@") or adresse.endswith("@"):
            raise HTTPException(400, f"Adresse invalide : {payload.email!r}")
        deja_pris = (
            session.query(Personne)
            .filter(Personne.email_constate == adresse, Personne.id != personne_id)
            .first()
        )
        if deja_pris is not None:
            raise HTTPException(
                409,
                f"{adresse} est déjà l'adresse de {deja_pris.prenom} "
                f"{deja_pris.nom} ({deja_pris.cle_pivot})",
            )
        p.email_constate = adresse
        # Une adresse attribuée était une décision prise faute de mieux —
        # un suffixe choisi pour lever une homonymie. Un constat la
        # remplace : la garder ferait resurgir l'ancienne le jour où l'on
        # efface le constat. Le second Hugo GUILLOU s'est vu attribuer
        # `hugo.guillou1@` par le programme, et créer dans Google sous
        # `hugo.guillou2@` — l'attribution n'avait plus lieu d'être.
        p.email_attribuee = None
    else:
        p.email_constate = None

    session.commit()
    sites_par_id = {s.id: s for s in session.query(Site).all()}
    return _serialiser(p, sites_par_id, _constats_par_badge(session))

class AnneeVecueOut(BaseModel):
    annee: str
    classe: str | None
    niveau: str | None
    regime: str | None
    date_ingestion: str | None


class CompteOut(BaseModel):
    cible: str
    etat: str
    ou_appliquee: str | None
    ou_constatee: str | None
    date_prevue_purge: str | None
    verification: str | None
    note: str | None


class FicheOut(BaseModel):
    personne: PersonneOut
    parcours: list[AnneeVecueOut]
    """Une ligne par année vécue, de la plus récente à la plus ancienne."""
    comptes: list[CompteOut]
    anciennes_fiches: list[str] = []
    """Les fiches réunies à celle-ci : `E717 (NDE)`. Sans elles, le
    parcours montrerait une année à NDE sans dire d'où elle vient."""


class IdentitePayload(BaseModel):
    nom: str | None = None
    prenom: str | None = None
    mode: str = "simulation"


class IdentiteOut(BaseModel):
    personne_id: int
    nom_avant: str
    prenom_avant: str
    nom_apres: str
    prenom_apres: str
    login: str
    email_avant: str | None
    email_apres: str | None
    changements: list[str]
    reste_a_faire: list[str]


@router.patch("/{personne_id}/identite", response_model=IdentiteOut)
def corriger_identite(
    personne_id: int,
    payload: IdentitePayload,
    session: Session = Depends(db_session),
) -> IdentiteOut:
    """Corrige le nom ou le prénom. Ne touche ni l'identifiant ni le badge.

    Charlemagne se trompe, ou il est en retard, et rien ne permettait de le
    contredire. En `simulation`, rien n'est écrit : la réponse montre ce
    que la correction entraînerait, l'adresse calculée comprise.
    """
    from backend.services.identite import (
        ModificationImpossible,
        modifier_identite,
    )

    if payload.mode not in ("simulation", "reel"):
        raise HTTPException(400, f"mode invalide : {payload.mode!r}")
    try:
        r = modifier_identite(
            session, personne_id,
            nom=payload.nom, prenom=payload.prenom, mode=payload.mode,
        )
    except ModificationImpossible as e:
        raise HTTPException(400, str(e)) from None
    return IdentiteOut(**vars(r))


@router.get("/{personne_id}/fiche", response_model=FicheOut)
def fiche(personne_id: int, session: Session = Depends(db_session)) -> FicheOut:
    """Tout ce que le référentiel sait d'une personne, en un appel.

    L'écran affichait la classe de l'année préparée et rien d'autre, alors
    que la base garde chaque année vécue. Savoir d'où vient un élève —
    quelle classe l'an dernier, quel régime — est ce qui permet de juger un
    cas douteux sans ouvrir Charlemagne à côté.
    """
    from backend.models import AnneeScolaire, CompteCible, Snapshot

    personne = session.query(Personne).filter_by(id=personne_id).one_or_none()
    if personne is None:
        raise HTTPException(404, f"Personne {personne_id} introuvable")

    lignes = (
        session.query(Snapshot, AnneeScolaire)
        .join(AnneeScolaire, Snapshot.annee_scolaire_id == AnneeScolaire.id)
        .filter(Snapshot.personne_id == personne_id)
        .all()
    )
    # Un même élève peut avoir plusieurs snapshots pour une année, si
    # l'export a été rejoué : on garde le plus récent de chacune.
    par_annee: dict[str, tuple] = {}
    for sn, an in lignes:
        garde = par_annee.get(an.libelle)
        if garde is None or sn.date_ingestion > garde[0].date_ingestion:
            par_annee[an.libelle] = (sn, an)

    parcours = [
        AnneeVecueOut(
            annee=libelle,
            classe=sn.classe,
            niveau=sn.niveau,
            regime=getattr(sn, "regime", None),
            date_ingestion=sn.date_ingestion.isoformat() if sn.date_ingestion else None,
        )
        for libelle, (sn, _) in sorted(par_annee.items(), reverse=True)
    ]

    comptes = [
        CompteOut(
            cible=c.cible,
            etat=c.etat,
            ou_appliquee=c.ou_appliquee,
            ou_constatee=getattr(c, "ou_constatee", None),
            date_prevue_purge=(
                c.date_prevue_purge.isoformat() if c.date_prevue_purge else None
            ),
            verification=getattr(c, "verification", None),
            note=c.note,
        )
        for c in session.query(CompteCible).filter_by(personne_id=personne_id).all()
    ]

    from backend.models import FicheFusionnee

    sites_par_id = {s_.id: s_ for s_ in session.query(Site).all()}
    return FicheOut(
        personne=_serialiser(
            personne, sites_par_id, _constats_par_badge(session)
        ),
        parcours=parcours,
        comptes=comptes,
        anciennes_fiches=[
            f.cle_pivot + (f" ({f.site})" if f.site else "")
            for f in session.query(FicheFusionnee)
            .filter_by(personne_id=personne_id)
            .order_by(FicheFusionnee.fusionnee_le)
        ],
    )


# ---------------------------------------------------------------------------
# L'enquête : ce que chaque source dit de cette personne
# ---------------------------------------------------------------------------


class DireOut(BaseModel):
    source: str
    consultee: bool
    valeurs: dict[str, str | None]
    motif: str | None


class DivergenceOut(BaseModel):
    quoi: str
    entre: tuple[str, str]
    valeurs: tuple[str | None, str | None]
    gravite: str


class EnqueteOut(BaseModel):
    personne_id: int
    libelle: str
    cle_pivot: str | None
    badge: int | None
    login: str | None
    adresse: str | None
    adresse_constatee: bool
    dires: list[DireOut]
    divergences: list[DivergenceOut]
    sources_consultees: list[str]
    tout_concorde: bool


@router.get("/{personne_id}/enquete", response_model=EnqueteOut)
def enquete(
    personne_id: int,
    annee_id: int | None = None,
    interroger_google: bool = True,
    session: Session = Depends(db_session),
) -> EnqueteOut:
    """Ce que chaque système dit de cette personne.

    Google est interrogé en direct — deux appels pour une seule personne,
    et c'est précisément la réponse qu'on vient chercher. Quand il n'est pas
    joignable, l'enquête le **dit** plutôt que de rendre une case vide : une
    absence de regard n'est pas une absence d'écart.
    """
    from backend.services.enquete_personne import enqueter

    etat_google = None
    groupes = None
    motif = None

    if interroger_google:
        personne = session.query(Personne).filter_by(id=personne_id).one_or_none()
        adresse = (
            (personne.email_constate or personne.email_attribuee or "").strip()
            if personne
            else ""
        )
        if not adresse:
            motif = (
                "Aucune adresse constatée : l'annuaire ne peut pas être "
                "interrogé sans risquer de désigner un homonyme."
            )
        else:
            from backend.services.google_api import ClientGoogle, charger_config

            try:
                client = ClientGoogle(charger_config(session))
                lus = client.lire_utilisateurs([adresse])
                decrit = lus.get(adresse.lower())
                if decrit is None:
                    etat_google = {"existe": False}
                else:
                    etat_google = {"existe": True, **decrit}
                    groupes = client.lister_groupes_de(adresse)
            except Exception as e:
                motif = f"Annuaire injoignable : {type(e).__name__}."
    else:
        motif = "Annuaire non interrogé — relance l'enquête pour le consulter."

    try:
        e = enqueter(
            session,
            personne_id,
            annee_id=annee_id,
            etat_google=etat_google,
            groupes_google=groupes,
            motif_google=motif,
        )
    except ValueError as err:
        raise HTTPException(404, str(err)) from None

    return EnqueteOut(
        personne_id=e.personne_id,
        libelle=e.libelle,
        cle_pivot=e.cle_pivot,
        badge=e.badge,
        login=e.login,
        adresse=e.adresse,
        adresse_constatee=e.adresse_constatee,
        dires=[DireOut(**vars(d)) for d in e.dires],
        divergences=[DivergenceOut(**vars(d)) for d in e.divergences],
        sources_consultees=e.sources_consultees,
        tout_concorde=e.tout_concorde,
    )
