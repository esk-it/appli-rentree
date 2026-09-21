/**
 * L'année sur laquelle on travaille.
 *
 * ## Pourquoi pas une base par année
 *
 * La question s'est posée : puisque le programme sert chaque été, pourquoi
 * ne pas repartir d'une base neuve à chaque rentrée ? Parce que c'est
 * exactement ce que faisait le classeur qu'il remplace, et c'est le défaut
 * qu'il existe pour corriger.
 *
 * Une base par année, c'est un référentiel reconstruit de zéro douze mois
 * sur douze, et avec lui :
 *
 * - **l'identité se perd.** La clé pivot `(type, id Charlemagne)` ne vaut
 *   que si elle traverse les années. Séparées, on retombe sur le
 *   rapprochement par nom — celui qui confond deux homonymes et détruit un
 *   compte à chaque changement de nom de famille.
 * - **le login n'est plus jamais recyclé… sauf qu'il l'est.** Un login
 *   figé à l'attribution et jamais réutilisé suppose de connaître tous
 *   ceux qui ont existé. Dans une base de l'année, ils n'existent plus.
 * - **les sortants disparaissent de la vue.** Un compte en quarantaine
 *   dix-huit mois vit par définition à cheval sur deux années.
 * - **on ne peut plus rien comparer.** La montée SU → NDK, le
 *   différentiel JPM, « qui était là l'an dernier et pas cette année » :
 *   tout cela lit deux années à la fois.
 *
 * Ce qu'on veut vraiment quand on demande des bases séparées, c'est **ne
 * pas mélanger** — ne pas voir la promotion précédente au milieu de
 * l'actuelle. Ça, le référentiel le fait déjà : chaque année a ses
 * `Snapshot`, et l'identité, elle, est commune. Il manquait seulement de
 * dire **laquelle on regarde**, en un endroit visible, valable partout.
 *
 * C'est ce que tient ce module.
 *
 * ## Ce qu'il retient
 *
 * L'année choisie survit à la fermeture du programme : on travaille sur la
 * même pendant des semaines, et la redemander à chaque lancement serait
 * une question dont la réponse ne change jamais.
 *
 * Le repli, quand rien n'est mémorisé, est **l'année au libellé le plus
 * haut** — `2026-2027` avant `2025-2026`. Surtout pas `est_active`, qui
 * est vrai sur plusieurs années à la fois et désigne donc n'importe
 * laquelle.
 */
import { annees as anneesApi } from "$lib/api.js";

const CLE_MEMOIRE = "appli-rentree.annee-de-travail";

/**
 * @typedef {Object} Annee
 * @property {number} id
 * @property {string} libelle
 * @property {boolean} est_active
 * @property {number} nb_snapshots
 * @property {number} nb_personnes_distinctes
 */

export const annee = $state({
  /** @type {Annee[]} */
  liste: [],
  /** @type {number|null} */
  id: null,
  chargee: false,
  erreur: "",
});

/** L'année choisie, en entier. */
export function courante() {
  return annee.liste.find((a) => a.id === annee.id) ?? null;
}

/** Le libellé de l'année de travail, ou une chaîne vide. */
export function libelleCourant() {
  return courante()?.libelle ?? "";
}

function memoriser(id) {
  try {
    localStorage.setItem(CLE_MEMOIRE, String(id));
  } catch {
    // Navigation privée, stockage refusé : on perd le choix au prochain
    // lancement, et rien d'autre.
  }
}

function memorise() {
  try {
    const brut = localStorage.getItem(CLE_MEMOIRE);
    return brut ? Number(brut) : null;
  } catch {
    return null;
  }
}

/**
 * Charge la liste des années et arrête celle sur laquelle on travaille.
 *
 * Appelée une fois au démarrage. Rappelée après une ingestion, quand une
 * année vient d'apparaître.
 */
export async function charger() {
  try {
    const liste = await anneesApi.lister();
    annee.liste = liste ?? [];
    annee.erreur = "";

    const souhaitee = memorise();
    const existe = annee.liste.some((a) => a.id === souhaitee);
    if (existe) {
      annee.id = souhaitee;
    } else {
      // Le libellé décroissant, jamais `est_active` — voir l'en-tête.
      const plusRecente = [...annee.liste].sort((a, b) =>
        b.libelle.localeCompare(a.libelle),
      )[0];
      annee.id = plusRecente?.id ?? null;
      if (annee.id) memoriser(annee.id);
    }
  } catch (e) {
    annee.erreur = String(e).replace(/^Error:\s*/, "");
  } finally {
    annee.chargee = true;
  }
}

/** Change l'année de travail, et s'en souvient. */
export function choisir(id) {
  if (!annee.liste.some((a) => a.id === id)) return;
  annee.id = id;
  memoriser(id);
}
