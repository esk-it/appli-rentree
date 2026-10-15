<script>
  import ImageIcon from "@lucide/svelte/icons/image";

  /**
   * La place du schéma d'un écran qui n'est pas encore dessiné. Elle dit
   * de quelle capture il naîtra : les consignes, à gauche, suffisent en
   * attendant.
   *
   * @typedef {Object} Props
   * @property {string} capture
   */
  /** @type {Props} */
  let { capture } = $props();
</script>

<div class="grid min-h-[220px] place-items-center rounded-xl border-2 border-dashed border-stone-300 bg-stone-50 px-6 py-8 text-center dark:border-stone-700 dark:bg-stone-900/50">
  <div class="max-w-md">
    <ImageIcon class="mx-auto h-7 w-7 text-stone-400" />
    <p class="mt-3 text-sm font-semibold text-stone-700 dark:text-stone-200">Le schéma de cet écran est à venir</p>
    <p class="mt-1 text-sm text-stone-500 dark:text-stone-400">
      En attendant, les consignes suffisent. Les captures d'où il sera
      redessiné : {capture}.
    </p>
  </div>
</div>
