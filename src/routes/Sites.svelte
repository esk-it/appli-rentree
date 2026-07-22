<script>
  import { onMount } from "svelte";
  import Building2 from "@lucide/svelte/icons/building-2";
  import Plus from "@lucide/svelte/icons/plus";
  import Trash2 from "@lucide/svelte/icons/trash-2";
  import Pencil from "@lucide/svelte/icons/pencil";
  import { sites as sitesApi } from "$lib/api.js";
  import { notify } from "$lib/toasts.js";

  let liste = $state([]);
  let chargement = $state(true);
  let erreur = $state("");

  let modaleOuverte = $state(null);
  let form = $state({ nom: "", nom_complet: "", domaine_mail: "", prefixe_annee_ou: "", numero_ordre: 2 });

  onMount(rafraichir);

  async function rafraichir() {
    chargement = true;
    try {
      liste = await sitesApi.lister();
    } catch (e) {
      erreur = String(e);
    } finally {
      chargement = false;
    }
  }

  function ouvrirNouveau() {
    form = { nom: "", nom_complet: "", domaine_mail: "", prefixe_annee_ou: "", numero_ordre: liste.length + 2 };
    modaleOuverte = { mode: "creer" };
  }

  function ouvrirEdition(s) {
    form = { ...s };
    modaleOuverte = { mode: "editer", id: s.id };
  }

  async function sauvegarder() {
    try {
      if (modaleOuverte.mode === "creer") {
        await sitesApi.creer({ ...form, numero_ordre: parseInt(form.numero_ordre) });
        notify.succes(`Site ${form.nom} créé`);
      } else {
        await sitesApi.modifier(modaleOuverte.id, { ...form, numero_ordre: parseInt(form.numero_ordre) });
        notify.succes(`Site ${form.nom} modifié`);
      }
      modaleOuverte = null;
      await rafraichir();
    } catch (e) {
      notify.erreur(String(e));
    }
  }

  async function supprimer(s) {
    if (!confirm(`Supprimer le site ${s.nom} ?`)) return;
    try {
      await sitesApi.supprimer(s.id);
      notify.succes(`Site ${s.nom} supprimé`);
      await rafraichir();
    } catch (e) {
      notify.erreur(String(e));
    }
  }
</script>

