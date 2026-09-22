<script>
  /**
   * Les groupes de classe Google, et qui doit y entrer ou en sortir.
   *
   * ## Ce que la maquette montrait, et ce qui se passe vraiment
   *
   * La maquette fait glisser un groupe entier vers le suivant — « Groupe
   * 6e A → Groupe 5e A ». Ce serait vrai d'un établissement où une classe
   * monte d'un bloc. Ici les classes sont recomposées chaque été : les
   * vingt-huit élèves de 6e A se répartissent entre quatre cinquièmes.
   *
   * Le groupe ne se déplace donc pas — il **gagne et perd des membres**.
   * Chaque ligne dit combien entrent et combien sortent, et c'est cette
   * différence qui se lit d'un coup d'œil.
   *
   * ## L'export CSV n'enlève jamais personne
   *
   * C'est la raison d'être de cet écran. Le fichier d'import de Google
   * ajoute des membres et ne sait pas en retirer : un groupe de sixième
   * garde ses promotions passées, année après année. Seule la
   * synchronisation par l'API fait les deux sens.
   *
   * ## Deux prudences qui ne se négocient pas
   *
   * Un membre qu'aucune personne du référentiel ne porte — un professeur,
   * une adresse de service, un ajout fait à la main — n'est **jamais**
   * retiré : le programme ignore pourquoi il est là.
   *
   * Et si un site n'a aucun élève chargé, ses retraits sont suspendus :
   * ils ne viendraient pas d'un départ mais d'un export Charlemagne qu'on
   * n'a pas encore ingéré. Les appliquer viderait les groupes d'un site
   * entier sur la foi d'un fichier absent.
   */
  import { onMount, onDestroy } from "svelte";
  import { SvelteSet } from "svelte/reactivity";
  import UsersRound from "@lucide/svelte/icons/users-round";
  import Search from "@lucide/svelte/icons/search";
  import Check from "@lucide/svelte/icons/check";
  import Plus from "@lucide/svelte/icons/plus";
  import Minus from "@lucide/svelte/icons/minus";
  import TriangleAlert from "@lucide/svelte/icons/triangle-alert";
  import Bouton from "$lib/components/Bouton.svelte";
  import EnTetePage from "$lib/components/EnTetePage.svelte";
  import EtatVide from "$lib/components/EtatVide.svelte";
  import Pastille from "$lib/components/Pastille.svelte";
  import BarreAction from "$lib/components/BarreAction.svelte";
  import Squelette from "$lib/components/Squelette.svelte";
  import { annees as anneesApi, googleApi, sites as sitesApi } from "$lib/api.js";
  import { notify } from "$lib/toasts.js";
  import { TEINTES } from "$lib/familles.js";

  let listeAnnees = $state(/** @type {any[]} */ ([]));
  let listeSites = $state(/** @type {any[]} */ ([]));
  let anneeId = $state(/** @type {number | null} */ (null));
  let filtreSite = $state("");
  let recherche = $state("");

  let rapport = $state(/** @type {any} */ (null));
  let aCreer = $state(/** @type {any} */ (null));
  let occupe = $state(false);
  let chargement = $state(true);

  /** Les classes retenues. Seules celles qui bougent sont cochables. */
  let retenues = $state(new SvelteSet());
  /** Retirer, et pas seulement ajouter. Le seul vrai choix de l'écran. */
  let retirer = $state(true);

  let lignes = $derived.by(() => {
    let l = (rapport?.diffs ?? []).filter(
      (d) => d.a_ajouter.length || d.a_retirer.length || !d.existe,
    );
    if (filtreSite) l = l.filter((d) => d.site === filtreSite);
    const q = recherche.trim().toLowerCase();
    if (q) {
      l = l.filter(
        (d) =>
          d.classe.toLowerCase().includes(q) ||
          d.groupe.toLowerCase().includes(q),
      );
    }
    return l;
  });

  let nbAjouts = $derived(
    lignes
      .filter((d) => retenues.has(d.classe))
      .reduce((n, d) => n + d.a_ajouter.length, 0),
  );
  let nbRetraits = $derived(
    retirer
      ? lignes
          .filter((d) => retenues.has(d.classe))
          .reduce((n, d) => n + d.a_retirer.length, 0)
      : 0,
  );
  let sitesDispo = $derived([
    ...new Set((rapport?.diffs ?? []).map((d) => d.site).filter(Boolean)),
  ]);

  onMount(async () => {
    try {
      [listeAnnees, listeSites] = await Promise.all([
        anneesApi.lister(),
        sitesApi.lister(),
      ]);
      const triees = [...listeAnnees].sort((a, b) =>
        b.libelle.localeCompare(a.libelle),
      );
      anneeId = triees[0]?.id ?? null;
    } catch (e) {
      notify.erreur(String(e).replace(/^Error:\s*/, ""));
    } finally {
      chargement = false;
    }
    await analyser();
  });

  onDestroy(() => arreter());

  async function analyser() {
    if (!anneeId) return;
    occupe = true;
    rapport = null;
    try {
      [rapport, aCreer] = await Promise.all([
        googleApi.diffGroupes({ anneeId }),
        googleApi.groupesACreer({ anneeId }),
      ]);
      retenues.clear();
      for (const d of rapport.diffs) {
        if (d.a_ajouter.length || d.a_retirer.length) retenues.add(d.classe);
      }
      for (const a of rapport.avertissements ?? []) {
        notify.avertissement(a, { duree: 12000 });
      }
    } catch (e) {
      notify.erreur(String(e).replace(/^Error:\s*/, ""), { duree: 12000 });
    } finally {
      occupe = false;
    }
  }

  function basculer(classe) {
    if (retenues.has(classe)) retenues.delete(classe);
    else retenues.add(classe);
  }

  function toutCocher() {
    const bougeables = lignes.filter((d) => d.a_ajouter.length || d.a_retirer.length);
    if (bougeables.every((d) => retenues.has(d.classe))) {
      for (const d of bougeables) retenues.delete(d.classe);
    } else {
      for (const d of bougeables) retenues.add(d.classe);
    }
  }

  let job = $state(/** @type {any} */ (null));
  let sondage = null;

  async function synchroniser() {
    if (!retenues.size || !anneeId) return;
    occupe = true;
    try {
      job = await googleApi.synchroniserGroupes({
        anneeId,
        retirer,
        classes: [...retenues],
      });
      sonder();
    } catch (e) {
      notify.erreur(String(e).replace(/^Error:\s*/, ""), { duree: 12000 });
    } finally {
      occupe = false;
    }
  }

  async function creerLesGroupes() {
    if (!anneeId) return;
    occupe = true;
    try {
      // Seulement ceux dont l'absence bloque des élèves aujourd'hui : un
      // groupe déclaré pour une classe vide n'a personne à accueillir.
      job = await googleApi.creerGroupes({ anneeId, seulementUtiles: true });
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
    icon={UsersRound}
    titre="Déplacer de groupe Google"
    description="Les classes sont recomposées chaque été : un groupe ne se déplace pas, il gagne et perd des membres. L'export CSV ne sait qu'ajouter — seule cette synchronisation fait les deux sens."
  />

  {#if chargement}
    <Squelette variante="ligne-tableau" nb={5} colonnes={5} />
  {:else}
    <!-- ----------------------------------------------------------------
         Filtrer, et voir combien ça fait.
         ---------------------------------------------------------------- -->
    <div class="flex flex-wrap items-end gap-4 border-b border-stone-200 pb-5 dark:border-stone-800">
      <div>
        <label class="libelle-champ" for="an-gr">Année</label>
        <select
          id="an-gr"
          class="champ mt-1 w-40"
          bind:value={anneeId}
          onchange={analyser}
        >
          {#each listeAnnees as a (a.id)}<option value={a.id}>{a.libelle}</option>{/each}
        </select>
      </div>

      <div class="relative">
        <Search class="pointer-events-none absolute top-1/2 left-3 h-4 w-4 translate-y-1 text-stone-400" />
        <label class="libelle-champ" for="q-gr">Chercher</label>
        <input
          id="q-gr"
          class="champ mt-1 w-64 pl-9"
          placeholder="Une classe ou un groupe…"
          bind:value={recherche}
        />
      </div>

      {#if sitesDispo.length > 1}
        <div class="flex gap-2 pb-1">
          <button
            class="rounded-full px-4 py-1.5 text-[13px] font-semibold transition-colors
                   {filtreSite === ''
                     ? 'bg-stone-900 text-white dark:bg-stone-100 dark:text-stone-900'
                     : 'bg-stone-100 text-stone-600 dark:bg-stone-800 dark:text-stone-300'}"
            onclick={() => (filtreSite = "")}
          >
            Tous
          </button>
          {#each sitesDispo as s (s)}
            <button
              class="rounded-full px-4 py-1.5 text-[13px] font-semibold transition-colors
                     {filtreSite === s
                       ? 'bg-stone-900 text-white dark:bg-stone-100 dark:text-stone-900'
                       : 'bg-stone-100 text-stone-600 dark:bg-stone-800 dark:text-stone-300'}"
              onclick={() => (filtreSite = s)}
            >
              {s}
            </button>
          {/each}
        </div>
      {/if}

      <Bouton icon={Search} occupe={occupe} onclick={analyser}>Relire Google</Bouton>

      {#if rapport}
        <div class="ml-auto flex items-end gap-8 text-right">
          <div>
            <p class="titre-affiche text-3xl leading-none" style="color: {TEINTES.koxo};">
              {rapport.nb_a_ajouter}
            </p>
            <p class="text-xs text-stone-600 dark:text-stone-400">à ajouter</p>
          </div>
          <div>
            <p class="titre-affiche text-3xl leading-none" style="color: var(--color-amber-600);">
              {rapport.nb_a_retirer}
            </p>
            <p class="text-xs text-stone-600 dark:text-stone-400">à retirer</p>
          </div>
        </div>
      {/if}
    </div>

    {#if job}
      <div class="card space-y-2 p-4">
        <p class="text-sm font-semibold">{job.libelle}</p>
        <div class="h-2 overflow-hidden rounded-full bg-stone-200 dark:bg-stone-800">
          <div
            class="h-full rounded-full transition-all"
            style="width: {Math.round((job.progression ?? 0) * 100)}%; background: {TEINTES.google};"
          ></div>
        </div>
        <p class="text-xs text-stone-600 dark:text-stone-400">
          {job.nb_reussies} réussie(s) · {job.nb_echecs} échec(s) sur {job.total}
        </p>
        {#if job.est_termine}
          <Bouton onclick={() => (job = null)}>Fermer</Bouton>
        {/if}
      </div>
    {:else if !rapport}
      <p class="py-10 text-center text-sm text-stone-500 dark:text-stone-400">
        Lecture des groupes Google…
      </p>
    {:else}
      {#if aCreer?.nb_utiles}
        <!-- Un groupe absent retient ses ajouts : les élèves attendent un
             groupe qui n'existe pas encore. C'est à régler avant tout le
             reste, et d'un clic. -->
        <div class="flex flex-wrap items-center gap-3 rounded-xl bg-amber-50 p-4 dark:bg-amber-400/10">
          <TriangleAlert class="h-4 w-4 shrink-0 text-amber-600 dark:text-amber-400" />
          <p class="min-w-0 flex-1 text-[13px] text-amber-900 dark:text-amber-200">
            <strong>{aCreer.nb_utiles}</strong> groupe{aCreer.nb_utiles > 1 ? "s" : ""}
            déclaré{aCreer.nb_utiles > 1 ? "s" : ""} dans la table que Google ne
            connaît pas — <strong>{aCreer.nb_membres_bloques}</strong> élève(s)
            attendent d'y entrer. Les créer d'abord.
          </p>
          <Bouton icon={Plus} occupe={occupe} onclick={creerLesGroupes}>
            Créer les {aCreer.nb_utiles} groupes
          </Bouton>
        </div>
      {/if}

      {#if rapport.sites_sans_eleve?.length}
        <p class="rounded-xl bg-stone-100 p-3 text-[13px] text-stone-700 dark:bg-stone-800/60 dark:text-stone-300">
          Aucun élève chargé pour <strong>{rapport.sites_sans_eleve.join(", ")}</strong> :
          les retraits de ces sites sont suspendus. Ils ne viendraient pas d'un
          départ mais d'un export Charlemagne qu'on n'a pas encore ingéré.
        </p>
      {/if}

      {#if !lignes.length}
        <EtatVide
          icon={Check}
          titre="Chaque groupe a exactement ses élèves"
          message="Rien à ajouter, rien à retirer sur les classes affichées."
        />
      {:else}
        <div class="min-h-0 flex-1 overflow-y-auto">
          <div class="mb-2 flex items-center justify-between">
            <button class="btn-secondary text-xs" onclick={toutCocher}>
              Tout cocher / décocher
            </button>
            <label class="flex cursor-pointer items-center gap-2 text-sm">
              <input type="checkbox" class="h-4 w-4 accent-emerald-600" bind:checked={retirer} />
              Retirer aussi ceux qui n'y sont plus
            </label>
          </div>

          <div class="grid grid-cols-[36px_110px_minmax(0,1fr)_90px_90px_110px_110px] items-center gap-3 border-b border-stone-200 py-2 dark:border-stone-800">
            <span></span>
            <span class="libelle-champ">Classe</span>
            <span class="libelle-champ">Groupe</span>
            <span class="libelle-champ">Entrent</span>
            <span class="libelle-champ">Sortent</span>
            <span class="libelle-champ">Déjà membres</span>
            <span class="libelle-champ">État</span>
          </div>

          {#each lignes as d (d.groupe)}
            <div class="grid grid-cols-[36px_110px_minmax(0,1fr)_90px_90px_110px_110px] items-center gap-3 border-b border-stone-100 py-3 text-sm dark:border-stone-800/70">
              <span>
                {#if d.a_ajouter.length || d.a_retirer.length}
                  <input
                    type="checkbox"
                    class="h-4 w-4 accent-emerald-600"
                    aria-label="Synchroniser {d.classe}"
                    checked={retenues.has(d.classe)}
                    onchange={() => basculer(d.classe)}
                  />
                {/if}
              </span>
              <span class="font-semibold">{d.classe}</span>
              <span class="min-w-0 truncate font-mono text-xs text-stone-600 dark:text-stone-400">
                {d.groupe}
              </span>
              <span class="tabular-nums">
                {#if d.a_ajouter.length}
                  <span class="inline-flex items-center gap-0.5 font-bold" style="color: {TEINTES.koxo};">
                    <Plus class="h-3.5 w-3.5" />{d.a_ajouter.length}
                  </span>
                {:else}
                  <span class="text-stone-400">—</span>
                {/if}
              </span>
              <span class="tabular-nums">
                {#if d.a_retirer.length}
                  <span
                    class="inline-flex items-center gap-0.5 font-bold"
                    class:opacity-40={!retirer}
                    style="color: var(--color-amber-600);"
                  >
                    <Minus class="h-3.5 w-3.5" />{d.a_retirer.length}
                  </span>
                {:else}
                  <span class="text-stone-400">—</span>
                {/if}
              </span>
              <span class="tabular-nums text-stone-600 dark:text-stone-400">
                {d.deja_membres}
              </span>
              {#if !d.existe}
                <Pastille etat="ecart" texte="Groupe absent" />
              {:else if d.inconnus.length}
                <!-- Des profs, des adresses de service. Jamais retirés :
                     le programme ignore pourquoi ils sont là. -->
                <Pastille
                  etat="attente"
                  texte="{d.inconnus.length} hors référentiel"
                />
              {:else}
                <Pastille etat="pret" texte="Prêt" />
              {/if}
            </div>
          {/each}

          {#if rapport.nb_inconnus}
            <p class="mt-3 text-[13px] text-stone-500 dark:text-stone-400">
              <strong>{rapport.nb_inconnus}</strong> membre(s) qu'aucune personne
              du référentiel ne porte — professeurs, adresses de service, ajouts
              manuels. Ils ne sont jamais retirés : le programme ignore pourquoi
              ils sont là.
            </p>
          {/if}
        </div>

        <BarreAction
          message="Rien n'est modifié tant que tu n'as pas validé. L'export CSV, lui, ne sait qu'ajouter : un groupe garderait ses promotions passées."
        >
          <span class="text-sm text-stone-600 dark:text-stone-400">
            {nbAjouts} entrée{nbAjouts > 1 ? "s" : ""}
            {#if retirer}· {nbRetraits} sortie{nbRetraits > 1 ? "s" : ""}{/if}
          </span>
          <Bouton
            variante="primary"
            icon={Check}
            occupe={occupe}
            disabled={retenues.size === 0}
            onclick={synchroniser}
          >
            Synchroniser {retenues.size} groupe{retenues.size > 1 ? "s" : ""}
          </Bouton>
        </BarreAction>
      {/if}
    {/if}
  {/if}
</section>
