<script>
  import FolderTree from "@lucide/svelte/icons/folder-tree";
  import Users from "@lucide/svelte/icons/users";
  import AlertTriangle from "@lucide/svelte/icons/alert-triangle";
  import Check from "@lucide/svelte/icons/check";
  import X from "@lucide/svelte/icons/x";
  import Eye from "@lucide/svelte/icons/eye";
  import Send from "@lucide/svelte/icons/send";
  import Bouton from "$lib/components/Bouton.svelte";
  import Modale from "$lib/components/Modale.svelte";
  import { googleApi } from "$lib/api.js";
  import { notify } from "$lib/toasts.js";

  /**
   * Déplacer dans Google ce qu'on a désigné : une personne, ou une sélection.
   *
   * ## Pourquoi trois temps, et pas un bouton
   *
   * Choisir la destination, la relire appliquée à des noms, puis confirmer.
   * La bascule peut se permettre un seul geste parce qu'elle calcule la
   * destination : il n'y a rien à vérifier qui ne le soit déjà dans la Table.
   * Ici la destination est tapée par quelqu'un, et une OU mal recopiée sort
   * une classe entière de son arborescence. L'aperçu est la seule barrière,
   * donc il n'est pas facultatif : le bouton d'application reste fermé tant
   * qu'aucun plan n'a été lu.
   *
   * ## Pourquoi l'aperçu se périme
   *
   * Changer une destination après avoir lu un plan rendrait ce plan
   * mensonger — on confirmerait un texte qui ne décrit plus ce qui partirait.
   * Toute modification efface donc l'aperçu et referme le bouton.
   *
   * @typedef {Object} Props
   * @property {{id: number, nom?: string, prenom?: string, classe?: string}[]} personnes
   * @property {number|null} [anneeId]  - pour afficher la classe en cours
   * @property {number|null} [siteId]   - restreint les destinations proposées
   * @property {() => void} onFermer
   * @property {() => void} [onApplique] - le parent rafraîchit sa liste
   */
  /** @type {Props} */
  let { personnes, anneeId = null, siteId = null, onFermer, onApplique } = $props();

  let destinations = $state(/** @type {any} */ (null));
  let chargeDest = $state(true);

  let ouDestination = $state("");
  let groupesAjouter = $state(/** @type {string[]} */ ([]));
  let groupesRetirer = $state(/** @type {string[]} */ ([]));
  let choixAjout = $state("");
  let choixRetrait = $state("");

  let plan = $state(/** @type {any} */ (null));
  let chargePlan = $state(false);
  let job = $state(/** @type {any} */ (null));
  let sondage = /** @type {any} */ (null);
  let envoi = $state(false);

  let ids = $derived(personnes.map((p) => p.id));
  let titre = $derived(
    personnes.length === 1
      ? `Déplacer ${personnes[0].prenom ?? ""} ${personnes[0].nom ?? ""}`.trim()
      : `Déplacer ${personnes.length} personnes dans Google`,
  );

  /** Rien de demandé : ni OU, ni groupe. Le plan n'aurait rien à dire. */
  let riensDemande = $derived(
    !ouDestination.trim() && !groupesAjouter.length && !groupesRetirer.length,
  );

  /**
   * Les destinations de la Table d'abord, le reste de l'arbre ensuite.
   * Neuf déplacements sur dix visent une classe déjà déclarée ; la faire
   * chercher parmi trois cents OU serait la cacher.
   */
  let ouProposees = $derived.by(() => {
    if (!destinations) return [];
    const declarees = destinations.ou_declarees ?? [];
    const reste = (destinations.ou ?? []).filter((o) => !declarees.includes(o));
    return [
      { groupe: "Déclarées dans la Table", options: declarees },
      { groupe: "Autres unités", options: reste },
    ].filter((g) => g.options.length);
  });

  let groupesProposes = $derived.by(() => {
    if (!destinations) return [];
    const declares = destinations.groupes_declares ?? [];
    const tous = (destinations.groupes ?? []).map((g) => g.adresse);
    const reste = tous.filter((a) => !declares.includes(a));
    return [
      { groupe: "Déclarés dans la Table", options: declares },
      { groupe: "Autres groupes", options: reste },
    ].filter((g) => g.options.length);
  });

  /**
   * Les groupes où la sélection se trouve déjà — proposés en un clic à la
   * sortie. Sans ce raccourci, sortir un élève de sa classe supposerait de
   * connaître par cœur l'adresse du groupe où il est.
   */
  let groupesActuelsConnus = $derived.by(() => {
    if (!plan) return [];
    const complets = plan.etats.some((e) => e.groupes_complets);
    if (!complets) return [];
    const vus = new Set();
    for (const e of plan.etats) for (const g of e.groupes_actuels) vus.add(g);
    return [...vus].filter((g) => !groupesRetirer.includes(g)).sort();
  });

  $effect(() => {
    charger();
    return () => arreterSondage();
  });

  async function charger() {
    chargeDest = true;
    try {
      destinations = await googleApi.destinationsDeplacement(siteId);
      // Une personne seule : on montre d'emblée où elle est, avant même
      // qu'une destination soit choisie. C'est souvent toute la question.
      if (personnes.length === 1) await apercu({ silencieux: true });
    } catch (e) {
      notify.erreur(String(e).replace(/^Error:\s*/, ""));
    } finally {
      chargeDest = false;
    }
  }

  /** Toute modification périme l'aperçu : voir l'en-tête. */
  function invalider() {
    plan = null;
  }

  function ajouterChip(liste, valeur) {
    const v = (valeur ?? "").trim().toLowerCase();
    if (!v || liste.includes(v)) return liste;
    invalider();
    return [...liste, v];
  }

  async function apercu({ silencieux = false } = {}) {
    chargePlan = true;
    try {
      plan = await googleApi.planDeplacement({
        personneIds: ids,
        anneeId,
        siteId,
        ouDestination: ouDestination.trim() || null,
        groupesAjouter,
        groupesRetirer,
      });
    } catch (e) {
      plan = null;
      if (!silencieux) notify.erreur(String(e).replace(/^Error:\s*/, ""));
    } finally {
      chargePlan = false;
    }
  }

  async function appliquer() {
    if (!plan?.est_executable) return;
    envoi = true;
    try {
      job = await googleApi.executerDeplacement({
        personneIds: ids,
        anneeId,
        siteId,
        ouDestination: ouDestination.trim() || null,
        groupesAjouter,
        groupesRetirer,
      });
      demarrerSondage();
    } catch (e) {
      notify.erreur(String(e).replace(/^Error:\s*/, ""));
    } finally {
      envoi = false;
    }
  }

  function demarrerSondage() {
    arreterSondage();
    sondage = setInterval(async () => {
      if (!job) return arreterSondage();
      try {
        job = await googleApi.suivreJob(job.id);
        if (!job.est_termine) return;
        arreterSondage();
        if (job.nb_echecs === 0) {
          notify.succes(`${job.nb_reussies} opération(s) appliquée(s)`);
        } else {
          notify.erreur(`${job.nb_echecs} échec(s) sur ${job.total}`);
        }
        onApplique?.();
        // L'état a changé : le plan d'avant ne décrit plus rien.
        plan = null;
      } catch (e) {
        arreterSondage();
        notify.erreur(String(e).replace(/^Error:\s*/, ""));
      }
    }, 700);
  }

  function arreterSondage() {
    if (sondage) clearInterval(sondage);
    sondage = null;
  }

  const LIBELLE_ACTION = {
    deplacer: "Unité",
    ajouter_groupe: "Entre",
    retirer_groupe: "Sort",
  };
