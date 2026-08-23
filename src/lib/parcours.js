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
  },
  {
    id: "amorcage",
    phase: "preparation",
    page: "amorcage",
    titre: "Amorcer depuis KoXo",
    role: "Récupère les identifiants déjà attribués. Un login est fixé pour toute la scolarité : le régénérer romprait tout ce qui s'y rattache.",
    reperer: "Les personnes existantes portent leur login d'origine.",
  },
  {
    id: "ingestion",
    phase: "preparation",
    page: "snapshots",
    titre: "Ingérer l'export Charlemagne",
    role: "Crée la photographie de l'année : qui est inscrit, dans quelle classe. C'est elle qui sert de référence à tout le reste.",
    reperer: "L'année préparée apparaît, avec son effectif.",
  },
  {
    id: "arbitrage",
    phase: "preparation",
    page: "arbitrage",
    titre: "Trancher les cas ambigus",
    role: "Collisions de login, homonymies, adresses visées par plusieurs personnes. Le programme ne tranche jamais seul : il présente et attend.",
    reperer: "Plus aucune décision en attente.",
  },

  {
    id: "vider",
    phase: "bascule",
    page: "sortants",
    titre: "Vider l'arbre de l'année révolue",
    role: "Les comptes qui restent dans le plus ancien arbre sont ceux des élèves partis un an plus tôt. Ils rejoignent leur unité de sortie, sans être suspendus.",
    reperer: "La branche est annoncée vide, ou ne garde que des élèves encore inscrits.",
    ecran: "Vider une arborescence d'année",
  },
  {
    id: "rotation",
    phase: "bascule",
    page: "table_correspondance",
    titre: "Tourner la table de correspondance",
    role: "Les chemins d'unités d'organisation portent l'année en toutes lettres. Tant qu'ils désignent l'ancienne, tout le reste vise la mauvaise cible.",
    reperer: "Toutes les lignes sont modifiées, aucune laissée de côté.",
    ecran: "Changer l'année des OU",
  },
  {
    id: "arborescence",
    phase: "bascule",
    page: "conformite_google",
    titre: "Renommer et créer les unités d'organisation",
    role: "Google refuse un déplacement vers une unité absente, et le refuse élève par élève sans nommer la cause. On recycle l'arbre vidé, on crée ce qui manque.",
    reperer: "Aucun avertissement sur l'année visée.",
    ecran: "onglet Arborescence",
  },
  {
    id: "adresses",
    phase: "bascule",
    page: "conformite_google",
    titre: "Corriger les adresses divergentes",
    role: "Une adresse enregistrée qui ne désigne aucun compte fait échouer le déplacement, puis crée un doublon à l'export. Seuls les cas sans ambiguïté sont corrigés.",
    reperer: "Plus aucun écart corrigeable.",
    ecran: "onglet Adresses",
  },
  {
    id: "comptes",
    phase: "bascule",
    page: "exports",
    titre: "Créer les comptes des nouveaux",
    role: "KoXo d'abord, qui génère les mots de passe, puis Google avec ce fichier en retour. Sans lui, la colonne mot de passe reste vide et Google refuse les créations.",
    reperer: "Le rapport indique combien de lignes ont reçu leur mot de passe.",
  },
  {
    id: "bascule",
    phase: "bascule",
    page: "bascule",
    titre: "Basculer les élèves",
    role: "Deux temps : tout le monde à la racine avant la rentrée, puis dans sa classe le jour J. Un élève dont la classe manque à la table arrête le traitement.",
    reperer: "Aucun élève « sans OU calculable ».",
  },
  {
    id: "groupes",
    phase: "bascule",
    page: "conformite_google",
    titre: "Créer et synchroniser les groupes",
    role: "L'export ajoute des membres sans jamais en retirer : un groupe garde ses promotions passées. La composition se calcule ici dans les deux sens.",
    reperer: "Aucun groupe déclaré ne manque à Google.",
    ecran: "onglet Groupes",
  },
  {
    id: "chromebooks",
    phase: "bascule",
    page: "chromebooks",
    titre: "Faire le point sur les Chromebooks",
    role: "Ce qu'il faut réclamer aux partants, attribuer aux arrivants, et à ceux qui ont rendu leur machine avant l'été puis sont revenus.",
    reperer: "Plus personne n'attend de machine.",
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
