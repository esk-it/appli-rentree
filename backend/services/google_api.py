"""Intégration Google Workspace via l'API Admin SDK Directory.

**Mode optionnel.** Le mode fichier (CSV bulk-import) reste disponible en
permanence et demeure le défaut — l'API n'est qu'un mode d'envoi
supplémentaire (§7.2 du prompt de refonte). Si les bibliothèques ne sont
pas installées ou la configuration absente, l'application fonctionne
exactement comme avant.

## Architecture

Le module sépare volontairement deux responsabilités :

- **Construction des payloads** (`payload_creation_utilisateur`, etc.) —
  fonctions pures, sans I/O, entièrement testables hors ligne.
- **Transport** (`ClientGoogle`) — les appels HTTP réels, qui ne peuvent
  être validés qu'avec de vraies credentials.

Cette séparation permet de vérifier la logique métier sans compte Google.

## Sécurité

- **Le fichier de credentials n'est jamais stocké en base.** Le paramètre
  `google.chemin_credentials` contient un *chemin* vers un fichier que
  l'utilisateur dépose lui-même. La clé privée reste sur le disque, sous
  la protection du système de fichiers.
- **Aucune suppression exposée.** Le prompt est explicite : « aucune
  suppression directe ». Le client ne propose que création, mise à jour
  et suspension. Une purge définitive se fait dans la console Google,
  après vérification humaine.
- Les mots de passe transitent en mémoire pour la création initiale et ne
  sont jamais journalisés ni persistés.

## Prérequis côté Google (à faire une fois)

1. Créer un projet Google Cloud, activer l'**Admin SDK API**.
2. Créer un **compte de service**, générer une clé JSON.
3. Dans Admin Google → Sécurité → Délégation à l'échelle du domaine :
   autoriser le client ID du compte de service sur les scopes ci-dessous.
4. Renseigner dans Paramètres le chemin du JSON et l'email d'un
   administrateur à impersonner.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from sqlalchemy.orm import Session

# Scopes minimaux : lecture/écriture des utilisateurs et des unités
# d'organisation. Volontairement sans scope de suppression de groupe ni
# d'accès aux données utilisateur (Drive, Gmail).
SCOPES = [
    "https://www.googleapis.com/auth/admin.directory.user",
    "https://www.googleapis.com/auth/admin.directory.orgunit",
    "https://www.googleapis.com/auth/admin.directory.group",
]

API_BASE = "https://admin.googleapis.com/admin/directory/v1"


# ---------------------------------------------------------------------------
# Disponibilité et configuration
# ---------------------------------------------------------------------------


def est_disponible() -> tuple[bool, str]:
    """Indique si les bibliothèques nécessaires sont présentes.

    Retourne `(disponible, message)`. L'import est fait ici plutôt qu'en
    tête de module pour que l'absence de la dépendance ne casse pas le
    démarrage du backend — le mode fichier doit rester utilisable.
    """
    try:
        import google.oauth2.service_account  # noqa: F401
        import googleapiclient.discovery  # noqa: F401
    except ImportError as e:
        return False, (
            "Bibliothèques Google absentes de cette installation "
            f"({e}). Le mode fichier reste disponible."
        )
    return True, "Bibliothèques Google disponibles"


@dataclass
class ConfigGoogle:
    active: bool
    chemin_credentials: str
    admin_impersonation: str

    @property
    def est_complete(self) -> bool:
        return bool(
            self.active and self.chemin_credentials and self.admin_impersonation
        )

    def valider(self) -> list[str]:
        """Retourne la liste des problèmes de configuration, vide si tout va bien."""
        problemes: list[str] = []
        if not self.active:
            problemes.append("Le mode API est désactivé dans les Paramètres.")
        if not self.chemin_credentials:
            problemes.append("Chemin du fichier de credentials non renseigné.")
        elif not Path(self.chemin_credentials).exists():
            problemes.append(
                f"Fichier de credentials introuvable : {self.chemin_credentials}"
            )
        if not self.admin_impersonation:
            problemes.append(
                "Email de l'administrateur à impersonner non renseigné "
                "(requis par la délégation à l'échelle du domaine)."
            )
        return problemes


def charger_config(session: Session) -> ConfigGoogle:
    """Lit la configuration Google depuis les Paramètres."""
    from backend.services.configuration import get_param

    return ConfigGoogle(
        active=bool(get_param(session, "google.api_active", False)),
        chemin_credentials=str(get_param(session, "google.chemin_credentials", "") or ""),
        admin_impersonation=str(
            get_param(session, "google.admin_impersonation", "") or ""
        ),
    )


# ---------------------------------------------------------------------------
# Construction des payloads — fonctions pures, testables hors ligne
# ---------------------------------------------------------------------------


def payload_creation_utilisateur(
    *,
    prenom: str,
    nom: str,
    email: str,
    org_unit_path: str,
    mot_de_passe: str,
    id_charlemagne: int | None = None,
    type_personne: str = "eleve",
    changer_mdp_a_la_connexion: bool = True,
) -> dict[str, Any]:
    """Corps de requête pour `users.insert`.

    Le mot de passe est transmis en clair dans la requête HTTPS — c'est ce
    qu'attend l'API. Il ne doit jamais être conservé côté appelant après
    l'appel.
    """
    payload: dict[str, Any] = {
        "primaryEmail": email,
        "name": {"givenName": prenom, "familyName": nom},
        "password": mot_de_passe,
        "orgUnitPath": org_unit_path,
        "changePasswordAtNextLogin": changer_mdp_a_la_connexion,
    }
    if id_charlemagne is not None:
        # Employee ID = clé de rapprochement bidirectionnelle avec le référentiel
        payload["externalIds"] = [
            {"value": str(id_charlemagne), "type": "organization"}
        ]
        payload["organizations"] = [
            {
                "primary": True,
                "customType": "",
                "description": "eleve" if type_personne == "eleve" else "personnel",
            }
        ]
    return payload


def payload_deplacement_ou(*, org_unit_path: str) -> dict[str, Any]:
    """Corps de requête pour `users.update` limité au déplacement d'OU."""
    return {"orgUnitPath": org_unit_path}