<section class="space-y-4">
  <header class="flex items-end justify-between gap-4">
    <div>
      <h1 class="text-2xl font-semibold text-stone-900 dark:text-stone-100">Sites de l'ensemble</h1>
      <p class="mt-1 text-sm text-stone-600 dark:text-stone-400">
        Chaque site porte son domaine mail Google Workspace et son préfixe d'arborescence OU.
        Amorçage minimal : NDE (@ndecleder.fr), NDK (@lekreisker.fr), SU (@lekreisker.fr).
      </p>
    </div>
    <button class="btn-primary" onclick={ouvrirNouveau}>
      <Plus class="h-4 w-4" />
      Nouveau site
    </button>
  </header>

  {#if erreur}
    <p class="rounded-lg bg-red-50 px-3 py-2 text-sm text-red-700 dark:bg-red-900/30 dark:text-red-300">{erreur}</p>
  {/if}

  <div class="card overflow-hidden">
    {#if chargement}
      <div class="p-8 text-center text-stone-500 dark:text-stone-400">Chargement…</div>
    {:else if liste.length === 0}
      <div class="p-8 text-center text-stone-500 dark:text-stone-400">
        <Building2 class="mx-auto mb-3 h-10 w-10 text-stone-300 dark:text-stone-600" />
        <p>Aucun site configuré.</p>
      </div>
    {:else}
      <table class="w-full text-sm">
        <thead class="bg-stone-100 text-stone-700 dark:bg-stone-800 dark:text-stone-300">
          <tr>
            <th class="border-b border-stone-200 px-4 py-2 text-left font-semibold dark:border-stone-700">Nom</th>
            <th class="border-b border-stone-200 px-4 py-2 text-left font-semibold dark:border-stone-700">Nom complet</th>
            <th class="border-b border-stone-200 px-4 py-2 text-left font-semibold dark:border-stone-700">Domaine mail</th>
            <th class="border-b border-stone-200 px-4 py-2 text-left font-semibold dark:border-stone-700">Racine OU</th>
            <th class="border-b border-stone-200 px-4 py-2"></th>
          </tr>
        </thead>
        <tbody>
          {#each liste as s (s.id)}
            <tr class="border-b border-stone-100 dark:border-stone-800 hover:bg-emerald-50/40 dark:hover:bg-emerald-900/20">
              <td class="whitespace-nowrap px-4 py-2 font-medium">{s.nom}</td>
              <td class="px-4 py-2 text-stone-600 dark:text-stone-400">{s.nom_complet}</td>
              <td class="px-4 py-2 font-mono text-xs text-stone-600 dark:text-stone-400">{s.domaine_mail}</td>
              <td class="px-4 py-2 font-mono text-xs text-stone-600 dark:text-stone-400">{s.prefixe_racine_ou}</td>
              <td class="px-4 py-2 text-right">
                <button class="rounded-md p-1 text-stone-400 hover:bg-stone-100 hover:text-stone-700 dark:hover:bg-stone-700 dark:hover:text-stone-200" onclick={() => ouvrirEdition(s)}>
                  <Pencil class="h-3.5 w-3.5" />
                </button>
                <button class="rounded-md p-1 text-stone-400 hover:bg-red-50 hover:text-red-600 dark:hover:bg-red-900/30" onclick={() => supprimer(s)}>
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

{#if modaleOuverte}
  <div class="fixed inset-0 z-50 flex items-center justify-center bg-stone-900/40 p-4" role="dialog" onclick={() => (modaleOuverte = null)}>
    <div class="card max-w-md w-full space-y-3 p-5" onclick={(e) => e.stopPropagation()} role="document">
      <h2 class="text-lg font-semibold">
        {modaleOuverte.mode === "creer" ? "Nouveau site" : "Modifier le site"}
      </h2>
      <label class="block text-sm">
        <span class="text-xs font-medium uppercase tracking-wide text-stone-600 dark:text-stone-400">Nom court (NDE, NDK, SU…)</span>
        <input type="text" bind:value={form.nom} class="mt-1 w-full rounded-lg border border-stone-300 px-3 py-2 text-sm dark:border-stone-600 dark:bg-stone-800" />
      </label>
      <label class="block text-sm">
        <span class="text-xs font-medium uppercase tracking-wide text-stone-600 dark:text-stone-400">Nom complet</span>
        <input type="text" bind:value={form.nom_complet} class="mt-1 w-full rounded-lg border border-stone-300 px-3 py-2 text-sm dark:border-stone-600 dark:bg-stone-800" />
      </label>
      <label class="block text-sm">
        <span class="text-xs font-medium uppercase tracking-wide text-stone-600 dark:text-stone-400">Domaine mail (Google Workspace)</span>
        <input type="text" bind:value={form.domaine_mail} placeholder="lekreisker.fr" class="mt-1 w-full rounded-lg border border-stone-300 px-3 py-2 text-sm dark:border-stone-600 dark:bg-stone-800" />
      </label>
      <div class="grid grid-cols-2 gap-2">
        <label class="block text-sm">
          <span class="text-xs font-medium uppercase tracking-wide text-stone-600 dark:text-stone-400">Préfixe année OU</span>
          <input type="text" bind:value={form.prefixe_annee_ou} placeholder="NDK" class="mt-1 w-full rounded-lg border border-stone-300 px-3 py-2 text-sm dark:border-stone-600 dark:bg-stone-800" />
        </label>
        <label class="block text-sm">
          <span class="text-xs font-medium uppercase tracking-wide text-stone-600 dark:text-stone-400">N° d'ordre</span>
          <input type="number" min="1" bind:value={form.numero_ordre} class="mt-1 w-24 rounded-lg border border-stone-300 px-3 py-2 text-sm dark:border-stone-600 dark:bg-stone-800" />
        </label>
      </div>
      <div class="flex justify-end gap-2 pt-2">
        <button class="btn-secondary" onclick={() => (modaleOuverte = null)}>Annuler</button>
        <button class="btn-primary" onclick={sauvegarder}>Enregistrer</button>
      </div>
    </div>
  </div>
{/if}
