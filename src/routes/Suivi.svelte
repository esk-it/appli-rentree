<script>
  import { onMount } from "svelte";
  import Activity from "@lucide/svelte/icons/activity";
  import Clock from "@lucide/svelte/icons/clock";
  import Trash2 from "@lucide/svelte/icons/trash-2";
  import { suivi } from "$lib/api.js";
  import { notify } from "$lib/toasts.js";

  let stats = $state(/** @type {null | any} */ (null));
  let purges = $state([]);
  let etatChoisi = $state("actif");
  let liste = $state([]);
  let chargement = $state(false);
  let erreur = $state("");

  const ETATS = ["prevu", "cree", "actif", "quarantaine", "purge"];

  onMount(async () => {
    await charger();
  });

  async function charger() {
    chargement = true;
    erreur = "";
    try {
      [stats, purges, liste] = await Promise.all([
        suivi.stats(),
        suivi.purgesEchues(),
        suivi.lister({ etat: etatChoisi }),
      ]);
    } catch (e) {
      erreur = String(e);
    } finally {
      chargement = false;
    }
  }

  async function changerEtat(e) {
    etatChoisi = e;
    try {
      liste = await suivi.lister({ etat: etatChoisi });
    } catch (err) {
      notify.erreur(String(err));
    }
  }

  function formaterDate(iso) {
    if (!iso) return "—";
    return new Date(iso).toLocaleDateString("fr-FR");
  }
</script>

