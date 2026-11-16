"""Endpoints du parc : états, pannes, prélèvements, accessoires.

Lecture d'un côté, gestes de l'autre. `GET /atelier` propose un plan de
remontage et n'écrit rien ; c'est `POST /prelever` qui l'applique, une
pièce à la fois — on ne lance pas un atelier entier d'un bouton, parce que
c'est le tournevis qui décide si la pièce entre vraiment.
"""
from __future__ import annotations

from dataclasses import asdict
from datetime import date, datetime

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session

from backend.database import db_session
from backend.models.parc_materiel import (
    ETATS_ACCESSOIRE,
    ETATS_MACHINE,
    ORGANES,
    TYPES_ACCESSOIRE,
)
from backend.services.parc_materiel import (
    GesteImpossible,
    affecter,
    analyser_atelier,
    changer_etat,
    declarer_panne,
    enregistrer_accessoire,
    etat_du_parc,
    etat_du_stock,
    preter,
    prelever,
    rendre,
    resoudre_panne,
)

router = APIRouter(prefix="/api/parc", tags=["parc"])


def _geste(action):
    """Traduit un refus métier en 400, avec son message tel quel."""
    try:
        return action()
    except GesteImpossible as e:
        raise HTTPException(400, str(e)) from None


# ---------------------------------------------------------------------------
# Vocabulaire — l'interface ne réinvente pas les listes
# ---------------------------------------------------------------------------


class VocabulaireOut(BaseModel):
    etats_machine: list[str]
    organes: list[str]
    etats_accessoire: list[str]
    types_accessoire: list[str]
    raisons: dict[str, str] = {}
    """`{code: libellé}` — pourquoi une machine change de mains."""


@router.get("/vocabulaire", response_model=VocabulaireOut)
def vocabulaire() -> VocabulaireOut:
    """Les listes fermées, servies au front pour qu'il n'en invente pas."""
    from backend.models.parc_inventaire import RAISONS

    return VocabulaireOut(
        etats_machine=list(ETATS_MACHINE),
        organes=list(ORGANES),
        etats_accessoire=list(ETATS_ACCESSOIRE),
        types_accessoire=list(TYPES_ACCESSOIRE),
        raisons=dict(RAISONS),
    )


# ---------------------------------------------------------------------------
# Machines
# ---------------------------------------------------------------------------


class MachineOut(BaseModel):
    serie: str
    etat: str
    etat_depuis: date | None
    attribue_a: str | None
    attribue_le: date | None
    note: str | None
    pannes_ouvertes: list[str]


class ParcOut(BaseModel):
    machines: list[MachineOut]
    en_service: int
    en_stock: int
    hs: int
    reforme: int


@router.get("/machines", response_model=ParcOut)
def lister_machines(session: Session = Depends(db_session)) -> ParcOut:
    machines, synthese = etat_du_parc(session)
    return ParcOut(
        machines=[MachineOut(**asdict(m)) for m in machines],
        **asdict(synthese),
    )


class EtatPayload(BaseModel):
    etat: str
    note: str | None = None


@router.post("/machines/{serie}/etat", response_model=MachineOut)
def poser_etat(
    serie: str, payload: EtatPayload, session: Session = Depends(db_session)
) -> MachineOut:
    _geste(lambda: changer_etat(session, serie, payload.etat, note=payload.note))
    machines, _ = etat_du_parc(session)
    return MachineOut(**asdict(next(m for m in machines if m.serie == serie)))


class AffectationPayload(BaseModel):
    attribue_a: str | None = None
    """À qui la machine est confiée. `null` la reprend."""
    depuis: date | None = None
    note: str | None = None


@router.post("/machines/{serie}/affecter", response_model=MachineOut)
def affecter_machine(
    serie: str, payload: AffectationPayload, session: Session = Depends(db_session)
) -> MachineOut:
    """Confie une machine à quelqu'un, ou la reprend.

    L'état suit : confiée elle passe en service, reprise elle retourne au
    stock — sauf si elle est HS, auquel cas la reprendre ne la répare pas.
    """
    _geste(
        lambda: affecter(
            session,
            serie,
            a=payload.attribue_a,
            depuis=payload.depuis,
            note=payload.note,
        )
    )
    machines, _ = etat_du_parc(session)
    return MachineOut(**asdict(next(m for m in machines if m.serie == serie)))


