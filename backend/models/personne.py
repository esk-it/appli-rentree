"""Modèle SQLAlchemy : Personne — l'identité persistante.

Une ligne par être humain. Créée à la **première apparition** (dans un
export Charlemagne ou lors de l'amorçage à partir des comptes existants),
**jamais supprimée**, même des années après le départ.

## Clé pivot

Le couple `(type, id_charlemagne)`. Les élèves et les adultes ont deux
espaces de numérotation Charlemagne indépendants qui se télescopent — l'ID
brut n'est jamais une clé.

## Login

Figé à l'attribution (première ingestion), suffixe d'homonymie compris.
Jamais régénéré. `pdupont2` reste `pdupont2` même après le départ de
`pdupont` — un login libéré n'est pas recyclé.

## Email

**L'adresse constatée fait autorité.** Si un compte existe déjà, son adresse
est mémorisée telle quelle dans `email_constate` et n'est jamais recalculée.

Ce n'est pas une précaution théorique : sur l'export réel, une formule ne
retrouve que ~93 % des 1251 adresses en place. Les comptes ont été créés à
la main au fil des ans avec des conventions divergentes — espaces tantôt
remplacés par un point (`ana.comtet.goupille`) tantôt supprimés
(`madelon.arnaultdelamenardiere`), noms composés tronqués (`sarah.henocq`
pour HENOCQ KERAUTRET), et jusqu'à des prénoms orthographiés autrement dans
Charlemagne que dans le compte (`tiphaine` vs `thifaine`). Recalculer
casserait un compte sur quatorze.

Pour une personne **sans compte** (nouvel arrivant), l'adresse est calculée
par `calculer_email` : `prenom.nom@<site.domaine_mail>` — la convention de
l'établissement. Surtout pas `login@domaine` : le login est
`initiale+nom` (`adanielou`) là où l'adresse est `ambre.danielou`.

## Badge

Pour les **élèves** : `badge = id_charlemagne * 10 + 10000`. Formule
vérifiée sur 1820/1820 lignes de l'export historique.
Pour les **adultes** : numérotation propre, reprise telle quelle depuis
Charlemagne.
"""
from __future__ import annotations

from datetime import date, datetime

from sqlalchemy import Boolean, Date, DateTime, ForeignKey, Integer, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from backend.database import Base


TYPES_PERSONNE = ("eleve", "adulte")


