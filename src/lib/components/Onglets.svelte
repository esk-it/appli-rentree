<script>
  import { teinteCourante } from "$lib/ecran.svelte.js";

  /**
   * Les onglets soulignés, à l'intérieur d'un écran.
   *
   * ## Pourquoi un second composant à côté de `Segments`
   *
   * Ils ne disent pas la même chose. Le sélecteur en pilule est un
   * **filtre** — on restreint une même liste. Les onglets soulignés sont
   * des **vues** : « Manquantes (37) », « Non rattachées (7) », trois
   * contenus différents dont un seul est montré.
   *
   * Les maquettes emploient les deux, et l'usage tranche : quand le
   * compteur fait partie du libellé, c'est une vue.
   *
   * ## Le compte est dans le libellé
   *
   * `Manquantes (37)` et non `Manquantes` avec une pastille : on choisit
   * l'onglet **parce que** le compte est ce qu'on cherche. Le sortir du
   * libellé oblige à le lire deux fois.
   *
   * @typedef {Object} Onglet
   * @property {string} id
   * @property {string} label
   * @property {number} [compte]  - ajouté entre parenthèses au libellé
   *
   * @typedef {Object} Props
   * @property {Onglet[]} onglets
   * @property {string} valeur   - bindable
   * @property {(id: string) => void} [onChange]
   */
  /** @type {Props} */
  let { onglets = [], valeur = $bindable(), onChange } = $props();

  let couleur = $derived(teinteCourante());

  function choisir(id) {
    if (id === valeur) return;
    valeur = id;
    onChange?.(id);
  }
</script>

<!-- Le filet du bas est une ombre intérieure, pas une bordure : l'onglet
     actif le recouvre de son soulignement sans déborder du conteneur. Avec
     une bordure et un `-mb-px`, le contenu dépassait d'un pixel — et
     `overflow-x-auto` faisait apparaître une barre de défilement verticale
     à côté des onglets. -->
<div
  class="flex gap-8 overflow-x-auto text-sm font-semibold shadow-[inset_0_-1px_0_var(--color-stone-200)] dark:shadow-[inset_0_-1px_0_var(--color-stone-800)]"
  role="tablist"
>
  {#each onglets as o (o.id)}
    {@const actif = o.id === valeur}
    <button
      type="button"
      role="tab"
      aria-selected={actif}
      class="shrink-0 border-b-2 py-2.5 whitespace-nowrap transition-colors
             {actif
               ? ''
               : 'border-transparent text-stone-500 hover:text-stone-800 dark:text-stone-400 dark:hover:text-stone-200'}"
      style={actif ? `color: ${couleur}; border-color: ${couleur};` : ""}
      onclick={() => choisir(o.id)}
    >
      {o.label}{#if o.compte !== undefined}&nbsp;({o.compte}){/if}
    </button>
  {/each}
</div>
