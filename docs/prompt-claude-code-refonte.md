# Prompt de démarrage — refonte du cœur d'appli-rentree

> **Mode d'emploi**
>
> 1. Place les deux documents `gestion-rentree-logique.md` et
>    `fonctionnement-programme-rentree.md` dans `docs/` à la racine du dépôt.
> 2. Ouvre Claude Code à la racine du dépôt.
> 3. Colle tout ce qui suit la ligne de séparation.
>
> Ne demande pas de code à la première réponse. La première étape attendue est
> un plan.

---

Tu interviens sur `appli-rentree`, une application déjà en production
(v0.21.0) qui prépare la rentrée scolaire d'un ensemble scolaire de trois
sites. Elle part des exports du logiciel Charlemagne et alimente cinq
systèmes : KoXo, Google Workspace, PMB, JPM/SmartAir et CardStudio.

**Ta mission est une refonte du cœur métier, pas une réécriture de
l'application.**

Avant toute chose, lis `docs/gestion-rentree-logique.md` et
`docs/fonctionnement-programme-rentree.md`. Ils font autorité. Le présent
prompt les résume et les complète ; en cas de contradiction, les documents
priment.

---

## 1. Le problème à corriger

Le modèle de données actuel repose sur `EleveSnapshot` et `AdulteSnapshot` :
une photo Charlemagne par année scolaire. Empiler des snapshots ne crée pas
d'identité. À chaque traitement, l'application doit re-déduire qui est qui, à
partir du nom et de l'adresse mail.

C'est la cause unique de tous les symptômes : homonymes réarbitrés chaque année
ou confondus, comptes fantômes remontant en faux positifs, changements de nom
qui détruisent et recréent un compte, incohérences entre systèmes.

**Il manque l'entité centrale : une `Personne` à identité persistante.**

Deuxième défaut : `EleveSnapshot` et `AdulteSnapshot` sont séparés. Or les deux
populations partagent le même domaine de messagerie, le même annuaire Google,
les mêmes serveurs KoXo et **le même format de login**. Un contrôle d'unicité
qui ne traverse pas les deux populations laissera passer des collisions.

---

## 2. Ce que tu conserves

Ne touche à rien de ce qui suit :

- toute la coquille Tauri 2, la CI GitHub Actions, l'updater signé minisign,
  le sidecar PyInstaller, le packaging NSIS ;
- tout le frontend Svelte 5 : shell, sidebar, routing, palette de commandes,
  toasts, mode sombre, `StatCard`, `DataTable`, `BarChart` ;
- les parsers d'entrée existants, dont `parser_charlemagne.py` ;
- les modèles `Etablissement`, `AnneeScolaire`, `Parametre`, `Generation` ;
- la logique de formatage contenue dans les exporters, qui reste valable —
  seule leur source de données change.

## 3. Ce que tu supprimes

- `Chambre` et `AffectationChambre`. Les chambres ne sont pas un attribut de
  personne : les cartes de chambre ne sont pas nominatives et constituent des
  lignes distinctes dans le fichier CardStudio. Voir §7.5.

## 4. Ce que tu refais

- la couche identité, entièrement neuve ;
- `comparaison.py` ;
- `regles_metier.py` ;
- `ingestion.py` et `ingestion_adultes.py`, fusionnés en un seul chemin
  d'ingestion paramétré par le type de population.

---

## 5. Le modèle de données cible

### `Personne` — l'identité persistante

Une ligne par être humain. Créée à la première apparition, **jamais
supprimée**, même des années après le départ.

**Clé** : couple `(type, id_charlemagne)`, sérialisé `E5292` / `A60`.

Les élèves et les adultes ont **deux espaces de numérotation Charlemagne
indépendants qui se télescopent** — l'ID 60 existe des deux côtés. L'ID brut
n'est jamais une clé.

Champs stables, figés à vie :

| Champ | Règle |
|---|---|
| `type` | `eleve` ou `adulte` |
| `id_charlemagne` | Entier, issu de la source |
| `badge` | Pour les élèves : `id_charlemagne * 10 + 10000`. Vérifié sur 1820/1820 lignes. Pour les adultes : numérotation propre, reprise telle quelle |
| `login` | Voir §6.2. **Jamais régénéré**, suffixe d'homonymie compris |
| `email` | Dérivé du login |
| `date_entree` | Date d'entrée réelle dans l'établissement |
| `google_user_id` | Identifiant interne immuable Google, voir §7.2 |

Champs d'état courant, mis à jour à chaque ingestion : `nom`, `prenom`,
`nom_usage`, `classe`, `niveau`, `site`, `code_etablissement`, `regime`,
`chemin_photo_constate`.

