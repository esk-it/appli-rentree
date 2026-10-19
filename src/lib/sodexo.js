/**
 * La procédure SoHappy, écrite là où elle sert.
 *
 * Source : « Procédure SoHappy - Import des comptes », deux pages, une par
 * population. Les pictogrammes qui l'accompagnent sont repris tels quels :
 * ce sont ceux qu'on voit à l'écran au moment du geste, et une icône
 * reconnue vaut mieux qu'une phrase qui la décrit.
 *
 * ## Pourquoi le programme fabrique désormais le fichier
 *
 * Le CSV naissait d'un classeur Google. Lu de près le 19 octobre 2026, il
 * n'avait jamais transmis les réductions : son script exportait l'onglet
 * Import au lieu de l'onglet Export, et les codes particuliers (10P,
 * 10POGEC) restaient dans une colonne que le portail ne lit pas. Le
 * programme reprend la seule règle du classeur — le code particulier
 * d'abord, sinon le régime — et la vérifie
 * (`backend/services/sodexo_fichier.py`).
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
import imageProgramme from "./assets/marque/losanges.png";
import imageClasseur from "./assets/sodexo/classeur-google.png";
import imageSodexo from "./assets/sodexo/sodexo.png";
import imageAdministration from "./assets/sodexo/administration.png";
import imageEngrenage from "./assets/sodexo/engrenage.png";

export const PORTAIL_SODEXO =
  "https://sodexo-nddukreisker-fr002586-solutions.moneweb.fr";

export const IDENTIFIANT_SODEXO = "ggallic";

export const REGLAGE_CLASSEUR_ELEVES = "url_classeur_sodexo_eleves";

/**
 * Les profils de gestion élèves du portail, avec leur libellé tel qu'il
 * s'affiche chez Sodexo (Administration › Configurations › Profils de
 * gestion, relevés le 19/10/2026). Le Code Régime du fichier désigne le
 * profil ; c'est le profil qui porte la subvention.
 *
 * Les codes acceptés par le programme se règlent dans les Paramètres
 * (`sodexo.profils_eleves`) ; un code sans libellé ici s'affiche seul.
 */
export const PROFILS_ELEVES = [
  { code: "D", libelle: "DEMI PENSIONNAIRE" },
  { code: "E", libelle: "EXTERNE" },
  { code: "P", libelle: "PENSIONNAIRE" },
  { code: "10P", libelle: "Subvention 10% sur formule" },
  { code: "10POGEC", libelle: "Subvention 10% sur formule ogec" },
  { code: "33P", libelle: "Subvention 33.33% sur formule" },
  { code: "50P", libelle: "Subvention 50% sur formule" },
  { code: "GRATUITE", libelle: "GRATUITE Subvention 100% sur formule" },
];

/** @param {string} code */
export const libelleProfil = (code) =>
  PROFILS_ELEVES.find((p) => p.code === code)?.libelle ?? "";

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
  programme: { nom: "Ce programme", image: imageProgramme },
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

/** @typedef {{code: string, libelle: string}} ProfilSodexo */

/**
 * @typedef {Object} ProcedureSodexo
 * @property {string} id
 * @property {string} titre
 * @property {string} resume
 * @property {EtapeSodexo[]} etapes
 * @property {{format: string, attributs: string[], regimes?: {defaut: ProfilSodexo[], autres: ProfilSodexo[]}}} memo
 */

/** @type {ProcedureSodexo[]} */
export const PROCEDURES = [
  {
    id: "eleves",
    titre: "Les élèves",
    resume:
      "Charlemagne sort la liste, le programme en fait le fichier et le vérifie, le portail l'avale.",
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
        titre: "Fabriquer le fichier",
        lieu: "programme",
        gestes: [
          { texte: "Dans cet écran, l'onglet", cible: "Fabriquer le fichier" },
          { texte: "Déposer l'édition de l'étape 1, telle qu'elle sort" },
          { texte: "Lire le rapport : codes particuliers, inscrits absents, erreurs" },
          { texte: "Enregistrer le CSV" },
        ],
        produit: "le CSV à importer",
        pieges: [
          "Le code particulier de Charlemagne (colonne PassageS : 10P, 10POGEC…) passe avant le régime : c'est lui qui donne la réduction. L'ancien classeur Google ne l'envoyait pas.",
          "Un code refusé par le programme n'existe pas comme profil dans le portail : l'élève n'y aurait aucun tarif. Corriger Charlemagne, ou ajouter le profil aux Paramètres s'il vient d'être créé chez Sodexo.",
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
      format: "CSV UTF-8, séparateur point-virgule — le portail repère les colonnes par leur en-tête",
      attributs: [
        "Num Badge — la clé du compte",
        "Nom",
        "Prénom",
        "Code Régime — devient le profil de gestion, donc le tarif",
      ],
      // 75P, PREFERENTIEL et passageS, cités par la procédure d'origine,
      // n'existent pas comme profils au portail.
      regimes: {
        defaut: PROFILS_ELEVES.slice(0, 3),
        autres: PROFILS_ELEVES.slice(3),
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
