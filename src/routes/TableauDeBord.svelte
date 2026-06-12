<script>
  import { onMount } from "svelte";
  import Database from "@lucide/svelte/icons/database";
  import Users from "@lucide/svelte/icons/users";
  import Building2 from "@lucide/svelte/icons/building-2";
  import Sparkles from "@lucide/svelte/icons/sparkles";
  import Upload from "@lucide/svelte/icons/upload";
  import Download from "@lucide/svelte/icons/download";
  import Package from "@lucide/svelte/icons/package";
  import CheckCircle2 from "@lucide/svelte/icons/check-circle-2";
  import {
    annees,
    etablissements,
    exports as exportsApi,
    telechargerFichierBase64,
  } from "$lib/api.js";

  let listeAnnees = $state(/** @type {any[]} */ ([]));
  let listeEtabs = $state(/** @type {any[]} */ ([]));

  let anneeN = $state("");
  let anneeNMoinsUn = $state("");

  let fichierSmartairNom = $state("");
  let contenuSmartairNMoinsUn = $state(/** @type {string|null} */ (null));
  let inputSmartAir = $state(/** @type {HTMLInputElement|null} */ (null));

  let chargement = $state(false);
  let erreur = $state("");
  let resultat = $state(/** @type {null | any} */ (null));

  let stats = $derived.by(() => {
    if (!listeAnnees.length) return null;
    const total = listeAnnees.reduce((s, a) => s + a.nb_eleves, 0);
    return { total, parAnnee: listeAnnees };
  });

  onMount(rafraichir);

  async function rafraichir() {
    try {
      const [a, e] = await Promise.all([
        annees.lister(),
        etablissements.lister(),
      ]);
      listeAnnees = a;
      listeEtabs = e;
      if (a.length >= 1 && !anneeN) anneeN = a[0].libelle;
      if (a.length >= 2 && !anneeNMoinsUn) anneeNMoinsUn = a[1].libelle;
    } catch (e) {
      erreur = String(e);
    }
  }

  async function chargerSmartair(e) {
    const f = e.target.files?.[0];
    if (!f) return;
    fichierSmartairNom = f.name;
    contenuSmartairNMoinsUn = await f.text();
  }

  function effacerSmartair() {
    fichierSmartairNom = "";
    contenuSmartairNMoinsUn = null;
    if (inputSmartAir) inputSmartAir.value = "";
  }

  async function genererTout() {
    if (!anneeN) return;
    chargement = true;
    erreur = "";
    resultat = null;
    try {
      resultat = await exportsApi.tout(
        anneeN,
        anneeNMoinsUn && anneeNMoinsUn !== anneeN ? anneeNMoinsUn : null,
        contenuSmartairNMoinsUn,
      );
    } catch (e) {
      erreur = String(e);
    } finally {
      chargement = false;
    }
  }

  function telechargerZip() {
    if (!resultat) return;
    telechargerFichierBase64(
      resultat.nom_archive,
      resultat.contenu_base64,
      "application/zip",
    );
  }

  function formaterTaille(octets) {
    if (octets < 1024) return `${octets} o`;
    if (octets < 1024 * 1024) return `${(octets / 1024).toFixed(1)} Ko`;
    return `${(octets / (1024 * 1024)).toFixed(1)} Mo`;
  }

  function fichiersParCible(fichiers) {
    const groupes = {};
    for (const f of fichiers) {
      (groupes[f.cible] = groupes[f.cible] || []).push(f);
    }
    return Object.entries(groupes);
  }
</script>

