<script>
  /**
   * Tableau interactif avec recherche, tri, et filtres rapides par colonne.
   * Pour 1700 lignes max, on reste léger sans pagination.
   *
   * @typedef {Object} Props
   * @property {string[]} colonnes
   * @property {Record<string, any>[]} lignes
   * @property {Record<string, string>} [libelles] - mapping colonne → libellé affiché
   */
  /** @type {Props} */
  let { colonnes, lignes, libelles = {} } = $props();

  let recherche = $state("");
  let triCol = $state(null);
  let triAsc = $state(true);

  const colonnesAffichees = $derived(
    colonnes.filter((c) => c !== "photo_chemin"),
  );

  const lignesFiltreesTriees = $derived.by(() => {
    let r = lignes;
    const q = recherche.trim().toLowerCase();
    if (q) {
      r = r.filter((l) =>
        colonnesAffichees.some((c) =>
          String(l[c] ?? "")
            .toLowerCase()
            .includes(q),
        ),
      );
    }
    if (triCol) {
      r = [...r].sort((a, b) => {
        const va = a[triCol];
        const vb = b[triCol];
        if (va == null && vb == null) return 0;
        if (va == null) return 1;
        if (vb == null) return -1;
        const cmp = String(va).localeCompare(String(vb), "fr", {
          numeric: true,
        });
        return triAsc ? cmp : -cmp;
      });
    }
    return r;
  });

  function trier(col) {
    if (triCol === col) {
      triAsc = !triAsc;
    } else {
      triCol = col;
      triAsc = true;
    }
  }

  function libelle(col) {
    return libelles[col] ?? col;
  }

  function formatCell(v) {
    if (v === null || v === undefined) return "";
    if (typeof v === "boolean") return v ? "Oui" : "";
    return String(v);
  }
</script>

<div class="card overflow-hidden">
  <div class="flex items-center justify-between gap-3 border-b border-stone-200 px-4 py-3">
    <input
      type="search"
      placeholder="Rechercher (nom, prénom, classe...)"
      bind:value={recherche}
      class="w-72 rounded-lg border border-stone-300 px-3 py-1.5 text-sm placeholder:text-stone-400 focus:border-emerald-600 focus:outline-none focus:ring-1 focus:ring-emerald-600"
    />
    <span class="text-sm text-stone-500 tabular-nums">
      {lignesFiltreesTriees.length.toLocaleString("fr-FR")} ligne(s){lignes.length !== lignesFiltreesTriees.length ? ` sur ${lignes.length.toLocaleString("fr-FR")}` : ""}
    </span>
  </div>

  <div class="max-h-[600px] overflow-auto">
    <table class="w-full border-collapse text-sm">
      <thead class="sticky top-0 z-10 bg-stone-100 text-stone-700">
        <tr>
          {#each colonnesAffichees as col (col)}
            <th
              class="cursor-pointer select-none whitespace-nowrap border-b border-stone-200 px-3 py-2 text-left font-semibold hover:bg-stone-200"
              onclick={() => trier(col)}
            >
              <span class="inline-flex items-center gap-1">
                {libelle(col)}
                {#if triCol === col}
                  <span class="text-xs">{triAsc ? "▲" : "▼"}</span>
                {/if}
              </span>
            </th>
          {/each}
        </tr>
      </thead>
      <tbody>
        {#each lignesFiltreesTriees as ligne, i (i)}
          <tr class="border-b border-stone-100 even:bg-stone-50/50 hover:bg-emerald-50/40">
            {#each colonnesAffichees as col (col)}
              <td class="whitespace-nowrap px-3 py-1.5 text-stone-700">
                {#if col === "nouvel_eleve" && ligne[col]}
                  <span class="badge-nouveau">Nouveau</span>
                {:else}
                  {formatCell(ligne[col])}
                {/if}
              </td>
            {/each}
          </tr>
        {/each}
      </tbody>
    </table>
  </div>
</div>
