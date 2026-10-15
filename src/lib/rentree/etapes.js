/**
 * Ce que dit chaque étape de la rentrée guidée.
 *
 * Le serveur porte l'ordre, les mesures et les validations
 * (`backend/services/rentree.py`) ; ici, ce qui guide : le but en une
 * phrase, les gestes un par un, l'outil du programme ou le logiciel où
 * cliquer, et le piège. Demandé par Johann le 15 octobre 2026 : « qu'une
 * personne qui n'a jamais géré la rentrée la fasse ultra facilement en
 * suivant les étapes ».
 *
 * Les pièges viennent de la rentrée 2026-2027 et ne se redécouvrent qu'en
 * se trompant — ne jamais les retirer.
 *
 * Un geste `externe` se fait hors du programme (Charlemagne, KoXo,
 * CardStudio…) : il porte un `schema` — le dessin de l'écran où cliquer,
 * à repères numérotés — ou, tant qu'il n'est pas dessiné, la `capture`
 * qu'il faut pour le faire. Un geste `programme` embarque l'`outil`.
 *
 * @typedef {Object} Geste
 * @property {string} id
 * @property {string} titre
 * @property {"programme"|"externe"} type
 * @property {string[]} consignes
 * @property {string} fait          - le bouton qui le déclare fait
 * @property {{page: string, props?: Record<string, any>}} [outil]
 * @property {string} [schema]      - composant de `schemas/`
 * @property {Record<string, any>} [schemaProps]
 * @property {string} [capture]     - la capture qu'il faut pour le dessiner
 * @property {string} [attendu]     - ce qu'on doit voir, à comparer
 *
 * @typedef {Object} ContenuEtape
 * @property {string} duree
 * @property {string} but
 * @property {Geste[]} gestes
 * @property {string[]} [pieges]
 */

/** Quand se fait chaque chapitre — des repères tirés de la rentrée 2026. */
export const CALENDRIER = {
  ouvrir: { debut: "08-20", fin: "08-21" },
  eleves: { debut: "08-21", fin: "08-22" },
  comptes: { debut: "08-25", fin: "08-26" },
  google: { debut: "08-27", fin: "08-31" },
  documents: { debut: "09-01", fin: "09-05" },
  clore: { debut: "09-08", fin: "09-12" },
};