<section class="space-y-6">
  <header>
    <h1 class="text-2xl font-semibold text-stone-900">Tableau de bord</h1>
    <p class="mt-1 text-sm text-stone-600">
      Vue d'ensemble de tes snapshots et génération en un clic de tous les imports
      pour une rentrée.
    </p>
  </header>

  {#if erreur}
    <p class="rounded-lg bg-red-50 px-3 py-2 text-sm text-red-700">{erreur}</p>
  {/if}

  {#if listeAnnees.length === 0}
    <div class="card p-8 text-center text-stone-500">
      <Database class="mx-auto mb-3 h-10 w-10 text-stone-300" />
      <p>Aucun snapshot en base.</p>
      <p class="mt-1 text-xs">
        Va dans <strong>Snapshots d'années</strong> et importe un export Charlemagne pour démarrer.
      </p>
    </div>
  {:else}
    <!-- Vue d'ensemble -->
    <div class="grid grid-cols-3 gap-3">
      <div class="card p-4">
        <div class="flex items-center gap-2 text-stone-700">
          <Users class="h-4 w-4 text-emerald-700" />
          <span class="text-xs font-semibold uppercase tracking-wide">Élèves en base</span>
        </div>
        <p class="mt-1 text-2xl font-semibold tabular-nums text-stone-900">
          {stats?.total.toLocaleString("fr-FR") ?? "0"}
        </p>
      </div>
      <div class="card p-4">
        <div class="flex items-center gap-2 text-stone-700">
          <Database class="h-4 w-4 text-sky-700" />
          <span class="text-xs font-semibold uppercase tracking-wide">Snapshots</span>
        </div>
        <p class="mt-1 text-2xl font-semibold tabular-nums text-stone-900">
          {listeAnnees.length}
        </p>
        <p class="text-xs text-stone-500">
          {listeAnnees.map((a) => a.libelle).join(", ")}
        </p>
      </div>
      <div class="card p-4">
        <div class="flex items-center gap-2 text-stone-700">
          <Building2 class="h-4 w-4 text-amber-700" />
          <span class="text-xs font-semibold uppercase tracking-wide">Établissements</span>
        </div>
        <p class="mt-1 text-2xl font-semibold tabular-nums text-stone-900">
          {listeEtabs.length}
        </p>
        <p class="text-xs text-stone-500">
          {listeEtabs.map((e) => e.code_court).join(" · ")}
        </p>
      </div>
    </div>

    <!-- Générateur global -->
    <div class="card p-5">
      <h2 class="mb-3 flex items-center gap-2 text-lg font-semibold text-stone-900">
        <Sparkles class="h-5 w-5 text-emerald-700" />
        Générer tous les imports pour une rentrée
      </h2>
      <p class="mb-4 text-sm text-stone-600">
        Lance d'un coup KoXo, PMB, CardStudio, SmartAir et Google Workspace.
        Résultat : un ZIP organisé par cible avec un README récapitulatif.
      </p>

      <div class="grid grid-cols-1 gap-3 md:grid-cols-2">
        <label class="block">
          <span class="text-xs font-medium uppercase tracking-wide text-stone-600">
            Année N (cible)
          </span>
          <select
            bind:value={anneeN}
            class="mt-1 w-full rounded-lg border border-stone-300 px-3 py-2 text-sm focus:border-emerald-600 focus:outline-none focus:ring-1 focus:ring-emerald-600"
          >
            <option value="">—</option>
            {#each listeAnnees as s (s.id)}
              <option value={s.libelle}>{s.libelle} ({s.nb_eleves})</option>
            {/each}
          </select>
        </label>

        <label class="block">
          <span class="text-xs font-medium uppercase tracking-wide text-stone-600">
            Année N-1 (optionnel)
          </span>
          <select
            bind:value={anneeNMoinsUn}
            class="mt-1 w-full rounded-lg border border-stone-300 px-3 py-2 text-sm focus:border-emerald-600 focus:outline-none focus:ring-1 focus:ring-emerald-600"
          >
            <option value="">— (skip Nouveaux/Anciens)</option>
            {#each listeAnnees as s (s.id)}
              <option value={s.libelle}>{s.libelle}</option>
            {/each}
          </select>
        </label>
      </div>

      <div class="mt-3">
        <span class="text-xs font-medium uppercase tracking-wide text-stone-600">
          Export SmartAir précédent (optionnel)
        </span>
        {#if !fichierSmartairNom}
          <label class="btn-secondary mt-1 inline-flex cursor-pointer">
            <Upload class="h-4 w-4" />
            Choisir le CSV
            <input
              bind:this={inputSmartAir}
              type="file"
              accept=".csv,.txt"
              onchange={chargerSmartair}
              class="hidden"
            />
          </label>
        {:else}
          <div class="mt-1 flex items-center gap-2 rounded-lg border border-emerald-200 bg-emerald-50 px-3 py-2 text-sm">
            <CheckCircle2 class="h-4 w-4 text-emerald-700" />
            <span class="flex-1 truncate text-emerald-900">{fichierSmartairNom}</span>
            <button
              class="text-xs text-emerald-700 underline hover:text-emerald-900"
              onclick={effacerSmartair}
            >
              changer
            </button>
          </div>
        {/if}
      </div>

      <div class="mt-5 flex items-center gap-3">
        <button
          class="btn-primary text-base"
          onclick={genererTout}
          disabled={!anneeN || chargement}
        >
          <Package class="h-5 w-5" />
          {chargement ? "Génération en cours…" : "Générer tout (ZIP)"}
        </button>
        {#if chargement}
          <span class="text-sm text-stone-500">
            5 générateurs en parallèle, compte ~5 secondes.
          </span>
        {/if}
      </div>
    </div>

    <!-- Résultat -->
    {#if resultat}
      <div class="card p-5">
        <div class="mb-4 flex items-center justify-between">
          <div>
            <h2 class="text-lg font-semibold text-stone-900">
              {resultat.nom_archive}
            </h2>
            <p class="text-sm text-stone-600">
              {resultat.nb_fichiers} fichiers · {formaterTaille(resultat.taille_octets)}
            </p>
          </div>
          <button class="btn-primary" onclick={telechargerZip}>
            <Download class="h-4 w-4" />
            Télécharger le ZIP
          </button>
        </div>

        <div class="grid grid-cols-1 gap-3 md:grid-cols-2 lg:grid-cols-3">
          {#each fichiersParCible(resultat.fichiers) as [cible, items] (cible)}
            <div class="rounded-lg border border-stone-200 bg-stone-50 p-3">
              <p class="mb-2 text-xs font-semibold uppercase tracking-wide text-stone-700">
                {cible}
              </p>
              <ul class="space-y-1 text-xs text-stone-600">
                {#each items as f (f.nom)}
                  <li class="truncate">
                    {f.nom}
                    <span class="text-stone-400"> · {f.nb_lignes.toLocaleString("fr-FR")} l.</span>
                  </li>
                {/each}
              </ul>
            </div>
          {/each}
        </div>
      </div>
    {/if}
  {/if}
</section>
