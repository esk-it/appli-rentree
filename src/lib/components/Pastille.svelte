<script>
  /**
   * La pastille d'état, en bout de ligne.
   *
   * Cinq états reviennent d'un écran à l'autre des maquettes : ce qui est
   * **prêt**, ce qui **diverge**, ce qui **attend**, ce qui **fait
   * référence**, et ce qui **n'a pas été regardé**. Le dernier compte
   * autant que les autres : un contrôle qui n'a pas tourné n'est pas un
   * contrôle réussi, et les confondre fait conclure au calme là où on n'a
   * rien vérifié.
   *
   * Voile pâle, texte foncé, jamais de bordure — et jamais de couleur
   * seule : chaque pastille porte un mot.
   *
   * @typedef {Object} Props
   * @property {"pret"|"ecart"|"attente"|"reference"|"inconnu"} [etat]
   * @property {string} texte
   */
  /** @type {Props} */
  let { etat = "inconnu", texte } = $props();

  const STYLES = {
    // Vert, et non l'accent : « prêt » et « c'est l'année en cours » ne
    // sont pas le même message, et l'échelle `emerald` est violette ici.
    pret: "bg-vert-100 text-vert-700 dark:bg-vert-500/15 dark:text-vert-300",
    ecart: "bg-red-100 text-red-700 dark:bg-red-400/15 dark:text-red-300",
    attente: "bg-amber-50 text-amber-800 dark:bg-amber-400/15 dark:text-amber-300",
    reference: "bg-sky-100 text-sky-700 dark:bg-sky-400/15 dark:text-sky-300",
    inconnu: "bg-stone-100 text-stone-600 dark:bg-stone-800 dark:text-stone-300",
  };
</script>

<span
  class="inline-flex items-center rounded-full px-2.5 py-0.5 text-xs font-bold whitespace-nowrap {STYLES[
    etat
  ] ?? STYLES.inconnu}"
>
  {texte}
</span>
