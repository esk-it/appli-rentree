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
  import Segments from "$lib/components/Segments.svelte";
  import Onglets from "$lib/components/Onglets.svelte";
  import Pastille from "$lib/components/Pastille.svelte";
  import { annees as anneesApi, photos } from "$lib/api.js";
  import { notify } from "$lib/toasts.js";
  import Progression from "$lib/components/Progression.svelte";
  import { TEINTES } from "$lib/familles.js";
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
  /**
   * Deux vues, et non un seul tas.
   *
   * « Manquante » et « à trancher » ne se règlent pas pareil : la
   * première demande une photo au professeur principal, la seconde
   * demande de renommer un fichier qui existe déjà. Mêlées, on relance
   * une famille pour une photo qui est sur le partage.
   */
  let vue = $state("absentes");
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

  let nbAbsentes = $derived(
    (inventaire?.manquantes ?? []).filter((e) => !e.pistes?.length).length,
  );
  let nbATrancher = $derived(
    (inventaire?.manquantes ?? []).filter((e) => e.pistes?.length).length,
  );

  let affichees = $derived(
    manquantes.filter((e) =>
      vue === "trancher" ? e.pistes?.length : !e.pistes?.length,
    ),
  );

  /** Les classes incomplètes, les pires d'abord — c'est l'ordre des relances. */
  let classes = $derived(
    (inventaire?.classes_incompletes ?? []).map((c) => ({
      code: c,
      sans: inventaire.par_classe[c]?.sans ?? 0,
      avec: inventaire.par_classe[c]?.avec ?? 0,
    })),
  );
</script>

