<script>
  import { onMount } from "svelte";
  import BarChart3 from "@lucide/svelte/icons/bar-chart-3";
  import Users2 from "@lucide/svelte/icons/users-2";
  import Building2 from "@lucide/svelte/icons/building-2";
  import Scale from "@lucide/svelte/icons/scale";
  import { annees, statistiques } from "$lib/api.js";

  let ref = $state(/** @type {null | any} */ (null));
  let listeAnnees = $state([]);
  let anneeChoisie = $state(/** @type {null | number} */ (null));
  let statsAnnee = $state(/** @type {null | any} */ (null));
  let erreur = $state("");

  onMount(async () => {
    try {
      [ref, listeAnnees] = await Promise.all([statistiques.referentiel(), annees.lister()]);
      if (listeAnnees.length > 0) {
        anneeChoisie = listeAnnees[0].id;
        await chargerAnnee();
      }
    } catch (e) {
      erreur = String(e);
    }
  });

  async function chargerAnnee() {
    if (!anneeChoisie) return;
    try {
      statsAnnee = await statistiques.annee(anneeChoisie);
    } catch (e) {
      erreur = String(e);
    }
  }

  function maxValeur(liste) {
    return Math.max(1, ...liste.map((v) => v.valeur));
  }
</script>

<section class="space-y-5">
  <header>
    <h1 class="text-2xl font-semibold text-stone-900 dark:text-stone-100">
      Statistiques
    </h1>
    <p class="mt-1 text-sm text-stone-600 dark:text-stone-400">
      Vue instantanée du référentiel et des effectifs par année.
    </p>
  </header>

  {#if erreur}
    <p class="rounded-lg bg-red-50 px-3 py-2 text-sm text-red-700 dark:bg-red-900/30 dark:text-red-300">
      {erreur}
    </p>
  {/if}

  {#if ref}
    <!-- Cards top -->
    <div class="grid grid-cols-2 gap-3 md:grid-cols-4">
      <div class="card p-4">
        <div class="flex items-center gap-3">
          <div class="rounded-lg bg-emerald-100 p-2 dark:bg-emerald-900/40">
            <Users2 class="h-5 w-5 text-emerald-700 dark:text-emerald-300" />
          </div>
          <div>
            <p class="text-xs uppercase tracking-wide text-stone-500">Personnes</p>
            <p class="text-2xl font-semibold tabular-nums">{ref.nb_personnes_total}</p>
            <p class="text-xs text-stone-500">
              {ref.nb_eleves_total} él. · {ref.nb_adultes_total} ad.
            </p>
          </div>
        </div>
      </div>
      <div class="card p-4">
        <div class="flex items-center gap-3">
          <div class="rounded-lg bg-sky-100 p-2 dark:bg-sky-900/40">
            <Building2 class="h-5 w-5 text-sky-700 dark:text-sky-300" />
          </div>
          <div>
            <p class="text-xs uppercase tracking-wide text-stone-500">Sites</p>
            <p class="text-2xl font-semibold tabular-nums">{ref.nb_sites}</p>
          </div>
        </div>
      </div>
      <div class="card p-4">
        <div class="flex items-center gap-3">
          <div class="rounded-lg bg-stone-100 p-2 dark:bg-stone-800">
            <BarChart3 class="h-5 w-5 text-stone-700 dark:text-stone-300" />
          </div>
          <div>
            <p class="text-xs uppercase tracking-wide text-stone-500">Années</p>
            <p class="text-2xl font-semibold tabular-nums">{ref.nb_annees_scolaires}</p>
          </div>
        </div>
      </div>
      <div class="card p-4">
        <div class="flex items-center gap-3">
          <div class="rounded-lg bg-amber-100 p-2 dark:bg-amber-900/40">
            <Scale class="h-5 w-5 text-amber-700 dark:text-amber-300" />
          </div>
          <div>
            <p class="text-xs uppercase tracking-wide text-stone-500">Arbitrages</p>
            <p class="text-2xl font-semibold tabular-nums">
              {ref.nb_arbitrages_en_attente}
              <span class="text-sm text-stone-400">/ {ref.nb_arbitrages_en_attente + ref.nb_arbitrages_tranches}</span>
            </p>
            <p class="text-xs text-stone-500">en attente / total</p>
          </div>
        </div>
      </div>
    </div>
  {/if}

  {#if listeAnnees.length > 0}
    <div class="card p-4 space-y-3">
      <div class="flex items-center justify-between gap-3">
        <h2 class="text-lg font-semibold">Détail par année</h2>
        <select
          bind:value={anneeChoisie}
          onchange={chargerAnnee}
          class="rounded-lg border border-stone-300 px-3 py-1 text-sm dark:border-stone-600 dark:bg-stone-800"
        >
          {#each listeAnnees as a (a.id)}
            <option value={a.id}>{a.libelle}</option>
          {/each}
        </select>
      </div>

      {#if statsAnnee}
        <div class="grid grid-cols-1 gap-4 md:grid-cols-2">
          <div>
            <p class="text-sm font-semibold text-stone-700 dark:text-stone-300 mb-2">
              {statsAnnee.nb_personnes} personne(s)
              — {statsAnnee.nb_eleves} él., {statsAnnee.nb_adultes} ad.
            </p>

            <h3 class="text-xs uppercase tracking-wide text-stone-500 mt-3 mb-1">Par site</h3>
            {#each statsAnnee.par_site as v (v.label)}
              {@const max = maxValeur(statsAnnee.par_site)}
              <div class="flex items-center gap-2 py-0.5 text-sm">
                <span class="w-24 text-stone-600 dark:text-stone-400">{v.label}</span>
                <div class="flex-1 rounded-full bg-stone-100 dark:bg-stone-800 overflow-hidden">
                  <div class="h-4 rounded-full bg-emerald-500" style="width: {(v.valeur / max) * 100}%"></div>
                </div>
                <span class="w-10 text-right tabular-nums font-medium">{v.valeur}</span>
              </div>
            {/each}
          </div>

          <div>
            <h3 class="text-xs uppercase tracking-wide text-stone-500 mt-3 mb-1">Par régime</h3>
            {#each statsAnnee.par_regime as v (v.label)}
              {@const max = maxValeur(statsAnnee.par_regime)}
              <div class="flex items-center gap-2 py-0.5 text-sm">
                <span class="w-24 text-stone-600 dark:text-stone-400">{v.label}</span>
                <div class="flex-1 rounded-full bg-stone-100 dark:bg-stone-800 overflow-hidden">
                  <div class="h-4 rounded-full bg-sky-500" style="width: {(v.valeur / max) * 100}%"></div>
                </div>
                <span class="w-10 text-right tabular-nums font-medium">{v.valeur}</span>
              </div>
            {/each}
          </div>
        </div>

        {#if statsAnnee.par_niveau.length > 0}
          <div class="mt-4">
            <h3 class="text-xs uppercase tracking-wide text-stone-500 mb-1">Par niveau</h3>
            <div class="grid grid-cols-2 gap-1 md:grid-cols-4">
              {#each statsAnnee.par_niveau as v (v.label)}
                <div class="rounded-lg border border-stone-200 bg-stone-50 p-2 text-sm dark:border-stone-700 dark:bg-stone-800">
                  <span class="font-mono text-xs text-stone-500">{v.label}</span>
                  <span class="ml-2 font-semibold tabular-nums">{v.valeur}</span>
                </div>
              {/each}
            </div>
          </div>
        {/if}
      {/if}
    </div>
  {/if}
</section>
