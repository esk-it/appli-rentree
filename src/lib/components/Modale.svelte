<script>
  /**
   * Fenêtre modale.
   *
   * ## Le problème qu'elle résout
   *
   * Un `flex items-center` sur un conteneur `fixed inset-0` centre bien la
   * boîte, mais si son contenu dépasse la hauteur de la fenêtre, le
   * débordement se répartit en haut ET en bas — et rien ne permet de
   * remonter : le haut du formulaire devient inatteignable.
   *
   * La parade tient en deux points :
   *
   * 1. le voile porte le défilement (`overflow-y-auto`) ;
   * 2. un conteneur intermédiaire en `min-h-full items-center` centre la
   *    boîte quand elle tient, et laisse le défilement opérer sinon.
   *
   * Le titre est rendu ici plutôt que laissé à l'appelant, ce qui garantit
   * qu'il reste le premier élément visible même après un défilement.
   *
   * @typedef {Object} Props
   * @property {string} titre
   * @property {"sm"|"md"|"lg"} [largeur]
   * @property {() => void} onFermer
   * @property {import('svelte').Snippet} children  - corps du formulaire
   * @property {import('svelte').Snippet} [actions] - boutons de pied
   */
  /** @type {Props} */
  let { titre, largeur = "md", onFermer, children, actions } = $props();

  const LARGEURS = {
    sm: "max-w-sm",
    md: "max-w-md",
    lg: "max-w-lg",
  };

  function surTouche(e) {
    if (e.key === "Escape") onFermer();
  }

  /**
   * Déplace le nœud à la racine du document.
   *
   * `position: fixed` ne se réfère à la fenêtre que si aucun ancêtre ne
   * porte `transform`, `filter`, `backdrop-filter` ou `will-change` : un
   * tel ancêtre devient bloc conteneur, et la modale se cale sur lui —
   * donc se retrouve rognée par la zone de contenu.
   *
   * Le défaut s'est produit ici même : l'animation de changement de page
   * laissait un `translateY(0)` résiduel sur le conteneur des écrans.
   * Corriger cette animation suffisait, mais dépendre de l'absence de
   * transform chez tous les ancêtres présents et futurs est fragile.
   * Sortir la modale de l'arbre supprime la classe de défaut entière.
   */
  function ancrerAuDocument(node) {
    document.body.appendChild(node);
    return {
      destroy() {
        node.remove();
      },
    };
  }
</script>

<svelte:window onkeydown={surTouche} />

<!-- Voile : porte le défilement pour que rien ne devienne inatteignable -->
<div
  use:ancrerAuDocument
  class="fixed inset-0 z-50 overflow-y-auto bg-stone-900/50 backdrop-blur-sm"
  role="presentation"
  onclick={onFermer}
>
  <!-- `min-h-full` + `items-center` : centré quand ça tient, défilable sinon -->
  <div class="flex min-h-full items-center justify-center p-4">
    <div
      class="card anim-apparition w-full {LARGEURS[largeur]} p-5"
      role="dialog"
      aria-modal="true"
      aria-label={titre}
      onclick={(e) => e.stopPropagation()}
    >
      <h2 class="mb-4 text-lg font-semibold text-stone-900 dark:text-stone-100">
        {titre}
      </h2>

      <div class="space-y-3">
        {@render children()}
      </div>

      {#if actions}
        <div class="mt-5 flex justify-end gap-2">
          {@render actions()}
        </div>
      {/if}
    </div>
  </div>
</div>
