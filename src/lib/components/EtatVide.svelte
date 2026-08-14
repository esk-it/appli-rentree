<script>
  /**
   * État vide — remplace les « Aucun résultat » en texte brut.
   *
   * Un écran vide doit dire trois choses : ce qui est vide, pourquoi, et
   * quoi faire ensuite. Le troisième point est le plus souvent oublié et
   * c'est celui qui débloque réellement l'utilisateur.
   *
   * @typedef {Object} Props
   * @property {any} [icon]        - composant Lucide
   * @property {string} titre
   * @property {string} [message]  - explication ou action suggérée
   * @property {"neutre"|"succes"|"attention"} [ton]
   * @property {import('svelte').Snippet} [children] - bouton d'action optionnel
   */
  /** @type {Props} */
  let { icon: Icon, titre, message = "", ton = "neutre", children } = $props();

  const TONS = {
    neutre: {
      bloc: "border-stone-200 bg-stone-50/60 dark:border-stone-700 dark:bg-stone-800/40",
      icone: "text-stone-300 dark:text-stone-600",
      titre: "text-stone-700 dark:text-stone-300",
    },
    succes: {
      bloc: "border-emerald-200 bg-emerald-50/60 dark:border-emerald-800 dark:bg-emerald-900/20",
      icone: "text-emerald-500 dark:text-emerald-400",
      titre: "text-emerald-900 dark:text-emerald-200",
    },
    attention: {
      bloc: "border-amber-200 bg-amber-50/60 dark:border-amber-800 dark:bg-amber-900/20",
      icone: "text-amber-500 dark:text-amber-400",
      titre: "text-amber-900 dark:text-amber-200",
    },
  };

  let style = $derived(TONS[ton] ?? TONS.neutre);
</script>

<div class="anim-apparition rounded-xl border border-dashed p-8 text-center {style.bloc}">
  {#if Icon}
    <Icon class="mx-auto mb-3 h-10 w-10 {style.icone}" />
  {/if}
  <p class="text-sm font-medium {style.titre}">{titre}</p>
  {#if message}
    <p class="mx-auto mt-1.5 max-w-md text-xs leading-relaxed text-stone-600 dark:text-stone-400">
      {message}
    </p>
  {/if}
  {#if children}
    <div class="mt-4 flex justify-center gap-2">
      {@render children()}
    </div>
  {/if}
</div>
