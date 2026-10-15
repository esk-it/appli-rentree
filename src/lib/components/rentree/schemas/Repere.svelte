<script>
  /**
   * Un repère numéroté : le même dans la consigne et sur le schéma, pour
   * que « ② » désigne sans hésiter le même endroit des deux côtés.
   *
   * @typedef {Object} Props
   * @property {number} n
   * @property {boolean} [petit] - dans le fil d'une consigne
   */
  /** @type {Props} */
  let { n, petit = false } = $props();
</script>

<span
  aria-label="repère {n}"
  class="inline-grid shrink-0 place-items-center rounded-full bg-[#FF7A59] font-extrabold text-white {petit
    ? 'h-[18px] w-[18px] align-[-3px] text-[10px]'
    : 'h-6 w-6 text-xs shadow-[0_0_0_4px_rgba(255,122,89,0.25)]'}"
>{n}</span>