/** @type {Record<string, ContenuEtape>} */
export const CONTENU = {
  mise_en_place: {
    duree: "≈ 5 min",
    but: "Les réglages faits une fois pour toutes : la connexion à Google, le coffre des mots de passe, les établissements, la table des classes. Chaque étape suivante en a besoin.",
    gestes: [
      {
        id: "google",
        titre: "La connexion à Google",
        type: "programme",
        consignes: [
          "La mesure, en haut, dit ce qui manque s'il manque quelque chose.",
          "Le fichier du compte de service, l'administrateur à emprunter, puis « Tester la connexion ».",
        ],
        outil: { page: "parametres" },
        fait: "Google répond",
      },
      {
        id: "coffre",
        titre: "Le coffre des mots de passe",
        type: "programme",
        consignes: [
          "Crée-le une fois, avec un mot de passe maître que tu notes ailleurs.",
          "Ensuite, ouvre-le à chaque séance de rentrée : les étapes y rangent et y lisent les mots de passe.",
        ],
        outil: { page: "coffre" },
        fait: "Le coffre est ouvert",
      },
      {
        id: "etablissements",
        titre: "Les établissements",
        type: "programme",
        consignes: ["NDK, SU et NDE, chacun avec son domaine de messagerie et sa base KoXo."],
        outil: { page: "sites" },
        fait: "Les établissements sont en place",
      },
    ],
    pieges: [
      "Le mot de passe maître du coffre ne se retrouve pas. Note-le ailleurs avant de commencer : oublié, tous les mots de passe gardés sont perdus.",
    ],
  },

  annee: {
    duree: "≈ 10 min",
    but: "Les classes de la table visent les unités Google de l'année. Tant qu'elles visent l'ancienne, tout le reste vise la mauvaise cible.",
    gestes: [
      {
        id: "tourner",
        titre: "Faire viser l'année aux classes",
        type: "programme",
        consignes: [
          "Dans la table : « Changer l'année des OU ».",
          "Toutes les lignes, aucune laissée de côté.",
        ],
        outil: { page: "table_correspondance" },
        fait: "Les classes visent l'année",
      },
    ],
    pieges: [
      "NDK2026 désigne l'année 2025-2026 : le millésime est l'année de fin. Se tromper d'un an fait viser l'arbre qu'on vient de vider.",
    ],
  },

  eleves: {
    duree: "≈ 15 min",
    but: "Tout part de là : qui entre, qui sort, qui change de classe. Le programme lit l'export de Charlemagne et montre ce qu'il va changer avant de rien écrire.",
    gestes: [
      {
        id: "exporter",
        titre: "Exporter les élèves depuis Charlemagne",
        type: "externe",
        consignes: [
          "Élèves › Exporter une liste.",
          "Le modèle « Export rentrée enrichi » — avec Id. National, ID et MDP Réseau Péda.",
          "Toute l'année, pas une seule classe.",
          "Au format Page web (.htm).",
        ],
        capture: "Charlemagne : le menu d'export des élèves, le choix du modèle, puis la fenêtre d'enregistrement",
        fait: "J'ai le fichier",
      },
      {
        id: "ingerer",
        titre: "Le donner au programme",
        type: "programme",
        consignes: [
          "Ouvre le coffre d'abord : les mots de passe réseau s'y rangent au passage.",
          "Dépose le fichier, lis l'aperçu : entrants, sortants, changements de classe.",
          "Puis applique l'ingestion réelle.",
        ],
        outil: { page: "snapshots" },
        fait: "C'est ingéré",
      },
    ],
    pieges: [
      "Un export pris avant le 1er septembre oublie les professeurs entrants : pour les élèves, il est bon dès que les classes sont faites.",
      "Charlemagne refuse les .xlsx écrits par un programme : pour lui renvoyer un fichier, passer par Excel (sinon erreur 40057).",
    ],
  },

  departager: {
    duree: "≈ 10 min",
    but: "Deux homonymes, ou une seule personne inscrite deux fois ? Le programme ne tranche jamais seul : il présente, et attend ta décision.",
    gestes: [
      {
        id: "trancher",
        titre: "Trancher les cas en attente",
        type: "programme",
        consignes: [
          "Chaque cas montre les deux fiches côte à côte.",
          "Même date de naissance ou même INE : c'est la même personne.",
        ],
        outil: { page: "arbitrage" },
        fait: "Plus rien en attente",
      },
      {
        id: "adresses",
        titre: "Départager les adresses disputées",
        type: "programme",
        consignes: [
          "Deux homonymes calculent la même adresse : celui qui a déjà un compte la garde.",
        ],
        outil: { page: "departager" },
        fait: "Les adresses sont départagées",
      },
    ],
    pieges: [
      "Une homonymie mal résolue donne à un élève l'adresse d'un autre — et ses mails.",
    ],
  },

  professeurs: {
    duree: "≈ 10 min",
    but: "Les professeurs et les personnels de l'année. Charlemagne ne les connaît pas tous avant le 1er septembre : cette étape peut attendre.",
    gestes: [
      {
        id: "exporter",
        titre: "Exporter les personnels depuis Charlemagne",
        type: "externe",
        consignes: [
          "Personnels › Exporter une liste, avec les matières.",
          "Au format Page web (.htm).",
        ],
        capture: "Charlemagne : l'export des personnels",
        fait: "J'ai le fichier",
      },
      {
        id: "ingerer",
        titre: "Le donner au programme",
        type: "programme",
        consignes: ["Dépose le fichier, vérifie l'aperçu, applique."],
        outil: { page: "snapshots" },
        fait: "C'est ingéré",
      },
    ],
    pieges: [
      "Un export pris avant le 1er septembre omet les professeurs entrants : ils ne sont pas encore saisis dans Charlemagne.",
    ],
  },

  koxo: {
    duree: "≈ 30 min",
    but: "KoXo crée les comptes réseau des entrants et range chacun dans sa classe. C'est lui qui fabrique LE mot de passe de l'élève. NDK d'abord, SU ensuite.",
    gestes: [
      {
        id: "fichier_ndk",
        titre: "Récupérer le fichier pour NDK",
        type: "programme",
        consignes: ["Site NDK, élèves, « Tous (état complet visé) ».", "Enregistre le fichier."],
        outil: { page: "exports", props: { cibleInitiale: "koxo" } },
        fait: "J'ai le fichier NDK",
      },
      {
        id: "importer_ndk",
        titre: "L'importer dans KoXo NDK",
        type: "externe",
        consignes: [
          "Ouvre KoXo Administrateur sur le serveur de NDK.",
          "Utilisateurs › Importer ①, choisis le fichier.",
          "Mode Synchronisation non destructive ②.",
          "Compare le résumé ③ à ce que le programme attend, avant de lancer.",
        ],
        schema: "koxo_import",
        schemaProps: { base: "NDK" },
        attendu: "Désactiver 0 — toujours. Créer : les entrants de NDK.",
        fait: "C'est importé dans KoXo NDK",
      },
      {
        id: "relire_ndk",
        titre: "Redonner au programme l'export de KoXo NDK",
        type: "programme",
        consignes: [
          "Dans KoXo NDK : exporte tous les comptes, mots de passe inclus.",
          "Dépose l'export ici, en désignant la base NDK : c'est ce qui prouve que c'est fait.",
        ],
        outil: { page: "controle_koxo" },
        fait: "L'export NDK est relu",
      },
      {
        id: "fichier_su",
        titre: "Récupérer le fichier pour SU",
        type: "programme",
        consignes: ["Site SU, élèves, « Tous (état complet visé) »."],
        outil: { page: "exports", props: { cibleInitiale: "koxo" } },
        fait: "J'ai le fichier SU",
      },
      {
        id: "importer_su",
        titre: "L'importer dans KoXo SU",
        type: "externe",
        consignes: [
          "Les mêmes gestes, sur le serveur de SU.",
          "Mode Synchronisation non destructive, et Désactiver 0.",
        ],
        schema: "koxo_import",
        schemaProps: { base: "SU" },
        attendu: "Désactiver 0 — toujours. Créer : les entrants de SU.",
        fait: "C'est importé dans KoXo SU",
      },
      {
        id: "relire_su",
        titre: "Redonner au programme l'export de KoXo SU",
        type: "programme",
        consignes: ["Exporte, mots de passe inclus, et dépose ici en désignant SU."],
        outil: { page: "controle_koxo" },
        fait: "L'export SU est relu",
      },
    ],
    pieges: [
      "KoXo lit le fichier comme un ÉTAT COMPLET : tout compte absent du fichier est désactivé. Un essai sur une seule ligne désactive tous les autres.",
      "Toujours en mode non destructif. Si KoXo annonce « Désactiver » plus que 0, n'appuie pas sur Lancer.",
      "La synchronisation reconnaît un compte par son ID unique, pas par la date de naissance : un compte non reconnu est recréé sous un autre identifiant.",
    ],
  },

  charlemagne_mdp: {
    duree: "≈ 20 min",
    but: "Charlemagne garde une copie de l'identifiant et du mot de passe de chaque élève. KoXo est LE mot de passe : on vérifie que la copie est juste, et on la corrige s'il le faut.",
    gestes: [
      {
        id: "comparer",
        titre: "Comparer KoXo et Charlemagne",
        type: "programme",
        consignes: [
          "Dépose l'export Charlemagne enrichi et les deux exports KoXo, mots de passe inclus.",
          "La section « Mots de passe : KoXo ↔ Charlemagne » dit qui diffère, et fabrique le fichier de correction.",
        ],
        outil: { page: "concordance" },
        fait: "J'ai le fichier de correction",
      },
      {
        id: "importer",
        titre: "Importer la correction dans Charlemagne",
        type: "externe",
        consignes: [
          "L'import des informations complémentaires des élèves.",
          "Le fichier Charlemagne_ReseauPeda_depuis_KoXo : identifiant, ID et MDP Réseau Péda.",
          "Supprime le fichier une fois importé : il contient des mots de passe.",
        ],
        capture: "Charlemagne : l'import des informations complémentaires, et son compte rendu",
        fait: "C'est importé dans Charlemagne",
      },
      {
        id: "reingerer",
        titre: "Refaire lire Charlemagne au programme",
        type: "programme",
        consignes: ["Un nouvel export enrichi, ingéré coffre ouvert : le coffre relit la copie corrigée."],
        outil: { page: "snapshots" },
        fait: "C'est relu",
      },
    ],
    pieges: [
      "KoXo est LE mot de passe : c'est Charlemagne qu'on corrige, jamais l'inverse.",
    ],
  },

  comptes_google: {
    duree: "≈ 10 min",
    but: "Chaque nouvel élève reçoit son compte Google, avec le mot de passe de KoXo, dans l'unité de sa classe et dans son groupe.",
    gestes: [
      {
        id: "creer",
        titre: "Créer les comptes",
        type: "programme",
        consignes: [
          "« Vérifier dans Google » relève qui n'a pas de compte.",
          "Lis la liste, puis « Créer » : rien ne part sans ton clic.",
        ],
        outil: { page: "comptes_google_nouveaux" },
        fait: "Les comptes sont créés",
      },
    ],
    pieges: [
      "Un compte au même nom sous une autre adresse a souvent été créé à la main. Il n'est jamais doublé : il t'est montré, et tu le rattaches.",
    ],
  },

  sortants: {
    duree: "≈ 15 min",
    but: "Les élèves partis rejoignent l'unité des sortis, sans être suspendus : ils gardent leurs documents le temps de les récupérer.",
    gestes: [
      {
        id: "ranger",
        titre: "Ranger les sortants",
        type: "programme",
        consignes: [
          "Recoupe d'abord avec un export Charlemagne frais.",
          "Déplace, sans suspendre.",
        ],
        outil: { page: "sortants" },
        fait: "Les sortants sont rangés",
      },
    ],
    pieges: [
      "« Absent du référentiel » n'est pas une preuve de départ. En septembre 2026, 8 élèves montés de NDE seraient partis en unité de sortie, dont 3 qui n'utilisaient que leur ancien compte.",
    ],
  },

  unites: {
    duree: "≈ 15 min",
    but: "Google refuse de ranger un élève dans une unité qui n'existe pas — et le refuse élève par élève, sans dire pourquoi. On recycle l'arbre vidé, on crée ce qui manque.",
    gestes: [
      {
        id: "preparer",
        titre: "Renommer et créer les unités",
        type: "programme",
        consignes: ["Analyse, puis applique les renommages et les créations proposés."],
        outil: { page: "renommer_ou" },
        fait: "Les unités sont prêtes",
      },
    ],
    pieges: [
      "Créer avant de basculer, jamais l'inverse.",
    ],
  },

  bascule: {
    duree: "≈ 20 min",
    but: "Chaque élève rejoint l'unité de sa classe. En deux temps : tout le monde à la racine avant la rentrée, puis dans sa classe le jour J.",
    gestes: [
      {
        id: "basculer",
        titre: "Basculer les élèves",
        type: "programme",
        consignes: ["Calcule le plan, lis-le, applique."],
        outil: { page: "bascule" },
        fait: "Les élèves sont basculés",
      },
    ],
    pieges: [
      "Un élève monté d'un autre site peut avoir gardé son ancien compte : vérifier qu'il n'en a pas deux avant de déplacer, sinon on range le mauvais.",
    ],
  },

  groupes: {
    duree: "≈ 10 min",
    but: "Chaque classe a son groupe Google : les élèves qui y entrent, ceux qui en sortent.",
    gestes: [
      {
        id: "synchroniser",
        titre: "Créer et synchroniser les groupes",
        type: "programme",
        consignes: ["Analyse, lis qui entre et qui sort, puis synchronise."],
        outil: { page: "groupes_google" },
        fait: "Les groupes sont à jour",
      },
    ],
    pieges: [
      "Les adultes mis à la main dans un groupe de classe n'en sont jamais retirés.",
      "Un membre inconnu du référentiel n'est jamais retiré d'office — le programme ignore pourquoi il est là.",
    ],
  },

  etiquettes: {
    duree: "≈ 30 min",
    but: "Chaque élève reçoit son étiquette : identifiant, mot de passe, adresse. Une planche par classe, pour chaque professeur principal.",
    gestes: [
      {
        id: "planches",
        titre: "Sortir les étiquettes et les listes",
        type: "programme",
        consignes: [
          "Source « Du coffre » : pas de fichier KoXo à charger.",
          "« Étiquettes en PDF, une planche par classe ».",
        ],
        outil: { page: "exports", props: { cibleInitiale: "listes" } },
        fait: "Les étiquettes sont imprimées",
      },
    ],
    pieges: [
      "Un élève dont le relevé KoXo est contredit n'a pas d'étiquette : le programme le nomme, relis KoXo avant d'imprimer.",
    ],
  },

  cartes: {
    duree: "≈ 1 h",
    but: "Les cartes des entrants et de ceux qui changent d'établissement, photos comprises.",
    gestes: [
      {
        id: "fichier",
        titre: "Préparer le fichier des cartes",
        type: "programme",
        consignes: ["Coche les élèves, vérifie les photos, enregistre le fichier."],
        outil: { page: "cartes" },
        fait: "J'ai le fichier",
      },
      {
        id: "imprimer",
        titre: "L'importer dans CardStudio et imprimer",
        type: "externe",
        consignes: [
          "Import par la colonne « Clé unique » : un nouvel élève s'ajoute sans recréer le projet.",
          "Imprime, puis encode.",
        ],
        capture: "CardStudio : l'import du fichier, le réglage de la clé unique, l'impression",
        fait: "Les cartes sont faites",
      },
    ],
    pieges: [
      "Ne pas écraser le projet CardStudio d'origine : importer dans le projet, ne pas le recréer.",
    ],
  },

  badges: {
    duree: "≈ 30 min",
    but: "La centrale d'accès connaît chaque carte : ajouts, déplacements et retraits, en lots numérotés.",
    gestes: [
      {
        id: "differentiel",
        titre: "Calculer les lots",
        type: "programme",
        consignes: ["Dépose l'export Users.xls de la centrale : le différentiel se calcule contre elle."],
        outil: { page: "ts1000" },
        fait: "J'ai les lots",
      },
      {
        id: "importer",
        titre: "Les importer dans la centrale",
        type: "externe",
        consignes: ["Dans l'ordre des numéros."],
        capture: "TS1000 : l'export Users.xls, puis l'import d'un lot",
        fait: "Les lots sont importés",
      },
    ],
    pieges: [
      "Un interne, un AVS ou un agent d'entretien vit dans un groupe d'ACCÈS, pas de classe : ne jamais l'en sortir, ça lui ferme les portes.",
      "Reprendre le CardId existant sur une modification, sinon la carte encodée cesse d'ouvrir.",
    ],
  },

  pmb_sodexo: {
    duree: "≈ 20 min",
    but: "Les lecteurs du CDI et les élèves de la restauration.",
    gestes: [
      {
        id: "pmb",
        titre: "Les lecteurs PMB",
        type: "programme",
        consignes: ["Dépose l'export Charlemagne : un fichier par établissement, sans en-tête."],
        outil: { page: "exports", props: { cibleInitiale: "pmb" } },
        fait: "J'ai les fichiers PMB",
      },
      {
        id: "pmb_import",
        titre: "Les importer dans PMB",
        type: "externe",
        consignes: ["Les cases à cocher comptent : voir l'aide de l'écran PMB."],
        capture: "PMB : l'écran d'import des lecteurs, avec ses cases",
        fait: "C'est importé dans PMB",
      },
      {
        id: "sodexo",
        titre: "Sodexo",
        type: "programme",
        consignes: ["Le fichier naît du classeur Google ; l'écran dit ce qui a changé."],
        outil: { page: "sodexo" },
        fait: "Sodexo est à jour",
      },
    ],
  },

  chromebooks: {
    duree: "≈ 1 h",
    but: "Ce qu'il faut réclamer aux partants, attribuer aux arrivants, et à ceux qui ont rendu leur machine avant l'été puis sont revenus.",
    gestes: [
      {
        id: "point",
        titre: "Faire le point sur la flotte",
        type: "programme",
        consignes: ["Qui attend une machine, qui doit la rendre."],
        outil: { page: "chromebooks" },
        fait: "Le point est fait",
      },
    ],
  },

  bilan: {
    duree: "≈ 10 min",
    but: "Ce qui a été fait, système par système, et ce qui reste à suivre.",
    gestes: [
      {
        id: "lire",
        titre: "Lire le bilan",
        type: "programme",
        consignes: ["Ce qui reste à suivre se retrouve dans « Où ça coince »."],
        outil: { page: "bilan" },
        fait: "C'est lu",
      },
    ],
  },
};

/** Le premier geste pas encore déclaré fait — celui qu'on montre ouvert. */
export function gesteCourant(contenu, faits) {
  return contenu?.gestes.find((g) => !faits.includes(g.id)) ?? null;
}
