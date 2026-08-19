<script>
  import { onMount } from "svelte";
  import Zap from "@lucide/svelte/icons/zap";
  import CheckCircle2 from "@lucide/svelte/icons/check-circle-2";
  import AlertTriangle from "@lucide/svelte/icons/alert-triangle";
  import FileDown from "@lucide/svelte/icons/file-down";
  import { annees, enregistrerFichierBase64, simulation } from "$lib/api.js";
  import { notify } from "$lib/toasts.js";

  let listeAnnees = $state([]);
  let anneeSourceId = $state(/** @type {null | number} */ (null));
  let anneeCibleId = $state(/** @type {null | number} */ (null));

  let rapport = $state(/** @type {null | any} */ (null));
  let chargement = $state(false);
  let erreur = $state("");

  onMount(async () => {
    try {
      listeAnnees = await annees.lister();
      if (listeAnnees.length >= 2) {
        anneeCibleId = listeAnnees[0].id;
        anneeSourceId = listeAnnees[1].id;
      }
    } catch (e) {
      erreur = String(e);
    }
  });

  async function lancer() {
    if (!anneeSourceId || !anneeCibleId) return;
    if (anneeSourceId === anneeCibleId) {
      notify.avertissement("Sélectionne deux années différentes");
      return;
    }
    chargement = true;
    erreur = "";
    try {
      rapport = await simulation.obtenir({ anneeSourceId, anneeCibleId });
    } catch (e) {
      erreur = String(e);
      notify.erreur(erreur);
    } finally {
      chargement = false;
    }
  }

  function totaux(cible) {
    return rapport?.totaux_par_cible?.[cible] ?? { nouveaux: 0, identiques: 0, modifies: 0, sortants: 0 };
  }

  async function exporterRapport(format) {
    if (!anneeSourceId || !anneeCibleId) return;
    try {
      const r = await simulation.exporter({ anneeSourceId, anneeCibleId, format });
      const { chemin, annule } = await enregistrerFichierBase64(
        r.nom_fichier,
        r.contenu_base64,
        format === "csv" ? "text/csv" : "text/plain",
      );
      if (annule) return;
      notify.succes(
        `Rapport enregistré — ${chemin ?? `${r.nom_fichier} dans ton dossier Téléchargements`}`,
        { duree: 8000 },
      );
    } catch (e) {
      notify.erreur(String(e));
    }
  }
</script>

