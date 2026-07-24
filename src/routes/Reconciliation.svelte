<script>
  import { onMount } from "svelte";
  import GitCompareArrows from "@lucide/svelte/icons/git-compare-arrows";
  import Plus from "@lucide/svelte/icons/plus";
  import Equal from "@lucide/svelte/icons/equal";
  import Pencil from "@lucide/svelte/icons/pencil";
  import LogOut from "@lucide/svelte/icons/log-out";
  import AlertTriangle from "@lucide/svelte/icons/alert-triangle";
  import { annees, reconciliation } from "$lib/api.js";
  import { notify } from "$lib/toasts.js";

  let listeAnnees = $state([]);
  let anneeSourceId = $state(/** @type {null | number} */ (null));
  let anneeCibleId = $state(/** @type {null | number} */ (null));
  let typePersonne = $state(/** @type {"eleve"|"adulte"|""} */ (""));

  let rapport = $state(/** @type {null | any} */ (null));
  let seauActif = $state("modifie");
  let chargement = $state(false);
  let erreur = $state("");

  const SEAUX = [
    { id: "nouveau", label: "Nouveau", icon: Plus, couleur: "emerald" },
    { id: "identique", label: "Identique", icon: Equal, couleur: "stone" },
    { id: "modifie", label: "Modifié", icon: Pencil, couleur: "sky" },
    { id: "sortant", label: "Sortant", icon: LogOut, couleur: "amber" },
    { id: "ambigu", label: "Ambigu", icon: AlertTriangle, couleur: "red" },
  ];

  onMount(async () => {
    try {
      listeAnnees = await annees.lister();
      // Défauts intelligents : cible = plus récente, source = juste avant
      if (listeAnnees.length >= 2) {
        anneeCibleId = listeAnnees[0].id;
        anneeSourceId = listeAnnees[1].id;
      } else if (listeAnnees.length === 1) {
        anneeCibleId = listeAnnees[0].id;
      }
    } catch (e) {
      erreur = String(e);
    }
  });

  async function lancer() {
    if (!anneeSourceId || !anneeCibleId) return;
    if (anneeSourceId === anneeCibleId) {
      notify.avertissement("Année source et cible identiques — sélectionne deux années différentes.");
      return;
    }
    chargement = true;
    erreur = "";
    rapport = null;
    try {
      rapport = await reconciliation.obtenir({
        anneeSourceId,
        anneeCibleId,
        typePersonne: typePersonne || null,
      });
      // Le seau modifie est le plus intéressant : on l'ouvre par défaut sauf s'il est vide
      const nonVides = SEAUX.filter((s) => (rapport.compteurs[s.id] ?? 0) > 0);
      if (nonVides.length > 0) {
        seauActif = nonVides[0].id;
      }
    } catch (e) {
      erreur = String(e);
      notify.erreur(erreur);
    } finally {
      chargement = false;
    }
  }

  function entreesSeau(id) {
    if (!rapport) return [];
    return rapport[id === "modifie" ? "modifies" : id === "identique" ? "identiques" : id + "s"] ?? [];
  }

  function classeCouleur(couleur, actif) {
    const map = {
      emerald: actif ? "border-emerald-500 bg-emerald-50 text-emerald-800 dark:bg-emerald-900/30 dark:text-emerald-300 dark:border-emerald-500" : "border-stone-200 dark:border-stone-700",
      stone: actif ? "border-stone-500 bg-stone-100 text-stone-800 dark:bg-stone-700/60 dark:text-stone-200 dark:border-stone-400" : "border-stone-200 dark:border-stone-700",
      sky: actif ? "border-sky-500 bg-sky-50 text-sky-800 dark:bg-sky-900/30 dark:text-sky-300 dark:border-sky-500" : "border-stone-200 dark:border-stone-700",
      amber: actif ? "border-amber-500 bg-amber-50 text-amber-800 dark:bg-amber-900/30 dark:text-amber-300 dark:border-amber-500" : "border-stone-200 dark:border-stone-700",
      red: actif ? "border-red-500 bg-red-50 text-red-800 dark:bg-red-900/30 dark:text-red-300 dark:border-red-500" : "border-stone-200 dark:border-stone-700",
    };
    return map[couleur];
  }

  let entreesCourantes = $derived(entreesSeau(seauActif));
</script>

