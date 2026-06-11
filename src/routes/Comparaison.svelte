<script>
  import { onMount } from "svelte";
  import UserPlus from "@lucide/svelte/icons/user-plus";
  import UserCheck from "@lucide/svelte/icons/user-check";
  import UserMinus from "@lucide/svelte/icons/user-minus";
  import ArrowRight from "@lucide/svelte/icons/arrow-right";
  import Search from "@lucide/svelte/icons/search";
  import { annees, comparaison } from "$lib/api.js";

  let snapshots = $state(/** @type {Array<{id:number,libelle:string,nb_eleves:number}>} */ ([]));
  let anneeN = $state("");
  let anneeNMoinsUn = $state("");

  let resultat = $state(/** @type {null | any} */ (null));
  let chargement = $state(false);
  let erreur = $state("");

  // Filtres
  let recherche = $state("");
  let filtreEtab = $state(/** @type {string[]} */ ([]));

  let etablissementsDisponibles = $derived.by(() => {
    if (!resultat) return [];
    const codes = new Set();
    for (const e of resultat.entrants) codes.add(e.etablissement_code);
    for (const e of resultat.sortants) codes.add(e.etablissement_code);
    for (const r of resultat.restants) codes.add(r.eleve_n.etablissement_code);
    return [...codes].sort();
  });

  onMount(async () => {
    try {
      snapshots = await annees.lister();
      // Pré-sélectionne les deux plus récents
      if (snapshots.length >= 2) {
        anneeN = snapshots[0].libelle;
        anneeNMoinsUn = snapshots[1].libelle;
      } else if (snapshots.length === 1) {
        anneeN = snapshots[0].libelle;
      }
    } catch (e) {
      erreur = String(e);
    }
  });

  async function lancerComparaison() {
    if (!anneeN || !anneeNMoinsUn || anneeN === anneeNMoinsUn) return;
    chargement = true;
    erreur = "";
    try {
      resultat = await comparaison.comparer(anneeN, anneeNMoinsUn);
    } catch (e) {
      erreur = String(e);
      resultat = null;
    } finally {
      chargement = false;
    }
  }

  function appliquerFiltres(/** @type {any[]} */ liste, mode) {
    if (!liste) return [];
    let r = liste;
    if (filtreEtab.length > 0) {
      if (mode === "restant") {
        r = r.filter((x) => filtreEtab.includes(x.eleve_n.etablissement_code));
      } else {
        r = r.filter((x) => filtreEtab.includes(x.etablissement_code));
      }
    }
    const q = recherche.trim().toLowerCase();
    if (q) {
      r = r.filter((x) => {
        const e = mode === "restant" ? x.eleve_n : x;
        const haystack = `${e.nom} ${e.prenom} ${e.code_classe ?? ""}`.toLowerCase();
        return haystack.includes(q);
      });
    }
    return r;
  }

  let entrantsFiltres = $derived(appliquerFiltres(resultat?.entrants, "eleve"));
  let restantsFiltres = $derived(appliquerFiltres(resultat?.restants, "restant"));
  let sortantsFiltres = $derived(appliquerFiltres(resultat?.sortants, "eleve"));
  let restantsAvecChangements = $derived(
    restantsFiltres.filter((r) => r.changements?.length > 0),
  );
</script>