class PannePayload(BaseModel):
    organe: str
    note: str | None = None
    passer_hs: bool = True
    """À faux, on consigne le défaut sans retirer la machine du service."""


class PanneOut(BaseModel):
    id: int
    serie: str
    organe: str
    constatee_le: date | None
    note: str | None
    resolue_le: date | None
    resolution: str | None
    prelevee_pour: str | None


@router.post("/machines/{serie}/panne", response_model=PanneOut)
def poser_panne(
    serie: str, payload: PannePayload, session: Session = Depends(db_session)
) -> PanneOut:
    p = _geste(
        lambda: declarer_panne(
            session,
            serie,
            payload.organe,
            note=payload.note,
            passer_hs=payload.passer_hs,
        )
    )
    return PanneOut(**{c: getattr(p, c) for c in PanneOut.model_fields})


@router.get("/machines/{serie}/pannes", response_model=list[PanneOut])
def lister_pannes(
    serie: str, session: Session = Depends(db_session)
) -> list[PanneOut]:
    """Toutes les pannes de la machine, ouvertes comme refermées.

    L'historique compte autant que l'état : savoir qu'un écran a déjà été
    remplacé une fois change le regard qu'on porte sur la machine.
    """
    from backend.models import PanneChromebook

    lignes = (
        session.query(PanneChromebook)
        .filter_by(serie=serie)
        .order_by(PanneChromebook.constatee_le.desc(), PanneChromebook.id.desc())
        .all()
    )
    return [PanneOut(**{c: getattr(p, c) for c in PanneOut.model_fields}) for p in lignes]


class ResolutionPayload(BaseModel):
    resolution: str = "reparee"


@router.post("/pannes/{panne_id}/resoudre", response_model=PanneOut)
def fermer_panne(
    panne_id: int, payload: ResolutionPayload, session: Session = Depends(db_session)
) -> PanneOut:
    p = _geste(lambda: resoudre_panne(session, panne_id, payload.resolution))
    return PanneOut(**{c: getattr(p, c) for c in PanneOut.model_fields})


# ---------------------------------------------------------------------------
# L'atelier
# ---------------------------------------------------------------------------


class RemontageOut(BaseModel):
    serie: str
    organes_manquants: list[str]
    donneurs: dict[str, str]


class AtelierOut(BaseModel):
    machines_hs: list[MachineOut]
    remontages: list[RemontageOut]
    organes_disponibles: dict[str, int]
    bloquees: list[tuple[str, list[str]]]
    nb_remontables: int


@router.get("/atelier", response_model=AtelierOut)
def atelier(session: Session = Depends(db_session)) -> AtelierOut:
    """Ce que la réserve de pièces permet de remonter. N'écrit rien."""
    a = analyser_atelier(session)
    return AtelierOut(
        machines_hs=[MachineOut(**asdict(m)) for m in a.machines_hs],
        remontages=[RemontageOut(**asdict(r)) for r in a.remontages],
        organes_disponibles=a.organes_disponibles,
        bloquees=a.bloquees,
        nb_remontables=a.nb_remontables,
    )


class PrelevementPayload(BaseModel):
    depuis: str
    vers: str
    organe: str
    note: str | None = None


@router.post("/prelever")
def poser_prelevement(
    payload: PrelevementPayload, session: Session = Depends(db_session)
) -> dict:
    """Prend un organe sur une machine pour en réparer une autre."""
    resolue, creee = _geste(
        lambda: prelever(
            session,
            depuis=payload.depuis,
            vers=payload.vers,
            organe=payload.organe,
            note=payload.note,
        )
    )
    machines, _ = etat_du_parc(session)
    par_serie = {m.serie: m for m in machines}
    return {
        "organe": payload.organe,
        "receveuse": MachineOut(**asdict(par_serie[payload.vers])).model_dump(),
        "donneuse": MachineOut(**asdict(par_serie[payload.depuis])).model_dump(),
    }


