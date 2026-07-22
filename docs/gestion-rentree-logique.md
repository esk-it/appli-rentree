# Gestion de la rentrée — logique de fonctionnement

**Ensemble Scolaire du Kreisker**
Document de référence — conception de la chaîne Charlemagne → systèmes cibles

---

## 1. Objet du document

Ce document décrit la logique de gestion des comptes et identités lors de la
préparation de rentrée, ainsi que le raisonnement qui a conduit à chaque choix.

Il ne traite pas de mise en œuvre technique. Il décrit **ce qu'il faut faire et
pourquoi**, indépendamment de l'outil qui le fera.

### Périmètre

| Élément | Valeur |
|---|---|
| Populations | Élèves et adultes (direction, professeurs, AESH, vie scolaire) |
| Sites | NDE, NDK, SU — regroupés sous l'ensemble scolaire ESK |
| Source | Charlemagne |
| Cibles | KoXo, Google Workspace, PMB, JPM (SmartAir), CardStudio |
| Volumétrie | ~1 800 élèves, ~170 adultes |

---

## 2. Diagnostic : quel est le vrai problème

### 2.1 Ce que le problème n'est pas

Le besoin ressemble à une conversion de format : prendre un export Charlemagne
et produire cinq fichiers d'import. Présenté ainsi, c'est un travail simple.

Ce n'est pas le problème.

### 2.2 Ce que le problème est

**Le problème est la gestion de l'identité dans le temps.**

Charlemagne fournit une **photo à l'instant T** : voici les personnes présentes,
avec leur classe.

Les systèmes cibles contiennent un **état accumulé** : des comptes créés au fil
des années, avec leur historique, leurs données, leurs mots de passe.

Comparer une photo à un état accumulé, sans mémoire de ce qui a été décidé
auparavant, oblige à **re-déduire chaque année qui est qui**. C'est de cette
re-déduction permanente que naissent tous les symptômes :

- les homonymes qu'il faut réarbitrer,
- les départs et arrivées à retrouver,
- les comptes fantômes qui reviennent chaque année,
- les incohérences entre systèmes.

Ce ne sont pas cinq problèmes distincts. C'est un seul problème, vu sous cinq
angles.

### 2.3 La cause racine

La chaîne dispose déjà d'un identifiant stable — le badge — qui circule dans
Charlemagne, KoXo, JPM et CardStudio.

**Google Workspace est le seul système de la chaîne à ne porter aucun
identifiant.** Le champ `Employee ID`, prévu exactement pour cela, est vide sur
la totalité des comptes.

C'est pour cette raison, et uniquement pour cette raison, que le rapprochement
avec Google se faisait sur le nom et l'adresse mail — la seule information
disponible. Tous les symptômes en découlent.

---

## 3. Les cinq principes fondateurs

### 3.1 Un référentiel, pas des comparaisons deux à deux

On insère une base intermédiaire entre la source et les cibles. Elle est la
seule autorité sur l'identité des personnes.

```
                    ┌──────────────┐
   Charlemagne  ──▶ │              │ ──▶  KoXo
                    │ RÉFÉRENTIEL  │ ──▶  Google Workspace
     (photo)        │  (mémoire)   │ ──▶  PMB
                    │              │ ──▶  JPM / SmartAir
                    └──────────────┘ ──▶  CardStudio
```

Conséquence : **les cibles ne sont plus jamais des sources d'information.**
Elles reçoivent, elles ne renseignent pas. La seule exception est KoXo, traitée
au §7.

### 3.2 Une seule base pour les élèves et les adultes

Les deux populations sont traitées séparément dans les documents actuels. Cette
séparation est trompeuse : elle empêche de voir les collisions, pas de les
produire.

Élèves et adultes partagent :

- le même domaine de messagerie `@lekreisker.fr`,
- le même annuaire Google,
- les mêmes serveurs KoXo,
- **le même format de login** (`jbars` pour un adulte, `skerbrat` pour un élève).

