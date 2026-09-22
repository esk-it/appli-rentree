/**
 * Quel écran est ouvert, et de quelle couleur il est.
 *
 * ## Pourquoi un module plutôt qu'une propriété
 *
 * Chaque écran porte la teinte de sa famille : c'est ce qui fait qu'on le
 * reconnaît avant de l'avoir lu. Mais aucun des trente écrans ne sait à
 * quelle famille il appartient, et le leur faire déclarer voudrait dire
 * trente fichiers à modifier — puis un de plus à chaque écran ajouté, avec
 * l'oubli qui va avec.
 *
 * La navigation, elle, le sait. Elle le dépose ici, et l'en-tête de page le
 * lit. Un seul endroit écrit, un seul endroit lit, zéro écran touché.
 *
 * C'est le même procédé que `parcours.embarque` : ce que l'écran n'a pas à
 * savoir, il ne le reçoit pas.
 */
import { teinte } from "$lib/familles.js";

export const ecran = $state({
  /** Identifiant de l'écran ouvert — `photos`, `personnes`… */
  id: "accueil",
  /** Identifiant de la partie qui le contient — `rentree`, `annee`… */
  partie: "annee",
  /** Son libellé — « L'année » — pour le fil d'Ariane. */
  partieLabel: "",
  /** Le libellé de l'écran, tel que la barre l'écrit. */
  label: "",
  /**
   * Comment revenir en arrière.
   *
   * Le fil d'Ariane doit être cliquable, sinon il décore. La navigation
   * vit dans `App.svelte` ; elle se dépose ici avec le reste plutôt que
   * de traverser trente composants en propriété.
   */
  /** @type {(page: string) => void} */
  aller: () => {},
});

/** La couleur de l'écran ouvert. */
export function teinteCourante() {
  return teinte(ecran.id, ecran.partie);
}

/** Déclare l'écran ouvert. Appelé par la navigation, et par elle seule. */
export function declarer(id, partie, { label = "", partieLabel = "", aller } = {}) {
  ecran.id = id;
  ecran.partie = partie ?? "annee";
  ecran.label = label;
  ecran.partieLabel = partieLabel;
  if (aller) ecran.aller = aller;
}
