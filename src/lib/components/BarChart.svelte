<script>
  /**
   * Histogramme horizontal CSS pur (pas de dépendance lib).
   * Optimisé pour des décomptes (clé/valeur).
   *
   * @typedef {Object} Props
   * @property {Array<{cle:string, valeur:number}>} donnees
   * @property {string} [couleur]    Classe Tailwind du bar (ex: "bg-emerald-500")
   * @property {string} [couleurFond]  Classe Tailwind du fond de track
   * @property {boolean} [valeursDansLabel]  Affiche la valeur dans le label
   */
  /** @type {Props} */
  let {
    donnees,
    couleur = "bg-emerald-500",
    couleurFond = "bg-stone-100",
    valeursDansLabel = true,
  } = $props();

  let max = $derived(Math.max(0, ...donnees.map((d) => d.valeur)));
</script>

<div class="space-y-1.5">
  {#each donnees as d (d.cle)}
    {@const pct = max === 0 ? 0 : (d.valeur / max) * 100}
    <div class="grid grid-cols-[6rem_1fr_3rem] items-center gap-2 text-xs">
      <span class="truncate font-medium text-stone-700" title={d.cle}>{d.cle}</span>
      <div class="h-3 overflow-hidden rounded-full {couleurFond}">
        <div
          class="h-full rounded-full {couleur} transition-all"
          style="width: {pct}%"
        ></div>
      </div>
      <span class="text-right tabular-nums text-stone-600">
        {valeursDansLabel ? d.valeur.toLocaleString("fr-FR") : ""}
      </span>
    </div>
  {/each}
</div>
