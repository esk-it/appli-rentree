"""Rapprochement de la flotte Chromebook et des enseignants.

## Où se cache l'information

Google offre un champ « utilisateur annoté » qui semble fait pour dire à
qui l'appareil est confié. Dans cette instance il porte partout le même
compte d'administration technique : il ne désigne personne.

L'établissement range l'information ailleurs, dans l'**étiquette**
(`annotatedAssetId`). Les appareils du personnel y portent l'adresse de
leur porteur ; ceux des élèves, un code d'emplacement (`K-B5-13-08`) ; et
le parc de prêt, un nom de rôle (`Prof_08`, `Stagiaire 9`).

Ce module lit donc l'étiquette, et ne s'en tient pas là : les **derniers
utilisateurs** de l'appareil, que Google enregistre seul, servent de
contre-épreuve. Quand les deux se contredisent, on ne tranche pas — deux
appareils échangés par erreur se voient précisément à cet endroit, et
c'est l'humain qui le corrige.

## Ce qu'il en tire

À qui réclamer une machine — les partants qui en détiennent une. À qui en
donner une — les arrivants qui n'en ont pas. Et lesquelles sont libres :
le parc de prêt, plus celles dont le porteur n'a plus de compte.

## Ce qu'il ne fait pas

Aucune écriture. Le droit demandé à Google est en lecture seule, et
réattribuer une machine reste un geste physique : le programme dit ce
qu'il constate, il ne déplace rien.
"""
from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass, field

ADRESSE = re.compile(r"^[^@\s]+@[^@\s]+\.[a-z]{2,}$", re.I)

# Étiquettes du parc de prêt : un rôle, pas une personne.
ROLES = re.compile(r"^(prof|stagiaire|maintenance|vs|pret|remplac)", re.I)

ACTIF = "ACTIVE"


def normaliser(texte: str | None) -> str:
    sans = unicodedata.normalize("NFD", (texte or "").strip().lower())
    return re.sub(
        r"[^a-z]", "", "".join(c for c in sans if unicodedata.category(c) != "Mn")
    )


@dataclass
class Appareil:
    serie: str
    modele: str
    ou: str
    statut: str
    etiquette: str
    porteur: str | None
    """Adresse lue dans l'étiquette, si c'en est une."""
    derniers_utilisateurs: list[str] = field(default_factory=list)
    emplacement: str = ""
    derniere_synchro: str | None = None

    @property
    def est_de_pret(self) -> bool:
        return bool(ROLES.match(self.etiquette)) and self.porteur is None

    @property
    def est_actif(self) -> bool:
        return self.statut == ACTIF


@dataclass
class Discordance:
    appareil: Appareil
    attendu: str
    constates: list[str]
    """Ce que Google a enregistré : qui s'est réellement connecté dessus."""


@dataclass
class LigneProf:
    nom: str
    prenom: str
    discipline: str
    code: str
    email: str | None
    appareils: list[Appareil] = field(default_factory=list)


@dataclass
class RapportFlotte:
    appareils: list[Appareil] = field(default_factory=list)
    profs: list[LigneProf] = field(default_factory=list)
    a_recuperer: list[LigneProf] = field(default_factory=list)
    """Partants qui détiennent au moins une machine."""
    a_attribuer: list[LigneProf] = field(default_factory=list)
    """Arrivants sans machine."""
    disponibles: list[Appareil] = field(default_factory=list)
    orphelins: list[Appareil] = field(default_factory=list)
    """Étiquetés au nom de quelqu'un qui n'a plus de compte."""
    discordances: list[Discordance] = field(default_factory=list)
    avertissements: list[str] = field(default_factory=list)

    @property
    def nb_a_recuperer(self) -> int:
        return sum(len(p.appareils) for p in self.a_recuperer)


def _porteur(etiquette: str) -> str | None:
    e = (etiquette or "").strip()
    return e.lower() if ADRESSE.match(e) else None


