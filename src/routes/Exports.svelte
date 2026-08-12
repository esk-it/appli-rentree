<script>
  import { onMount } from "svelte";
  import Download from "@lucide/svelte/icons/download";
  import FileDown from "@lucide/svelte/icons/file-down";
  import Upload from "@lucide/svelte/icons/upload";
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

  let cible = $state(/** @type {"koxo"|"google"|"pmb"|"jpm"|"cardstudio"} */ ("koxo"));
  let siteId = $state(/** @type {null | number} */ (null));
  let typePersonne = $state(/** @type {"eleve"|"adulte"} */ ("eleve"));
  let categorie = $state(/** @type {"tous"|"nouveaux"|"anciens"} */ ("tous"));
  let anneeCibleId = $state(/** @type {null | number} */ (null));
  let anneeSourceId = $state(/** @type {null | number} */ (null));

  let dernierRapport = $state(/** @type {null | any} */ (null));
  let chargement = $state(false);
  let erreur = $state("");

  // Boucle KoXo → Google (Lot 8b) — MDP transportés en mémoire uniquement
  let fichierKoxoEnrichi = $state(/** @type {File|null} */ (null));

  // Enregistrement du cycle de vie : inscrit les personnes du fichier en
  // CompteCible(etat="prevu") — c'est ce qui alimente l'écran Suivi.
  let enregistrerPrevus = $state(true);

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
      const params = {
        siteId,
        typePersonne,
        categorie,
        anneeCibleId,
        anneeSourceId: anneeSourceRequise ? anneeSourceId : null,
        enregistrerPrevus,
      };
      let r;
      if (cible === "koxo") {
        r = await exportsCible.koxo(params);
      } else if (cible === "google") {
        r = fichierKoxoEnrichi
          ? await exportsCible.googleAvecMdp({ fichierKoxo: fichierKoxoEnrichi, ...params })
          : await exportsCible.google(params);
      } else if (cible === "pmb") {
        r = await exportsCible.pmb(params);
      } else if (cible === "jpm") {
        r = await exportsCible.jpm({
          siteId, anneeCibleId, anneeSourceId, enregistrerPrevus,
        });
      } else if (cible === "cardstudio") {
        r = await exportsCible.cardstudio({
          siteId, categorie, anneeCibleId, anneeSourceId, enregistrerPrevus,
        });
      }
      const labelCible = cible === "google" && fichierKoxoEnrichi ? "google (avec MDP)" : cible;
      dernierRapport = { ...r, cible: labelCible };
      telechargerFichierBase64(r.nom_fichier, r.contenu_base64, "text/csv");
      const parts = [];
      if (r.nb_sans_ou > 0) parts.push(`${r.nb_sans_ou} sans OU — classe hors table`);
      if (r.nb_prevus_enregistres > 0) parts.push(`${r.nb_prevus_enregistres} compte(s) suivi(s)`);
      const suffixe = parts.length ? ` (${parts.join(" ; ")})` : "";
      const nb = r.nb_lignes ?? r.nb_total ?? 0;
      notify.succes(`${nb} ligne(s) exportée(s) — ${r.nom_fichier}${suffixe}`);
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
    <div class="flex items-center justify-between">
      <h2 class="text-lg font-semibold">Génération d'un CSV</h2>
      <div class="inline-flex flex-wrap gap-1 rounded-lg border border-stone-200 p-1 dark:border-stone-700">
        {#each [
          { id: "koxo", label: "KoXo" },
          { id: "google", label: "Google" },
          { id: "pmb", label: "PMB" },
          { id: "jpm", label: "JPM" },
          { id: "cardstudio", label: "CardStudio" },
        ] as c (c.id)}
          <button
            class="rounded-md px-2.5 py-1 text-xs font-medium transition
                   {cible === c.id ? 'bg-emerald-100 text-emerald-800 dark:bg-emerald-900/40 dark:text-emerald-300' : 'text-stone-600 hover:bg-stone-100 dark:text-stone-400 dark:hover:bg-stone-700'}"
            onclick={() => (cible = c.id)}
          >
            {c.label}
          </button>
        {/each}
      </div>
    </div>

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
        <div class="space-y-1">
          {#if cible === "koxo"}
            {#if categorie === "tous"}
              <p>Toutes les personnes du site+type ayant un snapshot dans l'année cible. Utile pour un import massif initial ou une resynchronisation.</p>
            {:else if categorie === "nouveaux"}
              <p>Uniquement les entrants (présents cible, absents source). KoXo <strong>générera les mots de passe à l'import</strong>.</p>
            {:else}
              <p>Uniquement les sortants (présents source, absents cible). À utiliser pour supprimer les comptes obsolètes côté KoXo.</p>
            {/if}
          {:else}
            {#if categorie === "tous"}
              <p>État complet visé — chaque personne est placée dans son OU définitive (via Table de correspondance).</p>
            {:else if categorie === "nouveaux"}
              <p>Nouveaux comptes Google — placés dans l'<strong>OU pré-rentrée</strong>, mot de passe vide (sera rempli à partir de KoXo au Lot 8b), forçage du changement de MDP à la 1<sup>re</sup> connexion.</p>
            {:else}
              <p>Sortants — à déplacer manuellement vers <code>/7. Sortis/…</code> (l'automatisation viendra plus tard).</p>
            {/if}
            <p class="text-stone-500">Format Google Admin bulk-import : 40 colonnes, UTF-8 avec BOM. Ce CSV se charge dans Admin Google → Utilisateurs → Importer utilisateurs.</p>
          {/if}
        </div>
      </div>
    </div>

    {#if cible === "google" && categorie === "nouveaux"}
      <div class="rounded-lg border-2 border-dashed border-emerald-300 bg-emerald-50/40 p-3 dark:border-emerald-700 dark:bg-emerald-900/10">
        <p class="text-xs font-medium text-emerald-900 dark:text-emerald-200 mb-2">
          Boucle de retour KoXo → Google (Lot 8b)
        </p>
        <p class="text-xs text-stone-700 dark:text-stone-300 mb-2">
          Si tu as déjà importé le CSV KoXo Nouveaux et re-exporté les comptes avec
          leurs mots de passe, dépose ce fichier ici — le CSV Google sera enrichi
          des MDP correspondants. <strong>Aucun MDP n'est stocké côté serveur.</strong>
        </p>
        <label class="inline-flex cursor-pointer items-center gap-2 rounded-lg border border-stone-300 bg-white px-3 py-1.5 text-xs text-stone-700 hover:border-emerald-400 dark:border-stone-600 dark:bg-stone-800 dark:text-stone-300">
          <Upload class="h-3.5 w-3.5" />
          {fichierKoxoEnrichi?.name ?? "Choisir le CSV KoXo (avec MDP)"}
          <input
            type="file"
            accept=".csv"
            onchange={(e) => (fichierKoxoEnrichi = e.target.files?.[0] ?? null)}
            class="hidden"
          />
        </label>
        {#if fichierKoxoEnrichi}
          <button
            class="ml-2 text-xs text-stone-500 hover:text-red-600"
            onclick={() => (fichierKoxoEnrichi = null)}
          >
            × retirer
          </button>
        {/if}
      </div>
    {/if}

    {#if categorie === "nouveaux"}
      <label class="flex items-start gap-2 text-xs text-stone-700 dark:text-stone-300">
        <input
          type="checkbox"
          bind:checked={enregistrerPrevus}
          class="mt-0.5 h-4 w-4 rounded border-stone-300 text-emerald-700 focus:ring-emerald-500"
        />
        <span>
          <strong>Enregistrer le suivi</strong> — inscrit les personnes du fichier
          comme comptes <em>prévus</em> sur cette cible. C'est ce qui alimente
          l'onglet <strong>Suivi</strong> ; tu confirmeras la création réelle
          après l'import.
        </span>
      </label>
    {/if}

    <div class="flex gap-2">
      <button
        class="btn-primary"
        onclick={generer}
        disabled={!siteId || !anneeCibleId || (anneeSourceRequise && !anneeSourceId) || chargement}
      >
        <FileDown class="h-4 w-4" />
        {cible === "google" && fichierKoxoEnrichi ? "Générer Google avec MDP" : "Générer et télécharger"}
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
            {dernierRapport.nb_lignes} ligne(s) — {dernierRapport.cible}, site {dernierRapport.site_nom},
            {dernierRapport.type_personne}s, catégorie {dernierRapport.categorie}
          </p>
          {#if dernierRapport.nb_sans_ou > 0}
            <p class="text-xs text-amber-700 dark:text-amber-400">
              ⚠ {dernierRapport.nb_sans_ou} ligne(s) sans OU — leur classe n'est pas dans la Table de correspondance.
            </p>
          {/if}
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
