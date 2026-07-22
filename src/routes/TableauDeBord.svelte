<script>
  import Construction from "@lucide/svelte/icons/construction";
  import { onMount } from "svelte";
  import { sites as sitesApi, personnes } from "$lib/api.js";

  let sites = $state([]);
  let nbPersonnes = $state(0);

  onMount(async () => {
    try {
      sites = await sitesApi.lister();
      nbPersonnes = (await personnes.lister()).length;
    } catch {}
  });
</script>

<section class="space-y-5">
  <header>
    <h1 class="text-2xl font-semibold text-stone-900 dark:text-stone-100">Tableau de bord</h1>
    <p class="mt-1 text-sm text-stone-600 dark:text-stone-400">
      Sera reconstruit au Lot 13 avec le parcours guidé complet (Charlemagne → Réconciliation
      → Arbitrage → Simulation → Validation → KoXo → Google → PMB / JPM / CardStudio).
    </p>
  </header>

  <div class="card border-amber-200 bg-amber-50/50 p-4 text-sm dark:border-amber-800 dark:bg-amber-900/20">
    <div class="flex items-start gap-3">
      <Construction class="mt-0.5 h-5 w-5 text-amber-700 dark:text-amber-400" />
      <div>
        <p class="font-medium text-amber-900 dark:text-amber-200">Refonte en cours</p>
        <p class="mt-1 text-stone-700 dark:text-stone-300">
          v0.22.0 pose les fondations d'identité (Personne / Snapshot / CompteCible). Les
          modules de traitement seront ajoutés lot par lot (v0.23 → v0.34).
        </p>
      </div>
    </div>
  </div>

  <div class="grid grid-cols-3 gap-3">
    <div class="card p-4">
      <p class="text-xs font-semibold uppercase tracking-wide text-stone-600 dark:text-stone-400">
        Personnes au référentiel
      </p>
      <p class="mt-1 text-2xl font-semibold tabular-nums">{nbPersonnes}</p>
    </div>
    <div class="card p-4">
      <p class="text-xs font-semibold uppercase tracking-wide text-stone-600 dark:text-stone-400">
        Sites configurés
      </p>
      <p class="mt-1 text-2xl font-semibold tabular-nums">{sites.length}</p>
      <p class="text-xs text-stone-500 dark:text-stone-400">
        {sites.map((s) => s.nom).join(" · ") || "aucun"}
      </p>
    </div>
    <div class="card p-4">
      <p class="text-xs font-semibold uppercase tracking-wide text-stone-600 dark:text-stone-400">
        Version
      </p>
      <p class="mt-1 text-2xl font-semibold tabular-nums">0.22.0</p>
      <p class="text-xs text-stone-500 dark:text-stone-400">Lot 1 — Fondations identité</p>
    </div>
  </div>
</section>
