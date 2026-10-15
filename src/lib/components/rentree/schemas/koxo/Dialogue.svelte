<script>
  /**
   * Une boîte de dialogue de KoXo : barre de titre blanche, corps bleuté.
   *
   * @typedef {Object} Props
   * @property {string} titre
   * @property {import('svelte').Snippet} children
   * @property {import('svelte').Snippet} [boutons]
   */
  /** @type {Props} */
  let { titre, children, boutons } = $props();
</script>

<div
  class="overflow-hidden rounded-[3px] border border-[#8C99AA] bg-white text-[12px] leading-[1.45] text-black shadow-[0_6px_20px_-8px_rgba(0,0,0,0.35)]"
  style="font-family: 'Segoe UI', Tahoma, sans-serif;"
>
  <div class="flex h-8 items-center justify-between bg-white pl-3 text-[12.5px]">
    <span class="truncate">{titre}</span>
    <span class="grid w-10 place-items-center text-[13px] text-[#333]" aria-hidden="true">✕</span>
  </div>
  <div class="border-t border-[#D5DEE8] bg-[#EEF4FB] px-3 py-3">{@render children()}</div>
  {#if boutons}
    <div class="flex items-center justify-between gap-2 border-t border-[#D5DEE8] bg-[#EEF4FB] px-2 py-1.5">{@render boutons()}</div>
  {/if}
</div>