Un professeur `Jean BARS` recruté alors qu'un élève `Julien BARS` existe déjà
produit deux fois `jbars`. Un contrôle d'unicité qui ne regarde qu'une seule
population ne verra jamais cette collision.

**Le contrôle d'unicité doit traverser les deux populations.** Il ne peut donc y
avoir qu'un référentiel. La séparation élèves / adultes est une distinction de
présentation, pas de stockage.

### 3.3 Décider une fois, exécuter dans l'ordre

Deux notions étaient confondues dans la méthode historique :

| | |
|---|---|
| **Séquence d'exécution** | KoXo avant Google, car les mots de passe doivent exister. **Contrainte réelle, on la conserve.** |
| **Séquence de décision** | Déterminer qui est nouveau au moment de traiter Google, puis le redéterminer pour KoXo, puis pour PMB. **Source de divergence, on la supprime.** |

La chaîne devient donc :

```
1. DÉCISION — une seule passe, toutes populations, toutes cibles
   Qui arrive, qui part, qui change, quel identifiant, quel mail, quelle classe
        │
        ▼
2. EXÉCUTION — dans l'ordre des dépendances
   KoXo → (retour mots de passe) → Google → PMB → JPM → CardStudio
```

### 3.4 Rien n'est irréversible sans validation

- **Simulation par défaut.** Tout traitement produit d'abord un rapport de ce
  qu'il *ferait*. L'application réelle est une action distincte et explicite.
- **Idempotence.** Rejouer deux fois le même traitement produit exactement le
  même résultat.
- **Aucune suppression immédiate sur Google.** Un compte supprimé par erreur de
  rapprochement est irrécupérable, avec ses courriels et son Drive.
- **Traçabilité.** Chaque traitement est journalisé : quoi, quand, sur qui,
  avec quel résultat.

### 3.5 Le doute ne se tranche pas automatiquement

La réconciliation classe chaque personne dans un seau. L'un d'eux s'appelle
**ambigu**, et il est aussi important que les autres.

Un cas ambigu n'est jamais résolu par une heuristique. Il est présenté pour
arbitrage humain, et l'arbitrage est **mémorisé** — il ne sera pas redemandé
l'année suivante.

---

## 4. La clé pivot

### 4.1 La formule

Charlemagne attribue un ID à chaque personne. Le badge en dérive :

```
badge = ID Charlemagne × 10 + 10000
```

Exemple : `ID 5292 → badge 62920`

Vérifié sur **1 820 lignes sur 1 820**, sans exception, et les 1 820 ID sont
tous uniques.

### 4.2 Propagation constatée

| Système | Champ portant la clé | Vérification |
|---|---|---|
| Charlemagne | `ID` et `badge` | 1820/1820 conformes à la formule |
| KoXo | `ID unique` | 649/649 correspondent à un badge Charlemagne |
| JPM / SmartAir | `Id`, `CardId` | badge repris tel quel |
| CardStudio | `Num Badge` | 1672 badges, tous multiples de 10 |
| **Google Workspace** | **`Employee ID` — vide** | **0 / 2321 comptes renseignés** |

### 4.3 L'action qui débloque tout

**Renseigner le champ `Employee ID` de Google avec l'ID Charlemagne.**

C'est une opération purement additive : on remplit un champ vide, on ne modifie
rien d'existant. Elle ne présente aucun risque pour les comptes en place.

Effets immédiats :

- deux homonymes deviennent deux personnes distinctes, sans ambiguïté ;
- un changement de nom, d'orthographe ou d'accent ne casse plus le
  rapprochement ;
- la comparaison Charlemagne / Google devient déterministe ;
- les comptes en quarantaine cessent de remonter en faux positifs.

### 4.4 Espaces de numérotation

Les élèves et les adultes ont **deux espaces d'ID Charlemagne indépendants** :

