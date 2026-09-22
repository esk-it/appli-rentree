/**
 * La couleur de chaque domaine.
 *
 * ## Pourquoi une couleur par famille plutôt qu'un accent unique
 *
 * Un seul accent posé partout ne dit rien d'autre que « c'est cliquable ».
 * Ici chaque domaine porte sa teinte, d'un bout à l'autre : la pastille de
 * sa section sur l'accueil, le trait de son icône, le voile derrière. On
 * reconnaît un écran à sa couleur avant d'avoir lu son titre — et surtout,
 * on retrouve du premier coup d'œil celui qu'on cherche dans une grille de
 * quinze.
 *
 * La contrainte est que les teintes partagent une même saturation et une
 * même clarté : huit couleurs prises au hasard font un sapin de Noël, huit
 * couleurs d'une même famille font un jeu.
 *
 * ## Le voile
 *
 * Chaque icône est un trait plein sur une forme remplie de la version pâle
 * de sa teinte. C'est ce qui donne l'air « dessiné » plutôt que
 * « pictogramme d'interface » — et ça se calcule, plutôt que de maintenir
 * seize constantes qui finiraient par diverger.
 */

/** @typedef {"rentree"|"annee"|"materiel"|"google"|"koxo"|"photos"|"repas"|"fichiers"} Famille */

/** Teinte pleine de chaque famille — le trait, la pastille, le texte. */
export const TEINTES = {
  rentree: "#e4502f",
  annee: "#5f4de8",
  materiel: "#0c8fa1",
  google: "#2f6ce0",
  koxo: "#16995f",
  photos: "#d93a8c",
  repas: "#c77f00",
  fichiers: "#58647e",
};

/**
 * À quelle famille appartient chaque écran.
 *
 * Un écran absent d'ici retombe sur la famille de sa partie : c'est le cas
 * courant, et il vaut mieux un défaut juste qu'une table à tenir à jour.
 */
export const FAMILLE_PAR_ECRAN = {
  // Ce qui touche aux comptes Google porte le bleu, où qu'il soit rangé.
  conformite: "google",
  bascule: "google",
  sortants: "google",
  vidange: "google",
  // KoXo a son vert.
  controle_koxo: "koxo",
  // Les écrans qui ont leur propre sujet gardent leur couleur.
  photos: "photos",
  sodexo: "repas",
  exports: "fichiers",
  cartes: "photos",
  journal: "fichiers",
  ts1000: "materiel",
  concordance: "koxo",
  coherence: "koxo",
};

/**
 * La teinte d'un écran : la sienne si elle est déclarée, sinon celle de sa
 * partie.
 *
 * @param {string} ecran
 * @param {string} partie
 */
export function teinte(ecran, partie = "annee") {
  const famille = FAMILLE_PAR_ECRAN[ecran] ?? partie;
  return TEINTES[famille] ?? TEINTES.annee;
}

/**
 * Le style à poser sur une plaque d'icône.
 *
 * `--teinte` est lue par `.plaque-icone` dans la feuille de style : la
 * couleur voyage en variable CSS plutôt qu'en classe, sinon il faudrait
 * huit classes figées que Tailwind ne saurait pas produire à la volée.
 *
 * @param {string} couleur
 */
export function styleTeinte(couleur) {
  return `--teinte: ${couleur};`;
}
