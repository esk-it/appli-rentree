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

  /**
   * La couleur porte l'état, le chiffre porte l'attention.
   *
   * Version précédente : un fond teinté sur toute la tuile, bordure
   * comprise. Cinq tuiles côte à côte donnaient cinq rectangles colorés
   * d'égal poids, où l'urgent ne se distinguait plus du normal.
   *
   * Ici le fond reste neutre et c'est **le nombre** qui prend la couleur,
   * avec l'icône sur sa plaque teintée. Une tuile rouge au milieu de
   * quatre sages se voit ; cinq tuiles colorées, non.
   */
  const TEINTES = {
    default: "var(--color-stone-500)",
    success: "var(--color-fam-koxo)",
    info: "var(--color-sky-600)",
    warning: "var(--color-amber-600)",
    danger: "var(--color-red-600)",
  };

  let couleur = $derived(TEINTES[variante] ?? TEINTES.default);
  let chiffreEnCouleur = $derived(variante !== "default");
</script>

<div
  class="card anim-apparition {compact ? 'p-3.5' : 'p-4'}"
  style="--teinte: {couleur};"
>
  <div class="flex items-start justify-between gap-3">
    <div class="min-w-0">
      <p class="libelle-champ">{label}</p>
      <p
        class="titre-affiche mt-1.5 tabular-nums {compact ? 'text-2xl' : 'text-3xl'}"
        style={chiffreEnCouleur ? `color: ${couleur};` : ""}
      >
        {#if typeof value === "number"}
          <Nombre valeur={value} />
        {:else}
          {value}
        {/if}
      </p>
      {#if hint}
        <p class="mt-1 text-xs text-stone-500 dark:text-stone-400">{hint}</p>
      {/if}
    </div>
    {#if Icon}
      <span class="plaque-icone h-9 w-9" aria-hidden="true">
        <Icon class="h-[18px] w-[18px]" style="stroke-width: 1.8;" />
      </span>
    {/if}
  </div>
</div>