# ---------------------------------------------------------------------------
# Accessoires
# ---------------------------------------------------------------------------


class AccessoireOut(BaseModel):
    serie: str
    type: str
    etat: str
    note: str | None
    prete_a: str | None
    prete_le: date | None
    retour_prevu_le: date | None
    pret_id: int | None
    en_retard: bool
    definitif: bool = False


class StockOut(BaseModel):
    accessoires: list[AccessoireOut]
    par_type: dict[str, dict[str, int]]
    nb_en_retard: int


def _stock_vers_out(stock) -> StockOut:
    return StockOut(
        accessoires=[
            AccessoireOut(**asdict(a), en_retard=a.en_retard) for a in stock.accessoires
        ],
        par_type=stock.par_type,
        nb_en_retard=len(stock.en_retard),
    )


@router.get("/accessoires", response_model=StockOut)
def lister_accessoires(session: Session = Depends(db_session)) -> StockOut:
    return _stock_vers_out(etat_du_stock(session))


class NouvelAccessoirePayload(BaseModel):
    serie: str | None = None
    """Vide : le programme donne un numéro maison (`CH-001`)."""
    type: str = "chargeur"
    note: str | None = None


@router.post("/accessoires", response_model=StockOut)
def ajouter_accessoire(
    payload: NouvelAccessoirePayload, session: Session = Depends(db_session)
) -> StockOut:
    _geste(
        lambda: enregistrer_accessoire(
            session, payload.serie, type_accessoire=payload.type, note=payload.note
        )
    )
    return _stock_vers_out(etat_du_stock(session))


class LotPayload(BaseModel):
    type: str = "chargeur"
    nombre: int
    note: str | None = None


@router.post("/accessoires/lot", response_model=StockOut)
def ajouter_lot(payload: LotPayload, session: Session = Depends(db_session)) -> StockOut:
    """Un carton de chargeurs sans numéro : le programme les numérote."""
    from backend.services.parc_materiel import enregistrer_lot

    _geste(
        lambda: enregistrer_lot(
            session, type_accessoire=payload.type, nombre=payload.nombre, note=payload.note
        )
    )
    return _stock_vers_out(etat_du_stock(session))


class PretPayload(BaseModel):
    a_qui: str
    retour_prevu_le: date | None = None
    note: str | None = None
    definitif: bool = False
    """Donné, et non prêté : il ne reviendra pas."""


@router.post("/accessoires/{serie}/preter", response_model=StockOut)
def sortir_accessoire(
    serie: str, payload: PretPayload, session: Session = Depends(db_session)
) -> StockOut:
    _geste(
        lambda: preter(
            session,
            serie,
            a_qui=payload.a_qui,
            retour_prevu_le=payload.retour_prevu_le,
            note=payload.note,
            definitif=payload.definitif,
        )
    )
    return _stock_vers_out(etat_du_stock(session))


class RetourPayload(BaseModel):
    etat: str = "en_stock"
    """L'objet peut revenir cassé : le retour dit dans quel état."""


@router.post("/accessoires/{serie}/rendre", response_model=StockOut)
def rentrer_accessoire(
    serie: str, payload: RetourPayload, session: Session = Depends(db_session)
) -> StockOut:
    _geste(lambda: rendre(session, serie, etat=payload.etat))
    return _stock_vers_out(etat_du_stock(session))


# ---------------------------------------------------------------------------
# L'inventaire : tout le parc, lu chez Google et superposé au suivi
# ---------------------------------------------------------------------------


