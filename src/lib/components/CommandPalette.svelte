<script>
  import Search from "@lucide/svelte/icons/search";
  import X from "@lucide/svelte/icons/x";
  import User from "@lucide/svelte/icons/user";
  import UserCog from "@lucide/svelte/icons/user-cog";
  import { personnes } from "$lib/api.js";

  /**
   * @typedef {Object} Props
   * @property {boolean} ouvert
   * @property {() => void} onFermer
   */
  /** @type {Props} */
  let { ouvert = $bindable(), onFermer } = $props();

  let terme = $state("");
  let toutes = $state(/** @type {any[]} */ ([]));
  let chargement = $state(false);
  let derniereChargeATime = $state(0);
  let inputRef = $state(/** @type {HTMLInputElement|null} */ (null));

  // Charge la liste complète au premier ouverture (max toutes les 60s)
  async function chargerSiBesoin() {
    const maintenant = Date.now();
    if (maintenant - derniereChargeATime < 60_000 && toutes.length > 0) return;
    chargement = true;
    try {
      toutes = await personnes.lister();
      derniereChargeATime = maintenant;
    } catch (e) {
      console.warn("[palette] chargement personnes échoué :", e);
      toutes = [];
    } finally {
      chargement = false;
    }
  }

  $effect(() => {
    if (ouvert && inputRef) {
      setTimeout(() => inputRef?.focus(), 50);
      terme = "";
      chargerSiBesoin();
    }
  });

  let resultats = $derived.by(() => {
    const q = terme.trim().toLowerCase();
    if (!q) return { eleves: [], adultes: [], nb: 0 };
    const filtree = toutes.filter((p) =>
      `${p.nom} ${p.prenom} ${p.login} ${p.cle_pivot} ${p.badge}`.toLowerCase().includes(q),
    );
    const eleves = filtree.filter((p) => p.type === "eleve").slice(0, 30);
    const adultes = filtree.filter((p) => p.type === "adulte").slice(0, 30);
    return { eleves, adultes, nb: filtree.length };
  });

  function gererTouche(e) {
    if (e.key === "Escape") {
      e.preventDefault();
      onFermer();
    }
  }
</script>

{#if ouvert}
  <div
    class="fixed inset-0 z-[100] flex items-start justify-center bg-stone-900/50 p-4 pt-24"
    role="dialog"
    onclick={onFermer}
    onkeydown={gererTouche}
  >
    <div
      class="w-full max-w-2xl overflow-hidden rounded-xl bg-white shadow-2xl dark:bg-stone-800"
      onclick={(e) => e.stopPropagation()}
      role="document"
    >
      <div class="flex items-center gap-3 border-b border-stone-200 px-4 py-3 dark:border-stone-700">
        <Search class="h-5 w-5 text-stone-400" />
        <input
          bind:this={inputRef}
          type="search"
          placeholder="Rechercher (nom, prénom, login, clé pivot, badge…)"
          bind:value={terme}
          class="flex-1 bg-transparent text-sm placeholder:text-stone-400 focus:outline-none dark:text-stone-200"
        />
        <kbd class="rounded border border-stone-300 bg-stone-100 px-1.5 py-0.5 text-[10px] font-medium text-stone-600 dark:border-stone-600 dark:bg-stone-700 dark:text-stone-300">
          Échap
        </kbd>
        <button
          class="rounded-md p-1 text-stone-400 hover:bg-stone-100 hover:text-stone-700 dark:hover:bg-stone-700 dark:hover:text-stone-200"
          onclick={onFermer}
        >
          <X class="h-4 w-4" />
        </button>
      </div>

      <div class="max-h-[60vh] overflow-y-auto">
        {#if chargement}
          <div class="p-4 text-center text-sm text-stone-500 dark:text-stone-400">Chargement du référentiel…</div>
        {:else if !terme.trim()}
          <div class="p-6 text-center text-sm text-stone-500 dark:text-stone-400">
            <p>Tape au moins 1 caractère pour chercher dans le référentiel.</p>
            <p class="mt-2 text-xs text-stone-400 dark:text-stone-500">
              Recherche dans les <strong>{toutes.length}</strong> personne(s) actuellement en base.
            </p>
          </div>
        {:else if resultats.nb === 0}
          <div class="p-6 text-center text-sm text-stone-500 dark:text-stone-400">
            Aucun résultat.
          </div>
        {:else}
          {#if resultats.eleves.length > 0}
            <p class="bg-stone-50 px-4 py-1.5 text-[11px] font-semibold uppercase tracking-wide text-stone-600 dark:bg-stone-900 dark:text-stone-400">
              Élèves ({resultats.eleves.length})
            </p>
            <ul class="divide-y divide-stone-100 dark:divide-stone-700">
              {#each resultats.eleves as p (p.id)}
                <li class="flex items-start gap-3 px-4 py-2.5">
                  <User class="mt-0.5 h-4 w-4 shrink-0 text-emerald-700 dark:text-emerald-400" />
                  <div class="min-w-0 flex-1">
                    <p class="text-sm font-medium text-stone-900 dark:text-stone-100">
                      {p.nom} {p.prenom}
                      <span class="ml-1 font-mono text-xs font-normal text-stone-500 dark:text-stone-400">
                        {p.cle_pivot} · {p.login}
                      </span>
                    </p>
                    <p class="text-xs text-stone-600 dark:text-stone-400">
                      {p.site ?? "—"} · {p.classe ?? "—"} · badge {p.badge}
                    </p>
                  </div>
                </li>
              {/each}
            </ul>
          {/if}
          {#if resultats.adultes.length > 0}
            <p class="bg-stone-50 px-4 py-1.5 text-[11px] font-semibold uppercase tracking-wide text-stone-600 dark:bg-stone-900 dark:text-stone-400">
              Personnel ({resultats.adultes.length})
            </p>
            <ul class="divide-y divide-stone-100 dark:divide-stone-700">
              {#each resultats.adultes as p (p.id)}
                <li class="flex items-start gap-3 px-4 py-2.5">
                  <UserCog class="mt-0.5 h-4 w-4 shrink-0 text-sky-700 dark:text-sky-400" />
                  <div class="min-w-0 flex-1">
                    <p class="text-sm font-medium text-stone-900 dark:text-stone-100">
                      {p.nom} {p.prenom}
                      <span class="ml-1 font-mono text-xs font-normal text-stone-500 dark:text-stone-400">
                        {p.cle_pivot} · {p.login}
                      </span>
                    </p>
                    <p class="text-xs text-stone-600 dark:text-stone-400">
                      {p.poste_occupe ?? "—"}
                    </p>
                  </div>
                </li>
              {/each}
            </ul>
          {/if}
        {/if}
      </div>

      <div class="border-t border-stone-200 bg-stone-50 px-4 py-2 text-[10px] text-stone-500 dark:border-stone-700 dark:bg-stone-900 dark:text-stone-400">
        <kbd class="rounded border border-stone-300 bg-white px-1 py-0 font-medium dark:border-stone-600 dark:bg-stone-800">Ctrl</kbd>
        +
        <kbd class="rounded border border-stone-300 bg-white px-1 py-0 font-medium dark:border-stone-600 dark:bg-stone-800">K</kbd>
        pour ouvrir cette palette depuis n'importe où.
      </div>
    </div>
  </div>
{/if}
