/**
 * Système de notifications toast léger, en runes Svelte 5.
 *
 * Usage :
 *   import { notify } from "$lib/toasts.js";
 *   notify.succes("Élève importé");
 *   notify.erreur("Échec de l'opération", { duree: 5000 });
 *   notify.info("Astuce : Ctrl+K pour la recherche");
 */
import { writable } from "svelte/store";

/** @typedef {{ id: number, type: "succes"|"erreur"|"info"|"avertissement", message: string, duree: number }} Toast */

/** @type {import("svelte/store").Writable<Toast[]>} */
export const toasts = writable([]);

let prochainId = 0;

function pousser(type, message, options = {}) {
  const id = ++prochainId;
  const duree = options.duree ?? 3500;
  toasts.update((arr) => [...arr, { id, type, message, duree }]);
  if (duree > 0) {
    setTimeout(() => {
      toasts.update((arr) => arr.filter((t) => t.id !== id));
    }, duree);
  }
  return id;
}

export const notify = {
  succes(message, options) {
    return pousser("succes", message, options);
  },
  erreur(message, options) {
    return pousser("erreur", message, { duree: 5000, ...options });
  },
  info(message, options) {
    return pousser("info", message, options);
  },
  avertissement(message, options) {
    return pousser("avertissement", message, options);
  },
  retirer(id) {
    toasts.update((arr) => arr.filter((t) => t.id !== id));
  },
};