class Personne(Base):
    __tablename__ = "personne"

    id: Mapped[int] = mapped_column(primary_key=True)

    # ------------------------------------------------------------------
    # Clé pivot — jamais modifiée après création
    # ------------------------------------------------------------------
    type: Mapped[str] = mapped_column(String(10), index=True)
    """`eleve` ou `adulte`. Deux espaces de numérotation Charlemagne distincts."""

    id_charlemagne: Mapped[int] = mapped_column(Integer, index=True)
    """Entier issu de Charlemagne. Combiné avec `type` pour former la clé pivot."""

    # ------------------------------------------------------------------
    # Identité stable — figée à vie
    # ------------------------------------------------------------------
    badge: Mapped[int] = mapped_column(Integer, index=True)
    """Élève : id_charlemagne * 10 + 10000. Adulte : numérotation propre."""

    login: Mapped[str] = mapped_column(String(50), unique=True, index=True)
    """Login réseau KoXo, figé à l'attribution. Suffixe d'homonymie inclus. Jamais recyclé."""

    date_entree: Mapped[date | None] = mapped_column(Date, nullable=True)
    """Date d'entrée réelle dans l'établissement (CardStudio `Date Entrée pour tri`)."""

    google_user_id: Mapped[str | None] = mapped_column(String(50), nullable=True, index=True)
    """Identifiant interne immuable Google Workspace. Capturé à l'amorçage/création via API."""

    email_constate: Mapped[str | None] = mapped_column(String(200), nullable=True, index=True)
    """Adresse du compte **existant**, relevée à l'amorçage ou dans l'export
    Charlemagne. Fait autorité et n'est jamais régénérée, exactement comme le
    login. `None` tant qu'aucun compte n'est constaté."""

    # ------------------------------------------------------------------
    # État courant — mis à jour à chaque ingestion
    # ------------------------------------------------------------------
    nom: Mapped[str] = mapped_column(String(100))
    prenom: Mapped[str] = mapped_column(String(100))
    nom_usage: Mapped[str | None] = mapped_column(String(100), nullable=True)

    classe: Mapped[str | None] = mapped_column(String(30), nullable=True)
    """Classe courante (code Charlemagne : ex. `31`, `1_BPAGORA`, `T_STMG1`)."""

    niveau: Mapped[str | None] = mapped_column(String(30), nullable=True)

    site_id: Mapped[int | None] = mapped_column(ForeignKey("site.id"), nullable=True, index=True)

    code_etablissement: Mapped[str | None] = mapped_column(String(20), nullable=True)
    """Code Charlemagne : `02-COL`, `03-LY`, `04-LP`. Différent du site (NDK regroupe 03-LY + 04-LP)."""

    regime: Mapped[str | None] = mapped_column(String(5), nullable=True)
    """`D` (demi-pension), `E` (externe), `P` (pensionnaire)."""

    chemin_photo_constate: Mapped[str | None] = mapped_column(String(500), nullable=True)
    """Chemin UNC de la photo constaté lors de la dernière ingestion.
    Mémorisé pour détecter les orphelines lors d'un changement de nom."""

    # ------------------------------------------------------------------
    # Champs spécifiques aux adultes — stockés mais ne pilotent pas de règle
    # ------------------------------------------------------------------
    civilite: Mapped[str | None] = mapped_column(String(10), nullable=True)
    poste_occupe: Mapped[str | None] = mapped_column(String(100), nullable=True)
    matieres: Mapped[str | None] = mapped_column(String(500), nullable=True)
    """Matières enseignées, séparées par `;` (ex. `MATHEMATIQUES;PHYSIQUE-CHIMIE`)."""

    classes_prof_principal: Mapped[str | None] = mapped_column(String(500), nullable=True)
    """Classes où prof principal, séparées par `;`."""

    email_professionnel: Mapped[str | None] = mapped_column(String(200), nullable=True)
    email_personnel: Mapped[str | None] = mapped_column(String(200), nullable=True)

    # ------------------------------------------------------------------
    # Traçabilité
    # ------------------------------------------------------------------
    date_creation: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    date_derniere_maj: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow, onupdate=datetime.utcnow
    )

    # Relations
    site: Mapped["Site | None"] = relationship()

    __table_args__ = (
        UniqueConstraint("type", "id_charlemagne", name="uq_personne_type_id_charlemagne"),
    )

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------
    @property
    def cle_pivot(self) -> str:
        """Représentation sérialisée de la clé pivot : `E5292`, `A60`."""
        prefixe = "E" if self.type == "eleve" else "A"
        return f"{prefixe}{self.id_charlemagne}"

    @property
    def email(self) -> str | None:
        """Adresse constatée si elle existe, sinon adresse calculée.

        `None` si aucun compte n'est constaté et que le site est inconnu — on
        ne devine pas un domaine.
        """
        if self.email_constate:
            return self.email_constate
        if not self.site:
            return None
        from backend.services.regles_metier import calculer_email

        return calculer_email(self.prenom, self.nom, self.site.domaine_mail) or None

    @property
    def email_est_constate(self) -> bool:
        """True si l'adresse vient d'un compte existant plutôt que d'un calcul.

        Distingue « ce compte est en place » de « voici l'adresse qu'il
        faudrait créer » — un export de création ne doit porter que la seconde.
        """
        return bool(self.email_constate)

    @staticmethod
    def calculer_badge(type_personne: str, id_charlemagne: int) -> int:
        """Formule badge — vérifiée sur 1820/1820 lignes historiques.

        - Élève : `id_charlemagne * 10 + 10000`
        - Adulte : `id_charlemagne` tel quel (numérotation propre)
        """
        if type_personne == "eleve":
            return id_charlemagne * 10 + 10000
        return id_charlemagne

    def __repr__(self) -> str:  # pragma: no cover
        return f"<Personne {self.cle_pivot} {self.nom} {self.prenom}>"
