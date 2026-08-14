<script>
  import { onMount } from "svelte";
  import Search from "@lucide/svelte/icons/search";
  import Users2 from "@lucide/svelte/icons/users-2";
  import Avatar from "$lib/components/Avatar.svelte";
  import CopiableTexte from "$lib/components/CopiableTexte.svelte";
  import EtatVide from "$lib/components/EtatVide.svelte";
  import Nombre from "$lib/components/Nombre.svelte";
  import Segments from "$lib/components/Segments.svelte";
  import Squelette from "$lib/components/Squelette.svelte";
  import { personnes } from "$lib/api.js";

  let liste = $state(/** @type {any[]} */ ([]));
  let chargement = $state(true);
  let erreur = $state("");

  let recherche = $state("");
  let filtreType = $state(/** @type {"" | "eleve" | "adulte"} */ (""));
  let filtreSite = $state("");

  let listeFiltree = $derived.by(() => {
    let r = liste;
    if (filtreType) r = r.filter((p) => p.type === filtreType);
    if (filtreSite) r = r.filter((p) => p.site === filtreSite);
    const q = recherche.trim().toLowerCase();
    if (q) {
      r = r.filter((p) =>
        `${p.nom} ${p.prenom} ${p.login} ${p.cle_pivot} ${p.badge}`
          .toLowerCase()
          .includes(q),
      );
    }
    return r;
  });

  let sitesDispo = $derived([
    ...new Set(liste.map((p) => p.site).filter(Boolean)),
  ].sort());

  // Les compteurs affichés dans les segments donnent la répartition sans
  // avoir à cliquer sur chaque filtre pour la découvrir.
  let optionsType = $derived([
    { id: "", label: "Tous", badge: liste.length },
    { id: "eleve", label: "Élèves", badge: liste.filter((p) => p.type === "eleve").length },
    { id: "adulte", label: "Adultes", badge: liste.filter((p) => p.type === "adulte").length },
  ]);

  let optionsSite = $derived([
    { id: "", label: "Tous sites" },
    ...sitesDispo.map((s) => ({
      id: s,
      label: s,
      badge: liste.filter((p) => p.site === s).length,
    })),
  ]);

  onMount(rafraichir);

  async function rafraichir() {
    chargement = true;
    erreur = "";
    try {
      liste = await personnes.lister();
    } catch (e) {
      erreur = String(e);
    } finally {
      chargement = false;
    }
  }
</script>

