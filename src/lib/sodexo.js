/**
 * La procédure Sodexo, écrite là où elle sert.
 *
 * ## Pourquoi le programme ne fabrique pas ce fichier
 *
 * Le CSV d'import naît d'un classeur Google qui reçoit l'export Charlemagne
 * et le transforme. Reproduire cette transformation sans l'avoir lue
 * produirait un fichier qui **ressemble** au bon sans en être un — et sur
 * de la restauration scolaire, l'erreur se découvre au self, un midi.
 *
 * Le programme fait donc ce qu'il sait faire de mieux ici : porter la
 * procédure, dans l'ordre, avec ses pièges et ses liens, pour qu'elle ne
 * vive plus dans un document qu'on ne retrouve pas.
 *
 * ## Pourquoi le mot de passe n'y est pas
 *
 * Un mot de passe écrit dans le programme part dans le dépôt, y reste dans
 * l'historique, et suit chaque installation. Il devient surtout **faux** :
 * la note d'origine de cette procédure en portait deux, dont un périmé
 * depuis un changement du 8 avril. Une procédure qui affiche un mot de
 * passe périmé fait perdre plus de temps qu'une qui n'en affiche aucun.
 *
 * L'identifiant est rappelé — il désigne un compte, il ne l'ouvre pas.
 *
 * ## L'adresse du classeur est un réglage
 *
 * Elle change si le document est déplacé ou dupliqué. Elle se déclare dans
 * les Paramètres plutôt que d'être figée ici.
 */

export const PORTAIL_SODEXO =
  "https://sodexo-nddukreisker-fr002586-solutions.moneweb.fr";

export const IDENTIFIANT_SODEXO = "ggallic";

/**
 * @typedef {Object} EtapeSodexo
 * @property {string} titre
 * @property {string[]} gestes    - ce qu'on fait, dans l'ordre
 * @property {string[]} [pieges]  - ce qui peut mal tourner
 * @property {{libelle: string, url?: string, reglage?: string}[]} [liens]
 */

/**
 * @typedef {Object} ProcedureSodexo
 * @property {string} id
 * @property {string} titre
 * @property {string} resume
 * @property {EtapeSodexo[]} etapes
 * @property {string[]} memo - le format attendu, à vérifier en cas de refus
 */

/** @type {ProcedureSodexo[]} */
export const PROCEDURES = [
  {
    id: "eleves",
    titre: "Les élèves",
    resume:
      "Trois temps : sortir l'export de Charlemagne, le transformer dans le classeur, importer le CSV dans le portail.",
    etapes: [
      {
        titre: "Sortir l'export de Charlemagne",
        gestes: [
          "Charlemagne Administratif → Traitement → Éditions → Listes → Les éditions établissements",
          "Double-cliquer sur « Liste des élèves - Export vers SoHappy »",
          "Valider la fenêtre « Sélection simple des élèves et des familles »",
        ],
        pieges: [
          "C'est l'édition « Export vers SoHappy » et aucune autre : les listes voisines n'ont pas les mêmes colonnes, et le classeur ne saura pas les lire.",
        ],
      },
      {
        titre: "Transformer dans le classeur",
        gestes: [
          "Ouvrir le classeur « SoHappy - Import des élèves »",
          "Vider entièrement l'onglet Import",
          "Coller le contenu de l'export de l'étape 1 dans l'onglet Import",
          "Aller sur l'onglet Export",
          "Menu → Exporter le fichier CSV → Cooperl",
          "Télécharger le fichier produit",
        ],
        pieges: [
          "Vider l'onglet Import AVANT de coller : un reliquat de l'export précédent ferait entrer des élèves partis, et le portail les recréerait.",
          "L'export se prend sur l'onglet Export, pas sur l'onglet Import — ce sont les colonnes transformées qui partent chez Sodexo.",
        ],
        liens: [
          {
            libelle: "Le classeur SoHappy - Import des élèves",
            reglage: "url_classeur_sodexo_eleves",
          },
        ],
      },
      {
        titre: "Importer dans le portail",
        gestes: [
          "Se connecter au portail Sodexo",
          "Icône Administration → Imports → Comptes/Convives",
          "Cliquer l'engrenage de « Import comptes par badge - Classification 1 - Elèves »",
          "Choisir le CSV de l'étape 2, puis valider",
        ],
        pieges: [
          "Bien prendre la ligne « Classification 1 - Elèves » : celle des adultes attend d'autres colonnes et refuserait le fichier — ou pire, l'accepterait mal.",
        ],
        liens: [{ libelle: "Portail Sodexo", url: PORTAIL_SODEXO }],
      },
    ],
    memo: [
      "CSV, séparateur point-virgule",
      "Attributs : Code établissement · Code niveau · Code classe · Code régime · Nom et prénom · Nom · Prénom · Photo",
      "Code régime : P / D / E par défaut — et 10P, 10POGEC, 50P, 75P, PREFERENTIEL, GRATUITE, passageS",
    ],
  },
  {
    id: "adultes",
    titre: "Les personnels",
    resume:
      "Plus court : Charlemagne écrit directement le CSV, il n'y a pas de classeur intermédiaire.",
    etapes: [
      {
        titre: "Sortir l'export de Charlemagne",
        gestes: [
          "Charlemagne Administratif → Administration → Adultes - Autres tiers → Éditions",
          "Lancer l'édition « Liste Adultes - Export vers SoHappy »",
          "Enregistrer en CSV, séparateur point-virgule",
          "Nommer : ExportCharlemagnePourSodexoAdultesYYMMDD",
        ],
        pieges: [
          "Le type doit être CSV point-virgule à l'enregistrement : Charlemagne propose d'autres formats, et le portail les refuse.",
        ],
      },
      {
        titre: "Importer dans le portail",
        gestes: [
          "Se connecter au portail Sodexo",
          "Icône Administration → Imports → Comptes/Convives",
          "Cliquer l'engrenage de « Import comptes par badge - Classification 1 - Adultes »",
          "Choisir le CSV de l'étape 1, puis valider",
        ],
        pieges: [
          "Ligne « Classification 1 - Adultes », pas celle des élèves.",
        ],
        liens: [{ libelle: "Portail Sodexo", url: PORTAIL_SODEXO }],
      },
    ],
    memo: [
      "CSV, séparateur point-virgule",
      "Attributs : N° de badge · Nom · Prénom · Identifiant",
    ],
  },
];