Champs adultes, stockés mais ne pilotant aucune règle : `poste_occupe`,
`matieres`, `classes_prof_principal`, `civilite`, `email_professionnel`,
`email_personnel`.

### `Snapshot` — l'historique brut

Fusion de `EleveSnapshot` et `AdulteSnapshot`. Rattaché à une `Personne`.

Il ne porte plus l'identité : il porte **l'état constaté à une date**. Une
ligne par personne et par ingestion.

**Conserve tous les snapshots indéfiniment.** L'utilisateur ne sait pas encore
quelles statistiques lui seront utiles ; tant que l'historique brut existe,
n'importe quelle statistique pourra être calculée plus tard, y compris
rétroactivement.

### `CompteCible` — le cycle de vie par cible

Une ligne par couple `(Personne, cible)`.

```
personne_id | cible       | etat        | date_prevue_purge | identifiant_externe
E5292       | koxo_ndk    | supprime    | —                 | 62920
E5292       | google      | quarantaine | 2027-12-31        | 114…  (google_user_id)
E5292       | pmb         | supprime    | —                 | 62920
```

États : `prevu` → `cree` → `actif` → `quarantaine` → `purge`.

Politique de sortie, **différente selon la cible** :

| Cible | Sortie |
|---|---|
| KoXo, PMB, JPM, CardStudio | Suppression immédiate en fin d'année |
| Google Workspace | Quarantaine 18 mois, puis suppression |

Une personne est donc simultanément supprimée d'un système et active dans un
autre pendant un an et demi. **L'état n'est jamais global à la personne.**

### `Arbitrage` — la mémoire des décisions humaines

Chaque décision prise par l'utilisateur sur un cas ambigu ou une collision de
login est enregistrée définitivement et **jamais redemandée**.

### `TableCorrespondance` — configuration métier

`site`, `classe_charlemagne`, `code_court`, `groupe_google`, `ou_pre_rentree`,
`ou_definitive`. Importée depuis un fichier, éditable dans l'interface, jamais
codée en dur.

### Migration

Écris une migration qui reconstruit des `Personne` à partir des snapshots
existants, sans perte. Les snapshots sont conservés et rattachés. La migration
doit être rejouable et testée.

---

## 6. Règles métier

### 6.1 Clé pivot

Le rapprochement se fait **toujours** sur `(type, id_charlemagne)`. En cas
d'absence ou d'incohérence, clé de secours `nom + prenom + date_naissance`.

Le couple `nom + prenom` seul n'est **jamais** une clé de rapprochement.

### 6.2 Login

Forme : initiale du prénom + nom. Normalisation : suppression des accents,
apostrophes, espaces, traits d'union ; minuscules ; troncature.

Le contrôle d'unicité interroge **toutes les `Personne`, tous types et toutes
années confondus, y compris les personnes parties**. Un login libéré n'est
jamais recyclé.

En cas de collision, un suffixe est proposé à l'utilisateur, puis **figé
définitivement**. `pdupont2` reste `pdupont2` même après le départ de
`pdupont`.

**Contrainte technique absolue** : un login existant ne doit jamais être
régénéré, sous peine de désynchroniser le mot de passe (§6.4).

### 6.3 Homonymes

Ils ne se détectent pas par comparaison entre deux listes — cette méthode peut
même les masquer complètement. Deux contrôles distincts, à deux moments
différents :

1. **À l'ingestion** — deux personnes de mêmes nom et prénom dans le même
   export.
2. **À l'attribution du login** — le login calculé existe déjà dans le
   référentiel.

### 6.4 Mots de passe

**KoXo est l'autorité unique.** Il génère le mot de passe à la création et
**ne le régénère jamais** : un élève garde le même toute sa scolarité.

Trois conséquences à respecter strictement :

- la dépendance KoXo → Google **ne concerne que les nouveaux comptes** ; les
  personnes maintenues ne voient jamais leur mot de passe manipulé ;
- **le mot de passe n'est jamais persisté.** Il transite en mémoire de KoXo
  vers Google le temps du traitement, puis il est oublié. Le référentiel n'est
  pas un coffre-fort ;
- en cas d'oubli, la réponse est une réinitialisation via KoXo, jamais une
  consultation.

### 6.5 Réconciliation — cinq seaux

| Seau | Définition |
|---|---|
| `nouveau` | Absent du référentiel |
| `identique` | Présent, aucun attribut modifié |
| `modifie` | Présent, attributs changés — le seau le plus volumineux |
| `sortant` | Dans le référentiel, absent de l'export |
| `ambigu` | Rapprochement incertain |

Un cas `ambigu` n'est **jamais** résolu par une heuristique. Il est présenté
pour arbitrage humain.

---

## 7. Les modules cibles

