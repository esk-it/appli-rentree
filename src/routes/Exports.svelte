<script>
  import { onMount } from "svelte";
  import Download from "@lucide/svelte/icons/download";
  import FileDown from "@lucide/svelte/icons/file-down";
  import Info from "@lucide/svelte/icons/info";
  import AlertTriangle from "@lucide/svelte/icons/alert-triangle";
  import {
    annees,
    exportsCible,
    sites as sitesApi,
    telechargerFichierBase64,
  } from "$lib/api.js";
  import { notify } from "$lib/toasts.js";

  let listeSites = $state([]);
  let listeAnnees = $state([]);

  let siteId = $state(/** @type {null | number} */ (null));
  let typePersonne = $state(/** @type {"eleve"|"adulte"} */ ("eleve"));
  let categorie = $state(/** @type {"tous"|"nouveaux"|"anciens"} */ ("tous"));
  let anneeCibleId = $state(/** @type {null | number} */ (null));
  let anneeSourceId = $state(/** @type {null | number} */ (null));

  let dernierRapport = $state(/** @type {null | any} */ (null));
  let chargement = $state(false);
  let erreur = $state("");

  onMount(async () => {
    try {
      listeSites = await sitesApi.lister();
      listeAnnees = await annees.lister();
      if (listeAnnees.length >= 1) anneeCibleId = listeAnnees[0].id;
      if (listeAnnees.length >= 2) anneeSourceId = listeAnnees[1].id;
    } catch (e) {
      erreur = String(e);
    }
  });

  let anneeSourceRequise = $derived(categorie === "nouveaux" || categorie === "anciens");

  async function generer() {
    if (!siteId || !anneeCibleId) return;
    if (anneeSourceRequise && !anneeSourceId) {
      notify.avertissement("Année source requise pour cette catégorie");
      return;
    }
    chargement = true;
    erreur = "";
    try {
      const r = await exportsCible.koxo({
        siteId,
        typePersonne,
        categorie,
        anneeCibleId,
        anneeSourceId: anneeSourceRequise ? anneeSourceId : null,
      });
      dernierRapport = r;
      telechargerFichierBase64(r.nom_fichier, r.contenu_base64, "text/csv");
      notify.succes(`${r.nb_lignes} ligne(s) exportée(s) — ${r.nom_fichier}`);
    } catch (e) {
      erreur = String(e);
      notify.erreur(erreur);
    } finally {
      chargement = false;
    }
  }
</script>

