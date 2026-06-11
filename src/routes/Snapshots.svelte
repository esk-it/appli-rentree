<script>
  import { onMount } from "svelte";
  import Database from "@lucide/svelte/icons/database";
  import Plus from "@lucide/svelte/icons/plus";
  import Trash2 from "@lucide/svelte/icons/trash-2";
  import FileSpreadsheet from "@lucide/svelte/icons/file-spreadsheet";
  import Building2 from "@lucide/svelte/icons/building-2";
  import { annees, charlemagne, etablissements } from "$lib/api.js";

  let listeAnnees = $state(/** @type {Array<{id:number,libelle:string,date_creation:string,est_active:boolean,nb_eleves:number}>} */ ([]));
  let listeEtabs = $state(/** @type {Array<{id:number,code_court:string,nom_long:string,type:string}>} */ ([]));
  let fichiers = $state(/** @type {Array<{nom:string,taille_octets:number}>} */ ([]));

  let chargement = $state(true);
  let erreur = $state("");

  // Modale d'import
  let modaleOuverte = $state(false);
  let fichierSelectionne = $state("");
  let libelleAnnee = $state("");
  let remplacerSiExiste = $state(false);
  let ingestionEnCours = $state(false);
  let messageIngestion = $state("");

  // Suggère un libellé d'année par défaut basé sur la date courante
  function libelleAnneeParDefaut() {
    const m = new Date();
    const annee = m.getMonth() >= 6 ? m.getFullYear() : m.getFullYear() - 1;
    return `${annee}-${annee + 1}`;
  }

  onMount(rafraichir);

  async function rafraichir() {
    chargement = true;
    erreur = "";
    try {
      const [a, e, f] = await Promise.all([
        annees.lister(),
        etablissements.lister(),
        charlemagne.listerFichiers(),
      ]);
      listeAnnees = a;
      listeEtabs = e;
      fichiers = f;
    } catch (err) {
      erreur = String(err);
    } finally {
      chargement = false;
    }
  }

  function ouvrirModale() {
    fichierSelectionne = fichiers[0]?.nom ?? "";
    libelleAnnee = libelleAnneeParDefaut();
    remplacerSiExiste = false;
    messageIngestion = "";
    modaleOuverte = true;
  }

  async function lancerIngestion() {
    if (!fichierSelectionne || !libelleAnnee) return;
    ingestionEnCours = true;
    messageIngestion = "Ingestion en cours…";
    try {
      const res = await charlemagne.ingerer(
        fichierSelectionne,
        libelleAnnee,
        remplacerSiExiste,
      );
      messageIngestion = `${res.nb_eleves_inseres} élève(s) importé(s) pour ${res.libelle}.`;
      await rafraichir();
      // Petite pause pour voir le succès, puis fermeture
      setTimeout(() => (modaleOuverte = false), 1500);
    } catch (e) {
      messageIngestion = `Échec : ${e instanceof Error ? e.message : e}`;
    } finally {
      ingestionEnCours = false;
    }
  }

  async function supprimerSnapshot(id, libelle) {
    if (!confirm(`Supprimer définitivement le snapshot "${libelle}" et tous ses élèves ?`)) {
      return;
    }
    try {
      await annees.supprimer(id);
      await rafraichir();
    } catch (e) {
      erreur = String(e);
    }
  }

  function formaterDate(iso) {
    try {
      const d = new Date(iso);
      return d.toLocaleString("fr-FR", {
        day: "2-digit",
        month: "2-digit",
        year: "numeric",
        hour: "2-digit",
        minute: "2-digit",
      });
    } catch {
      return iso;
    }
  }
</script>

