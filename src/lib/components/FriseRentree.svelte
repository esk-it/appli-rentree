<script>
  /**
   * La frise du parcours de rentrée.
   *
   * L'outil ne sert qu'une fois par an : entre deux campagnes, on a oublié
   * l'ordre et surtout ses raisons. Une navigation rangée par module
   * laissait cette connaissance hors de l'écran. La frise la remet dedans,
   * en permanence et sans occuper la place d'un module.
   *
   * Elle ne remplace pas le menu : on peut toujours aller où l'on veut.
   * Elle dit seulement où l'on en est, et ce que l'étape sert à faire.
   *
   * Deux principes de dessin :
   *
   * - **La position porte l'ordre.** Pas de numéro en gros caractères ;
   *   un rang discret suffit à se repérer, le reste se lit dans le rail.
   * - **Une seule étape parle à la fois.** Treize libellés alignés
   *   seraient illisibles ; seule l'étape courante déplie son propos.
   */
  import ChevronLeft from "@lucide/svelte/icons/chevron-left";
  import ChevronRight from "@lucide/svelte/icons/chevron-right";
  import ChevronsDownUp from "@lucide/svelte/icons/chevrons-down-up";
  import ChevronsUpDown from "@lucide/svelte/icons/chevrons-up-down";
  import Check from "@lucide/svelte/icons/check";
  import { ETAPES, PHASES, etapePour, etapesDe, indexDe } from "$lib/parcours.js";

  /**
   * @typedef {Object} Props
   * @property {string} page                    - écran affiché
   * @property {(p: string) => void} onNaviguer
   * @property {Record<string, boolean>} [faites] - étapes dont l'état se lit
   *   dans le référentiel. Les autres n'en ont pas : une case qui ne se
   *   coche jamais serait fausse autant que décourageante.
   */
  let { page, onNaviguer, faites = {} } = $props();

  // On travaille la rentrée sur plusieurs jours, en fermant l'application
  // entre deux. Retrouver l'étape où l'on s'était arrêté vaut mieux que de
  // la rechercher — et le repli, une fois choisi, n'a pas à être redemandé.
  const MEMOIRE = "parcours.etape";
  const MEMOIRE_REPLI = "parcours.replie";

  let idCourant = $state(
    typeof localStorage !== "undefined" ? localStorage.getItem(MEMOIRE) : null,
  );
  let replie = $state(
    typeof localStorage !== "undefined" &&
      localStorage.getItem(MEMOIRE_REPLI) === "1",
  );

  $effect(() => {
    if (typeof localStorage === "undefined") return;
    if (idCourant) localStorage.setItem(MEMOIRE, idCourant);
    localStorage.setItem(MEMOIRE_REPLI, replie ? "1" : "0");
  });

  // L'étape suivie prime sur la déduction par écran : trois étapes mènent à
  // la conformité, et changer d'onglet ne doit pas faire reculer la frise.
  let etape = $derived(etapePour(page, idCourant));
  let rang = $derived(etape ? indexDe(etape.id) : -1);

  // Hors parcours, on propose la suite de là où l'on s'était arrêté ; à
  // défaut, la première étape de préparation qui reste à faire.
  let prochaine = $derived.by(() => {
    const dernier = indexDe(idCourant ?? "");
    if (dernier >= 0 && dernier < ETAPES.length - 1) return ETAPES[dernier + 1];
    return (
      ETAPES.find((e) => e.phase === "preparation" && !faites[e.id]) ??
      ETAPES.find((e) => e.phase === "bascule")
    );
  });

  function etat(e) {
    if (etape && e.id === etape.id) return "courante";
    if (faites[e.id]) return "faite";
    return "attente";
  }

  function aller(e) {
    idCourant = e.id;
    onNaviguer(e.page);
  }

  function decaler(pas) {
    const cible = ETAPES[rang + pas];
    if (cible) aller(cible);
  }
</script>

<section
  class="border-b border-stone-200 bg-white/70 backdrop-blur-sm dark:border-stone-700 dark:bg-stone-800/60"
  aria-label="Parcours de la rentrée"