class PosteOut(BaseModel):
    serie: str
    modele: str
    ou: str
    categorie: str
    site: str | None
    statut_google: str | None
    etiquette: str
    emplacement: str
    etat: str
    porteur: str | None
    porteur_nom: str | None
    porteur_detail: str | None
    porteur_parti: bool | None
    tenue_par: str | None
    lieu: str | None
    depuis: date | None
    pannes: list[str]
    derniere_synchro: str | None
    derniers_utilisateurs: list[str]
    dort: bool
    fin_maj: date | None
    note: str | None
    source: str
    a_reporter: list[str]
    etiquette_voulue: str | None
    emplacement_voulu: str | None
    ou_voulue: str | None
    a_verifier: str | None
    present_google: bool
    pointe_le: date | None = None
    porteur_probable: str | None = None
    porteur_probable_nom: str | None = None


def _poste_out(p) -> PosteOut:
    return PosteOut(**{k: getattr(p, k) for k in PosteOut.model_fields})


class FinMajOut(BaseModel):
    depassee: int
    cette_annee: int
    l_an_prochain: int


class InventaireOut(BaseModel):
    postes: list[PosteOut]
    par_etat: dict[str, int]
    par_categorie: dict[str, int]
    chargeurs_en_stock: int
    seuils: dict[str, int]
    alertes: list[str]
    fin_maj: FinMajOut
    releve_le: datetime | None
    nb_a_reporter: int
    pointage_depuis: date | None = None
    pointees: int = 0
    a_pointer: int = 0


def _inventaire_out(session) -> InventaireOut:
    from backend.services.parc_inventaire import inventaire

    inv = inventaire(session)
    return InventaireOut(
        postes=[_poste_out(p) for p in inv.postes],
        par_etat=inv.par_etat,
        par_categorie=inv.par_categorie,
        chargeurs_en_stock=inv.chargeurs_en_stock,
        seuils=inv.seuils,
        alertes=inv.alertes,
        fin_maj=FinMajOut(**asdict(inv.fin_maj)),
        releve_le=inv.releve_le,
        nb_a_reporter=inv.nb_a_reporter,
        pointage_depuis=inv.pointage_depuis,
        pointees=inv.pointees,
        a_pointer=inv.a_pointer,
    )


@router.get("/inventaire", response_model=InventaireOut)
def lire_inventaire(session: Session = Depends(db_session)) -> InventaireOut:
    """Le parc tel que le programme le comprend. Ne lit pas Google : le dernier relevé."""
    return _inventaire_out(session)


def _client_google(session):
    from backend.services.google_api import ClientGoogle, charger_config

    try:
        return ClientGoogle(charger_config(session))
    except ValueError as e:
        raise HTTPException(400, str(e)) from None


class ReleveOut(BaseModel):
    nb: int
    nouveaux: int
    disparus: int
    reconcilies: int
    inventaire: InventaireOut


@router.post("/releve", response_model=ReleveOut)
def relever_flotte(session: Session = Depends(db_session)) -> ReleveOut:
    """Relit la flotte chez Google et garde ce qu'elle dit. Lecture seule côté Google."""
    from backend.services.parc_inventaire import enregistrer_releve

    client = _client_google(session)
    if not client.appareils_disponibles:
        raise HTTPException(
            400,
            "Le droit de lecture des Chromebooks n'est pas accordé au compte de "
            "service. Ajoute le champ d'application "
            "admin.directory.device.chromeos.readonly à la délégation, dans la "
            "console d'administration.",
        )
    try:
        appareils = client.lister_appareils()
    except Exception as e:
        raise HTTPException(502, f"Lecture Google impossible : {type(e).__name__}: {e}")
    r = enregistrer_releve(session, appareils)
    return ReleveOut(**asdict(r), inventaire=_inventaire_out(session))


class EchangePayload(BaseModel):
    ancienne: str | None = None
    nouvelle: str | None = None
    porteur: str | None = None
    raison: str
    precision: str | None = None
    devenir: str = "stock"
    organes: list[str] = []
    etiquette_ancienne: str | None = None
    chargeur: str | None = None
    ecrire_google: bool = True
    """Reporter tout de suite les étiquettes dans la console."""


class EcritureGoogleOut(BaseModel):
    serie: str
    ok: bool
    message: str


