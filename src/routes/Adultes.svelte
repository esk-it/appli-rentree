<script>
  import { onMount } from "svelte";
  import UserCircle2 from "@lucide/svelte/icons/user-circle-2";
  import Search from "@lucide/svelte/icons/search";
  import Upload from "@lucide/svelte/icons/upload";
  import Download from "@lucide/svelte/icons/download";
  import X from "@lucide/svelte/icons/x";
  import Plus from "@lucide/svelte/icons/plus";
  import Sparkles from "@lucide/svelte/icons/sparkles";
  import {
    adultes as adultesApi,
    annees,
    charlemagne,
    exports as exportsApi,
    telechargerFichier,
  } from "$lib/api.js";

  let snapshots = $state(/** @type {any[]} */ ([]));
  let anneeSelectionnee = $state("");
  let liste = $state(/** @type {any[]} */ ([]));
  let chargement = $state(true);
  let erreur = $state("");

  let recherche = $state("");
  let filtreFonction = $state(/** @type {string[]} */ ([]));

  // Modale détail
  let adulteSelectionne = $state(/** @type {null | any} */ (null));

  // Modale d'import
  let importOuvert = $state(false);
  let fichiersDispo = $state(/** @type {any[]} */ ([]));
  let fichierImport = $state("");
  let libelleAnneeImport = $state("");
  let remplacerImport = $state(false);
  let ingestionEnCours = $state(false);
  let messageIngestion = $state("");

  // Modale export adultes
  let exportOuvert = $state(false);
  let exportAnneeN = $state("");
  let exportAnneeN1 = $state("");
  let resultatExport = $state(/** @type {null | any} */ (null));
  let exportEnCours = $state(false);

  let fonctionsUniques = $derived(
    [...new Set(liste.map((a) => a.fonction).filter(Boolean))].sort(),
  );

  let listeFiltree = $derived.by(() => {
    let r = liste;
    if (filtreFonction.length) {
      r = r.filter((a) => filtreFonction.includes(a.fonction));
    }
    const q = recherche.trim().toLowerCase();
    if (q) {
      r = r.filter((a) =>
        `${a.nom} ${a.prenom} ${a.fonction ?? ""} ${a.matieres ?? ""} ${a.email_calcule}`
          .toLowerCase()
          .includes(q),
      );
    }
    return r;
  });

  onMount(async () => {
    try {
      snapshots = await annees.lister();
      if (snapshots.length >= 1) {
        anneeSelectionnee = snapshots[0].libelle;
        exportAnneeN = snapshots[0].libelle;
        if (snapshots.length >= 2) exportAnneeN1 = snapshots[1].libelle;
        await charger();
      } else {
        chargement = false;
      }
    } catch (e) {
      erreur = String(e);
      chargement = false;
    }
  });

  async function charger() {
    chargement = true;
    erreur = "";
    try {
      liste = await adultesApi.lister(anneeSelectionnee);
    } catch (e) {
      erreur = String(e);
    } finally {
      chargement = false;
    }
  }

  async function ouvrirImport() {
    importOuvert = true;
    libelleAnneeImport = anneeSelectionnee || "";
    messageIngestion = "";
    try {
      fichiersDispo = await charlemagne.listerFichiers();
      fichierImport = fichiersDispo[0]?.nom ?? "";
    } catch (e) {
      erreur = String(e);
    }
  }

  async function lancerIngestion() {
    if (!fichierImport || !libelleAnneeImport) return;
    ingestionEnCours = true;
    messageIngestion = "Ingestion en cours…";
    try {
      const res = await adultesApi.ingerer(
        fichierImport,
        libelleAnneeImport,
        remplacerImport,
      );
      messageIngestion = `${res.nb_adultes_inseres} adulte(s) importé(s) pour ${res.libelle}.`;
      // Si on a importé sur l'année courante, on recharge
      if (libelleAnneeImport === anneeSelectionnee) {
        await charger();
      }
      setTimeout(() => (importOuvert = false), 1500);
    } catch (e) {
      messageIngestion = `Échec : ${e instanceof Error ? e.message : e}`;
    } finally {
      ingestionEnCours = false;
    }
  }

  async function lancerExport() {
    if (!exportAnneeN) return;
    exportEnCours = true;
    resultatExport = null;
    try {
      const [koxo, google] = await Promise.all([
        exportsApi.koxoAdultes(
          exportAnneeN,
          exportAnneeN1 && exportAnneeN1 !== exportAnneeN ? exportAnneeN1 : null,
        ),
        exportsApi.googleAdultes(
          exportAnneeN,
          exportAnneeN1 && exportAnneeN1 !== exportAnneeN ? exportAnneeN1 : null,
        ),
      ]);
      resultatExport = {
        koxo: koxo.fichiers,
        google: google.fichiers,
      };
    } catch (e) {
      erreur = String(e);
    } finally {
      exportEnCours = false;
    }
  }

  function telecharger(f) {
    telechargerFichier(f.nom, f.contenu, "text/csv");
  }

  function toggle(arr, value) {
    return arr.includes(value) ? arr.filter((x) => x !== value) : [...arr, value];
  }
