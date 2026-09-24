<script>
  /**
   * Les filtres du Référentiel, chacun avec ce qu'il ramènerait.
   *
   * Un menu déroulant cache ce qu'il contient : on ne sait qu'il y a
   * vingt-quatre personnes sans site qu'après l'avoir ouvert, et choisi.
   * Ici chaque valeur porte son nombre — celui qu'on obtiendrait en la
   * cochant, compte tenu des autres filtres. On lit l'état du référentiel
   * avant même de filtrer.
   *
   * Dans un même groupe, cocher deux valeurs les ajoute (NDK **ou** SU) ;
   * d'un groupe à l'autre, elles se cumulent (NDK **et** sans INE).
   *
   * @typedef {Object} Option
   * @property {string} id
   * @property {string} label
   * @property {number} compte
   * @property {"alerte"|"attente"|""} [ton]
   *
   * @typedef {Object} Facette
   * @property {string} cle
   * @property {string} titre
   * @property {Option[]} options
   *
   * @typedef {Object} Props
   * @property {Facette[]} facettes
   * @property {Record<string, string[]>} choix  - bindable
   */
  /** @type {Props} */
  let { facettes = [], choix = $bindable({}) } = $props();

  function basculer(cle, id) {
    const actuels = choix[cle] ?? [];
    choix = {
      ...choix,
      [cle]: actuels.includes(id) ? actuels.filter((x) => x !== id) : [...actuels, id],
    };
  }

  const TONS = {
    alerte: "text-red-700 dark:text-red-400",
    attente: "text-amber-700 dark:text-amber-400",
    "": "text-stone-500 dark:text-stone-400",
  };
</script>

<div class="space-y-5">
  {#each facettes as f (f.cle)}
    <fieldset>
      <legend class="libelle-champ mb-1.5 flex w-full items-center gap-2">
        {f.titre}
        {#if choix[f.cle]?.length}
          <button
            type="button"
            class="ml-auto text-[11px] font-semibold tracking-normal text-stone-500 normal-case hover:text-stone-900 dark:hover:text-stone-100"
            onclick={() => (choix = { ...choix, [f.cle]: [] })}
          >
            effacer
          </button>
        {/if}
      </legend>
      {#each f.options as o (o.id)}
        {@const coche = choix[f.cle]?.includes(o.id) ?? false}
        <label
          class="flex h-8 cursor-pointer items-center gap-2.5 text-sm {o.compte === 0 && !coche
            ? 'opacity-45'
            : ''}"
        >
          <input
            type="checkbox"
            class="h-4 w-4 shrink-0 cursor-pointer accent-emerald-600"
            checked={coche}
            onchange={() => basculer(f.cle, o.id)}
          />
          <span class="min-w-0 flex-1 truncate {coche ? 'font-semibold text-stone-900 dark:text-stone-100' : 'text-stone-700 dark:text-stone-300'}">
            {o.label}
          </span>
          <span class="text-[13px] tabular-nums {TONS[o.ton ?? '']}">
            {o.compte.toLocaleString("fr-FR")}
          </span>
        </label>
      {/each}
    </fieldset>
  {/each}
</div>
