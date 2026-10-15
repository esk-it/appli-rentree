<script>
  /**
   * Les six chapitres en une bande : où l'on en est, d'un coup d'œil.
   * Chaque segment se remplit des étapes validées de son chapitre, dans la
   * couleur du chapitre — celle qu'on retrouve dans le calendrier et les
   * bilans.
   *
   * @typedef {Object} Props
   * @property {any[]} chapitres
   * @property {any[]} etapes
   * @property {string|null} [actif]
   * @property {boolean} [libelles]
   */
  /** @type {Props} */
  let { chapitres, etapes, actif = null, libelles = true } = $props();

  const part = (id) => {
    const siennes = etapes.filter((e) => e.chapitre === id);
    const faites = siennes.filter((e) => e.statut === "validee" || e.statut === "reportee").length;
    return siennes.length ? Math.round((100 * faites) / siennes.length) : 0;
  };
</script>

<nav aria-label="Chapitres de la rentrée" class="grid grid-cols-6 gap-1.5">
  {#each chapitres as c, i (c.id)}
    {@const p = part(c.id)}
    <div class="min-w-0">
      <div class="h-1.5 overflow-hidden rounded-full bg-stone-200 dark:bg-stone-800">
        <div class="h-full rounded-full" style="width: {p}%; background: {c.couleur};"></div>
      </div>
      {#if libelles}
        <p
          class="mt-1.5 truncate text-xs {c.id === actif ? 'font-bold' : p === 100 ? 'font-semibold' : 'text-stone-500 dark:text-stone-400'}"
          style={c.id === actif || p === 100 ? `color: color-mix(in srgb, ${c.couleur} 75%, var(--color-stone-900));` : ""}
        >
          {i + 1} · {c.titre}
        </p>
      {/if}
    </div>
  {/each}
</nav>
