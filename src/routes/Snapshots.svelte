<script>
  import { onMount } from "svelte";
  import Upload from "@lucide/svelte/icons/upload";
  import Sparkles from "@lucide/svelte/icons/sparkles";
  import PlayCircle from "@lucide/svelte/icons/play-circle";
  import AlertTriangle from "@lucide/svelte/icons/alert-triangle";
  import CheckCircle2 from "@lucide/svelte/icons/check-circle-2";
  import { annees, ingestion, sites } from "$lib/api.js";
  import { notify } from "$lib/toasts.js";

  let { onNaviguer = null } = $props();

  let listeAnnees = $state([]);
  let listeSites = $state([]);
  let libelleAnnee = $state("");
  let typePersonne = $state("auto");
  let fichierChoisi = $state(/** @type {File|null} */ (null));

  let rapport = $state(/** @type {null | any} */ (null));
  let chargement = $state(false);
  let erreur = $state("");

  // Suggère une année scolaire par défaut : celle en cours (juillet+ → N/N+1)
  function anneeParDefaut() {
    const m = new Date();
    const y = m.getMonth() >= 6 ? m.getFullYear() : m.getFullYear() - 1;
    return `${y}-${y + 1}`;
  }

  onMount(async () => {
    try {
      listeAnnees = await annees.lister();
      listeSites = await sites.lister();
    } catch (e) {
      erreur = String(e);
    }
    if (!libelleAnnee) libelleAnnee = anneeParDefaut();
  });

  function onSelection(e) {
    fichierChoisi = e.target.files?.[0] ?? null;
  }

  async function lancer(mode) {
    if (!fichierChoisi || !libelleAnnee) return;
    chargement = true;
    erreur = "";
    rapport = null;
    try {
      rapport = await ingestion.ingerer({
        fichier: fichierChoisi,
        libelleAnnee,
        typePersonne,
        mode,
      });
      if (mode === "reel" && !rapport.est_bloquee) {
        notify.succes(
          `${rapport.nb_personnes_creees} créée(s), ${rapport.nb_personnes_mises_a_jour} MAJ, ${rapport.nb_snapshots_crees} snapshot(s)`,
        );
        // Rafraîchit la liste
        listeAnnees = await annees.lister();
      } else if (rapport.est_bloquee) {
        notify.avertissement(
          `Ingestion bloquée : ${rapport.classes_inconnues.length} classe(s) hors table`,
          { duree: 6000 },
        );
      } else {
        notify.info("Simulation terminée — rien n'a été écrit");
      }
    } catch (e) {
      erreur = String(e);
      notify.erreur(erreur);
    } finally {
      chargement = false;
    }
  }

  let siteAmorce = $derived(listeSites.length >= 1);
</script>

