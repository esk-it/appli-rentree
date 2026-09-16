/**
 * Ce qu'un écran retient quand on le quitte.
 *
 * ## Le défaut
 *
 * Chaque écran est monté à l'arrivée et détruit au départ — le bloc
 * `{#key page}` d'`App.svelte` le reconstruit à chaque navigation, ce qui
 * relance l'animation d'apparition. Effet de bord : tout ce que l'écran
 * tenait disparaît avec lui.
 *
 * Sur un formulaire, c'est sans conséquence. Sur la Concordance, c'est un
 * export Charlemagne à recharger et un croisement de quatre sources à
 * relancer parce qu'on est allé vérifier un nom dans le référentiel. Sur
 * la Conformité, plusieurs centaines d'appels à Google. On finit par ne
 * plus oser quitter l'écran, ce qui est l'inverse du but.
 *
 * ## Pourquoi pas simplement garder les écrans montés
 *
 * Les masquer plutôt que les détruire retiendrait tout, sans rien écrire.
 * Mais un écran masqué continue de vivre : le suivi d'un job Google
 * continuerait d'interroger le backend toutes les sept centièmes de
 * seconde derrière un écran que personne ne regarde, et une minuterie
 * oubliée est une fuite qu'on ne voit jamais.
 *
 * On garde donc la destruction, et l'écran **déclare** ce qui mérite de
 * lui survivre. C'est un choix par valeur, pas une rétention par défaut :
 * on retient un résultat de scan, jamais un « en cours de chargement ».
 *
 * ## Portée
 *
 * La mémoire vit dans le module, donc dans l'onglet : elle survit à la
 * navigation, pas à un redémarrage. C'est voulu — ces valeurs sont des
 * constats datés, et les relire au lancement ferait croire à un état
 * frais. Un écran qui affiche du mémorisé doit dire de quand il date.
 *
 * ## Usage
 *
 * Sur un écran existant, `lire` et `ecrire` se posent sans toucher au reste
 * du fichier — la variable garde son nom et ses cent usages :
 *
 * ```js
 * let rapport = $state(lire("concordance.rapport", null));
 * $effect(() => ecrire("concordance.rapport", rapport));
 * ```
 *
 * Sur du neuf, `memoire` évite l'effet :
 *
 * ```js
 * const rapport = memoire("concordance.rapport", null);
 * rapport.valeur = await api.croiser(...);
 * ```
 */

/** @type {Map<string, unknown>} */
const registre = new Map();

/**
 * La valeur retenue pour cette clé, ou `defaut` au premier passage.
 *
 * @template T
 * @param {string} cle
 * @param {T} defaut
 * @returns {T}
 */
export function lire(cle, defaut) {
  return registre.has(cle) ? /** @type {T} */ (registre.get(cle)) : defaut;
}

/**
 * Retient une valeur pour le prochain passage sur l'écran.
 *
 * @param {string} cle
 * @param {unknown} valeur
 */
export function ecrire(cle, valeur) {
  registre.set(cle, valeur);
}

/**
 * Un état réactif qui survit à la navigation.
 *
 * @template T
 * @param {string} cle  identifiant stable, préfixé par l'écran
 * @param {T} initial   valeur au tout premier passage
 * @returns {{valeur: T}}
 */
export function memoire(cle, initial) {
  let valeur = $state(registre.has(cle) ? /** @type {T} */ (registre.get(cle)) : initial);
  return {
    get valeur() {
      return valeur;
    },
    set valeur(v) {
      valeur = v;
      registre.set(cle, v);
    },
  };
}

/**
 * Oublie ce qui a été mémorisé.
 *
 * Sans argument, tout ; avec un préfixe, ce qui en relève. Sert quand une
 * opération rend les constats caducs — une ingestion réelle périme tout
 * ce qui décrivait le référentiel d'avant, et le montrer ensuite serait
 * pire que de ne rien montrer.
 *
 * @param {string} [prefixe]
 */
export function oublier(prefixe) {
  if (prefixe === undefined) {
    registre.clear();
    return;
  }
  for (const cle of [...registre.keys()]) {
    if (cle === prefixe || cle.startsWith(`${prefixe}.`)) registre.delete(cle);
  }
}

/** Ce que la mémoire retient, pour un écran de diagnostic. */
export function clesMemorisees() {
  return [...registre.keys()].sort();
}