<section class="space-y-6">
  <EnTetePage
    titre="Photos"
    description="Un accès disque par élève sur le partage réseau. Qui a sa photo, et surtout qui ne l'a pas — nommément, par classe, pour relancer les professeurs principaux."
  >
    {#snippet actions()}
      <Segments
        bind:valeur={population}
        taille="sm"
        options={[
          { id: "eleve", label: "Élèves" },
          { id: "adulte", label: "Adultes" },
        ]}
      />
      {#if inventaire && anneeId}
        <a class="btn-secondary !py-1.5 text-xs" href={photos.urlClasseur(anneeId, population)}>
          <Download class="h-3.5 w-3.5" /> La liste en classeur
        </a>
      {/if}
      <Bouton taille="sm" icon={RefreshCw} occupe={occupe} onclick={relever}>
        {inventaire ? "Relancer la vérification" : "Relever le partage"}
      </Bouton>
    {/snippet}
  </EnTetePage>

  {#if erreur}
    <p class="rounded-xl bg-red-50 px-4 py-3 text-sm text-red-700 dark:bg-red-500/10 dark:text-red-300">
      {erreur}
    </p>
  {/if}

  <!-- Le relevé lit deux mille fichiers sur un partage réseau : sans trace
       visible, l'écran paraît figé et l'on reclique. -->
  {#if occupe}
    <Progression
      libelle="Lecture du partage"
      detail="Chaque fichier du dossier est comparé aux élèves de l'année — quelques secondes."
      teinte={TEINTES.photos}
    />
  {/if}

  {#if !inventaire}
    <EtatVide
      icon={Camera}
      titre="Le partage n'a pas encore été relu"
      message="Un accès disque par personne, sur le réseau : c'est trop cher pour partir tout seul à chaque ouverture. Lance le relevé quand le partage est monté."
    />
  {:else}
    <!-- La date du relevé, en bandeau : un constat sans date laisse croire
         qu'il est de maintenant. -->
    <div class="flex items-center gap-3.5 rounded-xl bg-amber-50 px-4.5 py-3 text-sm dark:bg-amber-400/10">
      <span class="h-2.5 w-2.5 shrink-0 rounded-full bg-amber-500"></span>
      <span class="text-stone-800 dark:text-stone-200">
        Dernière vérification : <strong>{age || "à l'instant"}</strong>.
        À relancer quand des photos ont été déposées depuis.
      </span>
      <span class="ml-auto truncate font-mono text-xs text-stone-500 dark:text-stone-400">
        {inventaire.dossier}
      </span>
    </div>

    <!-- Les trois constats, en grands chiffres colorés. -->
    <div class="flex flex-wrap gap-14 border-b border-stone-200 pb-5 dark:border-stone-800">
      <div>
        <p class="titre-affiche text-[32px] leading-none tabular-nums" style="color: {TEINTES.koxo};">
          {inventaire.nb_avec}
        </p>
        <p class="mt-1 text-[13px] text-stone-600 dark:text-stone-400">
          photos trouvées sur {inventaire.nb_eleves}
        </p>
      </div>
      <div>
        <p
          class="titre-affiche text-[32px] leading-none tabular-nums"
          style="color: {nbAbsentes ? 'var(--color-red-700)' : 'var(--color-stone-400)'};"
        >
          {nbAbsentes}
        </p>
        <p class="mt-1 text-[13px] text-stone-600 dark:text-stone-400">manquantes</p>
      </div>
      <div>
        <p
          class="titre-affiche text-[32px] leading-none tabular-nums"
          style="color: {nbATrancher ? 'var(--color-amber-700)' : 'var(--color-stone-400)'};"
        >
          {nbATrancher}
        </p>
        <p class="mt-1 text-[13px] text-stone-600 dark:text-stone-400">à trancher</p>
      </div>
    </div>

    {#if inventaire.nb_sans === 0}
      <div class="flex items-center gap-3.5 py-6">
        <CheckCircle2 class="h-7 w-7 shrink-0" style="color: {TEINTES.koxo};" />
        <div>
          <p class="titre-affiche text-lg">Tout le monde a sa photo.</p>
          <p class="text-sm text-stone-600 dark:text-stone-400">
            {inventaire.nb_eleves} personnes, aucun fichier introuvable sur le partage.
          </p>
        </div>
      </div>
    {:else}
      <Onglets
        bind:valeur={vue}
        onglets={[
          { id: "absentes", label: "Manquantes", compte: nbAbsentes },
          { id: "trancher", label: "À trancher", compte: nbATrancher },
        ]}
      />

      <!-- Les filtres : c'est par classe qu'on relance, et par site qu'on
           répartit les relances entre collègues. -->
      <div class="flex flex-wrap items-center gap-x-4 gap-y-2">
        <div class="relative min-w-56 flex-1 sm:max-w-xs">
          <Search class="pointer-events-none absolute top-1/2 left-3 h-4 w-4 -translate-y-1/2 text-stone-400" />
          <input class="champ !py-1.5 pl-9 text-sm" placeholder="Nom ou prénom…" bind:value={recherche} />
        </div>
        {#if sites.length > 1}
          <div class="flex flex-wrap items-center gap-1.5">
            <span class="libelle-champ">Site</span>
            {#each [["", "Tous"], ...sites.map(([n]) => [n, n])] as [id, label] (id)}
              <button
                class="rounded-full border px-2.5 py-1 text-xs font-semibold transition-colors {siteRetenu === id
                  ? 'border-transparent text-white'
                  : 'border-stone-300 text-stone-600 hover:border-stone-400 dark:border-stone-700 dark:text-stone-300'}"
                style={siteRetenu === id ? `background: ${TEINTES.photos};` : ""}
                onclick={() => { siteRetenu = id; classeRetenue = ""; }}
              >
                {label}
              </button>
            {/each}
          </div>
        {/if}
        {#if classes.length}
          <div class="flex flex-wrap items-center gap-1.5">
            <span class="libelle-champ">{population === "adulte" ? "Site" : "Classe"}</span>
            {#each [["", "Toutes"], ...classes.map((c) => [c.code, `${c.code} ${c.sans}`])] as [id, label] (id)}
              <button
                class="rounded-full border px-2.5 py-1 font-mono text-xs font-semibold transition-colors {classeRetenue === id
                  ? 'border-transparent text-white'
                  : 'border-stone-300 text-stone-600 hover:border-stone-400 dark:border-stone-700 dark:text-stone-300'}"
                style={classeRetenue === id ? `background: ${TEINTES.photos};` : ""}
                onclick={() => (classeRetenue = id)}
              >
                {label}
              </button>
            {/each}
          </div>
        {/if}
      </div>

      <!-- Le tableau du tour 5 : des filets, pas de cadre. -->
      <div class="overflow-x-auto">
        <div class="min-w-[56rem]">
          <div class="grid grid-cols-[minmax(0,1fr)_110px_150px_minmax(0,1.4fr)_90px] items-center gap-3 border-b border-stone-200 py-2 dark:border-stone-800">
            <span class="libelle-champ">{population === "adulte" ? "Personne" : "Élève"}</span>
            <span class="libelle-champ">{population === "adulte" ? "Site" : "Classe"}</span>
            <span class="libelle-champ">Problème</span>
            <span class="libelle-champ">Détail</span>
            <span class="libelle-champ text-right">Badge</span>
          </div>

          <div class="max-h-[calc(100vh-30rem)] min-h-40 overflow-y-auto">
            {#each affichees as e (e.personne_id)}
              <div class="grid grid-cols-[minmax(0,1fr)_110px_150px_minmax(0,1.4fr)_90px] items-center gap-3 border-b border-stone-100 py-2.5 text-sm dark:border-stone-800/70">
                <span class="truncate">
                  <strong class="font-semibold">{e.nom}</strong>
                  <span class="text-stone-600 dark:text-stone-300">{e.prenom}</span>
                </span>
                <span class="truncate font-mono text-xs text-stone-600 dark:text-stone-400">
                  {e.classe}
                </span>
                <span>
                  {#if e.pistes?.length}
                    <Pastille etat="attente" texte="À trancher" />
                  {:else}
                    <Pastille etat="ecart" texte="Photo absente" />
                  {/if}
                </span>
                <span class="truncate font-mono text-[11px] text-stone-500 dark:text-stone-400">
                  {#if e.pistes?.length}
                    {e.pistes.join(" · ")}
                  {:else}
                    Aucun fichier dans le dossier
                  {/if}
                </span>
                <span class="text-right font-mono text-xs text-stone-500 tabular-nums dark:text-stone-400">
                  {e.badge ?? "—"}
                </span>
              </div>
            {/each}
            {#if !affichees.length}
              <p class="py-8 text-center text-sm text-stone-500 dark:text-stone-400">
                Aucune ligne pour ces filtres.
              </p>
            {/if}
          </div>
        </div>
      </div>

      <p class="text-[13px] text-stone-500 dark:text-stone-400">
        Le fichier est cherché sous « NOM Prénom », « NOM_Prénom », « Prénom NOM »
        et le numéro de badge. Une photo présente sous une autre forme n'est pas
        déclarée manquante — et un fichier revendiqué par deux homonymes n'est
        donné à personne, il passe « à trancher ».
      </p>
    {/if}
  {/if}
</section>
