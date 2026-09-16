<script>
  import { onMount } from "svelte";
  import AlertTriangle from "@lucide/svelte/icons/alert-triangle";
  import CheckCircle2 from "@lucide/svelte/icons/check-circle-2";
  import Info from "@lucide/svelte/icons/info";
  import ArrowRight from "@lucide/svelte/icons/arrow-right";
  import Compass from "@lucide/svelte/icons/compass";
  import RefreshCw from "@lucide/svelte/icons/refresh-cw";
  import Image from "@lucide/svelte/icons/image";
  import Bouton from "$lib/components/Bouton.svelte";
  import EnTetePage from "$lib/components/EnTetePage.svelte";
  import Nombre from "$lib/components/Nombre.svelte";
  import Squelette from "$lib/components/Squelette.svelte";
  import { annees as anneesApi, statistiques } from "$lib/api.js";
  import { notify } from "$lib/toasts.js";

  /**
   * L'entrée de « L'année » : ce qui cloche, et le geste qui le règle.
   *
   * ## Pourquoi cet écran remplace un tableau de bord d'étapes
   *
   * L'accueil annonçait « 8 étapes faites sur 15 » et « prochaine étape :
   * vider l'arbre de l'année révolue ». C'est le bon écran en août, quand
   * la campagne se déroule dans un ordre connu. Le reste de l'année, la
   * question n'est plus « où en est le parcours » mais « qu'est-ce qui ne
   * colle pas, aujourd'hui » — et cette question-là n'avait aucune réponse.
   *
   * ## Un constat n'est utile que s'il porte son geste
   *
   * Afficher « 4 classes hors table » sans dire où aller, c'est laisser le
   * travail de traduction à celui qui lit. Chaque constat connaît donc
   * l'écran qui le règle, et le bouton y mène directement.
   *
   * ## Ce qui est lu tout de suite, et ce qui ne l'est pas
   *
   * Les anomalies se calculent dans la base locale : instantané, à chaque
   * ouverture. Deux choses ne s'y trouvent pas et coûtent cher :
   *
   * - les **photos**, un accès disque par élève sur un partage réseau ;
   * - l'état réel de **Google**, plusieurs centaines d'appels.
   *
   * Elles ne partent donc pas d'elles-mêmes. Elles sont annoncées comme
   * non vérifiées — ce qui est distinct de « tout va bien » — et se
   * demandent d'un clic.
   *
   * @typedef {Object} Props
   * @property {(page: string) => void} [onNaviguer]
   */
  /** @type {Props} */
  let { onNaviguer } = $props();

  let anomalies = $state(/** @type {any} */ (null));
  let stats = $state(/** @type {any} */ (null));
  let annee = $state(/** @type {any} */ (null));
  let chargement = $state(true);
  let erreur = $state("");
  let photosVerifiees = $state(false);
  let relecture = $state(false);

  /**
   * Où va-t-on pour régler chaque anomalie.
   *
   * La table vit ici plutôt que dans le service : le backend décrit ce
   * qu'il constate, l'interface sait par quel écran on y remédie. Une
   * anomalie sans destination reste affichée — sans bouton, mais visible.
   */
  const OU_REGLER = {
    classe_hors_table: { page: "table_correspondance", geste: "Compléter la Table" },
    classe_sans_groupe: { page: "table_correspondance", geste: "Compléter la Table" },
    arbitrage_en_attente: { page: "arbitrage", geste: "Trancher" },
    personne_sans_site: { page: "personnes", geste: "Voir les fiches" },
    personne_sans_email: { page: "personnes", geste: "Voir les fiches" },
    collision_email: { page: "personnes", geste: "Départager" },
    compte_purge_echue: { page: "sortants", geste: "Décider" },
    photo_orpheline: { page: "exports", geste: "Voir les photos" },
  };

  const TEINTES = {
    bloquant: {
      barre: "border-l-red-500",
      nb: "text-red-700 dark:text-red-400",
      icone: AlertTriangle,
      iconeClasse: "text-red-600 dark:text-red-400",
    },
    attention: {
      barre: "border-l-amber-500",
      nb: "text-amber-700 dark:text-amber-400",
      icone: AlertTriangle,
      iconeClasse: "text-amber-600 dark:text-amber-400",
    },
    information: {
      barre: "border-l-stone-300 dark:border-l-stone-600",
      nb: "text-stone-600 dark:text-stone-300",
      icone: Info,
      iconeClasse: "text-stone-400 dark:text-stone-500",
    },
  };

  /** Les bloquants d'abord : ce sont eux qui empêchent un traitement. */
  const ORDRE = { bloquant: 0, attention: 1, information: 2 };
  let triees = $derived(
    [...(anomalies?.anomalies ?? [])].sort(
      (a, b) => ORDRE[a.gravite] - ORDRE[b.gravite] || b.nb_concernes - a.nb_concernes,
    ),
  );

  let effectifs = $derived.by(() => {
    const par = new Map();
    for (const e of stats?.effectifs_par_site_type ?? []) {
      par.set(e.site, (par.get(e.site) ?? 0) + e.nb);
    }
    return [...par.entries()].sort((a, b) => b[1] - a[1]);
  });

  onMount(charger);

  async function charger({ avecPhotos = false } = {}) {
    if (avecPhotos) relecture = true;
    else chargement = true;
    erreur = "";
    try {
      const liste = await anneesApi.lister();
      // L'année préparée est la plus récente par libellé, comme partout
      // ailleurs. `est_active` ne départage rien : il est vrai sur les deux
      // années à la fois, et s'y fier affichait 2025-2026 en préparation.
      annee = [...liste].sort((a, b) => b.libelle.localeCompare(a.libelle))[0] ?? null;
      const [a, s] = await Promise.all([
        statistiques.anomalies({
          anneeId: annee?.id ?? null,
          verifierPhotos: avecPhotos,
        }),
        statistiques.referentiel(),
      ]);
      anomalies = a;
      stats = s;
      if (avecPhotos) photosVerifiees = true;
    } catch (e) {
      erreur = String(e).replace(/^Error:\s*/, "");
    } finally {
      chargement = false;
      relecture = false;
    }
  }

  function aller(page) {
    onNaviguer?.(page);
  }