- élèves : 5292, 7544, 7318… avec la formule badge ci-dessus ;
- adultes : 313, 60, 253, 184… numérotation courte et distincte.

Ces deux espaces peuvent se télescoper : l'ID 60 existe des deux côtés.

**La clé du référentiel est donc un couple `(type, ID)`** — noté `E5292` /
`A60` — et jamais l'ID brut.

---

## 5. Le référentiel

### 5.1 Rôle

Le référentiel est la mémoire de l'établissement sur l'identité des personnes.
Il contient **une ligne par être humain**, créée à la première apparition et
**jamais supprimée**, même longtemps après le départ.

Il répond à une seule question, mais il y répond de façon fiable et
permanente : *cette personne qui apparaît dans l'export d'aujourd'hui, est-ce
quelqu'un que nous connaissons déjà, et si oui, quels comptes lui
appartiennent ?*

### 5.2 Ce qu'il contient

**Identité stable** — ne change jamais de la vie de la personne :

- clé pivot `(type, ID Charlemagne)`
- badge
- login réseau, **figé à l'attribution, suffixe d'homonymie compris**
- adresse mail
- date d'entrée dans l'établissement

**État courant** — mis à jour à chaque ingestion :

- nom, prénom, nom d'usage
- classe, niveau, site, code établissement
- régime, statut interne, chambre le cas échéant
- chemin de la photo constaté

**Cycle de vie par cible** — voir §6.

**Historique** — la suite des états constatés, année par année, conservée pour
l'audit et les statistiques.

### 5.3 Ce qu'il ne contient pas

**Aucun mot de passe.** Voir §7.3.

### 5.4 Ce qui existe déjà

La feuille `Traitement Eleves année N` du classeur actuel *est* un référentiel,
construit à la main. Ses colonnes — ID, mails N et N-1, vérification de
doublons, identifiant, classe, site, groupes — puis les blocs de reformatage
vers KoXo et Google, décrivent exactement l'architecture ci-dessus.

**La logique était juste.** Ce qui manquait, c'est la persistance d'une année
sur l'autre : le référentiel était reconstruit de zéro chaque été, sans autre
mémoire du passé qu'une colonne `Email N-1`.

De même, la feuille `Table` est la table de correspondance
`Site / Classe Charlemagne / Groupe Google / Unité d'organisation`. C'est une
**configuration métier**, à conserver telle quelle et à maintenir séparément
des données.

---

## 6. Cycles de vie

### 6.1 Un attribut a un état, pas seulement une valeur

Une adresse mail peut être décidée dans Charlemagne alors que le compte Google
correspondant n'existe pas encore. Elle n'est ni absente, ni active : elle est
**prévue**.

```
prévu  →  créé  →  actif  →  quarantaine  →  purgé
```

Cette distinction permet de **préparer intégralement la rentrée en juillet sans
rien créer** : contrôler les collisions de logins, valider les arbitrages,
vérifier les affectations — avant que le moindre compte existe.

### 6.2 L'état est propre à chaque cible

La politique de sortie diffère selon les systèmes :

| Cible | Politique de sortie |
|---|---|
| KoXo | Suppression immédiate en fin d'année |
| PMB | Suppression immédiate en fin d'année |
| JPM / SmartAir | Suppression immédiate en fin d'année |
| CardStudio | Suppression immédiate en fin d'année |
| **Google Workspace** | **Conservation 18 mois, puis suppression** |

Justification : une personne ayant quitté l'établissement ne doit plus disposer
d'aucun accès physique ni réseau sur site — d'où l'immédiateté sur KoXo, PMB et
JPM. La messagerie relève d'une logique différente et bénéficie d'un délai.

Conséquence directe : **une même personne est simultanément supprimée d'un
système et active dans un autre, pendant un an et demi.**

Le cycle de vie n'est donc pas un état global de la personne, mais un état par
couple **personne × cible** :

