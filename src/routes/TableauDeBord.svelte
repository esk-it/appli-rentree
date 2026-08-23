<script>
  import { onMount } from "svelte";
  import Users2 from "@lucide/svelte/icons/users-2";
  import Building2 from "@lucide/svelte/icons/building-2";
  import Database from "@lucide/svelte/icons/database";
  import Scale from "@lucide/svelte/icons/scale";
  import ShieldAlert from "@lucide/svelte/icons/shield-alert";
  import ArrowRight from "@lucide/svelte/icons/arrow-right";
  import StatCard from "$lib/components/StatCard.svelte";
  import Squelette from "$lib/components/Squelette.svelte";
  import { annees, statistiques } from "$lib/api.js";

  let { onNaviguer = null } = $props();

  let ref = $state(/** @type {null | any} */ (null));
  let listeAnnees = $state([]);
  let anomalies = $state(/** @type {null | any} */ (null));
  let chargement = $state(true);

  onMount(async () => {
    try {
      [ref, listeAnnees, anomalies] = await Promise.all([
        statistiques.referentiel(),
        annees.lister(),
        statistiques.anomalies(),
      ]);
    } catch {
      // Le backend démarre peut-être encore — les cartes restent à zéro.
    } finally {
      chargement = false;
    }
  });


  let bloquants = $derived(
    (anomalies?.anomalies ?? []).filter((a) => a.gravite === "bloquant"),
  );

  function aller(page) {
    if (onNaviguer) onNaviguer(page);
  }
</script>

<section class="space-y-5">
  <header>
    <h1 class="text-2xl font-semibold text-stone-900 dark:text-stone-100">
      Tableau de bord
    </h1>
    <p class="mt-1 text-sm text-stone-600 dark:text-stone-400">
      Où en est la préparation de la rentrée.
    </p>
  </header>

  {#if chargement}
    <Squelette variante="carte" nb={4} />
  {:else}
    <!-- Chiffres clés -->
    <div class="anim-cascade grid grid-cols-2 gap-3 md:grid-cols-4">
      <StatCard
        label="Personnes"
        value={ref?.nb_personnes_total ?? 0}
        icon={Users2}
        hint="{ref?.nb_eleves_total ?? 0} élèves · {ref?.nb_adultes_total ?? 0} adultes"
      />
      <StatCard
        label="Sites"
        value={ref?.nb_sites ?? 0}
        icon={Building2}
        variante={(ref?.nb_sites ?? 0) > 0 ? "default" : "warning"}
      />
      <StatCard
        label="Années ingérées"
        value={listeAnnees.length}
        icon={Database}
        hint={listeAnnees.map((a) => a.libelle).join(" · ") || "aucune"}
      />
      <StatCard
        label="Arbitrages"
        value={ref?.nb_arbitrages_en_attente ?? 0}
        icon={Scale}
        variante={(ref?.nb_arbitrages_en_attente ?? 0) > 0 ? "warning" : "success"}
        hint="en attente de décision"
      />
    </div>

    <!-- Blocages éventuels, en tête car ils conditionnent la suite -->
    {#if bloquants.length > 0}
      <div class="card anim-apparition border-red-200 bg-red-50/60 p-4 dark:border-red-800 dark:bg-red-900/20">
        <div class="flex items-start gap-3">
          <ShieldAlert class="mt-0.5 h-5 w-5 shrink-0 text-red-600 dark:text-red-400" />
          <div class="flex-1">
            <p class="font-medium text-red-900 dark:text-red-200">
              {bloquants.length} point(s) bloquant(s)
            </p>
            <ul class="mt-1.5 space-y-1 text-sm text-stone-700 dark:text-stone-300">
              {#each bloquants as b (b.type)}
                <li>• {b.libelle}</li>
              {/each}
            </ul>
            <button class="btn-secondary mt-3 text-xs" onclick={() => aller("statistiques")}>
              Voir le détail
              <ArrowRight class="h-3.5 w-3.5" />
            </button>
          </div>
        </div>
      </div>
    {/if}

  {/if}
</section>
