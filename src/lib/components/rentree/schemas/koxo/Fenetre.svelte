<script>
  /**
   * La fenêtre de KoXo Administrator, telle que Windows la dessine —
   * redessinée d'après les captures de Johann (15 octobre 2026), noms et
   * chiffres inventés. Toujours en clair, quel que soit le thème : c'est
   * l'écran d'un autre logiciel.
   *
   * @typedef {Object} Props
   * @property {string} [titre]
   * @property {boolean} [modeSelection] - le bandeau rouge de l'export
   * @property {string|null} [menu]      - le menu ouvert, « Général »
   * @property {boolean} [pied]          - la barre de progression du bas
   * @property {import('svelte').Snippet} children
   */
  /** @type {Props} */
  let {
    titre = "KoXo Administrator V4.0 :: [Mode Expert]",
    modeSelection = false,
    menu = null,
    pied = true,
    children,
  } = $props();
</script>

<div
  class="overflow-hidden rounded-[3px] border border-[#8C99AA] bg-white text-[12px] leading-[1.4] text-black shadow-[0_6px_20px_-8px_rgba(0,0,0,0.35)]"
  style="font-family: 'Segoe UI', Tahoma, sans-serif;"
>
  <div class="flex h-7 items-center gap-2 bg-white pl-2">
    {#if modeSelection}
      <span class="bg-[#FF1F1F] px-1.5 py-0.5 text-[13px] font-bold whitespace-nowrap text-white">Vous êtes en MODE SELECTION</span>
    {:else}
      <span class="grid h-4 w-4 shrink-0 place-items-center rounded-[2px] bg-[#1C6DD0] text-[11px] font-black text-white">K</span>
    {/if}
    <span class="min-w-0 flex-1 truncate text-[#1A1A1A]">{titre}</span>
    <span class="flex h-full text-[13px] text-[#333]" aria-hidden="true">
      <span class="grid w-10 place-items-center">─</span>
      <span class="grid w-10 place-items-center">☐</span>
      <span class="grid w-10 place-items-center">✕</span>
    </span>
  </div>
  <div class="flex gap-3 border-b border-[#DADFE6] bg-white px-2 pb-1">
    {#each ["Général", "Action", "Aide"] as m (m)}
      <span class="px-1 {menu === m ? 'bg-[#CCE4F7] outline outline-1 outline-[#99C9EF]' : ''} {modeSelection ? 'text-[#8A8A8A]' : ''}">{m}</span>
    {/each}
  </div>
  <div class="relative">{@render children()}</div>
  {#if pied}
    <div class="flex items-center gap-1 border-t border-[#C9D3DF] bg-[#F0F0F0] p-0.5">
      <div class="flex-1 border border-[#BCBCBC] bg-white text-center text-[11px]">0%</div>
      <span class="px-3 text-[11px] text-[#A0A0A0]">✔ Appliquer</span>
    </div>
  {/if}
</div>
