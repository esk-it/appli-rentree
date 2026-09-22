<script>
  import { getContext } from "svelte";

  /**
   * En-tête de page — titre, description, actions.
   *
   * Chaque écran écrivait son propre en-tête, avec des tailles et des
   * marges légèrement différentes. Les écarts ne se voient pas isolément
   * mais donnent une impression de flottement quand on navigue.
   *
   * ## Ni icône ni carte
   *
   * Les maquettes du tour 5 posent un grand titre, sa description, et les
   * actions sur la même ligne de base. La couleur de la famille se lit
   * ailleurs — l'onglet ouvert, les chiffres du bandeau, les pastilles
   * d'état — et une icône de plus ne la dirait pas mieux.
   *
   * `icon` et `ton` restent acceptés sans effet : trente écrans les
   * passent, et les retirer partout pour un en-tête qui les ignore serait
   * trente diffs pour rien.
   *
   * ## Le filet plutôt que la boîte
   *
   * L'en-tête ne s'enferme pas dans une carte : un trait sous le titre
   * sépare autant, et laisse l'écran respirer.
   *
   * ## Embarqué dans une étape du parcours
   *
   * Le parcours affiche un écran à l'intérieur d'une étape qui porte déjà
   * son titre, son rôle et ses pièges. Deux titres empilés diraient deux
   * fois la même chose et repousseraient l'outil hors de vue. L'en-tête se
   * réduit alors à sa barre d'actions — les boutons, eux, restent
   * indispensables.
   *
   * @typedef {Object} Props
   * @property {string} titre
   * @property {string} [description]
   * @property {any} [icon]
   * @property {"emerald"|"sky"|"amber"|"stone"|"red"} [ton] - force une couleur
   * @property {import('svelte').Snippet} [actions] - boutons alignés à droite
   */
  /** @type {Props} */
  let { titre, description = "", icon: Icon, ton = null, actions } = $props();

  /** Vrai quand le parcours affiche cet écran dans une de ses étapes. */
  const embarque = getContext("parcours.embarque") === true;

</script>

{#if embarque}
  <!-- L'étape porte déjà le titre : ne reste que de quoi agir. -->
  {#if actions}
    <div class="flex flex-wrap items-center justify-end gap-2">
      {@render actions()}
    </div>
  {/if}
{:else}
  <!-- La forme des maquettes du tour 5 : titre et description à gauche,
       actions alignées sur la ligne de base du titre, rien autour. Pas de
       carte, pas d'icône — c'est le grand titre qui situe la page, et les
       chiffres en dessous qui portent la couleur. -->
  <header class="flex flex-wrap items-end justify-between gap-x-6 gap-y-3">
    <div class="min-w-0">
      <h1 class="titre-affiche text-[32px] leading-tight text-stone-900 dark:text-stone-50">
        {titre}
      </h1>
      {#if description}
        <p class="mt-1 max-w-4xl text-sm leading-relaxed text-stone-600 dark:text-stone-400">
          {description}
        </p>
      {/if}
    </div>
    {#if actions}
      <div class="flex shrink-0 flex-wrap items-center gap-3">
        {@render actions()}
      </div>
    {/if}
  </header>
{/if}
