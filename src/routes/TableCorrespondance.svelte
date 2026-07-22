<script>
  import { onMount } from "svelte";
  import Table from "@lucide/svelte/icons/table";
  import { tableCorrespondance, sites as sitesApi } from "$lib/api.js";

  let liste = $state([]);
  let sites = $state([]);
  let filtreSite = $state("");
  let chargement = $state(true);
  let erreur = $state("");

  let filtree = $derived(
    filtreSite ? liste.filter((l) => l.site_nom === filtreSite) : liste,
  );

  onMount(async () => {
    try {
      const [l, s] = await Promise.all([tableCorrespondance.lister(), sitesApi.lister()]);
      liste = l;
      sites = s;
    } catch (e) {
      erreur = String(e);
    } finally {
      chargement = false;
    }
  });
</script>

<section class="space-y-4">
  <header>
    <h1 class="text-2xl font-semibold text-stone-900 dark:text-stone-100">
      Table de correspondance
    </h1>
    <p class="mt-1 text-sm text-stone-600 dark:text-stone-400">
      Fait le pont entre les codes classe Charlemagne et les cibles : unité d'organisation
      Google (pré-rentrée + définitive) et adresses des groupes Google. Une classe absente est
      un cas bloquant à l'ingestion — le programme refuse plutôt que d'affecter par défaut.
    </p>
  </header>

  {#if erreur}
    <p class="rounded-lg bg-red-50 px-3 py-2 text-sm text-red-700 dark:bg-red-900/30 dark:text-red-300">{erreur}</p>
  {/if}

  {#if sites.length > 0}
    <div class="card p-3">
      <div class="flex flex-wrap items-center gap-2">
        <button
          class="rounded-full border px-3 py-0.5 text-xs font-medium
                 {!filtreSite ? 'border-emerald-600 bg-emerald-50 text-emerald-800 dark:bg-emerald-900/30 dark:text-emerald-300' : 'border-stone-200 bg-white text-stone-600 dark:border-stone-600 dark:bg-stone-800 dark:text-stone-400'}"
          onclick={() => (filtreSite = "")}
        >
          Tous
        </button>
        {#each sites as s (s.id)}
          <button
            class="rounded-full border px-3 py-0.5 text-xs font-medium
                   {filtreSite === s.nom ? 'border-emerald-600 bg-emerald-50 text-emerald-800 dark:bg-emerald-900/30 dark:text-emerald-300' : 'border-stone-200 bg-white text-stone-600 dark:border-stone-600 dark:bg-stone-800 dark:text-stone-400'}"
            onclick={() => (filtreSite = s.nom)}
          >
            {s.nom}
          </button>
        {/each}
        <span class="ml-auto text-xs text-stone-500 dark:text-stone-400 tabular-nums">
          {filtree.length} / {liste.length}
        </span>
      </div>
    </div>
  {/if}

  <div class="card overflow-hidden">
    {#if chargement}
      <div class="p-8 text-center text-stone-500 dark:text-stone-400">Chargement…</div>
    {:else if liste.length === 0}
      <div class="p-8 text-center text-stone-500 dark:text-stone-400">
        <Table class="mx-auto mb-3 h-10 w-10 text-stone-300 dark:text-stone-600" />
        <p>Table vide.</p>
        <p class="mt-1 text-xs">
          L'import automatique depuis l'onglet <code>Table</code> du classeur historique
          arrivera au Lot 6.
        </p>
      </div>
    {:else}
      <div class="max-h-[640px] overflow-auto">
        <table class="w-full text-sm">
          <thead class="sticky top-0 z-10 bg-stone-100 text-stone-700 dark:bg-stone-800 dark:text-stone-300">
            <tr>
              <th class="border-b border-stone-200 px-3 py-2 text-left font-semibold dark:border-stone-700">Site</th>
              <th class="border-b border-stone-200 px-3 py-2 text-left font-semibold dark:border-stone-700">Classe Charlemagne</th>
              <th class="border-b border-stone-200 px-3 py-2 text-left font-semibold dark:border-stone-700">Code court</th>
              <th class="border-b border-stone-200 px-3 py-2 text-left font-semibold dark:border-stone-700">Groupe Google</th>
              <th class="border-b border-stone-200 px-3 py-2 text-left font-semibold dark:border-stone-700">OU pré-rentrée</th>
              <th class="border-b border-stone-200 px-3 py-2 text-left font-semibold dark:border-stone-700">OU définitive</th>
            </tr>
          </thead>
          <tbody>
            {#each filtree as l (l.id)}
              <tr class="border-b border-stone-100 dark:border-stone-800 hover:bg-emerald-50/40 dark:hover:bg-emerald-900/20">
                <td class="px-3 py-1.5 font-medium">{l.site_nom}</td>
                <td class="px-3 py-1.5 text-stone-700 dark:text-stone-300">{l.classe_charlemagne_long}</td>
                <td class="px-3 py-1.5 font-mono text-xs">{l.classe_code_court}</td>
                <td class="px-3 py-1.5 font-mono text-xs text-stone-600 dark:text-stone-400">{l.groupe_google ?? "—"}</td>
                <td class="px-3 py-1.5 font-mono text-xs text-stone-600 dark:text-stone-400">{l.ou_pre_rentree}</td>
                <td class="px-3 py-1.5 font-mono text-xs text-stone-600 dark:text-stone-400">{l.ou_definitive}</td>
              </tr>
            {/each}
          </tbody>
        </table>
      </div>
    {/if}
  </div>
</section>
