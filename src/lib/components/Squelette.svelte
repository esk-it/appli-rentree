<script>
  /**
   * Squelette de chargement.
   *
   * Préféré à un « Chargement… » : la forme du contenu à venir apparaît
   * immédiatement, ce qui évite le saut de mise en page et donne une
   * impression de rapidité même à durée identique.
   *
   * @typedef {Object} Props
   * @property {"texte"|"titre"|"carte"|"ligne-tableau"} [variante]
   * @property {number} [nb]      - nombre de répétitions
   * @property {number} [colonnes] - pour la variante ligne-tableau
   */
  /** @type {Props} */
  let { variante = "texte", nb = 3, colonnes = 5 } = $props();

  let elements = $derived(Array.from({ length: nb }, (_, i) => i));
  let cellules = $derived(Array.from({ length: colonnes }, (_, i) => i));

  // Largeurs variables : un squelette à barres égales fait « faux ».
  const LARGEURS = ["w-full", "w-11/12", "w-4/5", "w-10/12", "w-3/4"];
</script>

{#if variante === "carte"}
  <div class="grid grid-cols-2 gap-3 md:grid-cols-4">
    {#each elements as i (i)}
      <div class="card p-4">
        <div class="squelette h-3 w-2/3"></div>
        <div class="squelette mt-3 h-7 w-1/2"></div>
      </div>
    {/each}
  </div>
{:else if variante === "ligne-tableau"}
  <div class="overflow-hidden rounded-lg border border-stone-200 dark:border-stone-700">
    {#each elements as i (i)}
      <div
        class="flex items-center gap-4 border-b border-stone-100 px-3 py-2.5 last:border-0 dark:border-stone-800"
      >
        {#each cellules as c (c)}
          <div class="squelette h-3 flex-1 {LARGEURS[(i + c) % LARGEURS.length]}"></div>
        {/each}
      </div>
    {/each}
  </div>
{:else if variante === "titre"}
  <div class="squelette h-6 w-1/3"></div>
{:else}
  <div class="space-y-2">
    {#each elements as i (i)}
      <div class="squelette h-3 {LARGEURS[i % LARGEURS.length]}"></div>
    {/each}
  </div>
{/if}
