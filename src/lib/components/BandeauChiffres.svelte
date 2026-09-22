<script>
  /**
   * Le bandeau de chiffres en tête d'écran.
   *
   * Deux à quatre constats, séparés par un filet vertical, sous une barre
   * qui les sépare du reste. C'est le motif des maquettes du tour 5, et il
   * remplace les tuiles encadrées : quatre rectangles bordés se disputent
   * l'attention, quatre colonnes séparées d'un trait se lisent d'un coup.
   *
   * Un chiffre porte sa couleur seulement s'il **veut dire quelque chose** —
   * un manque en rouge, un acquis en vert. Le reste est à l'encre : si tous
   * les nombres sont colorés, aucun ne ressort.
   *
   * @typedef {Object} Chiffre
   * @property {string} libelle     - l'étiquette, en petite capitale
   * @property {string|number} valeur
   * @property {string} [detail]    - la ligne sous le nombre
   * @property {string} [teinte]    - couleur du nombre ; absente = encre
   * @property {{texte: string, valeur: string|number, alerte?: boolean}[]} [lignes]
   *   - à la place d'un grand nombre : une petite liste (« NDK 1566 »)
   *
   * @typedef {Object} Props
   * @property {Chiffre[]} chiffres
   */
  /** @type {Props} */
  let { chiffres = [] } = $props();
</script>

<div
  class="grid gap-7 border-b border-stone-200 pb-5 dark:border-stone-800"
  style="grid-template-columns: repeat({Math.max(1, chiffres.length)}, minmax(0, 1fr));"
>
  {#each chiffres as c, i (c.libelle)}
    <div class={i > 0 ? "border-l border-stone-200 pl-7 dark:border-stone-800" : ""}>
      <p class="libelle-champ">{c.libelle}</p>

      {#if c.lignes?.length}
        <!-- Une répartition se lit en colonnes, pas en un seul nombre. -->
        <div class="mt-2 grid w-max grid-cols-[auto_auto] gap-x-5 gap-y-0.5 text-sm">
          {#each c.lignes as l (l.texte)}
            <span class={l.alerte ? "text-red-700 dark:text-red-400" : ""}>{l.texte}</span>
            <b class={"tabular-nums " + (l.alerte ? "text-red-700 dark:text-red-400" : "")}>
              {l.valeur}
            </b>
          {/each}
        </div>
      {:else}
        <p
          class="titre-affiche mt-1.5 text-4xl leading-none tabular-nums"
          style={c.teinte ? `color: ${c.teinte};` : ""}
        >
          {c.valeur}
        </p>
      {/if}

      {#if c.detail}
        <p class="mt-1.5 text-[13px] text-stone-600 dark:text-stone-400">{c.detail}</p>
      {/if}
    </div>
  {/each}
</div>
