/**
 * Le parcours de la rentrée, en un seul endroit.
 *
 * L'outil ne sert qu'une fois par an. Entre deux campagnes on a oublié
 * l'ordre, et surtout les raisons de l'ordre : pourquoi la Table doit être
 * tournée avant qu'on touche à l'arborescence, pourquoi les adresses se
 * corrigent avant la bascule. Ranger les écrans par module laissait cette
 * connaissance dans la tête de qui s'en était servi.
 *
 * Chaque étape porte donc, en plus de sa destination, ce qu'elle sert à
 * faire et ce qu'on doit voir quand elle a réussi. Ces deux phrases sont
 * le vrai contenu du parcours — la numérotation n'en est que l'ordre.
 *
 * `faite` n'existe que pour les étapes dont l'état se lit dans le
 * référentiel. Celles qui se constatent dans Google n'en ont pas : une
 * case qui ne se coche jamais serait fausse autant que décourageante.
 */

export const PHASES = [
  {
    id: "preparation",
    titre: "Préparer les données",
    resume:
      "Constituer le référentiel : qui est là, dans quelle classe, avec quel identifiant.",
  },
  {
    id: "bascule",
    titre: "Basculer dans Google",
    resume:
      "Faire passer l'année dans l'annuaire, dans un ordre qui ne se devine pas.",
  },
];

/**
 * @typedef {Object} Etape
 * @property {string} id
 * @property {string} phase
 * @property {string} page      - écran vers lequel l'étape mène
 * @property {string} titre
 * @property {string} role      - à quoi sert cette étape
 * @property {string} [reperer] - ce qu'on doit voir quand elle a réussi
 * @property {string[]} [pieges] - ce qui peut mal tourner, et qu'on ne
 *   redécouvre qu'en se trompant. Écrit là plutôt que retenu : ces
 *   phrases ont coûté des heures en 2026-2027, et douze mois séparent
 *   deux campagnes.
 * @property {string} [ecran]   - onglet ou section précise, quand l'écran en a
 */