>
  <div class="mx-auto max-w-7xl px-6 pt-2.5 {replie ? 'pb-2.5' : 'pb-3'}">
    <!-- Le rail : chaque phase garde son groupe, séparé par un intervalle
         plus large qu'entre deux étapes — la respiration dit la coupure
         mieux qu'un trait. -->
    <div class="flex items-end gap-10">
      {#each PHASES as phase (phase.id)}
        <div class="flex flex-col gap-1.5">
          <span
            class="pl-0.5 text-[10px] font-medium uppercase tracking-[0.14em] text-stone-400 dark:text-stone-500"
          >
            {phase.titre}
          </span>
          <div class="flex items-center">
            {#each etapesDe(phase.id) as e, i (e.id)}
              {@const s = etat(e)}
              {#if i > 0}
                <span
                  class="h-[1.5px] w-7 shrink-0 rounded-full transition-colors duration-200
                         {s === 'attente'
                    ? 'bg-stone-200 dark:bg-stone-700'
                    : 'bg-emerald-400/70 dark:bg-emerald-600/70'}"
                ></span>
              {/if}
              <button
                type="button"
                title="{e.titre}"
                aria-current={s === "courante" ? "step" : undefined}
                class="group relative grid h-6 w-6 shrink-0 place-items-center rounded-full
                       transition-transform duration-150 hover:scale-125
                       focus-visible:outline-none focus-visible:ring-2
                       focus-visible:ring-emerald-500 focus-visible:ring-offset-1"
                onclick={() => aller(e)}
              >
                {#if s === "courante"}
                  <span
                    class="absolute h-6 w-6 rounded-full bg-emerald-500/15 dark:bg-emerald-400/20"
                  ></span>
                  <span
                    class="h-3 w-3 rounded-full bg-emerald-600 shadow-sm dark:bg-emerald-400"
                  ></span>
                {:else if s === "faite"}
                  <span
                    class="h-2.5 w-2.5 rounded-full bg-emerald-500/80 dark:bg-emerald-500/70"
                  ></span>
                {:else}
                  <span
                    class="h-2.5 w-2.5 rounded-full border-[1.5px] border-stone-300 bg-white transition-colors
                           group-hover:border-stone-400 dark:border-stone-600 dark:bg-stone-800"
                  ></span>
                {/if}
              </button>
            {/each}
          </div>
        </div>
      {/each}

      <button
        type="button"
        class="ml-auto rounded-md p-1 text-stone-400 transition hover:bg-stone-100
               hover:text-stone-600 dark:hover:bg-stone-700 dark:hover:text-stone-300"
        title={replie ? "Déplier le parcours" : "Replier le parcours"}
        onclick={() => (replie = !replie)}
      >
        {#if replie}
          <ChevronsUpDown class="h-4 w-4" />
        {:else}
          <ChevronsDownUp class="h-4 w-4" />
        {/if}
      </button>
    </div>

    {#if !replie}
      {#if etape}
        <div class="mt-3 flex items-start gap-5">
          <div class="min-w-0 flex-1">
            <div class="flex items-baseline gap-2.5">
              <span
                class="shrink-0 font-mono text-[11px] tabular-nums text-stone-400 dark:text-stone-500"
              >
                {String(rang + 1).padStart(2, "0")}<span class="opacity-50">/{ETAPES.length}</span>
              </span>
              <h2 class="truncate text-[15px] font-semibold text-stone-900 dark:text-stone-100">
                {etape.titre}
              </h2>
              {#if etape.ecran}
                <span
                  class="hidden shrink-0 rounded bg-stone-100 px-1.5 py-0.5 text-[11px]
                         text-stone-500 sm:inline dark:bg-stone-700/60 dark:text-stone-400"
                >
                  {etape.ecran}
                </span>
              {/if}
            </div>
            <!-- Le propos et le repère tiennent sur un même filet de texte :
                 séparés, ils faisaient trois blocs pour deux phrases. -->
            <p class="mt-0.5 max-w-4xl text-[12.5px] leading-snug text-stone-600 dark:text-stone-400">
              {etape.role}
              {#if etape.reperer}
                <span class="text-emerald-700 dark:text-emerald-500">
                  <Check class="mb-px inline h-3 w-3" />
                  {etape.reperer}
                </span>
              {/if}
            </p>
          </div>

          <div class="flex shrink-0 items-center gap-1">
            <button
              type="button"
              class="flex items-center gap-1 rounded-md px-2 py-1.5 text-[13px] text-stone-500
                     transition hover:bg-stone-100 hover:text-stone-800 disabled:opacity-30
                     disabled:hover:bg-transparent dark:hover:bg-stone-700 dark:hover:text-stone-200"
              disabled={rang <= 0}
              onclick={() => decaler(-1)}
            >
              <ChevronLeft class="h-4 w-4" />
              <span class="hidden md:inline">Précédent</span>
            </button>
            <button
              type="button"
              class="flex items-center gap-1 rounded-md px-2.5 py-1.5 text-[13px] font-medium
                     text-emerald-800 transition hover:bg-emerald-50 disabled:opacity-30
                     disabled:hover:bg-transparent dark:text-emerald-400 dark:hover:bg-emerald-900/30"
              disabled={rang < 0 || rang >= ETAPES.length - 1}
              onclick={() => decaler(1)}
            >
              <span class="hidden md:inline">Suivant</span>
              <ChevronRight class="h-4 w-4" />
            </button>
          </div>
        </div>
      {:else if prochaine}
        <!-- Hors parcours : on ne montre pas d'étape courante, seulement
             celle qui attend. Prétendre le contraire ferait mentir le rail. -->
        <div class="mt-3 flex items-center gap-3">
          <p class="text-[13px] text-stone-500 dark:text-stone-400">
            Prochaine étape du parcours :
          </p>
          <button
            type="button"
            class="flex items-center gap-1.5 rounded-md px-2.5 py-1 text-[13px] font-medium
                   text-emerald-800 transition hover:bg-emerald-50
                   dark:text-emerald-400 dark:hover:bg-emerald-900/30"
            onclick={() => aller(prochaine)}
          >
            {prochaine.titre}
            <ChevronRight class="h-4 w-4" />
          </button>
        </div>
      {/if}
    {/if}
  </div>
</section>
