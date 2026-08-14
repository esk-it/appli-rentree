<script>
  import Loader2 from "@lucide/svelte/icons/loader-2";

  /**
   * Bouton avec état de travail intégré.
   *
   * Pendant une opération, l'icône laisse place à un indicateur qui
   * tourne et le bouton se désactive. L'information reste à l'endroit où
   * l'utilisateur vient de cliquer, au lieu d'un « Traitement… » posé à
   * côté qu'il faut aller chercher des yeux.
   *
   * @typedef {Object} Props
   * @property {"primary"|"secondary"|"danger"} [variante]
   * @property {any} [icon]           - composant Lucide
   * @property {boolean} [occupe]     - affiche l'indicateur et désactive
   * @property {boolean} [disabled]
   * @property {"sm"|"md"} [taille]
   * @property {string} [classe]
   * @property {() => void} [onclick]
   * @property {import('svelte').Snippet} [children]
   */
  /** @type {Props} */
  let {
    variante = "secondary",
    icon: Icon,
    occupe = false,
    disabled = false,
    taille = "md",
    classe = "",
    onclick,
    children,
  } = $props();

  const CLASSES = {
    primary: "btn-primary",
    secondary: "btn-secondary",
    danger: "btn-danger",
  };
</script>

<button
  type="button"
  class="{CLASSES[variante]} {taille === 'sm' ? '!px-3 !py-1.5 text-xs' : ''} {classe}"
  disabled={disabled || occupe}
  aria-busy={occupe}
  {onclick}
>
  {#if occupe}
    <Loader2 class="h-4 w-4 shrink-0 animate-spin" />
  {:else if Icon}
    <Icon class="h-4 w-4 shrink-0" />
  {/if}
  {@render children?.()}
</button>