Règle commune : **chaque module produit toujours un fichier d'import** au
format exact de sa cible. L'API n'est qu'un mode d'envoi supplémentaire, et le
fichier reste disponible en permanence, y compris quand l'API est utilisée.

### 7.1 KoXo

Deux serveurs distincts : **NDK** et **SU**.

CSV séparé par virgules. Attention au nommage des colonnes, contre-intuitif :

| Colonne du fichier | Contenu réel |
|---|---|
| `Groupe primaire` | **le login réseau** |
| `Identifiant` | **le mot de passe généré** |
| `ID unique` | le badge |

En sortie, le champ mot de passe est laissé vide — c'est KoXo qui le remplit.

**Boucle de retour** : l'utilisateur importe dans KoXo, exporte le fichier
« Nouveaux », le redépose dans l'application. Le module lit les mots de passe,
les associe par le badge, passe les comptes à `cree`, et **arme le module
Google**.

Tant que ce retour n'a pas eu lieu, le module Google **refuse** de créer les
nouveaux comptes et affiche explicitement la raison. La contrainte d'ordre est
un garde-fou vérifié, pas une convention.

### 7.2 Google Workspace

**Deux identifiants distincts, ne les confonds pas :**

- `Employee ID` — champ que *nous* remplissons avec l'ID Charlemagne.
  Actuellement **vide sur les 2321 comptes** : c'est la cause racine de tout le
  problème historique, et le renseigner est l'action déterminante du projet.
  Opération purement additive, aucun risque pour les comptes existants.
- `google_user_id` — identifiant interne **immuable** attribué par Google.
  Absent des exports CSV, disponible uniquement via l'API. Il ne change jamais,
  même si l'adresse mail change.

Le module s'adresse à un compte par `google_user_id` en priorité, avec repli
sur `Employee ID`, puis sur l'adresse mail en dernier recours. Capture le
`google_user_id` à l'amorçage et à chaque création.

Renseigne également `Employee Type` (`Élève` / `Adulte`) et `Department` (le
site) : champs libres, gratuits à remplir, qui rendent l'annuaire lisible dans
la console d'administration.

Unités d'organisation : `/<n>. SITE/SITEannée/classe`, par exemple
`/3. NDK/NDK2025/1_STMG1`. Deux niveaux configurés : pré-rentrée et définitive.

Garde-fous API obligatoires :

- simulation avant chaque exécution réelle ;
- reprise après interruption — le module sait ce qui a déjà été fait ;
- **aucune suppression directe.** Une suppression n'est proposée que pour les
  comptes dont la date de purge est échue, avec confirmation séparée. Un
  sortant part en quarantaine, jamais à la corbeille.

### 7.3 PMB

CSV séparé par points-virgules, un fichier par site.

**Point non résolu** : la clé de rapprochement de PMB n'est pas connue. Écris
le module pour utiliser le badge, avec une option INE activable par
configuration. Documente ce choix comme provisoire dans le code.

### 7.4 JPM / SmartAir

Fichier **différentiel** : colonne `Op` valant `a` (ajout), `b` (suppression),
`m` (modification). Colonnes `Op`, `Id`, `Name`, `CardId`, `Group`, dates
d'activation et d'expiration. `Id` et `CardId` reprennent le badge. `Name` est
obligatoire.

Groupes d'accès déduits du régime et du statut d'internat via la table de
correspondance.

**Ce traitement n'a jamais été exécuté dans l'établissement.** Le module
affiche un bandeau d'avertissement et reste en simulation seule tant qu'il n'a
pas été explicitement marqué comme validé dans la configuration.

### 7.5 CardStudio

Format `BadgesESK` : `Etablissement`, `Code établissement`, `Code niveau`,
`Code classe`, `Num Badge`, `Code Régime`, `Nom et prénom`, `Nom`, `Prénom`,
`Photo`, `Date Entrée pour tri` (format `AAAAMMJJ`), `NomFichierPhoto`,
`Chambres`.

Codes établissement : `02-COL`, `03-LY`, `04-LP`. Codes régime : `D`, `E`, `P`.

**Deux traitements spécifiques :**

1. **Une ligne par personne.** Le fichier de référence comporte 1749 lignes
   pour 1672 badges distincts : les 77 lignes excédentaires sont des cartes de
   chambre, non nominatives, et ne correspondent à aucune personne. Ne les
   confonds jamais avec des doublons d'élèves.

   Par défaut, le module peut ajouter ces lignes de cartes de chambre depuis
   une liste fixe en configuration, avec une option pour les omettre.

