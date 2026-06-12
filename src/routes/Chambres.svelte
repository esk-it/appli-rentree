<script>
  import { onMount } from "svelte";
  import BedDouble from "@lucide/svelte/icons/bed-double";
  import Plus from "@lucide/svelte/icons/plus";
  import Trash2 from "@lucide/svelte/icons/trash-2";
  import Pencil from "@lucide/svelte/icons/pencil";
  import UserPlus from "@lucide/svelte/icons/user-plus";
  import UserMinus from "@lucide/svelte/icons/user-minus";
  import Search from "@lucide/svelte/icons/search";
  import {
    annees,
    chambres as chambresApi,
    eleves as elevesApi,
  } from "$lib/api.js";

  let snapshots = $state(/** @type {any[]} */ ([]));
  let anneeSelectionnee = $state("");
  let listeChambres = $state(/** @type {any[]} */ ([]));
  let listeEleves = $state(/** @type {any[]} */ ([]));
  let affectations = $state(/** @type {Record<string, any>} */ ({}));
  let chargement = $state(true);
  let erreur = $state("");

  // Édition chambre
  let modaleChambre = $state(/** @type {null | any} */ (null));
  let formChambre = $state({
    numero: "",
    batiment: "",
    etage: "",
    capacite_max: 1,
    notes: "",
  });

  // Recherche élève pour affectation
  let chambreActive = $state(/** @type {null | any} */ (null));
  let rechercheEleve = $state("");

  let internesNonAffectes = $derived.by(() => {
    // Internat = code_regime 'P'
    return listeEleves.filter(
      (e) =>
        e.code_regime === "P" && !affectations[String(e.id)],
    );
  });

  let affectesACetteChambre = $derived.by(() => {
    if (!chambreActive) return [];
    return listeEleves.filter(
      (e) => affectations[String(e.id)]?.chambre_id === chambreActive.id,
    );
  });

  let internesNonAffectesFiltres = $derived.by(() => {
    const q = rechercheEleve.trim().toLowerCase();
    if (!q) return internesNonAffectes;
    return internesNonAffectes.filter((e) =>
      `${e.nom} ${e.prenom} ${e.code_classe ?? ""}`.toLowerCase().includes(q),
    );
  });

  onMount(async () => {
    try {
      snapshots = await annees.lister();
      if (snapshots.length >= 1) {
        anneeSelectionnee = snapshots[0].libelle;
        await rafraichir();
      } else {
        chargement = false;
      }
    } catch (e) {
      erreur = String(e);
      chargement = false;
    }
  });

  async function rafraichir() {
    chargement = true;
    try {
      const [c, el, af] = await Promise.all([
        chambresApi.lister(anneeSelectionnee),
        elevesApi.lister(anneeSelectionnee),
        chambresApi.listerAffectations(anneeSelectionnee),
      ]);
      listeChambres = c;
      listeEleves = el;
      affectations = af;
    } catch (e) {
      erreur = String(e);
    } finally {
      chargement = false;
    }
  }

  function ouvrirNouvelle() {
    formChambre = {
      numero: "",
      batiment: "",
      etage: "",
      capacite_max: 1,
      notes: "",
    };
    modaleChambre = { mode: "creer" };
  }

  function ouvrirEdition(c) {
    formChambre = {
      numero: c.numero,
      batiment: c.batiment ?? "",
      etage: c.etage ?? "",
      capacite_max: c.capacite_max,
      notes: c.notes ?? "",
    };
    modaleChambre = { mode: "editer", id: c.id };
  }

  async function sauvegarderChambre() {
    try {
      if (modaleChambre.mode === "creer") {
        await chambresApi.creer({
          ...formChambre,
          capacite_max: parseInt(formChambre.capacite_max) || 1,
        });
      } else {
        await chambresApi.modifier(modaleChambre.id, {
          ...formChambre,
          capacite_max: parseInt(formChambre.capacite_max) || 1,
        });
      }
      modaleChambre = null;
      await rafraichir();
    } catch (e) {
      erreur = String(e);
    }
  }

  async function supprimerChambre(c) {
    if (!confirm(`Supprimer la chambre ${c.numero} et toutes ses affectations ?`)) {
      return;
    }
    try {
      await chambresApi.supprimer(c.id);
      if (chambreActive?.id === c.id) chambreActive = null;
      await rafraichir();
    } catch (e) {
      erreur = String(e);
    }
  }

  async function affecter(eleveId, chambreId) {
    try {
      await chambresApi.affecter(eleveId, chambreId);
      await rafraichir();
    } catch (e) {
      erreur = String(e);
    }
  }
</script>

