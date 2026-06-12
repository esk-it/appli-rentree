<script>
  import { onMount } from "svelte";
  import IdCard from "@lucide/svelte/icons/id-card";
  import Download from "@lucide/svelte/icons/download";
  import FileText from "@lucide/svelte/icons/file-text";
  import Sparkles from "@lucide/svelte/icons/sparkles";
  import Upload from "@lucide/svelte/icons/upload";
  import CheckCircle2 from "@lucide/svelte/icons/check-circle-2";
  import { annees, exports as exportsApi, telechargerFichier } from "$lib/api.js";

  let snapshots = $state(/** @type {Array<{id:number,libelle:string,nb_eleves:number}>} */ ([]));
  let anneeN = $state("");
  let resultat = $state(/** @type {null | any} */ (null));
  let chargement = $state(false);
  let erreur = $state("");

  // Upload optionnel de l'export SmartAir N-1
  let fichierSmartairNom = $state("");
  let contenuSmartairNMoinsUn = $state(/** @type {string|null} */ (null));
  let inputFichier = $state(/** @type {HTMLInputElement|null} */ (null));

  onMount(async () => {
    try {
      snapshots = await annees.lister();
      if (snapshots.length >= 1) anneeN = snapshots[0].libelle;
    } catch (e) {
      erreur = String(e);
    }
  });

  async function chargerSmartairNMoinsUn(e) {
    const f = e.target.files?.[0];
    if (!f) return;
    fichierSmartairNom = f.name;
    contenuSmartairNMoinsUn = await f.text();
  }

  function effacerSmartairNMoinsUn() {
    fichierSmartairNom = "";
    contenuSmartairNMoinsUn = null;
    if (inputFichier) inputFichier.value = "";
  }

  async function genererExports() {
    if (!anneeN) return;
    chargement = true;
    erreur = "";
    resultat = null;
    try {
      resultat = await exportsApi.smartair(anneeN, contenuSmartairNMoinsUn);
    } catch (e) {
      erreur = String(e);
    } finally {
      chargement = false;
    }
  }

  function telecharger(f) {
    telechargerFichier(f.nom, f.contenu, "text/csv");
  }
</script>

