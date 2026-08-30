"""Ce que Google détient d'un compte, confronté à ce que le référentiel attend.

## Pourquoi cet écran existe

Un import de masse répond « 238 créations réussies » et s'arrête là. Il ne
dit pas dans quelle unité d'organisation les comptes ont atterri, ni s'ils
sont actifs, ni si Google réclamera un changement de mot de passe à la
première connexion. Ces trois-là décident pourtant si l'élève pourra se
connecter le jour de la rentrée.

Vérifier deux comptes par site suffit : ils sont créés par le même fichier,
d'un seul geste. Ce qui vaut pour deux vaut pour les autres.

## Ce qui ne se vérifie pas, et pourquoi

**Le mot de passe.** L'API d'administration ne le lit pas et n'en contrôle
aucun ; la délégation de domaine agit *au nom d'un* utilisateur, ce qui
contourne le mot de passe au lieu de l'éprouver. Aucun appel ne peut donc
répondre à « le mot de passe est-il celui de KoXo ? ».

Ce n'est pas gênant, parce que la question se tranche ailleurs et mieux :
l'export Google est fabriqué en recopiant le mot de passe du fichier KoXo,
et l'écran des exports compte les lignes servies. Si ce compte égale le
nombre de lignes, la jointure est bonne pour toutes — pas seulement pour
l'échantillon. Seule reste une connexion réelle pour l'éprouver de bout en
bout, et c'est un geste humain.

## Ce qui se vérifie

- **Le compte existe** — l'adresse du référentiel désigne bien un compte.
- **Son unité d'organisation**, comparée aux deux que la Table prévoit pour
  sa classe : celle d'attente et celle de la classe. On dit laquelle est
  atteinte plutôt que d'en imposer une : entre la pré-rentrée et le jour J,
  les deux sont justes, à des moments différents.
- **Il n'est pas suspendu.**
- **Aucun changement de mot de passe n'est exigé** à la connexion suivante.
  C'est ce réglage qui, laissé à vrai, ferait diverger Google de l'annuaire
  dès la première session.
"""
from __future__ import annotations

from dataclasses import dataclass, field

from sqlalchemy.orm import Session

from backend.models import Personne, Site, Snapshot, TableCorrespondance


@dataclass
class CompteVerifie:
    """Un compte, tel que Google le décrit et tel qu'on l'attendait."""

    adresse: str
    trouve: bool

    nom: str = ""
    prenom: str = ""
    classe: str | None = None
    login: str | None = None

    ou_google: str | None = None
    ou_attendue_pre_rentree: str | None = None
    ou_attendue_definitive: str | None = None
    ou_reconnue: str | None = None
    """`pre_rentree`, `definitive`, ou `None` quand l'OU n'est ni l'une ni
    l'autre — le compte est ailleurs que là où la Table le prévoit."""

    suspendu: bool | None = None
    changement_mdp_exige: bool | None = None
    date_creation: str | None = None
    derniere_connexion: str | None = None

    anomalies: list[str] = field(default_factory=list)

    @property
    def est_conforme(self) -> bool:
        return self.trouve and not self.anomalies


@dataclass
class RapportVerification:
    annee_libelle: str = ""
    comptes: list[CompteVerifie] = field(default_factory=list)
    avertissements: list[str] = field(default_factory=list)

    @property
    def nb_verifies(self) -> int:
        return len(self.comptes)

    @property
    def nb_conformes(self) -> int:
        return sum(1 for c in self.comptes if c.est_conforme)

    @property
    def nb_introuvables(self) -> int:
        return sum(1 for c in self.comptes if not c.trouve)

    @property
    def tout_va_bien(self) -> bool:
        return bool(self.comptes) and self.nb_conformes == len(self.comptes)


