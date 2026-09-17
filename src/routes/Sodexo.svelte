<script>
  import { onMount } from "svelte";
  import UtensilsCrossed from "@lucide/svelte/icons/utensils-crossed";
  import ExternalLink from "@lucide/svelte/icons/external-link";
  import AlertTriangle from "@lucide/svelte/icons/alert-triangle";
  import KeyRound from "@lucide/svelte/icons/key-round";
  import Settings from "@lucide/svelte/icons/settings";
  import CopiableTexte from "$lib/components/CopiableTexte.svelte";
  import EnTetePage from "$lib/components/EnTetePage.svelte";
  import Segments from "$lib/components/Segments.svelte";
  import { parametres } from "$lib/api.js";
  import {
    IDENTIFIANT_SODEXO,
    PORTAIL_SODEXO,
    PROCEDURES,
  } from "$lib/sodexo.js";

  /**
   * La procédure Sodexo, portée par le programme.
   *
   * ## Pourquoi le programme ne fabrique pas le fichier
   *
   * Le CSV d'import naît d'un classeur Google qui reçoit l'export
   * Charlemagne et le transforme. Refaire cette transformation sans l'avoir
   * lue produirait un fichier qui ressemble au bon sans en être un — et sur
   * de la restauration scolaire, l'erreur se découvre au self, un midi.
   *
   * Ce que le programme apporte : la procédure dans l'ordre, ses pièges, et
   * les liens qui évitent d'aller chercher les adresses ailleurs.
   *
   * @typedef {Object} Props
   * @property {(page: string) => void} [onNaviguer]
   */
  /** @type {Props} */
  let { onNaviguer } = $props();

  let idProcedure = $state(PROCEDURES[0].id);
  let reglages = $state(/** @type {Record<string, string>} */ ({}));

  let procedure = $derived(
    PROCEDURES.find((p) => p.id === idProcedure) ?? PROCEDURES[0],
  );

  onMount(async () => {
    try {
      const tous = await parametres.lister();
      reglages = Object.fromEntries(
        (tous ?? []).map((p) => [p.cle, p.valeur]),
      );
    } catch {
      // Sans les réglages, les liens vers les classeurs manquent — la
      // procédure reste lisible, c'est l'essentiel.
    }
  });

  /** L'adresse d'un classeur, quand elle a été déclarée. */
  function lien(l) {
    if (l.url) return l.url;
    const v = reglages[l.reglage];
    return typeof v === "string" && v.trim() ? v.trim() : null;
  }
</script>

<section class="space-y-5">
  <EnTetePage
    icon={UtensilsCrossed}
    titre="Sodexo"
    description="La procédure d'import, dans l'ordre, avec ses pièges. Le fichier se fabrique dans le classeur Google — le programme ne le refait pas, il t'y mène."
  />

  <Segments
    bind:valeur={idProcedure}
    options={PROCEDURES.map((p) => ({ id: p.id, label: p.titre }))}
  />

  <p class="max-w-3xl text-sm text-stone-600 dark:text-stone-300">{procedure.resume}</p>

  <!-- Les accès, sans le mot de passe. -->
  <div class="card flex flex-wrap items-center gap-x-6 gap-y-3 p-4">
    <div>
      <p class="libelle-champ">Portail</p>
      <a
        class="flex items-center gap-1.5 text-sm font-medium text-emerald-700 hover:underline dark:text-emerald-400"
        href={PORTAIL_SODEXO}
        target="_blank"
        rel="noreferrer"
      >
        <ExternalLink class="h-3.5 w-3.5" /> moneweb.fr
      </a>
    </div>
    <div>
      <p class="libelle-champ">Identifiant</p>
      <CopiableTexte valeur={IDENTIFIANT_SODEXO} />
    </div>
    <div class="flex items-start gap-2 text-xs text-stone-500 dark:text-stone-400">
      <KeyRound class="mt-0.5 h-3.5 w-3.5 shrink-0" />
      <p class="max-w-md">
        Le mot de passe n'est pas écrit ici, et c'est délibéré : il partirait
        dans le dépôt et y resterait. Surtout, il deviendrait
        <strong>faux</strong> — la note d'origine de cette procédure en portait
        deux, dont un périmé depuis un changement.
      </p>
    </div>
  </div>

  <!-- Les étapes -->
  <div class="flex flex-col gap-3">
    {#each procedure.etapes as etape, i (etape.titre)}
      <div class="card p-4">
        <h2 class="flex items-baseline gap-2 font-semibold">
          <span class="font-mono text-sm text-emerald-700 dark:text-emerald-400">
            {String(i + 1).padStart(2, "0")}
          </span>
          {etape.titre}
        </h2>

        <ol class="mt-2 flex flex-col gap-1.5">
          {#each etape.gestes as geste (geste)}
            <li class="flex gap-2 text-sm">
              <span class="mt-2 h-1 w-1 shrink-0 rounded-full bg-stone-400"></span>
              <span class="text-stone-700 dark:text-stone-200">{geste}</span>
            </li>
          {/each}
        </ol>

        {#if etape.liens?.length}
          <div class="mt-3 flex flex-wrap gap-2">
            {#each etape.liens as l (l.libelle)}
              {@const url = lien(l)}
              {#if url}
                <a
                  class="btn-secondary !py-1.5 text-xs"
                  href={url}
                  target="_blank"
                  rel="noreferrer"
                >
                  <ExternalLink class="h-3.5 w-3.5" />
                  {l.libelle}
                </a>
              {:else}
                <button
                  class="flex items-center gap-1.5 rounded-lg border border-dashed border-stone-300 px-3 py-1.5 text-xs text-stone-500 transition hover:border-emerald-400 dark:border-stone-600 dark:text-stone-400"
                  onclick={() => onNaviguer?.("parametres")}
                >
                  <Settings class="h-3.5 w-3.5" />
                  {l.libelle} — déclarer son adresse
                </button>
              {/if}
            {/each}
          </div>
        {/if}

        {#if etape.pieges?.length}
          <div class="mt-3 rounded-lg border-l-4 border-l-amber-500 bg-amber-50 p-3 dark:bg-amber-900/25">
            <p class="flex items-center gap-1.5 text-[11px] font-semibold uppercase tracking-wide text-amber-800 dark:text-amber-300">
              <AlertTriangle class="h-3.5 w-3.5" /> Ce qui peut mal tourner
            </p>
            <ul class="mt-1.5 flex flex-col gap-1.5">
              {#each etape.pieges as piege (piege)}
                <li class="text-sm leading-relaxed text-amber-900 dark:text-amber-200">
                  {piege}
                </li>
              {/each}
            </ul>
          </div>
        {/if}
      </div>
    {/each}
  </div>

  <!-- Le format attendu : à relire quand le portail refuse. -->
  <div class="card p-4">
    <h2 class="titre-section mb-2">Le format que le portail attend</h2>
    <p class="mb-2 text-xs text-stone-500 dark:text-stone-400">
      À relire d'abord quand un import est refusé : neuf fois sur dix, c'est
      une colonne ou un séparateur.
    </p>
    <ul class="flex flex-col gap-1 text-sm">
      {#each procedure.memo as ligne (ligne)}
        <li class="flex gap-2">
          <span class="mt-2 h-1 w-1 shrink-0 rounded-full bg-stone-400"></span>
          <span class="text-stone-700 dark:text-stone-200">{ligne}</span>
        </li>
      {/each}
    </ul>
  </div>
</section>
