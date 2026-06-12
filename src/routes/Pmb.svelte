<script>
  import { onMount } from "svelte";
  import BookOpen from "@lucide/svelte/icons/book-open";
  import Download from "@lucide/svelte/icons/download";
  import FileText from "@lucide/svelte/icons/file-text";
  import Sparkles from "@lucide/svelte/icons/sparkles";
  import ExternalLink from "@lucide/svelte/icons/external-link";
  import { annees, exports as exportsApi, telechargerFichier } from "$lib/api.js";

  let snapshots = $state(/** @type {Array<{id:number,libelle:string,nb_eleves:number}>} */ ([]));
  let anneeN = $state("");
  let resultat = $state(/** @type {null | { annee_n: string, fichiers: Array<{nom:string,contenu:string,nb_lignes:number,description:string}> }} */ (null));
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
      resultat = await exportsApi.pmb(anneeN);
    } catch (e) {
      erreur = String(e);
    } finally {
      chargement = false;
    }
  }

  function telecharger(f) {
    telechargerFichier(f.nom, f.contenu, "text/csv");
  }

  function telechargerTout() {
    if (!resultat) return;
    for (const f of resultat.fichiers) telecharger(f);
  }

  // Extrait l'URL PMB de la description pour rendre le lien cliquable
  function urlDepuisDescription(desc) {
    const m = desc.match(/https?:\/\/[^\s]+/);
    return m ? m[0] : null;
  }
</script>

<section class="space-y-5">
  <header>
    <h1 class="text-2xl font-semibold text-stone-900">Export PMB</h1>
    <p class="mt-1 text-sm text-stone-600">
      Génère les fichiers CSV à importer dans les deux instances PMB de l'ensemble (collège SU et
      lycée NDK). Format : séparateur point-virgule, UTF-8 BOM.
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
        {chargement ? "Génération…" : "Générer les CSV"}
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
          {@const url = urlDepuisDescription(f.description)}
          <li class="flex items-center justify-between gap-4 py-2.5">
            <div class="flex min-w-0 items-center gap-3">
              <FileText class="h-5 w-5 shrink-0 text-sky-600" />
              <div class="min-w-0">
                <p class="truncate text-sm font-medium text-stone-900">{f.nom}</p>
                <p class="truncate text-xs text-stone-500">
                  {#if url}
                    <a
                      href={url}
                      target="_blank"
                      rel="noopener"
                      class="text-sky-700 hover:underline"
                    >
                      {url}
                      <ExternalLink class="inline h-3 w-3" />
                    </a>
                  {:else}
                    {f.description}
                  {/if}
                </p>
              </div>
            </div>
            <div class="flex shrink-0 items-center gap-3">
              <span class="rounded-full bg-sky-50 px-2.5 py-0.5 text-xs font-medium text-sky-800">
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
      <h3 class="mb-2 text-sm font-semibold text-stone-700">Procédure d'import PMB</h3>
      <ol class="space-y-1.5 text-sm text-stone-600">
        <li>
          <span class="font-medium text-stone-900">1.</span>
          Connecte-toi à l'interface PMB correspondante (URL affichée sur chaque ligne)
        </li>
        <li>
          <span class="font-medium text-stone-900">2.</span>
          Menu <em>Administration</em> → <em>Lecteurs</em> → <em>Import Lecteurs</em>
        </li>
        <li>
          <span class="font-medium text-stone-900">3.</span>
          Sélectionne le CSV correspondant à cette instance (SU ou NDK) et lance l'import
        </li>
        <li>
          <span class="font-medium text-stone-900">4.</span>
          Vérifie le rapport d'import pour repérer d'éventuels doublons ou erreurs
        </li>
      </ol>
      <p class="mt-3 rounded-lg bg-amber-50 p-2 text-xs text-amber-800">
        <strong>Note</strong> : ce format est basé sur le standard PMB (cb, nom, prenom, email…).
        Si PMB rejette des colonnes ou en attend d'autres au premier import, dis-le moi pour
        qu'on ajuste l'exporter.
      </p>
    </div>
  {/if}
</section>