def choisir_echantillon(
    session: Session,
    *,
    annee_id: int,
    par_site: int = 2,
    site_id: int | None = None,
) -> list[str]:
    """Quelques adresses par site, prises parmi les élèves de l'année.

    L'échantillon vise les comptes **les plus récemment créés** — ceux dont
    le référentiel ne connaît pas encore l'adresse constatée, c'est-à-dire
    ceux que l'import vient de faire naître. Ce sont eux qu'on veut voir :
    un compte ancien n'apprend rien sur l'import du jour.
    """
    if par_site < 1:
        raise ValueError(f"par_site doit valoir au moins 1 : {par_site}")

    sites = session.query(Site)
    if site_id is not None:
        sites = sites.filter(Site.id == site_id)

    presents = {
        s.personne_id
        for s in session.query(Snapshot.personne_id).filter_by(
            annee_scolaire_id=annee_id
        )
    }

    adresses: list[str] = []
    for site in sites.order_by(Site.numero_ordre).all():
        candidats = [
            p
            for p in session.query(Personne)
            .filter_by(type="eleve", site_id=site.id)
            .order_by(Personne.id.desc())
            .all()
            if p.id in presents and p.email
        ]
        # Les entrants d'abord : c'est leur création qu'on contrôle.
        candidats.sort(key=lambda p: (bool(p.email_constate), -p.id))
        adresses += [p.email for p in candidats[:par_site]]
    return adresses


def verifier_comptes(
    session: Session,
    comptes_google: dict[str, dict | None],
    *,
    annee_id: int,
) -> RapportVerification:
    """Confronte ce que Google renvoie à ce que le référentiel attend.

    Args:
        comptes_google: `{adresse: description}` telle que
            `ClientGoogle.lire_utilisateurs` la produit. La valeur `None`
            signale une adresse que Google ne connaît pas.
        annee_id: l'année dont on tire la classe de chacun.
    """
    from backend.models import AnneeScolaire

    annee = session.query(AnneeScolaire).filter_by(id=annee_id).one_or_none()
    if annee is None:
        raise ValueError(f"Année introuvable : {annee_id}")

    rapport = RapportVerification(annee_libelle=annee.libelle)

    par_adresse: dict[str, Personne] = {}
    for p in session.query(Personne).all():
        for champ in (p.email, p.email_constate):
            if champ:
                par_adresse.setdefault(champ.strip().lower(), p)

    derniers: dict[int, Snapshot] = {}
    for snap in (
        session.query(Snapshot)
        .filter_by(annee_scolaire_id=annee_id)
        .order_by(Snapshot.date_ingestion)
        .all()
    ):
        derniers[snap.personne_id] = snap

    ou_par_classe = {
        (tc.site_id, tc.classe_code_court): (tc.ou_pre_rentree, tc.ou_definitive)
        for tc in session.query(TableCorrespondance).all()
    }

    for adresse, brut in comptes_google.items():
        cle = (adresse or "").strip().lower()
        compte = CompteVerifie(adresse=cle, trouve=brut is not None)
        personne = par_adresse.get(cle)

        if personne is not None:
            compte.nom = personne.nom or ""
            compte.prenom = personne.prenom or ""
            compte.login = personne.login
            snap = derniers.get(personne.id)
            compte.classe = snap.classe if snap else None
            ous = ou_par_classe.get((personne.site_id, compte.classe or ""))
            if ous:
                compte.ou_attendue_pre_rentree, compte.ou_attendue_definitive = ous
        else:
            compte.anomalies.append(
                "aucune personne du référentiel ne porte cette adresse"
            )

        if brut is None:
            compte.anomalies.append("aucun compte Google à cette adresse")
            rapport.comptes.append(compte)
            continue

        compte.ou_google = brut.get("ou")
        compte.suspendu = brut.get("suspendu")
        compte.changement_mdp_exige = brut.get("changement_mdp_exige")
        compte.date_creation = brut.get("date_creation")
        compte.derniere_connexion = brut.get("derniere_connexion")

        if compte.ou_google == compte.ou_attendue_pre_rentree:
            compte.ou_reconnue = "pre_rentree"
        elif compte.ou_google == compte.ou_attendue_definitive:
            compte.ou_reconnue = "definitive"
        elif compte.ou_attendue_pre_rentree or compte.ou_attendue_definitive:
            compte.anomalies.append(
                f"unité d'organisation inattendue : {compte.ou_google!r}"
            )

        if compte.suspendu:
            compte.anomalies.append("compte suspendu")
        if compte.changement_mdp_exige:
            # Le mot de passe vient de KoXo et figure sur la fiche de
            # l'élève ; le faire changer le ferait diverger de l'annuaire.
            compte.anomalies.append(
                "Google exigera un changement de mot de passe à la connexion"
            )

        rapport.comptes.append(compte)

    rapport.avertissements.append(
        "Le mot de passe lui-même ne se vérifie pas : l'API d'administration "
        "ne le lit pas. Qu'il vienne bien de KoXo se contrôle à la génération "
        "de l'export, où le nombre de lignes servies est affiché."
    )
    return rapport
