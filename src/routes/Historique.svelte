<script>
  import { onMount } from "svelte";
  import History from "@lucide/svelte/icons/history";
  import Trash2 from "@lucide/svelte/icons/trash-2";
  import Filter from "@lucide/svelte/icons/filter";
  import { historique } from "$lib/api.js";

  let liste = $state(/** @type {any[]} */ ([]));
  let chargement = $state(true);
  let erreur = $state("");
  let filtreCible = $state(/** @type {string|null} */ (null));

  const CIBLES = [
    "tout",
    "koxo",
    "koxo-adultes",
    "pmb",
    "cardstudio",
    "smartair",
    "google",
    "google-adultes",
  ];

  const COULEURS_CIBLE = {
    tout: "bg-emerald-100 text-emerald-800",
    koxo: "bg-sky-100 text-sky-800",
    "koxo-adultes": "bg-sky-100 text-sky-800",
    pmb: "bg-amber-100 text-amber-800",
    cardstudio: "bg-purple-100 text-purple-800",
    smartair: "bg-rose-100 text-rose-800",
    google: "bg-indigo-100 text-indigo-800",
    "google-adultes": "bg-indigo-100 text-indigo-800",
  };

  onMount(rafraichir);

  async function rafraichir() {
    chargement = true;
    try {
      liste = await historique.lister(200, filtreCible);
    } catch (e) {
      erreur = String(e);
    } finally {
      chargement = false;
    }
  }

  async function supprimer(id) {
    if (!confirm("Supprimer cette entrée d'historique ?")) return;
    try {
      await historique.supprimer(id);
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

  function couleur(cible) {
    return COULEURS_CIBLE[cible] || "bg-stone-100 text-stone-800";
  }

  let totalGenerations = $derived(liste.length);
  let totalFichiers = $derived(liste.reduce((s, g) => s + g.nb_fichiers, 0));
</script>

<section class="space-y-5">
  <header>
    <h1 class="text-2xl font-semibold text-stone-900">Historique des générations</h1>
    <p class="mt-1 text-sm text-stone-600">
      Trace de toutes les générations d'exports effectuées dans l'application.
      Pratique pour savoir ce que tu as déjà fait dans la préparation de la rentrée.
    </p>
  </header>

  {#if erreur}
    <p class="rounded-lg bg-red-50 px-3 py-2 text-sm text-red-700">{erreur}</p>
  {/if}

  <div class="grid grid-cols-2 gap-3">
    <div class="card p-4">
      <p class="text-xs font-semibold uppercase tracking-wide text-stone-600">
        Générations enregistrées
      </p>
      <p class="mt-1 text-2xl font-semibold tabular-nums">{totalGenerations}</p>
    </div>
    <div class="card p-4">
      <p class="text-xs font-semibold uppercase tracking-wide text-stone-600">
        Total fichiers produits
      </p>
      <p class="mt-1 text-2xl font-semibold tabular-nums">{totalFichiers}</p>
    </div>
  </div>

  <div class="card p-3">
    <div class="flex flex-wrap items-center gap-2">
      <Filter class="h-4 w-4 text-stone-500" />
      <button
        class="rounded-full border px-2.5 py-0.5 text-xs font-medium transition
               {filtreCible === null
                 ? 'border-emerald-600 bg-emerald-50 text-emerald-800'
                 : 'border-stone-200 bg-white text-stone-600 hover:border-stone-300'}"
        onclick={() => {
          filtreCible = null;
          rafraichir();
        }}
      >
        Toutes
      </button>
      {#each CIBLES as c (c)}
        <button
          class="rounded-full border px-2.5 py-0.5 text-xs font-medium transition
                 {filtreCible === c
                   ? 'border-emerald-600 bg-emerald-50 text-emerald-800'
                   : 'border-stone-200 bg-white text-stone-600 hover:border-stone-300'}"
          onclick={() => {
            filtreCible = c;
            rafraichir();
          }}
        >
          {c}
        </button>
      {/each}
    </div>
  </div>

  <div class="card overflow-hidden">
    {#if chargement}
      <div class="p-8 text-center text-stone-500">Chargement…</div>
    {:else if liste.length === 0}
      <div class="p-8 text-center text-stone-500">
        <History class="mx-auto mb-3 h-10 w-10 text-stone-300" />
        <p>Aucune génération enregistrée pour l'instant.</p>
        <p class="mt-1 text-xs">
          L'historique se remplit automatiquement à chaque clic "Générer" sur n'importe quelle cible.
        </p>
      </div>
    {:else}
      <table class="w-full text-sm">
        <thead class="bg-stone-50 text-stone-700">
          <tr>
            <th class="border-b border-stone-200 px-4 py-2 text-left font-semibold">Date</th>
            <th class="border-b border-stone-200 px-4 py-2 text-left font-semibold">Cible</th>
            <th class="border-b border-stone-200 px-4 py-2 text-left font-semibold">Année N</th>
            <th class="border-b border-stone-200 px-4 py-2 text-left font-semibold">N-1</th>
            <th class="border-b border-stone-200 px-4 py-2 text-right font-semibold">Fichiers</th>
            <th class="border-b border-stone-200 px-4 py-2 text-right font-semibold">Lignes</th>
            <th class="border-b border-stone-200 px-4 py-2 text-left font-semibold">Notes</th>
            <th class="border-b border-stone-200 px-4 py-2"></th>
          </tr>
        </thead>
        <tbody>
          {#each liste as g (g.id)}
            <tr class="border-b border-stone-100 hover:bg-emerald-50/30">
              <td class="whitespace-nowrap px-4 py-2 text-stone-600">{formaterDate(g.date_creation)}</td>
              <td class="px-4 py-2">
                <span class="rounded-full px-2.5 py-0.5 text-xs font-medium {couleur(g.cible)}">
                  {g.cible}
                </span>
              </td>
              <td class="px-4 py-2 font-medium">{g.annee_n}</td>
              <td class="px-4 py-2 text-stone-600">{g.annee_n_minus_1 ?? "—"}</td>
              <td class="px-4 py-2 text-right tabular-nums">{g.nb_fichiers}</td>
              <td class="px-4 py-2 text-right tabular-nums">{g.nb_lignes_total.toLocaleString("fr-FR")}</td>
              <td class="px-4 py-2 text-xs text-stone-600">{g.notes ?? ""}</td>
              <td class="px-4 py-2 text-right">
                <button
                  class="rounded-md p-1 text-stone-400 hover:bg-red-50 hover:text-red-600"
                  title="Supprimer cette entrée"
                  onclick={() => supprimer(g.id)}
                >
                  <Trash2 class="h-3.5 w-3.5" />
                </button>
              </td>
            </tr>
          {/each}
        </tbody>
      </table>
    {/if}
  </div>
</section>