<section class="space-y-5">
  <header>
    <h1 class="text-2xl font-semibold text-stone-900">Comparaison N vs N-1</h1>
    <p class="mt-1 text-sm text-stone-600">
      Compare deux snapshots pour identifier les entrants, restants (avec changements) et sortants.
      Matching par <strong>numéro de badge</strong> (clé stable Charlemagne).
    </p>
  </header>

  <!-- Sélecteurs -->
  <div class="card p-4">
    <div class="flex flex-wrap items-end gap-3">
      <label class="block">
        <span class="text-xs font-medium uppercase tracking-wide text-stone-600">
          Année N (nouvelle rentrée)
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

      <ArrowRight class="mb-2 h-5 w-5 text-stone-400" />

      <label class="block">
        <span class="text-xs font-medium uppercase tracking-wide text-stone-600">
          Année N-1 (précédente)
        </span>
        <select
          bind:value={anneeNMoinsUn}
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
        onclick={lancerComparaison}
        disabled={!anneeN || !anneeNMoinsUn || anneeN === anneeNMoinsUn || chargement}
      >
        {chargement ? "Calcul…" : "Comparer"}
      </button>
    </div>

    {#if snapshots.length < 2}
      <p class="mt-3 rounded-lg bg-amber-50 px-3 py-2 text-sm text-amber-800">
        Il faut au moins <strong>2 snapshots</strong> pour comparer. Va dans
        "Snapshots d'années" et importe une année supplémentaire.
      </p>
    {/if}
    {#if erreur}
      <p class="mt-3 rounded-lg bg-red-50 px-3 py-2 text-sm text-red-700">{erreur}</p>
    {/if}
  </div>

  {#if resultat}
    <!-- Filtres communs -->
    <div class="card p-3">
      <div class="flex flex-wrap items-center gap-3">
        <div class="relative">
          <Search class="absolute left-2.5 top-1/2 h-4 w-4 -translate-y-1/2 text-stone-400" />
          <input
            type="search"
            placeholder="Rechercher (nom, prénom, classe…)"
            bind:value={recherche}
            class="w-72 rounded-lg border border-stone-300 py-1.5 pl-8 pr-3 text-sm placeholder:text-stone-400 focus:border-emerald-600 focus:outline-none focus:ring-1 focus:ring-emerald-600"
          />
        </div>
        <div class="flex flex-wrap items-center gap-1">
          {#each etablissementsDisponibles as code (code)}
            <button
              class="rounded-full border px-2.5 py-0.5 text-xs font-medium transition
                     {filtreEtab.includes(code)
                       ? 'border-emerald-600 bg-emerald-50 text-emerald-800'
                       : 'border-stone-200 bg-white text-stone-600 hover:border-stone-300'}"
              onclick={() => {
                filtreEtab = filtreEtab.includes(code)
                  ? filtreEtab.filter((x) => x !== code)
                  : [...filtreEtab, code];
              }}
            >
              {code}
            </button>
          {/each}
          {#if filtreEtab.length > 0}
            <button
              class="ml-1 text-xs text-stone-500 underline hover:text-stone-700"
              onclick={() => (filtreEtab = [])}
            >
              tout
            </button>
          {/if}
        </div>
      </div>
    </div>

    <!-- Compteurs -->
    <div class="grid grid-cols-3 gap-3">
      <div class="rounded-xl border border-emerald-200 bg-emerald-50 p-4">
        <div class="flex items-center gap-2 text-emerald-800">
          <UserPlus class="h-4 w-4" />
          <span class="text-xs font-semibold uppercase tracking-wide">Entrants</span>
        </div>
        <p class="mt-1 text-2xl font-semibold tabular-nums text-emerald-900">
          {entrantsFiltres.length.toLocaleString("fr-FR")}
          <span class="text-sm font-normal text-emerald-700">
            / {resultat.totaux.entrants.toLocaleString("fr-FR")}
          </span>
        </p>
      </div>
      <div class="rounded-xl border border-sky-200 bg-sky-50 p-4">
        <div class="flex items-center gap-2 text-sky-800">
          <UserCheck class="h-4 w-4" />
          <span class="text-xs font-semibold uppercase tracking-wide">Restants</span>
        </div>
        <p class="mt-1 text-2xl font-semibold tabular-nums text-sky-900">
          {restantsFiltres.length.toLocaleString("fr-FR")}
          <span class="text-sm font-normal text-sky-700">
            / {resultat.totaux.restants.toLocaleString("fr-FR")}
          </span>
        </p>
        <p class="mt-0.5 text-xs text-sky-700">
          dont {restantsAvecChangements.length.toLocaleString("fr-FR")} avec changements
        </p>
      </div>
      <div class="rounded-xl border border-amber-200 bg-amber-50 p-4">
        <div class="flex items-center gap-2 text-amber-800">
          <UserMinus class="h-4 w-4" />
          <span class="text-xs font-semibold uppercase tracking-wide">Sortants</span>
        </div>
        <p class="mt-1 text-2xl font-semibold tabular-nums text-amber-900">
          {sortantsFiltres.length.toLocaleString("fr-FR")}
          <span class="text-sm font-normal text-amber-700">
            / {resultat.totaux.sortants.toLocaleString("fr-FR")}
          </span>
        </p>
      </div>
    </div>

    <!-- Trois colonnes -->
    <div class="grid grid-cols-3 gap-4">
      <!-- Entrants -->
      <div class="card overflow-hidden">
        <div class="border-b border-emerald-200 bg-emerald-50 px-4 py-2 text-sm font-semibold text-emerald-900">
          Entrants
        </div>
        <div class="max-h-[600px] overflow-auto">
          {#if entrantsFiltres.length === 0}
            <p class="p-4 text-center text-sm text-stone-500">Aucun.</p>
          {:else}
            <ul class="divide-y divide-stone-100">
              {#each entrantsFiltres as e (e.id)}
                <li class="px-3 py-2 hover:bg-emerald-50/40">
                  <p class="text-sm font-medium text-stone-900">{e.nom} {e.prenom}</p>
                  <p class="text-xs text-stone-500">
                    <span class="font-medium">{e.etablissement_code}</span>
                    · {e.code_classe ?? "—"} · {e.code_niveau ?? "—"}
                  </p>
                </li>
              {/each}
            </ul>
          {/if}
        </div>
      </div>

      <!-- Restants -->
      <div class="card overflow-hidden">
        <div class="border-b border-sky-200 bg-sky-50 px-4 py-2 text-sm font-semibold text-sky-900">
          Restants
          <span class="ml-2 text-xs font-normal text-sky-700">
            {restantsAvecChangements.length} avec changement(s)
          </span>
        </div>
        <div class="max-h-[600px] overflow-auto">
          {#if restantsFiltres.length === 0}
            <p class="p-4 text-center text-sm text-stone-500">Aucun.</p>
          {:else}
            <ul class="divide-y divide-stone-100">
              {#each restantsFiltres as r (r.eleve_n.id)}
                <li class="px-3 py-2 hover:bg-sky-50/40">
                  <p class="text-sm font-medium text-stone-900">
                    {r.eleve_n.nom} {r.eleve_n.prenom}
                  </p>
                  <p class="text-xs text-stone-500">
                    <span class="font-medium">{r.eleve_n.etablissement_code}</span>
                    · {r.eleve_n.code_classe ?? "—"}
                  </p>
                  {#if r.changements.length > 0}
                    <ul class="mt-1 space-y-0.5">
                      {#each r.changements as c (c.champ)}
                        <li class="text-[11px] text-sky-800">
                          <span class="font-medium">{c.champ}</span> :
                          <span class="line-through text-stone-400">{c.ancien ?? "∅"}</span>
                          → <span class="font-medium">{c.nouveau ?? "∅"}</span>
                        </li>
                      {/each}
                    </ul>
                  {/if}
                </li>
              {/each}
            </ul>
          {/if}
        </div>
      </div>

      <!-- Sortants -->
      <div class="card overflow-hidden">
        <div class="border-b border-amber-200 bg-amber-50 px-4 py-2 text-sm font-semibold text-amber-900">
          Sortants
        </div>
        <div class="max-h-[600px] overflow-auto">
          {#if sortantsFiltres.length === 0}
            <p class="p-4 text-center text-sm text-stone-500">Aucun.</p>
          {:else}
            <ul class="divide-y divide-stone-100">
              {#each sortantsFiltres as e (e.id)}
                <li class="px-3 py-2 hover:bg-amber-50/40">
                  <p class="text-sm font-medium text-stone-900">{e.nom} {e.prenom}</p>
                  <p class="text-xs text-stone-500">
                    <span class="font-medium">{e.etablissement_code}</span>
                    · {e.code_classe ?? "—"} · {e.code_niveau ?? "—"}
                  </p>
                </li>
              {/each}
            </ul>
          {/if}
        </div>
      </div>
    </div>
  {/if}
</section>
