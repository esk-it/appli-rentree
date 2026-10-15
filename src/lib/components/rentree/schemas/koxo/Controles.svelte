<script>
  /**
   * Les contrôles Windows de KoXo, en petit : case à cocher, liste
   * déroulante, bouton. Un seul fichier : ils ne servent qu'aux schémas.
   *
   * @typedef {Object} Props
   * @property {"case"|"liste"|"bouton"} genre
   * @property {string} [texte]
   * @property {boolean} [coche]
   * @property {boolean} [grise]
   * @property {boolean} [marque]  - entouré de corail : c'est là qu'il faut regarder
   * @property {string} [icone]    - pour un bouton : « suivant », « precedent », « ok », « annuler »
   */
  /** @type {Props} */
  let { genre, texte = "", coche = false, grise = false, marque = false, icone = "" } = $props();
</script>

{#if genre === "case"}
  <span class="inline-flex items-center gap-1.5 rounded-[3px] {marque ? 'outline outline-2 outline-offset-2 outline-[#FF7A59]' : ''} {grise ? 'text-[#8E8E8E]' : ''}">
    <span class="grid h-[13px] w-[13px] shrink-0 place-items-center border bg-white {grise ? 'border-[#BDBDBD]' : 'border-[#333]'}">
      {#if coche}
        <svg viewBox="0 0 10 10" class="h-[9px] w-[9px]" aria-hidden="true"><path d="M1.5 5.2 4 7.6 8.6 2.4" fill="none" stroke={grise ? "#9A9A9A" : "#1A1A1A"} stroke-width="1.6" /></svg>
      {/if}
    </span>
    {texte}
  </span>
{:else if genre === "liste"}
  <span class="flex h-[22px] items-center justify-between border bg-white px-1.5 {marque ? 'border-[#FF7A59] outline outline-1 outline-[#FF7A59]' : 'border-[#ABADB3]'} {grise ? 'bg-[#F4F4F4] text-[#8E8E8E]' : ''}">
    <span class="truncate">{texte}</span><span class="pl-2 text-[10px] text-[#555]">⌄</span>
  </span>
{:else}
  <span class="inline-flex h-[23px] items-center gap-1.5 rounded-[2px] border border-[#ADADAD] bg-[#E9E9E9] px-2.5 whitespace-nowrap {marque ? 'outline outline-2 outline-offset-1 outline-[#FF7A59]' : ''}">
    {#if icone === "precedent"}<span class="grid h-3.5 w-3.5 place-items-center rounded-full bg-[#F08A3C] text-[9px] font-black text-white">◀</span>{/if}
    {#if icone === "ok"}<span class="grid h-3.5 w-3.5 place-items-center rounded-full bg-[#3BA03B] text-[9px] font-black text-white">✓</span>{/if}
    {#if icone === "annuler"}<span class="text-[13px] font-black text-[#D02020]">✕</span>{/if}
    <span><span class="underline decoration-[#555] underline-offset-1">{texte.slice(0, 1)}</span>{texte.slice(1)}</span>
    {#if icone === "suivant"}<span class="grid h-3.5 w-3.5 place-items-center rounded-full bg-[#F08A3C] text-[9px] font-black text-white">▶</span>{/if}
  </span>
{/if}