```
Élève parti en juin 2026

  KoXo        supprimé          juillet 2026
  PMB         supprimé          juillet 2026
  JPM         supprimé          juillet 2026
  CardStudio  supprimé          juillet 2026
  Google      quarantaine  →  purge décembre 2027
```

Une unité d'organisation de quarantaine existe déjà à cet usage :
`/7. Sortis/Comptes à supprimer au 31-12-AAAA`.

### 6.3 Effet sur la fiabilité du diff

Les comptes en quarantaine sont, par construction, **présents dans Google et
absents de Charlemagne**.

Avec un rapprochement par nom, ils apparaissaient en « partants » à chaque
rentrée, pendant 18 mois — soit deux cohortes de faux positifs présentes en
permanence.

Avec le référentiel, ils portent l'état « quarantaine, purge prévue le … » et
n'apparaissent plus jamais dans le diff. Le nombre de faux positifs tombe à
zéro.

---

## 7. Identifiants et mots de passe

### 7.1 Génération du login

Le login réseau suit la forme `initiale du prénom + nom`, normalisée :
suppression des accents, des apostrophes, des espaces et des traits d'union,
passage en minuscules, troncature.

Exemples constatés : `skerbrat`, `llhourre`, `crefloch`, `jbars`, `mleguill`.

### 7.2 Homonymes

Les homonymes ne se détectent **pas** par comparaison entre deux listes. Cette
méthode peut même les masquer complètement :

> Pierre DUPONT quitte l'établissement en juin. Un autre Pierre DUPONT arrive en
> septembre. Une comparaison par nom ou par adresse mail conclut « présent des
> deux côtés, aucun changement ». Le nouvel élève hérite silencieusement du
> compte, de la messagerie et du Drive de l'ancien.

La détection repose sur deux contrôles distincts, à deux moments différents :

1. **À l'ingestion** — deux personnes portant les mêmes nom et prénom dans le
   même export.
2. **À l'attribution du login** — le login calculé pour une nouvelle personne
   existe déjà dans le référentiel, **toutes populations et toutes années
   confondues**, y compris pour des personnes parties.

Un suffixe de désambiguïsation est alors attribué, **et figé définitivement**.
Si `pdupont2` a été créé ainsi, il reste `pdupont2` même après le départ de
`pdupont`.

### 7.3 Mots de passe

**KoXo est l'autorité unique du mot de passe.** Il le génère à la création du
compte, et **ne le régénère jamais** : un élève conserve le même mot de passe
toute sa scolarité.

Trois conséquences majeures :

**a) La contrainte d'ordre ne concerne que les nouveaux.**

```
NOUVEAUX  (~10-15 % du volume)
  KoXo génère le mot de passe  →  Google le consomme
  ordre imposé

MAINTENUS (~85-90 % du volume)
  changement de classe, de site, d'unité d'organisation, de groupe
  aucun mot de passe manipulé, aucun ordre imposé
```

L'essentiel du travail est donc parallélisable et rejouable sans risque.

**b) Le mot de passe est une donnée de passage, jamais une donnée stockée.**

Il transite de KoXo vers Google, le temps du traitement des seuls nouveaux
comptes, puis il est oublié. Le référentiel n'est pas un coffre-fort.

En cas d'oubli par un élève, la réponse est une **réinitialisation via KoXo**,
et non une consultation.

*Point de vigilance : le classeur de travail actuel stocke en clair les mots de
passe de tous les élèves ainsi que des identifiants d'administration, dans un
fichier partagé. Cette situation est à corriger.*

**c) Le login devient une contrainte technique absolue.**

Si le login d'une personne existante était régénéré, son mot de passe ne
correspondrait plus à rien. La stabilité du login n'est donc pas une bonne
pratique : c'est une condition de fonctionnement.

### 7.4 Sur l'inversion de l'autorité du mot de passe