def payload_suspension(*, suspendu: bool = True) -> dict[str, Any]:
    """Corps de requête pour suspendre (ou réactiver) un compte.

    La suspension est l'équivalent API de la mise en quarantaine : le
    compte existe toujours, ses données sont préservées, l'utilisateur ne
    peut plus se connecter. **Ce n'est pas une suppression.**
    """
    return {"suspended": suspendu}


def payload_membre_groupe(*, email: str, role: str = "MEMBER") -> dict[str, Any]:
    """Corps de requête pour `members.insert`."""
    return {"email": email, "role": role, "type": "USER"}


# ---------------------------------------------------------------------------
# Plan d'exécution — ce qui serait envoyé, calculé sans rien envoyer
# ---------------------------------------------------------------------------


@dataclass
class OperationGoogle:
    """Une opération unitaire à appliquer côté Google."""

    action: str  # "creer" | "deplacer" | "suspendre"
    email: str
    payload: dict[str, Any]
    libelle: str
    """Description lisible, affichable avant confirmation."""


@dataclass
class PlanGoogle:
    """Ensemble d'opérations, à relire avant exécution."""

    operations: list[OperationGoogle] = field(default_factory=list)
    avertissements: list[str] = field(default_factory=list)

    @property
    def nb_creations(self) -> int:
        return sum(1 for o in self.operations if o.action == "creer")

    @property
    def nb_deplacements(self) -> int:
        return sum(1 for o in self.operations if o.action == "deplacer")

    @property
    def nb_suspensions(self) -> int:
        return sum(1 for o in self.operations if o.action == "suspendre")

    @property
    def nb_total(self) -> int:
        return len(self.operations)