</script>

<Modale {titre} largeur="xl" {onFermer}>
  {#if chargeDest}
    <p class="text-sm text-stone-500">Lecture de l'annuaire Google…</p>
  {:else if !destinations}
    <p class="text-sm text-red-600 dark:text-red-400">
      Destinations illisibles — l'API Google est-elle configurée ?
    </p>
  {:else}
    <!-- Qui -->
    <div class="rounded-lg bg-stone-50 p-3 text-sm dark:bg-stone-800/50">
      <span class="font-medium">{personnes.length}</span>
      personne{personnes.length > 1 ? "s" : ""} sélectionnée{personnes.length > 1 ? "s" : ""}
      {#if personnes.length <= 12}
        <span class="text-stone-500">
          — {personnes.map((p) => `${p.nom ?? ""} ${p.prenom ?? ""}`.trim()).join(", ")}
        </span>
      {/if}
    </div>

    <!-- Unité d'organisation -->
    <div>
      <label for="ou-dest" class="mb-1 flex items-center gap-1.5 text-sm font-medium">
        <FolderTree class="h-4 w-4" /> Unité d'organisation
      </label>
      <input
        id="ou-dest"
        list="ou-possibles"
        bind:value={ouDestination}
        oninput={invalider}
        placeholder="Laisser vide pour ne pas changer d'unité"
        class="w-full rounded-lg border border-stone-300 px-3 py-2 font-mono text-sm
               dark:border-stone-600 dark:bg-stone-900"
      />
      <datalist id="ou-possibles">
        {#each ouProposees as g (g.groupe)}
          {#each g.options as o (o)}
            <option value={o}>{g.groupe}</option>
          {/each}
        {/each}
      </datalist>
    </div>

    <!-- Groupes -->
    <div class="grid gap-3 sm:grid-cols-2">
      <div>
        <label for="grp-add" class="mb-1 flex items-center gap-1.5 text-sm font-medium">
          <Users class="h-4 w-4" /> Faire entrer dans
        </label>
        <select
          id="grp-add"
          bind:value={choixAjout}
          onchange={() => {
            groupesAjouter = ajouterChip(groupesAjouter, choixAjout);
            choixAjout = "";
          }}
          class="w-full rounded-lg border border-stone-300 px-3 py-2 text-sm
                 dark:border-stone-600 dark:bg-stone-900"
        >
          <option value="">Choisir un groupe…</option>
          {#each groupesProposes as g (g.groupe)}
            <optgroup label={g.groupe}>
              {#each g.options as o (o)}<option value={o}>{o}</option>{/each}
            </optgroup>
          {/each}
        </select>
        {#if groupesAjouter.length}
          <div class="mt-2 flex flex-wrap gap-1">
            {#each groupesAjouter as g (g)}
              <button
                type="button"
                class="flex items-center gap-1 rounded-full bg-emerald-100 px-2 py-0.5
                       text-xs text-emerald-800 dark:bg-emerald-900/40 dark:text-emerald-300"
                onclick={() => {
                  groupesAjouter = groupesAjouter.filter((x) => x !== g);
                  invalider();
                }}
              >
                {g} <X class="h-3 w-3" />
              </button>
            {/each}
          </div>
        {/if}
      </div>

      <div>
        <label for="grp-del" class="mb-1 flex items-center gap-1.5 text-sm font-medium">
          <Users class="h-4 w-4" /> Faire sortir de
        </label>
        <select
          id="grp-del"
          bind:value={choixRetrait}
          onchange={() => {
            groupesRetirer = ajouterChip(groupesRetirer, choixRetrait);
            choixRetrait = "";
          }}
          class="w-full rounded-lg border border-stone-300 px-3 py-2 text-sm
                 dark:border-stone-600 dark:bg-stone-900"
        >
          <option value="">Choisir un groupe…</option>
          {#each groupesProposes as g (g.groupe)}
            <optgroup label={g.groupe}>
              {#each g.options as o (o)}<option value={o}>{o}</option>{/each}
            </optgroup>
          {/each}
        </select>
        {#if groupesActuelsConnus.length}
          <p class="mt-1.5 text-xs text-stone-500">
            Actuellement :
            {#each groupesActuelsConnus as g (g)}
              <button
                type="button"
                class="mr-1 underline decoration-dotted hover:text-red-600"
                onclick={() => (groupesRetirer = ajouterChip(groupesRetirer, g))}
              >{g}</button>
            {/each}
          </p>
        {/if}
        {#if groupesRetirer.length}
          <div class="mt-2 flex flex-wrap gap-1">
            {#each groupesRetirer as g (g)}
              <button
                type="button"
                class="flex items-center gap-1 rounded-full bg-red-100 px-2 py-0.5
                       text-xs text-red-800 dark:bg-red-900/40 dark:text-red-300"
                onclick={() => {
                  groupesRetirer = groupesRetirer.filter((x) => x !== g);
                  invalider();
                }}
              >
                {g} <X class="h-3 w-3" />
              </button>
            {/each}
          </div>
        {/if}
      </div>
    </div>

    <!-- Où se trouve la personne, avant toute destination choisie. C'est
         la question qu'on se pose en ouvrant une fiche. -->
    {#if plan && personnes.length === 1 && plan.etats.length === 1 && !plan.etats[0].motif}
      <div class="rounded-lg bg-stone-50 p-3 text-xs dark:bg-stone-800/50">
        <p>
          <span class="text-stone-500">Unité actuelle :</span>
          <span class="font-mono">{plan.etats[0].ou_actuelle ?? "—"}</span>
        </p>
        {#if plan.etats[0].groupes_complets}
          <p class="mt-1">
            <span class="text-stone-500">Groupes :</span>
            {plan.etats[0].groupes_actuels.join(", ") || "aucun"}
          </p>
        {/if}
      </div>
    {/if}

    <!-- Aperçu -->
    {#if plan && !riensDemande}
      {#if plan.destinations_absentes.length}
        <div class="rounded-lg border border-red-300 bg-red-50 p-3 text-sm
                    dark:border-red-800 dark:bg-red-950/40">
          <p class="flex items-center gap-1.5 font-medium text-red-800 dark:text-red-300">
            <AlertTriangle class="h-4 w-4" /> Destination inexistante dans Google
          </p>
          <ul class="mt-1 list-inside list-disc font-mono text-xs text-red-700 dark:text-red-400">
            {#each plan.destinations_absentes as d (d)}<li>{d}</li>{/each}
          </ul>
          <p class="mt-1 text-xs text-red-700 dark:text-red-400">
            Rien ne partira tant qu'elle n'existe pas — la créer, ou corriger l'adresse.
          </p>
        </div>
      {/if}

      <div class="flex flex-wrap gap-3 rounded-lg bg-stone-50 p-3 text-sm dark:bg-stone-800/50">
        <span><strong>{plan.nb_deplacements}</strong> déplacement(s)</span>
        <span><strong class="text-emerald-700 dark:text-emerald-400">{plan.nb_entrees_groupe}</strong> entrée(s)</span>
        <span><strong class="text-red-700 dark:text-red-400">{plan.nb_sorties_groupe}</strong> sortie(s)</span>
        {#if plan.nb_deja_en_place}
          <span class="text-stone-500">{plan.nb_deja_en_place} déjà en place</span>
        {/if}
        {#if plan.etats.filter((e) => e.motif).length}
          <span class="text-amber-700 dark:text-amber-400">
            {plan.etats.filter((e) => e.motif).length} écartée(s)
          </span>
        {/if}
      </div>

      {#each plan.avertissements as a (a)}
        <p class="flex items-start gap-1.5 text-xs text-amber-700 dark:text-amber-400">
          <AlertTriangle class="mt-0.5 h-3.5 w-3.5 shrink-0" />{a}
        </p>
      {/each}

      {#if plan.mouvements.length}
        <div class="max-h-56 overflow-y-auto rounded-lg border border-stone-200 dark:border-stone-700">
          <table class="w-full text-xs">
            <tbody>
              {#each plan.mouvements as m, i (i)}
                <tr class="border-b border-stone-100 last:border-0 dark:border-stone-800">
                  <td class="w-16 px-2 py-1 text-stone-500">{LIBELLE_ACTION[m.action]}</td>
                  <td class="px-2 py-1">{m.libelle}</td>
                </tr>
              {/each}
            </tbody>
          </table>
        </div>
      {/if}

      {#if plan.etats.some((e) => e.motif)}
        <details class="text-xs">
          <summary class="cursor-pointer text-amber-700 dark:text-amber-400">
            Personnes écartées, et pourquoi
          </summary>
          <ul class="mt-1 space-y-0.5 pl-4">
            {#each plan.etats.filter((e) => e.motif) as e (e.personne_id)}
              <li>
                <span class="font-medium">{e.nom} {e.prenom}</span>
                <span class="text-stone-500">— {e.motif}</span>
              </li>
            {/each}
          </ul>
        </details>
      {/if}

    {/if}

    <!-- Exécution -->
    {#if job}
      <div class="rounded-lg border border-stone-200 p-3 dark:border-stone-700">
        <div class="mb-2 flex items-center justify-between text-sm">
          <span class="font-medium">{job.libelle}</span>
          <span class="tabular-nums text-stone-500">{job.nb_traitees} / {job.total}</span>
        </div>
        <div class="h-2 overflow-hidden rounded-full bg-stone-200 dark:bg-stone-700">
          <div
            class="h-full transition-all duration-300 {job.nb_echecs > 0
              ? 'bg-amber-500'
              : 'bg-emerald-500'}"
            style="width: {Math.round(job.progression * 100)}%"
          ></div>
        </div>
        {#if job.est_termine}
          <p class="mt-2 flex items-center gap-1.5 text-xs">
            <Check class="h-3.5 w-3.5 text-emerald-600" />
            {job.nb_reussies} appliquée(s){job.nb_echecs ? `, ${job.nb_echecs} en échec` : ""}
          </p>
        {/if}
        {#if job.nb_echecs > 0}
          <ul class="mt-1 space-y-0.5 text-xs text-red-700 dark:text-red-400">
            {#each job.etapes.filter((e) => e.statut === "echec") as e (e.index)}
              <li>{e.libelle} — {e.message}</li>
            {/each}
          </ul>
        {/if}
      </div>
    {/if}
  {/if}

  {#snippet actions()}
    <Bouton onclick={onFermer}>Fermer</Bouton>
    <Bouton
      icon={Eye}
      occupe={chargePlan}
      disabled={riensDemande || (job && !job.est_termine)}
      onclick={() => apercu()}
    >
      Aperçu
    </Bouton>
    <Bouton
      variante="primary"
      icon={Send}
      occupe={envoi}
      disabled={!plan?.est_executable || (job && !job.est_termine)}
      onclick={appliquer}
    >
      Appliquer{plan?.nb_total ? ` (${plan.nb_total})` : ""}
    </Bouton>
  {/snippet}
</Modale>
