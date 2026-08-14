<script>
  import Nombre from "$lib/components/Nombre.svelte";

  /**
   * Carte statistique — le bloc chiffré réutilisé dans tous les écrans.
   *
   * @typedef {Object} Props
   * @property {string} label
   * @property {string|number} value
   * @property {"default"|"success"|"info"|"warning"|"danger"} [variante]
   * @property {any} [icon]         - composant Lucide
   * @property {string} [hint]      - sous-texte optionnel
   * @property {boolean} [compact]  - version resserrée pour les grilles denses
   */
  /** @type {Props} */
  let {
    label,
    value,
    variante = "default",
    icon: Icon,
    hint,
    compact = false,
  } = $props();

  const variants = {
    default:
      "bg-white text-stone-900 border-stone-200 dark:bg-stone-800 dark:text-stone-100 dark:border-stone-700",
    success:
      "bg-emerald-50 text-emerald-900 border-emerald-200 dark:bg-emerald-900/20 dark:text-emerald-200 dark:border-emerald-800",
    info:
      "bg-sky-50 text-sky-900 border-sky-200 dark:bg-sky-900/20 dark:text-sky-200 dark:border-sky-800",
    warning:
      "bg-amber-50 text-amber-900 border-amber-200 dark:bg-amber-900/20 dark:text-amber-200 dark:border-amber-800",
    danger:
      "bg-red-50 text-red-900 border-red-200 dark:bg-red-900/20 dark:text-red-200 dark:border-red-800",
  };
  const iconColors = {
    default: "text-stone-400 dark:text-stone-500",
    success: "text-emerald-600 dark:text-emerald-400",
    info: "text-sky-600 dark:text-sky-400",
    warning: "text-amber-600 dark:text-amber-400",
    danger: "text-red-600 dark:text-red-400",
  };
</script>

<div
  class="anim-apparition rounded-xl border shadow-sm transition-shadow duration-200 hover:shadow-md
         {compact ? 'p-3' : 'p-4'} {variants[variante]}"
>
  <div class="flex items-start justify-between gap-3">
    <div class="min-w-0">
      <p class="text-xs font-medium uppercase tracking-wide opacity-70">
        {label}
      </p>
      <p class="mt-1 font-semibold tabular-nums {compact ? 'text-xl' : 'text-2xl'}">
        {#if typeof value === "number"}
          <Nombre valeur={value} />
        {:else}
          {value}
        {/if}
      </p>
      {#if hint}
        <p class="mt-1 text-xs opacity-60">{hint}</p>
      {/if}
    </div>
    {#if Icon}
      <Icon class="h-5 w-5 shrink-0 {iconColors[variante]}" />
    {/if}
  </div>
</div>