<section class="space-y-5">
  <header>
    <h1 class="text-2xl font-semibold text-stone-900 dark:text-stone-100">
      Ingestion Charlemagne
    </h1>
    <p class="mt-1 text-sm text-stone-600 dark:text-stone-400">
      Dépose un export élèves ou adultes. La <strong>simulation</strong> te dit ce qui
      serait fait sans écrire ; le mode <strong>réel</strong> commit après avoir vérifié
      qu'aucune classe n'est absente de la table de correspondance.
    </p>
  </header>

  {#if !siteAmorce}
    <div class="card border-amber-200 bg-amber-50/50 p-4 text-sm dark:border-amber-800 dark:bg-amber-900/20">
      <div class="flex items-start gap-3">
        <AlertTriangle class="mt-0.5 h-5 w-5 text-amber-700 dark:text-amber-400" />
        <div>
          <p class="font-medium text-amber-900 dark:text-amber-200">Amorçage requis</p>
          <p class="mt-1 text-stone-700 dark:text-stone-300">
            Aucun site n'est configuré. Va dans <strong>Sites</strong> pour créer NDE, NDK, SU,
            puis dans <strong>Table de correspondance</strong> pour déclarer les classes.
          </p>
        </div>
      </div>
    </div>
  {/if}

  <div class="card p-5 space-y-4">
    <div class="grid grid-cols-1 gap-3 md:grid-cols-3">
      <label class="block">
        <span class="text-xs font-medium uppercase tracking-wide text-stone-600 dark:text-stone-400">
          Année scolaire
        </span>
        <input
          type="text"
          bind:value={libelleAnnee}
          placeholder="2025-2026"
          class="mt-1 w-full rounded-lg border border-stone-300 px-3 py-2 text-sm dark:border-stone-600 dark:bg-stone-800"
        />
      </label>
      <label class="block">
        <span class="text-xs font-medium uppercase tracking-wide text-stone-600 dark:text-stone-400">
          Type
        </span>
        <select
          bind:value={typePersonne}
          class="mt-1 w-full rounded-lg border border-stone-300 px-3 py-2 text-sm dark:border-stone-600 dark:bg-stone-800"
        >
          <option value="auto">Auto-détection</option>
          <option value="eleve">Élèves</option>
          <option value="adulte">Adultes</option>
        </select>
      </label>
      <label class="block">
        <span class="text-xs font-medium uppercase tracking-wide text-stone-600 dark:text-stone-400">
          Fichier Charlemagne
        </span>
        <label class="btn-secondary mt-1 inline-flex w-full cursor-pointer justify-center">
          <Upload class="h-4 w-4" />
          {fichierChoisi?.name ?? "Choisir un fichier .htm ou .xlsx"}
          <input
            type="file"
            accept=".htm,.html,.xlsx,.xls"
            onchange={onSelection}
            class="hidden"
          />
        </label>
      </label>
    </div>

    <div class="flex gap-2">
      <button
        class="btn-secondary"
        onclick={() => lancer("simulation")}
        disabled={!fichierChoisi || !libelleAnnee || chargement}
      >
        <PlayCircle class="h-4 w-4" />
        Simuler
      </button>
      <button
        class="btn-primary"
        onclick={() => lancer("reel")}
        disabled={!fichierChoisi || !libelleAnnee || chargement}
      >
        <Sparkles class="h-4 w-4" />
        Ingérer (réel)
      </button>
      {#if chargement}
        <span class="self-center text-sm text-stone-500 dark:text-stone-400">Traitement…</span>
      {/if}
    </div>

    {#if erreur}
      <p class="rounded-lg bg-red-50 px-3 py-2 text-sm text-red-700 dark:bg-red-900/30 dark:text-red-300">
        {erreur}
      </p>
    {/if}
  </div>

  {#if rapport}
    <div class="card p-5 space-y-3">
      <div class="flex items-center justify-between">
        <h2 class="text-lg font-semibold text-stone-900 dark:text-stone-100">
          Rapport d'ingestion — {rapport.mode}
        </h2>
        {#if rapport.est_bloquee}
          <span class="inline-flex items-center gap-1 rounded-full bg-red-100 px-2.5 py-0.5 text-xs font-medium text-red-800 dark:bg-red-900/40 dark:text-red-300">
            <AlertTriangle class="h-3.5 w-3.5" />
            Bloqué
          </span>
        {:else if rapport.mode === "simulation"}
          <span class="inline-flex items-center gap-1 rounded-full bg-sky-100 px-2.5 py-0.5 text-xs font-medium text-sky-800 dark:bg-sky-900/40 dark:text-sky-300">
            Simulation
          </span>
        {:else}
          <span class="inline-flex items-center gap-1 rounded-full bg-emerald-100 px-2.5 py-0.5 text-xs font-medium text-emerald-800 dark:bg-emerald-900/40 dark:text-emerald-300">
            <CheckCircle2 class="h-3.5 w-3.5" />
            Committé
          </span>
        {/if}
      </div>

      <div class="grid grid-cols-2 gap-2 text-sm md:grid-cols-4">
        <div class="rounded-lg border border-stone-200 bg-stone-50 p-2 dark:border-stone-700 dark:bg-stone-800">
          <p class="text-xs text-stone-500 dark:text-stone-400">Lignes lues</p>
          <p class="text-lg font-semibold tabular-nums">{rapport.nb_lignes_lues}</p>
        </div>
        <div class="rounded-lg border border-stone-200 bg-stone-50 p-2 dark:border-stone-700 dark:bg-stone-800">
          <p class="text-xs text-stone-500 dark:text-stone-400">Personnes créées</p>
          <p class="text-lg font-semibold tabular-nums text-emerald-700 dark:text-emerald-400">
            +{rapport.nb_personnes_creees}
          </p>
        </div>
        <div class="rounded-lg border border-stone-200 bg-stone-50 p-2 dark:border-stone-700 dark:bg-stone-800">
          <p class="text-xs text-stone-500 dark:text-stone-400">Personnes mises à jour</p>
          <p class="text-lg font-semibold tabular-nums">{rapport.nb_personnes_mises_a_jour}</p>
        </div>
        <div class="rounded-lg border border-stone-200 bg-stone-50 p-2 dark:border-stone-700 dark:bg-stone-800">
          <p class="text-xs text-stone-500 dark:text-stone-400">Snapshots créés</p>
          <p class="text-lg font-semibold tabular-nums">{rapport.nb_snapshots_crees}</p>
          <p class="text-xs text-stone-400">
            ({rapport.nb_snapshots_identiques} inchangés)
          </p>
        </div>
      </div>

      {#if rapport.classes_inconnues?.length > 0}
        <div class="rounded-lg border border-amber-200 bg-amber-50 p-3 text-sm dark:border-amber-800 dark:bg-amber-900/20">
          <p class="font-medium text-amber-900 dark:text-amber-200">
            {rapport.classes_inconnues.length} classe(s) absente(s) de la table de correspondance
          </p>
          <p class="mt-1 text-xs text-stone-700 dark:text-stone-300">
            Ces classes bloquent l'ingestion réelle : déclare-les dans la
            <strong>Table de correspondance</strong>, via le bouton
            « Ajouter une classe ».
          </p>
          <ul class="mt-2 flex flex-wrap gap-1">
            {#each rapport.classes_inconnues as c (c)}
              <li class="rounded bg-amber-100 px-2 py-0.5 font-mono text-xs text-amber-900 dark:bg-amber-900/40 dark:text-amber-300">
                {c}
              </li>
            {/each}
          </ul>
          {#if onNaviguer}
            <button
              class="btn-secondary mt-3 text-xs"
              onclick={() => onNaviguer("table_correspondance")}
            >
              Ouvrir la Table de correspondance
            </button>
          {/if}
        </div>
      {/if}

      {#if rapport.homonymes_intra_export?.length > 0}
        <div class="rounded-lg border border-sky-200 bg-sky-50 p-3 text-sm dark:border-sky-800 dark:bg-sky-900/20">
          <p class="font-medium text-sky-900 dark:text-sky-200">
            {rapport.homonymes_intra_export.length} homonymie(s) détectée(s) dans l'export
          </p>
          <p class="mt-1 text-xs text-stone-700 dark:text-stone-300">
            À arbitrer au Lot 5. Les identités distinctes sont bien créées grâce à la clé pivot.
          </p>
          <ul class="mt-2 space-y-1 text-xs">
            {#each rapport.homonymes_intra_export as h (h.nom_normalise + h.prenom_normalise)}
              <li>
                <code>{h.nom_normalise} {h.prenom_normalise}</code>
                — IDs : {h.ids_charlemagne.join(", ")}
              </li>
            {/each}
          </ul>
        </div>
      {/if}

      {#if rapport.collisions_login?.length > 0}
        <div class="rounded-lg border border-sky-200 bg-sky-50 p-3 text-sm dark:border-sky-800 dark:bg-sky-900/20">
          <p class="font-medium text-sky-900 dark:text-sky-200">
            {rapport.collisions_login.length} collision(s) de login résolue(s) par suffixe
          </p>
          <ul class="mt-2 space-y-1 text-xs">
            {#each rapport.collisions_login as c (c.id_charlemagne)}
              <li>
                <strong>{c.nom} {c.prenom}</strong> (id {c.id_charlemagne})
                : <code>{c.login_base}</code> pris → attribué <code>{c.login_attribue}</code>
              </li>
            {/each}
          </ul>
        </div>
      {/if}

      {#if rapport.avertissements?.length > 0}
        <div class="rounded-lg border-l-4 border-amber-500 bg-amber-50 p-3 text-sm dark:bg-amber-900/20">
          <ul class="space-y-1 text-amber-900 dark:text-amber-200">
            {#each rapport.avertissements as a (a)}
              <li>{a}</li>
            {/each}
          </ul>
        </div>
      {/if}

      {#if rapport.erreurs?.length > 0}
        <div class="rounded-lg border border-red-200 bg-red-50 p-3 text-sm dark:border-red-800 dark:bg-red-900/20">
          <p class="font-medium text-red-900 dark:text-red-200">Erreurs</p>
          <ul class="mt-2 space-y-1 text-xs">
            {#each rapport.erreurs as e (e)}
              <li>{e}</li>
            {/each}
          </ul>
        </div>
      {/if}
    </div>
  {/if}

  {#if listeAnnees.length > 0}
    <div class="card p-4">
      <h3 class="mb-2 text-sm font-semibold text-stone-700 dark:text-stone-300">
        Années en base
      </h3>
      <ul class="space-y-1 text-sm">
        {#each listeAnnees as a (a.id)}
          <li class="flex items-center justify-between">
            <span class="font-medium">{a.libelle}</span>
            <span class="text-xs text-stone-500 dark:text-stone-400 tabular-nums">
              {a.nb_personnes_distinctes} personnes · {a.nb_snapshots} snapshots
            </span>
          </li>
        {/each}
      </ul>
    </div>
  {/if}
</section>
