<script>
  import { onMount } from "svelte";
  import Key from "@lucide/svelte/icons/key";
  import Download from "@lucide/svelte/icons/download";
  import FileText from "@lucide/svelte/icons/file-text";
  import Sparkles from "@lucide/svelte/icons/sparkles";
  import { annees, exports as exportsApi, telechargerFichier } from "$lib/api.js";

  let snapshots = $state(/** @type {Array<{id:number,libelle:string,nb_eleves:number}>} */ ([]));
  let anneeN = $state("");
  let anneeNMoinsUn = $state("");
  let resultat = $state(/** @type {null | { annee_n: string, annee_n_minus_1: string|null, fichiers: Array<{nom:string,contenu:string,nb_lignes:number,description:string}> }} */ (null));
  let chargement = $state(false);
  let erreur = $state("");

  onMount(async () => {
    try {
      snapshots = await annees.lister();
      if (snapshots.length >= 1) anneeN = snapshots[0].libelle;
      if (snapshots.length >= 2) anneeNMoinsUn = snapshots[1].libelle;
    } catch (e) {
      erreur = String(e);
    }
  });

  async function genererExports() {
    if (!anneeN) return;
    chargement = true;
    erreur = "";
    resultat = null;
    try {
      resultat = await exportsApi.koxo(
        anneeN,
        anneeNMoinsUn && anneeNMoinsUn !== anneeN ? anneeNMoinsUn : null,
      );
    } catch (e) {
      erreur = String(e);
    } finally {
      chargement = false;
    }
  }

  function telecharger(f) {
    telechargerFichier(f.nom, f.contenu, "text/csv");
  }

  function telechargerTout() {
    if (!resultat) return;
    for (const f of resultat.fichiers) {
      telecharger(f);
    }
  }

  /** Tailwind v4 scanne les classes statiques → on évite la concat dynamique. */
  function classesParType(nom) {
    if (nom.includes("Nouveaux")) {
      return {
        icone: "text-emerald-600",
        badge: "bg-emerald-50 text-emerald-800",
      };
    }
    if (nom.includes("Anciens")) {
      return {
        icone: "text-amber-600",
        badge: "bg-amber-50 text-amber-800",
      };
    }
    return {
      icone: "text-sky-600",
      badge: "bg-sky-50 text-sky-800",
    };
  }
</script>

<section class="space-y-5">
  <header class="flex items-end justify-between gap-4">
    <div>
      <h1 class="text-2xl font-semibold text-stone-900">Export KoXo</h1>
      <p class="mt-1 text-sm text-stone-600">
        Génère les fichiers CSV à importer dans KoXo pour gérer les comptes Active Directory
        des élèves. Format : virgule, UTF-8 BOM. Logins et emails calculés selon les règles
        de ton ensemble scolaire.
      </p>
    </div>
  </header>

  <div class="card p-4">
    <div class="flex flex-wrap items-end gap-3">
      <label class="block">
        <span class="text-xs font-medium uppercase tracking-wide text-stone-600">
          Année N (cible)
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

      <label class="block">
        <span class="text-xs font-medium uppercase tracking-wide text-stone-600">
          Année N-1 (optionnel)
        </span>
        <select
          bind:value={anneeNMoinsUn}
          class="mt-1 w-48 rounded-lg border border-stone-300 px-3 py-2 text-sm focus:border-emerald-600 focus:outline-none focus:ring-1 focus:ring-emerald-600"
        >
          <option value="">— (seul "Tous" généré)</option>
          {#each snapshots as s (s.id)}
            <option value={s.libelle}>{s.libelle}</option>
          {/each}
        </select>
        <span class="mt-1 block text-xs text-stone-500">
          Si fournie, on ajoute Nouveaux (avec MDP) et Anciens.
        </span>
      </label>

      <button
        class="btn-primary"
        onclick={genererExports}
        disabled={!anneeN || chargement}
      >
        <Sparkles class="h-4 w-4" />
        {chargement ? "Génération…" : "Générer les CSV"}
      </button>
    </div>

    {#if erreur}
      <p class="mt-3 rounded-lg bg-red-50 px-3 py-2 text-sm text-red-700">{erreur}</p>
    {/if}
  </div>

  {#if resultat}
    <div class="card p-4">
      <div class="mb-3 flex items-center justify-between">
        <h2 class="text-sm font-semibold text-stone-700">
          {resultat.fichiers.length} fichier(s) prêt(s)
          {#if resultat.annee_n_minus_1}
            <span class="text-stone-500"> · comparaison {resultat.annee_n} vs {resultat.annee_n_minus_1}</span>
          {/if}
        </h2>
        <button class="btn-secondary" onclick={telechargerTout}>
          <Download class="h-4 w-4" />
          Tout télécharger
        </button>
      </div>

      <ul class="divide-y divide-stone-100">
        {#each resultat.fichiers as f (f.nom)}
          {@const cls = classesParType(f.nom)}
          <li class="flex items-center justify-between gap-4 py-2.5">
            <div class="flex min-w-0 items-center gap-3">
              <FileText class="h-5 w-5 shrink-0 {cls.icone}" />
              <div class="min-w-0">
                <p class="truncate text-sm font-medium text-stone-900">{f.nom}</p>
                <p class="truncate text-xs text-stone-500">{f.description}</p>
              </div>
            </div>
            <div class="flex shrink-0 items-center gap-3">
              <span class="rounded-full px-2.5 py-0.5 text-xs font-medium {cls.badge}">
                {f.nb_lignes.toLocaleString("fr-FR")} ligne(s)
              </span>
              <button
                class="rounded-md p-1.5 text-stone-500 hover:bg-emerald-50 hover:text-emerald-700"
                title="Télécharger ce fichier"
                onclick={() => telecharger(f)}
              >
                <Download class="h-4 w-4" />
              </button>
            </div>
          </li>
        {/each}
      </ul>
    </div>

    <div class="card p-4">
      <h3 class="mb-2 text-sm font-semibold text-stone-700">Procédure d'import KoXo</h3>
      <ol class="space-y-1.5 text-sm text-stone-600">
        <li>
          <span class="font-medium text-stone-900">1.</span>
          Ouvre KoXo → <em>Groupe secondaire Élèves</em> de l'établissement cible
        </li>
        <li>
          <span class="font-medium text-stone-900">2.</span>
          Clique <em>Synchroniser…</em> et sélectionne le CSV correspondant
        </li>
        <li>
          <span class="font-medium text-stone-900">3.</span>
          Pour <strong>Nouveaux</strong> : KoXo va créer les comptes avec les mots de passe générés.
          Note-les ou exporte-les pour les distribuer.
        </li>
        <li>
          <span class="font-medium text-stone-900">4.</span>
          Pour <strong>Anciens</strong> : KoXo va proposer la suppression des comptes listés.
        </li>
      </ol>
    </div>
  {/if}
</section>