<section class="space-y-5">
  <header>
    <h1 class="text-2xl font-semibold text-stone-900">Export SmartAir (JPM)</h1>
    <p class="mt-1 text-sm text-stone-600">
      Génère le CSV à importer dans SmartAir pour la gestion des badges d'accès aux portes.
      Format : séparateur point-virgule, 28 colonnes.
    </p>
  </header>

  <div class="card p-4">
    <div class="flex flex-wrap items-end gap-3">
      <label class="block">
        <span class="text-xs font-medium uppercase tracking-wide text-stone-600">
          Année N (cible)
        </span>
        <select
          bind:value={anneeN}
          class="mt-1 w-48 rounded-lg border border-stone-300 px-3 py-2 text-sm focus:border-emerald-600 focus:outline-none focus:ring-1 focus:ring-emerald-600"
        >
          <option value="">—</option>
          {#each snapshots as s (s.id)}
            <option value={s.libelle}>{s.libelle} ({s.nb_eleves})</option>
          {/each}
        </select>
      </label>

      <button
        class="btn-primary"
        onclick={genererExports}
        disabled={!anneeN || chargement}
      >
        <Sparkles class="h-4 w-4" />
        {chargement ? "Génération…" : "Générer le CSV"}
      </button>
    </div>

    {#if erreur}
      <p class="mt-3 rounded-lg bg-red-50 px-3 py-2 text-sm text-red-700">{erreur}</p>
    {/if}
  </div>

  <!-- Upload optionnel de l'export SmartAir N-1 -->
  <div class="card p-4">
    <h3 class="mb-2 flex items-center gap-2 text-sm font-semibold text-stone-700">
      <Upload class="h-4 w-4 text-stone-500" />
      Export SmartAir précédent (optionnel mais recommandé)
    </h3>
    <p class="mb-3 text-xs text-stone-600">
      Pour préserver les <strong>CardId</strong> hexa (identifiants physiques des badges)
      et calculer correctement les opérations <code>a/b/m</code>, dépose ici un export
      SmartAir de l'année précédente. Sans ça, le CSV généré aura des CardId vides
      et toutes les lignes seront en Op <code>a</code> (ajout).
    </p>

    {#if !fichierSmartairNom}
      <label class="btn-secondary inline-flex cursor-pointer">
        <Upload class="h-4 w-4" />
        Choisir un fichier CSV
        <input
          bind:this={inputFichier}
          type="file"
          accept=".csv,.txt"
          onchange={chargerSmartairNMoinsUn}
          class="hidden"
        />
      </label>
    {:else}
      <div class="flex items-center gap-2 rounded-lg border border-emerald-200 bg-emerald-50 px-3 py-2 text-sm">
        <CheckCircle2 class="h-4 w-4 text-emerald-700" />
        <span class="flex-1 truncate text-emerald-900">{fichierSmartairNom}</span>
        <button
          class="text-xs text-emerald-700 underline hover:text-emerald-900"
          onclick={effacerSmartairNMoinsUn}
        >
          changer
        </button>
      </div>
    {/if}
  </div>

  {#if resultat}
    <div class="card p-4">
      <div class="mb-3 flex items-center justify-between">
        <h2 class="text-sm font-semibold text-stone-700">
          1 fichier prêt
          {#if resultat.a_utilise_n_minus_1}
            <span class="ml-2 inline-flex items-center gap-1 rounded-full bg-emerald-50 px-2 py-0.5 text-xs font-medium text-emerald-800">
              <CheckCircle2 class="h-3 w-3" />
              CardId préservés
            </span>
          {:else}
            <span class="ml-2 inline-flex items-center gap-1 rounded-full bg-amber-50 px-2 py-0.5 text-xs font-medium text-amber-800">
              CardId à scanner
            </span>
          {/if}
        </h2>
      </div>

      <ul class="divide-y divide-stone-100">
        {#each resultat.fichiers as f (f.nom)}
          <li class="flex items-center justify-between gap-4 py-2.5">
            <div class="flex min-w-0 items-center gap-3">
              <FileText class="h-5 w-5 shrink-0 text-sky-600" />
              <div class="min-w-0">
                <p class="truncate text-sm font-medium text-stone-900">{f.nom}</p>
                <p class="truncate text-xs text-stone-500">{f.description}</p>
              </div>
            </div>
            <div class="flex shrink-0 items-center gap-3">
              <span class="rounded-full bg-sky-50 px-2.5 py-0.5 text-xs font-medium text-sky-800">
                {f.nb_lignes.toLocaleString("fr-FR")} ligne(s)
              </span>
              <button
                class="rounded-md p-1.5 text-stone-500 hover:bg-emerald-50 hover:text-emerald-700"
                title="Télécharger"
                onclick={() => telecharger(f)}
              >
                <Download class="h-4 w-4" />
              </button>
            </div>
          </li>
        {/each}
      </ul>
    </div>

    <div class="card p-4">
      <h3 class="mb-2 text-sm font-semibold text-stone-700">Procédure d'import SmartAir</h3>
      <ol class="space-y-1.5 text-sm text-stone-600">
        <li><span class="font-medium text-stone-900">1.</span> Ouvre SmartAir → menu Importation</li>
        <li><span class="font-medium text-stone-900">2.</span> Sélectionne le CSV et lance l'import</li>
        <li><span class="font-medium text-stone-900">3.</span>
          Les lignes en Op <code>a</code> créent des comptes utilisateur ; <code>m</code> modifient
          (changement de groupe / classe) ; <code>b</code> suppriment
        </li>
        <li><span class="font-medium text-stone-900">4.</span>
          Si CardId vides : scanne chaque badge physique avec le lecteur de SmartAir pour
          associer l'identifiant carte au compte
        </li>
      </ol>
    </div>
  {/if}
</section>