<section class="space-y-4">
  <header>
    <h1 class="text-2xl font-semibold text-stone-900 dark:text-stone-100">
      Référentiel des personnes
    </h1>
    <p class="mt-1 text-sm text-stone-600 dark:text-stone-400">
      Identité persistante des élèves et adultes. Créée à la première apparition,
      jamais supprimée — le login reste figé, y compris après un départ.
    </p>
  </header>

  {#if erreur}
    <p class="rounded-lg bg-red-50 px-3 py-2 text-sm text-red-700 dark:bg-red-900/30 dark:text-red-300">
      {erreur}
    </p>
  {/if}

  <div class="card p-3">
    <div class="flex flex-wrap items-center gap-3">
      <div class="relative">
        <Search class="absolute left-2.5 top-1/2 h-4 w-4 -translate-y-1/2 text-stone-400" />
        <input
          type="search"
          placeholder="Nom, prénom, login, clé pivot, badge…"
          bind:value={recherche}
          class="w-80 rounded-lg border border-stone-300 py-1.5 pl-8 pr-3 text-sm dark:border-stone-600 dark:bg-stone-800 dark:text-stone-200"
        />
      </div>
      <Segments bind:valeur={filtreType} taille="sm" options={optionsType} />

      {#if sitesDispo.length}
        <Segments bind:valeur={filtreSite} taille="sm" options={optionsSite} />
      {/if}

      <span class="ml-auto text-xs tabular-nums text-stone-500 dark:text-stone-400">
        <Nombre valeur={listeFiltree.length} duree={300} /> / {liste.length}
      </span>
    </div>
  </div>

  <div class="card overflow-hidden">
    {#if chargement}
      <div class="p-4">
        <Squelette variante="ligne-tableau" nb={6} colonnes={6} />
      </div>
    {:else if liste.length === 0}
      <div class="p-4">
        <EtatVide
          icon={Users2}
          titre="Référentiel vide"
          message="Charge d'abord tes comptes existants depuis l'onglet Amorçage KoXo, puis dépose un export Charlemagne dans Snapshots d'années."
        />
      </div>
    {:else if listeFiltree.length === 0}
      <div class="p-4">
        <EtatVide
          icon={Search}
          titre="Aucun résultat"
          message="Aucune personne ne correspond à ces filtres. Élargis la recherche ou retire un filtre."
        />
      </div>
    {:else}
      <div class="max-h-[640px] overflow-auto">
        <table class="w-full text-sm">
          <thead class="sticky top-0 z-10 bg-stone-100 text-stone-700 dark:bg-stone-800 dark:text-stone-300">
            <tr>
              <th class="border-b border-stone-200 px-3 py-2 text-left font-semibold dark:border-stone-700"></th>
              <th class="border-b border-stone-200 px-3 py-2 text-left font-semibold dark:border-stone-700">Clé pivot</th>
              <th class="border-b border-stone-200 px-3 py-2 text-left font-semibold dark:border-stone-700">Type</th>
              <th class="border-b border-stone-200 px-3 py-2 text-left font-semibold dark:border-stone-700">Nom</th>
              <th class="border-b border-stone-200 px-3 py-2 text-left font-semibold dark:border-stone-700">Prénom</th>
              <th class="border-b border-stone-200 px-3 py-2 text-left font-semibold dark:border-stone-700">Login</th>
              <th class="border-b border-stone-200 px-3 py-2 text-left font-semibold dark:border-stone-700">Email</th>
              <th class="border-b border-stone-200 px-3 py-2 text-left font-semibold dark:border-stone-700">Site</th>
              <th class="border-b border-stone-200 px-3 py-2 text-left font-semibold dark:border-stone-700">Classe</th>
              <th class="border-b border-stone-200 px-3 py-2 text-right font-semibold dark:border-stone-700">Badge</th>
            </tr>
          </thead>
          <tbody>
            {#each listeFiltree as p (p.id)}
              <tr class="border-b border-stone-100 dark:border-stone-800 hover:bg-emerald-50/40 dark:hover:bg-emerald-900/20">
                <td class="px-3 py-1">
                  <Avatar personneId={p.id} nom={p.nom} prenom={p.prenom} taille={32} />
                </td>
                <td class="whitespace-nowrap px-3 py-1.5 font-mono text-xs text-stone-600 dark:text-stone-400">
                  {p.cle_pivot}
                </td>
                <td class="px-3 py-1.5 text-xs">
                  <span class="rounded-full px-2 py-0.5 {p.type === 'eleve' ? 'bg-emerald-100 text-emerald-800 dark:bg-emerald-900/40 dark:text-emerald-300' : 'bg-sky-100 text-sky-800 dark:bg-sky-900/40 dark:text-sky-300'}">
                    {p.type}
                  </span>
                </td>
                <td class="whitespace-nowrap px-3 py-1.5 font-medium">{p.nom}</td>
                <td class="whitespace-nowrap px-3 py-1.5">{p.prenom}</td>
                <td class="whitespace-nowrap px-3 py-1.5">
                  <CopiableTexte valeur={p.login} classe="font-mono text-xs" />
                </td>
                <td class="whitespace-nowrap px-3 py-1.5">
                  <CopiableTexte
                    valeur={p.email ?? ""}
                    classe="font-mono text-xs text-stone-600 dark:text-stone-400"
                  />
                </td>
                <td class="px-3 py-1.5 text-stone-600 dark:text-stone-400">{p.site ?? "—"}</td>
                <td class="whitespace-nowrap px-3 py-1.5 text-stone-600 dark:text-stone-400">{p.classe ?? "—"}</td>
                <td class="px-3 py-1.5 text-right tabular-nums text-stone-600 dark:text-stone-400">{p.badge}</td>
              </tr>
            {/each}
          </tbody>
        </table>
      </div>
    {/if}
  </div>
</section>
