<script>
  import { onMount } from "svelte";
  import Search from "@lucide/svelte/icons/search";
  import X from "@lucide/svelte/icons/x";
  import UserCircle2 from "@lucide/svelte/icons/user-circle-2";
  import Building2 from "@lucide/svelte/icons/building-2";
  import Mail from "@lucide/svelte/icons/mail";
  import Key from "@lucide/svelte/icons/key";
  import IdCard from "@lucide/svelte/icons/id-card";
  import GraduationCap from "@lucide/svelte/icons/graduation-cap";
  import { annees, eleves as elevesApi } from "$lib/api.js";

  let snapshots = $state(/** @type {any[]} */ ([]));
  let anneeSelectionnee = $state("");
  let liste = $state(/** @type {any[]} */ ([]));
  let chargement = $state(true);
  let erreur = $state("");

  // Filtres
  let recherche = $state("");
  let filtreEtab = $state(/** @type {string[]} */ ([]));
  let filtreRegime = $state(/** @type {string[]} */ ([]));
  let seulementNouveaux = $state(false);

  // Modale
  let eleveSelectionne = $state(/** @type {null | any} */ (null));

  let etabsUniques = $derived([
    ...new Set(liste.map((e) => e.etablissement_code)),
  ].sort());

  let regimesUniques = $derived(
    [...new Set(liste.map((e) => e.code_regime).filter(Boolean))].sort(),
  );

  let listeFiltree = $derived.by(() => {
    let r = liste;
    if (filtreEtab.length) {
      r = r.filter((e) => filtreEtab.includes(e.etablissement_code));
    }
    if (filtreRegime.length) {
      r = r.filter((e) => filtreRegime.includes(e.code_regime));
    }
    if (seulementNouveaux) {
      r = r.filter((e) => e.est_nouveau_charlemagne);
    }
    const q = recherche.trim().toLowerCase();
    if (q) {
      r = r.filter((e) =>
        `${e.nom} ${e.prenom} ${e.code_classe ?? ""} ${e.login_koxo} ${e.email} ${e.num_badge ?? ""}`
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
      liste = await elevesApi.lister(anneeSelectionnee);
    } catch (e) {
      erreur = String(e);
    } finally {
      chargement = false;
    }
  }

  function toggleFiltre(array, value) {
    return array.includes(value)
      ? array.filter((x) => x !== value)
      : [...array, value];
  }
</script>

<section class="space-y-4">
  <header class="flex items-end justify-between gap-4">
    <div>
      <h1 class="text-2xl font-semibold text-stone-900">Liste des élèves</h1>
      <p class="mt-1 text-sm text-stone-600">
        Recherche et explore un snapshot. Clique sur une ligne pour voir le détail
        avec login KoXo / email générés.
      </p>
    </div>
    <select
      bind:value={anneeSelectionnee}
      onchange={charger}
      class="rounded-lg border border-stone-300 px-3 py-2 text-sm focus:border-emerald-600 focus:outline-none focus:ring-1 focus:ring-emerald-600"
    >
      {#each snapshots as s (s.id)}
        <option value={s.libelle}>{s.libelle} ({s.nb_eleves})</option>
      {/each}
    </select>
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
          placeholder="Rechercher (nom, prénom, classe, badge, email…)"
          bind:value={recherche}
          class="w-80 rounded-lg border border-stone-300 py-1.5 pl-8 pr-3 text-sm placeholder:text-stone-400 focus:border-emerald-600 focus:outline-none focus:ring-1 focus:ring-emerald-600"
        />
      </div>
      <div class="flex items-center gap-1">
        {#each etabsUniques as code (code)}
          <button
            class="rounded-full border px-2.5 py-0.5 text-xs font-medium transition
                   {filtreEtab.includes(code)
                     ? 'border-emerald-600 bg-emerald-50 text-emerald-800'
                     : 'border-stone-200 bg-white text-stone-600 hover:border-stone-300'}"
            onclick={() => (filtreEtab = toggleFiltre(filtreEtab, code))}
          >
            {code}
          </button>
        {/each}
      </div>
      <div class="flex items-center gap-1">
        {#each regimesUniques as code (code)}
          <button
            class="rounded-full border px-2.5 py-0.5 text-xs font-medium transition
                   {filtreRegime.includes(code)
                     ? 'border-sky-600 bg-sky-50 text-sky-800'
                     : 'border-stone-200 bg-white text-stone-600 hover:border-stone-300'}"
            onclick={() => (filtreRegime = toggleFiltre(filtreRegime, code))}
          >
            {code}
          </button>
        {/each}
      </div>
      <label class="flex items-center gap-1.5 text-xs text-stone-700">
        <input
          type="checkbox"
          bind:checked={seulementNouveaux}
          class="h-3.5 w-3.5 rounded border-stone-300 text-emerald-700"
        />
        Nouveaux seulement
      </label>
      <span class="ml-auto text-xs text-stone-500 tabular-nums">
        {listeFiltree.length.toLocaleString("fr-FR")} / {liste.length.toLocaleString("fr-FR")}
      </span>
    </div>
  </div>

  <div class="card overflow-hidden">
    {#if chargement}
      <div class="p-8 text-center text-stone-500">Chargement…</div>
    {:else}
      <div class="max-h-[640px] overflow-auto">
        <table class="w-full text-sm">
          <thead class="sticky top-0 z-10 bg-stone-100 text-stone-700">
            <tr>
              <th class="border-b border-stone-200 px-3 py-2 text-left font-semibold">Nom</th>
              <th class="border-b border-stone-200 px-3 py-2 text-left font-semibold">Prénom</th>
              <th class="border-b border-stone-200 px-3 py-2 text-left font-semibold">Étab.</th>
              <th class="border-b border-stone-200 px-3 py-2 text-left font-semibold">Classe</th>
              <th class="border-b border-stone-200 px-3 py-2 text-left font-semibold">Régime</th>
              <th class="border-b border-stone-200 px-3 py-2 text-left font-semibold">Badge</th>
              <th class="border-b border-stone-200 px-3 py-2 text-left font-semibold">Statut</th>
            </tr>
          </thead>
          <tbody>
            {#each listeFiltree as e (e.id)}
              <tr
                class="cursor-pointer border-b border-stone-100 even:bg-stone-50/50 hover:bg-emerald-50/40"
                onclick={() => (eleveSelectionne = e)}
              >
                <td class="whitespace-nowrap px-3 py-1.5 font-medium">{e.nom}</td>
                <td class="whitespace-nowrap px-3 py-1.5">{e.prenom}</td>
                <td class="px-3 py-1.5 text-stone-600">{e.etablissement_code}</td>
                <td class="whitespace-nowrap px-3 py-1.5 text-stone-600">{e.code_classe ?? "—"}</td>
                <td class="px-3 py-1.5 text-stone-600">{e.code_regime ?? "—"}</td>
                <td class="px-3 py-1.5 tabular-nums text-stone-600">{e.num_badge ?? "—"}</td>
                <td class="px-3 py-1.5">
                  {#if e.est_nouveau_charlemagne}
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

{#if eleveSelectionne}
  <div
    class="fixed inset-0 z-50 flex items-center justify-center bg-stone-900/40 p-4"
    role="dialog"
    onclick={() => (eleveSelectionne = null)}
  >
    <div
      class="card max-w-lg w-full space-y-4 p-5"
      onclick={(e) => e.stopPropagation()}
      role="document"
    >
      <div class="flex items-start justify-between gap-3">
        <div class="flex items-start gap-3">
          <UserCircle2 class="h-10 w-10 shrink-0 text-emerald-700" />
          <div>
            <h2 class="text-lg font-semibold text-stone-900">
              {eleveSelectionne.nom} {eleveSelectionne.prenom}
            </h2>
            {#if eleveSelectionne.est_nouveau_charlemagne}
              <span class="badge-nouveau mt-1">Nouvel élève</span>
            {/if}
          </div>
        </div>
        <button
          class="rounded-md p-1 text-stone-400 hover:bg-stone-100 hover:text-stone-700"
          onclick={() => (eleveSelectionne = null)}
        >
          <X class="h-4 w-4" />
        </button>
      </div>

      <dl class="grid grid-cols-1 gap-2 text-sm">
        <div class="flex items-center gap-2 rounded-lg border border-stone-200 bg-stone-50 px-3 py-2">
          <Building2 class="h-4 w-4 text-stone-500" />
          <dt class="font-medium text-stone-700">Établissement</dt>
          <dd class="ml-auto text-stone-900">
            {eleveSelectionne.etablissement_code}
            <span class="text-xs text-stone-500"> — {eleveSelectionne.etablissement_nom}</span>
          </dd>
        </div>
        <div class="flex items-center gap-2 rounded-lg border border-stone-200 bg-stone-50 px-3 py-2">
          <GraduationCap class="h-4 w-4 text-stone-500" />
          <dt class="font-medium text-stone-700">Classe</dt>
          <dd class="ml-auto text-stone-900">
            {eleveSelectionne.code_classe ?? "—"}
            {#if eleveSelectionne.code_niveau}
              <span class="text-xs text-stone-500"> ({eleveSelectionne.code_niveau})</span>
            {/if}
          </dd>
        </div>
        <div class="flex items-center gap-2 rounded-lg border border-stone-200 bg-stone-50 px-3 py-2">
          <IdCard class="h-4 w-4 text-stone-500" />
          <dt class="font-medium text-stone-700">Badge</dt>
          <dd class="ml-auto tabular-nums text-stone-900">{eleveSelectionne.num_badge ?? "—"}</dd>
        </div>
        <div class="flex items-center gap-2 rounded-lg border border-stone-200 bg-stone-50 px-3 py-2">
          <Mail class="h-4 w-4 text-stone-500" />
          <dt class="font-medium text-stone-700">Email</dt>
          <dd class="ml-auto font-mono text-xs text-stone-900">{eleveSelectionne.email}</dd>
        </div>
        <div class="flex items-center gap-2 rounded-lg border border-stone-200 bg-stone-50 px-3 py-2">
          <Key class="h-4 w-4 text-stone-500" />
          <dt class="font-medium text-stone-700">Login KoXo</dt>
          <dd class="ml-auto font-mono text-xs text-stone-900">{eleveSelectionne.login_koxo}</dd>
        </div>
        <div class="flex items-center gap-2 rounded-lg border border-stone-200 bg-stone-50 px-3 py-2">
          <dt class="font-medium text-stone-700">Régime</dt>
          <dd class="ml-auto text-stone-900">{eleveSelectionne.code_regime ?? "—"}</dd>
        </div>
        {#if eleveSelectionne.date_entree}
          <div class="flex items-center gap-2 rounded-lg border border-stone-200 bg-stone-50 px-3 py-2">
            <dt class="font-medium text-stone-700">Date d'entrée</dt>
            <dd class="ml-auto text-stone-900">{eleveSelectionne.date_entree}</dd>
          </div>
        {/if}
      </dl>
    </div>
  </div>
{/if}
