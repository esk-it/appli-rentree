<script>
  import { onMount } from "svelte";
  import Camera from "@lucide/svelte/icons/camera";
  import Download from "@lucide/svelte/icons/download";
  import RefreshCw from "@lucide/svelte/icons/refresh-cw";
  import Search from "@lucide/svelte/icons/search";
  import CheckCircle2 from "@lucide/svelte/icons/check-circle-2";
  import Bouton from "$lib/components/Bouton.svelte";
  import EnTetePage from "$lib/components/EnTetePage.svelte";
  import EtatVide from "$lib/components/EtatVide.svelte";
  import { annees as anneesApi, photos } from "$lib/api.js";
  import { notify } from "$lib/toasts.js";
  import { lire, ecrire } from "$lib/memoire.svelte.js";

  /**
   * Qui a sa photo, qui ne l'a pas.
   *
   * ## Pourquoi un écran et non une anomalie
   *
   * Le manque était détecté comme une anomalie parmi huit : un compteur qui
   * disait « 9 photos orphelines » sans dire lesquelles. Or la question est
   * toujours nominative — *« la liste, avec nom, prénom et classe »* — parce
   * qu'elle sert à relancer les professeurs principaux, classe par classe.
   *
   * ## Pourquoi le relevé ne part pas tout seul
   *
   * Un accès disque par élève sur un partage réseau. C'est trop cher pour
   * une ouverture d'écran ; ici c'est le sujet, alors on le demande et on
   * l'attend. Le résultat survit ensuite à la navigation.
   */

  let listeAnnees = $state(/** @type {any[]} */ ([]));
  let anneeId = $state(/** @type {number | null} */ (null));
  /**
   * Élèves ou adultes : deux dossiers, deux relevés.
   *
   * Les photos du personnel vivent hors de l'arborescence par année. Les
   * mêler dans un seul relevé donnerait des absences fausses des deux
   * côtés — chacun cherche dans son dossier.
   */
  let population = $state(lire("photos.population", "eleve"));
  let inventaires = $state(
    lire("photos.inventaires", /** @type {Record<string, any>} */ ({})),
  );
  let inventaire = $derived(inventaires[population] ?? null);
  let relevesLe = $state(
    lire("photos.relevesLe", /** @type {Record<string, number>} */ ({})),
  );
  let releveLe = $derived(relevesLe[population] ?? null);
  let occupe = $state(false);
  let erreur = $state("");
  let recherche = $state("");
  let classeRetenue = $state("");
  let siteRetenu = $state("");

  $effect(() => ecrire("photos.inventaires", inventaires));
  $effect(() => ecrire("photos.relevesLe", relevesLe));
  $effect(() => ecrire("photos.population", population));

  // Changer de population change la maille : un filtre « 2_5 » gardé en
  // passant aux adultes masquerait la liste entière sans rien dire.
  $effect(() => {
    population;
    classeRetenue = "";
    siteRetenu = "";
  });

  onMount(async () => {
    try {
      const a = await anneesApi.lister();
      listeAnnees = a;
      anneeId =
        [...a].sort((x, y) => y.libelle.localeCompare(x.libelle))[0]?.id ?? null;
    } catch (e) {
      erreur = String(e).replace(/^Error:\s*/, "");
    }
  });

  async function relever() {
    if (!anneeId) return;
    occupe = true;
    erreur = "";
    try {
      inventaires = { ...inventaires, [population]: await photos.inventaire(anneeId, population) };
      relevesLe = { ...relevesLe, [population]: Date.now() };
      notify.succes(
        inventaires[population].nb_sans === 0
          ? "Tout le monde a sa photo."
          : `${inventaires[population].nb_sans} photo(s) manquante(s) sur ` +
            `${inventaires[population].nb_eleves}`,
        { duree: 8000 },
      );
    } catch (e) {
      inventaires = { ...inventaires, [population]: null };
      erreur = String(e).replace(/^Error:\s*/, "");
      notify.erreur(erreur, { duree: 12000 });
    } finally {
      occupe = false;
    }
  }

  let age = $derived.by(() => {
    if (!releveLe) return "";
    const m = Math.round((Date.now() - releveLe) / 60000);
    if (m < 2) return "à l'instant";
    if (m < 60) return `il y a ${m} min`;
    const h = Math.round(m / 60);
    return h < 24 ? `il y a ${h} h` : `il y a ${Math.round(h / 24)} j`;
  });

  let sites = $derived.by(() => {
    const par = new Map();
    for (const e of inventaire?.manquantes ?? []) {
      par.set(e.site ?? "—", (par.get(e.site ?? "—") ?? 0) + 1);
    }
    return [...par.entries()].sort((a, b) => b[1] - a[1]);
  });

  let manquantes = $derived.by(() => {
    let r = inventaire?.manquantes ?? [];
    if (siteRetenu) r = r.filter((e) => (e.site ?? "—") === siteRetenu);
    if (classeRetenue) r = r.filter((e) => e.classe === classeRetenue);
    const q = recherche.trim().toLowerCase();
    if (q) r = r.filter((e) => `${e.nom} ${e.prenom}`.toLowerCase().includes(q));
    return r;
  });

  /** Les classes incomplètes, les pires d'abord — c'est l'ordre des relances. */
  let classes = $derived(
    (inventaire?.classes_incompletes ?? []).map((c) => ({
      code: c,
      sans: inventaire.par_classe[c]?.sans ?? 0,
      avec: inventaire.par_classe[c]?.avec ?? 0,
    })),
  );