</script>

<section class="space-y-4">
  <header class="flex items-end justify-between gap-4">
    <div>
      <h1 class="text-2xl font-semibold text-stone-900">Personnel / Adultes</h1>
      <p class="mt-1 text-sm text-stone-600">
        Gestion des comptes profs, AESH, surveillants, administratifs.
        Pipeline parallèle à celui des élèves : ingestion, comparaison, exports.
      </p>
    </div>
    <div class="flex items-center gap-2">
      <button class="btn-secondary" onclick={ouvrirImport}>
        <Plus class="h-4 w-4" />
        Importer
      </button>
      <button
        class="btn-secondary"
        onclick={() => (exportOuvert = true)}
        disabled={!liste.length}
      >
        <Sparkles class="h-4 w-4" />
        Exporter
      </button>
      <select
        bind:value={anneeSelectionnee}
        onchange={charger}
        class="rounded-lg border border-stone-300 px-3 py-2 text-sm focus:border-emerald-600 focus:outline-none focus:ring-1 focus:ring-emerald-600"
      >
        {#each snapshots as s (s.id)}
          <option value={s.libelle}>{s.libelle}</option>
        {/each}
      </select>
    </div>
  </header>

  {#if erreur}
    <p class="rounded-lg bg-red-50 px-3 py-2 text-sm text-red-700">{erreur}</p>
  {/if}

  <div class="card p-3">
    <div class="flex flex-wrap items-center gap-3">
      <div class="relative">
        <Search class="absolute left-2.5 top-1/2 h-4 w-4 -translate-y-1/2 text-stone-400" />
        <input
          type="search"
          placeholder="Rechercher (nom, fonction, matière, email…)"
          bind:value={recherche}
          class="w-80 rounded-lg border border-stone-300 py-1.5 pl-8 pr-3 text-sm placeholder:text-stone-400 focus:border-emerald-600 focus:outline-none focus:ring-1 focus:ring-emerald-600"
        />
      </div>
      {#each fonctionsUniques as f (f)}
        <button
          class="rounded-full border px-2.5 py-0.5 text-xs font-medium transition
                 {filtreFonction.includes(f)
                   ? 'border-emerald-600 bg-emerald-50 text-emerald-800'
                   : 'border-stone-200 bg-white text-stone-600 hover:border-stone-300'}"
          onclick={() => (filtreFonction = toggle(filtreFonction, f))}
        >
          {f}
        </button>
      {/each}
      <span class="ml-auto text-xs text-stone-500 tabular-nums">
        {listeFiltree.length} / {liste.length}
      </span>
    </div>
  </div>

  <div class="card overflow-hidden">
    {#if chargement}
      <div class="p-8 text-center text-stone-500">Chargement…</div>
    {:else if liste.length === 0}
      <div class="p-8 text-center text-stone-500">
        <UserCircle2 class="mx-auto mb-3 h-10 w-10 text-stone-300" />
        <p>Aucun adulte importé pour {anneeSelectionnee}.</p>
        <p class="mt-1 text-xs">
          Clique <strong>Importer</strong> pour ingérer un export Charlemagne des adultes.
        </p>
      </div>
    {:else}
      <div class="max-h-[600px] overflow-auto">
        <table class="w-full text-sm">
          <thead class="sticky top-0 z-10 bg-stone-100 text-stone-700">
            <tr>
              <th class="border-b border-stone-200 px-3 py-2 text-left font-semibold">Civ.</th>
              <th class="border-b border-stone-200 px-3 py-2 text-left font-semibold">Nom</th>
              <th class="border-b border-stone-200 px-3 py-2 text-left font-semibold">Prénom</th>
              <th class="border-b border-stone-200 px-3 py-2 text-left font-semibold">Fonction</th>
              <th class="border-b border-stone-200 px-3 py-2 text-left font-semibold">Matières</th>
              <th class="border-b border-stone-200 px-3 py-2 text-left font-semibold">Email calculé</th>
              <th class="border-b border-stone-200 px-3 py-2"></th>
            </tr>
          </thead>
          <tbody>
            {#each listeFiltree as a (a.id)}
              <tr
                class="cursor-pointer border-b border-stone-100 even:bg-stone-50/50 hover:bg-emerald-50/40"
                onclick={() => (adulteSelectionne = a)}
              >
                <td class="px-3 py-1.5 text-stone-600">{a.civilite ?? "—"}</td>
                <td class="whitespace-nowrap px-3 py-1.5 font-medium">{a.nom}</td>
                <td class="whitespace-nowrap px-3 py-1.5">{a.prenom}</td>
                <td class="px-3 py-1.5 text-stone-600">{a.fonction ?? "—"}</td>
                <td class="px-3 py-1.5 text-xs text-stone-600">{a.matieres ?? "—"}</td>
                <td class="px-3 py-1.5 font-mono text-xs text-stone-600">{a.email_calcule}</td>
                <td class="px-3 py-1.5">
                  {#if a.est_nouveau_charlemagne}
                    <span class="badge-nouveau">Nouveau</span>
                  {/if}
                </td>
              </tr>
            {/each}
          </tbody>
        </table>
      </div>
    {/if}
  </div>
</section>

<!-- Modale d'import -->
{#if importOuvert}
  <div
    class="fixed inset-0 z-50 flex items-center justify-center bg-stone-900/40 p-4"
    role="dialog"
    onclick={() => (importOuvert = false)}
  >
    <div
      class="card max-w-lg w-full space-y-4 p-5"
      onclick={(e) => e.stopPropagation()}
      role="document"
    >
      <h2 class="text-lg font-semibold text-stone-900">Importer un export adultes</h2>
      <label class="block text-sm">
        <span class="text-xs font-medium uppercase tracking-wide text-stone-600">
          Fichier dans data/input/
        </span>
        <select
          bind:value={fichierImport}
          class="mt-1 w-full rounded-lg border border-stone-300 px-3 py-2 text-sm"
        >
          {#each fichiersDispo as f (f.nom)}
            <option value={f.nom}>{f.nom}</option>
          {/each}
        </select>
      </label>
      <label class="block text-sm">
        <span class="text-xs font-medium uppercase tracking-wide text-stone-600">Année</span>
        <input
          type="text"
          bind:value={libelleAnneeImport}
          placeholder="2025-2026"
          class="mt-1 w-full rounded-lg border border-stone-300 px-3 py-2 text-sm"
        />
      </label>
      <label class="flex items-center gap-2 text-sm">
        <input type="checkbox" bind:checked={remplacerImport} />
        Remplacer les adultes existants pour cette année
      </label>
      {#if messageIngestion}
        <p class="rounded-lg bg-emerald-50 px-3 py-2 text-sm text-emerald-800">
          {messageIngestion}
        </p>
      {/if}
      <div class="flex justify-end gap-2">
        <button class="btn-secondary" onclick={() => (importOuvert = false)} disabled={ingestionEnCours}>
          Annuler
        </button>
        <button class="btn-primary" onclick={lancerIngestion} disabled={ingestionEnCours}>
          {ingestionEnCours ? "Import…" : "Importer"}
        </button>
      </div>
    </div>
  </div>
{/if}

<!-- Modale d'export -->
{#if exportOuvert}
  <div
    class="fixed inset-0 z-50 flex items-center justify-center bg-stone-900/40 p-4"
    role="dialog"
    onclick={() => (exportOuvert = false)}
  >
    <div
      class="card max-w-2xl w-full space-y-4 p-5"
      onclick={(e) => e.stopPropagation()}
      role="document"
    >
      <h2 class="text-lg font-semibold text-stone-900">Exporter les adultes (KoXo + Google)</h2>
      <div class="grid grid-cols-2 gap-3">
        <label class="block text-sm">
          <span class="text-xs font-medium uppercase tracking-wide text-stone-600">Année N</span>
          <select
            bind:value={exportAnneeN}
            class="mt-1 w-full rounded-lg border border-stone-300 px-3 py-2 text-sm"
          >
            {#each snapshots as s (s.id)}
              <option value={s.libelle}>{s.libelle}</option>
            {/each}
          </select>
        </label>
        <label class="block text-sm">
          <span class="text-xs font-medium uppercase tracking-wide text-stone-600">Année N-1 (opt.)</span>
          <select
            bind:value={exportAnneeN1}
            class="mt-1 w-full rounded-lg border border-stone-300 px-3 py-2 text-sm"
          >
            <option value="">—</option>
            {#each snapshots as s (s.id)}
              <option value={s.libelle}>{s.libelle}</option>
            {/each}
          </select>
        </label>
      </div>
      <button class="btn-primary" onclick={lancerExport} disabled={exportEnCours}>
        <Sparkles class="h-4 w-4" />
        {exportEnCours ? "Génération…" : "Générer KoXo + Google"}
      </button>

      {#if resultatExport}
        <div class="space-y-3">
          <div>
            <p class="mb-1 text-xs font-semibold uppercase tracking-wide text-stone-600">KoXo</p>
            {#each resultatExport.koxo as f (f.nom)}
              <button class="flex w-full items-center justify-between rounded-lg border border-stone-200 px-3 py-2 text-sm hover:bg-emerald-50" onclick={() => telecharger(f)}>
                <span class="truncate">{f.nom}</span>
                <span class="ml-2 flex items-center gap-2 text-xs text-stone-500">
                  {f.nb_lignes} l.
                  <Download class="h-3.5 w-3.5" />
                </span>
              </button>
            {/each}
          </div>
          <div>
            <p class="mb-1 text-xs font-semibold uppercase tracking-wide text-stone-600">Google</p>
            {#each resultatExport.google as f (f.nom)}
              <button class="flex w-full items-center justify-between rounded-lg border border-stone-200 px-3 py-2 text-sm hover:bg-emerald-50" onclick={() => telecharger(f)}>
                <span class="truncate">{f.nom}</span>
                <span class="ml-2 flex items-center gap-2 text-xs text-stone-500">
                  {f.nb_lignes} l.
                  <Download class="h-3.5 w-3.5" />
                </span>
              </button>
            {/each}
          </div>
        </div>
      {/if}
    </div>
  </div>
{/if}

<!-- Modale détail -->
{#if adulteSelectionne}
  <div class="fixed inset-0 z-50 flex items-center justify-center bg-stone-900/40 p-4" role="dialog" onclick={() => (adulteSelectionne = null)}>
    <div class="card max-w-lg w-full space-y-4 p-5" onclick={(e) => e.stopPropagation()} role="document">
      <div class="flex items-start justify-between gap-3">
        <div class="flex items-start gap-3">
          <UserCircle2 class="h-10 w-10 shrink-0 text-emerald-700" />
          <div>
            <h2 class="text-lg font-semibold text-stone-900">
              {adulteSelectionne.civilite ?? ""} {adulteSelectionne.nom} {adulteSelectionne.prenom}
            </h2>
            <p class="text-sm text-stone-500">{adulteSelectionne.fonction ?? "—"}</p>
          </div>
        </div>
        <button class="rounded-md p-1 text-stone-400 hover:bg-stone-100 hover:text-stone-700" onclick={() => (adulteSelectionne = null)}>
          <X class="h-4 w-4" />
        </button>
      </div>
      <dl class="space-y-1.5 text-sm">
        {#if adulteSelectionne.matieres}
          <div class="flex justify-between gap-3 rounded-lg border border-stone-200 bg-stone-50 px-3 py-2">
            <dt class="font-medium text-stone-700">Matières</dt>
            <dd class="text-right text-stone-900">{adulteSelectionne.matieres}</dd>
          </div>
        {/if}
        {#if adulteSelectionne.num_personnel}
          <div class="flex justify-between gap-3 rounded-lg border border-stone-200 bg-stone-50 px-3 py-2">
            <dt class="font-medium text-stone-700">N° personnel</dt>
            <dd class="text-stone-900">{adulteSelectionne.num_personnel}</dd>
          </div>
        {/if}
        <div class="flex justify-between gap-3 rounded-lg border border-stone-200 bg-stone-50 px-3 py-2">
          <dt class="font-medium text-stone-700">Login KoXo</dt>
          <dd class="font-mono text-xs text-stone-900">{adulteSelectionne.login_koxo}</dd>
        </div>
        <div class="flex justify-between gap-3 rounded-lg border border-stone-200 bg-stone-50 px-3 py-2">
          <dt class="font-medium text-stone-700">Email calculé</dt>
          <dd class="font-mono text-xs text-stone-900">{adulteSelectionne.email_calcule}</dd>
        </div>
        {#if adulteSelectionne.email_personnel}
          <div class="flex justify-between gap-3 rounded-lg border border-stone-200 bg-stone-50 px-3 py-2">
            <dt class="font-medium text-stone-700">Email personnel</dt>
            <dd class="text-xs text-stone-900">{adulteSelectionne.email_personnel}</dd>
          </div>
        {/if}
      </dl>
    </div>
  </div>
{/if}
