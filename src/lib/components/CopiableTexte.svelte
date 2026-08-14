<script>
  import Copy from "@lucide/svelte/icons/copy";
  import Check from "@lucide/svelte/icons/check";

  /**
   * Valeur technique copiable au clic — login, email, clé pivot.
   *
   * Pensé pour l'usage réel : au moment de créer un compte à la main dans
   * KoXo ou Google, on veut récupérer un login sans le resélectionner à la
   * souris. Le retour visuel remplace l'icône pendant deux secondes plutôt
   * que d'ouvrir une notification, qui serait disproportionnée pour une
   * action aussi anodine.
   *
   * @typedef {Object} Props
   * @property {string} valeur
   * @property {string} [classe]  - classes appliquées au texte
   */
  /** @type {Props} */
  let { valeur = "", classe = "" } = $props();

  let copie = $state(false);
  let minuteur;

  async function copier() {
    if (!valeur) return;
    try {
      await navigator.clipboard.writeText(valeur);
      copie = true;
      clearTimeout(minuteur);
      minuteur = setTimeout(() => (copie = false), 2000);
    } catch {
      // Presse-papiers refusé par le contexte : on ne fait rien de visible
      // plutôt que d'afficher une erreur pour une action secondaire.
    }
  }
</script>

{#if valeur}
  <button
    type="button"
    class="group inline-flex max-w-full items-center gap-1 rounded px-1 -mx-1 text-left transition-colors hover:bg-stone-100 dark:hover:bg-stone-700 {classe}"
    onclick={copier}
    title="Copier « {valeur} »"
  >
    <span class="truncate">{valeur}</span>
    {#if copie}
      <Check class="h-3 w-3 shrink-0 text-emerald-600 dark:text-emerald-400" />
    {:else}
      <Copy
        class="h-3 w-3 shrink-0 text-stone-400 opacity-0 transition-opacity group-hover:opacity-100"
      />
    {/if}
  </button>
{:else}
  <span class={classe}>—</span>
{/if}