L'hypothèse d'un mot de passe généré par le référentiel puis imposé à KoXo et à
Google **a été écartée**.

Son seul intérêt était de supprimer la contrainte d'ordre — laquelle ne pèse
que sur 10 % du volume. En contrepartie, elle imposerait de réinitialiser le mot
de passe de tous les élèves déjà en place. Coût élevé, bénéfice nul.

---

## 8. La réconciliation

### 8.1 Principe

À chaque ingestion, l'export Charlemagne est comparé au **référentiel**, jamais
à une cible, sur la clé pivot `(type, ID)`.

### 8.2 Les cinq seaux

| Seau | Définition | Traitement |
|---|---|---|
| **Nouveau** | Absent du référentiel | Création d'identité, attribution login et mail, création des comptes |
| **Identique** | Présent, aucun attribut modifié | Aucune action |
| **Modifié** | Présent, attributs changés | Mise à jour ciblée : unité d'organisation, groupes, classe, chambre |
| **Sortant** | Dans le référentiel, absent de l'export | Application de la politique de sortie, par cible |
| **Ambigu** | Rapprochement incertain | **Arbitrage humain, puis mémorisation de la décision** |

Le seau « modifié » est le plus volumineux et génère l'essentiel du travail
réel : déplacements d'unités d'organisation Google, changements de groupes,
regroupements KoXo.

### 8.3 Rapprochement de secours

La clé pivot est primaire. En cas d'absence ou d'incohérence, le rapprochement
de secours combine **nom + prénom + date de naissance**.

Le couple nom + prénom seul n'est jamais une clé de rapprochement.

### 8.4 Amorçage — opération unique

Le référentiel initial se construit une fois, à partir d'un export Google
rapproché de Charlemagne.

Cette étape ne produit **pas** une liste d'actions, mais un **travail de
qualification manuel** : chaque compte Google est classé — élève réel, adulte
réel, compte fantôme à purger, doublon, compte de service à exclure du
périmètre.

Ce travail est fait une seule fois. Une fois le référentiel amorcé et le champ
`Employee ID` renseigné, il n'est jamais refait.

---

## 9. Séquence d'exécution

### 9.1 Ordre

```
0.  Ingestion       Export Charlemagne élèves + adultes
1.  Réconciliation  Comparaison au référentiel, classement en 5 seaux
2.  Arbitrage       Traitement humain des cas ambigus
3.  Attribution     Logins et adresses mail des nouveaux (état : prévu)
4.  Simulation      Rapport complet de ce qui sera fait, toutes cibles
    ─── point de validation ───
5.  KoXo            Création des nouveaux comptes
6.  Retour KoXo     Récupération des mots de passe générés
7.  Google          Création des nouveaux comptes, déplacement des existants
8.  PMB             Import des lecteurs
9.  JPM / SmartAir  Import du contrôle d'accès
10. CardStudio      Fichier badges pour le secrétariat
11. Journalisation  Traçabilité complète du traitement
```

Les étapes 5 et 7 sont liées par une dépendance stricte, uniquement pour les
nouveaux comptes. Les étapes 8 à 10 sont indépendantes entre elles.

### 9.2 Ce n'est pas un traitement annuel

Des personnes arrivent et partent toute l'année. La chaîne est conçue pour être
exécutée **régulièrement**, et non une seule fois en août. C'est précisément ce
que l'idempotence et la simulation rendent possible sans risque.

### 9.3 La boucle de retour KoXo

KoXo est la seule cible qui **produit** une donnée consommée par une autre.

```
Référentiel  →  KoXo  →  Référentiel  →  Google
```

Cette boucle est déjà pratiquée manuellement, via la feuille
`Import KoXo > Charlemagne` qui réinjecte les identifiants réseau dans
Charlemagne. Elle doit être modélisée explicitement plutôt que subie.

---

## 10. Fiches par système

### 10.1 Charlemagne — source

Export élèves :

