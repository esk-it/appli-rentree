<script>
  import ChevronRight from "@lucide/svelte/icons/chevron-right";
  import { ecran } from "$lib/ecran.svelte.js";

  /**
   * D'où l'on vient.
   *
   * Il ne fait pas double emploi avec la barre d'onglets : la barre dit
   * *ce qu'il y a à côté*, le fil dit *d'où l'on vient* — et il ramène à
   * l'accueil, qui n'est dans aucune barre.
   *
   * Les maillons viennent de la navigation, déposés dans un module :
   * aucun écran n'a à déclarer sa place. `chemin` ajoute ce que la
   * navigation ne peut pas savoir — le nom de la personne ouverte, par
   * exemple, qui change à chaque fiche.
   *
   * @typedef {Object} Props
   * @property {string[]} [chemin] - maillons ajoutés après l'écran
   */
  /** @type {Props} */
  let { chemin = [] } = $props();

  let maillons = $derived(
    [ecran.partieLabel, ecran.label, ...chemin].filter(Boolean),
  );
</script>

<nav class="flex flex-wrap items-center gap-1 text-sm" aria-label="Fil d'Ariane">
  <button
    type="button"
    class="text-stone-500 transition-colors hover:text-stone-900 dark:text-stone-400 dark:hover:text-stone-100"
    onclick={() => ecran.aller("accueil")}
  >
    Accueil
  </button>
  {#each maillons as m, i (m + i)}
    <ChevronRight class="h-3.5 w-3.5 shrink-0 text-stone-400" />
    <span
      class={i === maillons.length - 1
        ? "font-semibold text-stone-900 dark:text-stone-100"
        : "text-stone-500 dark:text-stone-400"}
    >
      {m}
    </span>
  {/each}
</nav>
