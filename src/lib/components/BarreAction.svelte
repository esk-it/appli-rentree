<script>
  /**
   * La barre d'action, en pied d'écran.
   *
   * ## Ce qu'elle dit, et pourquoi elle le dit toujours
   *
   * « Rien n'est modifié tant que tu n'as pas validé. » Cette phrase revient
   * sur chaque écran qui agit, dans les maquettes comme ici, et ce n'est pas
   * du remplissage : ces écrans déplacent des comptes Google, renomment des
   * unités, créent des lecteurs dans PMB. Savoir qu'on peut regarder sans
   * rien casser est ce qui permet de regarder.
   *
   * Elle est **collante** en bas : sur un tableau de quatre-vingt-sept
   * lignes, un bouton qui n'apparaît qu'après un long défilement donne
   * l'impression qu'il n'existe pas.
   *
   * @typedef {Object} Props
   * @property {string} [message]  - ce qu'il faut savoir avant de cliquer
   * @property {import('svelte').Snippet} children - les boutons
   */
  /** @type {Props} */
  let {
    message = "Rien n'est modifié tant que tu n'as pas validé.",
    children,
  } = $props();
</script>

<div
  class="sticky bottom-0 mt-4 flex flex-wrap items-center justify-between gap-4 border-t border-stone-200 bg-stone-50/95 py-4 backdrop-blur dark:border-stone-800 dark:bg-stone-950/95"
>
  {#if message}
    <p class="max-w-2xl text-sm text-stone-600 dark:text-stone-400">{message}</p>
  {/if}
  <div class="ml-auto flex flex-wrap items-center gap-3">
    {@render children()}
  </div>
</div>
