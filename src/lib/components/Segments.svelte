<script>
  /**
   * Sélecteur segmenté avec indicateur glissant.
   *
   * Remplace les groupes de boutons filtres/onglets répétés dans presque
   * tous les écrans, chacun avec son propre rendu. Un seul composant :
   * même comportement, même apparence, une seule chose à corriger.
   *
   * L'indicateur est un bloc positionné en absolu qui se déplace vers
   * l'option active. Le glissement rend le changement lisible — on voit
   * d'où l'on vient, pas seulement où l'on est.
   *
   * @typedef {Object} Option
   * @property {string} id
   * @property {string} label
   * @property {number} [badge]   - pastille numérique optionnelle
   * @property {any} [icon]       - composant Lucide
   *
   * @typedef {Object} Props
   * @property {Option[]} options
   * @property {string} valeur          - id de l'option active (bindable)
   * @property {"sm"|"md"} [taille]
   * @property {boolean} [pleineLargeur]
   * @property {(id: string) => void} [onChange]
   */
  /** @type {Props} */
  let {
    options = [],
    valeur = $bindable(),
    taille = "md",
    pleineLargeur = false,
    onChange,
  } = $props();

  let conteneur = $state(/** @type {HTMLElement|null} */ (null));
  let indicateur = $state({ gauche: 0, largeur: 0, pret: false });

  /**
   * Recalcule la position de l'indicateur depuis la géométrie réelle du
   * bouton actif — plus fiable qu'un calcul en pourcentage, qui casse dès
   * que les libellés ont des longueurs différentes.
   */
  function repositionner() {
    if (!conteneur) return;
    const actif = conteneur.querySelector('[data-actif="true"]');
    if (!(actif instanceof HTMLElement)) return;
    indicateur = {
      gauche: actif.offsetLeft,
      largeur: actif.offsetWidth,
      pret: true,
    };
  }

  $effect(() => {
    // Dépendances explicites. `conteneur` en fait partie : sans lui,
    // l'effet ne se relance pas quand `bind:this` est résolu et
    // l'indicateur ne s'affiche jamais au premier rendu.
    const el = conteneur;
    valeur;
    options;
    if (!el) return;

    // `$effect` s'exécute après mise à jour du DOM : la géométrie est déjà
    // juste. Une seconde passe différée rattrape le cas où une police se
    // charge après coup et change la largeur des libellés.
    repositionner();
    const t = setTimeout(repositionner, 60);
    return () => clearTimeout(t);
  });

  function choisir(id) {
    valeur = id;
    onChange?.(id);
  }

  let classesBouton = $derived(
    taille === "sm" ? "px-2.5 py-1 text-xs" : "px-3 py-1.5 text-sm",
  );
</script>

<svelte:window onresize={repositionner} />

<div
  bind:this={conteneur}
  class="relative inline-flex gap-0.5 rounded-lg border border-stone-200 bg-stone-50 p-1 dark:border-stone-700 dark:bg-stone-900/60
         {pleineLargeur ? 'flex w-full' : ''}"
  role="tablist"
>
  <!-- Indicateur glissant, sous les boutons -->
  {#if indicateur.pret}
    <span
      class="pointer-events-none absolute top-1 bottom-1 rounded-md bg-white shadow-sm ring-1 ring-stone-200 transition-all duration-200 ease-out dark:bg-stone-700 dark:ring-stone-600"
      style="left: {indicateur.gauche}px; width: {indicateur.largeur}px;"
    ></span>
  {/if}

  {#each options as opt (opt.id)}
    {@const actif = valeur === opt.id}
    <button
      type="button"
      role="tab"
      aria-selected={actif}
      data-actif={actif}
      class="relative z-10 inline-flex items-center justify-center gap-1.5 rounded-md font-medium transition-colors duration-150
             {classesBouton}
             {pleineLargeur ? 'flex-1' : ''}
             {actif
               ? 'text-emerald-800 dark:text-emerald-300'
               : 'text-stone-600 hover:text-stone-900 dark:text-stone-400 dark:hover:text-stone-200'}"
      onclick={() => choisir(opt.id)}
    >
      {#if opt.icon}
        <opt.icon class="h-3.5 w-3.5 shrink-0" />
      {/if}
      <span class="truncate">{opt.label}</span>
      {#if opt.badge != null && opt.badge > 0}
        <span
          class="rounded-full px-1.5 text-[10px] font-semibold tabular-nums transition-colors
                 {actif
                   ? 'bg-emerald-100 text-emerald-800 dark:bg-emerald-900/60 dark:text-emerald-300'
                   : 'bg-stone-200 text-stone-600 dark:bg-stone-700 dark:text-stone-400'}"
        >
          {opt.badge}
        </span>
      {/if}
    </button>
  {/each}
</div>