/** @type {Etape[]} */
export const ETAPES = [
  {
    id: "sites",
    phase: "preparation",
    page: "sites",
    titre: "Déclarer les sites",
    role: "Chaque site porte son domaine de messagerie et le préfixe de ses unités d'organisation. Tout le reste s'y rattache.",
    reperer: "Les trois sites apparaissent, avec leur domaine.",
  },
  {
    id: "table",
    phase: "preparation",
    page: "table_correspondance",
    titre: "Remplir la table de correspondance",
    role: "Elle fait le pont entre les codes classe de Charlemagne et les unités d'organisation et groupes Google. Une classe absente d'ici bloque son traitement plutôt que d'être devinée.",
    reperer: "Aucune classe constatée n'échappe à la table.",
    pieges: [
      "Une classe absente de la Table bloque son traitement partout — c'est voulu, mais ça se découvre tard si on ne la complète pas maintenant.",
    ]
  },
  {
    id: "amorcage",
    phase: "preparation",
    page: "amorcage",
    titre: "Amorcer depuis KoXo",
    role: "Récupère les identifiants déjà attribués. Un login est fixé pour toute la scolarité : le régénérer romprait tout ce qui s'y rattache.",
    reperer: "Les personnes existantes portent leur login d'origine.",
    pieges: [
      "Un login est figé pour toute la scolarité. Ce qui entre ici ne se corrige plus ensuite sans casser Google, KoXo et les étiquettes d'un coup.",
    ]
  },
  {
    id: "ingestion",
    phase: "preparation",
    page: "snapshots",
    titre: "Ingérer l'export Charlemagne",
    role: "Crée la photographie de l'année : qui est inscrit, dans quelle classe. C'est elle qui sert de référence à tout le reste.",
    reperer: "L'année préparée apparaît, avec son effectif.",
    pieges: [
      "Un export pris avant le 1er septembre omet les professeurs entrants : ils ne sont pas encore saisis dans Charlemagne.",
      "Charlemagne refuse les .xlsx écrits par un programme. Passer par Excel pour ré-enregistrer, sinon erreur 40057.",
    ]
  },
  {
    id: "arbitrage",
    phase: "preparation",
    page: "arbitrage",
    titre: "Trancher les cas ambigus",
    role: "Collisions de login, homonymies, adresses visées par plusieurs personnes. Le programme ne tranche jamais seul : il présente et attend.",
    reperer: "Plus aucune décision en attente.",
    pieges: [
      "Le programme ne tranche jamais seul, et il a raison : une homonymie mal résolue donne à un élève l'adresse d'un autre.",
    ]
  },

  {
    id: "vider",
    phase: "bascule",
    page: "sortants",
    titre: "Vider l'arbre de l'année révolue",
    role: "Les comptes qui restent dans le plus ancien arbre sont ceux des élèves partis un an plus tôt. Ils rejoignent leur unité de sortie, sans être suspendus.",
    reperer: "La branche est annoncée vide, ou ne garde que des élèves encore inscrits.",
    ecran: "Vider une arborescence d'année",
    pieges: [
      "« Absent du référentiel » n'est pas une preuve de départ. Recouper avec un export Charlemagne frais avant de vider : en septembre 2026, 8 élèves montés de NDE seraient partis en OU de sortie, dont 3 qui n'utilisaient que leur ancien compte.",
    ]
  },
  {
    id: "rotation",
    phase: "bascule",
    page: "table_correspondance",
    titre: "Tourner la table de correspondance",
    role: "Les chemins d'unités d'organisation portent l'année en toutes lettres. Tant qu'ils désignent l'ancienne, tout le reste vise la mauvaise cible.",
    reperer: "Toutes les lignes sont modifiées, aucune laissée de côté.",
    ecran: "Changer l'année des OU",
    pieges: [
      "NDK2026 désigne l'année 2025-2026 : le millésime est l'année de fin. Se tromper d'un an fait viser l'arbre qu'on vient de vider.",
    ]
  },
  {
    id: "arborescence",
    phase: "bascule",
    page: "renommer_ou",
    titre: "Renommer et créer les unités d'organisation",
    role: "Google refuse un déplacement vers une unité absente, et le refuse élève par élève sans nommer la cause. On recycle l'arbre vidé, on crée ce qui manque.",
    reperer: "Aucun avertissement sur l'année visée.",
    ecran: "Renommer les OU",
    pieges: [
      "Google refuse un déplacement vers une unité absente, et le refuse élève par élève sans nommer la cause. Créer avant de basculer, jamais l'inverse.",
    ]
  },
  {
    id: "adresses",
    phase: "bascule",
    page: "conformite_google",
    titre: "Corriger les adresses divergentes",
    role: "Une adresse enregistrée qui ne désigne aucun compte fait échouer le déplacement, puis crée un doublon à l'export. Seuls les cas sans ambiguïté sont corrigés.",
    reperer: "Plus aucun écart corrigeable.",
    ecran: "onglet Adresses",
    pieges: [
      "Une adresse calculée n'est juste qu'à 93 % sur cet annuaire : une sur quatorze désigne l'homonyme. Ne jamais écrire sur une adresse qui n'a pas été constatée dans Google.",
    ]
  },
  {
    id: "controle_koxo",
    phase: "bascule",
    page: "controle_koxo",
    titre: "Contrôler l'export KoXo",
    role: "La synchronisation reconnaît un compte par son ID unique, et la date de naissance n'est pas renseignée pour la départager. Un compte non reconnu est recréé sous un autre identifiant, ou supprimé en mode destructif.",
    reperer: "Aucun écart à corriger dans KoXo — seules restent les créations.",
    pieges: [
      "La synchronisation reconnaît par ID unique, pas par date de naissance — elle n'est pas renseignée. Un compte non reconnu est recréé sous un autre identifiant.",
    ]
  },
  {
    id: "synchro_koxo",
    phase: "bascule",
    page: "exports",
    titre: "Synchroniser KoXo",
    role: "Deux passes, dans cet ordre : les sortants d'abord, rangés dans un groupe dédié, puis tous les autres. Les deux en mode non destructif — le mode destructif supprime ce qui ne figure pas dans le fichier, à commencer par les comptes que la reconnaissance a manqués.",
    reperer: "Les élèves ont changé de groupe secondaire dans KoXo, et les nouveaux ont un mot de passe.",
    ecran: "cible KoXo",
    pieges: [
      "KoXo lit le fichier comme un ÉTAT COMPLET : tout compte absent du fichier est désactivé. Un essai sur une seule ligne désactive tous les autres.",
      "À l'écran 7/8 de l'assistant, vérifier le nombre de désactivations avant de valider. Il doit correspondre à ce qu'on attend, pas à la taille de la base.",
      "Toujours en mode non destructif. Les sortants d'abord, tous les autres ensuite.",
    ]
  },
  {
    id: "comptes",
    phase: "bascule",
    page: "exports",
    titre: "Créer les comptes des nouveaux",
    role: "KoXo d'abord, qui génère les mots de passe, puis Google avec ce fichier en retour. Sans lui, la colonne mot de passe reste vide et Google refuse les créations.",
    reperer: "Le rapport indique combien de lignes ont reçu leur mot de passe.",
    pieges: [
      "KoXo d'abord, Google ensuite avec le fichier en retour. Sans lui, la colonne mot de passe reste vide et Google refuse les créations.",
    ]
  },
  {
    id: "bascule",
    phase: "bascule",
    page: "bascule",
    titre: "Basculer les élèves",
    role: "Deux temps : tout le monde à la racine avant la rentrée, puis dans sa classe le jour J. Un élève dont la classe manque à la table arrête le traitement.",
    reperer: "Aucun élève « sans OU calculable ».",
    pieges: [
      "Un élève monté d'un autre site peut avoir gardé son ancien compte : vérifier qu'il n'en a pas deux avant de déplacer, sinon on range le mauvais.",
    ]
  },
  {
    id: "groupes",
    phase: "bascule",
    page: "groupes_google",
    titre: "Créer et synchroniser les groupes",
    role: "L'export ajoute des membres sans jamais en retirer : un groupe garde ses promotions passées. La composition se calcule ici dans les deux sens.",
    reperer: "Aucun groupe déclaré ne manque à Google.",
    ecran: "Groupes Google",
    pieges: [
      "L'export CSV ajoute des membres sans jamais en retirer : un groupe garde ses promotions passées. Seule la synchronisation par l'API fait les deux sens.",
      "Un membre inconnu du référentiel n'est jamais retiré d'office — le programme ignore pourquoi il est là.",
    ]
  },
  {
    id: "chromebooks",
    phase: "bascule",
    page: "chromebooks",
    titre: "Faire le point sur les Chromebooks",
    role: "Ce qu'il faut réclamer aux partants, attribuer aux arrivants, et à ceux qui ont rendu leur machine avant l'été puis sont revenus.",
    reperer: "Plus personne n'attend de machine.",
    pieges: [
      "Dans TS1000, un interne, un AVS ou un agent d'entretien vit dans un groupe d'ACCÈS, pas de classe. L'en sortir lui ferme les portes : ne jamais proposer de déplacement depuis autre chose qu'un groupe de classe.",
      "Reprendre le CardId existant sur une modification, sinon la carte encodée cesse d'ouvrir.",
    ]
  },
];

/** Les étapes d'une phase, dans l'ordre. */
export function etapesDe(phase) {
  return ETAPES.filter((e) => e.phase === phase);
}

/**
 * L'étape correspondant à un écran, s'il y en a une.
 *
 * Plusieurs étapes mènent au même écran — la conformité en compte trois.
 * On retient donc l'étape courante quand elle y mène déjà, pour ne pas
 * ramener l'utilisateur en arrière dès qu'il change d'onglet.
 */
export function etapePour(page, idCourant = null) {
  const courante = ETAPES.find((e) => e.id === idCourant);
  if (courante && courante.page === page) return courante;
  return ETAPES.find((e) => e.page === page) ?? null;
}

export function indexDe(id) {
  return ETAPES.findIndex((e) => e.id === id);
}
