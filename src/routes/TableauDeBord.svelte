<script>
  import { onMount } from "svelte";
  import Users2 from "@lucide/svelte/icons/users-2";
  import Building2 from "@lucide/svelte/icons/building-2";
  import Database from "@lucide/svelte/icons/database";
  import Scale from "@lucide/svelte/icons/scale";
  import ShieldAlert from "@lucide/svelte/icons/shield-alert";
  import ArrowRight from "@lucide/svelte/icons/arrow-right";
  import Cloud from "@lucide/svelte/icons/cloud";
  import StatCard from "$lib/components/StatCard.svelte";
  import Squelette from "$lib/components/Squelette.svelte";
  import Bouton from "$lib/components/Bouton.svelte";
  import { annees, parcoursApi, statistiques } from "$lib/api.js";
  import { PHASES, etapesDe } from "$lib/parcours.js";
  import { notify } from "$lib/toasts.js";

  let { onNaviguer = null } = $props();

  let ref = $state(/** @type {null | any} */ (null));
  let listeAnnees = $state([]);
  let anomalies = $state(/** @type {null | any} */ (null));
  let chargement = $state(true);

  /**
   * L'état de chaque étape du parcours.
   *
   * L'écran annonçait « où en est la préparation de la rentrée » et
   * montrait quatre compteurs qui ne répondaient pas à la question. Les
   * étapes, elles, y répondent — et depuis que le backend sait les lire,
   * il n'y a plus de raison de les taire.
   */
  let etats = $state(/** @type {Record<string, any>} */ ({}));
  let anneeCourante = $state(/** @type {any} */ (null));
  let interrogationGoogle = $state(false);

  onMount(async () => {
    try {
      [ref, listeAnnees, anomalies] = await Promise.all([
        statistiques.referentiel(),
        annees.lister(),
        statistiques.anomalies(),
      ]);
      await relireParcours();
    } catch {
      // Le backend démarre peut-être encore — les cartes restent à zéro.
    } finally {
      chargement = false;
    }
  });

  async function relireParcours() {
    if (!listeAnnees.length) return;
    // Les libellés `AAAA-AAAA` s'ordonnent alphabétiquement.
    anneeCourante = [...listeAnnees]
      .sort((a, b) => a.libelle.localeCompare(b.libelle))
      .at(-1);
    const r = await parcoursApi.avancement(anneeCourante.id);
    etats = Object.fromEntries(r.etapes.map((e) => [e.id, e]));
  }

  /**
   * Les cinq étapes que seul Google peut trancher.
   *
   * Plusieurs appels réseau : c'est un geste qu'on demande, jamais un
   * effet de bord de l'affichage.
   */
  async function interrogerGoogle() {
    if (!anneeCourante) return;
    interrogationGoogle = true;
    try {
      const r = await parcoursApi.avancementGoogle({ anneeId: anneeCourante.id });
      etats = Object.fromEntries(r.etapes.map((e) => [e.id, e]));
      notify.succes(`${r.nb_faites} étape(s) faites sur ${r.etapes.length}`);
    } catch (e) {
      notify.erreur(String(e).replace(/^Error:\s*/, ""));
    } finally {
      interrogationGoogle = false;
    }
  }

  let nbFaites = $derived(
    Object.values(etats).filter((e) => e.etat === "faite").length,
  );
  let nbEtapes = $derived(Object.keys(etats).length);
  let nbInconnues = $derived(
    Object.values(etats).filter((e) => e.etat === "inconnu").length,
  );


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
    <!-- Le parcours d'abord : c'est la question que le titre pose, et les
         compteurs n'y répondaient pas. -->
    {#if nbEtapes > 0}
      <div class="card anim-apparition p-4">
        <div class="flex flex-wrap items-baseline justify-between gap-2">
          <p class="text-sm">
            <strong class="text-lg text-emerald-700 dark:text-emerald-400">
              {nbFaites}
            </strong>
            <span class="text-stone-600 dark:text-stone-400">
              étape(s) faites sur {nbEtapes}
              {#if anneeCourante}· {anneeCourante.libelle}{/if}
            </span>
          </p>
          {#if nbInconnues > 0}
            <Bouton
              taille="sm"
              icon={Cloud}
              occupe={interrogationGoogle}
              onclick={interrogerGoogle}
            >
              Interroger Google ({nbInconnues})
            </Bouton>
          {/if}
        </div>

        <!-- La barre porte les trois états dans leur ordre réel : ce qui est
             fait, ce qui reste, ce qu'on n'a pas regardé. -->
        <div class="mt-3 flex h-1.5 overflow-hidden rounded-full bg-stone-200 dark:bg-stone-700">
          <div class="bg-emerald-600 dark:bg-emerald-500"
               style="width: {(nbFaites / nbEtapes) * 100}%"></div>
          <div class="bg-stone-300 dark:bg-stone-600"
               style="width: {(nbInconnues / nbEtapes) * 100}%"></div>
        </div>

        <div class="mt-4 grid gap-5 md:grid-cols-2">
          {#each PHASES as phase (phase.id)}
            <div>
              <p class="text-[10px] font-semibold uppercase tracking-widest text-stone-400 dark:text-stone-500">
                {phase.titre}
              </p>
              <ul class="mt-1.5 space-y-0.5">
                {#each etapesDe(phase.id) as etape (etape.id)}
                  {@const e = etats[etape.id]}
                  <li>
                    <button
                      class="group flex w-full items-start gap-2 rounded-md px-2 py-1 text-left hover:bg-stone-100 dark:hover:bg-stone-700/50"
                      onclick={() => aller(etape.page)}
                    >
                      <span
                        class="mt-1 h-2 w-2 shrink-0 rounded-full"
                        class:bg-emerald-600={e?.etat === "faite"}
                        class:bg-amber-500={e?.etat === "a_faire"}
                        class:bg-stone-300={!e || e.etat === "inconnu"}
                        class:dark:bg-stone-600={!e || e.etat === "inconnu"}
                      ></span>
                      <span class="min-w-0 flex-1">
                        <span class="block truncate text-sm text-stone-800 dark:text-stone-200">
                          {etape.titre}
                        </span>
                        {#if e?.detail}
                          <span class="block text-xs leading-snug text-stone-500 dark:text-stone-400">
                            {e.detail}
                          </span>
                        {/if}
                      </span>
                    </button>
                  </li>
                {/each}
              </ul>
            </div>
          {/each}
        </div>
      </div>
    {/if}

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
