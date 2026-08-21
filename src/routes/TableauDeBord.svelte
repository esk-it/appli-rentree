<script>
  import { onMount } from "svelte";
  import Users2 from "@lucide/svelte/icons/users-2";
  import Building2 from "@lucide/svelte/icons/building-2";
  import Database from "@lucide/svelte/icons/database";
  import Scale from "@lucide/svelte/icons/scale";
  import CheckCircle2 from "@lucide/svelte/icons/check-circle-2";
  import Circle from "@lucide/svelte/icons/circle";
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

  /**
   * Le parcours de la rentrée, dans l'ordre où il doit être suivi.
   * Chaque étape sait dire si elle est faite, à partir de l'état réel du
   * référentiel — pas d'une case cochée manuellement.
   */
  let etapes = $derived.by(() => {
    const nbSites = ref?.nb_sites ?? 0;
    const nbClasses = ref?.nb_classes_table ?? 0;
    const nbPersonnes = ref?.nb_personnes_total ?? 0;
    const nbAnnees = listeAnnees.length;
    const nbArbitrages = ref?.nb_arbitrages_en_attente ?? 0;

    return [
      {
        id: "sites",
        titre: "Déclarer les sites",
        detail: "NDE, NDK, SU — avec leur domaine de messagerie",
        faite: nbSites > 0,
        page: "sites",
      },
      {
        id: "table",
        titre: "Remplir la table de correspondance",
        detail:
          nbClasses > 0
            ? `${nbClasses} classe(s) déclarée(s)`
            : "Import du classeur historique : classes → OU et groupes Google",
        // Faite = des classes existent ET aucune classe constatée n'échappe
        // à la table. Les deux conditions sont nécessaires : la seconde est
        // trivialement vraie tant qu'aucun snapshot n'a été ingéré.
        faite:
          nbClasses > 0 &&
          !(anomalies?.anomalies ?? []).some((a) => a.type === "classe_hors_table"),
        page: "table_correspondance",
      },
      {
        id: "amorcage",
        titre: "Amorcer depuis KoXo",
        detail: "Récupère les logins existants pour ne jamais les régénérer",
        faite: nbPersonnes > 0,
        page: "amorcage",
      },
      {
        id: "ingestion",
        titre: "Ingérer l'export Charlemagne",
        detail: "Crée les snapshots de l'année",
        faite: nbAnnees > 0,
        page: "snapshots",
      },
      {
        id: "arbitrage",
        titre: "Trancher les cas ambigus",
        detail:
          nbArbitrages > 0
            ? `${nbArbitrages} décision(s) en attente`
            : "Collisions de login et homonymies",
        faite: nbAnnees > 0 && nbArbitrages === 0,
        page: "arbitrage",
      },
      {
        id: "simulation",
        titre: "Relire la simulation",
        detail: "Ce que le programme ferait, toutes cibles confondues",
        faite: false,
        page: "simulation",
      },
      {
        id: "exports",
        titre: "Générer les exports",
        detail: "KoXo, Google, PMB, JPM, CardStudio",
        faite: false,
        page: "exports",
      },
    ];
  });

  /**
   * La bascule Google, dans l'ordre où elle doit être menée.
   *
   * Ces étapes ne se déduisent pas de l'état du référentiel : elles se
   * constatent dans Google, et chaque écran le dit à sa manière. Les
   * afficher comme des cases à cocher qui ne se cochent jamais serait
   * décourageant et faux — ce sont des actions ordonnées, pas des états.
   *
   * L'ordre compte : renommer un arbre avant de l'avoir vidé emporterait
   * ses comptes, et vérifier la conformité avant d'avoir tourné la Table
   * mesurerait l'écart avec la mauvaise année.
   */
  const bascule = [
    {
      id: "b-vider",
      titre: "Vider les arbres de l'année révolue",
      detail: "Sortants → les comptes rejoignent leur OU de sortie, sans être suspendus",
      page: "sortants",
    },
    {
      id: "b-table",
      titre: "Tourner la Table de correspondance",
      detail: "Les chemins d'OU doivent viser la rentrée préparée",
      page: "table_correspondance",
    },
    {
      id: "b-ou",
      titre: "Renommer et créer les unités d'organisation",
      detail: "Conformité Google → Arborescence. Google refuse un déplacement vers une OU absente",
      page: "conformite_google",
    },
    {
      id: "b-adresses",
      titre: "Corriger les adresses divergentes",
      detail: "Conformité Google → Adresses. Sans quoi l'export crée un doublon",
      page: "conformite_google",
    },
    {
      id: "b-comptes",
      titre: "Créer les comptes des nouveaux",
      detail: "Exports → KoXo d'abord, qui génère les mots de passe, puis Google",
      page: "exports",
    },
    {
      id: "b-bascule",
      titre: "Basculer les élèves dans leurs classes",
      detail: "Bascule des OU, en deux phases",
      page: "bascule",
    },
    {
      id: "b-groupes",
      titre: "Créer puis synchroniser les groupes",
      detail: "Conformité Google → Groupes",
      page: "conformite_google",
    },
    {
      id: "b-chromebooks",
      titre: "Faire le point sur les Chromebooks",
      detail: "À réclamer aux partants, à attribuer aux arrivants",
      page: "chromebooks",
    },
  ];

  let prochaineEtape = $derived(etapes.find((e) => !e.faite));
  let nbFaites = $derived(etapes.filter((e) => e.faite).length);

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

    <!-- Parcours guidé -->
    <div class="card p-5">
      <div class="mb-4 flex items-center justify-between gap-3">
        <h2 class="titre-section">Parcours de la rentrée</h2>
        <span class="text-xs tabular-nums text-stone-500 dark:text-stone-400">
          {nbFaites} / {etapes.length}
        </span>
      </div>

      <!-- Barre de progression -->
      <div class="mb-5 h-1.5 overflow-hidden rounded-full bg-stone-200 dark:bg-stone-700">
        <div
          class="h-full rounded-full bg-emerald-600 transition-all duration-500 dark:bg-emerald-500"
          style="width: {(nbFaites / etapes.length) * 100}%"
        ></div>
      </div>

      <p class="mb-2 text-xs font-medium uppercase tracking-wide text-stone-400 dark:text-stone-500">
        Préparer les données
      </p>
      <ol class="space-y-1">
        {#each etapes as etape, i (etape.id)}
          {@const estProchaine = prochaineEtape?.id === etape.id}
          <li>
            <button
              class="group flex w-full items-start gap-3 rounded-lg p-2.5 text-left transition-colors duration-150
                     {estProchaine
                       ? 'bg-emerald-50 ring-1 ring-emerald-200 dark:bg-emerald-900/20 dark:ring-emerald-800'
                       : 'hover:bg-stone-50 dark:hover:bg-stone-700/40'}"
              onclick={() => aller(etape.page)}
            >
              {#if etape.faite}
                <CheckCircle2 class="mt-0.5 h-5 w-5 shrink-0 text-emerald-600 dark:text-emerald-400" />
              {:else}
                <Circle
                  class="mt-0.5 h-5 w-5 shrink-0 {estProchaine
                    ? 'text-emerald-600 dark:text-emerald-400'
                    : 'text-stone-300 dark:text-stone-600'}"
                />
              {/if}
              <div class="min-w-0 flex-1">
                <p
                  class="text-sm font-medium {etape.faite
                    ? 'text-stone-500 line-through decoration-stone-300 dark:text-stone-500'
                    : 'text-stone-900 dark:text-stone-100'}"
                >
                  {i + 1}. {etape.titre}
                </p>
                <p class="text-xs text-stone-500 dark:text-stone-400">{etape.detail}</p>
              </div>
              {#if estProchaine}
                <span class="badge-nouveau shrink-0">à faire</span>
              {/if}
              <ArrowRight
                class="mt-0.5 h-4 w-4 shrink-0 text-stone-300 transition-transform duration-150 group-hover:translate-x-0.5 group-hover:text-stone-500 dark:text-stone-600"
              />
            </button>
          </li>
        {/each}
      </ol>

      <p class="mb-2 mt-5 border-t border-stone-200 pt-4 text-xs font-medium uppercase tracking-wide text-stone-400 dark:border-stone-700 dark:text-stone-500">
        Basculer dans Google
      </p>
      <p class="mb-3 max-w-2xl text-xs text-stone-500 dark:text-stone-400">
        Ces opérations se constatent dans Google, pas dans le référentiel : chaque
        écran dit où il en est. L'ordre, lui, n'est pas indifférent — renommer un
        arbre avant de l'avoir vidé emporterait ses comptes.
      </p>
      <ol class="space-y-1">
        {#each bascule as etape, i (etape.id)}
          <li>
            <button
              class="group flex w-full items-start gap-3 rounded-lg p-2.5 text-left transition-colors duration-150 hover:bg-stone-50 dark:hover:bg-stone-700/40"
              onclick={() => aller(etape.page)}
            >
              <span
                class="mt-0.5 grid h-5 w-5 shrink-0 place-items-center rounded-full border border-stone-300 font-mono text-[10px] tabular-nums text-stone-500 dark:border-stone-600 dark:text-stone-400"
              >
                {i + 1}
              </span>
              <div class="min-w-0 flex-1">
                <p class="text-sm font-medium text-stone-900 dark:text-stone-100">
                  {etape.titre}
                </p>
                <p class="text-xs text-stone-500 dark:text-stone-400">{etape.detail}</p>
              </div>
              <ArrowRight
                class="mt-0.5 h-4 w-4 shrink-0 text-stone-300 transition-transform duration-150 group-hover:translate-x-0.5 group-hover:text-stone-500 dark:text-stone-600"
              />
            </button>
          </li>
        {/each}
      </ol>
    </div>
  {/if}
</section>