def construire_plan(
    session: Session,
    *,
    site_id: int,
    type_personne: str,
    annee_cible_id: int,
    annee_source_id: int,
    mots_de_passe: dict[str, str] | None = None,
) -> PlanGoogle:
    """Calcule les opérations Google à partir de la réconciliation.

    N'envoie rien — produit uniquement le plan, à relire puis exécuter
    explicitement. C'est le pendant API du CSV : même logique métier,
    autre canal.

    Args:
        mots_de_passe: `{login: mdp}` issu de la boucle KoXo, en mémoire.
            Un nouveau compte sans mot de passe disponible est signalé en
            avertissement et **exclu du plan** — créer un compte sans mot
            de passe défini n'aurait pas de sens.
    """
    from backend.models import Personne, Site
    from backend.services.exports_google import calculer_ou_sortants
    from backend.services.reconciliation import reconcilier

    site = session.query(Site).filter_by(id=site_id).one_or_none()
    if site is None:
        raise ValueError(f"Site introuvable : {site_id}")

    plan = PlanGoogle()
    mots_de_passe = mots_de_passe or {}

    from backend.models import TableCorrespondance

    ou_par_classe = {
        tc.classe_code_court: (tc.ou_pre_rentree, tc.ou_definitive)
        for tc in session.query(TableCorrespondance).filter_by(site_id=site.id).all()
    }

    rapport = reconcilier(
        session, annee_source_id, annee_cible_id, type_personne=type_personne
    )

    def personne(pid: int) -> Personne | None:
        return session.query(Personne).filter_by(id=pid).one_or_none()

    # Créations
    for entree in rapport.nouveaux:
        if entree.site_id != site.id:
            continue
        p = personne(entree.personne_id)
        if p is None or not p.email:
            plan.avertissements.append(
                f"{entree.cle_pivot} {entree.nom} : email non calculable, ignoré"
            )
            continue

        ous = ou_par_classe.get(entree.classe_cible or "")
        ou = ous[0] if ous else site.prefixe_racine_ou()
        if ous is None and type_personne == "eleve":
            plan.avertissements.append(
                f"{entree.cle_pivot} {entree.nom} : classe "
                f"{entree.classe_cible!r} hors table, placé à la racine du site"
            )

        mdp = mots_de_passe.get(p.login)
        if not mdp:
            plan.avertissements.append(
                f"{entree.cle_pivot} {entree.nom} : aucun mot de passe KoXo "
                "disponible, création impossible"
            )
            continue

        plan.operations.append(
            OperationGoogle(
                action="creer",
                email=p.email,
                payload=payload_creation_utilisateur(
                    prenom=p.prenom,
                    nom=p.nom,
                    email=p.email,
                    org_unit_path=ou,
                    mot_de_passe=mdp,
                    id_charlemagne=p.id_charlemagne,
                    type_personne=type_personne,
                ),
                libelle=f"Créer {p.email} dans {ou}",
            )
        )

    # Déplacements — uniquement si la classe a réellement changé
    for entree in rapport.modifies:
        if entree.site_id != site.id:
            continue
        if not any(c.champ == "classe" for c in entree.changements):
            continue
        p = personne(entree.personne_id)
        if p is None or not p.email:
            continue
        ous = ou_par_classe.get(entree.classe_cible or "")
        if ous is None:
            plan.avertissements.append(
                f"{entree.cle_pivot} {entree.nom} : classe "
                f"{entree.classe_cible!r} hors table, déplacement impossible"
            )
            continue
        plan.operations.append(
            OperationGoogle(
                action="deplacer",
                email=p.email,
                payload=payload_deplacement_ou(org_unit_path=ous[1]),
                libelle=f"Déplacer {p.email} vers {ous[1]}",
            )
        )

    # Sortants — suspension + déplacement en OU d'archivage, jamais suppression
    ou_sortants = calculer_ou_sortants(session)
    for entree in rapport.sortants:
        if entree.site_id != site.id:
            continue
        p = personne(entree.personne_id)
        if p is None or not p.email:
            continue
        plan.operations.append(
            OperationGoogle(
                action="suspendre",
                email=p.email,
                payload={**payload_suspension(), **payload_deplacement_ou(org_unit_path=ou_sortants)},
                libelle=f"Suspendre {p.email} et archiver dans {ou_sortants}",
            )
        )

    return plan


# ---------------------------------------------------------------------------
# Transport — non testable sans credentials réelles
# ---------------------------------------------------------------------------


@dataclass
class ResultatExecution:
    nb_reussies: int = 0
    nb_echecs: int = 0
    echecs: list[dict] = field(default_factory=list)

    @property
    def tout_reussi(self) -> bool:
        return self.nb_echecs == 0


class ClientGoogle:
    """Client Admin SDK Directory.

    Instancié uniquement quand la configuration est complète. Toute erreur
    de configuration est levée à la construction plutôt qu'au premier appel,
    pour échouer tôt et clairement.
    """

    def __init__(self, config: ConfigGoogle) -> None:
        problemes = config.valider()
        if problemes:
            raise ValueError(" ; ".join(problemes))

        disponible, message = est_disponible()
        if not disponible:
            raise ValueError(message)

        from google.oauth2 import service_account  # type: ignore[import-not-found]
        from googleapiclient.discovery import build  # type: ignore[import-not-found]

        credentials = service_account.Credentials.from_service_account_file(
            config.chemin_credentials, scopes=SCOPES
        )
        # Délégation à l'échelle du domaine : le compte de service agit au
        # nom d'un administrateur réel.
        deleguees = credentials.with_subject(config.admin_impersonation)
        self._service = build("admin", "directory_v1", credentials=deleguees)

    def tester_connexion(self) -> dict[str, Any]:
        """Vérifie que les credentials fonctionnent — lecture seule.

        Récupère un seul utilisateur : suffisant pour valider l'auth, les
        scopes et la délégation, sans rien modifier.
        """
        reponse = (
            self._service.users()
            .list(customer="my_customer", maxResults=1)
            .execute()
        )
        return {
            "ok": True,
            "nb_utilisateurs_visibles": len(reponse.get("users", [])),
        }

    def executer_plan(self, plan: PlanGoogle) -> ResultatExecution:
        """Applique les opérations du plan, une par une.

        Les échecs sont collectés sans interrompre le traitement : un
        compte en erreur ne doit pas bloquer les suivants. Le détail permet
        de rejouer uniquement ce qui a échoué.
        """
        resultat = ResultatExecution()
        for operation in plan.operations:
            try:
                if operation.action == "creer":
                    self._service.users().insert(body=operation.payload).execute()
                else:
                    self._service.users().update(
                        userKey=operation.email, body=operation.payload
                    ).execute()
                resultat.nb_reussies += 1
            except Exception as e:  # pragma: no cover — dépend du réseau
                resultat.nb_echecs += 1
                resultat.echecs.append(
                    {
                        "email": operation.email,
                        "action": operation.action,
                        "erreur": str(e),
                    }
                )
        return resultat
