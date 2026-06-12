<script>
  import { onMount } from "svelte";
  import Users2 from "@lucide/svelte/icons/users-2";
  import Download from "@lucide/svelte/icons/download";
  import FileText from "@lucide/svelte/icons/file-text";
  import Sparkles from "@lucide/svelte/icons/sparkles";
  import {
    annees,
    exports as exportsApi,
    telechargerFichierBase64,
  } from "$lib/api.js";

  const MIME_XLSX =
    "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet";

  let snapshots = $state(/** @type {Array<{id:number,libelle:string,nb_eleves:number}>} */ ([]));
  let anneeN = $state("");
  let resultat = $state(/** @type {null | { annee_n: string, fichiers: Array<{nom:string,contenu_base64:string,nb_lignes:number,description:string}> }} */ (null));
  let chargement = $state(false);
  let erreur = $state("");

  onMount(async () => {
    try {
      snapshots = await annees.lister();
      if (snapshots.length >= 1) anneeN = snapshots[0].libelle;
    } catch (e) {
      erreur = String(e);
    }
  });

  async function genererExports() {
    if (!anneeN) return;
    chargement = true;
    erreur = "";
    resultat = null;
    try {
      resultat = await exportsApi.cardstudio(anneeN);
    } catch (e) {
      erreur = String(e);
    } finally {
      chargement = false;
    }
  }

  function telecharger(f) {
    telechargerFichierBase64(f.nom, f.contenu_base64, MIME_XLSX);
  }

  function telechargerTout() {
    if (!resultat) return;
    for (const f of resultat.fichiers) telecharger(f);
  }
</script>

<section class="space-y-5">
  <header>
    <h1 class="text-2xl font-semibold text-stone-900">Export CardStudio</h1>
    <p class="mt-1 text-sm text-stone-600">
      Génère les fichiers XLSX à ouvrir dans CardStudio pour imprimer les badges
      visuels des élèves. Un fichier par groupe : KREISKER (lycée NDK général + pro)
      et SAINTE-URSULE (collège SU).
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
        {chargement ? "Génération…" : "Générer les XLSX"}
      </button>
    </div>

    {#if erreur}
      <p class="mt-3 rounded-lg bg-red-50 px-3 py-2 text-sm text-red-700">{erreur}</p>
    {/if}
  </div>

  {#if resultat}
    <div class="card p-4">
      <div class="mb-3 flex items-center justify-between">
        <h2 class="text-sm font-semibold text-stone-700">
          {resultat.fichiers.length} fichier(s) prêt(s)
          <span class="text-stone-500"> · pour {resultat.annee_n}</span>
        </h2>
        <button class="btn-secondary" onclick={telechargerTout}>
          <Download class="h-4 w-4" />
          Tout télécharger
        </button>
      </div>

      <ul class="divide-y divide-stone-100">
        {#each resultat.fichiers as f (f.nom)}
          <li class="flex items-center justify-between gap-4 py-2.5">
            <div class="flex min-w-0 items-center gap-3">
              <FileText class="h-5 w-5 shrink-0 text-emerald-600" />
              <div class="min-w-0">
                <p class="truncate text-sm font-medium text-stone-900">{f.nom}</p>
                <p class="truncate text-xs text-stone-500">{f.description}</p>
              </div>
            </div>
            <div class="flex shrink-0 items-center gap-3">
              <span class="rounded-full bg-emerald-50 px-2.5 py-0.5 text-xs font-medium text-emerald-800">
                {f.nb_lignes.toLocaleString("fr-FR")} ligne(s)
              </span>
              <button
                class="rounded-md p-1.5 text-stone-500 hover:bg-emerald-50 hover:text-emerald-700"
                title="Télécharger ce fichier"
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
      <h3 class="mb-2 text-sm font-semibold text-stone-700">Procédure d'impression CardStudio</h3>
      <ol class="space-y-1.5 text-sm text-stone-600">
        <li>
          <span class="font-medium text-stone-900">1.</span>
          Ouvre CardStudio sur le poste d'impression
        </li>
        <li>
          <span class="font-medium text-stone-900">2.</span>
          Charge le XLSX correspondant au groupe d'élèves à imprimer
        </li>
        <li>
          <span class="font-medium text-stone-900">3.</span>
          Vérifie que les photos sont bien résolues (le chemin UNC dans la
          colonne <em>Photo</em> doit être accessible depuis ce poste)
        </li>
        <li>
          <span class="font-medium text-stone-900">4.</span>
          Lance l'impression par lot
        </li>
      </ol>
      <p class="mt-3 rounded-lg bg-amber-50 p-2 text-xs text-amber-800">
        <strong>Note</strong> : la colonne <em>Chambres</em> est vide pour
        l'instant (donnée pas encore intégrée). À renseigner manuellement dans
        Excel si tu en as besoin avant impression, ou on ajoutera la gestion
        d'attribution des chambres dans une version future.
      </p>
    </div>
  {/if}
</section>