<section class="space-y-5">
  <header>
    <h1 class="text-2xl font-semibold text-stone-900 dark:text-stone-100">
      Suivi des comptes
    </h1>
    <p class="mt-1 text-sm text-stone-600 dark:text-stone-400">
      Cycle de vie de chaque compte cible : <code>prévu → créé → actif → quarantaine → purge</code>.
      Google passe par une quarantaine de 18 mois avant purge ; les autres cibles sont
      supprimées immédiatement à la sortie.
    </p>
  </header>

  {#if erreur}
    <p class="rounded-lg bg-red-50 px-3 py-2 text-sm text-red-700 dark:bg-red-900/30 dark:text-red-300">
      {erreur}
    </p>
  {/if}

  {#if stats}
    <!-- Cards totaux par état -->
    <div class="grid grid-cols-2 gap-3 md:grid-cols-5">
      {#each ETATS as e}
        <div class="card p-3">
          <p class="text-xs uppercase tracking-wide text-stone-500">{e}</p>
          <p class="text-2xl font-semibold tabular-nums">{stats.total_par_etat[e] ?? 0}</p>
        </div>
      {/each}
    </div>

    <!-- Purges échues -->
    {#if stats.nb_purges_echues > 0}
      <div class="card border-red-200 bg-red-50/50 p-4 dark:border-red-800 dark:bg-red-900/20">
        <div class="flex items-start gap-3">
          <Trash2 class="mt-0.5 h-5 w-5 text-red-700 dark:text-red-400" />
          <div class="flex-1">
            <p class="font-medium text-red-900 dark:text-red-200">
              {stats.nb_purges_echues} compte(s) en quarantaine avec date de purge échue
            </p>
            <p class="mt-1 text-sm text-stone-700 dark:text-stone-300">
              Ces comptes attendent une suppression définitive côté cible. Une
              action de purge (avec confirmation séparée) sera proposée dans un
              prochain lot.
            </p>
            <details class="mt-2">
              <summary class="cursor-pointer text-xs text-red-700 dark:text-red-400">
                Voir la liste ({purges.length})
              </summary>
              <ul class="mt-2 space-y-1 text-xs">
                {#each purges.slice(0, 20) as l}
                  <li>
                    <code>{l.login}</code> — {l.prenom} {l.nom} · {l.cible} · purge prévue {formaterDate(l.date_prevue_purge)}
                  </li>
                {/each}
              </ul>
            </details>
          </div>
        </div>
      </div>
    {/if}

    <!-- Détail par cible × état -->
    <div class="card p-4">
      <h2 class="text-sm font-semibold uppercase tracking-wide text-stone-600 dark:text-stone-400 mb-3">
        Répartition par cible × état
      </h2>
      <div class="overflow-hidden rounded-lg border border-stone-200 dark:border-stone-700">
        <table class="min-w-full divide-y divide-stone-200 text-sm dark:divide-stone-700">
          <thead class="bg-stone-50 text-xs uppercase tracking-wide text-stone-500 dark:bg-stone-800">
            <tr>
              <th class="px-3 py-2 text-left">Cible</th>
              {#each ETATS as e}
                <th class="px-3 py-2 text-right">{e}</th>
              {/each}
            </tr>
          </thead>
          <tbody class="divide-y divide-stone-100 dark:divide-stone-800">
            {#each Object.entries(stats.par_cible) as [cible, valeurs]}
              <tr class="hover:bg-stone-50 dark:hover:bg-stone-800/50">
                <td class="px-3 py-1.5 font-mono text-xs">{cible}</td>
                {#each ETATS as e}
                  <td class="px-3 py-1.5 text-right tabular-nums {valeurs[e] > 0 ? '' : 'text-stone-300'}">
                    {valeurs[e] ?? 0}
                  </td>
                {/each}
              </tr>
            {/each}
          </tbody>
        </table>
      </div>
    </div>

    <!-- Liste filtrée par état -->
    <div class="card p-4">
      <div class="flex items-center gap-2 mb-3">
        <h2 class="text-sm font-semibold uppercase tracking-wide text-stone-600 dark:text-stone-400">
          Comptes en état
        </h2>
        <div class="inline-flex gap-1 rounded-lg border border-stone-200 p-0.5 dark:border-stone-700">
          {#each ETATS as e}
            <button
              class="rounded-md px-2 py-0.5 text-xs font-medium transition
                     {etatChoisi === e ? 'bg-emerald-100 text-emerald-800 dark:bg-emerald-900/40 dark:text-emerald-300' : 'text-stone-500 hover:bg-stone-100 dark:hover:bg-stone-700'}"
              onclick={() => changerEtat(e)}
            >
              {e}
            </button>
          {/each}
        </div>
      </div>

      {#if liste.length === 0}
        <p class="text-sm text-stone-500 py-4 text-center">Aucun compte dans l'état « {etatChoisi} ».</p>
      {:else}
        <div class="overflow-hidden rounded-lg border border-stone-200 dark:border-stone-700">
          <table class="min-w-full divide-y divide-stone-200 text-sm dark:divide-stone-700">
            <thead class="bg-stone-50 text-xs uppercase tracking-wide text-stone-500 dark:bg-stone-800">
              <tr>
                <th class="px-3 py-2 text-left">Personne</th>
                <th class="px-3 py-2 text-left">Login</th>
                <th class="px-3 py-2 text-left">Site</th>
                <th class="px-3 py-2 text-left">Cible</th>
                <th class="px-3 py-2 text-left">Purge prévue</th>
              </tr>
            </thead>
            <tbody class="divide-y divide-stone-100 dark:divide-stone-800">
              {#each liste as l (l.id)}
                <tr class="hover:bg-stone-50 dark:hover:bg-stone-800/50">
                  <td class="px-3 py-1.5">
                    <div>{l.nom} {l.prenom}</div>
                    <div class="text-xs text-stone-500 font-mono">{l.cle_pivot}</div>
                  </td>
                  <td class="px-3 py-1.5 font-mono text-xs">{l.login}</td>
                  <td class="px-3 py-1.5 text-stone-600 dark:text-stone-400">{l.site_nom ?? "—"}</td>
                  <td class="px-3 py-1.5 font-mono text-xs">{l.cible}</td>
                  <td class="px-3 py-1.5 text-xs text-stone-500">{formaterDate(l.date_prevue_purge)}</td>
                </tr>
              {/each}
            </tbody>
          </table>
        </div>
      {/if}
    </div>
  {/if}
</section>
