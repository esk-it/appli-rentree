<script>
  import { onMount } from "svelte";
  import Search from "@lucide/svelte/icons/search";
  import AlertTriangle from "@lucide/svelte/icons/alert-triangle";
  import Cloud from "@lucide/svelte/icons/cloud";
  import ArrowRight from "@lucide/svelte/icons/arrow-right";
  import Squelette from "$lib/components/Squelette.svelte";
  import Bouton from "$lib/components/Bouton.svelte";
  import Progression from "$lib/components/Progression.svelte";
  import { annees, parcoursApi, statistiques } from "$lib/api.js";
  import { PHASES, etapesDe } from "$lib/parcours.js";
  import { TEINTES, teinte } from "$lib/familles.js";
  import { annee, courante } from "$lib/annee.svelte.js";
  import { notify } from "$lib/toasts.js";

  /**
   * L'accueil : où l'on est, ce qui cloche, et où aller.
   *
   * ## Ce que cet écran a cessé d'être
   *
   * Quatre compteurs dans quatre cartes — personnes, sites, années,
   * arbitrages — qui répondaient à des questions que personne ne se pose
   * en ouvrant le programme. On l'ouvre pour préparer la rentrée, ou pour
   * aller quelque part.
   *
   * Il tient donc trois choses, dans cet ordre : **où l'on en est** de la
   * campagne, **ce qui bloque**, et **la carte des modules**. Les chiffres
   * du référentiel ont reculé dans la ligne de contexte, sous le titre :
   * ils situent, ils ne sont pas la nouvelle du jour.
   *
   * ## Pourquoi une grille d'icônes plutôt que des cartes
   *
   * Une carte par module, c'est vingt rectangles de même poids où l'œil ne
   * s'accroche à rien. Une icône colorée et un nom se reconnaissent de
   * loin, et la couleur du domaine fait le reste du travail : on cherche
   * « le rose », pas « la sixième carte de la deuxième rangée ».
   *
   * @typedef {Object} Props
   * @property {(page: string) => void} [onNaviguer]
   * @property {any[]} [parties] - la navigation, telle qu'App.svelte la tient
   * @property {() => void} [onRechercher]
   */
  /** @type {Props} */
  let { onNaviguer = null, parties = [], onRechercher = null } = $props();

  let ref = $state(/** @type {null | any} */ (null));
  let listeAnnees = $state([]);
  let anomalies = $state(/** @type {null | any} */ (null));
  let chargement = $state(true);
  let etats = $state(/** @type {Record<string, any>} */ ({}));
  let interrogationGoogle = $state(false);

  /** L'année de travail choisie dans l'en-tête, et non une devinée ici. */
  let anneeCourante = $derived(courante());

  onMount(async () => {
    try {
      [ref, listeAnnees, anomalies] = await Promise.all([
        statistiques.referentiel(),
        annees.lister(),
        statistiques.anomalies(),
      ]);
    } catch {
      // Le backend démarre peut-être encore — l'écran reste sobre plutôt
      // que d'annoncer des zéros qui passeraient pour des constats.
    } finally {
      chargement = false;
    }
  });

  // Le parcours suit l'année choisie : en changer doit relire l'avancement,
  // sans quoi l'écran afficherait l'état d'une autre année sous son titre.
  $effect(() => {
    const id = annee.id;
    if (!id) return;
    parcoursApi
      .avancement(id)
      .then((r) => {
        etats = Object.fromEntries(r.etapes.map((e) => [e.id, e]));
      })
      .catch(() => {
        etats = {};
      });
  });

  /**
   * Les cinq étapes que seul Google peut trancher.
   *
   * Plusieurs appels réseau : c'est un geste qu'on demande, jamais un
   * effet de bord de l'affichage.
   */
  async function interrogerGoogle() {
    if (!annee.id) return;
    interrogationGoogle = true;
    try {
      const r = await parcoursApi.avancementGoogle({ anneeId: annee.id });
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
  let aSignaler = $derived(
    (anomalies?.anomalies ?? []).filter((a) => a.gravite !== "bloquant"),
  );

  function aller(page) {
    if (onNaviguer) onNaviguer(page);
  }

  /** Le fond pâle d'une icône : sa teinte, très diluée. */
  const voile = (t) => `color-mix(in oklab, ${t} 16%, transparent)`;
</script>

<section class="mx-auto max-w-6xl space-y-9 pb-10">
  <!-- ------------------------------------------------------------------
       Où l'on est.
       ------------------------------------------------------------------ -->
  <header class="pt-2 text-center">
    <h1 class="titre-affiche text-4xl text-stone-900 dark:text-stone-50">
      Qu'est-ce qu'on prépare&nbsp;?
    </h1>
    <p class="mt-2 text-sm text-stone-600 dark:text-stone-400">
      {#if anneeCourante}
        Année <strong class="font-semibold text-stone-800 dark:text-stone-200">
          {anneeCourante.libelle}
        </strong>
        ·
      {/if}
      <span class="tabular-nums">{ref?.nb_personnes_total ?? 0}</span> personnes au référentiel
      · <span class="tabular-nums">{ref?.nb_eleves_total ?? 0}</span> élèves
      · <span class="tabular-nums">{ref?.nb_sites ?? 0}</span> sites
    </p>

    <button
      type="button"
      class="mx-auto mt-5 flex h-12 w-full max-w-xl items-center gap-3 rounded-full border border-stone-300 px-5 text-left text-sm text-stone-500 transition-colors hover:border-stone-400 dark:border-stone-700 dark:text-stone-400 dark:hover:border-stone-600"
      onclick={() => onRechercher?.()}
    >
      <Search class="h-4 w-4 shrink-0" />
      <span class="flex-grow">Rechercher un module, un élève, un Chromebook…</span>
      <kbd class="shrink-0 rounded border border-stone-300 px-1.5 text-[11px] font-medium dark:border-stone-700">
        Ctrl K
      </kbd>
    </button>
  </header>

  {#if chargement}
    <Squelette variante="carte" nb={3} />
  {:else}
    <!-- ----------------------------------------------------------------
         Ce qui cloche — des bandeaux, pas des cartes : ils s'effacent
         quand il n'y a rien, au lieu de laisser un trou.
         ---------------------------------------------------------------- -->
    {#if bloquants.length || aSignaler.length}
      <div class="grid gap-2.5 md:grid-cols-[1.6fr_1fr]">
        {#if bloquants.length}
          <div class="flex flex-wrap items-center gap-x-4 gap-y-2 rounded-xl bg-red-50 px-5 py-3 text-sm dark:bg-red-500/10">
            <AlertTriangle class="h-4 w-4 shrink-0 text-red-700 dark:text-red-400" />
            {#each bloquants as b (b.type)}
              <span class="text-stone-800 dark:text-stone-200">{b.libelle}</span>
            {/each}
            <button
              class="ml-auto font-bold text-red-700 hover:underline dark:text-red-400"
              onclick={() => aller("ou_ca_coince")}
            >
              Départager →
            </button>
          </div>
        {/if}
        {#if aSignaler.length}
          <div class="flex flex-wrap items-center gap-3 rounded-xl bg-amber-50 px-5 py-3 text-sm dark:bg-amber-400/10">
            <span class="h-2.5 w-2.5 shrink-0 rounded-full bg-amber-500"></span>
            <span class="text-stone-800 dark:text-stone-200">
              {aSignaler.length} point{aSignaler.length > 1 ? "s" : ""} à regarder
            </span>
            <button
              class="ml-auto font-bold text-amber-800 hover:underline dark:text-amber-400"
              onclick={() => aller("ou_ca_coince")}
            >
              Vérifier →
            </button>
          </div>
        {/if}
      </div>
    {/if}

    <!-- ----------------------------------------------------------------
         La rentrée : l'avancement réel, pas un compteur.
         ---------------------------------------------------------------- -->
    {#if nbEtapes > 0}
      <section>
        <div class="flex items-center gap-3">
          <span class="h-2.5 w-2.5 shrink-0 rounded-full" style="background: {TEINTES.rentree}"></span>
          <h2 class="titre-affiche text-xl">La rentrée</h2>
          <span class="text-[13px] text-stone-500 dark:text-stone-400">
            {nbFaites} étape{nbFaites > 1 ? "s" : ""} faite{nbFaites > 1 ? "s" : ""} sur {nbEtapes}
          </span>
          <span class="filet"></span>
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
          <Bouton taille="sm" icon={ArrowRight} onclick={() => aller("parcours")}>
            Ouvrir le parcours
          </Bouton>
        </div>

        <div class="mt-4">
          <Progression
            valeur={nbFaites}
            total={nbEtapes}
            teinte={TEINTES.rentree}
          />
        </div>

        <div class="mt-5 grid gap-x-10 gap-y-6 md:grid-cols-2">
          {#each PHASES as phase (phase.id)}
            <div>
              <p class="titre-section">{phase.titre}</p>
              <ul class="mt-2">
                {#each etapesDe(phase.id) as etape (etape.id)}
                  {@const e = etats[etape.id]}
                  <li>
                    <button
                      class="flex w-full items-start gap-2.5 rounded-lg px-2 py-1.5 text-left transition-colors hover:bg-stone-100 dark:hover:bg-stone-900"
                      onclick={() => aller(etape.page)}
                    >
                      <span
                        class="mt-1.5 h-2 w-2 shrink-0 rounded-full"
                        style="background: {e?.etat === 'faite'
                          ? TEINTES.koxo
                          : e?.etat === 'a_faire'
                            ? 'var(--color-amber-500)'
                            : 'var(--color-stone-300)'}"
                      ></span>
                      <span class="min-w-0 flex-1">
                        <span class="block truncate text-sm font-medium text-stone-800 dark:text-stone-200">
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
      </section>
    {/if}

    <!-- ----------------------------------------------------------------
         Les modules, par domaine. La navigation en est la source : deux
         listes à tenir divergeraient au premier écran ajouté.
         ---------------------------------------------------------------- -->
    {#each parties.filter((p) => p.ecrans.length > 1) as partie (partie.id)}
      <section>
        <div class="flex items-center gap-3">
          <span
            class="h-2.5 w-2.5 shrink-0 rounded-full"
            style="background: {TEINTES[partie.id] ?? TEINTES.annee}"
          ></span>
          <h2 class="titre-affiche text-xl">{partie.label}</h2>
          <span class="text-[13px] text-stone-500 dark:text-stone-400">{partie.resume}</span>
          <span class="filet"></span>
        </div>

        <div class="anim-cascade mt-4 grid grid-cols-3 gap-1 sm:grid-cols-4 lg:grid-cols-6">
          {#each partie.ecrans as ecran (ecran.id)}
            {@const t = teinte(ecran.id, partie.id)}
            {@const compteur = ecran.badge ? ecran.badge() : 0}
            <button
              class="anim-apparition flex flex-col items-center gap-2 rounded-2xl p-3 text-center transition-colors hover:bg-stone-100 dark:hover:bg-stone-900"
              onclick={() => aller(ecran.id)}
            >
              <span class="relative block h-12 w-12" style="color: {t}">
                <!-- Le remplissage pâle est posé sur le tracé lui-même :
                     c'est ce qui distingue une icône dessinée d'un
                     pictogramme d'interface. -->
                <ecran.icon
                  class="h-12 w-12"
                  style="fill: {voile(t)}; stroke-width: 1.5;"
                />
                {#if compteur > 0}
                  <span class="pastille-compteur">{compteur}</span>
                {/if}
              </span>
              <span class="text-sm leading-tight font-semibold text-stone-900 dark:text-stone-100">
                {ecran.label}
              </span>
            </button>
          {/each}
        </div>
      </section>
    {/each}
  {/if}
</section>
