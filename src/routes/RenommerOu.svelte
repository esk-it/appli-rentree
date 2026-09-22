<script>
  /**
   * Les unités d'organisation Google passent à l'année suivante.
   *
   * ## Renommer plutôt que créer
   *
   * Google refuse un déplacement vers une unité absente, et le refuse
   * élève par élève sans nommer la cause. Il faut donc que l'arbre de la
   * nouvelle année existe avant la bascule.
   *
   * Le créer de zéro voudrait dire quatre-vingt-dix créations, puis
   * autant de suppressions l'an prochain. Renommer l'arbre de l'année
   * révolue coûte **trois gestes** — un par site — et emporte ses classes
   * avec lui : Google renomme le chemin, les sous-unités suivent.
   *
   * ## Pourquoi trois lignes et pas quatre-vingt-sept
   *
   * La maquette montre une ligne par classe. Ce serait faux : le
   * programme ne renomme pas les classes, il renomme l'arbre qui les
   * porte. Afficher quatre-vingt-sept lignes laisserait croire à
   * quatre-vingt-sept opérations indépendantes, dont on pourrait décocher
   * la moitié — or décocher une classe ne veut rien dire.
   *
   * Chaque ligne dit donc combien de classes elle emporte. Ce qui se
   * décoche, c'est un **site** : NDE n'a pas de KoXo et sa rentrée
   * décale, on ne renomme pas toujours les trois le même jour.
   *
   * ## Et ce que le renommage ne couvre pas
   *
   * Une classe qui n'existait pas l'an dernier n'a aucun chemin à
   * recycler : elle se crée. Le second bloc les liste — c'est la moitié
   * du travail que la maquette ne montrait pas, et l'oublier fait échouer
   * la bascule sur ces classes-là uniquement, ce qui est le pire des cas
   * pour comprendre.
   */
  import { onMount, onDestroy } from "svelte";
  import { SvelteSet } from "svelte/reactivity";
  import FolderTree from "@lucide/svelte/icons/folder-tree";
  import ArrowRight from "@lucide/svelte/icons/arrow-right";
  import Search from "@lucide/svelte/icons/search";
  import Check from "@lucide/svelte/icons/check";
  import TriangleAlert from "@lucide/svelte/icons/triangle-alert";
  import FolderPlus from "@lucide/svelte/icons/folder-plus";
  import Bouton from "$lib/components/Bouton.svelte";
  import EnTetePage from "$lib/components/EnTetePage.svelte";
  import EtatVide from "$lib/components/EtatVide.svelte";
  import Pastille from "$lib/components/Pastille.svelte";
  import BarreAction from "$lib/components/BarreAction.svelte";
  import Progression from "$lib/components/Progression.svelte";
  import { annees as anneesApi, googleApi } from "$lib/api.js";
  import { notify } from "$lib/toasts.js";
  import { TEINTES } from "$lib/familles.js";

  let { onNaviguer } = $props();

  let listeAnnees = $state(/** @type {any[]} */ ([]));
  let anneeSource = $state("");
  let anneeCible = $state("");
  let rapport = $state(/** @type {any} */ (null));
  let occupe = $state(false);
  let job = $state(/** @type {any} */ (null));
  let sondage = null;

  /** Ce qu'on applique. Tout coché par défaut : c'est le cas courant. */
  let retenus = $state(new SvelteSet());

  let renommages = $derived(rapport?.renommages ?? []);
  let aCreer = $derived(rapport?.a_creer ?? []);
  let nbEmportees = $derived(
    renommages
      .filter((r) => retenus.has(r.ancien))
      .reduce((n, r) => n + r.nb_sous_ou, 0),
  );
  let nbRetenus = $derived(
    renommages.filter((r) => retenus.has(r.ancien)).length +
      aCreer.filter((c) => retenus.has(c)).length,
  );

  /** Le site d'un chemin : `/3. NDK/NDK2025` → `NDK`. */
  function siteDe(chemin) {
    const m = /^\/\d+\.\s*([^/]+)/.exec(chemin ?? "");
    return m ? m[1].trim() : "—";
  }

  onMount(async () => {
    try {
      listeAnnees = await anneesApi.lister();
      const triees = [...listeAnnees].sort((a, b) =>
        b.libelle.localeCompare(a.libelle),
      );
      // L'arbre porte l'année qui se termine : la rentrée préparée moins
      // deux pour la source — l'arbre qu'on vient de vider.
      const fin = triees[0]?.libelle?.split("-")?.[1];
      if (fin) {
        anneeCible = fin;
        anneeSource = String(Number(fin) - 2);
      }
    } catch (e) {
      notify.erreur(String(e).replace(/^Error:\s*/, ""));
    }
    await analyser();
  });

  onDestroy(() => arreter());

  async function analyser() {
    if (!anneeSource || !anneeCible) return;
    occupe = true;
    rapport = null;
    try {
      rapport = await googleApi.conformiteOu({ anneeSource, anneeCible });
      retenus.clear();
      for (const r of rapport.renommages) retenus.add(r.ancien);
      for (const c of rapport.a_creer) retenus.add(c);
      for (const a of rapport.avertissements ?? []) {
        notify.avertissement(a, { duree: 12000 });
      }
    } catch (e) {
      notify.erreur(String(e).replace(/^Error:\s*/, ""), { duree: 12000 });
    } finally {
      occupe = false;
    }
  }

  function basculer(cle) {
    if (retenus.has(cle)) retenus.delete(cle);
    else retenus.add(cle);
  }

  async function appliquer() {
    if (!nbRetenus) return;
    occupe = true;
    try {
      job = await googleApi.appliquerOu({
        anneeSource,
        anneeCible,
        seulement: [...retenus],
      });
      rapport = null;
      sonder();
    } catch (e) {
      notify.erreur(String(e).replace(/^Error:\s*/, ""), { duree: 12000 });
    } finally {
      occupe = false;
    }
  }

  function sonder() {
    arreter();
    sondage = setInterval(async () => {
      if (!job) return arreter();
      try {
        job = await googleApi.suivreJob(job.id);
        if (job.est_termine) {
          arreter();
          notify.info(
            `${job.nb_reussies} réussie(s), ${job.nb_echecs} échec(s) sur ${job.total}`,
            { duree: 9000 },
          );
          await analyser();
        }
      } catch (e) {
        arreter();
        notify.erreur(String(e).replace(/^Error:\s*/, ""));
      }
    }, 700);
  }

  function arreter() {
    if (sondage) clearInterval(sondage);
    sondage = null;
  }
