<script>
  import { getContext } from "svelte";

  /**
   * En-tête de page — titre, description, actions.
   *
   * Chaque écran écrivait son propre en-tête, avec des tailles et des
   * marges légèrement différentes. Les écarts ne se voient pas isolément
   * mais donnent une impression de flottement quand on navigue.
   *
   * L'icône dans une pastille colorée sert de repère : on reconnaît la
   * page avant même d'avoir lu le titre.
   *
   * ## Embarqué dans une étape du parcours
   *
   * Le parcours affiche un écran à l'intérieur d'une étape qui porte déjà
   * son titre, son rôle et ses pièges. Deux titres empilés diraient deux
   * fois la même chose et repousseraient l'outil hors de vue. L'en-tête se
   * réduit alors à sa barre d'actions — les boutons, eux, restent
   * indispensables.
   *
   * Le contexte plutôt qu'une propriété : l'écran embarqué ne sait pas
   * qu'il l'est, et n'a pas à le savoir. Onze fichiers restent intacts.
   *
   * @typedef {Object} Props
   * @property {string} titre
   * @property {string} [description]
   * @property {any} [icon]
   * @property {"emerald"|"sky"|"amber"|"stone"|"red"} [ton]
   * @property {import('svelte').Snippet} [actions] - boutons alignés à droite
   */
  /** @type {Props} */
  let { titre, description = "", icon: Icon, ton = "emerald", actions } = $props();

  /** Vrai quand le parcours affiche cet écran dans une de ses étapes. */
  const embarque = getContext("parcours.embarque") === true;

  const TONS = {
    emerald: "bg-emerald-100 text-emerald-700 dark:bg-emerald-900/40 dark:text-emerald-400",
    sky: "bg-sky-100 text-sky-700 dark:bg-sky-900/40 dark:text-sky-400",
    amber: "bg-amber-100 text-amber-700 dark:bg-amber-900/40 dark:text-amber-400",
    stone: "bg-stone-100 text-stone-600 dark:bg-stone-800 dark:text-stone-400",
    red: "bg-red-100 text-red-700 dark:bg-red-900/40 dark:text-red-400",
  };
</script>

{#if embarque}
  <!-- L'étape porte déjà le titre : ne reste que de quoi agir. -->
  {#if actions}
    <div class="flex flex-wrap items-center justify-end gap-2">
      {@render actions()}
    </div>
  {/if}
{:else}
<header class="flex items-start justify-between gap-4">
  <div class="flex min-w-0 items-start gap-3">
    {#if Icon}
      <div class="mt-0.5 shrink-0 rounded-xl p-2.5 {TONS[ton]}">
        <Icon class="h-5 w-5" />
      </div>
    {/if}
    <div class="min-w-0">
      <h1 class="text-2xl font-semibold text-stone-900 dark:text-stone-100">
        {titre}
      </h1>
      {#if description}
        <p class="mt-1 max-w-3xl text-sm leading-relaxed text-stone-600 dark:text-stone-400">
          {description}
        </p>
      {/if}
    </div>
  </div>
  {#if actions}
    <div class="flex shrink-0 items-center gap-2">
      {@render actions()}
    </div>
  {/if}
</header>
{/if}
