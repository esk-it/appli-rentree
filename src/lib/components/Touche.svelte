<script>
  /**
   * Une touche du clavier, dessinée plutôt que nommée.
   *
   * La procédure d'origine montrait des images de touches — CTRL + A,
   * SUPPR — et c'était juste : « tout sélectionner puis supprimer » se lit,
   * `Ctrl` `A` se reconnaît. On la redessine en CSS plutôt que d'embarquer
   * les captures : une image de touche grise reste grise en thème sombre,
   * et pixellise dès qu'on agrandit.
   *
   * @typedef {Object} Props
   * @property {string} texte
   */
  /** @type {Props} */
  let { texte } = $props();
</script>

<kbd
  class="inline-flex min-w-7 items-center justify-center rounded-md border border-b-2 border-stone-300 border-b-stone-400
         bg-linear-to-b from-white to-stone-100 px-1.5 py-0.5 text-[11px] font-semibold text-stone-700 shadow-xs
         dark:border-stone-600 dark:border-b-stone-900 dark:from-stone-700 dark:to-stone-800 dark:text-stone-200"
>
  {texte}
</kbd>
