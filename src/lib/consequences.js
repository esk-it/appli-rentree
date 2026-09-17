/**
 * Ce qu'un mouvement entraîne, et que personne ne retient en entier.
 *
 * ## D'où vient cet écran
 *
 * À la question « quels documents sors-tu le plus souvent ? », la réponse
 * a été : *« les étiquettes, la liste des sans-photo, et à l'ajout d'un
 * nouvel élève je dois refaire les imports PMB et Sodexo »*.
 *
 * Cette dernière phrase n'est pas une demande de document : c'est une
 * **conséquence**. Le bon écran n'est donc pas un sélecteur « qui × quoi »,
 * mais la liste de ce qu'un mouvement déclenche — un élève arrive, part, ou
 * change de classe, et sept ou huit systèmes doivent suivre.
 *
 * ## Pourquoi l'écrire plutôt que s'en souvenir
 *
 * Un mouvement en cours d'année est rare et isolé. On en traite trois en
 * novembre, deux en février, et entre les deux on a oublié qu'il fallait
 * aussi reprendre PMB. Ce qu'on oublie ne se voit pas tout de suite : la
 * carte n'ouvre plus une porte en janvier, l'élève n'est pas au self en
 * mars, et personne ne fait le lien.
 *
 * ## Ce que ce module n'est pas
 *
 * Pas une automatisation : chaque conséquence reste un geste, souvent dans
 * un autre logiciel. C'est une liste à cocher qui sait où mène chaque case,
 * et ce qui peut y mal tourner.
 */

/**
 * @typedef {Object} Consequence
 * @property {string} id
 * @property {string} titre
 * @property {string} pourquoi    - ce qui casse si on l'oublie
 * @property {string} [page]      - l'écran qui le fait, s'il existe
 * @property {string} [ailleurs]  - le logiciel tiers, quand ce n'est pas nous
 * @property {string} [piege]
 */

/**
 * @typedef {Object} Mouvement
 * @property {string} id
 * @property {string} titre
 * @property {string} resume
 * @property {string} ton
 * @property {Consequence[]} consequences
 */