<section class="space-y-5">
  <header>
    <h1 class="text-2xl font-semibold text-stone-900 dark:text-stone-100">
      Simulation transverse
    </h1>
    <p class="mt-1 text-sm text-stone-600 dark:text-stone-400">
      Vue unifiée de ce que le programme <strong>ferait</strong> pour un couple
      d'années — toutes cibles confondues. Le point de validation avant de
      générer les exports individuels.
    </p>
  </header>

  <div class="card p-5 space-y-3">
    <div class="grid grid-cols-1 gap-3 md:grid-cols-3">
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
      <label class="block">
        <span class="text-xs font-medium uppercase tracking-wide text-stone-600 dark:text-stone-400">
          Année cible
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
      <div class="self-end">
        <button
          class="btn-primary w-full"
          onclick={lancer}
          disabled={!anneeSourceId || !anneeCibleId || chargement}
        >
          <Zap class="h-4 w-4" />
          Simuler
        </button>
      </div>
    </div>

    {#if erreur}
      <p class="rounded-lg bg-red-50 px-3 py-2 text-sm text-red-700 dark:bg-red-900/30 dark:text-red-300">
        {erreur}
      </p>
    {/if}
  </div>

  {#if rapport}
    <!-- Export du rapport -->
    <div class="flex flex-wrap items-center gap-2">
      <span class="text-xs text-stone-500 dark:text-stone-400">
        Archiver ce rapport pour le comparer l'an prochain :
      </span>
      <button class="btn-secondary text-xs" onclick={() => exporterRapport("texte")}>
        <FileDown class="h-3.5 w-3.5" />
        Texte
      </button>
      <button class="btn-secondary text-xs" onclick={() => exporterRapport("csv")}>
        <FileDown class="h-3.5 w-3.5" />
        CSV
      </button>
    </div>

    <!-- Statut global -->
    {#if rapport.est_pret_a_executer}
      <div class="card border-emerald-200 bg-emerald-50/50 p-4 dark:border-emerald-800 dark:bg-emerald-900/20">
        <div class="flex items-start gap-3">
          <CheckCircle2 class="mt-0.5 h-5 w-5 text-emerald-700 dark:text-emerald-400" />
          <div>
            <p class="font-medium text-emerald-900 dark:text-emerald-200">
              Prêt à exécuter — aucun blocage détecté
            </p>
            <p class="mt-1 text-sm text-stone-700 dark:text-stone-300">
              Va dans <strong>Exports</strong> pour générer les CSV KoXo et Google.
            </p>
          </div>
        </div>
      </div>
    {:else}
      <div class="card border-amber-200 bg-amber-50/50 p-4 dark:border-amber-800 dark:bg-amber-900/20">
        <div class="flex items-start gap-3">
          <AlertTriangle class="mt-0.5 h-5 w-5 text-amber-700 dark:text-amber-400" />
          <div class="flex-1">
            <p class="font-medium text-amber-900 dark:text-amber-200">
              {rapport.blocages.length} blocage(s) à traiter avant exécution
            </p>
            <ul class="mt-2 space-y-1 text-sm text-stone-700 dark:text-stone-300">
              {#each rapport.blocages as b}
                <li>• {b.description}</li>
              {/each}
            </ul>
          </div>
        </div>
      </div>
    {/if}

    <!-- Totaux transverses par cible -->
    <div class="grid grid-cols-1 gap-4 md:grid-cols-2">
      {#each ["koxo", "google"] as cible}
        {@const t = totaux(cible)}
        <div class="card p-4 space-y-3">
          <h3 class="text-sm font-semibold uppercase tracking-wide text-stone-600 dark:text-stone-400">
            {cible === "koxo" ? "KoXo (annuaires réseau)" : "Google Workspace"}
          </h3>
          <div class="grid grid-cols-2 gap-2 text-sm">
            <div class="rounded-lg border border-emerald-200 bg-emerald-50 p-2 dark:border-emerald-800 dark:bg-emerald-900/20">
              <p class="text-xs text-emerald-700 dark:text-emerald-400">À créer</p>
              <p class="text-lg font-semibold tabular-nums text-emerald-800 dark:text-emerald-300">
                +{t.nouveaux}
              </p>
            </div>
            <div class="rounded-lg border border-sky-200 bg-sky-50 p-2 dark:border-sky-800 dark:bg-sky-900/20">
              <p class="text-xs text-sky-700 dark:text-sky-400">À modifier</p>
              <p class="text-lg font-semibold tabular-nums text-sky-800 dark:text-sky-300">
                {t.modifies}
              </p>
            </div>
            <div class="rounded-lg border border-amber-200 bg-amber-50 p-2 dark:border-amber-800 dark:bg-amber-900/20">
              <p class="text-xs text-amber-700 dark:text-amber-400">À sortir</p>
              <p class="text-lg font-semibold tabular-nums text-amber-800 dark:text-amber-300">
                -{t.sortants}
              </p>
            </div>
            <div class="rounded-lg border border-stone-200 bg-stone-50 p-2 dark:border-stone-700 dark:bg-stone-800">
              <p class="text-xs text-stone-500">Inchangés</p>
              <p class="text-lg font-semibold tabular-nums text-stone-600 dark:text-stone-400">
                {t.identiques}
              </p>
            </div>
          </div>
        </div>
      {/each}
    </div>

    <!-- Détail par (site, type, cible) -->
    <div class="card p-4">
      <h3 class="text-sm font-semibold uppercase tracking-wide text-stone-600 dark:text-stone-400 mb-3">
        Détail par site et population
      </h3>
      {#if rapport.lignes.length === 0}
        <p class="text-sm text-stone-500">Aucune opération.</p>
      {:else}
        <div class="overflow-hidden rounded-lg border border-stone-200 dark:border-stone-700">
          <table class="min-w-full divide-y divide-stone-200 text-sm dark:divide-stone-700">
            <thead class="bg-stone-50 text-xs uppercase tracking-wide text-stone-500 dark:bg-stone-800 dark:text-stone-400">
              <tr>
                <th class="px-3 py-2 text-left">Site</th>
                <th class="px-3 py-2 text-left">Type</th>
                <th class="px-3 py-2 text-left">Cible</th>
                <th class="px-3 py-2 text-right">Nouveaux</th>
                <th class="px-3 py-2 text-right">Modifiés</th>
                <th class="px-3 py-2 text-right">Sortants</th>
                <th class="px-3 py-2 text-right">Inchangés</th>
                <th class="px-3 py-2 text-right">Total ops</th>
              </tr>
            </thead>
            <tbody class="divide-y divide-stone-100 dark:divide-stone-800">
              {#each rapport.lignes as l (`${l.site_id}-${l.type_personne}-${l.cible}`)}
                <tr class="hover:bg-stone-50 dark:hover:bg-stone-800/50">
                  <td class="px-3 py-1.5 font-medium">{l.site_nom}</td>
                  <td class="px-3 py-1.5 text-stone-600 dark:text-stone-400">{l.type_personne}</td>
                  <td class="px-3 py-1.5 text-stone-600 dark:text-stone-400">{l.cible}</td>
                  <td class="px-3 py-1.5 text-right tabular-nums text-emerald-700 dark:text-emerald-400">
                    +{l.nouveaux}
                  </td>
                  <td class="px-3 py-1.5 text-right tabular-nums text-sky-700 dark:text-sky-400">
                    {l.modifies}
                  </td>
                  <td class="px-3 py-1.5 text-right tabular-nums text-amber-700 dark:text-amber-400">
                    -{l.sortants}
                  </td>
                  <td class="px-3 py-1.5 text-right tabular-nums text-stone-400">
                    {l.identiques}
                  </td>
                  <td class="px-3 py-1.5 text-right tabular-nums font-semibold">
                    {l.total_operations}
                  </td>
                </tr>
              {/each}
            </tbody>
          </table>
        </div>
      {/if}
    </div>
  {/if}
</section>