2. **Contrôle des photos.** Le chemin est indexé par le nom, pas par le badge :
   `\\ESK-APP01\Alcuin$\Photos\Eleves\KREISKER\<année>\<NOM Prénom>.jpg`

   Un changement de nom, d'accent ou de trait d'union rend la photo orpheline
   **sans aucun signalement**, jusqu'à l'impression des cartes. Le module
   vérifie l'existence réelle de chaque fichier et produit la liste des
   orphelines avec le motif probable. Il ne reconstruit jamais le nom de
   fichier à la volée : il mémorise le chemin constaté par personne.

### 7.6 Suivi et purge

Surveillance permanente des comptes en quarantaine, avec affichage de ceux dont
la date de purge est échue. Validation manuelle avant toute purge.

---

## 8. Comportements transverses non négociables

| Règle | Détail |
|---|---|
| Simulation par défaut | Tout traitement produit d'abord un rapport de ce qu'il ferait. L'exécution est une action distincte et explicite |
| Idempotence | Rejouer deux fois produit exactement le même résultat |
| Blocage sur inconnue | Classe absente de la table, dépendance non satisfaite : arrêt avec explication. **Jamais d'affectation par défaut** |
| Journalisation | Chaque traitement tracé : quoi, quand, sur qui, résultat |
| Reprise | Un traitement interrompu reprend où il s'est arrêté |
| Traitement continu | La chaîne tourne toute l'année, pas une seule fois en août |
| Aucun secret persisté | Mots de passe en mémoire uniquement |

---

## 9. Statistiques

L'utilisateur ne sait pas encore lesquelles lui seront utiles. Construis une
couche générique de comptages sur le référentiel plutôt qu'un tableau de bord
figé, et livre ce jeu par défaut :

- effectifs par site, niveau et classe ;
- comparaison année N / N−1 ;
- mouvements sur la période : entrées, sorties, changements internes ;
- répartition des régimes ;
- comptes en quarantaine par échéance de purge ;
- anomalies : photos orphelines, classes hors table, collisions de login,
  cas ambigus en attente.

L'ajout ultérieur d'une statistique ne doit jamais nécessiter de modifier le
modèle de données.

---

## 10. Ordre d'implémentation

Respecte cet ordre. Ne passe à l'étape suivante qu'une fois la précédente
testée.

1. Modèles `Personne`, `Snapshot`, `CompteCible`, `Arbitrage`,
   `TableCorrespondance` + migration depuis l'existant
2. `regles_metier.py` — login, normalisation, homonymes, unicité globale
3. Ingestion unifiée élèves + adultes
4. Réconciliation et les cinq seaux
5. Écrans d'arbitrage
6. Moteur de simulation, commun à toutes les cibles
7. Module KoXo, avec la boucle de retour
8. Module Google, mode fichier d'abord, mode API ensuite
9. Modules PMB, JPM, CardStudio
10. Procédure d'amorçage et écran de qualification
11. Statistiques et tableau de bord

---

## 11. Tests

La suite existante compte 51 tests et la CI annule la release en cas d'échec.
Maintiens ce niveau. Couvre en particulier :

- la formule du badge et l'unicité des ID ;
- la collision de login entre un élève et un adulte ;
- l'homonyme masqué : une personne part, une homonyme arrive le même cycle —
  le programme doit produire deux identités distinctes, jamais un héritage de
  compte ;
- le changement de nom : la personne reste la même, aucun compte n'est détruit
  ni recréé ;
- l'idempotence : deux exécutions successives, résultat identique ;
- la divergence des cycles de vie : supprimé de KoXo, encore actif dans Google ;
- le blocage du module Google tant que le retour KoXo n'a pas eu lieu ;
- le refus de traiter une classe absente de la table ;
- la déduplication CardStudio et la détection des photos orphelines.

---

## 12. Ce que tu ne dois pas faire

- Rapprocher deux personnes sur le nom ou l'adresse mail quand la clé pivot est
  disponible.
- Régénérer le login ou le mot de passe d'une personne existante.
- Supprimer un compte Google sans passer par la quarantaine.
- Résoudre un cas ambigu par une heuristique.
- Affecter une classe inconnue à une valeur par défaut.
- Persister un mot de passe en base ou dans un fichier.
- Séparer les élèves et les adultes en deux référentiels.
- Toucher à la coquille Tauri, à la CI ou à l'updater.

---

## 13. Première réponse attendue

Ne produis pas encore de code.

1. Lis les deux documents de `docs/` et le code existant.
2. Restitue en quelques lignes ta compréhension du problème d'identité, pour
   vérification.
3. Liste les points où le code actuel devra être modifié, fichier par fichier.
4. Signale toute contradiction entre ce prompt, les documents et le code.
5. Propose un plan d'exécution découpé en lots livrables et testables.

Attends la validation avant d'écrire la première ligne.