/** @type {Mouvement[]} */
export const MOUVEMENTS = [
  {
    id: "arrivee",
    titre: "Un élève arrive",
    resume:
      "En cours d'année : il n'était dans aucun des exports de rentrée, donc rien ne le connaît.",
    ton: "emerald",
    consequences: [
      {
        id: "referentiel",
        titre: "L'inscrire au référentiel",
        pourquoi:
          "Tout le reste s'y rattache : sans fiche, il n'a ni login figé ni adresse, et aucun export ne le verra.",
        page: "arrivees",
        piege:
          "Le login attribué ici est figé pour toute sa scolarité. Le corriger ensuite casse Google, KoXo et les étiquettes d'un coup.",
      },
      {
        id: "koxo",
        titre: "Créer son compte KoXo",
        pourquoi:
          "C'est KoXo qui génère le mot de passe, et Google en a besoin pour créer le compte.",
        page: "exports",
        piege:
          "KoXo d'abord, Google ensuite avec le fichier en retour. L'inverse laisse la colonne mot de passe vide et Google refuse.",
      },
      {
        id: "google",
        titre: "Créer son compte Google et l'y ranger",
        pourquoi:
          "Sans compte, pas de messagerie ni de Drive ; sans la bonne unité, les règles de sa classe ne s'appliquent pas.",
        page: "arrivees",
      },
      {
        id: "groupe",
        titre: "L'ajouter au groupe de sa classe",
        pourquoi:
          "Les professeurs écrivent au groupe. Un élève absent du groupe ne reçoit simplement rien.",
        page: "personnes",
        piege:
          "Depuis sa fiche, « Déplacer dans Google » fait l'unité et les groupes en un seul geste.",
      },
      {
        id: "ts1000",
        titre: "Lui créer un badge dans TS1000",
        pourquoi: "Sans badge, aucune porte ne s'ouvre.",
        page: "ts1000",
        piege:
          "Le différentiel le proposera en création dès que le référentiel le connaîtra — inutile de le saisir à la main.",
      },
      {
        id: "carte",
        titre: "Imprimer et encoder sa carte",
        pourquoi: "Le badge existe dans la centrale, mais il lui faut l'objet.",
        page: "exports",
        piege: "Un fichier CardStudio par projet : sortir la carte avec les autres en attente.",
      },
      {
        id: "photo",
        titre: "Récupérer sa photo",
        pourquoi:
          "Sans photo, sa carte sort sans visage et le trombinoscope reste incomplet.",
        page: "photos",
      },
      {
        id: "pmb",
        titre: "Refaire l'import PMB",
        pourquoi: "Sans lui, il ne peut pas emprunter au CDI.",
        page: "exports",
        ailleurs: "PMB",
      },
      {
        id: "sodexo",
        titre: "Refaire l'import Sodexo",
        pourquoi: "Sans lui, son badge ne passe pas au self.",
        page: "sodexo",
        ailleurs: "Sodexo / SoHappy",
      },
      {
        id: "etiquette",
        titre: "Lui remettre son étiquette d'identifiants",
        pourquoi: "Il ne peut rien ouvrir tant qu'il ne connaît pas son mot de passe.",
        page: "exports",
      },
    ],
  },
  {
    id: "depart",
    titre: "Un élève part",
    resume:
      "Rien ne se supprime tout de suite : on range, on prévient, et on supprime plus tard.",
    ton: "amber",
    consequences: [
      {
        id: "desinscription",
        titre: "Le retirer de l'année",
        pourquoi:
          "C'est ce qui le sort des effectifs et des exports à venir. Sa fiche reste — son login demeure réservé.",
        page: "personnes",
        piege:
          "La fiche n'est jamais supprimée : si l'élève revient, il retrouve son identité et son login.",
      },
      {
        id: "google",
        titre: "Ranger son compte Google en unité de sortie",
        pourquoi:
          "Sans suspension : il garde l'accès à ses données le temps de les récupérer.",
        page: "sortants",
        piege:
          "« Absent du référentiel » n'est pas une preuve de départ — vérifier avant de déplacer. Huit élèves montés de NDE ont failli y passer.",
      },
      {
        id: "koxo",
        titre: "Le laisser sortir de KoXo à la prochaine synchro",
        pourquoi:
          "La synchronisation désactive ce qui n'est plus dans le fichier — il n'y a rien à faire de plus.",
        page: "exports",
        piege:
          "KoXo lit le fichier comme un état complet : ne jamais synchroniser une liste partielle.",
      },
      {
        id: "ts1000",
        titre: "Retirer son badge de TS1000",
        pourquoi: "Un badge parti qui ouvre encore est un badge en circulation.",
        page: "ts1000",
      },
      {
        id: "materiel",
        titre: "Récupérer sa carte et son Chromebook",
        pourquoi:
          "Le matériel ne revient pas tout seul, et la machine repart en stock ou en pièces.",
        page: "chromebooks",
      },
      {
        id: "pmb_sodexo",
        titre: "Refaire PMB et Sodexo",
        pourquoi:
          "Tant qu'ils ne sont pas repris, il figure encore comme emprunteur et comme convive.",
        page: "sodexo",
        ailleurs: "PMB · Sodexo",
      },
    ],
  },
  {
    id: "changement",
    titre: "Un élève change de classe",
    resume:
      "Le cas le plus discret, et celui qui se voit le plus tard : tout marche encore, mais au mauvais endroit.",
    ton: "sky",
    consequences: [
      {
        id: "referentiel",
        titre: "Corriger sa classe au référentiel",
        pourquoi:
          "Toutes les cibles s'en déduisent : tant qu'elle est fausse ici, elle le reste partout.",
        page: "snapshots",
        piege:
          "Une réingestion de l'export Charlemagne la reprend d'elle-même — souvent plus sûr qu'une correction à la main.",
      },
      {
        id: "google",
        titre: "Changer son unité et ses groupes Google",
        pourquoi:
          "Il reçoit sinon les messages de son ancienne classe, et pas ceux de la nouvelle.",
        page: "personnes",
        piege:
          "Depuis sa fiche, « Déplacer dans Google » fait l'unité, l'entrée dans le nouveau groupe et la sortie de l'ancien en un seul aperçu.",
      },
      {
        id: "koxo",
        titre: "Reprendre son groupe secondaire KoXo",
        pourquoi: "C'est lui qui décide de ses partages réseau.",
        page: "exports",
      },
      {
        id: "ts1000",
        titre: "Le déplacer dans TS1000",
        pourquoi:
          "Les horaires d'accès dépendent du groupe : une seconde dans un groupe de terminale n'ouvre pas les mêmes portes.",
        page: "ts1000",
        piege:
          "Jamais depuis un groupe d'accès. Un interne, un AVS, un agent y est rangé pour ouvrir des portes — l'en sortir les lui ferme.",
      },
      {
        id: "carte",
        titre: "Refaire sa carte si la classe y figure",
        pourquoi: "Une carte qui annonce l'ancienne classe se fait refuser à l'œil.",
        page: "exports",
      },
      {
        id: "pmb_sodexo",
        titre: "Refaire PMB et Sodexo",
        pourquoi:
          "Le régime de restauration et les droits d'emprunt suivent la classe.",
        page: "sodexo",
        ailleurs: "PMB · Sodexo",
      },
    ],
  },
];

export function mouvementParId(id) {
  return MOUVEMENTS.find((m) => m.id === id) ?? MOUVEMENTS[0];
}
