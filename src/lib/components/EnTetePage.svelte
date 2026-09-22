<script>
  import { getContext } from "svelte";
  import FilAriane from "$lib/components/FilAriane.svelte";
  import { teinteCourante } from "$lib/ecran.svelte.js";

  /**
   * En-tête de page — fil d'Ariane, titre, description, actions.
   *
   * Chaque écran écrivait son propre en-tête, avec des tailles et des
   * marges légèrement différentes. Les écarts ne se voient pas isolément
   * mais donnent une impression de flottement quand on navigue.
   *
   * ## Le fil d'Ariane, alors que la barre d'onglets existe
   *
   * Les deux ne disent pas la même chose. La barre dit *ce qu'il y a à
   * côté* ; le fil dit *d'où l'on vient* — et il ramène en un clic à
   * l'accueil, qui n'est dans aucune barre. Il vient des maquettes, où il
   * tient ce rôle seul.
   *
   * Ni l'un ni l'autre n'est déclaré par l'écran : la navigation dépose
   * dans un module ce qu'elle sait, l'en-tête l'y lit. Trente fichiers
   * restent intacts.
   *
   * ## L'icône porte la couleur de la famille
   *
   * Orange la rentrée, violet l'année, rose les photos. C'est le repère
   * qu'on attrape avant d'avoir lu le titre, et il coûte une plaque de
   * quarante-huit pixels. Le `ton` explicite l'emporte, pour les rares
   * écrans qui veulent se signaler autrement.
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
   * @property {string[]} [chemin] - étapes ajoutées après la partie
   * @property {import('svelte').Snippet} [actions] - boutons alignés à droite
   */
  /** @type {Props} */
  let {
    titre,
    description = "",
    icon: Icon,
    ton = null,
    chemin = [],
    actions,
  } = $props();

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
  <div class="space-y-3">
    <FilAriane {chemin} />

    <!-- La forme des maquettes : titre à gauche, actions alignées sur sa
         ligne de base, rien autour. -->
    <header class="flex flex-wrap items-end justify-between gap-x-6 gap-y-3">
      <div class="flex min-w-0 items-center gap-4">
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
          <h1 class="titre-affiche text-[32px] leading-tight text-stone-900 dark:text-stone-50">
            {titre}
          </h1>
          {#if description}
            <p class="mt-1 max-w-4xl text-sm leading-relaxed text-stone-600 dark:text-stone-400">
              {description}
            </p>
          {/if}
        </div>
      </div>
      {#if actions}
        <div class="flex shrink-0 flex-wrap items-center gap-3">
          {@render actions()}
        </div>
      {/if}
    </header>
  </div>
{/if}