</script>

<section class="flex min-h-[calc(100vh-10rem)] flex-col space-y-5">
  <EnTetePage
    icon={FolderTree}
    titre="Renommer les OU pour la nouvelle année"
    description="Les unités d'organisation de chaque site passent à l'année visée, et emportent leurs classes. Ce qui n'existait pas l'an dernier se crée."
  />

  <!-- ------------------------------------------------------------------
       De quelle année vers quelle année, et combien ça fait.
       ------------------------------------------------------------------ -->
  <div class="flex flex-wrap items-end gap-5 border-b border-stone-200 pb-5 dark:border-stone-800">
    <div>
      <label class="libelle-champ" for="an-source">De</label>
      <input
        id="an-source"
        class="champ mt-1 w-32 font-mono font-bold"
        bind:value={anneeSource}
        onchange={analyser}
      />
    </div>
    <ArrowRight class="mb-2.5 h-5 w-5 shrink-0 text-stone-400" />
    <div>
      <label class="libelle-champ" for="an-cible">Vers</label>
      <input
        id="an-cible"
        class="champ mt-1 w-32 !border-2 font-mono font-bold"
        style="border-color: {TEINTES.rentree};"
        bind:value={anneeCible}
        onchange={analyser}
      />
    </div>
    <Bouton icon={Search} occupe={occupe} onclick={analyser}>Relire Google</Bouton>

    {#if rapport}
      <div class="ml-auto flex items-end gap-8 text-right">
        <div>
          <p class="titre-affiche text-3xl leading-none" style="color: {TEINTES.rentree};">
            {renommages.length}
          </p>
          <p class="text-xs text-stone-600 dark:text-stone-400">
            arbre{renommages.length > 1 ? "s" : ""} à renommer
          </p>
        </div>
        <div>
          <p class="titre-affiche text-3xl leading-none" style="color: {TEINTES.google};">
            {aCreer.length}
          </p>
          <p class="text-xs text-stone-600 dark:text-stone-400">
            unité{aCreer.length > 1 ? "s" : ""} à créer
          </p>
        </div>
      </div>
    {/if}
  </div>

  {#if job}
    <!-- Le travail en cours : Google renomme une unité à la fois. -->
    <div class="card space-y-3 p-4">
      <p class="text-sm font-semibold">{job.libelle}</p>
      <Progression valeur={job.nb_traitees} total={job.total} />
      <p class="text-xs text-stone-600 dark:text-stone-400">
        {job.nb_reussies} réussie(s) · {job.nb_echecs} échec(s) sur {job.total}
      </p>
      {#each (job.operations ?? []).filter((o) => o.est_terminee && !o.reussie) as o (o.libelle)}
        <p class="text-xs text-red-700 dark:text-red-300">
          <strong>{o.libelle}</strong> — {o.message}
        </p>
      {/each}
      {#if job.est_termine}
        <Bouton onclick={() => (job = null)}>Fermer</Bouton>
      {/if}
    </div>
  {:else if !rapport}
    <p class="py-10 text-center text-sm text-stone-500 dark:text-stone-400">
      Lecture de l'arborescence Google…
    </p>
  {:else if !renommages.length && !aCreer.length}
    <EtatVide
      icon={Check}
      titre="L'arborescence est déjà à l'année visée"
      message="Chaque classe de la table de correspondance a son unité dans Google. Rien à renommer, rien à créer."
    />
  {:else}
    <div class="min-h-0 flex-1 space-y-8 overflow-y-auto">
      {#if renommages.length}
        <div>
          <h2 class="titre-affiche mb-1 text-xl">Les arbres à renommer</h2>
          <p class="mb-3 text-[13px] text-stone-600 dark:text-stone-400">
            Un renommage emporte toutes les classes qu'il contient : c'est un
            geste par site, pas un par classe.
          </p>

          <div class="grid grid-cols-[36px_70px_minmax(0,1fr)_24px_minmax(0,1fr)_130px_100px] items-center gap-3 border-b border-stone-200 py-2 dark:border-stone-800">
            <span></span>
            <span class="libelle-champ">Site</span>
            <span class="libelle-champ">Avant</span>
            <span></span>
            <span class="libelle-champ">Après</span>
            <span class="libelle-champ">Classes emportées</span>
            <span class="libelle-champ">État</span>
          </div>

          {#each renommages as r (r.ancien)}
            <div class="grid grid-cols-[36px_70px_minmax(0,1fr)_24px_minmax(0,1fr)_130px_100px] items-center gap-3 border-b border-stone-100 py-3 text-sm dark:border-stone-800/70">
              <input
                type="checkbox"
                class="h-4 w-4 accent-emerald-600"
                aria-label="Renommer {r.ancien}"
                checked={retenus.has(r.ancien)}
                onchange={() => basculer(r.ancien)}
              />
              <span class="font-semibold">{siteDe(r.ancien)}</span>
              <span class="min-w-0 truncate font-mono text-xs text-stone-500 line-through dark:text-stone-400">
                {r.ancien}
              </span>
              <ArrowRight class="h-4 w-4 shrink-0 text-stone-400" />
              <span
                class="min-w-0 truncate font-mono text-xs font-bold"
                style="color: {TEINTES.rentree};"
              >
                {r.nouveau}
              </span>
              <span class="tabular-nums text-stone-600 dark:text-stone-400">
                {r.nb_sous_ou} classe{r.nb_sous_ou > 1 ? "s" : ""}
              </span>
              {#if r.utile}
                <Pastille etat="pret" texte="Prêt" />
              {:else}
                <!-- Le chemin d'arrivée n'est réclamé par aucune classe de la
                     Table : c'est la Table qui n'a pas tourné, pas Google qui
                     a du retard. Renommer déplacerait un arbre que rien ne
                     vient chercher. -->
                <Pastille etat="attente" texte="Rien ne l'attend" />
              {/if}
            </div>
          {/each}

          {#if renommages.some((r) => !r.utile)}
            <div class="mt-3 flex items-start gap-2.5 rounded-xl bg-amber-50 p-3 dark:bg-amber-400/10">
              <TriangleAlert class="mt-0.5 h-4 w-4 shrink-0 text-amber-600 dark:text-amber-400" />
              <p class="text-[13px] text-amber-900 dark:text-amber-200">
                Une ligne « rien ne l'attend » vise un chemin qu'aucune classe
                de la table de correspondance ne réclame. C'est la
                <button
                  class="font-semibold underline"
                  onclick={() => onNaviguer?.("table_correspondance")}
                >table</button>
                qui n'a pas encore tourné vers {anneeCible} — la renommer quand
                même déplacerait un arbre que personne ne viendra chercher.
              </p>
            </div>
          {/if}
        </div>
      {/if}

      {#if aCreer.length}
        <div>
          <h2 class="titre-affiche mb-1 text-xl">Les unités à créer</h2>
          <p class="mb-3 text-[13px] text-stone-600 dark:text-stone-400">
            Aucun chemin de l'an dernier ne leur correspond — une classe
            nouvelle, un niveau qui apparaît. Elles se créent après les
            renommages, parent avant enfant.
          </p>

          <div class="grid grid-cols-[36px_70px_minmax(0,1fr)_100px] items-center gap-3 border-b border-stone-200 py-2 dark:border-stone-800">
            <span></span>
            <span class="libelle-champ">Site</span>
            <span class="libelle-champ">Chemin</span>
            <span class="libelle-champ">État</span>
          </div>

          {#each aCreer as c (c)}
            <div class="grid grid-cols-[36px_70px_minmax(0,1fr)_100px] items-center gap-3 border-b border-stone-100 py-2.5 text-sm dark:border-stone-800/70">
              <input
                type="checkbox"
                class="h-4 w-4 accent-emerald-600"
                aria-label="Créer {c}"
                checked={retenus.has(c)}
                onchange={() => basculer(c)}
              />
              <span class="font-semibold">{siteDe(c)}</span>
              <span
                class="flex min-w-0 items-center gap-2 truncate font-mono text-xs font-bold"
                style="color: {TEINTES.google};"
              >
                <FolderPlus class="h-3.5 w-3.5 shrink-0" />
                {c}
              </span>
              <Pastille etat="attente" texte="À créer" />
            </div>
          {/each}
        </div>
      {/if}
    </div>

    <BarreAction
      message="Rien n'est modifié tant que tu n'as pas validé. Aucune unité n'est supprimée : une OU devenue inutile peut encore contenir des comptes."
    >
      <span class="text-sm text-stone-600 dark:text-stone-400">
        {nbEmportees} classe{nbEmportees > 1 ? "s" : ""} emportée{nbEmportees > 1 ? "s" : ""}
      </span>
      <Bouton
        variante="primary"
        icon={Check}
        occupe={occupe}
        disabled={nbRetenus === 0}
        onclick={appliquer}
      >
        Appliquer {nbRetenus} opération{nbRetenus > 1 ? "s" : ""}
      </Bouton>
    </BarreAction>
  {/if}
</section>
