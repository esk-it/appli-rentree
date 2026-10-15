<script>
  import Repere from "./Repere.svelte";

  /**
   * Un geste qui traverse plusieurs fenêtres : une planche par fenêtre,
   * chacune nommée par les repères qu'elle porte — « ③ Étape 1/8 » — pour
   * qu'on passe de la consigne à la bonne image sans chercher.
   *
   * @typedef {Object} Planche
   * @property {string} id
   * @property {string} titre
   * @property {number[]} reperes
   *
   * @typedef {Object} Props
   * @property {Planche[]} planches
   * @property {string} actuelle
   * @property {(id: string) => void} onChoisir
   * @property {import('svelte').Snippet} children
   */
  /** @type {Props} */
  let { planches, actuelle, onChoisir, children } = $props();
</script>

<div class="flex flex-col gap-3">
  <div role="tablist" aria-label="Les fenêtres du geste" class="flex flex-wrap gap-1.5">
    {#each planches as p (p.id)}
      <button
        type="button"
        role="tab"
        aria-selected={p.id === actuelle}
        class="inline-flex items-center gap-1.5 rounded-full border px-3 py-1 text-xs font-semibold transition-colors
          {p.id === actuelle
          ? 'border-stone-900 bg-stone-900 text-white dark:border-stone-100 dark:bg-stone-100 dark:text-stone-900'
          : 'border-stone-300 text-stone-600 hover:border-stone-400 dark:border-stone-700 dark:text-stone-300'}"
        onclick={() => onChoisir(p.id)}
      >
        {#each p.reperes as n (n)}<Repere {n} petit />{/each}
        {p.titre}
      </button>
    {/each}
  </div>
  <div class="overflow-x-auto pb-2">
    <div class="max-w-3xl min-w-[700px]">{@render children()}</div>
  </div>
</div>