</script>

<section class="space-y-5">
  <EnTetePage
    icon={Camera}
    titre="Les photos"
    description="Qui a sa photo sur le partage, et surtout qui ne l'a pas — nommément, par classe, pour relancer les professeurs principaux."
  >
    {#snippet actions()}
      <div class="flex overflow-hidden rounded-lg border border-stone-300 dark:border-stone-600">
        {#each [["eleve", "Élèves"], ["adulte", "Adultes"]] as [id, label] (id)}
          <button
            class="px-3 py-1.5 text-sm transition {population === id
              ? 'bg-emerald-600 font-medium text-white'
              : 'text-stone-600 hover:bg-stone-100 dark:text-stone-300 dark:hover:bg-stone-700'}"
            onclick={() => (population = id)}
          >
            {label}
          </button>
        {/each}
      </div>
      {#if inventaire && anneeId}
        <a class="btn-secondary" href={photos.urlClasseur(anneeId, population)}>
          <Download class="h-4 w-4" /> La liste en classeur
        </a>
      {/if}
      <Bouton variante="primary" icon={RefreshCw} occupe={occupe} onclick={relever}>
        {inventaire ? "Relever à nouveau" : "Relever le partage"}
      </Bouton>
    {/snippet}
  </EnTetePage>

  {#if erreur}
    <p class="rounded-lg bg-red-50 px-3 py-2 text-sm text-red-700 dark:bg-red-900/30 dark:text-red-300">
      {erreur}
    </p>
  {/if}

  {#if !inventaire}
    <EtatVide
      icon={Camera}
      titre="Le partage n'a pas encore été relu"
      message="Un accès disque par personne, sur le réseau : c'est trop cher pour partir tout seul à chaque ouverture. Lance le relevé quand le partage est monté."
    />
  {:else}
    {#if age && age !== "à l'instant"}
      <p class="text-xs text-stone-500 dark:text-stone-400">
        Relevé retrouvé — il date de <strong>{age}</strong>. Relance-le si des
        photos ont été déposées depuis.
      </p>
    {/if}

    <div class="grid gap-px overflow-hidden rounded-xl border border-stone-200 bg-stone-200 dark:border-stone-700 dark:bg-stone-700 sm:grid-cols-2 lg:grid-cols-4">
      <div class="bg-white p-4 dark:bg-stone-800">
        <p class="libelle-champ">Photos en place</p>
        <p class="mt-1 text-2xl font-semibold tabular-nums">
          {inventaire.nb_avec}
          <span class="text-sm font-normal text-stone-500">/ {inventaire.nb_eleves}</span>
        </p>
        <div class="mt-2 h-1.5 overflow-hidden rounded-full bg-stone-200 dark:bg-stone-700">
          <div
            class="h-full bg-emerald-500 transition-all duration-500"
            style="width: {Math.round(inventaire.taux * 100)}%"
          ></div>
        </div>
      </div>
      <div class="bg-white p-4 dark:bg-stone-800">
        <p class="libelle-champ">Manquantes</p>
        <p class="mt-1 text-2xl font-semibold tabular-nums {inventaire.nb_sans ? 'text-amber-700 dark:text-amber-400' : ''}">
          {inventaire.nb_sans}
        </p>
        <p class="text-xs text-stone-500 dark:text-stone-400">
          dans {classes.length}
          {population === "adulte" ? "site" : "classe"}{classes.length > 1 ? "s" : ""}
        </p>
      </div>
      <div class="bg-white p-4 dark:bg-stone-800 sm:col-span-2">
        <p class="libelle-champ">Partage lu</p>
        <p class="mt-1 truncate font-mono text-xs text-stone-600 dark:text-stone-300">
          {inventaire.dossier}
        </p>
        <p class="mt-1 text-xs text-stone-500 dark:text-stone-400">
          Le fichier est cherché sous « NOM Prénom », « NOM_Prénom »,
          « Prénom NOM » et le numéro de badge — une photo présente sous une
          autre forme n'est pas déclarée manquante.
        </p>
      </div>
    </div>

    {#if inventaire.nb_a_verifier > 0}
      <div class="rounded-lg border-l-4 border-l-amber-500 bg-amber-50 p-3 dark:bg-amber-900/25">
        <p class="text-sm font-medium text-amber-900 dark:text-amber-200">
          {inventaire.nb_a_verifier} cas à trancher — un fichier existe, mais
          rien ne dit à qui il est.
        </p>
        <p class="mt-0.5 text-xs text-amber-800 dark:text-amber-300">
          Des homonymes. La vie scolaire ajoute la classe entre parenthèses
          pour les départager ; quand l'abréviation ne correspond à aucune
          classe connue, le programme refuse de choisir — mettre le visage
          d'une élève sur la carte de son homonyme serait pire que rien.
          Les fichiers candidats sont nommés dans la liste.
        </p>
      </div>
    {/if}

    {#if inventaire.nb_sans === 0}
      <div class="card flex items-center gap-3 p-5">
        <CheckCircle2 class="h-6 w-6 shrink-0 text-emerald-600 dark:text-emerald-400" />
        <div>
          <p class="font-medium">Tout le monde a sa photo.</p>
          <p class="text-sm text-stone-500 dark:text-stone-400">
            {inventaire.nb_eleves} élèves, aucun fichier introuvable sur le partage.
          </p>
        </div>
      </div>
    {:else}
      <!-- Par classe : c'est à cette maille qu'on relance. -->
      {#if sites.length > 1}
        <div class="card p-4">
          <h2 class="titre-section mb-2">Par site</h2>
          <div class="flex flex-wrap gap-1.5">
            <button
              class="rounded-full border px-2.5 py-1 text-xs transition {siteRetenu === ''
                ? 'border-emerald-500 bg-emerald-50 font-medium text-emerald-800 dark:bg-emerald-900/40 dark:text-emerald-300'
                : 'border-stone-300 text-stone-600 hover:border-stone-400 dark:border-stone-600 dark:text-stone-300'}"
              onclick={() => (siteRetenu = "")}
            >
              Tous <span class="tabular-nums">{inventaire.nb_sans}</span>
            </button>
            {#each sites as [nom, nb] (nom)}
              <button
                class="rounded-full border px-2.5 py-1 text-xs transition {siteRetenu === nom
                  ? 'border-emerald-500 bg-emerald-50 font-medium text-emerald-800 dark:bg-emerald-900/40 dark:text-emerald-300'
                  : 'border-stone-300 text-stone-600 hover:border-stone-400 dark:border-stone-600 dark:text-stone-300'}"
                onclick={() => {
                  siteRetenu = nom;
                  classeRetenue = "";
                }}
              >
                {nom} <span class="tabular-nums font-semibold">{nb}</span>
              </button>
            {/each}
          </div>
        </div>
      {/if}

      <div class="card p-4">
        <h2 class="titre-section mb-2">
          {population === "adulte" ? "Par site" : "Par classe, les plus incomplètes d'abord"}
        </h2>
        <div class="flex flex-wrap gap-1.5">
          <button
            class="rounded-full border px-2.5 py-1 text-xs transition {classeRetenue === ''
              ? 'border-emerald-500 bg-emerald-50 font-medium text-emerald-800 dark:bg-emerald-900/40 dark:text-emerald-300'
              : 'border-stone-300 text-stone-600 hover:border-stone-400 dark:border-stone-600 dark:text-stone-300'}"
            onclick={() => (classeRetenue = "")}
          >
            Toutes <span class="tabular-nums">{inventaire.nb_sans}</span>
          </button>
          {#each classes as c (c.code)}
            <button
              class="rounded-full border px-2.5 py-1 text-xs transition {classeRetenue === c.code
                ? 'border-emerald-500 bg-emerald-50 font-medium text-emerald-800 dark:bg-emerald-900/40 dark:text-emerald-300'
                : 'border-stone-300 text-stone-600 hover:border-stone-400 dark:border-stone-600 dark:text-stone-300'}"
              title="{c.avec} photo(s) en place sur {c.avec + c.sans}"
              onclick={() => (classeRetenue = c.code)}
            >
              {c.code} <span class="tabular-nums font-semibold">{c.sans}</span>
            </button>
          {/each}
        </div>
      </div>

      <div class="card overflow-hidden">
        <div class="border-b border-stone-200 p-3 dark:border-stone-700">
          <div class="relative max-w-md">
            <Search class="pointer-events-none absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-stone-400" />
            <input class="champ pl-9" placeholder="Nom ou prénom…" bind:value={recherche} />
          </div>
        </div>
        <div class="max-h-[max(24rem,calc(100vh-30rem))] overflow-auto">
          <table class="tableau">
            <thead class="entete-tableau">
              <tr>
                <th class="px-3 py-2 text-left">{population === "adulte" ? "Site" : "Classe"}</th>
                <th class="px-3 py-2 text-left">Nom</th>
                <th class="px-3 py-2 text-left">Prénom</th>
                <th class="px-3 py-2 text-left">Site</th>
                <th class="px-3 py-2 text-right">Badge</th>
                <th class="px-3 py-2 text-left">Fichier attendu</th>
              </tr>
            </thead>
            <tbody class="corps-tableau">
              {#each manquantes as e (e.personne_id)}
                <tr>
                  <td class="whitespace-nowrap px-3 py-1.5 text-xs font-medium">{e.classe}</td>
                  <td class="px-3 py-1.5 font-medium">{e.nom}</td>
                  <td class="px-3 py-1.5">{e.prenom}</td>
                  <td class="px-3 py-1.5 text-xs text-stone-500">{e.site ?? "—"}</td>
                  <td class="px-3 py-1.5 text-right font-mono text-xs tabular-nums text-stone-500">
                    {e.badge ?? "—"}
                  </td>
                  <td class="px-3 py-1.5 font-mono text-[11px]">
                    {#if e.pistes?.length}
                      <span class="text-amber-700 dark:text-amber-400">
                        à trancher : {e.pistes.join(" · ")}
                      </span>
                    {:else}
                      <span class="truncate text-stone-400">{e.chemin_attendu ?? ""}</span>
                    {/if}
                  </td>
                </tr>
              {/each}
            </tbody>
          </table>
        </div>
      </div>
    {/if}
  {/if}
</section>
