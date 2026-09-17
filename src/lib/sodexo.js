/**
 * La procédure SoHappy, écrite là où elle sert.
 *
 * Source : « Procédure SoHappy - Import des comptes », deux pages, une par
 * population. Les pictogrammes qui l'accompagnent sont repris tels quels :
 * ce sont ceux qu'on voit à l'écran au moment du geste, et une icône
 * reconnue vaut mieux qu'une phrase qui la décrit.
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
 * vive plus dans un PDF qu'on ne retrouve pas.
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
 * Elle change si le document est déplacé ou dupliqué. Elle se déclare donc
 * une fois, depuis l'écran, plutôt que d'être figée ici.
 */

import imageCharlemagne from "./assets/sodexo/charlemagne.png";
import imageClasseur from "./assets/sodexo/classeur-google.png";
import imageSodexo from "./assets/sodexo/sodexo.png";
import imageAdministration from "./assets/sodexo/administration.png";
import imageEngrenage from "./assets/sodexo/engrenage.png";

export const PORTAIL_SODEXO =
  "https://sodexo-nddukreisker-fr002586-solutions.moneweb.fr";

export const IDENTIFIANT_SODEXO = "ggallic";

export const REGLAGE_CLASSEUR_ELEVES = "url_classeur_sodexo_eleves";

/**
 * Les trois endroits où se passe la procédure.
 *
 * Leurs logos sont toujours posés sur une plaque blanche, en thème sombre
 * comme en clair : ils sont dessinés pour du papier, et le bleu marine de
 * Sodexo disparaît sur un fond anthracite.
 */
export const LIEUX = {
  charlemagne: { nom: "Charlemagne", image: imageCharlemagne },
  classeur: { nom: "Le classeur Google", image: imageClasseur },
  portail: { nom: "Le portail Sodexo", image: imageSodexo },
};

/**
 * Les icônes du portail, à la taille où elles se reconnaissent.
 *
 * Celle d'Administration embarque son libellé : réduite à la hauteur d'une
 * ligne, le mot devient un pâté gris. Chacune porte donc sa hauteur.
 */
export const ICONES = {
  administration: {
    image: imageAdministration,
    alt: "Administration",
    hauteur: "h-8",
  },
  engrenage: { image: imageEngrenage, alt: "Engrenage", hauteur: "h-5" },
};

/**
 * Un geste, sous l'une de ces formes :
 *
 *   { depuis, chemin: [...] }   un chemin de menus, à suivre dans l'ordre
 *   { texte, cible }            une action, et l'intitulé exact à viser
 *   { texte, touches: [[…]] }   une action au clavier
 *   { texte, icone }            une action sur une icône reconnaissable
 *   { texte }                   une action qui se suffit
 *
 * @typedef {Object} Geste
 * @property {string} [texte]
 * @property {string} [depuis]
 * @property {string[]} [chemin]
 * @property {string} [cible]
 * @property {string[][]} [touches]
 * @property {"administration" | "engrenage"} [icone]
 */

/**
 * @typedef {Object} EtapeSodexo
 * @property {string} titre
 * @property {keyof typeof LIEUX} lieu
 * @property {Geste[]} gestes
 * @property {string} [produit]   - ce qui sort de l'étape
 * @property {string[]} [pieges]
 * @property {{libelle: string, url?: string, reglage?: string}[]} [liens]
 */

/**
 * @typedef {Object} ProcedureSodexo
 * @property {string} id
 * @property {string} titre
 * @property {string} resume
 * @property {EtapeSodexo[]} etapes
 * @property {{format: string, attributs: string[], regimes?: {defaut: string[], autres: string[]}}} memo
 */

