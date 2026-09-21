<script>
  import { getContext } from "svelte";
  import { teinteCourante } from "$lib/ecran.svelte.js";

  /**
   * En-tête de page — titre, description, actions.
   *
   * Chaque écran écrivait son propre en-tête, avec des tailles et des
   * marges légèrement différentes. Les écarts ne se voient pas isolément
   * mais donnent une impression de flottement quand on navigue.
   *
   * ## La couleur vient de la navigation, pas de l'écran
   *
   * L'icône est posée sur un voile de la teinte de la famille — orange la
   * rentrée, violet l'année, rose les photos. Aucun des trente écrans n'a
   * eu à la déclarer : la navigation dépose l'écran ouvert dans un module,
   * et l'en-tête l'y lit. Le `ton` explicite reste possible et l'emporte,
   * pour les rares cas où un écran veut se signaler autrement.
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

  const TONS = {
    emerald: "var(--color-emerald-600)",
    sky: "var(--color-sky-600)",
    amber: "var(--color-amber-600)",
    stone: "var(--color-stone-500)",
    red: "var(--color-red-600)",
  };

  let couleur = $derived(ton ? (TONS[ton] ?? TONS.emerald) : teinteCourante());
</script>

{#if embarque}
  <!-- L'étape porte déjà le titre : ne reste que de quoi agir. -->
  {#if actions}
    <div class="flex flex-wrap items-center justify-end gap-2">
      {@render actions()}
    </div>
  {/if}
{:else}
  <header class="border-b border-stone-200 pb-4 dark:border-stone-800">
    <div class="flex items-start justify-between gap-4">
      <div class="flex min-w-0 items-center gap-3.5">
        {#if Icon}
          <span
            class="plaque-icone h-12 w-12"
            style="--teinte: {couleur};"
            aria-hidden="true"
          >
            <Icon class="h-6 w-6" style="stroke-width: 1.8;" />
          </span>
        {/if}
        <div class="min-w-0">
          <h1 class="titre-affiche text-[28px] leading-tight text-stone-900 dark:text-stone-50">
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
    </div>
  </header>
{/if}