<section class="space-y-4">
  <header class="flex items-end justify-between gap-4">
    <div>
      <h1 class="text-2xl font-semibold text-stone-900">Chambres internat</h1>
      <p class="mt-1 text-sm text-stone-600">
        Déclare les chambres physiques disponibles et affecte les élèves internes
        (régime "P"). La colonne <em>Chambres</em> du fichier CardStudio sera renseignée
        automatiquement à partir d'ici.
      </p>
    </div>
    <div class="flex items-center gap-2">
      <button class="btn-primary" onclick={ouvrirNouvelle}>
        <Plus class="h-4 w-4" />
        Nouvelle chambre
      </button>
      <select
        bind:value={anneeSelectionnee}
        onchange={rafraichir}
        class="rounded-lg border border-stone-300 px-3 py-2 text-sm focus:border-emerald-600 focus:outline-none focus:ring-1 focus:ring-emerald-600"
      >
        {#each snapshots as s (s.id)}
          <option value={s.libelle}>{s.libelle}</option>
        {/each}
      </select>
    </div>
  </header>

  {#if erreur}
    <p class="rounded-lg bg-red-50 px-3 py-2 text-sm text-red-700">{erreur}</p>
  {/if}

  <div class="grid grid-cols-2 gap-3">
    <div class="card p-4">
      <p class="text-xs font-semibold uppercase tracking-wide text-stone-600">
        Chambres déclarées
      </p>
      <p class="mt-1 text-2xl font-semibold tabular-nums">{listeChambres.length}</p>
      <p class="text-xs text-stone-500">
        Capacité totale : {listeChambres.reduce((s, c) => s + c.capacite_max, 0)} lits
      </p>
    </div>
    <div class="card p-4">
      <p class="text-xs font-semibold uppercase tracking-wide text-stone-600">
        Internes ({anneeSelectionnee})
      </p>
      <p class="mt-1 text-2xl font-semibold tabular-nums">
        {listeEleves.filter((e) => e.code_regime === "P").length}
      </p>
      <p class="text-xs text-stone-500">
        Non affectés : {internesNonAffectes.length}
      </p>
    </div>
  </div>

  <div class="grid grid-cols-2 gap-4">
    <!-- Liste des chambres -->
    <div class="card overflow-hidden">
      <div class="border-b border-stone-200 bg-stone-50 px-4 py-2 text-sm font-semibold text-stone-700">
        Chambres
      </div>
      {#if chargement}
        <div class="p-6 text-center text-stone-500">Chargement…</div>
      {:else if listeChambres.length === 0}
        <div class="p-6 text-center text-stone-500">
          <BedDouble class="mx-auto mb-3 h-8 w-8 text-stone-300" />
          <p>Pas encore de chambres. Clique "Nouvelle chambre" pour commencer.</p>
        </div>
      {:else}
        <div class="max-h-[520px] overflow-auto">
          <ul class="divide-y divide-stone-100">
            {#each listeChambres as c (c.id)}
              {@const surcapacite = c.nb_occupants > c.capacite_max}
              <li>
                <div
                  role="button"
                  tabindex="0"
                  class="flex w-full cursor-pointer items-start justify-between gap-3 px-3 py-2 text-left hover:bg-emerald-50/40 {chambreActive?.id === c.id ? 'bg-emerald-50' : ''}"
                  onclick={() => (chambreActive = c)}
                  onkeydown={(e) => {
                    if (e.key === "Enter" || e.key === " ") {
                      e.preventDefault();
                      chambreActive = c;
                    }
                  }}
                >
                  <div class="flex-1">
                    <p class="text-sm font-medium text-stone-900">
                      Ch. {c.numero}
                      {#if c.batiment} <span class="text-xs font-normal text-stone-500">/ {c.batiment}</span>{/if}
                      {#if c.etage} <span class="text-xs font-normal text-stone-500">· étage {c.etage}</span>{/if}
                    </p>
                    {#if c.notes}
                      <p class="mt-0.5 text-xs text-stone-500">{c.notes}</p>
                    {/if}
                    <p class="mt-1 text-xs {surcapacite ? 'text-red-700' : 'text-stone-600'}">
                      {c.nb_occupants} / {c.capacite_max} occupant(s)
                    </p>
                  </div>
                  <div class="flex items-center gap-1">
                    <button
                      class="rounded-md p-1 text-stone-400 hover:bg-stone-100 hover:text-stone-700"
                      onclick={(e) => {
                        e.stopPropagation();
                        ouvrirEdition(c);
                      }}
                    >
                      <Pencil class="h-3.5 w-3.5" />
                    </button>
                    <button
                      class="rounded-md p-1 text-stone-400 hover:bg-red-50 hover:text-red-600"
                      onclick={(e) => {
                        e.stopPropagation();
                        supprimerChambre(c);
                      }}
                    >
                      <Trash2 class="h-3.5 w-3.5" />
                    </button>
                  </div>
                </div>
              </li>
            {/each}
          </ul>
        </div>
      {/if}
    </div>

    <!-- Détail / affectations de la chambre sélectionnée -->
    <div class="card overflow-hidden">
      {#if !chambreActive}
        <div class="p-6 text-center text-stone-500">
          <BedDouble class="mx-auto mb-3 h-8 w-8 text-stone-300" />
          <p>Sélectionne une chambre pour gérer ses affectations.</p>
        </div>
      {:else}
        <div class="border-b border-stone-200 bg-emerald-50 px-4 py-2 text-sm font-semibold text-emerald-900">
          Chambre {chambreActive.numero} —
          {affectesACetteChambre.length} / {chambreActive.capacite_max} occupant(s)
        </div>

        {#if affectesACetteChambre.length > 0}
          <div>
            <p class="bg-stone-50 px-4 py-1 text-[11px] font-semibold uppercase tracking-wide text-stone-600">
              Occupants
            </p>
            <ul class="divide-y divide-stone-100">
              {#each affectesACetteChambre as e (e.id)}
                <li class="flex items-center justify-between gap-3 px-3 py-2">
                  <div>
                    <p class="text-sm font-medium">{e.nom} {e.prenom}</p>
                    <p class="text-xs text-stone-500">{e.code_classe ?? "—"} · {e.etablissement_code}</p>
                  </div>
                  <button
                    class="rounded-md px-2 py-1 text-xs text-amber-700 hover:bg-amber-50"
                    onclick={() => affecter(e.id, null)}
                  >
                    <UserMinus class="inline h-3.5 w-3.5" />
                    Retirer
                  </button>
                </li>
              {/each}
            </ul>
          </div>
        {/if}

        <div>
          <p class="flex items-center justify-between bg-stone-50 px-4 py-1 text-[11px] font-semibold uppercase tracking-wide text-stone-600">
            <span>Internes non affectés ({internesNonAffectesFiltres.length})</span>
          </p>
          <div class="border-b border-stone-100 px-3 py-2">
            <div class="relative">
              <Search class="absolute left-2 top-1/2 h-3.5 w-3.5 -translate-y-1/2 text-stone-400" />
              <input
                type="search"
                placeholder="Filtrer…"
                bind:value={rechercheEleve}
                class="w-full rounded-md border border-stone-300 py-1 pl-7 pr-2 text-xs"
              />
            </div>
          </div>
          <div class="max-h-72 overflow-y-auto">
            {#if internesNonAffectesFiltres.length === 0}
              <p class="p-3 text-center text-xs text-stone-500">
                Aucun interne non affecté.
              </p>
            {:else}
              <ul class="divide-y divide-stone-100">
                {#each internesNonAffectesFiltres as e (e.id)}
                  <li class="flex items-center justify-between gap-3 px-3 py-1.5">
                    <div>
                      <p class="text-sm">{e.nom} {e.prenom}</p>
                      <p class="text-xs text-stone-500">{e.code_classe ?? "—"} · {e.etablissement_code}</p>
                    </div>
                    <button
                      class="rounded-md px-2 py-1 text-xs text-emerald-700 hover:bg-emerald-50"
                      onclick={() => affecter(e.id, chambreActive.id)}
                    >
                      <UserPlus class="inline h-3.5 w-3.5" />
                      Affecter
                    </button>
                  </li>
                {/each}
              </ul>
            {/if}
          </div>
        </div>
      {/if}
    </div>
  </div>
</section>

<!-- Modale chambre -->
{#if modaleChambre}
  <div class="fixed inset-0 z-50 flex items-center justify-center bg-stone-900/40 p-4" role="dialog" onclick={() => (modaleChambre = null)}>
    <div class="card max-w-md w-full space-y-3 p-5" onclick={(e) => e.stopPropagation()} role="document">
      <h2 class="text-lg font-semibold">
        {modaleChambre.mode === "creer" ? "Nouvelle chambre" : "Modifier la chambre"}
      </h2>
      <label class="block text-sm">
        <span class="text-xs font-medium uppercase tracking-wide text-stone-600">Numéro</span>
        <input
          type="text"
          bind:value={formChambre.numero}
          class="mt-1 w-full rounded-lg border border-stone-300 px-3 py-2 text-sm"
        />
      </label>
      <div class="grid grid-cols-2 gap-2">
        <label class="block text-sm">
          <span class="text-xs font-medium uppercase tracking-wide text-stone-600">Bâtiment</span>
          <input
            type="text"
            bind:value={formChambre.batiment}
            class="mt-1 w-full rounded-lg border border-stone-300 px-3 py-2 text-sm"
          />
        </label>
        <label class="block text-sm">
          <span class="text-xs font-medium uppercase tracking-wide text-stone-600">Étage</span>
          <input
            type="text"
            bind:value={formChambre.etage}
            class="mt-1 w-full rounded-lg border border-stone-300 px-3 py-2 text-sm"
          />
        </label>
      </div>
      <label class="block text-sm">
        <span class="text-xs font-medium uppercase tracking-wide text-stone-600">Capacité max</span>
        <input
          type="number"
          min="1"
          bind:value={formChambre.capacite_max}
          class="mt-1 w-24 rounded-lg border border-stone-300 px-3 py-2 text-sm"
        />
      </label>
      <label class="block text-sm">
        <span class="text-xs font-medium uppercase tracking-wide text-stone-600">Notes</span>
        <input
          type="text"
          bind:value={formChambre.notes}
          class="mt-1 w-full rounded-lg border border-stone-300 px-3 py-2 text-sm"
        />
      </label>
      <div class="flex justify-end gap-2 pt-2">
        <button class="btn-secondary" onclick={() => (modaleChambre = null)}>Annuler</button>
        <button class="btn-primary" onclick={sauvegarderChambre}>Enregistrer</button>
      </div>
    </div>
  </div>
{/if}