```
badge | ID | Nom | Prénom | Code Classe prec. | Code classe |
Code Classe an prochain | Email | Code Régime
```

Export adultes :

```
Identifiant | Nom | Prénom | Poste occupé | Liste des matières |
Liste des classes (Prof principal) | Date de Naissance | Civilité |
Adresse | Code Postal | Ville | Téléphone | Email professionnel | Email personnel
```

**Point notable :** Charlemagne porte trois colonnes de classe — précédente,
courante et de l'année suivante. **La transition d'année est donc déjà dans la
source** ; elle n'a pas à être déduite.

**Dépendance humaine :** la qualité de l'ensemble de la chaîne repose sur la
saisie effectuée par le secrétariat avant les congés d'été. Le traitement doit
tolérer une saisie incomplète et être rejoué au fil des complétions.

### 10.2 KoXo — annuaire réseau

Deux serveurs distincts : **NDK** et **SU**.

```
Groupe primaire | Groupe secondaire | Titre | Nom | Prénom |
Identifiant | ID unique | Mot de passe | Date de naissance | Email
```

**Attention au nommage des colonnes**, contre-intuitif :

| Colonne | Contenu réel |
|---|---|
| `Groupe primaire` | **le login réseau** |
| `Identifiant` | **le mot de passe généré** |
| `ID unique` | le badge |

Format d'échange : CSV séparé par virgules.
Rôle : autorité du mot de passe. Sortie immédiate en fin d'année.

### 10.3 Google Workspace — messagerie et services

```
First Name | Last Name | Email Address | Password | Org Unit Path |
Employee ID | … (et de nombreux champs annexes)
```

Structure des unités d'organisation : `/<n>. SITE/SITEannée/classe`
Exemples : `/3. NDK/NDK2025/1_STMG1`, `/4. SU/SU2025/33`, `/2. NDE/NDE2026/3F`

Deux niveaux d'unité sont prévus dans la configuration : **pré-rentrée** et
**définitive**, permettant de préparer les affectations avant la rentrée
effective.

Groupes : une adresse de groupe par classe, par site.

**Champ `Employee ID` : vide aujourd'hui, à renseigner avec l'ID Charlemagne.**
C'est l'action déterminante décrite au §4.3.

Politique de sortie : quarantaine 18 mois, puis suppression.

### 10.4 PMB — gestion documentaire

Un serveur par site. Import des lecteurs en CSV séparé par points-virgules.
Export dédié disponible dans Charlemagne.

**Point ouvert :** la clé de rapprochement utilisée par PMB n'est pas
déterminée. L'hypothèse de l'INE est à vérifier en examinant l'export
Charlemagne dédié à PMB ainsi qu'un export de lecteurs existants. Si l'INE est
confirmé, il devra être ajouté au référentiel.

Politique de sortie : suppression immédiate.

### 10.5 JPM / SmartAir — contrôle d'accès

```
Op | Id | Name | CardId | Group | Technology | ActivationDate |
ExpirationDate | Grants | PIN | …
```

La colonne `Op` porte l'opération : `a` ajout, `b` suppression, `m`
modification. Le fichier est donc **différentiel**, et non un état complet —
il dépend directement de la qualité de la réconciliation.

Groupes d'accès organisés notamment par régime d'internat (internes collège,
internes seconde, internes première et terminale) et par situation de handicap.

Le champ `Name` est obligatoire pour le traitement.

Clés : `Id` et `CardId` reprennent le badge.

**Vigilance particulière :** ce traitement n'a jamais été exécuté. Il doit être
préparé, simulé, et son résultat comparé à une production manuelle avant toute
exécution réelle.

### 10.6 CardStudio — production des cartes

Exécuté sur le poste du secrétariat, qui fabrique les cartes.

```
Etablissement | Code établissement | Code niveau | Code classe | Num Badge |
Code Régime | Nom et prénom | Nom | Prénom | Photo | Date Entrée pour tri |
NomFichierPhoto | Chambres
```