class EchangeOut(BaseModel):
    message: str
    google: list[EcritureGoogleOut]
    inventaire: InventaireOut


@router.post("/echanger", response_model=EchangeOut)
def poser_echange(payload: EchangePayload, session: Session = Depends(db_session)) -> EchangeOut:
    """Remet, reprend ou échange une machine, puis écrit les étiquettes dans Google.

    Le geste est noté d'abord. L'écriture Google vient après, et son échec
    n'annule rien : la machine reste parmi les étiquettes à reporter.
    """
    from backend.services.parc_inventaire import echanger, ecrire_dans_google

    recu = _geste(
        lambda: echanger(
            session,
            ancienne=payload.ancienne,
            nouvelle=payload.nouvelle,
            porteur=payload.porteur,
            raison=payload.raison,
            precision=payload.precision,
            devenir=payload.devenir,
            organes=payload.organes,
            etiquette_ancienne=payload.etiquette_ancienne,
            chargeur=payload.chargeur,
        )
    )
    google: list[EcritureGoogleOut] = []
    if payload.ecrire_google and recu.a_ecrire:
        try:
            client = _client_google(session)
            google = [
                EcritureGoogleOut(**asdict(r))
                for r in ecrire_dans_google(session, client, recu.a_ecrire)
            ]
        except HTTPException as e:
            google = [
                EcritureGoogleOut(serie=s, ok=False, message=str(e.detail))
                for s in recu.a_ecrire
            ]
    return EchangeOut(message=recu.message, google=google, inventaire=_inventaire_out(session))


class ReporterPayload(BaseModel):
    series: list[str] | None = None
    """Vide : toutes les machines dont l'étiquette Google est en retard."""


class ReporterOut(BaseModel):
    google: list[EcritureGoogleOut]
    inventaire: InventaireOut


@router.post("/google/reporter", response_model=ReporterOut)
def reporter_dans_google(
    payload: ReporterPayload, session: Session = Depends(db_session)
) -> ReporterOut:
    """Écrit dans la console les étiquettes que les gestes notés ici attendent."""
    from backend.services.parc_inventaire import ecrire_dans_google, series_a_reporter

    series = payload.series or series_a_reporter(session)
    client = _client_google(session)
    resultats = ecrire_dans_google(session, client, series)
    return ReporterOut(
        google=[EcritureGoogleOut(**asdict(r)) for r in resultats],
        inventaire=_inventaire_out(session),
    )


class EntreeStockPayload(BaseModel):
    precision: str | None = None


@router.post("/machines/{serie}/stock", response_model=InventaireOut)
def mettre_au_stock(
    serie: str, payload: EntreeStockPayload, session: Session = Depends(db_session)
) -> InventaireOut:
    """Déclare une machine disponible — neuve, ou réparée hors du programme."""
    from backend.services.parc_inventaire import entrer_au_stock

    _geste(lambda: entrer_au_stock(session, serie, precision=payload.precision))
    return _inventaire_out(session)


class MouvementOut(BaseModel):
    id: int
    quand: datetime
    objet: str
    serie: str
    geste: str
    de: str | None
    vers: str | None
    raison: str | None
    precision: str | None
    autre_serie: str | None
    google: str | None


@router.get("/journal", response_model=list[MouvementOut])
def lire_journal(
    serie: str | None = None,
    personne: str | None = None,
    limite: int = 300,
    session: Session = Depends(db_session),
) -> list[MouvementOut]:
    from backend.services.parc_inventaire import journal

    return [
        MouvementOut(**{k: getattr(m, k) for k in MouvementOut.model_fields})
        for m in journal(session, serie=serie, personne=personne, limite=min(limite, 2000))
    ]


class FicheOut(BaseModel):
    poste: PosteOut | None
    pannes: list[PanneOut]
    journal: list[MouvementOut]