/** @type {ProcedureSodexo[]} */
export const PROCEDURES = [
  {
    id: "eleves",
    titre: "Les élèves",
    resume:
      "Charlemagne sort la liste, le classeur Google la transforme, le portail l'avale.",
    etapes: [
      {
        titre: "Sortir la liste de Charlemagne",
        lieu: "charlemagne",
        gestes: [
          {
            depuis: "Charlemagne Administratif",
            chemin: [
              "Traitement",
              "Éditions",
              "Listes",
              "Les éditions établissements",
            ],
          },
          {
            texte: "Double-cliquer sur",
            cible: "Liste des élèves - Export vers SoHappy",
          },
          {
            texte: "Valider la fenêtre",
            cible: "Sélection simple des élèves et des familles",
          },
        ],
        produit: "un classeur .xlsx ÉLÈVES",
        pieges: [
          "C'est cette édition et aucune autre : les listes voisines n'ont pas les mêmes colonnes, et le classeur ne saura pas les lire.",
        ],
      },
      {
        titre: "Transformer dans le classeur",
        lieu: "classeur",
        gestes: [
          { texte: "Ouvrir le classeur", cible: "SoHappy - Import des élèves" },
          {
            texte: "Onglet Import : tout sélectionner, puis supprimer",
            touches: [
              ["Ctrl", "A"],
              ["Suppr"],
            ],
          },
          {
            texte: "Copier le contenu du fichier de l'étape 1",
            touches: [["Ctrl", "C"]],
          },
          {
            texte: "Le coller dans l'onglet Import",
            touches: [["Ctrl", "V"]],
          },
          { texte: "Passer sur l'onglet Export" },
          { depuis: "Menu", chemin: ["Exporter le fichier CSV", "Cooperl"] },
          { texte: "Télécharger le fichier produit" },
        ],
        produit: "le CSV à importer",
        pieges: [
          "Vider l'onglet Import AVANT de coller : un reliquat de l'export précédent ferait entrer des élèves partis, et le portail les recréerait.",
          "L'export se prend sur l'onglet Export, pas sur l'onglet Import — ce sont les colonnes transformées qui partent chez Sodexo.",
        ],
        liens: [
          {
            libelle: "SoHappy - Import des élèves",
            reglage: REGLAGE_CLASSEUR_ELEVES,
          },
        ],
      },
      {
        titre: "Importer dans le portail",
        lieu: "portail",
        gestes: [
          { texte: "Se connecter au portail" },
          { texte: "Cliquer l'icône", icone: "administration" },
          { depuis: "Puis", chemin: ["Imports", "Comptes/Convives"] },
          {
            texte: "Cliquer l'engrenage de la ligne",
            cible: "Import comptes par badge - Classification 1 - Elèves",
            icone: "engrenage",
          },
          { texte: "Choisir le CSV de l'étape 2, puis valider" },
        ],
        pieges: [
          "Bien prendre la ligne « Classification 1 - Elèves » : celle des adultes attend d'autres colonnes et refuserait le fichier — ou pire, l'accepterait mal.",
        ],
        liens: [{ libelle: "Portail Sodexo", url: PORTAIL_SODEXO }],
      },
    ],
    memo: {
      format: "CSV, séparateur point-virgule",
      attributs: [
        "Code établissement",
        "Code niveau",
        "Code classe",
        "Code régime",
        "Nom et prénom",
        "Nom",
        "Prénom",
        "Photo",
      ],
      regimes: {
        defaut: ["P", "D", "E"],
        autres: [
          "10P",
          "10POGEC",
          "50P",
          "75P",
          "PREFERENTIEL",
          "GRATUITE",
          "passageS",
        ],
      },
    },
  },
  {
    id: "adultes",
    titre: "Les personnels",
    resume:
      "Plus court : Charlemagne écrit directement le CSV, il n'y a pas de classeur intermédiaire.",
    etapes: [
      {
        titre: "Sortir la liste de Charlemagne",
        lieu: "charlemagne",
        gestes: [
          {
            depuis: "Charlemagne Administratif",
            chemin: ["Administration", "Adultes - Autres tiers", "Éditions"],
          },
          {
            texte: "Lancer l'édition",
            cible: "Liste Adultes - Export vers SoHappy",
          },
          {
            texte: "Enregistrer sous le nom",
            cible: "ExportCharlemagnePourSodexoAdultesYYMMDD",
          },
          { texte: "Type : CSV (séparateur : point-virgule)" },
        ],
        produit: "le CSV à importer",
        pieges: [
          "Le type doit être CSV point-virgule à l'enregistrement : Charlemagne propose d'autres formats, et le portail les refuse.",
        ],
      },
      {
        titre: "Importer dans le portail",
        lieu: "portail",
        gestes: [
          { texte: "Se connecter au portail" },
          { texte: "Cliquer l'icône", icone: "administration" },
          { depuis: "Puis", chemin: ["Imports", "Comptes/Convives"] },
          {
            texte: "Cliquer l'engrenage de la ligne",
            cible: "Import comptes par badge - Classification 1 - Adultes",
            icone: "engrenage",
          },
          { texte: "Choisir le CSV de l'étape 1, puis valider" },
        ],
        pieges: [
          "Ligne « Classification 1 - Adultes », pas celle des élèves. La procédure d'origine renvoie ici à « l'étape 2 » — il n'y en a pas pour les adultes, c'est le fichier de l'étape 1.",
        ],
        liens: [{ libelle: "Portail Sodexo", url: PORTAIL_SODEXO }],
      },
    ],
    memo: {
      format: "CSV, séparateur point-virgule",
      attributs: ["N° de badge", "Nom", "Prénom", "Identifiant"],
    },
  },
];
