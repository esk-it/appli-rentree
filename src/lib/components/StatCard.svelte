<script>
  /**
   * Carte statistique pour le tableau de bord.
   * @typedef {Object} Props
   * @property {string} label
   * @property {string|number} value
   * @property {string} [variante]  - "default", "success", "info", "warning"
   * @property {any} [icon]         - composant lucide-svelte
   * @property {string} [hint]      - sous-texte optionnel
   */
  /** @type {Props} */
  let { label, value, variante = "default", icon: Icon, hint } = $props();

  const variants = {
    default: "bg-white text-stone-900 border-stone-200",
    success: "bg-emerald-50 text-emerald-900 border-emerald-200",
    info: "bg-sky-50 text-sky-900 border-sky-200",
    warning: "bg-amber-50 text-amber-900 border-amber-200",
  };
  const iconColors = {
    default: "text-stone-500",
    success: "text-emerald-600",
    info: "text-sky-600",
    warning: "text-amber-600",
  };
</script>

<div class="rounded-xl border p-4 shadow-sm transition hover:shadow-md {variants[variante]}">
  <div class="flex items-start justify-between gap-3">
    <div class="min-w-0">
      <p class="text-xs font-medium uppercase tracking-wide opacity-70">
        {label}
      </p>
      <p class="mt-1 text-2xl font-semibold tabular-nums">{value}</p>
      {#if hint}
        <p class="mt-1 text-xs opacity-60">{hint}</p>
      {/if}
    </div>
    {#if Icon}
      <Icon class="h-5 w-5 shrink-0 {iconColors[variante]}" />
    {/if}
  </div>
</div>
