<script>
  import ChevronDown from "@lucide/svelte/icons/chevron-down";
  import Check from "@lucide/svelte/icons/check";
  import { annee, choisir, courante } from "$lib/annee.svelte.js";

  /**
   * L'année de travail, dans l'en-tête.
   *
   * ## Pourquoi en haut à droite, et pas dans chaque écran
   *
   * Dix-neuf écrans demandaient leur année chacun de leur côté, avec
   * chacun son menu et son défaut. Rien ne garantissait qu'ils parlent de
   * la même : on pouvait lire la concordance de 2025-2026 en croyant
   * préparer 2026-2027, et ça ne se voyait nulle part.
   *
   * Une seule année, déclarée une fois, affichée en permanence. Un choix
   * qui vaut pour tout le programme a sa place là où rien ne le cache.
   */
  let ouvert = $state(false);
  let conteneur = $state(/** @type {HTMLElement|null} */ (null));

  let active = $derived(courante());

  function dehors(e) {
    if (conteneur && !conteneur.contains(e.target)) ouvert = false;
  }

  $effect(() => {
    if (!ouvert) return;
    document.addEventListener("mousedown", dehors);
    return () => document.removeEventListener("mousedown", dehors);
  });
</script>

<div class="relative" bind:this={conteneur}>
  <button
    type="button"
    class="flex items-center gap-1.5 rounded-full px-3 py-1.5 text-sm font-semibold text-stone-900 transition-colors hover:bg-stone-100 dark:text-stone-100 dark:hover:bg-stone-800"
    aria-haspopup="listbox"
    aria-expanded={ouvert}
    onclick={() => (ouvert = !ouvert)}
  >
    {#if active}
      {active.libelle}
    {:else}
      <span class="text-stone-500">Année…</span>
    {/if}
    <ChevronDown class="h-3.5 w-3.5 opacity-60" />
  </button>

  {#if ouvert}
    <div
      class="card card-relief anim-apparition-sans-transform absolute right-0 z-50 mt-1.5 w-72 overflow-hidden p-1"
      role="listbox"
    >
      <p class="px-3 pt-2 pb-1.5 text-[11px] leading-relaxed text-stone-500 dark:text-stone-400">
        Une seule base, une année de travail. L'identité des personnes
        traverse les années — c'est ce qui permet de les suivre.
      </p>
      {#each annee.liste as a (a.id)}
        {@const choisie = a.id === annee.id}
        <button
          type="button"
          role="option"
          aria-selected={choisie}
          class="flex w-full items-center gap-2.5 rounded-xl px-3 py-2 text-left transition-colors hover:bg-stone-100 dark:hover:bg-stone-800"
          onclick={() => {
            choisir(a.id);
            ouvert = false;
          }}
        >
          <span class="w-4 shrink-0 text-emerald-600 dark:text-emerald-400">
            {#if choisie}<Check class="h-4 w-4" />{/if}
          </span>
          <span class="min-w-0 flex-1">
            <span class="block text-sm font-semibold">{a.libelle}</span>
            <span class="block text-xs text-stone-500 tabular-nums dark:text-stone-400">
              {a.nb_personnes_distinctes} personne{a.nb_personnes_distinctes > 1 ? "s" : ""}
            </span>
          </span>
        </button>
      {/each}
      {#if !annee.liste.length}
        <p class="px-3 py-3 text-sm text-stone-500 dark:text-stone-400">
          Aucune année ingérée pour l'instant.
        </p>
      {/if}
    </div>
  {/if}
</div>