<section class="space-y-6">
  <header class="flex items-end justify-between gap-4">
    <div>
      <h1 class="text-2xl font-semibold text-stone-900">Snapshots d'années</h1>
      <p class="mt-1 text-sm text-stone-600">
        Chaque snapshot est un export Charlemagne ingéré pour une année scolaire donnée.
        Les snapshots servent de base à la comparaison N vs N-1 (entrants / restants / sortants).
      </p>
    </div>
    <button
      class="btn-primary"
      onclick={ouvrirModale}
      disabled={fichiers.length === 0}
    >
      <Plus class="h-4 w-4" />
      Importer un export
    </button>
  </header>

  {#if erreur}
    <p class="rounded-lg bg-red-50 px-3 py-2 text-sm text-red-700">{erreur}</p>
  {/if}

  <!-- Liste des établissements détectés -->
  {#if listeEtabs.length > 0}
    <div class="card p-4">
      <div class="mb-3 flex items-center gap-2 text-sm font-semibold text-stone-700">
        <Building2 class="h-4 w-4 text-stone-500" />
        Établissements détectés ({listeEtabs.length})
      </div>
      <div class="flex flex-wrap gap-2">
        {#each listeEtabs as e (e.id)}
          <span class="rounded-full border border-stone-200 bg-stone-50 px-3 py-1 text-xs text-stone-700">
            <strong>{e.code_court}</strong>
            <span class="text-stone-500">— {e.nom_long}</span>
          </span>
        {/each}
      </div>
    </div>
  {/if}

  <!-- Liste des snapshots -->
  <div class="card overflow-hidden">
    {#if chargement}
      <div class="p-8 text-center text-stone-500">Chargement…</div>
    {:else if listeAnnees.length === 0}
      <div class="p-8 text-center text-stone-500">
        <Database class="mx-auto mb-3 h-10 w-10 text-stone-300" />
        <p>Aucun snapshot pour l'instant.</p>
        <p class="mt-1 text-xs">
          Dépose un export Charlemagne dans <code>data/input/</code> via l'Accueil,
          puis clique « Importer un export » ci-dessus.
        </p>
      </div>
    {:else}
      <table class="w-full text-sm">
        <thead class="bg-stone-50 text-stone-700">
          <tr>
            <th class="border-b border-stone-200 px-4 py-2 text-left font-semibold">Libellé année</th>
            <th class="border-b border-stone-200 px-4 py-2 text-left font-semibold">Date de création</th>
            <th class="border-b border-stone-200 px-4 py-2 text-right font-semibold">Élèves</th>
            <th class="border-b border-stone-200 px-4 py-2 text-center font-semibold">Active</th>
            <th class="border-b border-stone-200 px-4 py-2"></th>
          </tr>
        </thead>
        <tbody>
          {#each listeAnnees as a (a.id)}
            <tr class="border-b border-stone-100 hover:bg-emerald-50/30">
              <td class="px-4 py-2 font-medium">{a.libelle}</td>
              <td class="px-4 py-2 text-stone-600">{formaterDate(a.date_creation)}</td>
              <td class="px-4 py-2 text-right tabular-nums">{a.nb_eleves.toLocaleString("fr-FR")}</td>
              <td class="px-4 py-2 text-center">
                {#if a.est_active}
                  <span class="rounded-full bg-emerald-100 px-2 py-0.5 text-xs font-medium text-emerald-800">oui</span>
                {:else}
                  <span class="text-xs text-stone-400">archivée</span>
                {/if}
              </td>
              <td class="px-4 py-2 text-right">
                <button
                  class="rounded-md p-1 text-stone-400 hover:bg-red-50 hover:text-red-600"
                  title="Supprimer ce snapshot"
                  onclick={() => supprimerSnapshot(a.id, a.libelle)}
                >
                  <Trash2 class="h-4 w-4" />
                </button>
              </td>
            </tr>
          {/each}
        </tbody>
      </table>
    {/if}
  </div>
</section>

<!-- Modale d'import -->
{#if modaleOuverte}
  <div
    class="fixed inset-0 z-50 flex items-center justify-center bg-stone-900/40 p-4"
    role="dialog"
  >
    <div class="card max-w-lg w-full space-y-4 p-5">
      <h2 class="text-lg font-semibold text-stone-900">Importer un export Charlemagne</h2>

      <label class="block">
        <span class="text-xs font-medium uppercase tracking-wide text-stone-600">
          Fichier à importer
        </span>
        <select
          bind:value={fichierSelectionne}
          class="mt-1 w-full rounded-lg border border-stone-300 px-3 py-2 text-sm focus:border-emerald-600 focus:outline-none focus:ring-1 focus:ring-emerald-600"
        >
          {#each fichiers as f (f.nom)}
            <option value={f.nom}>{f.nom}</option>
          {/each}
        </select>
        <span class="mt-1 block text-xs text-stone-500">
          <FileSpreadsheet class="inline h-3 w-3" />
          Fichiers détectés dans <code>data/input/</code>
        </span>
      </label>

      <label class="block">
        <span class="text-xs font-medium uppercase tracking-wide text-stone-600">
          Libellé d'année scolaire
        </span>
        <input
          type="text"
          bind:value={libelleAnnee}
          placeholder="2025-2026"
          class="mt-1 w-full rounded-lg border border-stone-300 px-3 py-2 text-sm focus:border-emerald-600 focus:outline-none focus:ring-1 focus:ring-emerald-600"
        />
      </label>

      <label class="flex items-start gap-2 text-sm text-stone-700">
        <input
          type="checkbox"
          bind:checked={remplacerSiExiste}
          class="mt-0.5 h-4 w-4 rounded border-stone-300 text-emerald-700 focus:ring-emerald-500"
        />
        <span>
          Remplacer si ce libellé existe déjà
          <span class="block text-xs text-stone-500">
            Vide les élèves existants pour ce libellé avant l'import (utile pour corriger un import partiel).
          </span>
        </span>
      </label>

      {#if messageIngestion}
        <p class="rounded-lg bg-emerald-50 px-3 py-2 text-sm text-emerald-800">
          {messageIngestion}
        </p>
      {/if}

      <div class="flex justify-end gap-2 pt-2">
        <button
          class="btn-secondary"
          onclick={() => (modaleOuverte = false)}
          disabled={ingestionEnCours}
        >
          Annuler
        </button>
        <button
          class="btn-primary"
          onclick={lancerIngestion}
          disabled={ingestionEnCours || !fichierSelectionne || !libelleAnnee}
        >
          {ingestionEnCours ? "Import…" : "Importer"}
        </button>
      </div>
    </div>
  </div>
{/if}