<section class="space-y-5">
  <header>
    <h1 class="text-2xl font-semibold text-stone-900 dark:text-stone-100">
      Réconciliation
    </h1>
    <p class="mt-1 text-sm text-stone-600 dark:text-stone-400">
      Compare deux années scolaires sur la clé pivot <code>(type, ID Charlemagne)</code>
      et classe chaque personne dans un des <strong>cinq seaux</strong>. Aucun cas
      ambigu n'est résolu automatiquement — l'arbitrage reste humain (Lot 5).
    </p>
  </header>

  {#if listeAnnees.length < 2}
    <div class="card border-amber-200 bg-amber-50/50 p-4 text-sm dark:border-amber-800 dark:bg-amber-900/20">
      <div class="flex items-start gap-3">
        <AlertTriangle class="mt-0.5 h-5 w-5 text-amber-700 dark:text-amber-400" />
        <div>
          <p class="font-medium text-amber-900 dark:text-amber-200">
            Il faut au moins deux années ingérées pour réconcilier.
          </p>
          <p class="mt-1 text-stone-700 dark:text-stone-300">
            Ingère un export via l'onglet <strong>Snapshots d'années</strong> puis reviens.
          </p>
        </div>
      </div>
    </div>
  {/if}

  <div class="card p-5 space-y-4">
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
          Année cible (à évaluer)
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
      <label class="block">
        <span class="text-xs font-medium uppercase tracking-wide text-stone-600 dark:text-stone-400">
          Filtre
        </span>
        <select
          bind:value={typePersonne}
          class="mt-1 w-full rounded-lg border border-stone-300 px-3 py-2 text-sm dark:border-stone-600 dark:bg-stone-800"
        >
          <option value="">Élèves + adultes</option>
          <option value="eleve">Élèves uniquement</option>
          <option value="adulte">Adultes uniquement</option>
        </select>
      </label>
    </div>

    <div class="flex gap-2">
      <button
        class="btn-primary"
        onclick={lancer}
        disabled={!anneeSourceId || !anneeCibleId || chargement}
      >
        <GitCompareArrows class="h-4 w-4" />
        Comparer
      </button>
      {#if chargement}
        <span class="self-center text-sm text-stone-500 dark:text-stone-400">Chargement…</span>
      {/if}
    </div>

    {#if erreur}
      <p class="rounded-lg bg-red-50 px-3 py-2 text-sm text-red-700 dark:bg-red-900/30 dark:text-red-300">
        {erreur}
      </p>
    {/if}
  </div>

  {#if rapport}
    <div class="card p-5 space-y-4">
      <div class="flex items-center justify-between">
        <div>
          <h2 class="text-lg font-semibold text-stone-900 dark:text-stone-100">
            {rapport.annee_source_libelle} → {rapport.annee_cible_libelle}
          </h2>
          <p class="text-xs text-stone-500 dark:text-stone-400">
            {#if rapport.type_personne}
              Population : <strong>{rapport.type_personne}s</strong>
            {:else}
              Élèves + adultes
            {/if}
          </p>
        </div>
      </div>

      <!-- Onglets seaux -->
      <div class="grid grid-cols-2 gap-2 md:grid-cols-5">
        {#each SEAUX as seau (seau.id)}
          {@const n = rapport.compteurs[seau.id] ?? 0}
          {@const actif = seauActif === seau.id}
          <button
            class="flex flex-col items-start gap-1 rounded-xl border-2 p-3 text-left transition
                   {classeCouleur(seau.couleur, actif)}
                   {!actif ? 'hover:border-stone-300 dark:hover:border-stone-500' : ''}"
            onclick={() => (seauActif = seau.id)}
          >
            <div class="flex items-center gap-2">
              <seau.icon class="h-4 w-4" />
              <span class="text-xs font-medium uppercase tracking-wide">{seau.label}</span>
            </div>
            <span class="text-2xl font-semibold tabular-nums">{n}</span>
          </button>
        {/each}
      </div>

      <!-- Contenu du seau actif -->
      {#if entreesCourantes.length === 0}
        <p class="rounded-lg border border-stone-200 bg-stone-50 p-4 text-center text-sm text-stone-500 dark:border-stone-700 dark:bg-stone-800 dark:text-stone-400">
          Aucune personne dans ce seau.
        </p>
      {:else}
        <div class="overflow-hidden rounded-lg border border-stone-200 dark:border-stone-700">
          <table class="min-w-full divide-y divide-stone-200 text-sm dark:divide-stone-700">
            <thead class="bg-stone-50 text-xs uppercase tracking-wide text-stone-500 dark:bg-stone-800 dark:text-stone-400">
              <tr>
                <th class="px-3 py-2 text-left">Clé</th>
                <th class="px-3 py-2 text-left">Nom Prénom</th>
                <th class="px-3 py-2 text-left">Login</th>
                <th class="px-3 py-2 text-left">Classe {rapport.annee_source_libelle}</th>
                <th class="px-3 py-2 text-left">Classe {rapport.annee_cible_libelle}</th>
                <th class="px-3 py-2 text-left">Motif / changement</th>
              </tr>
            </thead>
            <tbody class="divide-y divide-stone-100 dark:divide-stone-800">
              {#each entreesCourantes as e (e.personne_id)}
                <tr class="hover:bg-stone-50 dark:hover:bg-stone-800/50">
                  <td class="px-3 py-2 font-mono text-xs text-stone-500 dark:text-stone-400">
                    {e.cle_pivot}
                  </td>
                  <td class="px-3 py-2">
                    <div class="font-medium text-stone-900 dark:text-stone-100">{e.nom} {e.prenom}</div>
                    <div class="text-xs text-stone-500 dark:text-stone-400">{e.type}</div>
                  </td>
                  <td class="px-3 py-2 font-mono text-xs">{e.login}</td>
                  <td class="px-3 py-2 text-stone-600 dark:text-stone-400">
                    {e.classe_source ?? "—"}
                  </td>
                  <td class="px-3 py-2 text-stone-600 dark:text-stone-400">
                    {e.classe_cible ?? "—"}
                  </td>
                  <td class="px-3 py-2">
                    <div class="text-stone-700 dark:text-stone-300">{e.motif}</div>
                    {#if e.changements?.length > 1}
                      <details class="mt-1">
                        <summary class="cursor-pointer text-xs text-sky-700 dark:text-sky-400">
                          Voir les {e.changements.length} changements
                        </summary>
                        <ul class="mt-1 space-y-0.5 text-xs text-stone-500 dark:text-stone-400">
                          {#each e.changements as c (c.champ)}
                            <li>
                              <strong>{c.champ}</strong> : <code>{c.avant ?? "∅"}</code>
                              → <code>{c.apres ?? "∅"}</code>
                            </li>
                          {/each}
                        </ul>
                      </details>
                    {/if}
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
