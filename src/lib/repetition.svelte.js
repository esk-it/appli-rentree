/**
 * La répétition en cours, ou non — su de tous les écrans.
 *
 * Pendant une répétition, le programme entier travaille sur une copie de
 * la base et Google n'est que lu (`backend/services/repetition.py`). Le
 * bandeau d'`App.svelte` le rappelle en permanence ; l'assistant de
 * rentrée adapte ses consignes.
 *
 * Entrer ou sortir recharge la page : chaque écran relit alors la base
 * sur laquelle il travaille, sans rien garder de l'autre.
 */
import { repetitionApi } from "$lib/api.js";

export const repetition = $state({
  active: false,
  copie_existe: false,
  /** @type {string|null} */
  copiee_le: null,
});

export async function relireRepetition() {
  try {
    Object.assign(repetition, await repetitionApi.etat());
  } catch {
    // Backend pas encore prêt : on reste sur « pas de répétition », qui est
    // aussi ce que le backend fait au démarrage.
  }
}

const PAGE_APRES = "appli.page-apres-rechargement";

/** Commence (ou reprend) la répétition, puis recharge tout — on revient sur la rentrée. */
export async function entrerEnRepetition({ neuve = false } = {}) {
  await repetitionApi.commencer({ neuve });
  try {
    sessionStorage.setItem(PAGE_APRES, "rentree");
  } catch {
    // Stockage indisponible : on reviendra sur l'accueil, sans dommage.
  }
  window.location.reload();
}

/** L'écran à rouvrir après un rechargement voulu, une seule fois. */
export function pageApresRechargement() {
  try {
    const p = sessionStorage.getItem(PAGE_APRES);
    sessionStorage.removeItem(PAGE_APRES);
    return p;
  } catch {
    return null;
  }
}

/** Revient à la vraie base, puis recharge tout. */
export async function quitterLaRepetition() {
  await repetitionApi.quitter();
  window.location.reload();
}

/** « 2026-10-16T10:42 » → « 16/10 à 10 h 42 ». */
export function dateCopie(iso) {
  if (!iso) return "";
  return `${iso.slice(8, 10)}/${iso.slice(5, 7)} à ${iso.slice(11, 13)} h ${iso.slice(14, 16)}`;
}