</script>

<section class="space-y-5">
  <EnTetePage
    icon={Compass}
    titre="Où ça coince"
    description="Ce que le programme constate dans le référentiel, maintenant. Chaque ligne porte le geste qui la règle."
  >
    {#snippet actions()}
      <Bouton icon={RefreshCw} occupe={chargement && !relecture} onclick={() => charger()}>
        Relire
      </Bouton>
    {/snippet}
  </EnTetePage>

  {#if erreur}
    <p class="rounded-lg bg-red-50 px-3 py-2 text-sm text-red-700 dark:bg-red-900/30 dark:text-red-300">
      {erreur}
    </p>
  {/if}

  <!-- L'état des lieux : le contexte chiffré, avant les problèmes. Ce sont
       les chiffres de l'écran Statistiques, ramenés là où on passe. -->
  {#if chargement && !stats}
    <Squelette variante="ligne-tableau" nb={3} colonnes={4} />
  {:else if stats}
    <div class="grid gap-px overflow-hidden rounded-xl border border-stone-200 bg-stone-200 dark:border-stone-700 dark:bg-stone-700
                sm:grid-cols-2 lg:grid-cols-4">
      <div class="bg-white p-4 dark:bg-stone-800">
        <p class="libelle-champ">Au référentiel</p>
        <p class="mt-1 text-2xl font-semibold tabular-nums">
          <Nombre valeur={stats.nb_personnes_total} duree={400} />
        </p>
        <p class="text-xs text-stone-500 dark:text-stone-400">
          {stats.nb_eleves_total} élèves · {stats.nb_adultes_total} adultes
        </p>
      </div>
      <div class="bg-white p-4 dark:bg-stone-800">
        <p class="libelle-champ">Année préparée</p>
        <p class="mt-1 text-2xl font-semibold">{annee?.libelle ?? "—"}</p>
        <p class="text-xs text-stone-500 dark:text-stone-400">
          {stats.nb_classes_table} classes dans la Table
        </p>
      </div>
      <div class="bg-white p-4 dark:bg-stone-800">
        <p class="libelle-champ">Par site</p>
        <div class="mt-1 flex flex-col gap-0.5 text-sm">
          {#each effectifs as [site, nb] (site)}
            <div class="flex justify-between gap-3">
              <span class="text-stone-600 dark:text-stone-300">{site}</span>
              <span class="tabular-nums font-medium">{nb}</span>
            </div>
          {/each}
        </div>
      </div>
      <div class="bg-white p-4 dark:bg-stone-800">
        <p class="libelle-champ">Arbitrages</p>
        <p class="mt-1 text-2xl font-semibold tabular-nums">
          {stats.nb_arbitrages_en_attente}
        </p>
        <p class="text-xs text-stone-500 dark:text-stone-400">
          en attente · {stats.nb_arbitrages_tranches} tranchés
        </p>
      </div>
    </div>
  {/if}

  <!-- Les constats -->
  {#if chargement && !anomalies}
    <Squelette variante="ligne-tableau" nb={4} colonnes={3} />
  {:else if anomalies}
    <div class="flex flex-col gap-2">
      {#if triees.length === 0}
        <div class="card flex items-center gap-3 p-5">
          <CheckCircle2 class="h-6 w-6 shrink-0 text-emerald-600 dark:text-emerald-400" />
          <div>
            <p class="font-medium">Rien ne cloche dans le référentiel.</p>
            <p class="text-sm text-stone-500 dark:text-stone-400">
              Les huit contrôles passent. Ce qui se vérifie dans Google reste à
              demander séparément, plus bas.
            </p>
          </div>
        </div>
      {:else}
        <p class="text-sm text-stone-600 dark:text-stone-400">
          <strong>{triees.length}</strong>
          chose{triees.length > 1 ? "s" : ""} demande{triees.length > 1 ? "nt" : ""} ton attention{#if anomalies.nb_bloquants}, dont
            <strong class="text-red-700 dark:text-red-400">{anomalies.nb_bloquants}</strong>
            qui bloque{anomalies.nb_bloquants > 1 ? "nt" : ""} un traitement{/if}.
        </p>

        {#each triees as a (a.type)}
          {@const t = TEINTES[a.gravite] ?? TEINTES.information}
          {@const dest = OU_REGLER[a.type]}
          <div class="card flex flex-wrap items-center gap-4 border-l-4 p-4 {t.barre}">
            <span class="text-3xl font-semibold tabular-nums {t.nb}" style="min-width:3ch">
              {a.nb_concernes}
            </span>
            <div class="min-w-0 flex-1">
              <p class="flex items-center gap-1.5 font-medium">
                <t.icone class="h-4 w-4 shrink-0 {t.iconeClasse}" />
                {a.libelle}
              </p>
              {#if a.details.length}
                <p class="mt-0.5 truncate text-xs text-stone-500 dark:text-stone-400">
                  {a.details.slice(0, 6).join(" · ")}{a.details.length > 6 ? " …" : ""}
                </p>
              {/if}
              {#if a.action_suggeree}
                <p class="mt-0.5 text-xs text-stone-500 dark:text-stone-400">
                  {a.action_suggeree}
                </p>
              {/if}
            </div>
            {#if dest}
              <Bouton taille="sm" icon={ArrowRight} onclick={() => aller(dest.page)}>
                {dest.geste}
              </Bouton>
            {/if}
          </div>
        {/each}
      {/if}
    </div>
  {/if}

  <!-- Ce qui n'a pas été vérifié, et qui n'est pas « tout va bien ». -->
  <div class="card space-y-3 p-4">
    <h2 class="titre-section">Ce qui n'a pas été vérifié</h2>
    <p class="text-sm text-stone-600 dark:text-stone-400">
      Deux contrôles coûtent trop cher pour partir à chaque ouverture. Tant
      qu'ils n'ont pas tourné, leur silence ne veut rien dire.
    </p>

    <div class="grid gap-3 sm:grid-cols-2">
      <div class="rounded-lg border border-stone-200 p-3 dark:border-stone-700">
        <p class="flex items-center gap-1.5 text-sm font-medium">
          <Image class="h-4 w-4 text-stone-400" /> Les photos
        </p>
        <p class="mt-1 text-xs text-stone-500 dark:text-stone-400">
          Un accès disque par élève sur le partage réseau. À lancer quand le
          partage est monté.
        </p>
        <div class="mt-2">
          {#if photosVerifiees}
            <span class="badge-neutre">Vérifiées à la dernière relecture</span>
          {:else}
            <Bouton taille="sm" occupe={relecture} onclick={() => charger({ avecPhotos: true })}>
              Vérifier les photos
            </Bouton>
          {/if}
        </div>
      </div>

      <div class="rounded-lg border border-stone-200 p-3 dark:border-stone-700">
        <p class="flex items-center gap-1.5 text-sm font-medium">
          <AlertTriangle class="h-4 w-4 text-stone-400" /> L'état réel de Google
        </p>
        <p class="mt-1 text-xs text-stone-500 dark:text-stone-400">
          Unités, groupes et comptes suspendus — plusieurs centaines d'appels.
          C'est la Conformité qui les relève.
        </p>
        <div class="mt-2">
          <Bouton taille="sm" icon={ArrowRight} onclick={() => aller("conformite_google")}>
            Aller à la Conformité
          </Bouton>
        </div>
      </div>
    </div>

    <p class="text-xs text-stone-500 dark:text-stone-400">
      Pour comparer Charlemagne, le référentiel, Google et KoXo sur la classe de
      chacun, c'est la <button
        type="button"
        class="font-medium text-emerald-700 underline decoration-dotted hover:text-emerald-800 dark:text-emerald-400"
        onclick={() => aller("concordance")}>Concordance</button
      > — elle demande un export Charlemagne frais, donc elle ne peut pas tourner toute seule.
    </p>
  </div>
</section>
