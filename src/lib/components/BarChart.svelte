<script>
  /**
   * Histogramme horizontal, en CSS pur — aucune bibliothèque de graphiques
   * pour une représentation aussi simple.
   *
   * Les barres poussent depuis zéro à l'affichage, avec un léger décalage
   * entre elles : le regard suit la construction et repère les écarts.
   *
   * @typedef {Object} Props
   * @property {Array<{cle: string, valeur: number}>} donnees
   * @property {string} [couleur]        - classe Tailwind de la barre
   * @property {boolean} [afficherPart]  - ajoute le pourcentage du total
   * @property {number} [maxLignes]      - au-delà, regroupe le reste
   */
  /** @type {Props} */
  let {
    donnees = [],
    couleur = "bg-emerald-500",
    afficherPart = false,
    maxLignes = 0,
  } = $props();

  let total = $derived(donnees.reduce((s, d) => s + d.valeur, 0));
  let max = $derived(Math.max(0, ...donnees.map((d) => d.valeur)));

  /**
   * Au-delà de `maxLignes`, les valeurs restantes sont agrégées en une
   * ligne « autres » — une liste de cinquante barres minuscules
   * n'apprend rien de plus qu'un total.
   */
  let lignes = $derived.by(() => {
    if (!maxLignes || donnees.length <= maxLignes) return donnees;
    const tetes = donnees.slice(0, maxLignes);
    const reste = donnees.slice(maxLignes).reduce((s, d) => s + d.valeur, 0);
    return reste > 0 ? [...tetes, { cle: "autres", valeur: reste }] : tetes;
  });
</script>

<div class="space-y-1.5">
  {#each lignes as d, i (d.cle)}
    {@const pct = max === 0 ? 0 : (d.valeur / max) * 100}
    {@const part = total === 0 ? 0 : (d.valeur / total) * 100}
    <div
      class="grid items-center gap-2 text-xs {afficherPart
        ? 'grid-cols-[6rem_1fr_3rem_3rem]'
        : 'grid-cols-[6rem_1fr_3rem]'}"
    >
      <span
        class="truncate font-medium text-stone-700 dark:text-stone-300"
        title={d.cle}
      >
        {d.cle}
      </span>
      <div class="h-3 overflow-hidden rounded-full bg-stone-100 dark:bg-stone-700">
        <div
          class="h-full rounded-full {couleur} origin-left"
          style="width: {pct}%; animation: pousser 500ms cubic-bezier(0.22, 1, 0.36, 1) both; animation-delay: {i * 35}ms;"
        ></div>
      </div>
      <span class="text-right tabular-nums text-stone-600 dark:text-stone-400">
        {d.valeur.toLocaleString("fr-FR")}
      </span>
      {#if afficherPart}
        <span class="text-right tabular-nums text-stone-400 dark:text-stone-500">
          {part.toFixed(0)} %
        </span>
      {/if}
    </div>
  {/each}
</div>

<style>
  /* Croissance depuis la gauche — `scaleX` plutôt que `width` pour rester
     sur le compositeur et éviter de relayouter à chaque image. */
  @keyframes pousser {
    from {
      transform: scaleX(0);
    }
    to {
      transform: scaleX(1);
    }
  }
</style>