Codes établissement : `02-COL`, `03-LY`, `04-LP`.
Codes régime : `D`, `E`, `P`.

**Deux pièges avérés :**

1. **Le fichier n'est pas à raison d'une ligne par personne.** Sur un export de
   référence : 1 749 lignes pour 1 672 badges distincts. Les 77 lignes
   excédentaires correspondent exactement aux 77 lignes portant une chambre —
   les internes apparaissent deux fois.

2. **Les photos sont indexées par le nom, non par le badge :**
   ```
   \\ESK-APP01\Alcuin$\Photos\Eleves\KREISKER\<année>\<NOM Prénom>.jpg
   ```
   Un changement de nom, une correction d'accent ou une variation de trait
   d'union rend la photo orpheline, **sans aucun signalement**, jusqu'à
   l'impression des cartes.

   Le référentiel doit donc **mémoriser le chemin de photo constaté** par
   personne et signaler les orphelines, plutôt que de reconstruire le nom de
   fichier à la volée.

Le champ `Date Entrée pour tri` (format `AAAAMMJJ`) fournit la **date d'entrée
réelle dans l'établissement**, information indisponible ailleurs et à conserver
au référentiel.

---

## 11. Points de vigilance

| Risque | Nature | Parade |
|---|---|---|
| Homonyme masqué par un départ simultané | Silencieux, détecté des mois plus tard | Clé pivot + contrôle d'unicité sur l'historique complet |
| Collision de login élève / adulte | Silencieux | Référentiel unique traversant les deux populations |
| Changement de nom | Compte détruit et recréé, perte de données | Rapprochement sur la clé, jamais sur le nom |
| Photo orpheline après changement de nom | Silencieux jusqu'à l'impression | Chemin de photo mémorisé et contrôlé |
| Doublons dans l'export CardStudio | Comptage et traitements faussés | Déduplication sur le badge |
| Collision des espaces d'ID élèves / adultes | Silencieux | Clé typée `(type, ID)` |
| Suppression Google par erreur de rapprochement | Irréversible | Quarantaine 18 mois, jamais de suppression directe |
| Saisie Charlemagne incomplète en juillet | Traitement partiel | Idempotence, exécutions répétées |
| Mots de passe en clair dans les fichiers de travail | Confidentialité | Mot de passe en donnée de passage, jamais stocké |
| JPM jamais exécuté | Inconnue opérationnelle | Simulation et comparaison manuelle avant première exécution |

---

## 12. Points restant à déterminer

1. **Clé de rapprochement PMB** — INE ou autre. À vérifier via l'export
   Charlemagne dédié et un export de lecteurs existants.
2. **Rythme d'exécution en cours d'année** — fréquence retenue pour le
   traitement des arrivées et départs hors rentrée.
3. **Traitement des personnes changeant de statut** — un ancien élève recruté
   comme adulte conserve-t-il son identité au référentiel, ou en ouvre-t-il une
   seconde.

---

## 13. Synthèse

| | Avant | Après |
|---|---|---|
| Mémoire | Une colonne `Email N-1` | Référentiel persistant, historique complet |
| Clé de rapprochement | Nom et adresse mail | `(type, ID Charlemagne)` sur les 5 cibles |
| Homonymes | Réarbitrés chaque année, parfois manqués | Structurellement impossibles à confondre |
| Comptes fantômes | Remontent en faux positifs pendant 18 mois | État de quarantaine daté, hors du diff |
| Populations | Deux documents indépendants | Un référentiel, deux vues |
| Décisions | Reprises à chaque cible | Une passe unique, puis projections |
| Cycle de vie | Global et implicite | Par personne et par cible, explicite |
| Réversibilité | Aucune | Simulation par défaut, idempotence, journalisation |
| Élément déclencheur | — | **Renseigner `Employee ID` dans Google** |