<section class="space-y-5">
  <header>
    <h1 class="text-2xl font-semibold text-stone-900 dark:text-stone-100">
      Exports vers les cibles
    </h1>
    <p class="mt-1 text-sm text-stone-600 dark:text-stone-400">
      Génère les fichiers à importer dans les systèmes tiers. Pour l'instant
      seul <strong>KoXo</strong> est disponible (Lot 8a) — Google, PMB, JPM,
      CardStudio viennent dans les lots suivants.
    </p>
  </header>

  {#if listeSites.length === 0 || listeAnnees.length === 0}
    <div class="card border-amber-200 bg-amber-50/50 p-4 text-sm dark:border-amber-800 dark:bg-amber-900/20">
      <div class="flex items-start gap-3">
        <AlertTriangle class="mt-0.5 h-5 w-5 text-amber-700 dark:text-amber-400" />
        <div>
          <p class="font-medium text-amber-900 dark:text-amber-200">Données manquantes</p>
          <p class="mt-1 text-stone-700 dark:text-stone-300">
            Il faut au moins un <strong>Site</strong> et une <strong>année scolaire</strong>
            {#if listeAnnees.length === 0}(via un amorçage ou une ingestion){/if} pour
            générer un export.
          </p>
        </div>
      </div>
    </div>
  {/if}

  <div class="card p-5 space-y-4">
    <h2 class="text-lg font-semibold">KoXo — génération d'un CSV</h2>

    <div class="grid grid-cols-1 gap-3 md:grid-cols-3">
      <label class="block">
        <span class="text-xs font-medium uppercase tracking-wide text-stone-600 dark:text-stone-400">
          Site KoXo cible
        </span>
        <select
          bind:value={siteId}
          class="mt-1 w-full rounded-lg border border-stone-300 px-3 py-2 text-sm dark:border-stone-600 dark:bg-stone-800"
        >
          <option value={null}>— Choisir —</option>
          {#each listeSites as s (s.id)}
            <option value={s.id}>{s.nom}</option>
          {/each}
        </select>
      </label>
      <label class="block">
        <span class="text-xs font-medium uppercase tracking-wide text-stone-600 dark:text-stone-400">
          Type de population
        </span>
        <select
          bind:value={typePersonne}
          class="mt-1 w-full rounded-lg border border-stone-300 px-3 py-2 text-sm dark:border-stone-600 dark:bg-stone-800"
        >
          <option value="eleve">Élèves</option>
          <option value="adulte">Adultes / Profs</option>
        </select>
      </label>
      <label class="block">
        <span class="text-xs font-medium uppercase tracking-wide text-stone-600 dark:text-stone-400">
          Catégorie
        </span>
        <select
          bind:value={categorie}
          class="mt-1 w-full rounded-lg border border-stone-300 px-3 py-2 text-sm dark:border-stone-600 dark:bg-stone-800"
        >
          <option value="tous">Tous (état complet visé)</option>
          <option value="nouveaux">Nouveaux (à créer)</option>
          <option value="anciens">Anciens (à supprimer)</option>
        </select>
      </label>
    </div>

    <div class="grid grid-cols-1 gap-3 md:grid-cols-2">
      <label class="block">
        <span class="text-xs font-medium uppercase tracking-wide text-stone-600 dark:text-stone-400">
          Année cible (à traiter)
        </span>
        <select
          bind:value={anneeCibleId}
          class="mt-1 w-full rounded-lg border border-stone-300 px-3 py-2 text-sm dark:border-stone-600 dark:bg-stone-800"
        >
          <option value={null}>— Choisir —</option>
          {#each listeAnnees as a (a.id)}
            <option value={a.id}>{a.libelle}</option>
          {/each}
        </select>
      </label>
      {#if anneeSourceRequise}
        <label class="block">
          <span class="text-xs font-medium uppercase tracking-wide text-stone-600 dark:text-stone-400">
            Année source (référentiel)
          </span>
          <select
            bind:value={anneeSourceId}
            class="mt-1 w-full rounded-lg border border-stone-300 px-3 py-2 text-sm dark:border-stone-600 dark:bg-stone-800"
          >
            <option value={null}>— Choisir —</option>
            {#each listeAnnees as a (a.id)}
              <option value={a.id}>{a.libelle}</option>
            {/each}
          </select>
        </label>
      {/if}
    </div>

    <div class="rounded-lg border border-stone-200 bg-stone-50 p-3 text-xs dark:border-stone-700 dark:bg-stone-800">
      <div class="flex items-start gap-2 text-stone-700 dark:text-stone-300">
        <Info class="mt-0.5 h-4 w-4 shrink-0" />
        <p>
          {#if categorie === "tous"}
            Toutes les personnes du site+type ayant un snapshot dans l'année cible.
            Utile pour un import massif initial ou une resynchronisation.
          {:else if categorie === "nouveaux"}
            Uniquement les entrants (présents à l'année cible, absents de la source).
            KoXo <strong>générera les mots de passe à l'import</strong> — c'est le
            fichier à charger pour créer les comptes.
          {:else}
            Uniquement les sortants (présents à la source, absents de la cible).
            À utiliser pour supprimer les comptes obsolètes côté KoXo.
          {/if}
        </p>
      </div>
    </div>

    <div class="flex gap-2">
      <button
        class="btn-primary"
        onclick={generer}
        disabled={!siteId || !anneeCibleId || (anneeSourceRequise && !anneeSourceId) || chargement}
      >
        <FileDown class="h-4 w-4" />
        Générer et télécharger
      </button>
      {#if chargement}
        <span class="self-center text-sm text-stone-500">Génération…</span>
      {/if}
    </div>

    {#if erreur}
      <p class="rounded-lg bg-red-50 px-3 py-2 text-sm text-red-700 dark:bg-red-900/30 dark:text-red-300">
        {erreur}
      </p>
    {/if}
  </div>

  {#if dernierRapport}
    <div class="card p-4">
      <div class="flex items-center justify-between">
        <div>
          <p class="text-sm font-semibold text-stone-900 dark:text-stone-100">
            Dernier export : <code>{dernierRapport.nom_fichier}</code>
          </p>
          <p class="text-xs text-stone-500 dark:text-stone-400">
            {dernierRapport.nb_lignes} ligne(s) — site {dernierRapport.site_nom},
            {dernierRapport.type_personne}s, catégorie {dernierRapport.categorie}
          </p>
        </div>
        <button
          class="btn-secondary text-xs"
          onclick={() => telechargerFichierBase64(dernierRapport.nom_fichier, dernierRapport.contenu_base64, "text/csv")}
        >
          <Download class="h-3.5 w-3.5" />
          Re-télécharger
        </button>
      </div>
    </div>
  {/if}
</section>