def analyser_flotte(
    appareils_bruts: list[dict],
    profs: list,
    comptes: list[dict],
    *,
    prefixe_personnel: str = "/1. Chromebooks/1. Personnel",
) -> RapportFlotte:
    """Croise les machines, le tableau des enseignants et les comptes Google.

    Args:
        appareils_bruts: retour de `ClientGoogle.lister_appareils`.
        profs: les `Prof` lus par `import_profs`.
        comptes: retour de `ClientGoogle.lister_utilisateurs`, pour relier
            un nom du tableau à une adresse — le tableau n'en porte pas.
    """
    rapport = RapportFlotte()

    for a in appareils_bruts:
        etiquette = (a.get("etiquette") or "").strip()
        rapport.appareils.append(
            Appareil(
                serie=a.get("serie") or "",
                modele=a.get("modele") or "",
                ou=a.get("ou") or "",
                statut=a.get("statut") or "",
                etiquette=etiquette,
                porteur=_porteur(etiquette),
                derniers_utilisateurs=[
                    u.lower() for u in (a.get("derniers_utilisateurs") or [])
                ],
                emplacement=a.get("emplacement") or "",
                derniere_synchro=a.get("derniere_synchro"),
            )
        )

    # Le tableau des enseignants ne porte pas d'adresse : elle vient des
    # comptes, rapprochés par nom et prénom.
    adresses_connues = set()
    par_nom: dict[tuple[str, str], str] = {}
    for c in comptes:
        adresse = (c.get("email") or "").lower()
        if not adresse:
            continue
        adresses_connues.add(adresse)
        cle = (normaliser(c.get("nom")), normaliser(c.get("prenom")))
        # Un homonyme rendrait l'attribution arbitraire : on ne garde que
        # les rapprochements sans ambiguïté.
        par_nom[cle] = "" if cle in par_nom else adresse
    par_nom = {k: v for k, v in par_nom.items() if v}

    par_porteur: dict[str, list[Appareil]] = {}
    for ap in rapport.appareils:
        if ap.porteur:
            par_porteur.setdefault(ap.porteur, []).append(ap)

    for p in profs:
        adresse = par_nom.get((normaliser(p.nom), normaliser(p.prenom)))
        ligne = LigneProf(
            nom=p.nom, prenom=p.prenom, discipline=p.discipline, code=p.code,
            email=adresse, appareils=par_porteur.get(adresse, []) if adresse else [],
        )
        rapport.profs.append(ligne)
        if p.code == "sortant" and ligne.appareils:
            rapport.a_recuperer.append(ligne)
        elif p.code == "arrivant" and not ligne.appareils:
            rapport.a_attribuer.append(ligne)

    # Machines libres : le parc de prêt, et celles dont le porteur a disparu.
    for ap in rapport.appareils:
        if not ap.ou.startswith(prefixe_personnel) or not ap.est_actif:
            continue
        if ap.est_de_pret:
            rapport.disponibles.append(ap)
        elif ap.porteur and ap.porteur not in adresses_connues:
            rapport.orphelins.append(ap)
            rapport.disponibles.append(ap)

    # Contre-épreuve : l'étiquette dit une chose, l'usage en dit une autre.
    for ap in rapport.appareils:
        if not ap.porteur or not ap.derniers_utilisateurs:
            continue
        if ap.porteur not in ap.derniers_utilisateurs:
            rapport.discordances.append(
                Discordance(
                    appareil=ap,
                    attendu=ap.porteur,
                    constates=ap.derniers_utilisateurs[:3],
                )
            )

    if rapport.discordances:
        rapport.avertissements.append(
            f"{len(rapport.discordances)} appareil(s) portent une étiquette que "
            "les connexions démentent. Deux machines échangées par erreur se "
            "voient ici — le programme ne tranche pas, il montre."
        )
    sans_adresse = [p for p in rapport.profs if p.email is None]
    if sans_adresse:
        rapport.avertissements.append(
            f"{len(sans_adresse)} enseignant(s) du tableau n'ont pas de compte "
            "Google retrouvé par leur nom : leurs machines ne peuvent pas leur "
            "être rattachées."
        )
    return rapport
