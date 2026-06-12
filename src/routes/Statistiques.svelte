<script>
  import { onMount } from "svelte";
  import BarChart3 from "@lucide/svelte/icons/bar-chart-3";
  import Users from "@lucide/svelte/icons/users";
  import UserPlus from "@lucide/svelte/icons/user-plus";
  import LayoutGrid from "@lucide/svelte/icons/layout-grid";
  import { annees, statistiques } from "$lib/api.js";
  import BarChart from "$lib/components/BarChart.svelte";

  let snapshots = $state(/** @type {any[]} */ ([]));
  let anneeSelectionnee = $state("");
  let stats = $state(/** @type {null | any} */ (null));
  let chargement = $state(false);
  let erreur = $state("");

  onMount(async () => {
    try {
      snapshots = await annees.lister();
      if (snapshots.length >= 1) {
        anneeSelectionnee = snapshots[0].libelle;
        await charger();
      }
    } catch (e) {
      erreur = String(e);
    }
  });

  async function charger() {
    if (!anneeSelectionnee) return;
    chargement = true;
    erreur = "";
    try {
      stats = await statistiques.annee(anneeSelectionnee);
    } catch (e) {
      erreur = String(e);
    } finally {
      chargement = false;
    }
  }

  let pourcentageNouveaux = $derived.by(() => {
    if (!stats || !stats.total) return 0;
    return Math.round((stats.nouveaux / stats.total) * 100);
  });
</script>

<section class="space-y-5">
  <header class="flex items-end justify-between gap-4">
    <div>
      <h1 class="text-2xl font-semibold text-stone-900">Statistiques</h1>
      <p class="mt-1 text-sm text-stone-600">
        Vue analytique d'un snapshot : ventilation par établissement, niveau,
        classe et régime.
      </p>
    </div>
    <select
      bind:value={anneeSelectionnee}
      onchange={charger}
      class="rounded-lg border border-stone-300 px-3 py-2 text-sm focus:border-emerald-600 focus:outline-none focus:ring-1 focus:ring-emerald-600"
    >
      {#each snapshots as s (s.id)}
        <option value={s.libelle}>{s.libelle}</option>
      {/each}
    </select>
  </header>

  {#if erreur}
    <p class="rounded-lg bg-red-50 px-3 py-2 text-sm text-red-700">{erreur}</p>
  {/if}

  {#if chargement}
    <div class="card p-8 text-center text-stone-500">Chargement…</div>
  {:else if stats}
    <!-- KPIs en haut -->
    <div class="grid grid-cols-4 gap-3">
      <div class="card p-4">
        <div class="flex items-center gap-2 text-stone-700">
          <Users class="h-4 w-4 text-emerald-700" />
          <span class="text-xs font-semibold uppercase tracking-wide">Élèves total</span>
        </div>
        <p class="mt-1 text-2xl font-semibold tabular-nums text-stone-900">
          {stats.total.toLocaleString("fr-FR")}
        </p>
      </div>
      <div class="card p-4">
        <div class="flex items-center gap-2 text-stone-700">
          <UserPlus class="h-4 w-4 text-emerald-700" />
          <span class="text-xs font-semibold uppercase tracking-wide">Nouveaux</span>
        </div>
        <p class="mt-1 text-2xl font-semibold tabular-nums text-stone-900">
          {stats.nouveaux.toLocaleString("fr-FR")}
        </p>
        <p class="text-xs text-emerald-700">{pourcentageNouveaux}% de l'effectif</p>
      </div>
      <div class="card p-4">
        <div class="flex items-center gap-2 text-stone-700">
          <LayoutGrid class="h-4 w-4 text-sky-700" />
          <span class="text-xs font-semibold uppercase tracking-wide">Classes</span>
        </div>
        <p class="mt-1 text-2xl font-semibold tabular-nums text-stone-900">
          {stats.classes_distinctes}
        </p>
        <p class="text-xs text-stone-500">
          ~{(stats.total / Math.max(1, stats.classes_distinctes)).toFixed(0)} élèves / classe
        </p>
      </div>
      <div class="card p-4">
        <div class="flex items-center gap-2 text-stone-700">
          <BarChart3 class="h-4 w-4 text-amber-700" />
          <span class="text-xs font-semibold uppercase tracking-wide">Niveaux</span>
        </div>
        <p class="mt-1 text-2xl font-semibold tabular-nums text-stone-900">
          {stats.par_niveau.length}
        </p>
      </div>
    </div>

    <!-- Graphiques -->
    <div class="grid grid-cols-2 gap-4">
      <div class="card p-4">
        <h3 class="mb-3 text-sm font-semibold text-stone-700">
          Par établissement
        </h3>
        <BarChart donnees={stats.par_etablissement} couleur="bg-emerald-500" />
      </div>

      <div class="card p-4">
        <h3 class="mb-3 text-sm font-semibold text-stone-700">Par régime</h3>
        <BarChart donnees={stats.par_regime} couleur="bg-amber-500" />
      </div>

      <div class="card p-4">
        <h3 class="mb-3 text-sm font-semibold text-stone-700">Par niveau</h3>
        <BarChart donnees={stats.par_niveau} couleur="bg-sky-500" />
      </div>

      <div class="card p-4">
        <h3 class="mb-3 text-sm font-semibold text-stone-700">
          Par classe
          <span class="ml-1 text-xs font-normal text-stone-500">
            ({stats.par_classe.length})
          </span>
        </h3>
        <div class="max-h-96 overflow-y-auto pr-1">
          <BarChart donnees={stats.par_classe} couleur="bg-stone-500" />
        </div>
      </div>
    </div>
  {:else}
    <div class="card p-8 text-center text-stone-500">
      <BarChart3 class="mx-auto mb-3 h-10 w-10 text-stone-300" />
      <p>Aucun snapshot en base — va d'abord en importer un.</p>
    </div>
  {/if}
</section>
