<script>
  import { onMount } from "svelte";
  import Upload from "@lucide/svelte/icons/upload";
  import Sparkles from "@lucide/svelte/icons/sparkles";
  import PlayCircle from "@lucide/svelte/icons/play-circle";
  import AlertTriangle from "@lucide/svelte/icons/alert-triangle";
  import CheckCircle2 from "@lucide/svelte/icons/check-circle-2";
  import Info from "@lucide/svelte/icons/info";
  import Lock from "@lucide/svelte/icons/lock";
  import { amorcage, sites as sitesApi } from "$lib/api.js";
  import { notify } from "$lib/toasts.js";

  let listeSites = $state([]);
  let siteId = $state(/** @type {null | number} */ (null));
  let typePersonne = $state(/** @type {"eleve"|"adulte"} */ ("eleve"));
  let fichier = $state(/** @type {File|null} */ (null));

  let rapport = $state(/** @type {null | any} */ (null));
  let chargement = $state(false);
  let erreur = $state("");

  onMount(async () => {
    try {
      listeSites = await sitesApi.lister();
      if (listeSites.length === 1) siteId = listeSites[0].id;
    } catch (e) {
      erreur = String(e);
    }
  });

  function onSelection(e) {
    fichier = e.target.files?.[0] ?? null;
    rapport = null;
  }

  async function lancer(mode) {
    if (!fichier || !siteId) return;
    chargement = true;
    erreur = "";
    rapport = null;
    try {
      rapport = await amorcage.koxo({ fichier, siteId, typePersonne, mode });
      if (mode === "reel" && !rapport.est_bloque) {
        notify.succes(
          `+${rapport.nb_creations} créées, ${rapport.nb_deja_presentes} déjà là, ${rapport.nb_conflits_login} conflits`,
        );
      } else if (rapport.est_bloque) {
        notify.erreur(rapport.erreurs.join(" ; "));
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
</script>

<section class="space-y-5">
  <header>
    <h1 class="text-2xl font-semibold text-stone-900 dark:text-stone-100">
      Amorçage
    </h1>
    <p class="mt-1 text-sm text-stone-600 dark:text-stone-400">
      Charge le référentiel <strong>depuis tes comptes KoXo existants</strong> — les
      <code>Personne</code> sont créées avec leurs vrais logins figés, ceux que
      tes utilisateurs connaissent déjà. Étape à faire <strong>avant</strong> la première
      ingestion Charlemagne, pour éviter que le programme régénère des logins
      pour des élèves qui en ont déjà.
    </p>
  </header>

  <div class="card border-emerald-200 bg-emerald-50/50 p-3 text-xs dark:border-emerald-800 dark:bg-emerald-900/20">
    <div class="flex items-start gap-2 text-emerald-900 dark:text-emerald-200">
      <Lock class="mt-0.5 h-4 w-4 shrink-0" />
      <p>
        <strong>Aucun mot de passe n'est stocké.</strong> Si le fichier KoXo en contient
        (colonne « Mot de passe »), ils sont lus pour respecter le format mais
        immédiatement ignorés côté persistance.
      </p>
    </div>
  </div>

  {#if listeSites.length === 0}
    <div class="card border-amber-200 bg-amber-50/50 p-4 text-sm dark:border-amber-800 dark:bg-amber-900/20">
      <div class="flex items-start gap-3">
        <AlertTriangle class="mt-0.5 h-5 w-5 text-amber-700 dark:text-amber-400" />
        <div>
          <p class="font-medium text-amber-900 dark:text-amber-200">Sites requis</p>
          <p class="mt-1 text-stone-700 dark:text-stone-300">
            Crée d'abord les sites NDE, NDK, SU dans l'onglet <strong>Sites</strong>.
          </p>
        </div>
      </div>
    </div>
  {/if}

  <div class="card p-5 space-y-4">
    <div class="grid grid-cols-1 gap-3 md:grid-cols-3">
      <label class="block">
        <span class="text-xs font-medium uppercase tracking-wide text-stone-600 dark:text-stone-400">
          Site KoXo source
        </span>
        <select
          bind:value={siteId}
          class="mt-1 w-full rounded-lg border border-stone-300 px-3 py-2 text-sm dark:border-stone-600 dark:bg-stone-800"
        >
          <option value={null}>— Choisir —</option>
          {#each listeSites as s (s.id)}
            <option value={s.id}>{s.nom} — {s.nom_complet}</option>
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
          Export KoXo (.csv)
        </span>
        <label class="btn-secondary mt-1 inline-flex w-full cursor-pointer justify-center">
          <Upload class="h-4 w-4" />
          {fichier?.name ?? "Choisir un .csv"}
          <input type="file" accept=".csv" onchange={onSelection} class="hidden" />
        </label>
      </label>
    </div>

    <div class="flex flex-wrap gap-2">
      <button
        class="btn-secondary"
        onclick={() => lancer("simulation")}
        disabled={!fichier || !siteId || chargement}
      >
        <PlayCircle class="h-4 w-4" />
        Simuler
      </button>
      <button
        class="btn-primary"
        onclick={() => lancer("reel")}
        disabled={!fichier || !siteId || chargement}
      >
        <Sparkles class="h-4 w-4" />
        Amorcer (réel)
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
    <div class="card p-5 space-y-4">
      <div class="flex items-center justify-between">
        <h2 class="text-lg font-semibold">
          Rapport d'amorçage — {rapport.mode} · <span class="text-stone-500">{rapport.site} / {rapport.type_personne}s</span>
        </h2>
        {#if rapport.est_bloque}
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

      {#if rapport.contient_mots_de_passe}
        <div class="rounded-lg border border-emerald-200 bg-emerald-50 p-3 text-xs dark:border-emerald-800 dark:bg-emerald-900/20">
          <div class="flex items-start gap-2">
            <Info class="mt-0.5 h-4 w-4 text-emerald-700 dark:text-emerald-400 shrink-0" />
            <p class="text-emerald-900 dark:text-emerald-200">
              Le fichier contient une colonne <strong>Mot de passe</strong>. Ces valeurs
              ont été lues pour ne pas casser le mapping, mais <strong>jamais stockées</strong> — le
              référentiel n'est pas un coffre-fort.
            </p>
          </div>
        </div>
      {/if}

      <div class="grid grid-cols-2 gap-2 text-sm md:grid-cols-4">
        <div class="rounded-lg border border-stone-200 bg-stone-50 p-2 dark:border-stone-700 dark:bg-stone-800">
          <p class="text-xs text-stone-500">Lignes lues</p>
          <p class="text-lg font-semibold tabular-nums">{rapport.nb_lignes_lues}</p>
        </div>
        <div class="rounded-lg border border-stone-200 bg-stone-50 p-2 dark:border-stone-700 dark:bg-stone-800">
          <p class="text-xs text-stone-500">Créées</p>
          <p class="text-lg font-semibold tabular-nums text-emerald-700 dark:text-emerald-400">
            +{rapport.nb_creations}
          </p>
        </div>
        <div class="rounded-lg border border-stone-200 bg-stone-50 p-2 dark:border-stone-700 dark:bg-stone-800">
          <p class="text-xs text-stone-500">Déjà présentes</p>
          <p class="text-lg font-semibold tabular-nums">{rapport.nb_deja_presentes}</p>
        </div>
        <div class="rounded-lg border border-stone-200 bg-stone-50 p-2 dark:border-stone-700 dark:bg-stone-800">
          <p class="text-xs text-stone-500">Conflits de login</p>
          <p class="text-lg font-semibold tabular-nums text-amber-700 dark:text-amber-400">
            {rapport.nb_conflits_login}
          </p>
        </div>
      </div>

      {#if rapport.conflits?.length > 0}
        <div class="rounded-lg border border-amber-200 bg-amber-50 p-3 text-sm dark:border-amber-800 dark:bg-amber-900/20">
          <p class="font-medium text-amber-900 dark:text-amber-200">
            {rapport.conflits.length} conflit(s) de login — la base a été conservée
          </p>
          <p class="mt-1 text-xs text-stone-700 dark:text-stone-300">
            Le login est figé à vie. Si le fichier KoXo diverge, la valeur en base
            prime. Ces cas peuvent indiquer un login modifié manuellement à un
            moment dans KoXo — à investiguer.
          </p>
          <ul class="mt-2 space-y-1 text-xs">
            {#each rapport.conflits.slice(0, 20) as c}
              <li>
                <span class="font-mono text-stone-500">L{c.ligne_source}</span>
                — <strong>{c.prenom} {c.nom}</strong> ({c.cle_pivot}) :
                base <code>{c.login_en_base}</code>, fichier <code>{c.login_dans_fichier}</code>
              </li>
            {/each}
            {#if rapport.conflits.length > 20}
              <li class="text-stone-400">… et {rapport.conflits.length - 20} autres</li>
            {/if}
          </ul>
        </div>
      {/if}

      {#if rapport.rejets?.length > 0}
        <details class="rounded-lg border border-stone-200 dark:border-stone-700">
          <summary class="cursor-pointer bg-stone-50 px-3 py-2 text-sm font-medium dark:bg-stone-800">
            {rapport.rejets.length} ligne(s) rejetée(s)
          </summary>
          <ul class="max-h-64 overflow-auto p-3 space-y-1 text-xs">
            {#each rapport.rejets as lr}
              <li>
                <span class="font-mono text-stone-500">L{lr.ligne_source}</span>
                — {lr.raison}
              </li>
            {/each}
          </ul>
        </details>
      {/if}

      {#if rapport.erreurs?.length > 0}
        <div class="rounded-lg border border-red-200 bg-red-50 p-3 text-sm dark:border-red-800 dark:bg-red-900/20">
          <ul class="space-y-1">
            {#each rapport.erreurs as e}
              <li>{e}</li>
            {/each}
          </ul>
        </div>
      {/if}
    </div>
  {/if}
</section>
