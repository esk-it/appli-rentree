<script>
  import { onMount } from "svelte";
  import Search from "@lucide/svelte/icons/search";
  import X from "@lucide/svelte/icons/x";
  import User from "@lucide/svelte/icons/user";
  import UserCog from "@lucide/svelte/icons/user-cog";
  import { recherche } from "$lib/api.js";

  /** @typedef {Object} Props
   * @property {boolean} ouvert
   * @property {() => void} onFermer
   */
  /** @type {Props} */
  let { ouvert = $bindable(), onFermer } = $props();

  let terme = $state("");
  let resultats = $state(/** @type {null | any} */ (null));
  let chargement = $state(false);
  let inputRef = $state(/** @type {HTMLInputElement|null} */ (null));
  let timer = null;

  // Auto-focus input quand ouvert
  $effect(() => {
    if (ouvert && inputRef) {
      // Petit délai pour laisser le DOM se monter
      setTimeout(() => inputRef?.focus(), 50);
      terme = "";
      resultats = null;
    }
  });

  // Recherche debounced à chaque frappe
  $effect(() => {
    const t = terme.trim();
    if (timer) clearTimeout(timer);
    if (!t) {
      resultats = null;
      return;
    }
    timer = setTimeout(async () => {
      chargement = true;
      try {
        resultats = await recherche.rechercher(t);
      } catch (e) {
        console.error(e);
      } finally {
        chargement = false;
      }
    }, 200);
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
      class="w-full max-w-2xl overflow-hidden rounded-xl bg-white shadow-2xl"
      onclick={(e) => e.stopPropagation()}
      role="document"
    >
      <div class="flex items-center gap-3 border-b border-stone-200 px-4 py-3">
        <Search class="h-5 w-5 text-stone-400" />
        <input
          bind:this={inputRef}
          type="search"
          placeholder="Rechercher un élève ou un adulte par nom, prénom, badge…"
          bind:value={terme}
          class="flex-1 bg-transparent text-sm placeholder:text-stone-400 focus:outline-none"
        />
        <kbd class="rounded border border-stone-300 bg-stone-100 px-1.5 py-0.5 text-[10px] font-medium text-stone-600">
          Échap
        </kbd>
        <button
          class="rounded-md p-1 text-stone-400 hover:bg-stone-100 hover:text-stone-700"
          onclick={onFermer}
        >
          <X class="h-4 w-4" />
        </button>
      </div>

      <div class="max-h-[60vh] overflow-y-auto">
        {#if chargement}
          <div class="p-4 text-center text-sm text-stone-500">Recherche…</div>
        {:else if !resultats}
          <div class="p-6 text-center text-sm text-stone-500">
            <p>Tape au moins 1 caractère pour chercher.</p>
            <p class="mt-2 text-xs text-stone-400">
              Recherche dans <strong>tous les snapshots</strong> par nom, prénom,
              numéro de badge ou numéro de personnel.
            </p>
          </div>
        {:else if resultats.nb_eleves === 0 && resultats.nb_adultes === 0}
          <div class="p-6 text-center text-sm text-stone-500">
            Aucun résultat pour <strong>"{resultats.terme}"</strong>.
          </div>
        {:else}
          {#if resultats.nb_eleves > 0}
            <div>
              <p class="bg-stone-50 px-4 py-1.5 text-[11px] font-semibold uppercase tracking-wide text-stone-600">
                Élèves ({resultats.nb_eleves})
              </p>
              <ul class="divide-y divide-stone-100">
                {#each resultats.eleves as e (e.num_badge ?? `${e.nom}-${e.prenom}`)}
                  <li class="px-4 py-2.5">
                    <div class="flex items-start gap-3">
                      <User class="mt-0.5 h-4 w-4 shrink-0 text-emerald-700" />
                      <div class="min-w-0 flex-1">
                        <p class="text-sm font-medium text-stone-900">
                          {e.nom} {e.prenom}
                          {#if e.num_badge}
                            <span class="ml-1 text-xs font-normal text-stone-500">badge {e.num_badge}</span>
                          {/if}
                        </p>
                        <ul class="mt-1 space-y-0.5">
                          {#each e.apparitions as ap (ap.annee_libelle)}
                            <li class="text-xs text-stone-600">
                              <span class="font-medium text-stone-700">{ap.annee_libelle}</span>
                              · {ap.etablissement_code}
                              · {ap.code_classe ?? "—"}
                              {#if ap.code_regime}<span class="text-stone-400"> · {ap.code_regime}</span>{/if}
                            </li>
                          {/each}
                        </ul>
                      </div>
                    </div>
                  </li>
                {/each}
              </ul>
            </div>
          {/if}

          {#if resultats.nb_adultes > 0}
            <div>
              <p class="bg-stone-50 px-4 py-1.5 text-[11px] font-semibold uppercase tracking-wide text-stone-600">
                Personnel ({resultats.nb_adultes})
              </p>
              <ul class="divide-y divide-stone-100">
                {#each resultats.adultes as a (a.num_personnel ?? `${a.nom}-${a.prenom}`)}
                  <li class="px-4 py-2.5">
                    <div class="flex items-start gap-3">
                      <UserCog class="mt-0.5 h-4 w-4 shrink-0 text-sky-700" />
                      <div class="min-w-0 flex-1">
                        <p class="text-sm font-medium text-stone-900">
                          {a.nom} {a.prenom}
                          {#if a.num_personnel}
                            <span class="ml-1 text-xs font-normal text-stone-500">n° {a.num_personnel}</span>
                          {/if}
                        </p>
                        <ul class="mt-1 space-y-0.5">
                          {#each a.apparitions as ap (ap.annee_libelle)}
                            <li class="text-xs text-stone-600">
                              <span class="font-medium text-stone-700">{ap.annee_libelle}</span>
                              {#if ap.fonction} · {ap.fonction}{/if}
                              {#if ap.matieres} <span class="text-stone-400">· {ap.matieres}</span>{/if}
                            </li>
                          {/each}
                        </ul>
                      </div>
                    </div>
                  </li>
                {/each}
              </ul>
            </div>
          {/if}
        {/if}
      </div>

      <div class="border-t border-stone-200 bg-stone-50 px-4 py-2 text-[10px] text-stone-500">
        Astuce :
        <kbd class="rounded border border-stone-300 bg-white px-1 py-0.5 font-medium">Ctrl</kbd>
        +
        <kbd class="rounded border border-stone-300 bg-white px-1 py-0.5 font-medium">K</kbd>
        pour ouvrir cette palette de n'importe où.
      </div>
    </div>
  </div>
{/if}