@router.get("/machines/{serie}/fiche", response_model=FicheOut)
def fiche_machine(serie: str, session: Session = Depends(db_session)) -> FicheOut:
    """Tout ce qu'on sait d'une machine : où elle est, ses pannes, son histoire."""
    from backend.models import PanneChromebook
    from backend.services.parc_inventaire import inventaire, journal

    poste = next((p for p in inventaire(session).postes if p.serie == serie), None)
    pannes = (
        session.query(PanneChromebook)
        .filter_by(serie=serie)
        .order_by(PanneChromebook.constatee_le.desc(), PanneChromebook.id.desc())
        .all()
    )
    return FicheOut(
        poste=_poste_out(poste) if poste else None,
        pannes=[PanneOut(**{c: getattr(p, c) for c in PanneOut.model_fields}) for p in pannes],
        journal=[
            MouvementOut(**{k: getattr(m, k) for k in MouvementOut.model_fields})
            for m in journal(session, serie=serie)
        ],
    )


class PersonneChoixOut(BaseModel):
    adresse: str
    nom: str
    prenom: str
    type: str
    detail: str | None
    inscrit: bool


@router.get("/personnes", response_model=list[PersonneChoixOut])
def personnes_choisissables(session: Session = Depends(db_session)) -> list[PersonneChoixOut]:
    """Les inscrits de l'année qui ont une adresse — à qui confier, à qui donner."""
    from backend.services.parc_inventaire import annuaire

    gens = [p for p in annuaire(session).values() if p.inscrit]
    gens.sort(key=lambda p: (p.type == "eleve", p.nom.lower(), p.prenom.lower()))
    return [PersonneChoixOut(**asdict(p)) for p in gens]


class DetentionOut(BaseModel):
    adresse: str
    nom: str | None
    detail: str | None
    inscrit: bool | None
    machines: list[PosteOut]
    accessoires: list[dict]


@router.get("/detient", response_model=DetentionOut)
def ce_que_detient(adresse: str, session: Session = Depends(db_session)) -> DetentionOut:
    from backend.services.parc_inventaire import detient

    d = detient(session, adresse)
    return DetentionOut(
        adresse=d.adresse,
        nom=d.nom,
        detail=d.detail,
        inscrit=d.inscrit,
        machines=[_poste_out(p) for p in d.machines],
        accessoires=d.accessoires,
    )


class PointagePayload(BaseModel):
    depuis: date | None = None


@router.post("/pointage/commencer", response_model=InventaireOut)
def ouvrir_pointage(payload: PointagePayload, session: Session = Depends(db_session)) -> InventaireOut:
    """Ouvre un inventaire physique : tout ce qui a été vu avant est à revoir."""
    from backend.services.parc_inventaire import commencer_pointage

    commencer_pointage(session, payload.depuis)
    return _inventaire_out(session)


class ConstatPayload(BaseModel):
    constat: str
    porteur: str | None = None
    lieu: str | None = None
    organes: list[str] = []
    note: str | None = None


class ConstatOut(BaseModel):
    message: str
    inventaire: InventaireOut


@router.post("/machines/{serie}/pointer", response_model=ConstatOut)
def pointer_machine(
    serie: str, payload: ConstatPayload, session: Session = Depends(db_session)
) -> ConstatOut:
    """Note ce qu'on constate d'une machine pendant l'inventaire. N'écrit pas dans Google."""
    from backend.services.parc_inventaire import pointer

    message = _geste(
        lambda: pointer(
            session,
            serie,
            constat=payload.constat,
            porteur=payload.porteur,
            lieu=payload.lieu,
            organes=payload.organes,
            note=payload.note,
        )
    )
    return ConstatOut(message=message, inventaire=_inventaire_out(session))


class SeuilsPayload(BaseModel):
    machines: int | None = None
    chargeurs: int | None = None


@router.post("/seuils", response_model=dict[str, int])
def regler_seuils(payload: SeuilsPayload, session: Session = Depends(db_session)) -> dict:
    """En dessous, le parc le signale : il est temps de commander."""
    from backend.services.parc_inventaire import poser_seuils

    return poser_seuils(session, payload.model_dump(exclude_none=True))
